"""Fresh independent Alpha guard; historical792 and actual profile are not fresh proofs."""
import csv,hashlib,io,os,socket,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from . import contracts as C
from secondary_moleculenet_csv6_identity_v1 import contracts as frozen_CSV


def account(reference,job,parents):
    Q.need(reference in parents,'EXACT_PARENT_ACCOUNTING_APPROVED');value=Q.load_ref(reference);p=value['actual_parent']
    Q.need(value['query_returncode']==0 and value['endpoint']==Q.ENDPOINT and value['uid']==1264 and p['JobIDRaw']==str(job)
        and p['State']=='COMPLETED' and p['ExitCode']=='0:0' and p['UID']=='1264' and p['AllocCPUS']=='16'
        and p['NodeList'] in Q.NODES and p['Partition']=='cpu','ACTUAL_ALPHA_CPU16_C0_PARENT')
    raw=value['raw_sacct_reference'];Q.need(raw in parents,'RAW_PARENT_ACCOUNTING_APPROVED')
    rows=list(csv.DictReader(io.StringIO(Q.read_small(Q.verify(raw)).decode()),delimiter='|'));found=[r for r in rows if r.get('JobIDRaw')==str(job)]
    Q.need(len(found)==1 and all(found[0][k]==p[k] for k in ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition'))
        and value['allocated_core_seconds_observed']==int(p['ElapsedRaw'])*16,'ACTUAL_PARENT_RAW_STATE_AND_COST')
    return value


def require_startup(plan_path,proof_path):
    plan=Q.load(plan_path);proof=Q.load(proof_path);mode=plan['mode'];Q.need(mode in C.MODES,'ONLY_SIX_CSV_NEWLINE_DIAGNOSIS')
    spec=C.MODES[mode];primary=C.HERE/'run.py';wall=plan['wall_seconds'];cap=plan['output_cap_bytes']
    argv=[plan['python'],'-B','-m',C.MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    Q.need(plan['schema']==spec['plan'] and proof['schema']==spec['proof'] and plan['producer_key']==plan['scope_key']==spec['key']
        and plan['stage']==spec['stage'] and plan['scope_parameters']==C.parameters(mode) and plan['scope_mode']==spec['scope_mode']
        and plan['performance_profile'] is spec['performance_profile'] and plan['kind']=='analysis' and plan['pilot'] is spec['pilot']
        and plan['endpoint']==Q.ENDPOINT and plan['uid']==1264 and plan['run_root']==str(C.ROOT) and plan['node'] in Q.NODES
        and plan['cpus']==16 and plan['memory_policy']==Q.POLICY and type(wall) is int and 0<wall<=spec['wall_max'] and wall%60==0
        and type(cap) is int and cap==spec['cap'],'EXACT_SIX_CSV_BYTE_CENSUS_SCOPE_AND_RESOURCE')
    Q.need(primary==Path(sys.modules['__main__'].__file__).absolute() and Path(sys.executable).absolute()==Path(plan['python']).absolute()
        and sys.argv==[str(primary),*argv[4:]] and plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),'EXACT_MAIN_AND_COMPLETE_ARGV')
    review=Q.load_ref(plan['root_review_reference']);Q.need(review['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','EXACT_ROOT_STAGE_REVIEW')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot','wall_seconds',
                'output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile'):
        Q.need(plan[key]==review[key],'ROOT_FIELD_DIFFERS:'+key)
    Q.need(plan['source_references']==review['approved_source_references'],'EXACT_ROOT_APPROVED_SOURCE_SET')
    data_paths={r['path'] for r in plan['data_references']}
    Q.need(len(data_paths)==6 and not any(r['path'] in data_paths for r in [*plan['source_references'],*plan['parent_evidence_references']]),'SIX_PAYLOADS_NOT_PRE_FIXTURE_METADATA')
    declared={r['path']:{k:r[k] for k in ('path','bytes','sha256')} for r in proof['source_target_verification']}
    for value in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],Q.ref(plan_path)]:
        Q.need(declared.get(value['path'])==value,'ACTUAL_SOURCE_OR_PARENT_NOT_ATTESTED');Q.verify(value)
    for path in [*(C.HERE/name for name in C.FILES),Path(Q.__file__),Path(Q.__file__).parent/'__init__.py']:
        Q.need(Q.ref(path) in plan['source_references'],'EVERY_ACTUAL_NEW_AND_BASE_SOURCE_APPROVED')
    for path in (C.AUTHORITY_HERE/name for name in frozen_CSV.FILES):
        Q.need(Q.ref(path) in plan['source_references'],'EVERY_IMPORTED_FROZEN_CSV_HELPER_AND_METADATA_SOURCE')
    Q.need(proof['endpoint']==Q.ENDPOINT and proof['uid']==os.getuid()==1264 and proof['node']==plan['node']==socket.gethostname().split('.')[0]
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and 0<=time.time()-proof['observed_unix_seconds']<=120
        and proof['plan_reference']==Q.ref(plan_path) and proof['root_review_reference']==plan['root_review_reference'],'INDEPENDENT_FRESH_ALPHA_STARTUP')
    Q.need(proof['request']=={'kind':'analysis','pilot':spec['pilot'],'cpus':16,'memory_policy':Q.POLICY,'wall_seconds':wall,'execution_argv':argv}
        and proof['scope_key']==spec['key'] and proof['scope_mode']==spec['scope_mode'] and proof['performance_profile'] is spec['performance_profile']
        and proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False,'HONEST_PHASE_REQUEST_NO_MEMORY_OR_EXCLUSIVE')
    env=os.environ;Q.need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('SLURM_CPUS_PER_TASK')=='16'
        and env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(x)=='1' for x in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'ACTUAL_CPU16_SINGLE_LIBRARY_THREADS')
    job=Q.fields(proof['job_metadata']);Q.need(job['JobId']==str(proof['job_id']) and job['UserId']=='alpha(1264)' and job['JobState']=='RUNNING'
        and job['NodeList']==plan['node'] and job['Partition']=='cpu' and job['NumCPUs']=='16' and job['NumTasks']=='1' and job['Requeue']=='0'
        and job['Command']==proof['script_reference']['path'] and Q.duration(job['TimeLimit'])==wall,'ACTUAL_RUNNING_JOB_SCRIPT_WALL')
    signer=proof['controller_evidence'];Q.need(signer['endpoint']==Q.ENDPOINT and signer['uid']==1264 and signer['hostname']=='sonmi'
        and signer['proof_is_not_created_by_scientific_worker'] is True and signer['actual_script_reference']==proof['script_reference'],'INDEPENDENT_LOGIN_CONTROLLER')
    for text in Q.read_small(Q.verify(proof['script_reference'])).decode().splitlines():
        if text.strip().startswith('#SBATCH'):Q.need(not any(x in text for x in ('--mem','--exclusive','--gpu','--gres')),'NO_MEMORY_EXCLUSIVE_OR_GPU_DIRECTIVE')
    tail=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split();gate=proof['actual_gate_process']
    Q.need(gate['pid']==os.getpid() and gate['uid']==1264 and gate['start_ticks']==int(tail[19]) and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0)
        and gate['cgroup_sha256']==hashlib.sha256(Path('/proc/self/cgroup').read_bytes()).hexdigest(),'SAME_ATTESTED_GATE_PROCESS')
    storage=proof['storage_observation'];raw=Q.load_ref(proof['storage_observation_reference']);scope_ref=storage['storage_scope_review_reference']
    Q.need(declared.get(scope_ref['path'])==scope_ref and raw['uid']==1264 and raw['node']==proof['node'] and raw['run_root']==str(C.ROOT)
        and raw['observed_unix_seconds']==storage['observed_unix_seconds'],'SIGNED_ACTUAL_RAW_STORAGE_AND_SCOPE')
    scope=Q.load_ref(scope_ref);extra=sum(r['whole_output_cap_bytes'] for r in scope.get('additional_task_output_reservations',[]));reserved=storage['whole_output_caps_reserved_bytes']-extra
    Q.need(reserved>=cap and Q.effective_storage(raw,scope_ref['path'],reserved,reservation_evidence=storage['registered_task_reservation_evidence'])==storage
        and proof['account_free_bytes']==storage['effective_free_bytes'] and 0<=time.time()-storage['observed_unix_seconds']<=120,'RECOMPUTED_CURRENT_CAPS_PLUS200GB')
    for key in ('resource_authority_reference','cost_decision_reference','format_authority_reference'):
        Q.need(plan[key] in plan['source_references'],'APPROVED_SMALL_AUTHORITY:'+key)
    authority=Q.load_ref(plan['resource_authority_reference']);cost=Q.load_ref(plan['cost_decision_reference'])
    Q.need(authority['schema']=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and authority['status']=='USER_AUTHORIZED'
        and authority['endpoint']==Q.ENDPOINT and authority['observed_uid']==1264,'USER_ALPHA_AUTHORITY')
    Q.need(cost['schema']=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1' and cost['status']=='USER_AUTHORIZED'
        and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'REPORT_COST_CONTINUE_QUALITY_UNCHANGED')
    frozen=Q.load_ref(plan['format_authority_reference']);Q.need(plan['format_authority_reference']==Q.ref(C.AUTHORITY_HERE/'format792_authority.json')
        and frozen['schema']=='ACTUAL792_SIX_CSV_PHYSICAL_IDENTITY_AUTHORITY_V1' and frozen['actual_job_id']=='1884792'
        and [s['source_id'] for s in frozen['sources']]==list(C.IDS),'FROZEN_ACTUAL792_SIX_CSV_AUTHORITY')
    for name in ('format_receipt_reference','format_plan_reference','format_proof_reference'):
        Q.need(frozen[name] in plan['parent_evidence_references'],'ACTUAL792_PARENT_PIN:'+name)
    receipt=Q.load_ref(frozen['format_receipt_reference']);old_plan=Q.load_ref(frozen['format_plan_reference']);old_proof=Q.load_ref(frozen['format_proof_reference'])
    Q.need(receipt['schema']=='MISSING11_IDENTITY_INPUT_FORMAT_PROFILE_RECEIPT_V1' and receipt['status']=='FORMAT_METADATA_PROFILE_COMPLETE_IDENTITY_ACCEPTANCE_PENDING'
        and receipt['job_id']=='1884792' and receipt['uid']==1264 and receipt['endpoint']==Q.ENDPOINT and receipt['node'] in Q.NODES
        and receipt['plan_reference']==frozen['format_plan_reference'] and receipt['startup_proof_reference']==frozen['format_proof_reference']
        and old_plan['producer_key']=='moleculenet_missing11_identity_format_probe_alpha_v1' and old_plan['endpoint']==Q.ENDPOINT
        and old_plan['uid']==1264 and old_plan['cpus']==16 and old_plan['node']==receipt['node']
        and old_proof['uid']==1264 and old_proof['endpoint']==Q.ENDPOINT and old_proof['node']==receipt['node']
        and str(old_proof['job_id'])=='1884792' and old_proof['plan_reference']==frozen['format_plan_reference'],'ACTUAL792_PLAN_PROOF_RECEIPT_BINDING')
    account(plan['format_accounting_reference'],'1884792',plan['parent_evidence_references'])
    Q.need(receipt['fixtures_reference'] in plan['parent_evidence_references'],'ACTUAL792_EIGHT_FIXTURE_PIN')
    tests=Q.load_ref(receipt['fixtures_reference']);Q.need(tests['status']=='PASS' and tests['counts']=={'run':8,'failures':0,'errors':0,'skips':0,'expected_failures':0,'unexpected_successes':0},'ACTUAL792_EIGHT_BOUNDARIES_PASS')
    for source in frozen['sources']:
        value=source['format_report_reference'];Q.need(value in plan['source_references'] and any(r['source_id']==source['source_id'] and r['report_reference']==value for r in receipt['reports']),'ACTUAL792_SIX_REPORT_PINS')
        report=Q.load_ref(value);Q.need(report['status']=='CSV_INPUT_METADATA_OBSERVED' and report['error'] is None and report['payload_reference']==source['payload_reference']
            and report['CSV']==source['expected_CSV_summary'] and report['CSV']['record_counts']['physical_data_records']==C.COUNTS[source['source_id']], 'ACTUAL792_EXACT_HEADER_COUNTS_AND_IDENTITY_COLUMNS')
    Q.need(plan['data_references']==[s['payload_reference'] for s in frozen['sources']],'SIX_ORIGINAL_PAYLOADS_IN_FROZEN_ORDER')
    for value in frozen['frozen_helper_source_references']:Q.need(value in plan['source_references'],'EVERY_ACTUAL_ORIGINAL_FORMAT_B_AND_IDENTITY_SOURCE_REQUIRED')
    Q.need(receipt['fixtures_reference'] in plan['parent_evidence_references'],'HISTORICAL_FORMAT_TEST_REFERENCE_REQUIRED')
    Q.need(tests['source_reference'] in plan['source_references'],'EXACT_ORIGINAL_EIGHT_FIXTURE_SOURCE_REQUIRED')
    Q.need(scope_ref['path']==str(C.ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'),'EXACT_CURRENT_NEWLINE_SCOPE7')
    out=Q.literal(plan['output_directory']);Q.need(C.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_OUTPUT_LEAF_ONLY')
    return plan,proof,frozen
