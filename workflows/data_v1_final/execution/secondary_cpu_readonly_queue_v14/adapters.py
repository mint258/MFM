"""Only exact canonical32 original sparse-LMDB reads; zero UFF/QM or membership."""
import copy,csv,io,re
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from n1_sparse32_readchain_v1 import guard as C
ROOT=Q.ROOT;ENDPOINT=Q.ENDPOINT;UID=Q.UID;POLICY=Q.POLICY
HERE=ROOT/'code/secondary_cpu_readonly_queue_v14';CONSUMER=ROOT/'code/n1_sparse32_readchain_v1'
STORAGE_SCOPE=ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'
MAIN=Path('/share/home/zixiao/descriptor_analysis');RUN=MAIN/'runs/data_v1_20261025'
MAIN_REPO=RUN/'repository';MAIN_EXPORT_BASE=RUN/'artifacts/conformers/n1_sparse32_readchain_v1'
ALPHA_INPUT_BASE=ROOT/'inputs/n1_sparse32_readchain_v1';MODULE='n1_sparse32_readchain_v1.alpha_read'
MODE='EXACT_CANONICAL32_ORIGINAL_READ_ONLY_CONTROL'
PROTOCOLS={C.ALPHA_KEY:{'plan':'SECONDARY_N1_SPARSE32_READCHAIN_PLAN_V1','proof':'SECONDARY_N1_SPARSE32_READCHAIN_STARTUP_V1',
    'stage':C.ALPHA_STAGE,'module':MODULE,'pilot':False,'scope_mode':MODE,'performance_profile':False,'cap':2<<30,'wall_max':3600}}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','output_directory','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')
FROZEN11={
 '__init__.py':(84,'5b669cad99392bdb2300beed181630bbbdca8ee5112471aeaf62f0a75f3fd289'),
 'alpha_read.py':(11380,'c1a205701ccdeadcba956b47da208476e5e28a67bb4e8616a8e3367cc427cace'),
 'common.py':(6300,'1fc6c497a1fcc6771a5dc2b75474b3af420da84bd72c11ca2b288cd9e6fe53c2'),
 'driver.py':(2826,'295e9b06bb8ff73c4d092967bf8ea99452a51fd4b50aed12092f1b9571e66a09'),
 'guard.py':(16774,'62ad773dbb64880d99aeec97a089701d32db93c37eb37a8c351ac29a50b884bb'),
 'main_export.py':(14546,'0279b39a41a7c6858705626cf796c2ea5b971f4951977c0df48b9999c0545aea'),
 'README.md':(13799,'b76f2db30d11c22d9c5f9b3bf1f4a8f7c5257584e0d3cc45bb8a7c7280ccdd97'),
 'signatures.py':(6652,'cc430d6e67653dee52cde3a9a9d5bad7523d12dc85821fe192407cc0269fbc73'),
 'source.py':(6802,'e8183f087701dd7d40b7aa9aef37dba362fd8b32ce0aef0879c8b0e18b27db90'),
 'test_readchain.py':(5441,'ec8b97f0756b87108a370468e308834e38c1c1661b4cae307e22277514d4a52c'),
 'verify_port.py':(3621,'58e1d350bab311268f80a7f957c43241aad96558428cf5b5ab015abefc114028')}

def locator(value,base):
    Q.need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>0
        and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']),'ACTUAL_PRODUCER_EXACT_NONEMPTY_TRIPLE')
    path=Path(value['path']);Q.need(path.is_absolute() and '..' not in path.parts and base in path.parents,'EXPLICIT_ENDPOINT_LOCATOR_PREFIX')
    # Even .json task/signature bodies remain locators here: no stat/open/hash.
    return path

def identical_bytes(origin,target):
    Q.need(all(origin[k]==target[k] for k in ('bytes','sha256')),'ORIGINAL_MAIN_AND_ALPHA_COPY_BYTES_SHA_DIFFER')

def metadata(plan,key,parent=False):
    reference=plan[key];Q.need(reference in plan['source_references'] and (not parent or reference in plan['parent_evidence_references']),
        'EXPLICIT_APPROVED_SMALL_AUTHORITY:'+key)
    return Q.load_ref(reference)

def source_handoff(plan):
    handoff=metadata(plan,'source_handoff_reference')
    Q.need(handoff.get('schema')=='N1_SPARSE32_READCHAIN_SOURCE_FINAL_DEPLOYMENT_HANDOFF_V1'
        and handoff.get('status')=='SOURCE_FINAL_EXPECTED_TARGETS_NOT_DEPLOYMENT_VERIFIED' and handoff.get('source_files')==11
        and handoff.get('frozen_11_bytes_modified_after_SOURCEFINAL') is False,'ACTUAL_FROZEN11_SOURCE_HANDOFF')
    rows={r['name']:r for r in handoff['files']};Q.need(len(rows)==len(handoff['files'])==11 and set(rows)==set(FROZEN11),'EXACT_ELEVEN_SOURCE_NAMES')
    Q.need({p.name for p in CONSUMER.iterdir() if p.suffix in ('.py','.md')}==set(FROZEN11),'NO_EXTRA_OR_MISSING_CONSUMER_SOURCE')
    for name,(size,digest) in FROZEN11.items():
        row=rows[name];alpha={'path':str(CONSUMER/name),'bytes':size,'sha256':digest}
        main={'path':str(MAIN_REPO/'workflows/data_v1_final/conformers/n1_sparse32_readchain_v1'/name),'bytes':size,'sha256':digest}
        Q.need(row['expected_Alpha_reference']==alpha and row['expected_Root_reference']==main
            and all(row['origin_reference'][k]==alpha[k] for k in ('bytes','sha256')),'FROZEN_SOURCE_TARGET_ORIGIN_MAPPING')
        Q.need(alpha in plan['source_references'] and Q.ref(CONSUMER/name)==alpha,'ACTUAL_ALPHA_DEPLOYED_SOURCE_BYTES_NOT_EXPECTED_ONLY')
    return rows

def main_parent_and_runtime(plan,manifest,handoff_rows):
    account=metadata(plan,'main_export_accounting_reference',True)
    raw_reference=plan['main_export_raw_sacct_reference'];Q.need(raw_reference in plan['parent_evidence_references']
        and raw_reference in plan['source_references'],'ACTUAL_MAIN_EXPORT_RAW_ACCOUNTING_COPY_APPROVED')
    locator(plan['main_export_accounting_origin_reference'],RUN)
    identical_bytes(plan['main_export_accounting_origin_reference'],plan['main_export_accounting_reference'])
    locator(account['raw_sacct_reference'],RUN);identical_bytes(account['raw_sacct_reference'],raw_reference)
    rows=list(csv.DictReader(io.StringIO(Q.verify(raw_reference).read_text()),delimiter='|'))
    selected=[r for r in rows if r.get('JobIDRaw',r.get('JobID'))==manifest['job_id']]
    Q.need(account.get('schema')=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account.get('status')=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
        and account.get('query_returncode')==0 and account.get('endpoint')=='202.38.247.57:22' and account.get('uid')==1278
        and len(selected)==1 and selected[0].get('UID')=='1278' and selected[0].get('State')=='COMPLETED'
        and selected[0].get('ExitCode')=='0:0' and selected[0].get('AllocCPUS')=='16' and selected[0].get('NodeList')=='compute-0-13',
        'ACTUAL_NEW_MAIN_EXPORT_C0_UID1278_CPU16_NOT_ALPHA_OR_CANONICAL_PILOT')
    declared=[r for r in account['parents'] if str(r['job_id'])==manifest['job_id']]
    Q.need(len(declared)==1 and declared[0]['state']=='COMPLETED' and declared[0]['exit_code']=='0:0'
        and declared[0]['alloc_cpus']==16 and declared[0]['elapsed_raw_seconds']==int(selected[0]['ElapsedRaw']),'MAIN_C0_DECLARED_RAW_AGREEMENT')
    proof=metadata(plan,'main_export_startup_proof_reference',True);request=metadata(plan,'main_export_request_reference',True)
    script_reference=plan['main_export_script_reference'];Q.need(script_reference in plan['parent_evidence_references']
        and script_reference in plan['source_references'],'EXACT_MAIN_EXPORT_SCRIPT_COPY_APPROVED')
    locator(manifest['actual_parent_proof_reference'],RUN);identical_bytes(manifest['actual_parent_proof_reference'],plan['main_export_startup_proof_reference'])
    locator(proof['request_reference'],RUN);identical_bytes(proof['request_reference'],plan['main_export_request_reference'])
    locator(request['script_reference'],RUN);identical_bytes(request['script_reference'],script_reference)
    Q.need(proof.get('schema')=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and proof.get('uid')==1278
        and str(proof.get('job_id'))==manifest['job_id'] and proof.get('memory_policy')==POLICY
        and proof.get('memory_admission_evaluated') is False and proof.get('memory_limits_requested') is False
        and proof.get('execution_admission_granted') is True and proof['request']==request
        and proof['source_references']==request['source_references']==manifest['source_references']
        and proof['script_reference']==request['script_reference'],'REAL_MAIN_STARTUP_REQUEST_SOURCE_CHAIN_ONLY_AS_PARENT_EVIDENCE')
    Q.need(request.get('schema')=='CPU_AUTO_MEMORY_QUEUED_REQUEST_V1' and request.get('scope_key')==C.MAIN_KEY
        and request.get('scope_parameters')==C.PARAMETERS and request.get('kind')=='analysis' and request.get('pilot') is False
        and request.get('node')=='compute-0-13' and request.get('partition')=='cpu' and request.get('cpus')==16
        and request.get('memory_policy')==POLICY and type(request.get('wall_seconds')) is int and 120<request['wall_seconds']<=3600
        and request.get('estimated_peak_output_bytes')>=2<<30,'EXACT_ORIGINAL_MAIN_EXPORT_RESOURCE_SCOPE')
    argv=request['execution_argv'];Q.need(len(argv)==8 and argv[:4]==['/share/home/zixiao/.conda/envs/chemprop/bin/python','-B','-m',
        'workflows.data_v1_final.conformers.n1_sparse32_readchain_v1.main_export'] and argv[4]=='--plan' and argv[6]=='--root-preflight'
        and argv[7]==manifest['actual_parent_proof_reference']['path'],'EXACT_MAIN_EXPORT_PRIMARY_NOT_GENERATION_OR_QA')
    for row in handoff_rows.values():Q.need(row['expected_Root_reference'] in request['source_references'],'ACTUAL_MAIN_EXECUTED_SAME_FROZEN11_SOURCE')
    for line in Q.verify(script_reference).read_text().splitlines():
        if line.strip().startswith('#SBATCH'):Q.need(not any(v in line for v in ('--mem','--exclusive','--gres','--gpu')),'ORIGINAL_MAIN_NO_SCHEDULER_MEMORY_GPU_OR_EXCLUSIVE')
    # This is historical Main proof validation, never freshness or execution
    # authority for Alpha. Alpha's new controller creates a separate fresh proof.
    return account,proof,request

def inventory_and_relocation(plan,manifest,account,main_proof,main_request):
    expected=[];data=[];record_ids=set();molecules=set();keys=set();raw_total=0;map_total=0
    main_root=locator(plan['origin_manifest_reference'],MAIN_EXPORT_BASE).parent
    def pair(kind,origin,target):
        locator(origin,MAIN);locator(target,ROOT);identical_bytes(origin,target)
        expected.append({'kind':kind,'origin_reference':origin,'target_locator':target})
    databases={r['group_id']:r for r in manifest['databases']}
    Q.need(1<=len(databases)==len(manifest['databases'])<=32,'UNIQUE_MAIN_EXPORT_ORIGIN_GROUPS')
    for group_id,db in databases.items():
        locator(db['reference'],main_root);locator(db['alpha_target_locator'],ALPHA_INPUT_BASE)
        Q.need(db['all_original_KV_bytes_equal_after_reopen'] is True and db['original_whole_LMDB_SHA256'] is None
            and type(db['map_size_bytes']) is int and 0<db['map_size_bytes']<=528<<20
            and 0<db['reference']['bytes']<=db['map_size_bytes'] and db['unique_keys']==db['logical_records'],
            'ACTUAL_REOPENED_NEW_DB_FULL_SHA_NO_INVENTED_ORIGINAL715GB_SHA')
        pair('sparse_lmdb',db['reference'],db['alpha_target_locator']);data.append(db['alpha_target_locator']);map_total+=db['map_size_bytes']
    for row in manifest['records']:
        pointer=row['origin_pointer'];index=pointer['real_index'];rid=row['record_id'];mid=row['molecule_id'];db=databases[row['group_id']]
        Q.need(type(index) is int and 0<=index<1<<63 and row['key_hex']==f'{index:09d}'.encode('ascii').hex()
            and rid==pointer['record_id'] and mid==pointer['molecule_id'] and rid not in record_ids and mid not in molecules
            and row['origin_pointer_sha256']==Q.sha(Q.canonical(pointer)),'EXACT_ORIGINAL_RECORD_IDX_POINTER_IDENTITY')
        origin_path=Path(pointer['source_path']);origin_path=origin_path if origin_path.is_absolute() else MAIN/origin_path
        Q.need(str(origin_path)==db['origin_source_path'],'CANONICAL_POINTER_MUST_BELONG_TO_ITS_ORIGIN_DATABASE')
        key=(db['origin_source_path'],row['key_hex']);Q.need(key not in keys,'NO_DUPLICATE_ORIGIN_KEY')
        keys.add(key);record_ids.add(rid);molecules.add(mid)
        for name,path in (('main_sparse_execution_pointer',db['reference']['path']),('alpha_execution_pointer',db['alpha_target_locator']['path'])):
            Q.need(row[name]==dict(pointer,source_path=path),'SOURCE_PATH_ONLY_EXECUTION_RELOCATION_NOT_REINDEX')
        Q.need(type(row['raw_value_bytes']) is int and 0<row['raw_value_bytes']<=8<<20
            and row['raw_value_sha256']==pointer['record_payload_sha256'] and re.fullmatch('[0-9a-f]{64}',row['raw_value_sha256'])
            and row['main_sparse_original_reader_comparison']=='EXACT_TYPED_FIELD_BITS_MATCH','NO_RAW_OR_FIELD_UNKNOWN_AUTOMATIC_PASS')
        raw_total+=row['raw_value_bytes']
        for kind,old,new in (('original_task','main_task_copy_reference','alpha_task_reference'),
            ('original_baseline','main_baseline_copy_reference','alpha_baseline_reference'),('main_signature','main_signature_reference','alpha_signature_reference')):
            locator(row[old],main_root);locator(row[new],ALPHA_INPUT_BASE);pair(kind,row[old],row[new]);data.append(row[new])
        for origin_name,target_name in (('origin_task_reference','main_task_copy_reference'),('origin_baseline_reference','main_baseline_copy_reference')):
            locator(row[origin_name],RUN);identical_bytes(row[origin_name],row[target_name])
    Q.need(len(record_ids)==len(molecules)==len(keys)==32 and raw_total==manifest['raw_value_bytes']<=256<<20
        and map_total<=1<<30 and data==manifest['alpha_data_references']==plan['data_references']
        and len(data)==len(databases)+96 and sum(r['bytes'] for r in data)==manifest['alpha_expected_input_bytes']<=2<<30,
        'COMPLETE_REAL_EXPORTED_BODY_INVENTORY_CONSERVATION')
    for group_id,db in databases.items():
        members=[r for r in manifest['records'] if r['group_id']==group_id]
        expected_hashes=sorted([{'key_hex':r['key_hex'],'value_bytes':r['raw_value_bytes'],'value_sha256':r['raw_value_sha256']} for r in members],key=lambda r:bytes.fromhex(r['key_hex']))
        Q.need(db['key_value_hashes']==expected_hashes and len(members)==db['unique_keys'] and db['raw_value_bytes']==sum(r['raw_value_bytes'] for r in members),
            'EACH_NEW_DATABASE_ORIGINAL_KV_HASH_MEMBERSHIP')
    science={}
    Q.need(len(manifest['science_source_copies'])==3,'EXACT_THREE_ORIGINAL_READER_SOURCES')
    for row in manifest['science_source_copies']:
        name=row['name'];Q.need(name not in science and name in ('common','legacy','prepare'),'EXACT_ORIGINAL_READER_SOURCE_NAME')
        identical_bytes(row['origin_reference'],row['main_copy_reference']);pair('frozen_'+name,row['main_copy_reference'],row['alpha_target_locator'])
        Q.need(row['origin_reference'] in main_request['source_references'],'ACTUAL_MAIN_ORIGINAL_READER_PIN_USED')
        science[name]=row['alpha_target_locator']
    Q.need(science==manifest['alpha_science_sources']==plan['science_sources'],'EXACT_READER_SOURCE_COPY_PATHS')
    pair('original_recipe',manifest['original_recipe_copy_reference'],manifest['alpha_original_recipe_reference'])
    pair('relocated_recipe',manifest['alpha_recipe_copy_reference'],manifest['alpha_recipe_reference'])
    identical_bytes(manifest['origin_recipe_reference'],manifest['original_recipe_copy_reference'])
    Q.need(plan['recipe_reference']==manifest['alpha_recipe_reference'] and plan['original_recipe_reference']==manifest['alpha_original_recipe_reference'],
        'EXPLICIT_ORIGINAL_AND_NEW_RECIPE_LOCATORS')
    original=metadata(plan,'original_recipe_reference');relocated=metadata(plan,'recipe_reference');wanted=copy.deepcopy(original)
    wanted['science_source_pins']=[dict(original['science_source_pins'][0],path=science['legacy']['path']),dict(original['science_source_pins'][1],path=science['prepare']['path'])]
    wanted['external_output_root']=str(ROOT/'artifacts/n1_sparse32_readchain_v1')
    Q.need(relocated==wanted,'NEW_RECIPE_ONLY_TWO_CODE_LOCATORS_AND_OUTPUT_ROOT_CHANGE')
    for kind,origin,target in (
        ('Main_export_manifest',plan['origin_manifest_reference'],plan['input_manifest_reference']),
        ('Main_export_accounting',plan['main_export_accounting_origin_reference'],plan['main_export_accounting_reference']),
        ('Main_export_raw_sacct',account['raw_sacct_reference'],plan['main_export_raw_sacct_reference']),
        ('Main_export_startup_proof',manifest['actual_parent_proof_reference'],plan['main_export_startup_proof_reference']),
        ('Main_export_request',main_proof['request_reference'],plan['main_export_request_reference']),
        ('Main_export_script',main_request['script_reference'],plan['main_export_script_reference'])):pair(kind,origin,target)
    relocation=metadata(plan,'copy_relocation_reference')
    Q.need(relocation.get('schema')=='ROOT_MAIN_SPARSE32_ALPHA_COPY_RELOCATION_V1'
        and relocation.get('status')=='ROOT_REVIEWED_EXPECTED_LOCATORS_NOT_BODY_HASH_ACCEPTANCE'
        and relocation.get('reviewer')=='root' and relocation.get('source_endpoint')=='202.38.247.57:22'
        and relocation.get('target_endpoint')==ENDPOINT and relocation.get('Main_export_manifest_origin_reference')==plan['origin_manifest_reference']
        and relocation.get('Alpha_manifest_copy_reference')==plan['input_manifest_reference']
        and relocation.get('Alpha_body_hash_acceptance_claimed') is False,'INDEPENDENT_ROOT_COPY_RELOCATION_NOT_SCIENCE_SUCCESS')
    actual=relocation['entries'];by_origin=lambda rows:{r['origin_reference']['path']:r for r in rows}
    Q.need(len(actual)==len(expected)==len(by_origin(actual))==len(by_origin(expected)) and by_origin(actual)==by_origin(expected)
        and len({r['target_locator']['path'] for r in actual})==len(actual),'EXACT_ROOT_RELOCATION_ALL_ACTUAL_FILES_NO_EXTRA_OR_ALIAS')
    return len(data),sum(r['bytes'] for r in data)

def readonly(input_path,deployment_path,node,seconds,**unused):
    Q.need(deployment_path is None,'V14_NO_OLD_QA_DEPLOYMENT_WRAPPER')
    plan=Q.load(input_path);spec=PROTOCOLS[C.ALPHA_KEY];refs={};wall=plan.get('wall_seconds')
    Q.need(plan.get('schema')==spec['plan'] and plan.get('scope_key')==plan.get('producer_key')==C.ALPHA_KEY
        and plan.get('scope_parameters')==C.PARAMETERS and plan.get('stage')==C.ALPHA_STAGE and plan.get('kind')=='analysis'
        and plan.get('pilot') is False and plan.get('scope_mode')==MODE and plan.get('performance_profile') is False
        and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node')==node and node in Q.NODES
        and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and type(wall) is int and wall==seconds and 120<wall<=3600
        and wall%60==0 and plan.get('output_cap_bytes')==2<<30,'V14_ONLY_CANONICAL32_ORIGINAL_READ_NO_GENERATION_SCOPE')
    review=Q.load_ref(plan['root_review_reference'])
    Q.need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE'
        and review.get('reviewer')=='root','EXACT_SPARSE32_INDEPENDENT_ROOT_REVIEW')
    for key in REVIEW_FIELDS:Q.need(plan[key]==review[key],'EXACT_ROOT_READCHAIN_REVIEW_DIFFERS:'+key)
    Q.need(plan['source_references']==review['approved_source_references'],'EXACT_READCHAIN_APPROVED_SOURCE_SET')
    for value in plan['data_references']:locator(value,ALPHA_INPUT_BASE)
    body_paths={r['path'] for r in plan['data_references']}
    Q.need(len(body_paths)==len(plan['data_references']) and not body_paths.intersection(r['path'] for r in [*plan['source_references'],*plan['parent_evidence_references']]),
        'SCIENTIFIC_TASK_SIGNATURE_OR_LMDB_NEVER_LOGIN_SOURCE_BODY')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],Q.ref(input_path),plan['root_review_reference']]:
        Q.normalized(value);Q.verify(value);Q.need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_READCHAIN_SMALL_SOURCE_PIN');refs[value['path']]=value
    for value in plan['parent_evidence_references']:Q.need(value in plan['source_references'],'ALL_MAIN_PARENT_COPIES_SMALL_APPROVED_SOURCE')
    for path in [*(p for p in HERE.iterdir() if p.suffix in ('.py','.md')),*Q.PACKAGE.glob('*.py')]:
        Q.need(Q.ref(path) in plan['source_references'],'ALL_ACTUAL_V14_AND_BASE_GATE_RUNTIME_SOURCE_PINS')
    for key in ('resource_authority_reference','cost_decision_reference','source_handoff_reference','copy_relocation_reference'):
        Q.need(plan[key] in plan['source_references'],'EXACT_NEW_READCHAIN_AUTHORITY:'+key)
    Q.authority(plan['resource_authority_reference']['path']);handoff=source_handoff(plan)
    manifest=metadata(plan,'input_manifest_reference',True);locator(plan['origin_manifest_reference'],MAIN_EXPORT_BASE)
    identical_bytes(plan['origin_manifest_reference'],plan['input_manifest_reference'])
    Q.need(manifest.get('schema')=='MAIN_N1_SPARSE32_EXACT_READCHAIN_EXPORT_V1'
        and manifest.get('status')=='ALL32_RAW_KV_EXPORTED_AND_REOPEN_VERIFIED_NO_GENERATION'
        and manifest.get('endpoint')=='202.38.247.57:22' and manifest.get('uid')==1278 and manifest.get('node')=='compute-0-13'
        and isinstance(manifest.get('job_id'),str) and manifest['job_id'].isdecimal() and manifest['job_id'] not in ('4521417','4521418','1884766','1884768')
        and manifest.get('scope_key')==C.MAIN_KEY and manifest.get('scope_parameters')==C.PARAMETERS
        and manifest.get('logical_record_count')==manifest.get('unique_molecule_count')==manifest.get('unique_KV_count')==32 and len(manifest['records'])==32
        and manifest.get('complete_field_signatures')==32 and manifest.get('unknown_field_signatures')==0
        and manifest.get('source_record_values_SHA_verified')==32 and manifest.get('new_sparse_LMDBs_whole_SHA_verified')==len(manifest['databases'])
        and len(set(manifest['main_original_read_actual_worker_PIDs']))==len(set(manifest['main_sparse_read_actual_worker_PIDs']))==16
        and manifest.get('source_LMDB_bodies_fully_hashed') is False and manifest.get('new_UFF_calls')==manifest.get('new_QM_calls')==0
        and manifest.get('once_ledger_opened') is False and manifest.get('canonical32_attempts_consumed') is False
        and manifest.get('dataset_membership') is False and manifest.get('production_population_release') is False
        and manifest.get('alpha_transfer_verified') is False and manifest.get('alpha_target_locations_are_expected_only') is True
        and manifest['resource_evidence']['stop'] is None,'ONLY_ACTUAL_MAIN_C0_EXACT32_RAW_AND_FIELD_READCHAIN_EXPORT_NO_UNKNOWN')
    account,main_proof,main_request=main_parent_and_runtime(plan,manifest,handoff)
    body_count,body_bytes=inventory_and_relocation(plan,manifest,account,main_proof,main_request)
    for value in [*plan['science_sources'].values(),plan['recipe_reference'],plan['original_recipe_reference']]:
        Q.need(value in plan['source_references'],'EXPLICIT_ACTUAL_ORIGINAL_READER_RUNTIME_COPY')
    proof=Q.literal(plan['startup_proof_path']);out=Q.literal(plan['output_directory'])
    Q.need(ROOT/'artifacts/n1_sparse32_readchain_v1' in out.parents and not out.exists(),'NEW_EXACT_ALPHA_READCHAIN_OUTPUT_PREFIX')
    Q.need(plan.get('transfer_verification_reference') is None and plan.get('transfer_verification_expected_output_path')==str(out/'transfer_verification.json'),
        'FUTURE_BODY_VERIFICATION_RECEIPT_MUST_NOT_BE_PRECLAIMED')
    argv=[plan['python'],'-B','-m',MODULE,'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    Q.need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_ALPHA_ORIGINAL_READ_PRIMARY_AND_COMPLETE_ARGV')
    return {'producer':'readonly','input_reference':Q.ref(input_path),'producer_argv':argv,'producer_plan_reference':Q.ref(input_path),
        'producer_review_reference':plan['root_review_reference'],'producer_authority_reference':plan['resource_authority_reference'],
        'source_references':list(refs.values()),'data_reference_locators_only':plan['data_references'],'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':2<<30,'producer_working_directory':str(ROOT/'code'),
        'proof_schema':spec['proof'],'request_kind':'analysis','pilot':False,'scope_key':C.ALPHA_KEY,'scope_parameters':C.PARAMETERS,
        'stage':C.ALPHA_STAGE,'scope_mode':MODE,'performance_profile':False,
        'fixed_archive_authority':{'Main_export_actual_job_id':manifest['job_id'],'original_PM7_records':32,'new_sparse_databases':len(manifest['databases']),
            'body_files':body_count,'body_bytes':body_bytes,'new_UFF_QM_calls':0,'once_ledger_opened':False,
            'Alpha_body_SHA_or_read_equivalence_claimed':False,'native_QA_or_full_generation_or_dataset_release_authorized':False}}

def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    Q.need(adapter['producer']=='readonly' and adapter['scope_key']==C.ALPHA_KEY and request['kind']==adapter['request_kind']=='analysis'
        and request['pilot'] is adapter['pilot'] is False and request['scope_key']==C.ALPHA_KEY
        and request['scope_parameters']==adapter['scope_parameters']==C.PARAMETERS and request['stage']==adapter['stage']==C.ALPHA_STAGE
        and request['scope_mode']==adapter['scope_mode']==MODE and request['performance_profile'] is adapter['performance_profile'] is False,
        'V14_ONLY_EXACT_ORIGINAL_SPARSE32_READ_REQUEST_NOT_NATIVE_QA_OR_FULL')
    Q.need(storage['storage_scope_review_reference']['path']==str(STORAGE_SCOPE),'EXACT_READCHAIN_STORAGE_SCOPE7')
    return {'schema':PROTOCOLS[C.ALPHA_KEY]['proof'],'endpoint':ENDPOINT,'uid':UID,'node':request['node'],
        'boot_id':probe['boot_id'],'job_id':str(jid),'observed_unix_seconds':probe['observed_unix_seconds'],
        'memory_policy':POLICY,'memory_limits_requested':False,'exclusive_requested':False,
        'script_reference':request['script_reference'],'controller_evidence':controller_evidence,
        'source_target_verification':request['verified_target_references'],'actual_gate_process':probe['gate_process'],
        'actual_memory_environment':probe['actual_memory_environment'],'scheduler_memory_is_recorded_not_an_admission_threshold':True,
        'other_jobs_modified':False,'forced_signals_sent':False,'job_metadata':raw,
        'request':{'kind':'analysis','pilot':False,'cpus':16,'memory_policy':POLICY,'wall_seconds':request['wall_seconds'],'execution_argv':adapter['producer_argv']},
        'plan_reference':adapter['producer_plan_reference'],'root_review_reference':adapter['producer_review_reference'],
        'account_free_bytes':storage['effective_free_bytes'],'effective_free_basis':storage['effective_free_basis'],
        'storage_observation_reference':storage_reference,'storage_observation':storage,
        'scope_key':C.ALPHA_KEY,'stage':C.ALPHA_STAGE,'scope_mode':MODE,'performance_profile':False,
        'bounded_readonly_scope_only':True,'bounded_source_acquisition_scope_only':False,
        'scientific_population_or_full_SQL_status_coverage_accepted':False,'new_UFF_QM_calls_authorized':0,
        'Main_runtime_proof_reused_as_Alpha_startup':False,'once_ledger_or_generation_or_dataset_release_authorized':False}
