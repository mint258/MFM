"""Draft portable metadata/identity contracts; no scheduler or main ledger access."""
from __future__ import annotations
import hashlib,json,os,socket,stat,sys,time
from pathlib import Path
ORIGINAL_RECIPE_BYTES=3629
ORIGINAL_RECIPE_SHA='cfd153fb524ad823d3903b0ff7d78e402bbbcb74e124136b4bfeb3035279407a'
CONTROL_MODE='SECONDARY_SOFTWARE_COMPATIBILITY_CONTROLS_ONLY'
MISSING_IDS={'principal_01112964','principal_00509656'}


def control_selection_rule():
    return {'schema':'EXISTING334_SECONDARY_QA_CONTROL16_SELECTION_V1','count':16,'required_status':'SUCCESS',
        'new_real_accepted_count_min':1,'max_heavy_atoms':32,'max_expected_conformers':30,
        'max_observed_main_elapsed_seconds':60.0,'hash_domain':'secondary-software-control16-v1:20261026:',
        'order':['sha256(hash_domain+molecule_id)','molecule_id'],'automatic_threshold_widening':False,
        'old_elapsed_is_selection_evidence_not_secondary_runtime_forecast':True}


def need(ok,message):
    if not ok:raise ValueError(message)


def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(value):return hashlib.sha256(value).hexdigest()
def normalized(pin):return {k:pin[k] for k in ('path','bytes','sha256')}


def read_small(path):
    path=Path(path);need(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)),'LITERAL_SMALL_PATH_REQUIRED')
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());need(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_size<=2<<20,'SMALL_OWNED_FILE_REQUIRED')
        raw=stream.read((2<<20)+1);after=os.fstat(stream.fileno())
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
         and len(raw)==before.st_size,'SMALL_FILE_CHANGED')
    return raw


def ref(path):
    path=Path(path).absolute();raw=read_small(path);return {'path':str(path),'bytes':len(raw),'sha256':sha(raw)}
def verify(pin):
    need(ref(pin['path'])==normalized(pin),'ACTUAL_LOCAL_SMALL_PIN_DIFFERS');return Path(pin['path'])
def load(pin):return json.loads(read_small(verify(pin)))


def environment_for_controls(value,source_reference,endpoint_id,target):
    """Accept the actual offline result via an explicit new Root metadata review.

    The existing result is copied unchanged as separate evidence; READY is never
    promoted to a scientific compatibility PASS by this conversion.
    """
    if value.get('schema')=='SECONDARY_UFF_ENVIRONMENT_ROOT_REVIEW_V1':return value
    need(value.get('schema')=='SECONDARY_OFFLINE_ENVIRONMENT_VALIDATION_V1' and
         value.get('status')=='READY_FOR_GOLDEN16_COMPATIBILITY_TEST' and value.get('endpoint')=='218.192.171.238:22' and
         value.get('uid')==1264 and value.get('user')=='alpha' and value.get('cpus')==16 and
         value.get('node') in target['allowed_cpu_nodes'] and value.get('memory_requested') is False and
         value.get('formal_generation_authorized') is False and value.get('golden_compatibility_accepted') is False and
         value.get('torch_matches_main_build_claimed') is False and value.get('dataset_records_read')==0 and
         value.get('UFF_calls')==0 and value.get('QM_calls')==0 and str(value.get('job_id','')).isdecimal() and
         value.get('forced_signals_sent') is False,'ACTUAL_SECONDARY_OFFLINE_VALIDATION_NOT_A_SCIENCE_PASS_REQUIRED')
    versions=value['versions']
    need(versions.get('python')=='3.11.14' and versions.get('numpy')=='2.2.6' and versions.get('rdkit')=='2025.09.5' and
         versions.get('torch')=='2.5.1+cpu' and versions.get('torch_geometric')=='2.7.0' and versions.get('torch_cuda_build') is None and
         versions.get('toy_numpy_svd_passed') is True and versions.get('toy_pickle_tensor_PyG_float64_exact') is True and
         versions.get('toy_rdkit_parse_atoms')==3 and versions.get('executable')==value['python_path'],
         'ACTUAL_EXACT_VERSIONS_AND_TOY_IO_CHECKS_REQUIRED_BUT_NOT_DATASET_COMPATIBILITY')
    return {'schema':'SECONDARY_UFF_ENVIRONMENT_ROOT_REVIEW_V1','status':'READY_FOR_GOLDEN16_COMPATIBILITY_TEST',
        'reviewer':'root','endpoint_id':endpoint_id,'formal_compatibility_passed':False,'python_executable':value['python_path'],
        'expected_versions':{k:versions[k] for k in ('python','numpy','rdkit','torch','torch_geometric','scipy','lmdb','pyarrow')},
        'probe_evidence_references':[normalized(source_reference)],'source_validation_reference':normalized(source_reference),
        'actual_secondary_validation_job_id':str(value['job_id']),'torch_build_identical_to_main':False,
        'main_torch_version_provenance':{'version_family':'2.10','exact_build':'NOT_CLAIMED_BY_THIS_ADAPTER',
            'source':'Root reported main2.10; actual offline result explicitly records secondary2.5.1+cpu',
            'secondary_actual_torch':versions['torch'],'actual_version_difference_note':value.get('version_difference_note')},
        'conversion_kind':'NEW_ROOT_METADATA_ONLY_ORIGINAL_RESULT_UNCHANGED',
        'actual_terminal_accounting':'ROOT_MUST_BIND_REAL_ENDPOINT_ACCOUNTING_SEPARATELY',
        'scientific_compatibility_accepted':False}


def recipe_equivalence(original,deployed,mapping,output_root):
    """Only two operational locator fields may differ; all science values equal."""
    expected=json.loads(json.dumps(original))
    for pin in original['science_source_pins']:
        target=mapping[pin['path']]
        need(target['bytes']==pin['bytes'] and target['sha256']==pin['sha256'],'SCIENTIFIC_SOURCE_MAPPING_CHANGED_BYTES')
    expected['science_source_pins']=[dict(pin,path=mapping[pin['path']]['path']) for pin in original['science_source_pins']]
    expected['external_output_root']=str(output_root)
    need(canonical(deployed)==canonical(expected),'NONLOCATOR_RECIPE_CHANGE')
    need(original['rdkit_version']=='2025.09.5','EXACT_ORIGINAL_RDKIT_RECIPE_REQUIRED')
    for old,new in zip(original['science_source_pins'],deployed['science_source_pins']):
        need(old['bytes']==new['bytes'] and old['sha256']==new['sha256'],'SCIENTIFIC_SOURCE_BYTES_MUST_BE_IDENTICAL')
    return {'equal_after_exact_locator_substitution':True,'scientific_values_changed':False,
        'allowed_changes':['science_source_pins[].path','external_output_root'],
        'main_authority_paths_are_provenance_only_not_opened_on_secondary':True}


def prep_metadata(prep):
    need(prep.get('schema')=='MAIN_EXISTING334_SECONDARY_CONTROL16_PREPARATION_V1' and
         prep.get('status')=='ROOT_APPROVED_EXISTING_PACKETS_FOR_SECONDARY_SOFTWARE_QA_ONLY' and prep.get('reviewer')=='root',
         'ACTUAL_EXISTING334_CONTROL16_EXPORT_AND_REVIEW_REQUIRED')
    need(prep.get('mode')==CONTROL_MODE and prep.get('formal_generation_authorized') is False and
         prep.get('main_preparation_on_legal_cpu_allocation') is True and prep.get('automatic_retry') is False,
         'SOFTWARE_QA_ONLY_NO_FORMAL_OR_AUTOMATIC_RETRY')
    protected=prep['protected_original_population_ids'];ids=prep['molecule_ids'];expected=prep['golden_expected']
    allow=prep['allowed_original_control_ids'];forbidden=prep['forbidden_original_population_ids']
    need(len(protected)==len(set(protected))==336 and MISSING_IDS<=set(protected),
         'FULL_PROTECTED_OLD336_AND_TWO_MISSING_IDS_REQUIRED')
    need(len(ids)==len(set(ids))==len(allow)==len(set(allow))==16 and set(ids)==set(allow)<=set(protected)-MISSING_IDS and
         len(forbidden)==len(set(forbidden))==320 and set(forbidden)==set(protected)-set(allow) and MISSING_IDS<=set(forbidden) and
         len(expected)==16 and {row['molecule_id'] for row in expected}==set(ids),'EXACT16_ROOT_QA_ALLOWLIST_WITH_TWO_MISSING_ALWAYS_FORBIDDEN')
    need(prep.get('population_members_added')==0 and prep.get('main_production_once_ledger_accessed') is False and
         prep.get('current_main_recovery_2plus14_scope_changed') is False and prep.get('new_main_science_baseline_computed') is False and
         prep.get('original_pilot_parent_state')=='TIMEOUT' and prep.get('partial_audit_parent_job_id')=='4520527' and
         prep.get('partial_audit_parent_state')=='COMPLETED','QA_CONTROL_REPLAY_CANNOT_CHANGE_POPULATION_RECOVERY_OR_ORIGINAL_TIMEOUT')
    need(canonical(prep['selection_rule'])==canonical(control_selection_rule()) and
         isinstance(prep.get('root_control_authorization_reference'),dict) and isinstance(prep.get('qa_slice_marker_reference'),dict) and
         all(isinstance(prep.get(k),dict) for k in ('original_audit_reference','original_complete_packages_reference','partial_audit_monitor_closure_reference')),
         'EXACT_FIXED_ROOT_RULE_CONTROL_SLICE_AND_EXISTING_AUDIT_PINS_REQUIRED')
    task=prep['tasks_reference']
    need(isinstance(prep.get('slice_id'),str) and 0<len(prep['slice_id'])<=128 and Path(task['path']).is_absolute() and
         type(task['bytes']) is int and 0<task['bytes']<=1<<30 and isinstance(task['sha256'],str) and len(task['sha256'])==64 and
         set(task['sha256'])<=set('0123456789abcdef'),'ACTUAL_BOUNDED_MAIN_TASK_EXPORT_LOCATOR_REQUIRED')
    for row in expected:
        need(all(isinstance(row.get(k),str) and len(row[k])==64 and set(row[k])<=set('0123456789abcdef')
                 for k in ('task_sha256','scientific_sha256_excluding_elapsed_seconds')),'ACTUAL_MAIN_TASK_AND_GOLDEN_HASHES_REQUIRED')
        need(row.get('baseline_summary_status')=='SUCCESS' and isinstance(row.get('baseline_packet_reference'),dict) and
             isinstance(row.get('baseline_file_identity'),dict),'ACTUAL_SUCCESSFUL_EXISTING_BASELINE_PACKET_PINS_REQUIRED')
    return {row['molecule_id']:row for row in expected}


def installed(deployment):
    target=deployment['target'];root=Path(target['deployment_root'])
    need(target['ssh_host']=='218.192.171.238' and target['ssh_user']=='alpha' and target['uid']==1264 and
         root==Path('/gfshome/alpha/codex_data_v1_20261026'),'EXPLICIT_SECONDARY_ENDPOINT_REQUIRED')
    need(deployment['endpoint_id']==sha(canonical(target)) and deployment['mode']==CONTROL_MODE and
         deployment['formal_generation_authorized'] is False,'EXACT_SECONDARY_DEPLOYMENT_ID_AND_GOLDEN_SCOPE_REQUIRED')
    need(deployment.get('schema')=='PORTABLE_SECONDARY_UFF_CONTROL16_DEPLOYMENT_MAP_V1','PORTABLE_DEPLOYMENT_MAP_SCHEMA_REQUIRED')
    authority=load(deployment['target_authority_target_locator'])
    need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_FREE_CPU_UFF_V1' and authority.get('status')=='USER_AUTHORIZED' and
         authority.get('target')==target and authority.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED' and
         authority.get('formal_generation_authorized') is False,'ACTUAL_SECONDARY_USER_AUTHORITY_REQUIRED')
    for row in deployment['science_sources']+deployment['portable_worker_sources']:
        local=row['target_locator'];need(root in Path(local['path']).parents,'SOURCE_OUTSIDE_SECONDARY_ROOT')
        verify(local)
        need(row['origin_reference']['bytes']==local['bytes'] and row['origin_reference']['sha256']==local['sha256'],
             'SOURCE_RELOCATION_CHANGED_BYTES')
    environment=load(deployment['environment_review_target_locator'])
    env_origin=deployment['environment_input_origin_reference'];env_local=deployment['environment_validation_target_locator']
    need(env_origin['bytes']==env_local['bytes'] and env_origin['sha256']==env_local['sha256'],
         'ORIGINAL_ENVIRONMENT_RESULT_BYTES_MUST_REMAIN_UNCHANGED')
    normalized_environment=environment_for_controls(load(env_local),env_origin,deployment['endpoint_id'],target)
    need(environment.get('schema')=='SECONDARY_UFF_ENVIRONMENT_ROOT_REVIEW_V1' and
         environment.get('status')=='READY_FOR_GOLDEN16_COMPATIBILITY_TEST' and environment.get('reviewer')=='root' and
         environment.get('endpoint_id')==deployment['endpoint_id'] and environment.get('formal_compatibility_passed') is False and
         canonical(environment)==canonical(normalized_environment) and environment.get('torch_build_identical_to_main') is False and
         environment.get('main_torch_version_provenance')==deployment['main_torch_version_provenance'],
         'ACTUAL_ENVIRONMENT_REVIEW_NOT_YET_FORMAL_COMPATIBILITY_PASS')
    prep=load(deployment['main_preparation_target_locator']);expected=prep_metadata(prep)
    authorization=load(deployment['control_authorization_target_locator'])
    need(authorization.get('schema')=='ROOT_SECONDARY_EXISTING334_CONTROL16_AUTHORIZATION_V1' and
         authorization.get('status')=='APPROVED_FOR_SECONDARY_SOFTWARE_COMPATIBILITY_ONLY' and authorization.get('reviewer')=='root' and
         authorization.get('endpoint_id')==deployment['endpoint_id'] and authorization.get('mode')==CONTROL_MODE and
         authorization.get('formal_generation_authorized') is False and
         authorization.get('allowed_existing_control_count')==16 and set(authorization['forbidden_missing_ids'])==MISSING_IDS and
         canonical(authorization['selection_rule'])==canonical(control_selection_rule()),'EXACT_ROOT_SOFTWARE_CONTROL_AUTHORIZATION_REQUIRED')
    for origin_name,target_name in (('root_control_authorization_reference','control_authorization_target_locator'),
            ('original_audit_reference','original_audit_target_locator'),('original_complete_packages_reference','original_complete_packages_target_locator'),
            ('partial_audit_monitor_closure_reference','partial_audit_monitor_closure_target_locator')):
        old,new=prep[origin_name],deployment[target_name]
        need(old['bytes']==new['bytes'] and old['sha256']==new['sha256'],'EXISTING_AUDIT_OR_QA_AUTHORITY_RELOCATION_CHANGED_BYTES')
    audit=load(deployment['original_audit_target_locator']);closed=load(deployment['original_complete_packages_target_locator'])
    monitor=load(deployment['partial_audit_monitor_closure_target_locator'])
    need(audit['status']=='PARTIAL_PILOT_NOT_ACCEPTED_FOR_FORMAL' and audit['original_job_id']=='4520364' and audit['original_parent_state']=='TIMEOUT' and
         audit['complete_reusable_molecules']==334 and audit['missing_molecules']==2 and monitor['job_id']=='4520527' and
         audit['invalid_molecules']==0 and audit['unexpected_entries']==0 and len(closed)==334 and
         len({row['molecule_id'] for row in closed})==334 and not {row['molecule_id'] for row in closed}&MISSING_IDS and
         set(prep['protected_original_population_ids'])=={row['molecule_id'] for row in closed}|MISSING_IDS and
         monitor['status']=='COMPLETED_NO_MEMORY_DENIAL' and monitor['durable_evidence_exported'] is True and
         prep['original_complete_packages_reference'] in audit['outputs'],'EXISTING334_PARTIAL_AUDIT_C0_NOT_ORIGINAL_PILOT_C0_REQUIRED')
    from .prepare_existing_controls import select_metadata
    selected,selection=select_metadata(closed)
    need(len(selected)==16 and [row['molecule_id'] for row in selected]==prep['allowed_original_control_ids'],
         'EXACT_FIXED_HASH_SMALL_FAST_CONTROL16_SELECTION_REQUIRED')
    for row in selected:
        baseline=expected[row['molecule_id']]
        need(row['reference']==baseline['baseline_packet_reference'] and row['file_identity']==baseline['baseline_file_identity'],
             'ORIGINAL_BASELINE_PACKET_PIN_OR_IDENTITY_CHANGED')
    for name in ('tasks_target_locator','recipe_target_locator','main_preparation_target_locator'):
        need(root in Path(deployment[name]['path']).parents,'NO_MAIN_ABSOLUTE_INPUT_ALIAS_ON_SECONDARY')
    catalog=load(deployment['source_catalog_target_locator'])
    need({row['basename']:row['origin_reference'] for row in catalog['sources']}==
         {row['basename']:row['origin_reference'] for row in deployment['science_sources']},
         'ACTUAL_ORIGINAL_SCIENTIFIC_CATALOG_DIFFERS')
    recipe=load(deployment['recipe_target_locator']);origin=deployment['original_recipe_value']
    original_pin=deployment['original_recipe_target_locator']
    need(original_pin['bytes']==ORIGINAL_RECIPE_BYTES and original_pin['sha256']==ORIGINAL_RECIPE_SHA and
         canonical(load(original_pin))==canonical(origin),'EXACT_FROZEN_ORIGINAL_RECIPE_REQUIRED')
    mapping={row['origin_reference']['path']:row['target_locator'] for row in deployment['science_sources']}
    recipe_equivalence(origin,recipe,mapping,root/'outputs')
    return target,recipe


def startup(deployment,map_path,proof_path,output):
    """Separate endpoint/UID/proof namespace; main proof schemas are rejected."""
    target,recipe=installed(deployment);proof=json.loads(read_small(proof_path));request=proof['request']
    need(proof.get('schema')=='SECONDARY_PORTABLE_UFF_CONTROL16_STARTUP_V1' and
         proof.get('endpoint_id')==deployment['endpoint_id'] and proof.get('uid')==target['uid']==os.getuid() and
         proof.get('boot_id')==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
         'ACTUAL_SECONDARY_ENDPOINT_UID_BOOT_PROOF_REQUIRED')
    need(os.environ.get('SLURM_JOB_ID')==str(proof['job_id']) and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and
         os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('CUDA_VISIBLE_DEVICES')=='' and
         socket.gethostname().split('.')[0]==proof['node'] and proof['node'] in target['allowed_cpu_nodes'],
         'ACTUAL_SECONDARY_CPU16_ALLOWED_NODE_AND_NO_GPU_REQUIRED')
    need(all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),
         'ONE_LIBRARY_THREAD_PER_WORKER_REQUIRED')
    age=time.time()-proof['observed_unix_seconds'];need(0<=age<=120,'SECONDARY_STARTUP_PROOF_NOT_FRESH')
    need(request.get('kind')=='conformer' and request.get('pilot') is True and request['cpus']==16 and
         request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and 'memory_gib' not in request and
         type(request['wall_seconds']) is int and 0<request['wall_seconds']<=deployment['max_wall_seconds'],
         'FINITE_NEW_CPU_REQUEST_WITH_MEMORY_OMITTED_REQUIRED')
    main=Path(sys.modules['__main__'].__file__).absolute()
    expected_main=Path(target['deployment_root'])/'code/portable_secondary_uff_v1/worker.py'
    expected=[deployment['python'],'-B','-m','portable_secondary_uff_v1.worker','--deployment-map',str(Path(map_path).absolute()),
        '--startup-proof',str(Path(proof_path).absolute()),'--output',str(Path(output).absolute())]
    need(main==expected_main and Path(sys.executable).absolute()==Path(deployment['python']).absolute() and
         request['execution_argv']==expected and sys.argv==[str(expected_main),*expected[4:]],
         'ACTUAL_SECONDARY_PRIMARY_AND_ALL_OPTIONS_REQUIRED')
    need(proof['deployment_map_reference']==ref(map_path) and proof.get('root_exact_scope_reviewed') is True and
         proof.get('environment_ready_for_golden16_only') is True and proof.get('execution_admission_granted') is True,
         'ROOT_EXACT_MAP_SCOPE_ENVIRONMENT_AND_EXECUTION_PROOF_REQUIRED')
    review=load(proof['root_scope_review_reference'])
    need(review.get('schema')=='SECONDARY_PORTABLE_UFF_CONTROL16_ROOT_SCOPE_V1' and
         review.get('status')=='APPROVED_FOR_EXACT_SECONDARY_CONTROL16' and review.get('reviewer')=='root' and
         review.get('endpoint_id')==deployment['endpoint_id'] and review.get('deployment_map_reference')==ref(map_path) and
         review.get('mode')==CONTROL_MODE and review.get('population_members_added')==0 and
         review.get('execution_argv')==expected and review.get('wall_seconds')==request['wall_seconds'] and
         review.get('script_reference')==proof['script_reference'] and review.get('formal_generation_authorized') is False,
         'ACTUAL_EXACT_SECONDARY_ROOT_SCOPE_REVIEW_PIN_REQUIRED')
    script=read_small(verify(proof['script_reference'])).decode()
    for line in script.splitlines():
        if line.strip().startswith('#SBATCH'):
            need(not any(word in line for word in ('--mem','--gres','--gpu','--exclusive')),'NO_SECONDARY_MEMORY_GPU_OR_EXCLUSIVITY_REQUEST')
    job=proof['job_metadata']
    need(str(job['JobId'])==str(proof['job_id']) and str(job['UserId']).split('(')[-1].rstrip(')')==str(os.getuid()) and
         job['JobState']=='RUNNING' and job['Partition']=='cpu' and str(job['NumCPUs'])=='16' and
         job['NodeList']==proof['node'] and job['Command']==proof['script_reference']['path'],
         'ACTUAL_SECONDARY_SLURM_JOB_IDENTITY_REQUIRED')
    wall=job['TimeLimit'];days,clock=wall.split('-',1) if '-' in wall else ('0',wall)
    parts=list(map(int,clock.split(':')))
    need(len(parts)==3 and int(days)>=0 and all(v>=0 for v in parts) and parts[1]<60 and parts[2]<60 and
         int(days)*86400+parts[0]*3600+parts[1]*60+parts[2]==request['wall_seconds'] and
         str(job.get('NumTasks','1'))=='1' and str(job.get('Requeue','0'))=='0',
         'ACTUAL_SECONDARY_WALL_SINGLE_TASK_AND_NO_REQUEUE_REQUIRED')
    need(proof['account_free_bytes']-deployment['max_output_bytes']>=200000000000 and proof.get('quota_raw'),
         'ACTUAL_SECONDARY_OUTPUT_PLUS200GB_QUOTA_REQUIRED')
    return proof,recipe
