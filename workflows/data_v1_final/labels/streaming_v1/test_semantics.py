"""Scientific boundary tests on tiny fixtures; never opens real scientific labels."""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import hashlib
import math
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest

from calibration import RadixCounts,TSQR,WinsorMoments,advance,float_key,initial_queries,key_float,merge_qr,train_values,weighted_spearman
from compact import bits,encode,reason_code,restore_mask,unpack
from normalization_gate import validate_authority
from support import budget,legacy,load,unique_bytes

CONFIG=None
BARRIER=None


def exact_quantile(values,p="0.5",mad_center=None):
    fields=[{"field_id":0}]
    request=initial_queries(fields,"MAD" if mad_center is not None else "median",{0:mad_center} if mad_center is not None else None,p)
    finished=[]
    for _ in range(8):
        hist=RadixCounts(request)
        hist.add(0,values)
        request,complete=advance(request,hist.rows());finished.extend(complete)
        if not request["fields"]:return finished[0]
    raise AssertionError("Radix refinement failed to resolve all 64 key bits")


def init_barrier(barrier):
    global BARRIER
    BARRIER=barrier


def barrier_task(i):
    BARRIER.wait(timeout=60)
    return os.getpid()


class CompactMaskTests(unittest.TestCase):
    def test_bitsets_cover_ids_above_64_and_reject_unassigned_bits(self):
        self.assertEqual(unpack(bits([0,64,145])),[0,64,145])
        with self.assertRaises(ValueError):bits([146])

    def test_partial_leaf_masks_roundtrip_without_normal_values(self):
        row={"field_id":145,"values_float64":[1.0,None,3.0],"source_value_mask":[True,False,True],
            "value_mask":[True,False,False],"source_reasons":["SOURCE_NONFINITE_OR_NONNUMERIC"],
            "new_reasons":["PHYSICAL_DEFINITION_RANGE"],"review_reasons":[]}
        encoded=encode(9,3,[row])
        self.assertEqual(restore_mask(encoded,145,3),row["value_mask"])
        self.assertNotIn("values_float64",encoded)
        self.assertEqual(unpack(encoded["newly_masked_fields"]),[145])

    def test_all_false_field_needs_no_leaf_index_copy(self):
        row={"field_id":0,"values_float64":[1.0]*1000,"source_value_mask":[True]*1000,"value_mask":[False]*1000,
            "source_reasons":[],"new_reasons":["EXPLICIT_ELECTRONIC_NONCONVERGENCE"],"review_reasons":[]}
        encoded=encode(7,0,[row])
        self.assertEqual(encoded["leaf_exceptions"],[])
        self.assertEqual(restore_mask(encoded,0,1000),[False]*1000)

    def test_unknown_convergence_status_is_review_not_decode_failure(self):
        self.assertEqual(reason_code("CALCULATION_FAILED_WITH_CONVERGENCE_EVIDENCE_UNKNOWN"),reason_code("OTHER_TASK_STATUS_WITH_CONVERGENCE_EVIDENCE_UNKNOWN"))

    def test_real_failure_aware_D20_null_names_remain_old_missing(self):
        common,masks=legacy(CONFIG)
        field={"field_id":0,"source_path":"MolLogP","component":"value","level":"molecule","registry_id":None,
            "physical_range":{"lower":None,"lower_exclusive":False,"upper":None}}
        row={"total_atoms":3,"status":"PROPERTY_FAILED","values_float64":[None]*20,"valid_mask":[False]*20,"descriptor_names":None}
        f,values,_,reason=next(common.task_components(row,"D20",[field]))
        source,a,b,sr,nr,review=masks.source_value_mask(f,row,values,reason)
        item={"field_id":0,"values_float64":values,"source_value_mask":a,"value_mask":b,
            "source_reasons":sr,"new_reasons":nr,"review_reasons":review}
        encoded=encode(1,0,[item])
        self.assertFalse(source);self.assertEqual(unpack(encoded["newly_masked_fields"]),[])

    def test_NULL_convergence_keeps_otherwise_valid_label(self):
        _,masks=legacy(CONFIG)
        field={"physical_range":{"lower":None,"lower_exclusive":False,"upper":None}}
        source,a,b,_,new,review=masks.source_value_mask(field,{"status":"SUCCESS","converged":None},[1.0],None)
        self.assertTrue(source);self.assertEqual(b,[True]);self.assertEqual(new,[])
        self.assertIn("SUCCESS_WITH_CONVERGENCE_EVIDENCE_UNKNOWN",review)


class ExactCalibrationTests(unittest.TestCase):
    def test_float_keys_preserve_numeric_order_and_pool_signed_zero(self):
        values=[-1e300,-2.0,-0.0,0.0,1e-300,1.0,1e300]
        keys=[float_key(v) for v in values]
        self.assertEqual(keys,sorted(keys));self.assertEqual(keys[2],keys[3])
        self.assertEqual([key_float(k) for k in keys],[float(v) for v in values])

    def test_exact_median_ties_negative_values_and_even_interpolation(self):
        self.assertEqual(exact_quantile([-8,-2,-2,0,5,9])["value"],-1.0)
        self.assertEqual(exact_quantile([4,4,4,4])["value"],4.0)

    def test_MAD_uses_given_TRAIN_median_and_exact_mass(self):
        result=exact_quantile([0,1,1,2,100],mad_center=1)
        self.assertEqual((result["n"],result["value"]),(5,1.0))

    def test_exact_tail_quantile_engine_for_later_frozen_normalization(self):
        self.assertEqual(exact_quantile([0,100,200,300],"0.001")["value"],0.3)
        self.assertEqual(exact_quantile([0,100,200,300],"0.999")["value"],299.7)

    def test_refinement_rejects_changed_prefix_mass(self):
        req=initial_queries([{"field_id":0}]);h=RadixCounts(req);h.add(0,[1,2,3,4]);req,_=advance(req,h.rows())
        h=RadixCounts(req);h.add(0,[1,3,4])
        with self.assertRaisesRegex(ValueError,"MASS_CHANGED"):advance(req,h.rows())

    def test_VAL_FULL_and_masked_leaves_cannot_fit(self):
        self.assertEqual(train_values("VAL",[1e100],[True]),[])
        self.assertEqual(train_values("FULL",[1e100],[True]),[])
        self.assertEqual(train_values("TRAIN",[2,math.nan],[True,False]),[2.0])

    def test_TSQR_group_merge_matches_direct_lstsq(self):
        import numpy as np
        molecules=[[1,1,6],[1,1,1,1,6],[1,1,6,8],[1,1,1,1,1,1,6,6]]
        coef=np.asarray([-.5,-1.3,-2.1,.7]);X=np.asarray([[m.count(z) for z in [1,6,8]]+[1] for m in molecules]);y=X@coef
        a,b=TSQR([1,6,8],2),TSQR([1,6,8],2)
        for i,(m,v) in enumerate(zip(molecules,y)):(a if i<2 else b).add(m,float(v))
        got=merge_qr([a.state(),b.state()]);observed=got["coefficients"]+[got["intercept"]]
        np.testing.assert_allclose(observed,np.linalg.lstsq(X,y,rcond=1e-12)[0],atol=1e-12,rtol=0)

    def test_winsor_statistics_do_not_modify_labels(self):
        source=[-100.0,0.0,1.0,100.0];original=source[:];mom=WinsorMoments(0,1);mom.add(source[:2]);mom.add(source[2:])
        got=mom.result();self.assertEqual(source,original);self.assertEqual(got["mean"],.5);self.assertEqual(got["std_ddof0"],.5)


class SourceAndResourceTests(unittest.TestCase):
    def test_physical_parquet_ordinals_survive_filter_pushdown(self):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory(prefix="dv1_stream_test_") as directory:
            path=Path(directory)/"tiny.parquet";pq.write_table(pa.table({"record_id":["r2","r0","r1"]}),path)
            db=duckdb.connect();rows=db.execute("SELECT file_row_number FROM read_parquet(?,file_row_number=true) WHERE record_id='r0'",[str(path)]).fetchall();db.close()
            self.assertEqual(rows,[(1,)])

    def test_weighted_rank_reducer_matches_expanded_average_ties(self):
        from reduce import rho_external
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        rows=[(1.,2,3),(1.,3,2),(5.,3,1),(9.,5,4)]
        expected=weighted_spearman(rows)
        with tempfile.TemporaryDirectory(prefix="dv1_rank_test_") as directory:
            path=Path(directory)/"joint.parquet";pq.write_table(pa.Table.from_pylist([{"field_id":0,"value":v,"heavy_atoms":h,"n":n} for v,h,n in rows]),path)
            db=duckdb.connect();got=rho_external(db,[str(path)],0);db.close()
        self.assertEqual(got["pair_n"],expected["n"]);self.assertAlmostEqual(got["rho"],expected["rho"],places=14)

    def test_unique_inode_count_and_foreign_hardlink_rejection(self):
        with tempfile.TemporaryDirectory(prefix="dv1_budget_test_") as directory:
            root=Path(directory)/"own";root.mkdir();f=root/"a";f.write_bytes(b"x"*1000);os.link(f,root/"b")
            self.assertEqual(unique_bytes(root),root.stat().st_size+1000)
            with self.assertRaises(RuntimeError):budget(root,1)
            os.link(f,Path(directory)/"outside")
            with self.assertRaisesRegex(ValueError,"OUTSIDE_OWN_RUN"):unique_bytes(root)

    def test_role_freeze_alone_never_opens_final_D4_gate(self):
        with self.assertRaisesRegex(ValueError,"COMMON_POPULATION_NOT_FROZEN"):
            validate_authority({"status":"ROUTINE_MOLECULE_VAL_ROLES_FROZEN"},{},"roles")
        common={"status":"COMMON_POPULATION_V1_FROZEN","roles_manifest_sha256":"roles","membership_tables":[{}]}
        with self.assertRaisesRegex(ValueError,"DIAGNOSTIC_GEOMETRIES_NOT_FROZEN"):
            validate_authority(common,{},"roles")

    def test_sixteen_tasks_force_sixteen_actual_workers(self):
        context=multiprocessing.get_context("spawn");barrier=context.Barrier(16)
        with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=init_barrier,initargs=(barrier,)) as pool:
            pids=list(pool.map(barrier_task,range(16),chunksize=1))
        self.assertEqual(len(set(pids)),16)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--config",required=True);args,remaining=parser.parse_known_args()
    CONFIG=load(args.config)
    unittest.main(argv=[__file__,*remaining],verbosity=2)
