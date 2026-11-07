"""Six interface/gate fixtures; producer geometry math is reused, not retested."""
import unittest
from close_pilot import (COMPLETE,READBACK,accounting_from_raw,checked_ids,
                        distribution,require_complete,review_draft)


class ClosureTests(unittest.TestCase):
    def complete(self):
        return {"status":COMPLETE,"failure":None,"resource_denial":None,"expected_molecules":336,
            "submitted_molecules":336,"completed_molecules":336,"never_dispatched_molecules":0,
            "parquet_readback":{"status":READBACK},"runtime":{"job_id":"364"},
            "signals_sent":False,"original_data_modified":False,"scientific_recipe_changed":False,
            "monitor_thread_closed":True}
    def test_running_or_partial_pilot_never_closes(self):
        require_complete(self.complete(),job_id="364")
        with self.assertRaisesRegex(ValueError,"ALL336"):
            require_complete(dict(self.complete(),completed_molecules=335))
        with self.assertRaisesRegex(ValueError,"FINAL_336"):
            require_complete(dict(self.complete(),status="PILOT_INCOMPLETE"))
    def test_resource_denial_and_wrong_actual_job_never_close(self):
        with self.assertRaisesRegex(ValueError,"FINAL_336"):
            require_complete(dict(self.complete(),resource_denial={"reason":"memory"}))
        with self.assertRaisesRegex(ValueError,"REGISTERED_PILOT_JOB"):
            require_complete(self.complete(),job_id="365")
    def test_adapter_preserves_all_parent_cost_rows_but_excludes_steps(self):
        raw="JobIDRaw|State|ExitCode|ElapsedRaw|AllocCPUS|\n364|COMPLETED|0:0|60|16|\n364.batch|COMPLETED|0:0|60|16|\n363|FAILED|1:0|5|16|\n"
        parents=accounting_from_raw(raw,"364")
        self.assertEqual([row["job_id"] for row in parents],["363","364"])
        self.assertEqual(sum(row["alloc_cpus"]*row["elapsed_raw_seconds"] for row in parents),1040)
        with self.assertRaisesRegex(ValueError,"TERMINAL"):
            accounting_from_raw(raw.replace("COMPLETED|0:0|60|16","RUNNING|0:0|60|16"),"364")
    def test_root_draft_cannot_automatically_accept_or_disclose_for_root(self):
        draft=review_draft({}, {}, {}, {}, {})
        self.assertEqual(draft["status"],"ROOT_REVIEW_PENDING")
        self.assertFalse(draft["accept_scientific_failure_disclosure"])
        self.assertNotIn(draft["status"],{"APPROVED","PILOT_ACCEPTED_FOR_PLANNING"})
    def test_exact_prepared_manifest_identity_not_count_alone(self):
        tasks=[{"meta":{"molecule_id":"a"}},{"meta":{"molecule_id":"b"}}]
        refs=[{"molecule_id":"a","path":"a.gz"},{"molecule_id":"b","path":"b.gz"}]
        self.assertEqual(set(checked_ids(tasks,refs,2)),{"a","b"})
        with self.assertRaisesRegex(ValueError,"SAME336_UNIQUE"):
            checked_ids(tasks,[refs[0],dict(refs[1],molecule_id="other")],2)
    def test_scientific_failure_retained_in_cohort_disclosure(self):
        base={"cohort":"retry_once","prior_status":"EMBED_FAILED","file_group":1,"elapsed_seconds":2.,
            "original_accepted_count":1,"old_references_in_package":0,"new_real_accepted_count":0,
            "below_dedup_threshold":0,"raw_candidates_retained":0}
        groups=distribution([dict(base,status="EMBED_FAILED"),dict(base,status="SUCCESS",elapsed_seconds=4.,new_real_accepted_count=1)])
        self.assertEqual(groups[0]["status_counts"],{"EMBED_FAILED":1,"SUCCESS":1})
        self.assertEqual(groups[0]["science_worker_seconds"],6.)
        self.assertEqual(groups[0]["old_baseline_count"],2)
        self.assertEqual(groups[0]["old_references_in_packages"],0)


if __name__=="__main__":unittest.main()
