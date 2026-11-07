"""Pure conservative outcome/partition/accounting boundaries for readonly close."""
from __future__ import annotations
import hashlib,json,pathlib,re

ENDPOINT='202.38.247.57:22';UID=1278;NODE='compute-0-13';CPUS=16;CAP=8<<30
RUN=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
BASE=RUN/'artifacts/conformers/n1_pprime2_source_close_v1'
KEY_CLOSE='n1_pprime2_source_terminal_close_v1';KEY_REDUCE='n1_pprime2_source_terminal_reduce_v1'
EVIDENCE_KINDS=('claim','dispatch','start','finished','packet','worker_failure','events','partial_packet','producer_receipt_entry')


def need(ok,message):
    if not ok:raise ValueError(message)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def key_shape(value):
    need(isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value),'EXACT_N1_ONCE_TASK_KEY_REQUIRED');return value


def same_sha(actual,expected):
    need(isinstance(actual,dict) and isinstance(expected,dict),'REFERENCE_DICTIONARIES_REQUIRED')
    need(all(actual.get(k)==expected.get(k) for k in ('path','bytes','sha256')),'ACTUAL_EVIDENCE_SHA_BYTES_OR_LOCATOR_MISMATCH')


def require_parents(job_ids,parents):
    wanted=set(map(str,job_ids));need(wanted<=set(parents),'MISSING_ACTUAL_TERMINAL_ACCOUNTING_FOR_CONSUMED_OR_REGISTERED_PARENT')
    allowed={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED','SPECIAL_EXIT'}
    need(all(parents[j]['state'] in allowed for j in wanted),'EVERY_CONSUMED_PARENT_MUST_ACTUALLY_BE_TERMINAL')


def classify(evidence,*,claim_valid=False,start_valid=False,dispatch_valid=False,packet_valid=False,has_second=False,conflicts=()):
    """Absence is unstarted only when *all* durable evidence is absent.

    A missing final receipt is deliberately irrelevant to science classification.
    A real packet without a reliable once/start/dispatch chain remains visible
    conflict evidence, never a reason to resubmit or fabricate a worker start.
    """
    need(not has_second or packet_valid,'SECOND_GEOMETRY_REQUIRES_A_VALIDATED_REAL_PACKET')
    scientific_evidence=any(bool(evidence.get(k)) for k in EVIDENCE_KINDS)
    if not scientific_evidence:
        need(not(claim_valid or start_valid or dispatch_valid or packet_valid),'VALIDITY_WITHOUT_ACTUAL_EVIDENCE')
        return {'state':'PROVEN_UNSTARTED_UNCONSUMED','safety_consumed':False,'science_result_observed':False,
            'scientific_status_may_be_copied':False,'real_second':False,'automatic_retry_authorized':False}
    chain=claim_valid and dispatch_valid and start_valid
    if conflicts or not chain:
        return {'state':'UNKNOWN_CONFLICT_DURABLE_EVIDENCE_NO_AUTORETRY','safety_consumed':True,'science_result_observed':False,
            'scientific_status_may_be_copied':False,'real_second':False,'automatic_retry_authorized':False}
    if not packet_valid:
        return {'state':'UNKNOWN_CONSUMED_NO_VALIDATED_PACKET','safety_consumed':True,'science_result_observed':False,
            'scientific_status_may_be_copied':False,'real_second':False,'automatic_retry_authorized':False}
    return {'state':'REAL_SECOND_SOURCE_PACKET' if has_second else 'CONSUMED_VALID_PACKET_PENDING_SECOND',
        'safety_consumed':True,'science_result_observed':True,'scientific_status_may_be_copied':True,
        'real_second':has_second,'automatic_retry_authorized':False}


def union_source(roster,imports,closed_rows):
    keys=[r['task_key'] for r in roster];import_keys=[r['task_key'] for r in imports]
    need(len(keys)==len(set(keys))==4631 and len(import_keys)==len(set(import_keys))==32
        and set(import_keys)<=set(keys),'EXACT4631_SOURCE_AND32_UNIQUE_IMPORT_KEYS')
    expected=set(keys)-set(import_keys);need(len(expected)==4599,'EXACT4599_NEW_ONCE_KEYS')
    seen={}
    for row in closed_rows:
        key=row['task_key'];need(key in expected,'IMPORTED_OR_UNKNOWN_KEY_CANNOT_ENTER_NEW_BATCH_CLOSE')
        need(key not in seen,'DUPLICATE_CLOSED_TASK_KEY_REQUIRES_ROOT_REVIEW');seen[key]=row
    need(len(import_keys)+len(seen)+len(expected-set(seen))==4631,'SOURCE_PARTITION_MUST_CONSERVE_ALL4631')
    return {'new_keys':expected,'closed_by_key':seen,'not_registered_or_not_closed_keys':expected-set(seen)}


def parent_cost(parents):
    total=0
    for jid,row in parents.items():
        need(str(row['job_id'])==str(jid),'PARENT_COST_KEY_MISMATCH')
        cpus,seconds=int(row['alloc_cpus']),int(row['elapsed_raw_seconds'])
        need(cpus>=0 and seconds>=0,'NONNEGATIVE_ACTUAL_PARENT_ALLOCATION_REQUIRED');total+=cpus*seconds
    return total


def scope(stage):
    need(stage in {'close','reduce'},'EXACT_READONLY_STAGE_REQUIRED')
    return {'stage':'N1_REGISTERED_TERMINAL_SOURCE_CLOSE' if stage=='close' else 'N1_ALL_SOURCE_CLOSED_BATCH_REDUCTION',
        'source_mother':5105,'eligible_source':4631,'imported_unchanged':32,'new_attempt_roster':4599,
        'maximum_batch_molecules':64,'new_UFF_calls':0,'new_QM_calls':0,'new_source_dispatch':False,
        'missing_producer_receipt_allowed':True,'automatic_retry':False,'common':False,'pilot_membership':False,
        'production_membership':False,'physical_int64_integration_frozen':False,'production_population_release':False,
        'endpoint':ENDPOINT,'uid':UID,'node':NODE,'whole_output_cap_bytes':CAP,
        'transitive_body_authority':'EXACT_FROZEN_SOURCE_KEYS_AND_ACTUAL_REGISTERED_OUTPUT_NAMESPACE_ONLY',
        'cost_policy':'REPORT_AND_CONTINUE_ALL_ACTUAL_TERMINAL_PARENTS'}
