"""Root-only one-phase WP5 main and dependent cleanup submission."""
import argparse,ast,getpass,hashlib,json,os,socket,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
PRIOR_SUBMISSIONS=(ROOT/'submission/submitted_jobs.json',
    ROOT/'submission/recovery_attempt_v11/submitted_jobs.json',
    ROOT/'submission/startup_replacement_v1/submitted_jobs.json')
PRIOR_COUNTS=(78,78,73)
FROZEN_R12_SHA='91ec1ce7bf82589b647db43502bc86f9bb2c7c0a98a845ef28446703cc48d278'
NODES={f'compute-0-{n}' for n in (12,13,14,17,18,19)}
PYTHON='/share/home/zixiao/.conda/envs/chemprop/bin/python'

def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):value.update(block)
    return value.hexdigest()
def atomic(path,obj):
    temp=path.with_name(path.name+'.pending')
    with temp.open('w') as stream:
        json.dump(obj,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)

def validate_authority(node_authority,tasks):
    authority=json.loads(node_authority.read_text())
    slots={'compute-0-12':4,'compute-0-13':4,'compute-0-14':4,'compute-0-17':8,'compute-0-18':4,'compute-0-19':5}
    mapping={'compute-0-15':'compute-0-12','compute-0-16':'compute-0-13'}
    if authority.get('schema')!='WP5_NODE_REPLACEMENT_USER_APPROVAL_V1' or authority.get('status')!='USER_APPROVED':
        raise ValueError('Actual explicit user-approved node authority required')
    if authority.get('server')!='zixiao@202.38.247.57:22' or authority.get('project')!='/share/home/zixiao/descriptor_analysis':
        raise ValueError('Node authority applies to exact development server/project')
    if authority.get('old_to_new')!=mapping or authority.get('authorized_node_slots')!=slots:
        raise ValueError('Node authority exact map/29slots differs')
    if authority.get('per_formal_job')!={'cpus':24,'memory_gib':32,'slurm_hours':48,'internal_cutoff_hours':46}:
        raise ValueError('Node authority changes formal resource/deadline recipe')
    if authority.get('G3_capacity_waived') is not False or authority.get('other_gates_and_200_recompute_waived') is not False or authority.get('scientific_configuration_changed') is not False:
        raise ValueError('Node authorization does not waive capacity/gates/200 or change science')
    manifest=json.loads((ROOT/'packing/node_assignment_v3/manifest.json').read_text())
    if manifest.get('schema')!='WP5_NODE_ASSIGNMENT_V3' or manifest['tasks_sha256']!=digest(ROOT/'packing/node_assignment_v3/tasks.json'):
        raise ValueError('New task authority manifest SHA differs')
    if manifest['user_approval']!={'path':str(node_authority),'sha256':digest(node_authority)}:
        raise ValueError('New task authority does not bind actual approval')
    if digest(manifest['source_tasks'])!=manifest['source_tasks_sha256']:
        raise ValueError('Original task authority changed')
    original={str(item['task_id']):item for item in json.loads(Path(manifest['source_tasks']).read_text())['tasks']}
    if len(original)!=72 or len(tasks)!=72:raise ValueError('Exact72tasks required')
    for task in tasks:
        expected=dict(original[str(task['task_id'])]);expected['node']=mapping.get(expected['node'],expected['node'])
        if task!=expected:raise ValueError('Task content changed beyond approved node value:'+str(task['task_id']))

def prior_submission_bindings():
    refs=[];identifiers=[];used_authorities=[]
    for path,expected in zip(PRIOR_SUBMISSIONS,PRIOR_COUNTS):
        content=json.loads(path.read_text());entries=content['main']+content['cleanup']
        ids=[str(row['job_id']) for row in entries]
        if len(ids)!=expected or len(set(ids))!=expected:raise ValueError('Actual prior job map count/IDs differs: '+str(path))
        refs.append({'path':str(path),'sha256':digest(path),'main':len(content['main']),'cleanup':len(content['cleanup']),'status':content['status']});identifiers.extend(ids)
        for key in ('recovery_authority','user_authority'):
            if isinstance(content.get(key),dict) and content[key].get('path') and content[key].get('sha256'):
                used_authorities.append(content[key])
    if len(identifiers)!=229 or len(set(identifiers))!=229:raise ValueError('All three actual prior phases must close exact229 unique IDs')
    return refs,sorted(identifiers,key=int),used_authorities

def fresh_all_prior_terminal(plan):
    refs,ids,_=prior_submission_bindings()
    if refs!=plan['prior_submissions'] or ids!=plan['prior_job_ids']:raise ValueError('Prepared prior phases changed')
    path=ROOT/'reports/observation_latest.json';raw=path.read_bytes();observation=json.loads(raw)
    age=time.time()-observation['time']
    if age< -30 or age>180:raise ValueError('Fresh actual all229 scheduler closure is required')
    states=observation['registered_job_states'];closed={}
    terminal={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','PREEMPTED','BOOT_FAIL'}
    for job in ids:
        value=states.get(job)
        state=value.split()[0].rstrip('+') if isinstance(value,str) and value else None
        if state not in terminal:raise ValueError('Prior job active, missing or unsupported terminal state: '+job+' '+str(value))
        closed[job]=state
    return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'observed_epoch':observation['time'],
            'unique_jobs':229,'all_registered_jobs_terminal':True,'states':closed}

def validate_recovery_evidence(authority,plan,prepared,authority_path):
    refs,ids,used=prior_submission_bindings()
    actual_authority={'path':str(authority_path),'sha256':digest(authority_path)}
    if any(actual_authority['sha256']==ref['sha256'] or authority_path.resolve()==Path(ref['path']).resolve() for ref in used):
        raise ValueError('Previously used R11 phase or69+4 authorization cannot authorize a new R12 phase')
    if authority.get('prior_submissions')!=refs or authority.get('prepared_plan')!={'path':str(prepared),'sha256':digest(prepared)}:
        raise ValueError('New actual user authority must bind all229 prior jobs and exactprepared12')
    evidence=authority.get('queue_reconciliation_report',{})
    if not evidence.get('path') or digest(evidence['path'])!=evidence.get('sha256'):
        raise ValueError('Actual terminal reconcile_v3 apply report required')
    report=json.loads(Path(evidence['path']).read_text())
    if report.get('schema')!='WP5_TERMINAL_SUBSET_RECONCILIATION_APPLY_V3' or report.get('status')!='APPLIED_AND_VERIFIED':
        raise ValueError('Partial/old reconciliation cannot authorize formalR12')
    if any(report.get(key) is not True for key in ('all_registered_jobs_terminal','plan_was_all229_terminal','full229_terminal_scope_verified','all_applied_rows_verified')) or report.get('plan_skipped_count')!=0:
        raise ValueError('Partial/old reconciliation cannot authorize formalR12')
    if report.get('prior_submissions')!=refs or report.get('protected_jobs')!={} or report.get('protected_tasks')!=[]:
        raise ValueError('Reconciliation all229 ownership/protected jobs not closed')
    plan_ref=report['plan']
    if digest(plan_ref['path'])!=plan_ref['sha256']:raise ValueError('Reconciliation actualplan SHA differs')
    reconcile_plan=json.loads(Path(plan_ref['path']).read_text())
    if reconcile_plan.get('protected_jobs')!={}:raise ValueError('Reconciliation plan still protects active jobs')
    bootstrap=authority.get('queue_bootstrap_report',{})
    if not bootstrap.get('path') or digest(bootstrap['path'])!=bootstrap.get('sha256'):
        raise ValueError('Actual productionR12 metadata bootstrap evidence required')
    proof=json.loads(Path(bootstrap['path']).read_text())
    if proof.get('schema')!='WP5_R12_PRODUCTION_BOOTSTRAP_V1' or proof.get('status')!='BOOTSTRAP_SCHEMA_VERIFIED':
        raise ValueError('Production bootstrap not actually verified')
    contract=json.loads(Path(plan['production_contract']['path']).read_text())
    runtime=contract['current_runtime']['wp5_runner_v12.py']
    if proof.get('queue_path')!=str(ROOT/'queue/pending.sqlite') or proof.get('runner')!=runtime or proof.get('contract')!=plan['production_contract'] or proof.get('uid')!=1278:
        raise ValueError('Production bootstrap queue/runner/contract/UID differs')
    result=proof.get('result',{})
    if result.get('status')!='SCHEMA_READY_READ_ONLY' or result.get('path')!=str(ROOT/'queue/pending.sqlite') or result.get('bootstrap_explicit') is not True:
        raise ValueError('Production bootstrap result missing exactschema/path evidence')
    if not {'export_repairs','meta','molecules','sessions','tasks'}<=set(result.get('tables',[])):
        raise ValueError('Production bootstrap expected tables not closed')
    if not {'pending_order','completion_order','owner_state_order','cleanup_pending_cost','cleanup_task_pending_cost'}<=set(result.get('indices',[])):
        raise ValueError('Production bootstrap required metadata indexes missing')
    support=result.get('summary_index_support',{})
    if not support.get('state_record_count_covering_index') or not support.get('durable_receipt_partial_index'):
        raise ValueError('Production bootstrap real narrow summary indexes missing')
    return {'queue_reconciliation_report':evidence,'queue_bootstrap_report':bootstrap}

POLICY='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT'
TRACE_FIELDS=('status','software_version_id','elapsed_seconds','scf_iterations','converged','input_file_sha256')
def validate_current_contract(path,node_authority):
    if path.resolve()!=(ROOT/'configs/production_contract_v5.json').resolve():raise ValueError('Actual newcontract5 required')
    contract=json.loads(path.read_text())
    if contract.get('schema')!='WP5_PRODUCTION_CONTRACT_V1' or contract.get('status')!='PRODUCTION_CONTRACT_FROZEN' or contract.get('policy')!=POLICY:
        raise ValueError('Actual current user-override contract must be frozen')
    for key in ('audit_manifest','reproduction_package','protocol','registry','node_authority','node_scope_plan','authority'):
        ref=contract[key]
        if digest(ref['path'])!=ref['sha256']:raise ValueError('Frozen production ref differs:'+key)
    if contract['node_authority']!={'path':str(node_authority),'sha256':digest(node_authority)}:
        raise ValueError('Production contract actual approved node receipt differs')
    if contract['node_scope_plan']!={'path':str(ROOT/'packing/node_assignment_v3/tasks.json'),'sha256':digest(ROOT/'packing/node_assignment_v3/tasks.json')}:
        raise ValueError('Production contract is not actual immutable72-task authority')
    if contract['authority']['sha256']!='b368187eb93d0641c0628fc33ed447192cf0e260bcfb0e01230812c49ba72b2c':
        raise ValueError('Latest user override not bound')
    if tuple(contract['trace_fields'])!=TRACE_FIELDS or contract['final200_required'] is not True:
        raise ValueError('Six typed trace fields/final200 scope differs')
    if contract['seeds']!={'geometry_perturbation':20261010,'audit':20261010,'reproduction50':20261011,'final200':20261011}:
        raise ValueError('Declared original scientific/audit/reproduction seeds differ')
    sources=contract['sources'];names={Path(ref['path']).name for ref in sources}
    mandatory={'wp5_runner_v11.py','wp5_runner_v12.py','wp5_engine_v3.py','wp5_parser.py','wp5_parser_v2.py','wp5_archive_v5.py','wp5_parquet_v2.py','wp5_main_v12.sbatch','wp5_registry_coverage_v2.py',Path(__file__).name}
    if not mandatory<=names:raise ValueError('Current runtime/source chain not complete:'+repr(sorted(mandatory-names)))
    current=contract.get('current_runtime',{})
    runners=[ref for ref in current.values() if Path(ref['path']).name.startswith('wp5_runner_')]
    mains=[ref for ref in current.values() if Path(ref['path']).name.startswith('wp5_main_')]
    if len(runners)!=1 or runners[0].get('path')!=str(ROOT/'scripts/wp5_runner_v12.py') or runners[0].get('sha256')!=FROZEN_R12_SHA:
        raise ValueError('Current runtime must bind actual byte-for-byte frozenR12 candidate5')
    if len(mains)!=1 or mains[0].get('path')!=str(ROOT/'scripts/wp5_main_v12.sbatch') or mains[0].get('sha256')!=digest(ROOT/'scripts/wp5_main_v12.sbatch'):
        raise ValueError('Current runtime must bind actualmain12')
    reference=json.loads((ROOT/'configs/production_contract_v4.json').read_text())
    for key in ('audit_manifest','protocol','registry','node_authority','node_scope_plan','authority','trace_fields','seeds','policy','final200_required'):
        if contract[key]!=reference[key]:raise ValueError('R12 changes unchanged scientific/audit scope:'+key)
    for name,ref in reference['current_runtime'].items():
        if not name.startswith(('wp5_runner_','wp5_main_')) and current.get(name)!=ref:
            raise ValueError('R12 changes scientificIO source:'+name)
    for ref in sources:
        if digest(ref['path'])!=ref['sha256']:raise ValueError('Current production source differs:'+ref['path'])
    audit=json.loads(Path(contract['audit_manifest']['path']).read_text())
    if audit.get('status')!='AUDIT_MEMBERSHIP_CLOSED' or (audit['population']['records'],audit['population']['molecules'])!=(11231854,1220466):
        raise ValueError('Audit is not fixed formal physical population')
    selected=audit['selected_records']
    if digest(selected['path'])!=selected['sha256']:raise ValueError('Audit membership leaf changed')
    package=json.loads(Path(contract['reproduction_package']['path']).read_text())
    if package.get('status')!='REPRODUCTION_PACKAGE_CLOSED' or package['audit_membership']!=contract['audit_manifest']:
        raise ValueError('Actual package does not bind fixed record-level audit')
    if {name:package['software_versions'][name]['software_version_id'] for name in ('mopac','xtb')}!={'mopac':1,'xtb':2}:
        raise ValueError('Software version ID mapping differs')
    return contract

def prepare(node_authority,production_contract):
    contract=validate_current_contract(production_contract,node_authority)
    tasks=json.loads((ROOT/'packing/node_assignment_v3/tasks.json').read_text())['tasks']
    ids=[str(t['task_id']) for t in tasks]
    if len(set(ids))!=len(ids) or not tasks or set(t['node'] for t in tasks)!=NODES:
        raise ValueError('Frozen task/node identity not closed')
    main=[{'name':'wp5_recovery12_main_'+str(t['task_id']),'task_id':str(t['task_id']),
           'node':t['node'],'mode':'main'} for t in tasks]
    cleanup=[{'name':'wp5_recovery12_cleanup_'+str(n),'task_id':'cleanup_'+str(n),
              'node':'compute-0-'+str(n),'mode':'cleanup',
              'afterany_main_names':[r['name'] for r in main if r['node']=='compute-0-'+str(n)]}
              for n in (12,13,14,17,18,19)]
    if len(main)!=72 or len(cleanup)!=6:raise ValueError('One-phase must contain exactly72main+6cleanup')
    if not node_authority.is_file() or not node_authority.resolve().is_relative_to(ROOT):raise ValueError('Actual new user node authority file required')
    validate_authority(node_authority,tasks)
    prior_refs,prior_ids,_=prior_submission_bindings()
    return {'status':'PREPARED_NOT_SUBMITTED','version':12,'prior_submissions':prior_refs,'prior_job_ids':prior_ids,'prior_unique_jobs':229,'main':main,'cleanup':cleanup,
            'production_contract':{'path':str(production_contract),'sha256':digest(production_contract)},'raw_policy':POLICY,
            'audit_manifest':contract['audit_manifest'],'reproduction_package':contract['reproduction_package'],
            'node_authority':str(node_authority),'node_authority_sha256':digest(node_authority),
            'submit_helper':str(ROOT/'scripts/submit_wp5_job_v2.py'),'submit_helper_sha256':digest(ROOT/'scripts/submit_wp5_job_v2.py'),
            'tasks_sha256':digest(ROOT/'packing/node_assignment_v3/tasks.json'),'script':str(ROOT/'scripts/wp5_main_v12.sbatch'),
            'script_sha256':digest(ROOT/'scripts/wp5_main_v12.sbatch'),
            'resources':{'cpus':24,'memory_gib':32,'time':'48:00:00'},
            'submission_policy':'All main jobs then all six node-specific afterany cleanup jobs in one phase; no waves'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--submit',action='store_true')
    parser.add_argument('--node-authority',type=Path);parser.add_argument('--production-contract',type=Path)
    parser.add_argument('--recovery-authority',type=Path)
    args=parser.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());print('AST_PASS_NO_SUBMISSION');return
    if os.getuid()!=1278 or getpass.getuser()!='zixiao' or socket.gethostname().split('.')[0]!='sonmi':
        raise ValueError('Actual Root coordinator zixiao UID1278 on sonmi required')
    if args.node_authority is None or args.production_contract is None:parser.error('--node-authority and --production-contract actual frozen authority are required')
    directory=ROOT/'submission/recovery_attempt_v12';directory.mkdir(exist_ok=True)
    plan=prepare(args.node_authority,args.production_contract)
    if args.prepare:
        destination=directory/'prepared_plan_v12.json'
        if destination.exists() and json.loads(destination.read_text())!=plan:raise ValueError('Prepared plan changed')
        if not destination.exists():atomic(destination,plan)
        print(json.dumps({'plan':str(destination),'main_jobs':len(plan['main']),'cleanup_jobs':6,'node_authority_sha256':plan['node_authority_sha256']}));return
    if not args.submit:parser.error('Choose --prepare or --submit')
    if args.recovery_authority is None or not args.recovery_authority.is_file():
        raise ValueError('Guide step3.5 requires the actual user recovery instruction before any new formal submission')
    authority=json.loads(args.recovery_authority.read_text())
    if authority.get('status')!='USER_APPROVED_ONE_PHASE_RECOVERY':raise ValueError('Actual user recovery authority missing')
    if authority.get('original_submission_sha256')!=digest(ROOT/'submission/submitted_jobs.json'):
        raise ValueError('Recovery authority binds a different original formal phase')
    if authority.get('production_contract')!=plan['production_contract']:
        raise ValueError('Recovery authority binds a different tested runtime contract')
    terminal_evidence=fresh_all_prior_terminal(plan)
    prepared=directory/'prepared_plan_v12.json'
    if not prepared.exists() or json.loads(prepared.read_text())!=plan:raise ValueError('Frozen preparedv12 recovery plan required unchanged')
    recovery_evidence=validate_recovery_evidence(authority,plan,prepared,args.recovery_authority)
    gate=ROOT/'gates/g0_ready_for_recovery_v12.json'
    if not gate.exists():raise ValueError('Actual remaining G0 evidence is not yet closed')
    ready=json.loads(gate.read_text())
    if ready['status']!='READY_FOR_ONE_PHASE_FORMAL_SUBMISSION':raise ValueError('G0 not ready')
    for name in ['G1','G2','G3','G4','G6']:
        if ready['gates'][name]['status']!='PASS':raise ValueError(name+' not passed')
    if ready['gates']['G5']['status'] not in ('PASS','PASS_FULL_FIELD_EXTRACTION'):raise ValueError('Current full active-v2 field extraction G5 not passed')
    if ready['gates']['REPRO50']['status']!='PASS':raise ValueError('Actual50x2 parsed-field validation not passed')
    if ready.get('production_contract')!=plan['production_contract']:raise ValueError('G0 binds a different current production contract')
    for evidence in ready['bindings']:
        if digest(evidence['path'])!=evidence['sha256']:raise ValueError('G0 frozen binding changed: '+evidence['path'])
    if (ROOT/'STOP_NEW_MOLECULES.json').exists():raise ValueError('A real runtime stop condition is still active')
    policy=ready['raw_policy']
    if policy!=POLICY or policy!=plan['raw_policy']:raise ValueError('G3/G0 does not bind the latest exact no-input record-audit policy')
    result_path=directory/'submitted_jobs.json'
    if result_path.exists():raise ValueError('Submission phase already exists; inspect its actual IDs before any continuation')
    lock=directory/'root_submit.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.write(fd,json.dumps({'pid':os.getpid(),'uid':os.getuid(),'time':time.time()}).encode());os.close(fd)
    result={'status':'ONE_PHASE_SUBMISSION_IN_PROGRESS','start':time.time(),'g0_sha256':digest(gate),
            'prepared_plan':plan,'prior_terminal_snapshot':terminal_evidence,'runtime_recovery_evidence':recovery_evidence,'recovery_authority':{'path':str(args.recovery_authority),'sha256':digest(args.recovery_authority)},'original_submission_sha256':digest(ROOT/'submission/submitted_jobs.json'),'main':[],'cleanup':[],'error':None}
    atomic(result_path,result)
    try:
        environment=dict(os.environ)
        environment.update(WP5_DICTIONARIES=ready['dictionary_manifest'],WP5_BASELINE=str(ROOT/'configs/pilot_success_baseline.json'),WP5_POLICY=policy,WP5_NODE_AUTHORITY=plan['node_authority'],WP5_AUDIT_MEMBERSHIP=plan['audit_manifest']['path'],WP5_REPRODUCTION_PACKAGE=plan['reproduction_package']['path'],WP5_PRODUCTION_CONTRACT=plan['production_contract']['path'])
        for role in ['main','cleanup']:
            for item in plan[role]:
                environment.update(WP5_TASK_ID=item['task_id'],WP5_MODE=item['mode'])
                command=[PYTHON,'-B',str(ROOT/'scripts/submit_wp5_job_v2.py'),'--script',plan['script'],
                  '--name',item['name'],'--node',item['node'],'--cpus','24','--memory-gb','32',
                  '--time','48:00:00','--kind','quantum','--allow-pending']
                if role=='cleanup':
                    ids=[row['job_id'] for row in result['main'] if row['node']==item['node']]
                    if not ids:raise ValueError('Cleanup has no own-node main dependencies')
                    command+=['--dependency','afterany:'+':'.join(ids)]
                process=subprocess.run(command,env=environment,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
                if process.returncode:raise RuntimeError(item['name']+': '+process.stderr)
                receipt=json.loads(process.stdout)
                result[role].append({**item,**receipt});atomic(result_path,result)
                print(json.dumps({'role':role,'task_id':item['task_id'],'job_id':receipt['job_id'],'node':item['node']}),flush=True)
        result['status']='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED';result['end']=time.time();atomic(result_path,result)
    except BaseException as exc:
        result['status']='PARTIAL_ONE_PHASE_SUBMISSION_REQUIRES_ROOT_RECONCILIATION'
        result['error']=repr(exc);atomic(result_path,result);raise
    finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()
