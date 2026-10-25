"""New physical aggregation/weighting fixtures only; no old test suites rerun."""
from __future__ import annotations

import argparse
import concurrent.futures
import copy
import multiprocessing
import os
from pathlib import Path
import socket
import tempfile
import unittest

from size_shared import adapter_from,load,ref,save
from aggregate import aggregate,pair_keys,median,target_catalog
from build_proposal import build
from rank_sql import rho
from size_reader import rows_for_group


def entry(values,mask=None,indices=None,path="values.local"):
    return {"values_float64":list(values),"value_mask":[True]*len(values) if mask is None else list(mask),
            "atom_indices":list(range(len(values))) if indices is None else indices,"field":{"source_path":path}}


def target(op,ids=None):return {"operation":op,"field_ids":[0] if ids is None else ids}


def rotation():
    import numpy as np
    q,r=np.linalg.qr(np.array([[1.,2.,3.],[4.,2.,1.],[2.,7.,5.]]))
    return q


class SizeIncremental(unittest.TestCase):
    def test_dipole_norm_under_nontrivial_rotation(self):
        import numpy as np
        t=target("JOINT_XYZ_L2",[0,1,2]);a=np.array([3.,-4.,2.]);b=rotation()@a
        make=lambda v:{i:entry([float(x)],indices=[None]) for i,x in enumerate(v)}
        x=aggregate(t,make(a),[6])[0];y=aggregate(t,make(b),[6])[0]
        self.assertAlmostEqual(x,y,places=12)

    def test_tensor_frobenius_rotation_and_naive_six_norm_negative(self):
        import numpy as np
        a=np.array([[1.,2.,3.],[2.,-4.,5.],[3.,5.,3.]])
        b=rotation()@a@rotation().T
        unpack=lambda m:[m[0,0],m[0,1],m[1,1],m[0,2],m[1,2],m[2,2]]
        make=lambda v:{i:entry([float(x)],indices=[None]) for i,x in enumerate(v)}
        t=target("SYMMETRIC_FROBENIUS",list(range(6)))
        self.assertAlmostEqual(aggregate(t,make(unpack(a)),[6])[0],aggregate(t,make(unpack(b)),[6])[0],places=12)
        self.assertGreater(abs(np.linalg.norm(unpack(a))-np.linalg.norm(unpack(b))),1e-5)

    def test_atom_vector_rms_norm_rotation_and_atom_permutation(self):
        import numpy as np
        a=np.array([[1.,2.,3.],[3.,4.,5.]])
        b=(a@rotation().T)[::-1]
        make=lambda v:{0:entry(v.reshape(-1).tolist(),indices=[0,0,0,1,1,1])}
        t=target("ATOM_VECTOR_RMS_NORM")
        x=aggregate(t,make(a),[6,8]);y=aggregate(t,make(b),[8,6])
        self.assertAlmostEqual(x[0],y[0],places=12)
        self.assertAlmostEqual(x[2]["global_vector_L2"],x[0]*(2**.5),places=12)

    def test_partial_excluded_from_rho_without_changing_masks_or_labels(self):
        a=entry([1.,2.,3.],[True,False,True],[0,0,0]);old=copy.deepcopy(a)
        value,reason,_=aggregate(target("ATOM_VECTOR_RMS_NORM"),{0:a},[6])
        self.assertIsNone(value);self.assertEqual(reason,"PARTIAL_OR_INVALID_SOURCE_MASK");self.assertEqual(a,old)

    def test_zero_is_value_empty_is_missing(self):
        self.assertEqual(aggregate(target("RAW_SCALAR"),{0:entry([0.],indices=[None])},[6])[0],0.)
        self.assertIsNone(aggregate(target("SEMANTIC_ATOM_SUM"),{0:entry([])},[6])[0])

    def test_atom_scope_rms_avoids_charge_sum_cancellation(self):
        t=target("SEMANTIC_ATOM_RMS");e=entry([-1.,1.])
        value,reason,extra=aggregate(t,{0:e},[6,8])
        self.assertEqual((value,reason,extra["signed_mean"],extra["sum_abs"]),(1.,None,0.,2.))
        s=entry([2.,3.],indices=[1,2],path="values.super_heavy_atom_rows")
        self.assertIsNotNone(aggregate(t,{0:s},[1,6,8])[0])
        s["atom_indices"]=[1,1];self.assertIsNone(aggregate(t,{0:s},[1,6,8])[0])

    def test_sparse_pair_duplicate_conflict_and_stored_representation(self):
        t=target("STORED_PAIR_RMS");e=entry([3.,4.]);e["pair_keys"]=[(0,1),(0,2)]
        self.assertAlmostEqual(aggregate(t,{0:e},[6,6,6])[0],(12.5)**.5)
        e["pair_keys"]=list(reversed(e["pair_keys"]));e["values_float64"].reverse()
        self.assertAlmostEqual(aggregate(t,{0:e},[6,6,6])[0],(12.5)**.5)
        e["pair_keys"]=[(0,1),(0,1)]
        self.assertEqual(aggregate(t,{0:e},[6,6,6])[1],"DUPLICATE_PAIR_KEY_CONFLICT")
        e["values_float64"]=[3.,3.]
        self.assertEqual(aggregate(t,{0:e},[6,6,6])[1],"DUPLICATE_PAIR_KEY_SAME_VALUE")

    def test_enpart_sum_keeps_sign_and_orbital_keys_remain_basis_specific(self):
        e=entry([-10.,3.]);e["pair_keys"]=[(0,1),(0,2)]
        self.assertEqual(aggregate(target("STORED_PAIR_ENERGY_SUM"),{0:e},[6,8,1])[0],-7.)
        keys=pair_keys([{"atom_i":1,"basis_i":"P-PI","atom_j":0,"basis_j":"S-SIGMA"},
                        {"atom_i":1,"basis_i":"P-SIGMA","atom_j":0,"basis_j":"S-SIGMA"}],"sigma_pi_entries")
        self.assertNotEqual(keys[0],keys[1])

    def test_hof_requires_own_context_model(self):
        from calibration import TSQR,merge_qr
        q=TSQR([6]);r=TSQR([6])
        for n in (1,2,3):q.add([6]*n,2*n+1.);r.add([6]*n,7*n+4.)
        mq,mr=merge_qr([q.state()]),merge_qr([r.state()]);t=target("TRAIN_ELEMENT_RESIDUAL_SCALAR")
        self.assertIsNone(aggregate(t,{0:entry([5.])},[6,6])[0])
        self.assertAlmostEqual(aggregate(t,{0:entry([5.])},[6,6],mq)[0],0.,places=12)
        self.assertGreater(abs(aggregate(t,{0:entry([5.])},[6,6],mr)[0]),1.)

    def test_rank_sql_ties_and_variant_filter_match_existing_oracle(self):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        from calibration import weighted_spearman
        rows=[(0.,2,3),(1.,2,2),(2.,3,4),(2.,4,1)]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"hist.parquet"
            a=[{"target_id":"a","variant":"record_primary","value":v,"heavy_atoms":h,"n":n} for v,h,n in rows]
            a.append({"target_id":"wrong","variant":"record_primary","value":-1000.,"heavy_atoms":99,"n":10000})
            pq.write_table(pa.Table.from_pylist(a),p)
            db=duckdb.connect();db.execute("SET threads=1")
            actual=rho(db,[str(p)],"a","record_primary");expected=weighted_spearman(rows)
            self.assertEqual(actual["pair_n"],expected["n"]);self.assertAlmostEqual(actual["rho"],expected["rho"],places=14)
            db.close()

    def test_record_and_molecule_weights_are_distinct_and_median_keeps_ties(self):
        from calibration import weighted_spearman
        record=weighted_spearman([(1.,1,100),(2.,2,1),(0.,3,1)])["rho"]
        molecule=weighted_spearman([(median([1.]*100),1,1),(median([2.]),2,1),(median([0.]),3,1)])["rho"]
        self.assertNotAlmostEqual(record,molecule,places=4);self.assertEqual(median([-0.,0.,1.,1.]),.5)

    def test_actual_metadata_exhaustive_mapping_and_unit_pending(self):
        root=Path(__file__).resolve().parents[4]
        cfg=load(root/"configs/data_v1/labels/size_semantics_proposal_v1.json")
        reg=load(cfg["registry"]["path"]);proposal=build(cfg,reg)
        fs=[dict(f,field_id=i) for i,f in enumerate(sorted((f for f in reg["fields"] if f["status"]=="enabled"),key=lambda f:f["field_key"]))]
        targets=target_catalog(proposal,fs);self.assertEqual(len(targets),129);self.assertEqual(len(proposal["components"]),146)
        self.assertEqual(sum(t["operation"]=="SEMANTIC_ATOM_SUM" for t in targets),20)
        self.assertEqual(sum(t["operation"]=="SEMANTIC_ATOM_RMS" for t in targets),19)
        self.assertEqual(sum(t["basis_invariance_status"]=="BASIS_INVARIANCE_UNPROVEN" for t in targets),1)
        mr=next(r for r in proposal["components"] if r["field_key"]=="D20.MolMR")
        self.assertFalse(mr["unit_review"]["source_scale_proven"])

    def test_provisional_canonical_reader_rejects_val_without_pretend_common(self):
        import threading
        import pyarrow as pa
        import pyarrow.parquet as pq
        from compact import encode,arrow_schema
        from reader import atom_order
        root=Path(__file__).resolve().parents[4];cfg=load(root/"configs/data_v1/labels/size_rho_pilot_v1.json")
        source_cfg=load(root/"configs/data_v1/labels/streaming_v1.json")
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);f={"field_id":0,"field_key":"fixture.MolLogP","task":"D20","registry_id":None,
                "source_path":"MolLogP","component":"value","level":"molecule","physical_range":{"lower":None,"upper":None,"lower_exclusive":False}}
            mapping=save(out/"fields.json",[f]);plan={"field_map":mapping,"task_codes":{"D20":0}}
            adapter=adapter_from(cfg["scan_adapter"],source_cfg,plan,out,None,threading.Event())
            owners=[];base=[];labels=[];masks=[]
            for i,role in enumerate(("TRAIN","VAL")):
                o={"record_id":"fixture"+str(i),"molecule_id":"m"+str(i),"attempt_id":"a","job_id":1,"task_id":2}
                owners.append({**o,"record_ordinal":i,"new_role":role,"lane":"fixture","total_atoms":1,"heavy_atoms":1,"record_payload_sha256":"payload"})
                base.append({**o,"atomic_numbers":[6],"geometry_status":"ORIGINAL_PM7_GEOMETRY","native_atom_order_sha256":atom_order([6]),"source_payload_sha256":"payload"})
                values=[.25 if i==0 else -1e9]+[0.]*19
                labels.append({**o,"status":"SUCCESS","values_float64":values,"valid_mask":[True]*20,"descriptor_names":adapter.WORK["common"].D20_NAMES})
                masks.append(encode(i,0,[{"field_id":0,"values_float64":[values[0]],"source_value_mask":[True],"value_mask":[True],"source_reasons":[],"new_reasons":[],"review_reasons":[]}]))
            for name,rows in (("owner",owners),("base",base),("labels",labels)):pq.write_table(pa.Table.from_pylist(rows),out/(name+".parquet"))
            pq.write_table(pa.Table.from_pylist(masks,schema=arrow_schema()),out/"D20_000.mask.parquet")
            group={"owner_index":ref(out/"owner.parquet"),"expected_records":2,"base_files":[ref(out/"base.parquet")],"label_files":[{**ref(out/"labels.parquet"),"family":"D20"}]}
            result=list(rows_for_group(adapter,source_cfg,plan,group,{"outputs":[ref(out/"D20_000.mask.parquet")]}))
            self.assertEqual(len(result),1);self.assertEqual(result[0][0]["new_role"],"TRAIN")
            self.assertNotIn("common_population",result[0][0]);self.assertEqual(result[0][3][0]["values_float64"],[.25])


BARRIER=None


def initialize_fixture(barrier):
    global BARRIER
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);BARRIER=barrier


def partition_run(names):
    import pyarrow as pa
    BARRIER.wait(timeout=180);rows=[]
    for name in names:
        test=SizeIncremental(name);r=unittest.TestResult();test.run(r)
        rows.append({"name":name,"failures":[[str(t),trace] for t,trace in r.failures],"errors":[[str(t),trace] for t,trace in r.errors]})
    return {"pid":os.getpid(),"arrow_cpu":pa.cpu_count(),"arrow_io":pa.io_thread_count(),"semantic_results":rows}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",required=True);a=p.parse_args()
    if not os.environ.get("SLURM_JOB_ID") or socket.gethostname().split(".")[0]!="compute-0-20" or int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<16:
        raise ValueError("INCREMENTAL_SIZE_FIXTURES_REQUIRE_ROOT_16_CPU_ANALYSIS20_SLURM")
    names=unittest.defaultTestLoader.getTestCaseNames(SizeIncremental);parts=[names[i::16] for i in range(16)]
    context=multiprocessing.get_context("spawn");barrier=context.Barrier(16)
    with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=initialize_fixture,initargs=(barrier,)) as pool:
        groups=list(pool.map(partition_run,parts,chunksize=1))
    results=[r for g in groups for r in g["semantic_results"]]
    ok=(len({g["pid"] for g in groups})==16 and all(g["arrow_cpu"]==g["arrow_io"]==1 for g in groups)
        and len(results)==len(names) and not any(r["failures"] or r["errors"] for r in results))
    save(a.output,{"status":"PASS" if ok else "FAIL","semantic_tests":len(results),"actual_worker_groups":len(groups),
        "actual_worker_pids":sorted({g["pid"] for g in groups}),"workers":groups,"only_fixtures_and_small_metadata_read":True,
        "real_scientific_label_bodies_read":False,"old_19_or_24_test_suites_repeated":False})
    print("INCREMENTAL_SIZE_FIXTURES",len(results),"PASS" if ok else "FAIL",flush=True)
    if not ok:raise SystemExit(1)


if __name__=="__main__":main()
