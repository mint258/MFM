import unittest
from .cpu_tabpfn_primary import defer_cpu_statistics,model_calls,remap_tabpfn_cpu_specs
class CpuTabpfnTests(unittest.TestCase):
    def test_statistics_deferred_without_changing_model_configuration_or_prediction(self):
        original="def score(y,p,m,g):\n    raise RuntimeError('no replay')\nmodel=TabPFNRegressor.create_default_for_version(ModelVersion.V2,device='cpu',random_state=20261025,inference_config={'SUBSAMPLE_SAMPLES':10000})\nmodel.fit(x,y)\nprediction=model.predict(z)\n"
        result=defer_cpu_statistics(original)
        self.assertEqual(model_calls(original),model_calls(result))
        self.assertIn("device='cpu'",result)
        namespace={};exec(result.split("model =",1)[0],namespace)
        self.assertEqual(namespace["score"]([1,2],None,None,None)["bootstrap_draws"],0)
        self.assertEqual(model_calls(original),model_calls(original.replace("device='cpu'","device='cuda'")))
    def test_only_pending_native_identity_is_remapped_and_inputs_are_preserved(self):
        row=dict(dataset="Biogen_ADME",feature_group="Pprime",learner="TabPFN",job=101,folder="C1/job_101",original_CPU_job=80)
        other=dict(dataset="other",feature_group="D",learner="LightGBM",job=99,folder="D/job_99")
        output=remap_tabpfn_cpu_specs([row,other],{101:201})
        self.assertEqual(output[1],other);self.assertEqual(output[0]["original_CPU_job"],80)
        self.assertEqual(row["job"],101);self.assertEqual(output[0]["job"],201)
        with self.assertRaises(ValueError):remap_tabpfn_cpu_specs([row,other],{99:202})
        with self.assertRaises(ValueError):remap_tabpfn_cpu_specs([row,other],{102:202})
        with self.assertRaises(ValueError):remap_tabpfn_cpu_specs([row,row],{101:201})
if __name__=="__main__":unittest.main()
