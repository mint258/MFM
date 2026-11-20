"""New GPU admission policy tests; no GPU or scientific outputs are read."""
import unittest
from types import SimpleNamespace
from workflows.benchmark_evaluation.gpu_runtime import gpu_admission,root_capacity,quota_observation,prepare_neural_source,GIB,validate_model_selector

class GpuPolicyTests(unittest.TestCase):
    def card(self):return dict(uuid="GPU-A",used_mib=5.,total_mib=24576.,utilization_percent=0.)
    def test_idle_actual_uuid_with_sufficient_memory_is_admitted(self):
        self.assertEqual(gpu_admission(self.card(),[],"GPU-A")["uuid"],"GPU-A")
    def test_small_memory_does_not_override_an_existing_compute_context(self):
        with self.assertRaises(RuntimeError):
            gpu_admission(self.card(),[dict(gpu_uuid="GPU-A",pid=10)],"GPU-A")
    def test_active_or_wrong_physical_card_is_not_assumed_idle(self):
        with self.assertRaises(RuntimeError):gpu_admission(dict(self.card(),utilization_percent=80.),[],"GPU-A")
        with self.assertRaises(RuntimeError):gpu_admission(self.card(),[],"GPU-B")
    def test_actual_GPU_memory_covers_the_forecast(self):
        with self.assertRaises(RuntimeError):
            gpu_admission(dict(self.card(),used_mib=8000.),[],"GPU-A")
    def test_system_and_inode_reserves_are_kept_on_the_actual_node(self):
        stat=SimpleNamespace(f_blocks=75*GIB,f_frsize=1,f_bavail=40*GIB,f_favail=10000)
        self.assertEqual(root_capacity(stat,16*1024**2)["reserved_bytes"],10*GIB)
        with self.assertRaises(RuntimeError):
            root_capacity(SimpleNamespace(f_blocks=75*GIB,f_frsize=1,f_bavail=10*GIB,f_favail=10000),1)
        with self.assertRaises(RuntimeError):
            root_capacity(SimpleNamespace(f_blocks=75*GIB,f_frsize=1,f_bavail=40*GIB,f_favail=100),1)
    def test_source_adapter_preserves_budget_and_defers_CPU_statistics(self):
        source="from workflows.benchmark_data.admission import protect\nimport unittest\ndef score(y,p,mean,groups):\n    raise RuntimeError('must be deferred')\nif not unittest.TextTestRunner().run(suite).wasSuccessful():raise SystemExit(1)\nmodel=pl.Trainer(accelerator='cpu',max_epochs=50,devices=1)\nSEED=20261025\nBATCH_SIZE=64\n"
        actual=prepare_neural_source(source,'Chemprop-v2')
        self.assertIn("accelerator='gpu'",actual)
        self.assertIn("max_epochs=50",actual)
        self.assertIn("BATCH_SIZE = 64",actual)
        self.assertIn("SEED = 20261025",actual)
        self.assertIn("PENDING_CPU_STATISTICS",actual)
        self.assertNotIn("TextTestRunner",actual)
    def test_TabPFN_routing_keeps_native_feature_values_and_masks(self):
        source="model=TabPFNRegressor.create_default_for_version(version,device='cpu',random_state=20261025)\nvalues=[1.0,None]\n"
        actual=prepare_neural_source(source,'TabPFN')
        self.assertIn("device='cuda'",actual)
        self.assertIn("random_state=20261025",actual)
        self.assertIn("values = [1.0, None]",actual)
    def test_native_model_selector_cannot_dispatch_a_traditional_fit(self):
        validate_model_selector("Chemprop-v2","Chemprop-v2")
        validate_model_selector("C1-TabPFN-Pprime","TabPFN")
        validate_model_selector("","TabPFN")
        with self.assertRaises(RuntimeError):validate_model_selector("RF-ECFP4","Chemprop-v2")
        with self.assertRaises(RuntimeError):validate_model_selector("LightGBM-RDKit2D","TabPFN")
    def test_traditional_CPU_models_cannot_use_the_neural_GPU_adapter(self):
        with self.assertRaises(ValueError):prepare_neural_source("model.fit(x,y)","LightGBM")
    def test_stale_or_different_UID_quota_is_not_reused(self):
        base=dict(uid=1278,generation="benchmarkB020261119",returncode=0,observed_epoch=100.,
                  raw="Disk quotas for user zixiao (uid 1278):\n/dev/a 1000 0 100000000 0 0 0\n")
        self.assertGreater(quota_observation(base,1278,150.),0)
        with self.assertRaises(RuntimeError):quota_observation(base,1278,200.)
        with self.assertRaises(RuntimeError):quota_observation(base,1264,150.)

if __name__=="__main__":unittest.main()
