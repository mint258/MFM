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


def current_runtime_binding(contract):
    """Read the execution entry from the SHA-frozen current contract."""
    runtime=contract.get('current_runtime',{})
    mains=[(name,ref) for name,ref in runtime.items() if re.fullmatch(r'wp5_main_v[0-9]+\.sbatch',name)]
    runners=[(name,ref) for name,ref in runtime.items() if re.fullmatch(r'wp5_runner_v[0-9]+\.py',name)]
    if len(mains)!=1 or len(runners)!=1:raise ValueError('CONTRACT_UNIQUE_CURRENT_MAIN_AND_RUNNER_REQUIRED')
    main_name,main_ref=mains[0];runner_name,runner_ref=runners[0]
    version=int(re.fullmatch(r'wp5_main_v([0-9]+)\.sbatch',main_name).group(1))
    if int(re.fullmatch(r'wp5_runner_v([0-9]+)\.py',runner_name).group(1))!=version:
        raise ValueError('CONTRACT_CURRENT_MAIN_RUNNER_VERSION_DIFFERS')
    for name,ref in ((main_name,main_ref),(runner_name,runner_ref)):
        if Path(ref['path']).resolve()!=(ROOT/'scripts'/name).resolve() or not re.fullmatch(r'[0-9a-f]{64}',ref.get('sha256','')):
            raise ValueError('CONTRACT_CURRENT_RUNTIME_ENTRY_BINDING_INVALID:'+name)
        matches=[x for x in contract['sources'] if Path(x['path']).resolve()==Path(ref['path']).resolve()]
        if len(matches)!=1 or matches[0]['sha256']!=ref['sha256']:
            raise ValueError('CONTRACT_CURRENT_RUNTIME_ENTRY_NOT_SAME_FROZEN_SOURCE:'+name)
    return {'version':version,'main':main_ref,'runner':runner_ref}

def prepared_runtime_differences(bulk,contract,binding,node_tasks,tasks_sha,contract_ref):
    """Compare frozen plan fields without allowing current values to replace SHA authority."""
    differences=[]
    if bulk.get('script')!=binding['main']['path'] or bulk.get('script_sha256')!=binding['main']['sha256'] or bulk.get('tasks_sha256')!=tasks_sha:
        differences.append('CURRENT_PREPARED_SCRIPT_SHA_OR_TASKPLAN_DIFFERS')
    if bulk.get('version')!=binding['version'] or bulk.get('production_contract')!=contract_ref or bulk.get('raw_policy')!=contract['policy']:
        differences.append('CURRENT_PREPARED_PLAN_VERSION_POLICY_OR_CONTRACT_DIFFERS')
    if bulk.get('audit_manifest')!=contract['audit_manifest'] or bulk.get('reproduction_package')!=contract['reproduction_package']:
        differences.append('CURRENT_PREPARED_PLAN_AUDIT_OR_PACKAGE_DIFFERS')
    main=bulk.get('main',[]);cleanup=bulk.get('cleanup',[])
    expected={str(t['task_id']):t['node'] for t in node_tasks}
    actual={str(t.get('task_id')):t.get('node') for t in main}
    nodes=set(expected.values())
    if len(main)!=72 or len(actual)!=72 or actual!=expected or any(t.get('mode')!='main' for t in main):
        differences.append('CURRENT_PREPARED_MAIN72_TASK_NODE_AUTHORITY_DIFFERS')
    if len(cleanup)!=6 or len({t.get('node') for t in cleanup})!=6 or {t.get('node') for t in cleanup}!=nodes or any(t.get('mode')!='cleanup' for t in cleanup):
        differences.append('CURRENT_PREPARED_SIX_CLEANUP_NODE_SCOPE_DIFFERS')
    else:
        for item in cleanup:
            own=[t['name'] for t in main if t['node']==item['node']]
            dependencies=item.get('afterany_main_names',[])
            if len(dependencies)!=len(own) or set(dependencies)!=set(own):
                differences.append('CURRENT_PREPARED_CLEANUP_OWN_NODE_AFTERANY_DIFFERS:'+item['node'])
    if bulk.get('resources')!={'cpus':24,'memory_gib':32,'time':'48:00:00'}:
        differences.append('CURRENT_PREPARED_RESOURCE_RECIPE_DIFFERS')
    return differences

def check_runtime_binding():
    """Pure metadata migration check; no production files or submissions."""
    main={'path':str(ROOT/'scripts/wp5_main_v11.sbatch'),'sha256':'1'*64}
    runner={'path':str(ROOT/'scripts/wp5_runner_v11.py'),'sha256':'2'*64}
    contract={'current_runtime':{'wp5_main_v11.sbatch':main,'wp5_runner_v11.py':runner},
              'sources':[main,runner],'policy':'FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT',
              'audit_manifest':{'path':'fixture_audit','sha256':'3'*64},
              'reproduction_package':{'path':'fixture_package','sha256':'4'*64}}
    binding=current_runtime_binding(contract)
    assert binding['version']==11 and binding['main']==main and binding['runner']==runner
    nodes=['compute-0-'+str(n) for n in (12,13,14,17,18,19)]
    tasks=[{'task_id':str(i),'node':nodes[i%6]} for i in range(72)]
    mains=[{**t,'name':'fixture_main_'+t['task_id'],'mode':'main'} for t in tasks]
    cleanups=[{'node':node,'mode':'cleanup','afterany_main_names':[t['name'] for t in mains if t['node']==node]} for node in nodes]
    ref={'path':'fixture_contract','sha256':'5'*64}
    bulk={'script':main['path'],'script_sha256':main['sha256'],'tasks_sha256':'6'*64,'version':11,
          'production_contract':ref,'raw_policy':contract['policy'],'audit_manifest':contract['audit_manifest'],
          'reproduction_package':contract['reproduction_package'],'main':mains,'cleanup':cleanups,
          'resources':{'cpus':24,'memory_gib':32,'time':'48:00:00'}}
    assert not prepared_runtime_differences(bulk,contract,binding,tasks,'6'*64,ref)
    for key,value,expected in (
        ('script',str(ROOT/'scripts/wp5_main_v10.sbatch'),'CURRENT_PREPARED_SCRIPT_SHA_OR_TASKPLAN_DIFFERS'),
        ('script_sha256','0'*64,'CURRENT_PREPARED_SCRIPT_SHA_OR_TASKPLAN_DIFFERS'),
        ('version',10,'CURRENT_PREPARED_PLAN_VERSION_POLICY_OR_CONTRACT_DIFFERS'),
        ('cleanup',cleanups[:-1],'CURRENT_PREPARED_SIX_CLEANUP_NODE_SCOPE_DIFFERS')):
        changed={**bulk,key:value}
        assert expected in prepared_runtime_differences(changed,contract,binding,tasks,'6'*64,ref)
    bad={**contract,'sources':[main,{**runner,'sha256':'0'*64}]}
    try:current_runtime_binding(bad);raise AssertionError('Unbound runtime accepted')
    except ValueError as error:assert 'NOT_SAME_FROZEN_SOURCE' in str(error)


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
    dictionary_ref=spec['dictionary_manifest'];dictionary_path=Path(dictionary_ref['path']);dictionary=json.loads(dictionary_path.read_text())
    targets.append(reference(dictionary_path,expected=dictionary_ref['sha256']))
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
    from wp5_submit_formal_v11 import validate_authority,validate_current_contract
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
    bulk_path=Path(spec['prepared_plan']['path']);bulk=json.loads(bulk_path.read_text())
    targets.append(reference(bulk_path,expected=spec['prepared_plan']['sha256']))
    if bulk['node_authority']!=str(authority) or bulk['node_authority_sha256']!=spec['node_authority_sha256'] or bulk['submit_helper']!=str(ROOT/'scripts/submit_wp5_job_v2.py'):differences.append('CURRENT_PREPARED_NODE_AUTHORITY_OR_HELPER_DIFFERS')
    targets.append(reference(bulk['submit_helper'],expected=bulk['submit_helper_sha256']))
    contract_path=Path(spec['production_contract']['path'])
    contract=validate_current_contract(contract_path,authority)
    targets.append(reference(contract_path,expected=spec['production_contract']['sha256']))
    runtime_binding=current_runtime_binding(contract)
    for ref in (runtime_binding['main'],runtime_binding['runner']):
        targets.append(reference(ref['path'],expected=ref['sha256']))
    targets.append(reference(bulk['script'],expected=bulk['script_sha256']))
    differences.extend(prepared_runtime_differences(bulk,contract,runtime_binding,node_plan['tasks'],node_manifest['tasks_sha256'],spec['production_contract']))
    if spec.get('scope')!='CURRENT_USER_OVERRIDE_RECORD_AUDIT_NO_INPUTS_12_TASKS_F64':differences.append('SPEC_NOT_CURRENT_USER_OVERRIDE_SCOPE')
    for key in ('audit_manifest','reproduction_package','protocol','registry','node_authority','node_scope_plan','authority'):
        ref=contract[key];targets.append(reference(ref['path'],expected=ref['sha256']))
    for ref in contract['sources']:targets.append(reference(ref['path'],expected=ref['sha256']))
    package=json.loads(Path(contract['reproduction_package']['path']).read_text())
    for asset in package['assets']:
        targets.append(reference(asset['path'],expected=asset['sha256'],bytes_expected=asset['bytes']))
        if asset.get('source_path'):targets.append(reference(asset['source_path'],expected=asset['sha256'],bytes_expected=asset['bytes']))
    for key in ('environment','recipes'):
        ref=package[key];targets.append(reference(ref['path'],expected=ref['sha256']))
    audit=json.loads(Path(contract['audit_manifest']['path']).read_text())
    selected=audit['selected_records'];targets.append(reference(selected['path'],expected=selected['sha256'],bytes_expected=selected['bytes'],rows_expected=selected['rows']))
    if (audit['population']['records'],audit['population']['molecules'])!=(pop['formal_records'],pop['formal_molecules']):differences.append('AUDIT_FORMAL_PHYSICAL_POPULATION_DIFFERS')
    if package['protocol']!=contract['protocol'] or package['registry']!=contract['registry']:differences.append('PACKAGE_PROTOCOL_OR_REGISTRY_DIFFERS')
    if {name:package['software_versions'][name]['software_version_id'] for name in ('mopac','xtb')}!={'mopac':1,'xtb':2}:differences.append('SIX_TRACE_SOFTWARE_ID_MAPPING_DIFFERS')
    baseline=json.loads((ROOT/'configs/pilot_success_baseline.json').read_text())
    if set(baseline['success_rates'])!=set(CALCS):differences.append('BASELINE_NOT12_CALC_TYPES')
    for rate in baseline['success_rates'].values():
        if not isinstance(rate,(int,float)) or not 0<=rate<=1:differences.append('BASELINE_INVALID_SUCCESS_RATE')
    return targets,differences,{'software':binaries,'actual_version_evidence':{'mopac':actual_mopac_line,'xtb':xtb['actual_version_line']},
      'recipes':keyword_records,'population':{'records':pop['formal_records'],'molecules':pop['formal_molecules'],'tasks':72},
      'actual_node_authority':{'path':str(authority),'sha256':spec['node_authority_sha256'],'authorized_node_slots':json.loads(authority.read_text())['authorized_node_slots'],'node_replacement_scope':'smoke and formal, not G3 capacity exemption'},
      'current_runtime_binding':runtime_binding,
      'changed_scope_description':spec.get('changed_scope'),
      'current_override':{'policy':contract['policy'],'authority':contract['authority'],'audit_manifest':contract['audit_manifest'],'reproduction_package':contract['reproduction_package'],'trace_fields':contract['trace_fields'],'final200_required':True,'contract_sha256':sha(contract_path)},
      'cached_input_sha_binding':'Prior actual population/packing closure SHA referenced; byte lengths rechecked. Original LMDB and source Parquet rows are not read.',
      'dictionary_historical_training_config_sha256':dictionary.get('formal_config_sha256'),'dictionary_note':'Dictionary codec payload is independently frozen; historical training config metadata is not an executable current recipe.',
      'new_data_leaf_hashes':'Current new formal population/assignments/task Parquet files hashed on this compute allocation; no original LMDB access.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,default=ROOT/'configs/g4_freeze_spec_v11.json');p.add_argument('--output',type=Path)
    p.add_argument('--workers',type=int,default=24);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        ast.parse(Path(__file__).read_text());assert len(CALCS)==12 and len(set(CALCS))==12
        check_runtime_binding()
        print('G4_AST_SCOPE_AND_CURRENT_RUNTIME_BINDING_PASS_NO_QM_NO_LMDB_NO_HASH');return
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
