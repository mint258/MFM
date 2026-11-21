import ast
import unittest
from .feature_startup_recovery import continuation_decision,prepare_legacy_namespace_continuation

RAW="""#!/bin/bash
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=2
#SBATCH --time=06:00:00
#SBATCH --job-name=original-feature-source
python - <<'PY'
import os
from pathlib import Path
b1=Path("synthetic-only")
out=b1/'C1_Pprime_reference_features'/('job_'+os.environ['SLURM_JOB_ID'])
out.mkdir(parents=True)
def native_features(row):
    return row['original_F64']
report=dict(status='FEATURES_CLOSED',job=os.environ['SLURM_JOB_ID'],scientific_parameters_unchanged=True)
(out/'manifest.json').write_text(str(report))
PY
"""
class FeatureStartupRecoveryTests(unittest.TestCase):
    def test_native_success_is_noop(self):
        self.assertEqual(continuation_decision("COMPLETED","0:0",True),"NO_OP_SUCCESS")
    def test_active_and_unknown_are_rejected(self):
        for state in ("RUNNING","PENDING","COMPLETING","UNKNOWN"):
            with self.subTest(state=state),self.assertRaises(ValueError):continuation_decision(state,"0:0",False)
    def test_empty_native_timeout_allows_one_scoped_continuation(self):
        self.assertEqual(continuation_decision("TIMEOUT","0:0",False),"RETRY_EMPTY_FAILED_OUTPUT")
    def test_partial_native_output_never_acquires_whole_replay(self):
        self.assertEqual(continuation_decision("TIMEOUT","0:0",True),"PARTIAL_OUTPUT_REQUIRES_SCOPED_RECOVERY")
    def test_actual_cancellation_state_suffix_and_bad_exit(self):
        self.assertEqual(continuation_decision("CANCELLED by 1278","0:15",False),"RETRY_EMPTY_FAILED_OUTPUT")
        with self.assertRaises(ValueError):continuation_decision("COMPLETED","1:0",False)
    def test_original_namespace_retains_actual_producer_identity_and_budget(self):
        answer=prepare_legacy_namespace_continuation(RAW)
        self.assertIn("C1_Pprime_reference_features/job_4537149",answer)
        self.assertIn("job=os.environ['SLURM_JOB_ID']",answer)
        self.assertIn("output_namespace_job=4537149",answer)
        self.assertIn("#SBATCH --time=06:00:00",answer)
        self.assertIn("#SBATCH --cpus-per-task=2",answer)
        self.assertNotIn("exist_ok=True",answer)
        ast.parse(answer.split("<<'PY'\n",1)[1].rsplit("\nPY",1)[0])
    def test_fitted_model_cannot_use_feature_recovery(self):
        with self.assertRaises(ValueError):prepare_legacy_namespace_continuation(RAW.replace("def native_features(row):","model.fit(x,y)\ndef native_features(row):"))
    def test_duplicate_output_route_rejected(self):
        with self.assertRaises(ValueError):prepare_legacy_namespace_continuation(RAW.replace("out.mkdir(parents=True)","out=other\nout.mkdir(parents=True)"))
    def test_existing_directory_overwrite_not_allowed(self):
        with self.assertRaises(ValueError):prepare_legacy_namespace_continuation(RAW.replace("out.mkdir(parents=True)","out.mkdir(parents=True,exist_ok=True)"))
    def test_fabricated_native_identity_rejected(self):
        with self.assertRaises(ValueError):prepare_legacy_namespace_continuation(RAW.replace("job=os.environ['SLURM_JOB_ID']","job=4537149"))
