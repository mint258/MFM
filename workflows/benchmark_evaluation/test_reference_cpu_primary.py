import ast
import unittest
from workflows.benchmark_evaluation.reference_cpu_primary import prepare_reference_cpu_source,remap_reference_cpu_specs,bounded_cpu_predecessors

class RegisteredReferenceCPUPrimaryTests(unittest.TestCase):
    def program(self):
        return """binding_path=b1/'C1_Pprime_reference_features/job_4537149/Pprime/Joung2020_cv_binding.json'
checkpoint=b1/'smoke100/job_4536865/model_cache/tabpfn-v2-regressor.ckpt'
model=TabPFNRegressor.create_default_for_version(ModelVersion.V2,device='cuda',model_path=str(checkpoint),random_state=SEED,n_preprocessing_jobs=cpus,inference_config={'SUBSAMPLE_SAMPLES':10000})
model.fit(x,y)
p=model.predict(test)
"""
    def test_only_device_changes_full_registered_source(self):
        original=self.program();result=prepare_reference_cpu_source(original,'Joung2020','Pprime')
        self.assertIn("device='cpu'",result)
        restored=result.replace("device='cpu'","device='cuda'")
        self.assertEqual(ast.dump(ast.parse(restored),include_attributes=False),ast.dump(ast.parse(original),include_attributes=False))
    def test_wrong_binding_or_unregistered_group_is_rejected(self):
        for dataset,group in (('Joung2020','Pprime_plus_D'),('PPE1694','Pprime'),('NMRShiftDB2','Pprime')):
            with self.subTest(dataset=dataset,group=group),self.assertRaises(ValueError):
                prepare_reference_cpu_source(self.program(),dataset,group)
    def test_changed_checkpoint_family_or_already_CPU_constructor_is_rejected(self):
        for source in (self.program().replace('ModelVersion.V2','ModelVersion.V2_5'),
                       self.program().replace("device='cuda'","device='cpu'"),
                       self.program().replace('tabpfn-v2-regressor.ckpt','unapproved.ckpt'),
                       self.program()+"second=TabPFNRegressor.create_default_for_version(ModelVersion.V2,device='cuda')\n"):
            with self.subTest(source=source),self.assertRaises(ValueError):prepare_reference_cpu_source(source,'Joung2020','Pprime')
    def test_only_exact_registered_reference_source_is_rebound(self):
        row=dict(dataset='Joung2020',feature_group='Pprime',learner='TabPFN',job=10,folder='reference_cv_models/job_10',original_CPU_job=5)
        other=dict(dataset='NMRShiftDB2',feature_group='Pprime_plus_RDKit_atom',learner='LightGBM',job=11,folder='atomic/job_11')
        result=remap_reference_cpu_specs([row,other],{10:20})
        self.assertEqual(row['job'],10);self.assertEqual(result[1],other)
        self.assertEqual(result[0]['folder'],'reference_cv_models/job_20')
        self.assertEqual(result[0]['original_CPU_job'],5)
    def test_duplicate_or_wrong_atomic_or_source_identity_rejected(self):
        row=dict(dataset='Joung2020',feature_group='Pprime',learner='TabPFN',job=10,folder='reference_cv_models/job_10')
        for specs,mapping in (([row,row],{10:20}),([dict(row,learner='LightGBM')],{10:20}),
                              ([dict(row,dataset='NMRShiftDB2')],{10:20}),([dict(row,folder='wrong/job_10')],{10:20}),
                              ([row],{10:10}),([row],{99:20})):
            with self.subTest(specs=specs,mapping=mapping),self.assertRaises(ValueError):remap_reference_cpu_specs(specs,mapping)

    def test_eight_slot_limit_keeps_existing_joint_disk_peak(self):
        jobs=list(range(100,115));plan=bounded_cpu_predecessors(jobs)
        self.assertEqual(sum(v is None for v in plan.values()),8)
        for i,j in enumerate(jobs[8:],8):self.assertEqual(plan[j],jobs[i-8])
        for selected,limit in (([1,1],8),([1],9),([1],True),([1],0)):
            with self.subTest(selected=selected,limit=limit),self.assertRaises(ValueError):bounded_cpu_predecessors(selected,limit)
if __name__=='__main__':unittest.main()

