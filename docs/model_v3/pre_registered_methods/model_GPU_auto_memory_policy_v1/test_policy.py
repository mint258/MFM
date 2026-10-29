"""Operational arithmetic/schema tests, without model/data/SDK imports."""
import unittest
from unittest.mock import patch
import policy

G=1<<30
NODE='NodeName=compute-0-21 RealMemory=120000 AllocMem=120000'
MEM='MemAvailable: 120000000 kB\n'
REF=dict(path='/share/home/zixiao/descriptor_analysis/test.json',bytes=1,sha256='a'*64)

def record(name,job=None,budget=64,mode='automatic_default'):
    return dict(registration_id=name,node='compute-0-21',gpu_uuid='GPU-c35',software_budget_bytes=budget*G,
                rss_limit_bytes=(56 if budget==64 else 28)*G,Root_source=REF,source_pins=REF,
                actual_submission=REF if job else None,status='SUBMITTED' if job else 'PRE_SUBMISSION',
                job_id=job,slurm_memory_mode=mode)

def assess(queue='',records=None,job=None,mem=MEM):
    if records is None: records=[record('self',job)]
    return policy._assess(NODE,queue,mem,node='compute-0-21',software_budget_bytes=64*G,rss_limit_bytes=56*G,
                          registrations=records,current_job_id=job,current_reservation_id='self')

class ArithmeticTests(unittest.TestCase):
    def test_native_fixed32_counted_once_and_automatic_zero_still32(self):
        for mode,decl in [('fixed_declared','32G'),('automatic_default','0')]:
            with self.subTest(mode=mode):
                out=assess('4782|zixiao|R|'+decl+'|16\n',[record('self'),record('native','4782',32,mode)])
                self.assertEqual(out['prior_counted_bytes'],32*G)
                self.assertEqual(out['with_new_software_bytes'],96*G)
                self.assertEqual(len(out['own_active_budgets']),1)

    def test_worker_self_counted_once(self):
        out=assess('4782|zixiao|R|0|16\n9000|zixiao|R|0|16\n',
                   [record('self','9000'),record('native','4782',32)],'9000')
        self.assertEqual(out['with_new_software_bytes'],96*G)

    def test_own_unregistered_active_budget_holds(self):
        with self.assertRaisesRegex(ValueError,'unknown or mismatched own'):
            assess('4782|zixiao|R|32G|16\n')

    def test_foreign_unknown_is_explicit_and_not_finite_guarantee(self):
        out=assess('1|another|R|0|16\n2|another|R|UNLIMITED|16\n')
        self.assertEqual(out['prior_counted_bytes'],0)
        self.assertEqual(len(out['foreign_unknown_declarations']),2)
        self.assertFalse(out['unknown_foreign_finite_guarantee_claimed'])
        self.assertFalse(out['Slurm_finite_physical_allocation_guarantee_claimed'])

    def test_foreign_finite_added_to_software85(self):
        with self.assertRaisesRegex(ValueError,'RealMemory85'):
            assess('4782|zixiao|R|32G|16\n2|another|R|16G|16\n',
                   [record('self'),record('native','4782',32,'fixed_declared')])

    def test_memavailable_gate_retained(self):
        with self.assertRaisesRegex(ValueError,'MemAvailable'):
            assess(mem='MemAvailable: 80000000 kB\n')

    def test_other_presubmission_intent_keeps_nonzero_budget(self):
        out=assess(records=[record('self'),record('pending',budget=32)])
        self.assertEqual(out['prior_counted_bytes'],32*G)
        self.assertIsNone(out['other_presubmission_intents'][0]['actual_job_id'])

    def test_worker_requires_actual_submitted_job(self):
        with self.assertRaisesRegex(ValueError,'exact actual SUBMITTED'):
            assess('9000|zixiao|R|0|16\n',[record('self')],'9000')

    def test_fixed_zero_and_duplicate_owned_jobs_rejected(self):
        with self.assertRaisesRegex(ValueError,'fixed declaration'):
            assess('4782|zixiao|R|0|16\n',[record('self'),record('native','4782',32,'fixed_declared')])
        with self.assertRaisesRegex(ValueError,'Duplicate actual'):
            assess(records=[record('self'),record('native','4782',32),record('other','4782',32)])

    def test_slurm_allocmem_automatic_default_is_observed_not_software_budget(self):
        out=assess()
        self.assertEqual(out['observed_AllocMem_MiB'],120000)
        self.assertEqual(out['prior_counted_bytes'],0)
        self.assertIsNone(out['fixed_Slurm_memory_requested_bytes'])

class RegistrationTests(unittest.TestCase):
    def make(self,**extra):
        args=dict(registration_id='self',node='compute-0-21',gpu_uuid='GPU-c35',software_budget_bytes=64*G,
                  rss_limit_bytes=56*G,Root_source=REF,source_pins=REF)
        args.update(extra)
        return policy.make_registration(**args)

    def test_presubmission_null_is_honest_and_old_storage_fields_untouched(self):
        with patch.object(policy,'bound',return_value={}):
            value=self.make(); registry={'reservations':{'native':{'remaining_bytes':123}}}
            policy.put_registration(registry,value)
            self.assertEqual(registry['reservations'],{'native':{'remaining_bytes':123}})
            self.assertIsNone(value['job_id']);self.assertIsNone(value['actual_submission'])
            with self.assertRaisesRegex(ValueError,'no invented job'):
                self.make(job_id='9000')

    def test_native_actual_submission_field_and_no_job_rebinding(self):
        with patch.object(policy,'bound',return_value={'status':'SUBMITTED','actual_sbatch_job_id':'9000'}):
            value=self.make(status='SUBMITTED',job_id='9000',actual_submission=REF,job_id_field='actual_sbatch_job_id')
            registry={};policy.put_registration(registry,value)
            changed={**value,'job_id':'9001'}
            with self.assertRaisesRegex(ValueError,'actual Root SUBMITTED'):
                policy.put_registration(registry,changed)

if __name__=='__main__': unittest.main()
