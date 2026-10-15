"""Root-only one-phase WP5 main and dependent cleanup submission."""
import argparse,ast,getpass,hashlib,json,os,socket,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
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

POLICY='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT'
TRACE_FIELDS=('status','software_version_id','elapsed_seconds','scf_iterations','converged','input_file_sha256')
def validate_current_contract(path,node_authority):
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
    if contract['seeds']!={'geometry':20261010,'audit':20261010,'repro50':20261011,'final200':20261011}:
        raise ValueError('Declared original scientific/audit/reproduction seeds differ')
    sources=contract['sources'];names={Path(ref['path']).name for ref in sources}
    mandatory={'wp5_runner_v8.py','wp5_engine_v2.py','wp5_parser.py','wp5_archive_v5.py','wp5_parquet_v2.py','wp5_main_v8.sbatch','wp5_registry_coverage.py',Path(__file__).name}
    if not mandatory<=names:raise ValueError('Current runtime/source chain not complete:'+repr(sorted(mandatory-names)))
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
    main=[{'name':'wp5_formal_main_'+str(t['task_id']),'task_id':str(t['task_id']),
           'node':t['node'],'mode':'main'} for t in tasks]
    cleanup=[{'name':'wp5_formal_cleanup_'+str(n),'task_id':'cleanup_'+str(n),
              'node':'compute-0-'+str(n),'mode':'cleanup',
              'afterany_main_names':[r['name'] for r in main if r['node']=='compute-0-'+str(n)]}
              for n in (12,13,14,17,18,19)]
    if len(main)!=72 or len(cleanup)!=6:raise ValueError('One-phase must contain exactly72main+6cleanup')
    if not node_authority.is_file() or not node_authority.resolve().is_relative_to(ROOT):raise ValueError('Actual new user node authority file required')
    validate_authority(node_authority,tasks)
    return {'status':'PREPARED_NOT_SUBMITTED','version':7,'main':main,'cleanup':cleanup,
            'production_contract':{'path':str(production_contract),'sha256':digest(production_contract)},'raw_policy':POLICY,
            'audit_manifest':contract['audit_manifest'],'reproduction_package':contract['reproduction_package'],
            'node_authority':str(node_authority),'node_authority_sha256':digest(node_authority),
            'submit_helper':str(ROOT/'scripts/submit_wp5_job_v2.py'),'submit_helper_sha256':digest(ROOT/'scripts/submit_wp5_job_v2.py'),
            'tasks_sha256':digest(ROOT/'packing/node_assignment_v3/tasks.json'),'script':str(ROOT/'scripts/wp5_main_v8.sbatch'),
            'script_sha256':digest(ROOT/'scripts/wp5_main_v8.sbatch'),
            'resources':{'cpus':24,'memory_gib':32,'time':'48:00:00'},
            'submission_policy':'All main jobs then all six node-specific afterany cleanup jobs in one phase; no waves'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--submit',action='store_true')
    parser.add_argument('--node-authority',type=Path);parser.add_argument('--production-contract',type=Path)
    args=parser.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());print('AST_PASS_NO_SUBMISSION');return
    if os.getuid()!=1278 or getpass.getuser()!='zixiao' or socket.gethostname().split('.')[0]!='sonmi':
        raise ValueError('Actual Root coordinator zixiao UID1278 on sonmi required')
    if args.node_authority is None or args.production_contract is None:parser.error('--node-authority and --production-contract actual frozen authority are required')
    directory=ROOT/'submission';directory.mkdir(exist_ok=True)
    plan=prepare(args.node_authority,args.production_contract)
    if args.prepare:
        destination=directory/'prepared_plan_v7.json'
        if destination.exists() and json.loads(destination.read_text())!=plan:raise ValueError('Prepared plan changed')
        if not destination.exists():atomic(destination,plan)
        print(json.dumps({'plan':str(destination),'main_jobs':len(plan['main']),'cleanup_jobs':6,'node_authority_sha256':plan['node_authority_sha256']}));return
    if not args.submit:parser.error('Choose --prepare or --submit')
    prepared=directory/'prepared_plan_v7.json'
    if not prepared.exists() or json.loads(prepared.read_text())!=plan:raise ValueError('Frozen preparedv7 plan required unchanged')
    gate=ROOT/'gates/g0_ready_for_formal.json'
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
            'prepared_plan':plan,'main':[],'cleanup':[],'error':None}
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
