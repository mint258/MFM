"""Root-only one-phase WP5 main and dependent cleanup submission."""
import argparse,ast,getpass,hashlib,json,os,socket,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
PRIOR_SUBMISSIONS=(ROOT/'submission/submitted_jobs.json',
    ROOT/'submission/recovery_attempt_v11/submitted_jobs.json',
    ROOT/'submission/startup_replacement_v1/submitted_jobs.json',
    ROOT/'submission/recovery_attempt_v13/submitted_jobs.json',
    ROOT/'submission/recovery_attempt_v14/submitted_jobs.json',
    ROOT/'submission/recovery_attempt_v15/submitted_jobs.json')
PRIOR_COUNTS=(78,78,73,78,78,78)
FROZEN_R14_SHA='7d4aa3932be408ff051003446ae7f3fd1eab7b7bdb386d67a41eadb18e3af740'
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
    if len(identifiers)!=463 or len(set(identifiers))!=463:raise ValueError('All six actual prior phases must close exact463 unique IDs')
    return refs,sorted(identifiers,key=int),used_authorities

POLICY='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT'
TRACE_FIELDS=('status','software_version_id','elapsed_seconds','scf_iterations','converged','input_file_sha256')
def validate_current_contract(path,node_authority):
    if path.resolve()!=(ROOT/'configs/production_contract_v7.json').resolve():raise ValueError('Actual newcontract7 required')
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
    mandatory={'wp5_runner_v11.py','wp5_runner_v14.py','wp5_engine_v3.py','wp5_parser.py','wp5_parser_v2.py','wp5_archive_v5.py','wp5_parquet_v2.py','wp5_main_v14.sbatch','wp5_registry_coverage_v2.py',Path(__file__).name}
    if not mandatory<=names:raise ValueError('Current runtime/source chain not complete:'+repr(sorted(mandatory-names)))
    current=contract.get('current_runtime',{})
    runners=[ref for ref in current.values() if Path(ref['path']).name.startswith('wp5_runner_')]
    mains=[ref for ref in current.values() if Path(ref['path']).name.startswith('wp5_main_')]
    if len(runners)!=1 or runners[0].get('path')!=str(ROOT/'scripts/wp5_runner_v14.py') or runners[0].get('sha256')!=FROZEN_R14_SHA:
        raise ValueError('Current runtime must bind actual byte-for-byte frozenR13 cleanup-scope metadata bridge')
    if len(mains)!=1 or mains[0].get('path')!=str(ROOT/'scripts/wp5_main_v14.sbatch') or mains[0].get('sha256')!=digest(ROOT/'scripts/wp5_main_v14.sbatch'):
        raise ValueError('Current runtime must bind actualmain13')
    reference=json.loads((ROOT/'configs/production_contract_v6.json').read_text())
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
    main=[{'name':'wp5_runtime14_main_'+str(t['task_id']),'task_id':str(t['task_id']),
           'node':t['node'],'mode':'main'} for t in tasks]
    cleanup=[{'name':'wp5_runtime14_cleanup_'+str(n),'task_id':'cleanup_'+str(n),
              'node':'compute-0-'+str(n),'mode':'cleanup',
              'afterany_main_names':[r['name'] for r in main if r['node']=='compute-0-'+str(n)]}
              for n in (12,13,14,17,18,19)]
    if len(main)!=72 or len(cleanup)!=6:raise ValueError('One-phase must contain exactly72main+6cleanup')
    if not node_authority.is_file() or not node_authority.resolve().is_relative_to(ROOT):raise ValueError('Actual new user node authority file required')
    validate_authority(node_authority,tasks)
    prior_refs,prior_ids,_=prior_submission_bindings()
    return {'status':'PREPARED_NOT_SUBMITTED','version':14,'prior_submissions':prior_refs,'prior_job_ids':prior_ids,'prior_unique_jobs':463,'main':main,'cleanup':cleanup,
            'production_contract':{'path':str(production_contract),'sha256':digest(production_contract)},'raw_policy':POLICY,
            'audit_manifest':contract['audit_manifest'],'reproduction_package':contract['reproduction_package'],
            'node_authority':str(node_authority),'node_authority_sha256':digest(node_authority),
            'submit_helper':str(ROOT/'scripts/submit_wp5_job_v2.py'),'submit_helper_sha256':digest(ROOT/'scripts/submit_wp5_job_v2.py'),
            'tasks_sha256':digest(ROOT/'packing/node_assignment_v3/tasks.json'),'script':str(ROOT/'scripts/wp5_main_v14.sbatch'),
            'script_sha256':digest(ROOT/'scripts/wp5_main_v14.sbatch'),
            'resources':{'cpus':24,'memory_gib':32,'time':'48:00:00'},
            'submission_policy':'All main jobs then all six node-specific afterany cleanup jobs in one phase; no waves'}

def main():
    parser=argparse.ArgumentParser(description='Runtime14 validator/prepared freeze only. Phase16 Root coordinator owns actual submission.')
    parser.add_argument('--check',action='store_true');parser.add_argument('--prepare',action='store_true');parser.add_argument('--submit',action='store_true')
    parser.add_argument('--node-authority',type=Path);parser.add_argument('--production-contract',type=Path)
    args=parser.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());print('AST_PASS_NO_SUBMISSION');return
    if args.submit:raise ValueError('HISTORICAL_229_SUBMIT_FLOW_DISABLED_USE_CURRENT_ROOT_PHASE_COORDINATOR')
    if not args.prepare:parser.error('--prepare required')
    if args.node_authority is None or args.production_contract is None:parser.error('--node-authority and --production-contract required')
    if os.getuid()!=1278 or getpass.getuser()!='zixiao' or socket.gethostname().split('.')[0]!='sonmi':raise ValueError('Root zixiao UID1278 on sonmi required')
    plan=prepare(args.node_authority,args.production_contract)
    directory=ROOT/'submission/runtime_v14_freeze';directory.mkdir(exist_ok=True)
    destination=directory/'prepared_plan_v14.json'
    if destination.exists() and json.loads(destination.read_text())!=plan:raise ValueError('Prepared runtime14 freeze changed')
    if not destination.exists():atomic(destination,plan)
    print(json.dumps({'plan':str(destination),'main_jobs':len(plan['main']),'cleanup_jobs':len(plan['cleanup']),'actual_submission':False,'prior_unique_jobs':plan['prior_unique_jobs']}))
if __name__=='__main__':main()