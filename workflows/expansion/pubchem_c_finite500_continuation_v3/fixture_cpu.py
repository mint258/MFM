"""Fixed state5 only, independent fresh Alpha proof; no range, Budget, DATA or claim."""
import argparse,hashlib,json,os,socket,sys,time,traceback,unittest
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
HERE=Q.ROOT/'code/pubchem_c_finite500_continuation_v3';QUEUE=Q.ROOT/'code/secondary_cpu_readonly_pubchem_cont_v1'
FILES=('__init__.py','controller.py','state.py','test_state.py')
KEY='pubchem_c_continuation_state5_alpha_v3';MODULE='pubchem_c_finite500_continuation_v3.fixture_cpu'
PLAN='SECONDARY_PUBCHEM_CONTINUATION_STATE5_PLAN_V3';PROOF='SECONDARY_PUBCHEM_CONTINUATION_STATE5_STARTUP_V3'
STAGE='PUBCHEM_C_CONTINUATION_STATE5_NO_DATA';CAP=64<<20;WALL=600;MODE='FIXTURE_ONLY'
STORAGE_SCOPE=Q.ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'
PARAMETERS={'stage':'FIXED_FIVE_STATE_BOUNDARIES_ONLY','methods':5,'tested_controller_source_files':4,'scientific_DATA_read':False,
    'range_authority_required':False,'Budget_constructed':False,'ProcessPool_started':False,'ordinal_claim_written':False,
    'Slurm_submitted_by_fixture':False,'original_partition_and_no_retry_checks':True,'new_UFF_QM_training_calls':0}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')


def tested_sources():return [Q.ref(HERE/n) for n in FILES]
def sources():return [*tested_sources(),Q.ref(HERE/'fixture_cpu.py'),Q.ref(QUEUE/'controller.py'),Q.ref(QUEUE/'adapters.py'),
    Q.ref(Q.ROOT/'code/pubchem_c_finite500_queue_v2/state.py'),*[Q.ref(p) for p in sorted(Q.PACKAGE.glob('*.py'))]]


def validate_metadata(plan):
    Q.need(plan['schema']==PLAN and plan['producer_key']==plan['scope_key']==KEY and plan['scope_parameters']==PARAMETERS and plan['stage']==STAGE
        and plan['scope_mode']==MODE and plan['performance_profile'] is False and plan['kind']=='analysis' and plan['pilot'] is False
        and plan['endpoint']==Q.ENDPOINT and plan['uid']==1264 and plan['run_root']==str(Q.ROOT) and plan['node'] in Q.NODES
        and plan['cpus']==16 and plan['memory_policy']==Q.POLICY and plan['wall_seconds']==600 and plan['output_cap_bytes']==CAP
        and plan['data_references']==plan['parent_evidence_references']==[],'ONLY_FIXED_STATE5_NO_PRODUCTION_OR_RANGE_DEPENDENCY')
    review=Q.load_ref(plan['root_review_reference']);Q.need(review['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','ROOT_EXACT_STATE5_SCOPE_APPROVAL')
    for key in REVIEW_FIELDS:Q.need(plan[key]==review[key],'FIXTURE_REVIEW_FIELD:'+key)
    Q.need(plan['source_references']==review['approved_source_references'],'EXACT_APPROVED_STATE5_SOURCE_SET')
    for r in sources():Q.need(r in plan['source_references'],'ALL_ACTUAL_TESTED4_ENTRY_QUEUE_BASE_SOURCE_PINS')
    Q.need(plan['resource_authority_reference'] in plan['source_references'] and Q.ref(STORAGE_SCOPE) in plan['source_references'],'ACTUAL_ALPHA_AUTHORITY_AND_STORAGE7_SOURCE')
    Q.authority(plan['resource_authority_reference']['path'])
    for r in plan['source_references']:Q.verify(r)
    return True


def require_startup(plan_path,proof_path):
    plan=Q.load(plan_path);proof=Q.load(proof_path);validate_metadata(plan)
    argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==HERE/'fixture_cpu.py' and Path(sys.executable).absolute()==Path(plan['python']).absolute()
        and sys.argv==[str(HERE/'fixture_cpu.py'),*argv[4:]] and plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),'ACTUAL_FIXED_STATE5_PRIMARY_FULL_ARGV')
    declared={r['path']:{k:r[k] for k in ('path','bytes','sha256')} for r in proof['source_target_verification']}
    for r in [*plan['source_references'],plan['root_review_reference'],Q.ref(plan_path)]:
        Q.need(declared.get(r['path'])==r,'ACTUAL_STATE5_SOURCE_TARGET_VERIFICATION');Q.verify(r)
    Q.need(proof['schema']==PROOF and proof['scope_key']==KEY and proof['stage']==STAGE and proof['scope_mode']==MODE
        and proof['performance_profile'] is False and proof['endpoint']==Q.ENDPOINT and proof['uid']==os.getuid()==1264
        and proof['node']==plan['node']==socket.gethostname().split('.')[0] and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        and 0<=time.time()-proof['observed_unix_seconds']<=120 and proof['plan_reference']==Q.ref(plan_path)
        and proof['root_review_reference']==plan['root_review_reference'],'FRESH_REAL_ALPHA_STATE5_IDENTITY_NOT_MAIN_OR_FUTURE_PROOF')
    Q.need(proof['request']=={'kind':'analysis','pilot':False,'cpus':16,'memory_policy':Q.POLICY,'wall_seconds':600,'execution_argv':argv}
        and proof['memory_policy']==Q.POLICY and proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False,'EXACT_CPU16_NO_REQUESTED_MEMORY')
    env=os.environ;Q.need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('SLURM_CPUS_PER_TASK')=='16'
        and env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'REAL_CPU_ENVIRONMENT')
    job=Q.fields(proof['job_metadata']);Q.need(job['JobId']==str(proof['job_id']) and job['UserId']=='alpha(1264)' and job['JobState']=='RUNNING'
        and job['NodeList']==plan['node'] and job['Partition']=='cpu' and job['NumCPUs']=='16' and job['NumTasks']=='1'
        and job['Requeue']=='0' and job['Command']==proof['script_reference']['path'] and Q.duration(job['TimeLimit'])==600,'ACTUAL_RUNNING_JOB_SCRIPT_WALL')
    signer=proof['controller_evidence'];Q.need(signer['endpoint']==Q.ENDPOINT and signer['uid']==1264 and signer['hostname']=='sonmi'
        and signer['proof_is_not_created_by_scientific_worker'] is True and signer['actual_script_reference']==proof['script_reference'],'INDEPENDENT_LOGIN_PROOF')
    for line in Q.read_small(Q.verify(proof['script_reference'])).decode().splitlines():
        if line.strip().startswith('#SBATCH'):Q.need(not any(v in line for v in ('--mem','--exclusive','--gpu','--gres')),'NO_MEMORY_OR_GPU_OR_EXCLUSIVE_DIRECTIVE')
    identity=Q.self_identity();gate=proof['actual_gate_process']
    Q.need(all(gate[k]==identity[k] for k in ('pid','uid','start_ticks','pgid','sid','cgroup_sha256')),'SAME_ATTESTED_GATE_PROCESS_AFTER_EXEC')
    storage=proof['storage_observation'];raw=Q.load_ref(proof['storage_observation_reference']);scope_ref=storage['storage_scope_review_reference']
    Q.need(scope_ref['path']==str(STORAGE_SCOPE) and declared.get(scope_ref['path'])==scope_ref and raw['uid']==1264
        and raw['node']==proof['node'] and raw['run_root']==str(Q.ROOT) and raw['observed_unix_seconds']==storage['observed_unix_seconds'],'ACTUAL_STORAGE7_RAW_SCOPE_AND_NODE')
    scope=Q.load_ref(scope_ref);extra=sum(r['whole_output_cap_bytes'] for r in scope.get('additional_task_output_reservations',[]));reserved=storage['whole_output_caps_reserved_bytes']-extra
    Q.need(reserved>=CAP and Q.effective_storage(raw,scope_ref['path'],reserved,reservation_evidence=storage['registered_task_reservation_evidence'])==storage
        and proof['account_free_bytes']==storage['effective_free_bytes'] and 0<=time.time()-storage['observed_unix_seconds']<=120,'REAL_CURRENT_STORAGE_CAPS_PLUS200GB')
    return plan,proof


def cpu(plan_path,proof_path):
    plan,proof=require_startup(plan_path,proof_path);out=Q.literal(plan['output_directory'])
    Q.need(Q.ROOT/'artifacts/pubchem_continuation_state5_alpha_v3' in out.parents and not out.exists(),'NEW_FIXED_STATE5_OUTPUT_ONLY');out.mkdir(parents=True,mode=0o700)
    tested=tested_sources();report=None
    try:
        from .test_state import Boundaries
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==5,'EXACT_FIVE_FIXED_STATE_METHODS')
        result=unittest.TextTestRunner(verbosity=2).run(suite);ok=result.testsRun==5 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses)
        report={'schema':'PUBCHEM_CONTINUATION_STATE5_CPU_RECEIPT_V3','status':'PASS_PENDING_REAL_TERMINAL_ACCOUNTING' if ok else 'FAIL',
            'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
            'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses),
            'failure_details':[{'test':t.id(),'traceback':e} for t,e in result.failures],'error_details':[{'test':t.id(),'traceback':e} for t,e in result.errors],
            'scientific_body_reads':0,'Budget_constructed':False,'ProcessPool_started':False,'ordinal_claim_written':False,
            'actual_runtime':{'endpoint':Q.ENDPOINT,'uid':os.getuid(),'node':proof['node'],'job_id':str(proof['job_id']),'cpus':16,'boot_id':proof['boot_id']},
            'source_references':tested,'tested_source_references':tested,'admitted_source_references':plan['source_references'],
            'plan_reference':Q.ref(plan_path),'startup_proof_reference':Q.ref(proof_path),'actual_parent':None,
            'actual_terminal_accounting_required':True,'range_authority_created':False,'new_UFF_QM_calls':0}
        Q.need(len(Q.canonical(report))<CAP and sum(p.stat().st_size for p in out.iterdir() if p.is_file())+len(Q.canonical(report))<CAP,'FINITE64MIB_METADATA_OUTPUT')
        Q.write_new(out/'receipt.json',report);return 0 if ok else 3
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'status':'STATE5_FAILED_NO_SCIENCE_OR_RANGE','error':repr(exc),'traceback':traceback.format_exc(),
            'actual_job_id':str(proof['job_id']),'scientific_body_reads':0,'parent_terminal_accounting_pending':True});raise


def metadata(a):
    Q.login();Q.need(a.authority and a.node and a.plan_path and a.stage_output and a.proof_path and a.metadata_output,'EXACT_FIXED_STATE5_METADATA_ARGUMENTS')
    out=Q.literal(a.metadata_output);plan_path=Q.literal(a.plan_path);output=Q.literal(a.stage_output);proof=Q.literal(a.proof_path)
    Q.need(Q.ROOT/'control' in out.parents and not out.exists() and Q.ROOT/'control' in plan_path.parents and not plan_path.exists()
        and Q.ROOT/'artifacts/pubchem_continuation_state5_alpha_v3' in output.parents and not output.exists() and not proof.exists()
        and a.node in Q.NODES,'NEW_FIXED_FIXTURE_METADATA_PATHS');out.mkdir(parents=True,mode=0o700)
    authority=Q.ref(a.authority);Q.authority(a.authority);refs=sources()+[authority,Q.ref(STORAGE_SCOPE)]
    argv=[a.python,'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof)]
    plan={'schema':PLAN,'producer_key':KEY,'scope_key':KEY,'scope_parameters':PARAMETERS,'stage':STAGE,'scope_mode':MODE,'performance_profile':False,
        'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'node':a.node,'kind':'analysis','pilot':False,'cpus':16,'memory_policy':Q.POLICY,
        'wall_seconds':600,'output_cap_bytes':CAP,'python':a.python,'execution_argv':argv,'startup_proof_path':str(proof),'output_directory':str(output),
        'source_references':refs,'data_references':[],'parent_evidence_references':[],'resource_authority_reference':authority}
    review={k:plan[k] for k in REVIEW_FIELDS};review.update(schema='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1',status='ROOT_REVIEW_REQUIRED',reviewer='UNSIGNED',
        proposed_runtime_status='APPROVED_FOR_EXACT_STAGE',approved_source_references=refs,root_review_reason=None)
    if a.scope_review:
        approved=Q.load(a.scope_review);Q.need(approved['status']=='APPROVED_FOR_EXACT_STAGE' and approved['reviewer']=='root','ROOT_FIXED_STATE5_SCOPE_APPROVAL')
        for k,v in review.items():
            if k not in ('status','reviewer','proposed_runtime_status','root_review_reason'):Q.need(approved[k]==v,'EXACT_FIXED_SCOPE:'+k)
        plan['root_review_reference']=Q.ref(a.scope_review);plan_path.parent.mkdir(parents=True,exist_ok=True);Q.write_new(plan_path,plan)
    else:Q.write_new(out/'scope_candidate.json',review);Q.write_new(out/'plan_candidate.json',plan)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path);p.add_argument('--startup-proof',type=Path)
    for name in ('authority','plan-path','stage-output','proof-path','metadata-output','scope-review'):p.add_argument('--'+name,type=Path)
    p.add_argument('--node');p.add_argument('--python',default=str(Q.ROOT/'chemprop_compatible_v2/bin/python'));a=p.parse_args()
    if a.metadata_output:metadata(a);return 0
    Q.need(a.plan and a.startup_proof,'ONLY_FIXED_STATE5_CPU_ENTRY_OR_EXPLICIT_METADATA_MODE');return cpu(a.plan,a.startup_proof)


if __name__=='__main__':raise SystemExit(main())
