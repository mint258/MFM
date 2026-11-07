"""Shared Alpha admission for independent versioned stages; no science imports."""
import os
from pathlib import Path
import sys
from ..alpha_runtime_v1 import common as Q

VERSION='alpha-original502-generic3642-recovery-v1'
REPRESENTATION='GENERIC_ALLC_SINGLE_HEAVY_ADJACENCY_DEFERRED_VALENCE_V1'


def read(ref):
    Q.need(ref['bytes']<=2<<20,'Small exact pinned metadata only')
    return Q.load(Q.verify(ref))


def admit(plan,proof,plan_path,proof_path,schema,scope):
    from ..alpha_runtime_v1.profile import admit as actual
    if 'reviewed_storage_budget_reference' in plan:
        b=read(plan['reviewed_storage_budget_reference']);scope_name=plan['storage_budget_scope']
        Q.need(b['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and b['reviewer']=='root'
            and b['endpoint']==plan['endpoint']=='218.192.171.238:22' and b['uid']==plan['uid']==1264
            and b['quota_root']==plan['quota_authority']['quota_root']
            and b['scope_total_caps_bytes'][scope_name]==plan['output_cap_bytes']
            and b['other_future_reserved_bytes_for_each_scope'][scope_name]==plan['other_future_reserved_bytes']
            and b['minimum_free_after_all_future_bytes']==plan['minimum_free_bytes'], 'Exact current aggregate budget binding')
    authority=actual(plan,minimum_workers=16);request=proof['request']
    Q.need(plan['schema']==schema and plan['scope_key']==request['scope_key']==scope
        and plan['population_version']==VERSION,'Explicit separate stage and population version')
    Q.need(request['producer_plan_reference']==Q.reference(plan_path)
        and request['execution_argv']==plan['execution_argv']
        and sys.argv[-4:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)]
        and request['execution_argv'][-4:]==sys.argv[-4:],'Actual exact plan/startup command')
    Q.need(proof['endpoint']==plan['endpoint']=='218.192.171.238:22'
        and proof['uid']==plan['uid']==os.getuid()==1264 and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Actual Alpha UID/job/boot')
    refs={r['path']:r for r in request['source_references']}
    for path in Path(__file__).parent.glob('*.py'):
        Q.need(refs.get(str(path.absolute()))==Q.reference(path),'Every new package source pinned in startup')
    for ref in request['source_references']:
        Q.need(ref['bytes']<=2<<20,'Source list cannot disguise data bodies');Q.verify(ref)
    return authority


def actual_parent(review):
    p=review['actual_parent'];account=read(review['actual_accounting_reference'])
    Q.need(p['State']=='COMPLETED' and p['ExitCode']=='0:0' and str(p['UID'])=='1264'
        and p['endpoint']=='218.192.171.238:22' and p in account['actual_parents']
        and account['endpoint']=='218.192.171.238:22','Actual closed source parent accounting, not inferred C0')
    Q.verify(account['raw_sacct_reference'])
    return p
