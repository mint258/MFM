"""Eight synthetic semantic boundaries; no optimizer, raw source or scheduler."""
from __future__ import annotations
import copy,hashlib,unittest
from . import contract as C
from .identity import append_generated,old_identity,physical_id
from .finalize import exclusion_gates,membership


class FormalCensoredBoundaries(unittest.TestCase):
    def fixture(self):
        task={'meta':{'molecule_id':'synthetic','cohort':'retry_once','expected_conformers':2},'records':[],'existing_conformers':[]}
        outcome={'molecule_id':'synthetic','cohort':'retry_once','expected_conformers':2,'original_task_sha256':C.sha_value(task),
            'original_task_seed':C.seed_for('synthetic',True),'package_reference':None,'science_result_observed':False,
            'scientific_status':None,'execution_resolution':'UNRESOLVED_AFTER_PARENT_TIMEOUT'}
        ref={'path':'/synthetic/reference.json','bytes':1,'sha256':'a'*64}
        return task,outcome,ref

    def test_01_original_once_domain_and_two_seed_domains_are_preserved(self):
        expected=hashlib.sha256(('sprime-fill-once-v1:'+C.KERNEL_SHA+':synthetic:retry_once').encode()).hexdigest()
        self.assertEqual(C.task_key('synthetic','retry_once'),expected)
        self.assertNotEqual(C.seed_for('synthetic',False),C.seed_for('synthetic',True))
        self.assertEqual(C.task_key('synthetic','retry_once'),C.task_key('synthetic','retry_once'))

    def test_02_timeout_import_remains_consumed_without_fake_geometry_or_worker(self):
        task,outcome,ref=self.fixture();row=C.import_outcome(outcome,task,ref,ref)
        self.assertFalse(row['science_result_observed']);self.assertIsNone(row['package_reference']);self.assertIsNone(row['scientific_status'])
        self.assertIsNone(row['worker_identity']);self.assertIsNone(row['formal_start']);self.assertFalse(row['new_scientific_attempt'])

    def test_03_original_task_sha_seed_cohort_and_N_cannot_drift(self):
        task,outcome,ref=self.fixture()
        for key,value in (('original_task_sha256','b'*64),('original_task_seed',outcome['original_task_seed']+1),('cohort','fill_10N'),('expected_conformers',3)):
            bad={**outcome,key:value}
            with self.assertRaises(ValueError):C.import_outcome(bad,task,ref,ref)

    def test_04_unknown_is_never_an_empty_package_or_invented_chemical_failure(self):
        task,outcome,ref=self.fixture()
        for change in ({'package_reference':ref},{'scientific_status':'EMBED_FAILED'},{'science_result_observed':True}):
            with self.assertRaises(ValueError):C.import_outcome({**outcome,**change},task,ref,ref)

    def test_05_generated_ids_append_above_all_historical_failed_ids_and_N(self):
        rows=[{'task_key':'b'*64,'seed':2,'candidate_id':5},{'task_key':'a'*64,'seed':1,'candidate_id':9}]
        result=append_generated(rows,3,42)
        self.assertEqual([r['sprime_conf_idx'] for r in result],[43,44]);self.assertEqual(result[0]['task_key'],'a'*64)
        self.assertEqual(old_identity(42)['sprime_conf_idx'],42)
        self.assertEqual(append_generated(rows,100,42)[0]['sprime_conf_idx'],100)

    def test_06_duplicate_provenance_overflow_negative_and_bool_ids_reject(self):
        row={'task_key':'a'*64,'seed':1,'candidate_id':0}
        with self.assertRaises(ValueError):append_generated([row,row],2,9)
        with self.assertRaises(ValueError):append_generated([row],2,(1<<63)-1)
        for invalid in (-1,True,1.0):
            with self.assertRaises(ValueError):physical_id(invalid)

    def test_07_exact2percent_20percent_boundaries_and_Se_only_exception(self):
        rows=[{'effective_role':'TRAIN','common_population':i!=0,'elements_atomic_numbers':[6] if i<5 else [1]} for i in range(50)]
        self.assertTrue(exclusion_gates(rows)['passed']) #1/50=2%,1/5=20%
        carbon=copy.deepcopy(rows);carbon[4]['elements_atomic_numbers']=[1]
        self.assertFalse(exclusion_gates(carbon)['passed']) #1/4 carbon>20%, denominator remains50
        selenium=copy.deepcopy(carbon)
        for row in selenium:
            if row['elements_atomic_numbers']==[6]:row['elements_atomic_numbers']=[34]
        self.assertTrue(exclusion_gates(selenium)['passed'])
        overall=copy.deepcopy(rows);overall[5]['common_population']=False
        self.assertTrue(exclusion_gates(overall)['overall_gt2_percent'])

    def test_08_unknown_preserves_old_count_and_explicitly_excludes_insufficient(self):
        row={'effective_role':'TRAIN','S_usable_conformers':2,'S_conformers':2,'records':2,
            'Sprime_status':'EMBED_FAILED','merged_uff_count':1,'fill_status':'EXECUTION_UNRESOLVED'}
        result=membership(row)
        self.assertFalse(result['common_population']);self.assertIn('EXECUTION_UNRESOLVED',result['exclusion_reasons'])
        self.assertIn('INSUFFICIENT_ACCEPTED_SPRIME',result['exclusion_reasons'])
        row.update(merged_uff_count=2,fill_status='SUCCESS');self.assertTrue(membership(row)['common_population'])


if __name__=='__main__':unittest.main()
