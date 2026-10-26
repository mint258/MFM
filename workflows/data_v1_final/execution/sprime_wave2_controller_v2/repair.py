"""Exactly one Root-adopted metadata replacement, never an automatic retry."""
import pathlib
from workflows.data_v1_final.execution.sprime_wave2_controller_v1 import controller as V
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as F

BID='batch-00033';FAILED='4521632';SCIENCE='4521623'
CLOSER=V.REPO/'workflows/data_v1_final/conformers/formal_cpu_auto_close_index_v2'
FILES=('__init__.py','admission.py','run.py','test_admission.py','README.md')


def literals(value):
    F.need(value['batch_id']==BID and value['stage']=='close' and str(value['failed_job_id'])==FAILED
        and str(value['science_job_id'])==SCIENCE and value['no_science_retry'] is True,'ONLY_ACTUAL33_METADATA_REPAIR_NOT_OTHER_STAGE_RETRY')
    F.need(value['replacement_output_root']==str(V.G.WAVE2/BID/'closed_root_repair_v1')
        and value['replacement_primary_reference']['path']==str(CLOSER/'run.py'),'EXACT_NEW33_CLOSER_PRIMARY_AND_OUTPUT')


class Repair:
    def __init__(self,reference,review):
        self.reference=reference;F.need(V.pin(reference['path'])==reference,'ROOT_REPAIR_MAP_CHANGED');self.value=V.load(reference['path']);value=self.value
        F.need(value['schema']=='ROOT_SPRIME_SINGLE_CLOSE_REPAIR_MAP_V2' and value['status']=='APPROVED_SINGLE_METADATA_CLOSE_REPLACEMENT'
            and value['reviewer']=='root' and value['endpoint']=='202.38.247.57:22' and value['uid']==1278
            and value['manifest_reference']==V.MANIFEST and value['plan_reference']==V.PLAN
            and value['resume_state_reference']==review['repair_original_hold_reference'],'INDEPENDENT_ROOT_EXACT_PRIOR_HOLD_REPAIR_MAP')
        literals(value);previous=V.load(value['resume_state_reference']['path']);F.need(V.pin(value['resume_state_reference']['path'])==value['resume_state_reference'],'ORIGINAL_HOLD_STATE_PIN')
        old=previous['stages'][BID]['close']
        F.need(previous['status'].startswith('HOLD') and old['job_id']==FAILED and old['terminal'] is True and old['state']=='FAILED'
            and old['actual_registered_references']==value['failed_registration']
            and previous['stages'][BID]['run']['job_id']==SCIENCE,'REAL_OLD_FAILED_METADATA_CLOSURE_AND_SCIENCE_PARENT')
        for record in (value['failed_registration'],value['replacement_registration']):
            for name in ('stage_spec_reference','request_reference','submission_reference','activation_reference','registry_reference'):
                F.need(V.pin(record[name]['path'])==record[name],'ACTUAL_REPAIR_REGISTRATION_PIN_CHAIN')
        failed=F.accounting(value['failed_accounting_reference'],[FAILED])[FAILED]
        F.need(failed['state']=='FAILED' and failed['exit_code']=='1:0','FAILED33_REAL_COST_PRESERVED_NOT_FAKE_C0')
        submission=V.load(value['replacement_registration']['submission_reference']['path']);self.job_id=str(submission['job_id'])
        F.need(self.job_id.isdecimal() and self.job_id not in {FAILED,SCIENCE},'ACTUAL_DISTINCT_REPLACEMENT_PARENT')
        parent=F.accounting(value['replacement_accounting_reference'],[self.job_id])[self.job_id]
        F.need(parent['state']=='COMPLETED' and parent['exit_code']=='0:0' and int(parent['alloc_cpus'])==16,'ACTUAL_REPLACEMENT_CLOSE_C0_BEFORE_RESUME')
        expected=[V.pin(CLOSER/name) for name in FILES]
        F.need(value['replacement_source_references']==expected and value['replacement_primary_reference']==V.pin(CLOSER/'run.py'),'ALL_REAL_REPLACEMENT_SOURCE_PINS')
        self.entry=value['replacement_registration'];self.failed=failed;self.parent=parent

    def primary(self,bid):return CLOSER/'run.py' if bid==BID else V.G.CLOSER/'run.py'
    def output(self,bid):return V.G.WAVE2/bid/('closed_root_repair_v1' if bid==BID else 'closed_v1')
    def report_path(self,bid):return self.output(bid)/'closed_batch.json'
