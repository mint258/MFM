"""G4 independent byte/source/recipe freeze. No QM and no LMDB opened or scanned."""
from __future__ import annotations
import argparse,ast,concurrent.futures,hashlib,importlib.metadata,json,multiprocessing,os,re,socket,sys,time,traceback
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
CALCS=('pm7_B','pm7_water','pm7_octanol','pm7_cation','pm7_anion','xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient')
_BARRIER=None
_HASH_DEADLINE=None

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):
            if _HASH_DEADLINE is not None and time.monotonic()>=_HASH_DEADLINE:raise TimeoutError('G4_INTERNAL46H_HASH_DEADLINE')
            h.update(block)
    return h.hexdigest()

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise FileExistsError('New immutable G4 output required')
    with path.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

def reference(path,kind='HASH_CURRENT',expected=None,bytes_expected=None,rows_expected=None,closure=None):
    return {'path':str(path),'kind':kind,'expected_sha256':expected,'expected_bytes':bytes_expected,'expected_rows':rows_expected,'closure':closure}

def bind(barrier,deadline):
    global _BARRIER,_HASH_DEADLINE
    _BARRIER=barrier;_HASH_DEADLINE=deadline

def inspect_file(item):
    path=Path(item['path']);result=dict(item)
    try:
        if path.suffix=='.lmdb' or any(p.endswith('.lmdb') for p in path.parts):raise ValueError('NO_LMDB_ACCESS_IN_G4')
        stat=path.stat();result.update(bytes=stat.st_size,uid=stat.st_uid,mtime_ns=stat.st_mtime_ns)
        if not path.is_file():raise ValueError('NOT_REGULAR_FILE')
        errors=[]
        if item.get('expected_bytes') is not None and stat.st_size!=item['expected_bytes']:errors.append('BYTE_COUNT_DIFFERS')
        if item['kind']=='REFERENCE_ALREADY_CLOSED_SHA':
            if not re.fullmatch(r'[0-9a-f]{64}',item.get('expected_sha256') or ''):errors.append('MISSING_PRIOR_CLOSED_SHA')
            result['sha256']=item.get('expected_sha256');result['hash_read_in_this_job']=False
        else:
            result['sha256']=sha(path);result['hash_read_in_this_job']=True
            if item.get('expected_sha256') is not None and result['sha256']!=item['expected_sha256']:errors.append('SHA256_DIFFERS')
            if path.suffix=='.py':ast.parse(path.read_text());result['AST']='PASS'
            if item.get('expected_rows') is not None:
                import pyarrow.parquet as pq
                result['parquet_rows']=pq.ParquetFile(path).metadata.num_rows
                if result['parquet_rows']!=item['expected_rows']:errors.append('PARQUET_FOOTER_ROW_COUNT_DIFFERS')
            after=path.stat()
            if (after.st_size,after.st_mtime_ns)!=(stat.st_size,stat.st_mtime_ns):errors.append('FILE_CHANGED_DURING_HASH')
        result['differences']=errors;result['status']='MATCH' if not errors else 'DIFFERENCE'
    except BaseException as exc:result.update(status='ERROR',differences=[type(exc).__name__+':'+str(exc)])
    return result

def lane(items):
    _BARRIER.wait(timeout=120)
    return {'pid':os.getpid(),'files':[inspect_file(item) for item in items]}

def build(spec):
    targets=[];differences=[]
    for item in spec['files']:targets.append(reference(item['path'],expected=item['sha256'],bytes_expected=item['bytes']))
    protocol=json.loads((ROOT/'configs/protocol.json').read_text());old=json.loads(Path(spec['old_native_metadata']).read_text())
    targets.append(reference(spec['old_native_metadata'],expected=spec['old_native_metadata_sha256']))
    targets.append(reference(spec['registry'],expected=spec['registry_sha256']))
    targets.append(reference(spec['source_plan'],expected=spec['source_plan_sha256']))
    targets.append(reference(spec['mopac_version_output']))
    targets.append(reference(spec['xtb_verification'],expected=spec['xtb_verification_sha256']))
    actual_mopac_line=next((line.strip() for line in Path(spec['mopac_version_output']).read_text().splitlines() if 'MOPAC v' in line),None)
    mopac_version=re.search(r'MOPAC v([0-9.]+)',actual_mopac_line or '')
    mopac_actual=mopac_version.group(1) if mopac_version else None
    xtb=json.loads(Path(spec['xtb_verification']).read_text());xtb_match=re.search(r'xtb version\s+([0-9.]+)',xtb['actual_version_line'])
    xtb_actual=xtb_match.group(1) if xtb_match else None
    if {'mopac':mopac_actual,'xtb':xtb_actual}!=spec['software_versions'] or protocol['expected_versions']!=spec['software_versions']:differences.append('ACTUAL_EXISTING_VERSION_EVIDENCE_OR_PROTOCOL_DIFFERS')
    binaries={}
    for name in ('mopac','xtb'):
        key=name+'_executable';exe=old['software']['executables'][key]
        if protocol[key]!=exe['path']:differences.append('BINARY_ABSOLUTE_ENTRY_DIFFERS:'+name)
        binaries[name]={'version':spec['software_versions'][name],'path':protocol[key],'expected_sha256':exe['sha256'],
             'version_source':spec['mopac_version_output'] if name=='mopac' else spec['xtb_verification']}
        targets.append(reference(protocol[key],kind='CURRENT_BINARY_EQUALS_ACTUAL_PILOT_SHA',expected=exe['sha256']))
    if xtb['actual_entry_sha256']!=binaries['xtb']['expected_sha256']:differences.append('XTB_INSTALL_AND_PILOT_BINARY_SHA_DIFFERS')
    for param in xtb['parameter_files']:
        targets.append(reference(Path(protocol['xtb_environment']['XTBPATH'])/param['name'],expected=param['sha256'],bytes_expected=param['bytes']))
    for item in protocol['frozen_dependencies'].values():targets.append(reference(item['path'],expected=item['sha256']))
    for item in protocol.get('mulliken_official_references',{}).values():targets.append(reference(item['path'],expected=item['sha256'],bytes_expected=item.get('bytes')))
    if protocol['seed']!=old['config']['seed'] or protocol['timeout_seconds']!=old['config']['timeout_seconds']:differences.append('PILOT_SEED_OR_DEFAULT_TIMEOUT_DIFFERS')
    for key in ('perturb_sigma_A','pair_cutoff_A','mopac_environment','xtb_environment','per_file_limit_bytes','mulliken_overlap_charge_tolerance_e','mulliken_minimum_absolute_eigenvalue'):
        if protocol.get(key)!=old['config'].get(key):differences.append('PILOT_EXECUTION_PARAMETER_DIFFERS:'+key)
    if tuple(t['name'] for t in protocol['tasks'])!=CALCS:differences.append('FORMAL_TWELVE_TASK_ORDER_OR_SCOPE_DIFFERS')
    old_tasks={task['name']:task for task in old['config']['tasks']}
    keyword_records=[]
    for task in protocol['tasks']:
        old_task=dict(old_tasks.get(task['name'],{}))
        if task['name']=='pm7_B':
            old_task['keywords']=' '.join(old_task.get('keywords','').replace('POLAR(E=(0.0),BETA=0,GAMMA=0)','').split())
            old_task['required_values']=[x for x in old_task.get('required_values',[]) if x!='static_polar_block']
        for key in ('family','keywords','args','xcontrol','perturbed','timeout_seconds','required_values'):
            if task.get(key)!=old_task.get(key):differences.append('NONAUTHORIZED_TASK_RECIPE_DIFFERS:'+task['name']+':'+key)
        if task['family']=='mopac' and any(word in task['keywords'] for word in ('POLAR','ESP')):differences.append('DELETED_KEYWORD_STILL_REQUESTED:'+task['name'])
        if task['family']=='xtb' and any(word in task['args'] for word in ('--opt','--hess','--ohess')):differences.append('GEOMETRY_CHANGE_OR_HESS_STILL_REQUESTED:'+task['name'])
        keywords=task['keywords']+' THREADS=1' if task['family']=='mopac' else task['args']
        keyword_records.append({'calc_type':task['name'],'keywords_or_arguments':keywords,'keywordSHA':hashlib.sha256(json.dumps(keywords,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'xcontrol':task.get('xcontrol'),'per_call_timeout_seconds':task.get('timeout_seconds',protocol['timeout_seconds'])})
    dictionary_path=ROOT/'dictionaries/job_4513894/dictionary_manifest.json';dictionary=json.loads(dictionary_path.read_text())
    if len(dictionary['dictionaries'])!=12 or {d['calc_type'] for d in dictionary['dictionaries']}!=set(CALCS):differences.append('DICTIONARY_TWELVE_CALC_TYPE_SCOPE_DIFFERS')
    for item in dictionary['dictionaries']:targets.append(reference(item['path'],kind='CURRENT_DICTIONARY',expected=item['sha256'],bytes_expected=item['bytes']))
    pop_path=ROOT/'population/manifest.json';pack_path=ROOT/'packing/manifest.json';pop=json.loads(pop_path.read_text());pack=json.loads(pack_path.read_text())
    for path,obj in ((pop_path,pop),(pack_path,pack)):
        for item in obj['inputs']:
            targets.append(reference(item['path'],kind='REFERENCE_ALREADY_CLOSED_SHA',expected=item['sha256'],bytes_expected=item['bytes'],closure={'path':str(path),'sha256':sha(path),'job_id':obj['job_id']}))
    if pop['status']!='WP5_FORMAL_POPULATION_CLOSED' or pack['status']!='WP5_PACKING_CLOSED':differences.append('POPULATION_OR_PACKING_NOT_CLOSED')
    if (pop['formal_records'],pop['formal_molecules'])!=(pack['formal_records'],pack['formal_molecules']):differences.append('POPULATION_PACKING_COUNT_DIFFERS')
    row_targets={pop['outputs']['record_index']:pop['formal_records'],pop['outputs']['molecule_index']:pop['formal_molecules'],pack['outputs']['molecule_assignments']:pop['formal_molecules']}
    for path in pop['outputs'].values():targets.append(reference(path,kind='CURRENT_FORMAL_POPULATION_LEAF',rows_expected=row_targets.get(path)))
    for path in (ROOT/'population').glob('*.parquet'):
        if str(path) not in pop['outputs'].values():targets.append(reference(path,kind='CURRENT_FORMAL_POPULATION_LEAF'))
    targets.append(reference(pack['outputs']['molecule_assignments'],kind='CURRENT_FROZEN_ASSIGNMENTS',rows_expected=pop['formal_molecules']))
    node_manifest=json.loads((ROOT/'packing/node_assignment_v3/manifest.json').read_text());node_plan=json.loads(Path(node_manifest['tasks']).read_text())
    from wp5_submit_formal_v6 import validate_authority
    authority=Path(spec['node_authority']);validate_authority(authority,node_plan['tasks'])
    targets.append(reference(authority,expected=spec['node_authority_sha256']))
    if node_manifest['user_approval']!={'path':str(authority),'sha256':spec['node_authority_sha256']}:differences.append('ACTUAL_NODE_APPROVAL_BINDING_DIFFERS')
    targets.append(reference(node_manifest['source_tasks'],expected=node_manifest['source_tasks_sha256']))
    targets.append(reference(node_manifest['tasks'],expected=node_manifest['tasks_sha256']))
    if node_manifest['molecule_assignments']!=pack['outputs']['molecule_assignments'] or not node_manifest['molecule_assignments_unchanged']:differences.append('NEW_NODE_PLAN_CHANGED_ASSIGNMENTS')
    if len(node_plan['tasks'])!=72 or set(t['node'] for t in node_plan['tasks'])!={'compute-0-'+str(i) for i in (12,13,14,17,18,19)}:differences.append('TASK_NODE_POPULATION_NOT72_CURRENT_USER_APPROVED')
    partition_rows=0
    for task in node_plan['tasks']:
        directory=Path(task['record_directory'])
        if not directory.resolve().is_relative_to((ROOT/'packing/record_partitions').resolve()):differences.append('PARTITION_DIRECTORY_SCOPE:'+str(directory));continue
        files=sorted(directory.glob('*.parquet'))
        if not files:differences.append('PARTITION_DIRECTORY_EMPTY:'+str(directory))
        for file in files:targets.append(reference(file,kind='CURRENT_TASK_RECORD_PARTITION',rows_expected=task['records'] if len(files)==1 else None))
        partition_rows+=task['records']
    if partition_rows!=pop['formal_records']:differences.append('TASK_RECORD_COUNTS_NOT_FORMAL_POPULATION')
    bulk=json.loads((ROOT/'submission/prepared_plan_v6.json').read_text())
    if bulk['script']!=str(ROOT/'scripts/wp5_main_v7.sbatch') or bulk['tasks_sha256']!=node_manifest['tasks_sha256']:differences.append('BULKV6_SCRIPT_OR_TASKPLAN_DIFFERS')
    if bulk['node_authority']!=str(authority) or bulk['node_authority_sha256']!=spec['node_authority_sha256'] or bulk['submit_helper']!=str(ROOT/'scripts/submit_wp5_job_v2.py'):differences.append('BULKV6_NODE_AUTHORITY_OR_HELPER_DIFFERS')
    targets.append(reference(bulk['submit_helper'],expected=bulk['submit_helper_sha256']))
    targets.append(reference(bulk['script'],expected=bulk['script_sha256']))
    baseline=json.loads((ROOT/'configs/pilot_success_baseline.json').read_text())
    if set(baseline['success_rates'])!=set(CALCS):differences.append('BASELINE_NOT12_CALC_TYPES')
    for rate in baseline['success_rates'].values():
        if not isinstance(rate,(int,float)) or not 0<=rate<=1:differences.append('BASELINE_INVALID_SUCCESS_RATE')
    return targets,differences,{'software':binaries,'actual_version_evidence':{'mopac':actual_mopac_line,'xtb':xtb['actual_version_line']},
      'recipes':keyword_records,'population':{'records':pop['formal_records'],'molecules':pop['formal_molecules'],'tasks':72},
      'actual_node_authority':{'path':str(authority),'sha256':spec['node_authority_sha256'],'authorized_node_slots':json.loads(authority.read_text())['authorized_node_slots'],'node_replacement_scope':'smoke and formal, not G3 capacity exemption'},
      'cached_input_sha_binding':'Prior actual population/packing closure SHA referenced; byte lengths rechecked. Original LMDB and source Parquet rows are not read.',
      'dictionary_historical_training_config_sha256':dictionary.get('formal_config_sha256'),'dictionary_note':'Dictionary codec payload is independently frozen; historical training config metadata is not an executable current recipe.',
      'new_data_leaf_hashes':'Current new formal population/assignments/task Parquet files hashed on this compute allocation; no original LMDB access.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,default=ROOT/'configs/g4_freeze_spec_v3.json');p.add_argument('--output',type=Path)
    p.add_argument('--workers',type=int,default=24);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        ast.parse(Path(__file__).read_text());assert len(CALCS)==12 and len(set(CALCS))==12
        print('G4_AST_AND_SCOPE_PASS_NO_QM_NO_LMDB_NO_HASH');return
    node=socket.gethostname().split('.')[0];job=os.environ.get('SLURM_JOB_ID')
    if not job or node not in {'compute-0-'+str(i) for i in (12,13,14,17,18,19)} or a.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers:raise ValueError('G4_ACTUAL_ALLOCATED16PLUS_CPU_ON_CURRENT_APPROVED_NODES_REQUIRED')
    out=a.output or ROOT/'gates/G4_freeze'/('job_'+job);out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();deadline=started+46*3600;results=[];differences=[];context={}
    try:
        spec=json.loads(a.spec.read_text());targets,differences,context=build(spec)
        if time.monotonic()>=deadline:raise TimeoutError('INTERNAL46H_DEADLINE_BEFORE_HASH')
        save(out/'requested_bindings.json',targets)
        mp=multiprocessing.get_context('spawn');barrier=mp.Barrier(a.workers)
        bins=[targets[i::a.workers] for i in range(a.workers)]
        with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=mp,initializer=bind,initargs=(barrier,deadline)) as pool:
            results=list(pool.map(lane,bins))
        files=[record for result in results for record in result['files']]
        hash_by_path={f['path']:f['sha256'] for f in files if f.get('hash_read_in_this_job') and f.get('sha256')}
        for file in files:
            if file['status']!='MATCH':differences.append({'path':file['path'],'kind':file['kind'],'differences':file['differences']})
            if file['kind']=='REFERENCE_ALREADY_CLOSED_SHA' and file['path'] in hash_by_path and file['sha256']!=hash_by_path[file['path']]:differences.append({'path':file['path'],'differences':['PRIOR_CLOSED_SHA_DIFFERS_FROM_INDEPENDENT_CURRENT_HASH']})
        pids=sorted({r['pid'] for r in results})
        if len(pids)<a.workers:differences.append('FEWER_ACTUAL_HASH_WORKER_PIDS_THAN_REQUESTED')
        packages={}
        for package in ('numpy','pyarrow','rdkit','torch','lmdb','duckdb'):
            try:packages[package]=importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:packages[package]='DISTRIBUTION_METADATA_UNAVAILABLE'
        bindings={}
        for file in files:
            if file.get('hash_read_in_this_job') and file.get('sha256'):
                bindings[file['path']]={'path':file['path'],'bytes':file['bytes'],'sha256':file['sha256'],'kind':file['kind']}
        report={'status':'PASS' if not differences else 'NOT_PASS','gate':'G4','scope':'FORMAL_CURRENT12_ORIGINAL_COORDINATES_ALL_CONFORMERS_FREEZE',
          'job_id':job,'hostname':node,'uid':os.getuid(),'elapsed_seconds':time.monotonic()-started,'internal_deadline_hours':46,
          'source_sha256':sha(__file__),'spec_path':str(a.spec),'spec_sha256':sha(a.spec),'worker_pids':pids,'workers':a.workers,
          'files':files,'bindings':list(bindings.values()),'binding_differences':differences,'context':context,
          'python_executable':sys.executable,'python_version':sys.version,'packages':packages,
          'QM_started':False,'source_LMDB_accessed':False,'source_LMDB_created':False,'original_data_written':False,'historical_evidence_overwritten':False}
        save(out/'report.json',report)
        print(json.dumps({'report':str(out/'report.json'),'status':report['status'],'differences':len(differences),'actual_workers':len(pids)}))
    except BaseException:
        save(out/'report.json',{'status':'NOT_PASS','gate':'G4','job_id':job,'hostname':node,'source_sha256':sha(__file__),
            'spec_path':str(a.spec),'spec_sha256':sha(a.spec),'error':traceback.format_exc(),'binding_differences':differences,
            'elapsed_seconds':time.monotonic()-started,'QM_started':False,'source_LMDB_accessed':False,'original_data_written':False})
        raise
if __name__=='__main__':main()
