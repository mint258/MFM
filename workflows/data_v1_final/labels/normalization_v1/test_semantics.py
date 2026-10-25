"""Final-fit fixtures only; meaningful leakage, geometry, tails and replay checks."""
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
from unittest.mock import patch

from runtime import TSQR, WinsorMoments, advance, canonical_bytes, initial_queries, merge_qr, ref, save
from runtime import assert_final_allocation
from authority import check_diagnostic_rows, eligible, frozen_inputs, geometry_key, physical_key
from moments import combine, state, JointMoments, combine_joint
from reader import atom_order, parity
from series import energy_residual, inventory, views
from sources import side_table
from run import check_mass, mass_signature, quantile_results
from test_reader_pipeline import ReaderPipelineTests


def field(fid=0, level="atom", energy=False, component="value"):
    return {"field_id": fid, "field_key": "fixture."+str(fid), "level": level,
            "element_reference_eligible": energy, "component": component, "unit": "fixture_unit",
            "task": "fixture_task", "registry_id": 100 + (0 if level.startswith("molecule_") else fid),
            "source_path": "values.fixture"}


def entry(f, values, keep, indices):
    return {"field": f, "field_id": f["field_id"], "values_float64": values,
            "value_mask": keep, "atom_indices": indices}


def exact_tail(values, probability):
    from runtime import RadixCounts
    request = initial_queries([{"field_id": 0}], "fixture_tail", probability=probability)
    done = []
    while request["fields"]:
        h = RadixCounts(request); h.add(0, values)
        request, finished = advance(request, h.rows()); done.extend(finished)
    return done[0]


class GeometryTests(unittest.TestCase):
    def test_production_memory_guard_rejects_32g_in_request_or_allocation(self):
        cfg={"memory_gib":64};proof={"request":{"memory_gib":64,"cpus":16}}
        with patch.dict(os.environ,{"SLURM_MEM_PER_NODE":"65536","SLURM_CPUS_PER_TASK":"16"}):
            assert_final_allocation(cfg,proof)
            with self.assertRaises(ValueError):
                assert_final_allocation(cfg,{"request":{"memory_gib":32,"cpus":16}})
        with patch.dict(os.environ,{"SLURM_MEM_PER_NODE":"32768","SLURM_CPUS_PER_TASK":"16"}):
            with self.assertRaises(ValueError):assert_final_allocation(cfg,proof)

    def test_uff_parent_record_does_not_exclude_siblings(self):
        excluded = {("mol", "uff_sprime", "opaque-last")}
        self.assertTrue(eligible("TRAIN", True, ("mol", "uff_sprime", "opaque-first"), None, excluded)[0])
        self.assertFalse(eligible("TRAIN", True, ("mol", "uff_sprime", "opaque-last"), None, excluded)[0])

    def test_pm7_and_perturbed_view_excluded(self):
        base = ("mol", "pm7", "id not parsed")
        self.assertFalse(eligible("TRAIN", True, base, None, {base})[0])
        self.assertFalse(eligible("TRAIN", True, ("mol", "pm7", "perturbed"), base, {base})[0])

    def test_val_full_embargo_never_fit(self):
        for role in ("VAL", "FULL", "EMBARGO"):
            self.assertFalse(eligible(role, True, ("m", "pm7", "g"), None, set())[0])

    def test_noncommon_train_never_fits(self):
        self.assertFalse(eligible("TRAIN", False, ("m", "pm7", "g"), None, set())[0])

    def test_no_frozen_common_no_run(self):
        with self.assertRaisesRegex(ValueError, "REAL_FROZEN_AUTHORITY"):
            frozen_inputs({"authority": {"common": None, "roles": None, "geometry_map": None, "diagnostic": None}})

    def test_physical_source_keys_are_explicit(self):
        self.assertEqual(physical_key({"molecule_id":"m","geometry_source":"uff_sprime","geometry_id":"opaque", "sprime_conf_idx":3,"native_record_id":"same provenance"}), ("m","uff_sprime",3))
        with self.assertRaises(ValueError):
            physical_key({"molecule_id":"m","geometry_source":"uff_sprime","geometry_id":"opaque", "sprime_conf_idx":True})

    def test_diagnostic_requires_same_molecules_and_fks(self):
        geom = [{"molecule_id":m, "geometry_source":s, "geometry_id":m+s, "parent_geometry_id":None} for m in ("a","b") for s in ("pm7","uff_sprime")]
        excluded = check_diagnostic_rows(geom, geom, {"a":True,"b":True}, {"a":"TRAIN","b":"TRAIN"}, expected=2)
        self.assertEqual(len(excluded), 4)
        with self.assertRaises(ValueError):
            check_diagnostic_rows(geom, geom, {"a":True,"b":True}, {"a":"TRAIN","b":"VAL"}, expected=2)
        with self.assertRaises(ValueError):
            check_diagnostic_rows(geom+[geom[0]], geom, {"a":True,"b":True}, {"a":"TRAIN","b":"TRAIN"}, expected=2)

    def test_atom_order_is_sensitive_to_order(self):
        self.assertNotEqual(atom_order([6,1,8]), atom_order([8,1,6]))
        with self.assertRaises(ValueError):
            atom_order([True,6])

    def test_side_table_joins_uff_exact_index_not_source_record(self):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory(prefix="norm_side_fixture_") as tmp:
            root = Path(tmp); db = duckdb.connect(); db.execute("SET threads=1")
            owners = [{"record_id":"pprime"+str(i),"record_ordinal":i,"molecule_id":"mol", "attempt_id":1,"job_id":2,"task_id":3,
                       "lane":"fixture", "new_role":"TRAIN","sprime_conf_idx":i,"source_record_id":"shared-parent"} for i in range(3)]
            pq.write_table(pa.Table.from_pylist(owners), root/"owners.parquet")
            db.execute("CREATE TABLE roles(molecule_id VARCHAR,effective_role VARCHAR)"); db.execute("INSERT INTO roles VALUES ('mol','TRAIN')")
            db.execute("CREATE TABLE members(molecule_id VARCHAR,common_population BOOLEAN)"); db.execute("INSERT INTO members VALUES ('mol',true)")
            db.execute("CREATE TABLE geometry(molecule_id VARCHAR,geometry_source VARCHAR,geometry_id VARCHAR,parent_geometry_id VARCHAR,view_id VARCHAR,native_record_id VARCHAR,sprime_conf_idx BIGINT)")
            for i in range(3):
                db.execute("INSERT INTO geometry VALUES ('mol','uff_sprime',?,NULL,NULL,'shared-parent',?)",["opaque"+str(i),i])
            db.execute("CREATE TABLE diagnostic(molecule_id VARCHAR,geometry_source VARCHAR,geometry_id VARCHAR)")
            db.execute("INSERT INTO diagnostic VALUES ('mol','uff_sprime','opaque2')")
            got = side_table(db,{"owner_index":ref(root/"owners.parquet"),"expected_records":3,"group_index":0},
                             {"geometry_source":"uff_sprime","dataset_id":"fixture"},root,{"output_cap_bytes":32<<20})
            self.assertEqual(got["fit_records"],2)
            self.assertEqual(got["reason_counts"]["HELDOUT_GEOMETRY_OR_ITS_PERTURBED_VIEW"],1)
            db.close()


class StatisticsTests(unittest.TestCase):
    def test_exact_tail_type7(self):
        values = [-1000.,0.,1.,2.,3.,1000.]
        self.assertAlmostEqual(exact_tail(values,"0.001")["value"],-995.)
        self.assertAlmostEqual(exact_tail(values,"0.999")["value"],995.015)

    def test_winsor_tail_never_mutates_source(self):
        values = [-1000.,0.,1.,2.,3.,1000.]; old = values.copy()
        m = WinsorMoments(-995.,995.015); m.add(values)
        self.assertEqual(values,old); self.assertEqual(m.n,6)
        self.assertAlmostEqual(float(m.mean),1.0025)

    def test_constant_std_zero_no_fake_one(self):
        m=WinsorMoments(7.,7.);m.add([7.,7.]);r=combine([state(m)])
        self.assertEqual((r["mean"],r["std_ddof0"]),(7.,0.))

    def test_empty_element_is_null(self):
        r=combine([]);self.assertEqual(r["n"],0);self.assertIsNone(r["mean"]);self.assertIsNone(r["std_ddof0"])

    def test_single_element_rank_deficient_energy_reference_explicit(self):
        q=TSQR([6]);q.add([6],4.);q.add([6],4.)
        model=merge_qr([q.state()]);self.assertEqual(model["rank"],1)
        self.assertAlmostEqual(energy_residual(4.,[6],model),0.,places=12)

    def test_pprime_models_remain_independent(self):
        a=TSQR([6]);b=TSQR([6])
        for n in (1,2,3):
            a.add([6]*n,2.*n+1.);b.add([6]*n,20.*n+7.)
        ma,mb=merge_qr([a.state()]),merge_qr([b.state()])
        self.assertNotAlmostEqual(ma["coefficients"][0],mb["coefficients"][0])

    def test_atom_elements_and_partial_vector(self):
        f=field(level="atom_vector");values=[1.,2.,3.,4.,5.,6.]
        out,joint=views([entry(f,values,[True,True,True,True,False,True],[0,0,0,1,1,1])],[6,8],[],{})
        self.assertEqual(len(out["0/raw"]),5);self.assertEqual(len(out["0/raw/Z6"]),3)
        self.assertEqual(len(out["0/raw/Z8"]),2);self.assertEqual(len(out["0/norm"]),1)
        self.assertEqual(values,[1.,2.,3.,4.,5.,6.])

    def test_physical_tensor_frobenius_offdiagonal_weight(self):
        names=["xx","xy","yy","xz","yz","zz"]
        fs=[field(i,"molecule_tensor",component=c) for i,c in enumerate(names)]
        cat,groups=inventory({"fields":fs,"plan":{"element_basis":[6]}})
        out,_=views([entry(f,[v],[True],[None]) for f,v in zip(fs,[1.,2.,3.,4.,5.,6.])],[6],groups,{})
        self.assertAlmostEqual(out[groups[0]["key"]+"/frobenius_norm"][0],(1+9+36+2*(4+16+25))**.5)
        self.assertEqual(out[groups[0]["key"]+"/trace"],[10.])
        self.assertTrue(all("DRAFT" in r["normalization_policy"] for r in cat))

    def test_joint_covariance_is_raw_audit(self):
        a=JointMoments(3);a.add([[1,2,3],[3,4,5]])
        r=combine_joint([a.state()]);self.assertEqual(r["mean_vector"],[2.,3.,4.]);self.assertEqual(r["covariance_ddof0"][0][0],1.)

    def test_rebuild_idempotence_has_no_walltime_or_paths(self):
        a=WinsorMoments(0.,5.);a.add([1.,2.,3.]);b=WinsorMoments(0.,5.);b.add([4.,5.])
        first=combine([state(a),state(b)]);second=combine([state(a),state(b)])
        self.assertEqual(canonical_bytes(first),canonical_bytes(second))

    def test_tail_mass_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,"TAIL_MASS"):
            quantile_results({"d":[{"field_id":0}]},{"d":{"lower":[{"field_id":0,"n":2,"value":1.}],"upper":[{"field_id":0,"n":3,"value":2.}]}})

    def test_source_mass_drift_rejected(self):
        row={"dataset_id":"d","group_index":0,"fit_task_rows":2,"fields_mass":{"0":2},"masked_source_fit_mass_sha256":"a"}
        expected=mass_signature([row]); changed={**row,"masked_source_fit_mass_sha256":"b"}
        with self.assertRaises(ValueError):check_mass([changed],expected)

    def test_mask_reason_parity_cannot_hide_drift(self):
        a={k:[] for k in ("record_ordinal","task_code","in_scope_fields","source_valid_fields","valid_fields","all_leaves_valid_fields","newly_masked_fields","source_reason_groups","new_reason_groups","leaf_exceptions")}
        b=copy.deepcopy(a);b["new_reason_groups"]=[1]
        with self.assertRaises(ValueError):parity(a,b)


BARRIER=None


def fixture_initialize(barrier):
    global BARRIER
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);BARRIER=barrier


def fixture_run(item):
    index,name=item
    if index<16:BARRIER.wait(timeout=180)
    cls,method=name.split(".");test=globals()[cls](method);result=unittest.TestResult();test.run(result)
    return {"name":name,"pid":os.getpid(),"failures":[[str(t),trace] for t,trace in result.failures],
            "errors":[[str(t),trace] for t,trace in result.errors],"testsRun":result.testsRun}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",required=True);a=p.parse_args()
    if not os.environ.get("SLURM_JOB_ID") or socket.gethostname().split(".")[0]!="compute-0-20" or int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<16:
        raise ValueError("FIXTURE_VALIDATION_REQUIRES_ROOT_16_CPU_ANALYSIS20_SLURM")
    names=[]
    for cls in (GeometryTests,StatisticsTests,ReaderPipelineTests):
        names.extend(cls.__name__+"."+name for name in unittest.defaultTestLoader.getTestCaseNames(cls))
    context=multiprocessing.get_context("spawn");barrier=context.Barrier(16)
    with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=fixture_initialize,initargs=(barrier,)) as pool:
        rows=list(pool.map(fixture_run,enumerate(names),chunksize=1))
    ok=len({r["pid"] for r in rows})==16 and not any(r["failures"] or r["errors"] for r in rows)
    save(a.output,{"status":"PASS" if ok else "FAIL","scientific_sources_read":False,
                   "tests":len(rows),"actual_workers":len({r["pid"] for r in rows}),"results":rows})
    print("FINAL_NORMALIZATION_FIXTURES",len(rows),"PASS" if ok else "FAIL",flush=True)
    if not ok:raise SystemExit(1)


if __name__=="__main__":main()
