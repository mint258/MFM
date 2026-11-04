"""Import provenance must extend, rather than replace, original continuation history."""
import copy,unittest
from .prepare_alpha_partition_import import preserve_resume

class ResumeLineage(unittest.TestCase):
    def setUp(self):
        self.previous=dict(output_directory='/gfshome/alpha/example',partition_id='low11',external_score_import_references=[dict(path='Main245',sha256='original')],external_score_import_completed=dict(runtime=dict(job_id='245')),resume_previous_allocations=[dict(runtime=dict(job_id='259'),plan_reference=dict(path='259'))])
        self.seed=copy.deepcopy(self.previous);self.seed['resume_output_directory']=self.previous['output_directory']
        self.old=dict(runtime=dict(job_id='263'),plan_reference=dict(path='263'),startup_proof_reference=dict(path='startup263'),accounting_reference=dict(path='native263'))
        self.imported=dict(runtime=dict(job_id='actual-import'),plan_reference=dict(path='import-plan'),startup_proof_reference=dict(path='import-startup'),accounting_reference=dict(path='import-native'))
        self.receipt=dict(path='closed-import',sha256='actual')
    def test_original_history_retained_and_new_history_bound(self):
        original=copy.deepcopy(self.previous)
        result=preserve_resume(self.seed,self.previous,self.old,self.receipt,self.imported)
        self.assertEqual(self.previous,original)
        for key in('external_score_import_references','external_score_import_completed'):self.assertEqual(result[key],original[key])
        self.assertEqual(result['resume_previous_allocations'],[*original['resume_previous_allocations'],self.old])
        self.assertEqual(result['alpha_partition_score_import_references'],[self.receipt])
        self.assertEqual(result['alpha_partition_score_import_completed'],self.imported)
    def test_existing_current_writer_and_import_not_duplicated(self):
        self.previous['resume_previous_allocations'].append(self.old)
        self.previous['alpha_partition_score_import_references']=[self.receipt]
        result=preserve_resume(self.seed,self.previous,self.old,self.receipt,self.imported)
        self.assertEqual(len(result['resume_previous_allocations']),2)
        self.assertEqual(result['alpha_partition_score_import_references'],[self.receipt])
    def test_replacing_original_import_or_root_rejected(self):
        for change in(dict(external_score_import_references=[]),dict(external_score_import_completed={}),dict(resume_output_directory='/other')):
            seed=copy.deepcopy(self.seed);seed.update(change)
            with self.assertRaises(ValueError):preserve_resume(seed,self.previous,self.old,self.receipt,self.imported)

if __name__=='__main__':unittest.main()
