"""Synthetic stage-state contracts; no scientific prediction files are read."""
import copy,unittest
from workflows.benchmark_evaluation.confirmation_combination import combine_stage_reports
from workflows.benchmark_evaluation.selection import IncompleteComparison
class CombinationTests(unittest.TestCase):
    def fixtures(self):
        base=dict(status="CONDITIONAL_CONFIRMATION_STAGE_REPORT_CLOSED",
            all_declared_producers_terminal=True,original_TEST_binding_enforced=True,
            original_primary_scores_recomputed=False,required_configurations=0,records=[],
            frozen_B1_roster="/frozen",C1_primary_manifest="/primary",
            native_accounting={"1":dict(state="COMPLETED",actual_job="1")})
        return [dict(base,stage="B1",C1_primary_manifest=None),dict(base,stage="C1")]
    def test_closed_zero_required_stages_combine_without_extra_fits_or_scores(self):
        reports=self.fixtures();before=copy.deepcopy(reports);out=combine_stage_reports(reports)
        self.assertEqual(out["status"],"CONDITIONAL_CONFIRMATION_REPORT_CLOSED")
        self.assertEqual(reports,before);self.assertFalse(out["score_replay"])
        self.assertEqual(out["B1"],[]);self.assertEqual(out["C1"],[])
    def test_changed_frozen_roster_is_rejected(self):
        reports=self.fixtures();reports[1]["frozen_B1_roster"]="/changed"
        with self.assertRaises(IncompleteComparison):combine_stage_reports(reports)
    def test_live_source_or_conflicting_accounting_cannot_be_finalized(self):
        for value in ("RUNNING","PENDING"):
            reports=self.fixtures();reports[1]["native_accounting"]={"2":dict(state=value)}
            with self.assertRaises(IncompleteComparison):combine_stage_reports(reports)
        reports=self.fixtures();reports[1]["native_accounting"]={"1":dict(state="FAILED",actual_job="1")}
        with self.assertRaises(IncompleteComparison):combine_stage_reports(reports)
    def test_missing_stage_or_required_cell_is_rejected(self):
        reports=self.fixtures()
        with self.assertRaises(IncompleteComparison):combine_stage_reports(reports[:1])
        reports[0]["required_configurations"]=1
        with self.assertRaises(IncompleteComparison):combine_stage_reports(reports)
