"""Synthetic lifecycle/conservation tests; no UFF/LMDB/real sbatch or large scans."""
from __future__ import annotations
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from full_common import IO,begin_attempt,require_actual_accounting,require_budget_review,runtime,task_key
from plan_batches import split_batches
from finalize_common import exclusion_gates,membership,merge_counts,normalize_package


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="sprime_formal_fixture_");self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def test_exclusive_started_attempt_is_never_retried(self):
        value={"external_output_root":str(self.root),"attempt_ledger_root":str(self.root/"ledger")}
        meta={"molecule_id":"m","cohort":"retry_once","task_key":task_key("m","retry_once")}
        with patch.dict(os.environ,{"SLURM_JOB_ID":"fixture-job"}):
            row=begin_attempt(value,{"meta":meta})
            self.assertIn("pid_start_ticks",row)
            with self.assertRaises(FileExistsError):begin_attempt(value,{"meta":meta})

    def test_task_key_depends_on_molecule_and_once_cohort(self):
        self.assertNotEqual(task_key("m","retry_once"),task_key("m","fill_10N"))
        self.assertNotEqual(task_key("m","retry_once"),task_key("other","retry_once"))

    def test_over500_requires_root_explicit_review(self):
        require_budget_review(500,{"approved_total_core_hours_cap":500})
        with self.assertRaisesRegex(ValueError,"OVER500"):
            require_budget_review(500.1,{"approved_total_core_hours_cap":600})
        require_budget_review(500.1,{"approved_total_core_hours_cap":600,"approved_over_500_core_hours":True})
        with self.assertRaisesRegex(ValueError,"FINITE_ADEQUATE"):
            require_budget_review(10,{"approved_total_core_hours_cap":float("nan")})

    def test_formal_cannot_use32g_or_live_memory_approval(self):
        intent=self.root/"intent.json"
        intent.write_text(json.dumps({"request":{"pilot":False,"memory_gib":32,"cpus":16}}))
        with patch.dict(os.environ,{"SLURM_JOB_ID":"fixture","SLURM_CPUS_PER_TASK":"16"}),patch("socket.gethostname",return_value="compute-0-14"):
            with self.assertRaisesRegex(ValueError,"NO_SMALL_PILOT"):
                runtime({},intent,self.root/"config.json",science=True)

    def test_actual_accounting_ignores_steps_and_matches_raw(self):
        raw=self.root/"sacct.txt"
        raw.write_text("JobID|State|ExitCode|ElapsedRaw|AllocCPUS|NodeList\n42|COMPLETED|0:0|60|16|fixture\n42.batch|COMPLETED|0:0|60|16|fixture\n")
        path=self.root/"accounting.json"
        value={"schema":"DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1","status":"ACTUAL_PARENT_ACCOUNTING_CLOSED",
               "query_returncode":0,"raw_sacct_reference":IO.reference(raw),
               "parents":[{"job_id":"42","state":"COMPLETED","exit_code":"0:0","alloc_cpus":16,"elapsed_raw_seconds":60}]}
        path.write_text(json.dumps(value))
        _,seconds=require_actual_accounting(path,"42")
        self.assertEqual(seconds,960)
        value["parents"][0]["elapsed_raw_seconds"]=0;path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,"DIFFERS_FROM_RAW"):
            require_actual_accounting(path,"42")

    def test_shards_preserve_each_task_and_fixed_startup_budget(self):
        rows=[{"molecule_id":str(i),"estimated_allocated_core_seconds":1} for i in range(5)]
        batches=split_batches(rows,{"wall_seconds":10,"stop_dispatch_before_wall_seconds":0,"max_molecules_per_batch":2},3)
        self.assertEqual([len(rows) for rows,_ in batches],[2,2,1])
        self.assertEqual([estimate for _,estimate in batches],[5,5,4])
        self.assertEqual([row["molecule_id"] for batch,_ in batches for row in batch],[str(i) for i in range(5)])


class CommonTests(unittest.TestCase):
    def row(self,role="TRAIN",n=1,uff=1,elements=None,included=True):
        return {"molecule_id":"m","effective_role":role,"S_usable_conformers":n,"S_conformers":n,
            "records":n,"Sprime_status":"SUCCESS","merged_uff_count":uff,
            "elements_atomic_numbers":elements or [6],"common_population":included}

    def test_n1_stays_in_common_and_pprime_is_pending(self):
        result=membership(self.row())
        self.assertTrue(result["common_population"])
        self.assertTrue(result["pprime_two_conformers_pending"])

    def test_p_task_failure_does_not_remove_complete_geometry(self):
        row=self.row(n=2,uff=2);row["all_P_tasks_success"]=False
        self.assertTrue(membership(row)["common_population"])

    def test_remaining_full_is_outside_denominator(self):
        rows=[self.row(),self.row("VAL"),self.row("FULL",included=False)]
        self.assertFalse(membership(rows[-1])["common_population"])
        gates=exclusion_gates(rows)
        self.assertEqual(gates["mother_molecules"],2)
        self.assertEqual(gates["excluded_molecules"],0)

    def test_exact2_percent_allowed_exceeding_stops(self):
        rows=[self.row(included=i>=2) for i in range(100)]
        self.assertTrue(exclusion_gates(rows)["passed"])
        rows[2]["common_population"]=False
        self.assertTrue(exclusion_gates(rows)["overall_gt2_percent"])

    def test_only_se_gets20_percent_exception(self):
        rows=[self.row(elements=[6,34] if i<5 else [6],included=i>=5) for i in range(1000)]
        self.assertTrue(exclusion_gates(rows)["passed"])
        for row in rows[:5]:row["elements_atomic_numbers"]=[6,15]
        self.assertFalse(exclusion_gates(rows)["passed"])

    def test_old_replacement_rows_do_not_double_count(self):
        old={"origin":"accepted_sprime","kernel_sprime_conf_idx":0}
        new={"origin":"data_v1_fill_10N","kernel_sprime_conf_idx":1,"seed":7,"candidate_id":0}
        self.assertEqual(merge_counts(1,[old,new],2),2)

    def test_new_candidate_reuse_or_index_gap_rejected(self):
        row={"origin":"data_v1_fill_10N","kernel_sprime_conf_idx":0,"seed":7,"candidate_id":0}
        with self.assertRaisesRegex(ValueError,"DUPLICATE_NEW"):
            merge_counts(0,[row,dict(row,kernel_sprime_conf_idx=1)],2)
        with self.assertRaisesRegex(ValueError,"HAVE_GAPS"):
            merge_counts(0,[dict(row,kernel_sprime_conf_idx=1)],2)

    def test_equal_coordinates_are_allowed_only_as_distinct_real_candidate_ids(self):
        import numpy as np
        numbers=[6,1];coordinates=[[0.,0.,0.],[0.,0.,1.]]
        atom_sha=hashlib.sha256(np.asarray(numbers,dtype="<i8").tobytes()).hexdigest()
        base={"molecule_id":"m","atomic_numbers":numbers,"coordinates":coordinates,
              "status":"SUCCESS","converged":True,"atom_order_sha256":atom_sha,
              "geometry_sha256":IO.geometry_sha(numbers,coordinates),"origin":"data_v1_fill_10N",
              "original_sprime_conf_idx":None,"seed":7,"uff_energy_kcal_mol":0.,
              "source_record_id":"native","below_dedup_threshold":True}
        packet={"summary":{"molecule_id":"m","source_record_id":"native","atom_order_sha256":atom_sha},
                "conformers":[dict(base,sprime_conf_idx=i,candidate_id=i) for i in range(2)]}
        with tempfile.TemporaryDirectory(prefix="formal_package_fixture_") as tmp:
            path=Path(tmp)/"packet.json.gz";path.write_bytes(gzip.compress(json.dumps(packet).encode(),mtime=0))
            ref={"molecule_id":"m",**IO.reference(path)}
            result=normalize_package(ref)
            self.assertEqual(merge_counts(0,result["rows"],2),2)
            packet["conformers"][1]["candidate_id"]=0
            path.write_bytes(gzip.compress(json.dumps(packet).encode(),mtime=0))
            with self.assertRaisesRegex(ValueError,"CANDIDATE_REUSED"):
                normalize_package({"molecule_id":"m",**IO.reference(path)})

    def test_physical_parquet_row_number_is_before_usable_filter(self):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory(prefix="physical_row_fixture_") as tmp:
            path=Path(tmp)/"old.parquet"
            pq.write_table(pa.table({"molecule_id":["m"]*3,"sprime_conf_idx":[0,1,2],
                "status":["SUCCESS","UFF_NOT_CONVERGED","SUCCESS"],"converged":[True,False,True]}),path)
            db=duckdb.connect()
            rows=db.execute("SELECT sprime_conf_idx,file_row_number FROM read_parquet(?,file_row_number=true) WHERE status='SUCCESS' AND converged ORDER BY sprime_conf_idx",[str(path)]).fetchall()
            self.assertEqual(rows,[(0,0),(2,2)])
            db.close()


if __name__=="__main__":unittest.main()
