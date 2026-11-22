import unittest
from .cpu_tabpfn_primary import defer_cpu_statistics,model_calls,remap_tabpfn_cpu_specs,ALLOWED_TABULAR_CPU,failed_reporting_keys,prepare_failed_reporting_source
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
    def test_registered_official_dataset_and_feature_pairs_keep_original_aliases(self):
        self.assertIn(("tdc_asap","Pprime"),ALLOWED_TABULAR_CPU)
        self.assertNotIn(("TDC_ADMET","Pprime"),ALLOWED_TABULAR_CPU)
        rows=[dict(dataset=dataset,feature_group=feature,learner="TabPFN",job=100+i,folder="registered/job_"+str(100+i),original_CPU_job=10+i) for i,(dataset,feature) in enumerate(sorted(ALLOWED_TABULAR_CPU))]
        replacements={row["job"]:row["job"]+1000 for row in rows}
        result=remap_tabpfn_cpu_specs(rows,replacements)
        for old,new in zip(rows,result):
            self.assertEqual(old["original_CPU_job"],new["original_CPU_job"])
            self.assertEqual((old["dataset"],old["feature_group"],old["learner"]),(new["dataset"],new["feature_group"],new["learner"]))
            self.assertEqual(new["primary_execution_backend"],"CPU")
    def test_reference_atomic_or_changed_learner_cannot_use_tabular_resource_reassignment(self):
        for dataset,feature,learner in (("Joung2020","Pprime","TabPFN"),("NMRShiftDB2","Pprime","TabPFN"),("Biogen_ADME","D","TabPFN"),("Biogen_ADME","Pprime","LightGBM")):
            row=dict(dataset=dataset,feature_group=feature,learner=learner,job=100,folder="source/job_100")
            with self.assertRaises(ValueError):remap_tabpfn_cpu_specs([row],{100:200})
    def test_official_metric_assignments_are_deferred_with_the_pending_statistics(self):
        original="def score(y,p,m,g):\n    raise RuntimeError('no scoring in model producer')\nmetrics=score([1.],None,None,None)\nofficial_score=metrics['MAE']\nofficial_value=forbidden_official_score()\n"
        adapted=defer_cpu_statistics(original)
        namespace={}
        exec(adapted,namespace)
        self.assertIsNone(namespace["official_score"])
        self.assertIsNone(namespace["official_value"])
        self.assertTrue(namespace["metrics"]["CPU_statistics_deferred"])
        self.assertEqual(namespace["metrics"]["bootstrap_draws"],0)
        self.assertEqual(model_calls(original),model_calls(adapted))
    def failed_manifest(self):
        return dict(job="100",status="C1_Pprime_TABPFN_TDC_ASAP_CLOSED",tasks_expected=23,tasks_completed=22,
            failures=[dict(dataset="TDC_ADMET",task="retry",status="FIRST_ATTEMPT_FAILED",error="KeyError('MAE')")])
    def test_failed_only_continuation_requires_actual_closed_error_metadata(self):
        manifest=self.failed_manifest()
        self.assertEqual(failed_reporting_keys(manifest,"100|COMPLETED|0:0",100),(("TDC_ADMET","retry"),))
        for accounting in ("100|RUNNING|0:0","101|COMPLETED|0:0","100|FAILED|1:0"):
            with self.assertRaises(ValueError):failed_reporting_keys(manifest,accounting,100)
        manifest["failures"][0]["error"]="ValueError('different problem')"
        with self.assertRaises(ValueError):failed_reporting_keys(manifest,"100|COMPLETED|0:0",100)
    def test_failed_only_continuation_never_refits_successful_original_tasks(self):
        original="coverage={'keep':1,'retry':1}\nfor group in ('TDC_ADMET',):\n    for endpoint in sorted(coverage):\n        model.fit(endpoint)\n        prediction=model.predict(endpoint)\nreport={'tasks_expected':23}\n"
        result,keys=prepare_failed_reporting_source(original,self.failed_manifest(),"100|COMPLETED|0:0",100)
        fitted=[]
        class Model:
            def fit(self,key):fitted.append(key)
            def predict(self,key):return key
        namespace={"model":Model()};exec(result,namespace)
        self.assertEqual(fitted,["retry"])
        self.assertEqual(namespace["report"]["tasks_expected"],1)
        self.assertEqual(namespace["report"]["continuation_of_native_job"],100)
        self.assertFalse(namespace["report"]["successful_original_predictions_replayed"])
        self.assertFalse(namespace["report"]["training_rollback"])
        self.assertEqual(model_calls(original),model_calls(result))
if __name__=="__main__":unittest.main()


from .cpu_tabpfn_primary import validated_closed_reporting_authorization

class ClosedReportingAuthorizationTests(unittest.TestCase):
    def authorization(self):
        record="100|COMPLETED|0:0|1278|zixiao\n"
        manifest=dict(job="100",status="C1_Pprime_TABPFN_TDC_ASAP_CLOSED",tasks_expected=23,tasks_completed=22,
            failures=[dict(dataset="TDC_ADMET",task="retry",status="FIRST_ATTEMPT_FAILED",error="KeyError('MAE')")])
        return dict(schema="C1_CLOSED_REPORT_FAILURE_AUTHORIZATION_V1",source_job=100,
            native_evidence_kind="NATIVE_SACCT_CLOSED_RECORD",raw_native_evidence=record,native_accounting=record,
            closed_source_manifest=manifest,failed_tasks=[["TDC_ADMET","retry"]],model_seed=20261025,
            fixed_weight_context_inference=True,training_rollback=False,max_additional_context_inference_attempts_per_task=1)
    def test_native_closed_prerequisite_is_fulfilled_without_new_network_or_fit(self):
        self.assertEqual(validated_closed_reporting_authorization(self.authorization(),100),(("TDC_ADMET","retry"),))
    def test_active_or_failed_native_source_is_never_relabelled_closed(self):
        for state,code in (("RUNNING","0:0"),("TIMEOUT","0:0"),("FAILED","1:0")):
            value=self.authorization();record="100|"+state+"|"+code+"|1278|zixiao\n"
            value.update(native_accounting=record,raw_native_evidence=record)
            with self.subTest(state=state),self.assertRaises(ValueError):validated_closed_reporting_authorization(value,100)
    def test_actual_native_owner_must_match(self):
        for uid,user in (("999","zixiao"),("1278","other")):
            value=self.authorization();record="100|COMPLETED|0:0|"+uid+"|"+user+"\n"
            value.update(native_accounting=record,raw_native_evidence=record)
            with self.subTest(uid=uid,user=user),self.assertRaises(ValueError):validated_closed_reporting_authorization(value,100)
    def test_seed_rollback_and_context_attempt_cap_remain(self):
        for field,value in (("model_seed",20261026),("fixed_weight_context_inference",False),("training_rollback",True),("max_additional_context_inference_attempts_per_task",2),("max_additional_context_inference_attempts_per_task",True)):
            authorization=self.authorization();authorization[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):validated_closed_reporting_authorization(authorization,100)
    def test_changed_failed_keys_source_identity_or_native_evidence_rejected(self):
        for field,value in (("source_job",101),("failed_tasks",[["TDC_ADMET","successful"]]),("native_evidence_kind","UNVERIFIED"),("raw_native_evidence","100|RUNNING|0:0|1278|zixiao\n")):
            authorization=self.authorization();authorization[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validated_closed_reporting_authorization(authorization,100)
