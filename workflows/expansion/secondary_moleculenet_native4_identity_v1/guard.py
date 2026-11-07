"""Independent fresh Alpha gate, exact Root scope, actual792/B3 parent receipts."""
import hashlib,os,socket,sys,time
from pathlib import Path
from secondary_moleculenet_csv6_identity_v1.guard import account
from . import contracts as C
Q=C.Q


def require_startup(plan_path,proof_path):
    plan=Q.load(plan_path);proof=Q.load(proof_path);a=C.authority(plan);primary=C.HERE/'run.py'
    argv=[plan['python'],'-B','-m',C.MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    Q.need(plan['schema']==C.PLAN and proof['schema']==C.PROOF and plan['producer_key']==plan['scope_key']==C.KEY and plan['scope_parameters']==C.PARAMETERS
        and plan['stage']==C.STAGE and plan['scope_mode']==C.SCOPE and plan['performance_profile'] is True and plan['mode']=='profile'
        and plan['kind']=='analysis' and plan['pilot'] is True and plan['endpoint']==Q.ENDPOINT and plan['uid']==1264 and plan['run_root']==str(C.ROOT)
        and plan['node'] in Q.NODES and plan['cpus']==16 and plan['memory_policy']==Q.POLICY and plan['wall_seconds']==14400 and plan['output_cap_bytes']==C.CAP,'EXACT_NATIVE4_PROFILE_SCOPE')
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==primary and sys.argv==[str(primary),*argv[4:]]
        and Path(sys.executable).absolute()==Path(plan['python']).absolute() and sys.version_info[:3]==(3,11,14)
        and plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),'EXACT_PRIMARY_FULL_ARGV_AND_SAMPLER')
    review=Q.load_ref(plan['root_review_reference']);Q.need(review['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','INDEPENDENT_EXACT_ROOT_REVIEW')
    for k in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot','wall_seconds','output_cap_bytes',
              'execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile'):
        Q.need(plan[k]==review[k],'EXACT_ROOT_FIELD:'+k)
    Q.need(plan['source_references']==review['approved_source_references'] and review['source_only_PDB_seam_and_MOL2_unknowns_reviewed'] is True
        and review['full_or_pool_release'] is False,'EXACT_SOURCE_SET_AND_NATIVE_SEAMS_REVIEWED')
    bodies={r['path'] for r in plan['data_references']};Q.need(not bodies.intersection(r['path'] for r in [*plan['source_references'],*plan['parent_evidence_references']]),'NO_ORIGINAL_BODIES_BEFORE_FIXTURES')
    declared={r['path']:{k:r[k] for k in ('path','bytes','sha256')} for r in proof['source_target_verification']}
    for ref in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],Q.ref(plan_path)]:
        Q.need(declared.get(ref['path'])==ref,'EXACT_SIGNED_SMALL_SOURCE_OR_PARENT');Q.verify(ref)
    for path in [*(C.HERE/n for n in C.FILES),Path(Q.__file__),Path(Q.__file__).parent/'__init__.py']:
        Q.need(Q.ref(path) in plan['source_references'],'ALL_NEW_AND_BASE_SOURCES_PINNED')
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if name.startswith('secondary_') and path and Path(path).suffix=='.py':
            Q.need(C.ROOT/'code' in Path(path).absolute().parents and Q.ref(path) in plan['source_references'],'EVERY_ACTUAL_ALPHA_IMPORT_PIN:'+name)
    Q.need(proof['endpoint']==Q.ENDPOINT and proof['uid']==os.getuid()==1264 and proof['node']==plan['node']==socket.gethostname().split('.')[0]
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and 0<=time.time()-proof['observed_unix_seconds']<=120
        and proof['plan_reference']==Q.ref(plan_path) and proof['root_review_reference']==plan['root_review_reference'],'FRESH_ALPHA1264_PROOF_NOT_MAIN')
    Q.need(proof['request']=={'kind':'analysis','pilot':True,'cpus':16,'memory_policy':Q.POLICY,'wall_seconds':14400,'execution_argv':argv}
        and proof['scope_key']==C.KEY and proof['scope_mode']==C.SCOPE and proof['performance_profile'] is True
        and proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False,'HONEST_NATIVE_PROFILE_RESOURCES')
    env=os.environ;Q.need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('SLURM_CPUS_PER_TASK')=='16'
        and env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'ACTUAL_CPU16_THREADS')
    job=Q.fields(proof['job_metadata']);Q.need(job['JobId']==str(proof['job_id']) and job['UserId']=='alpha(1264)' and job['JobState']=='RUNNING'
        and job['NodeList']==plan['node'] and job['Partition']=='cpu' and job['NumCPUs']=='16' and job['NumTasks']=='1' and job['Requeue']=='0'
        and job['Command']==proof['script_reference']['path'] and Q.duration(job['TimeLimit'])==14400,'ACTUAL_RUNNING_ALPHA_SCRIPT_WALL')
    signer=proof['controller_evidence'];Q.need(signer['endpoint']==Q.ENDPOINT and signer['uid']==1264 and signer['hostname']=='sonmi'
        and signer['proof_is_not_created_by_scientific_worker'] is True and signer['actual_script_reference']==proof['script_reference'],'INDEPENDENT_ALPHA_CONTROLLER')
    for line in Q.read_small(Q.verify(proof['script_reference'])).decode().splitlines():
        if line.strip().startswith('#SBATCH'):Q.need(not any(x in line for x in ('--mem','--exclusive','--gpu','--gres')),'NO_MEMORY_EXCLUSIVE_GPU')
    gate=proof['actual_gate_process'];tail=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    Q.need(gate['pid']==os.getpid() and gate['uid']==1264 and gate['start_ticks']==int(tail[19]) and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0)
        and gate['cgroup_sha256']==hashlib.sha256(Path('/proc/self/cgroup').read_bytes()).hexdigest(),'ACTUAL_ATTESTED_GATE_PROCESS')
    storage=proof['storage_observation'];raw=Q.load_ref(proof['storage_observation_reference']);sr=storage['storage_scope_review_reference'];Q.need(declared.get(sr['path'])==sr,'SIGNED_CURRENT_STORAGE_SCOPE')
    scope=Q.load_ref(sr);extra=sum(v['whole_output_cap_bytes'] for v in scope.get('additional_task_output_reservations',[]));reserved=storage['whole_output_caps_reserved_bytes']-extra
    Q.need(raw['uid']==1264 and raw['node']==plan['node'] and raw['run_root']==str(C.ROOT) and raw['observed_unix_seconds']==storage['observed_unix_seconds']
        and reserved>=C.CAP and Q.effective_storage(raw,sr['path'],reserved,reservation_evidence=storage['registered_task_reservation_evidence'])==storage
        and proof['account_free_bytes']==storage['effective_free_bytes'] and 0<=time.time()-storage['observed_unix_seconds']<=120,'RECOMPUTED_ALL_REGISTERED_CAPS_AND200GB')
    for k in ('resource_authority_reference','cost_decision_reference'):Q.need(plan[k] in plan['source_references'],'ACTUAL_ALPHA_AUTHORITY_PIN')
    auth=Q.load_ref(plan['resource_authority_reference']);cost=Q.load_ref(plan['cost_decision_reference'])
    Q.need(auth['schema']=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and auth['status']=='USER_AUTHORIZED' and auth['endpoint']==Q.ENDPOINT and auth['observed_uid']==1264,'USER_ALPHA_AUTHORITY')
    Q.need(cost['schema']=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1' and cost['status']=='USER_AUTHORIZED'
        and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'COST_CONTINUE_QUALITY_UNCHANGED')
    parents=plan['parent_evidence_references']
    for k in ('format_receipt_reference','format_plan_reference','format_proof_reference','format_fixture_reference'):Q.need(a[k] in parents,'ACTUAL792_PARENT:'+k)
    receipt=Q.load_ref(a['format_receipt_reference']);old=Q.load_ref(a['format_plan_reference']);ps=Q.load_ref(a['format_proof_reference'])
    Q.need(receipt['job_id']=='1884792' and receipt['uid']==1264 and receipt['endpoint']==Q.ENDPOINT and receipt['status']=='FORMAT_METADATA_PROFILE_COMPLETE_IDENTITY_ACCEPTANCE_PENDING'
        and receipt['plan_reference']==a['format_plan_reference'] and receipt['startup_proof_reference']==a['format_proof_reference']
        and old['uid']==1264 and old['endpoint']==Q.ENDPOINT and ps['uid']==1264 and ps['endpoint']==Q.ENDPOINT and str(ps['job_id'])=='1884792'
        and ps['plan_reference']==a['format_plan_reference'],'EXACT_ACTUAL792_PLAN_PROOF')
    tests=Q.load_ref(a['format_fixture_reference']);Q.need(tests['status']=='PASS' and tests['counts']=={'run':8,'failures':0,'errors':0,'skips':0,'expected_failures':0,'unexpected_successes':0},'ACTUAL792_FORMAT8_NOT_B3')
    account(plan['format_accounting_reference'],'1884792',parents)
    for source in a['sources']:
        ref=source['format_report_reference'];Q.need(ref in plan['source_references'] and any(v['source_id']==source['source_id'] and v['report_reference']==ref for v in receipt['reports']),'EXACT792_REPORT_SOURCE')
        r=Q.load_ref(ref);Q.need(r['payload_reference']==source['payload_reference'] and r['inventory']['inventory_reference']==source['inventory_reference']
            and r['inventory']['category_counts']==source['category_counts'],'UNCHANGED_ACTUAL_FORMAT_INPUT_LOCATORS')
    kr=plan['kernel_profile_receipt_reference'];Q.need(kr in parents,'ACTUAL_OLD_B3_PARENT_REFERENCE');kernel=Q.load_ref(kr)
    Q.need(kernel['schema']=='SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_RECEIPT_V1' and kernel['status']=='SAMPLED_FROZEN_IDENTITY_KEY_OBSERVATIONS_COMPLETE'
        and kernel['job_id']=='1884785' and kernel['uid']==1264 and kernel['endpoint']==Q.ENDPOINT
        and kernel['fixtures']=={'tests_run':3,'failures':0,'errors':0,'skips':0,'before_A_body_IO':True},'ACTUAL1884785_B3_PASS_NOT_REEXECUTED')
    for ref in (kernel['plan'],kernel['startup_proof']):Q.need(ref in parents,'ACTUAL_B_PLAN_PROOF_PIN')
    kp=Q.load_ref(kernel['plan']);sp=Q.load_ref(kernel['startup_proof']);Q.need(kp['frozen_identity_source_references']==plan['frozen_identity_source_references']
        and sp['uid']==1264 and sp['endpoint']==Q.ENDPOINT and str(sp['job_id'])=='1884785' and sp['plan_reference']==kernel['plan'],'ACTUAL_SAME_FROZEN_KERNEL_PLAN_PROOF')
    for name in ('__init__.py','contracts.py','runtime.py','run.py'):
        Q.need(Q.ref(C.ROOT/'code/secondary_coconut_identity_norm_profile_v1'/name) in kp['source_references'],'UNCHANGED_ACTUAL_B_PROFILE_KERNEL_SOURCE')
    account(plan['kernel_profile_accounting_reference'],'1884785',parents)
    return plan,proof,a
