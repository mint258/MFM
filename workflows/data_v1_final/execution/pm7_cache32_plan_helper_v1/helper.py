"""Main login stdlib metadata only: candidates/inputs, never Root-sign or submit."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,os,pathlib,re,socket,stat,sys
RUN=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository'
HERE=pathlib.Path(__file__).absolute().parent;CACHE=REPO/'workflows/data_v1_final/conformers/pm7_independent_cache32_v1'
BASE=RUN/'artifacts/conformers/pm7_independent_cache32_v1';PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
CAP=8<<30;SPRIME_RESERVE=182*CAP;COMBINED_RESERVE=184*CAP
OLD_QUOTA=RUN/'control/sprime_v3_wave2_freeze_stage_v1/quota_reuse_review.json'
MAPPING=RUN/'control/sprime_v3_node13_canonical_source_mount_root_review_v1.json'
GOLD=RUN/'artifacts/conformers/statistics_v1';PROFILE=REPO/'workflows/data_v1_final/conformers/statistics_v1'
SOURCE_HASHES={'__init__.py':'ccdb4df81612bd7a160f0a59d4e6f448dda29c5f758c2feb7eb0e500998c365b',
    'contract.py':'06466779988a394fbfd91f393758b800b7a635ce5c8a3e0a037e899c2cf256c5',
    'inheritance.py':'48c7d3204c00dd50176ca7db7257950ae067409a1c318fa84db58545b553ea3b',
    'io.py':'610182fc7abf09735ef21353d37960ebbc41f21ec2f1eaa62ab85c747793597a',
    'core.py':'910459fa51f5a91a5ccec2025c7d0ee71701c14be236b44ea2dcf68897f1a53e',
    'prepare32.py':'df557023dea2f26892a0cbe572e268e3ba22eb7d58747db7cd8cb40962d9a1a3',
    'run32.py':'28401efacb2ee70c2187e1a96771cdf2373bf9f0b2aae3dddd4f2da69eb50483',
    'test_cache.py':'c08b8681e5fa849571268099a4fc765f0aa55982b30be50d0855536f838637ff',
    'schemas.json':'fa8da3373aa8e163cddf2afd91722a0d45d8602fc5a3bf37a2c0c8b4579a9eb4',
    'README.md':'3c11f9e051a4c90bfb49b418bcc3e52d120043de4c560326adbc345ebf8998d8'}


def need(ok,message):
    if not ok:raise ValueError(message)


def triple(value):
    r={k:value[k] for k in ('path','bytes','sha256')};p=pathlib.Path(r['path'])
    need(p.is_absolute() and '..' not in p.parts and type(r['bytes']) is int and r['bytes']>0
        and re.fullmatch('[0-9a-f]{64}',r['sha256']),'ACTUAL_POSITIVE_LITERAL_REFERENCE_ONLY');return r


def scientific(path):
    p=pathlib.Path(path)
    return p.suffix in {'.parquet','.gz','.jsonl','.lmdb','.mdb','.sqlite','.sqlite3'} or any(x in p.parts for x in ('tasks','molecules','baseline_packets')) or p.name in {'molecule_manifest.json','terminal_outcomes.json','source_files.json','catalog.json','verification_report.json','source_authority.json'}


def raw(path):
    p=pathlib.Path(path);need(p.is_absolute() and '..' not in p.parts and not scientific(p)
        and not any(x.is_symlink() for x in (p,*p.parents)),'SOURCE_OR_SMALL_CONTROL_HEADER_ONLY_NO_SCIENTIFIC_BODY')
    with p.open('rb') as f:
        before=os.fstat(f.fileno());need(stat.S_ISREG(before.st_mode) and before.st_size<=2<<20,'SMALL_METADATA_SOURCE_ONLY')
        body=f.read((2<<20)+1);after=os.fstat(f.fileno())
    need(len(body)==before.st_size and (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'SMALL_METADATA_CHANGED')
    return body


def pin(path):
    body=raw(path);return {'path':str(pathlib.Path(path)),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def load(path):return json.loads(raw(path))


def verify_small(reference):
    need(pin(reference['path'])==triple(reference),'SMALL_METADATA_PIN_CHANGED');return load(reference['path'])


def write(path,value):
    body=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode();need(len(body)<2<<20,'BOUNDED_METADATA_OUTPUT')
    with pathlib.Path(path).open('xb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
    fd=os.open(pathlib.Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return pin(path)


def unique(rows):
    result={}
    for value in rows:
        r=triple(value);need(r['path'] not in result or result[r['path']]==r,'CONFLICTING_REFERENCE_PINS');result[r['path']]=r
    return list(result.values())


def known():
    prep_path=GOLD/'prepared_v1/prepared.json';receipt_path=GOLD/'profile_v1/receipt.json'
    need(pin(prep_path)=={'path':str(prep_path),'bytes':32876,'sha256':'09960a447e2130b48fca6eded17a98b1da0ce5bfc74a922e77db387bb853cca6'}
        and pin(receipt_path)=={'path':str(receipt_path),'bytes':2149,'sha256':'7319dbad1317172ee03f26fd7b5f5721cdbeed0271a57584f4203f408be9009d'},'ORIGINAL_ACTUAL256_METADATA_PINS_CHANGED')
    prep,receipt=load(prep_path),load(receipt_path)
    need(prep['molecules']==receipt['completed_molecules']==256 and receipt['error_molecules']==0
        and receipt['status']=='D7_PROFILE_COMPLETED_NOT_FULL_POPULATION' and receipt['prepared']==pin(prep_path),'REAL_CLOSED256_HEADER_CHAIN')
    manifests=[r for r in receipt['outputs'] if pathlib.Path(r['path']).name=='molecule_manifest.json'];need(len(manifests)==1,'ACTUAL_GOLDEN_MANIFEST_REF_ONLY')
    config=verify_small(prep['config']);per=[r for r in config['metadata_data_pins'] if r['path']==config['per_molecule']]
    need(len(per)==1 and prep['formal_population']['sha256']=='ef2d99ae1b6c1001f6ffeb979ebafd10b04c13fa4774e52527a90a6276c06276','EXACT_CANONICAL_AND_PER_MOLECULE_DECLARED_REFS')
    return {'formal_source':triple(prep['formal_population']),'per_molecule':triple(per[0]),'golden_prepared':pin(prep_path),
        'golden_profile_receipt':pin(receipt_path),'golden_manifest':triple(manifests[0]),'mapping_review':pin(MAPPING)},prep


def scope(stage):
    return {'stage':'PM7_INDEPENDENT_CACHE32_'+stage.upper(),'pilot':False,'molecules':32,'golden':16,'independent':16,
        'maximum_workers':16,'new_UFF_calls':0,'new_QM_calls':0,'no_Sprime_SUCCESS_filter':True,'no_Sprime_anchor':True,
        'source_mother_molecules':1220466,'source_records':11231854,'record_ID_basis':'NATIVE_RECORD_ID',
        'rmsd_A':0.5,'order_seed':20261025,'whole_output_cap_bytes':CAP,'common':False,'full_cache_release':False,
        'future_shard_roster_preparation_only':True,'physical_int64_or_production_release':False,
        'input_authority':'PINNED_CANONICAL_POINTERS_PLUS_PER_RECORD_NATIVE_PAYLOAD_SHA_AND_EXACT_FROZEN_HOF_OWNER','cost_policy':'REPORT_AND_CONTINUE'}


def candidates(args,out):
    refs,prep=known();old=load(OLD_QUOTA)
    need(old['status']=='APPROVED_RESOURCE_FACT_REUSE_ONLY' and old['reviewer']=='root' and old['whole_wave_output_reserve_bytes']==SPRIME_RESERVE,'EXISTING_APPROVED182CAP_RESERVE_REQUIRED')
    quota=dict(old,status='ROOT_REVIEW_REQUIRED',reviewer='UNSIGNED',whole_wave_output_reserve_bytes=COMBINED_RESERVE,
        prior_182cap_review_reference=pin(OLD_QUOTA),preserved_Sprime_reserve_bytes=SPRIME_RESERVE,
        additional_cache_prepare_and_run_caps_bytes=2*CAP,publisher_started_or_renewed=False,
        proposed_runtime_status='APPROVED_RESOURCE_FACT_REUSE_ONLY',root_action='Root independently reviews and writes a new approved resource review; do not overwrite old182cap review.')
    projection_path=RUN/'control/sb3_catalog_projection_v1/projection_receipt.json'
    hof={'schema':'ROOT_PM7_CACHE_CANONICAL_HOF_AUTHORITY_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED',
        'endpoint':'202.38.247.57:22','uid':1278,'proposed_runtime_status':'GEOMETRY_ONLY_HOF_UNVERIFIED' if args.hof_mode=='GEOMETRY_ONLY_UNVERIFIED' else 'VERIFIED_FROZEN_PM7_B_SCALAR_READER',
        'registry_id':60,'unit':'kcal/mol','native_energy_fallback_allowed':False}
    if args.hof_mode=='CANONICAL_VERIFIED':
        projection=load(projection_path);need(projection['status']=='CATALOG_METADATA_PROJECTION_VERIFIED','ACTUAL_HOF_PROJECTION_METADATA_REQUIRED')
        hof.update(latest_owner_reference=triple(prep['latest_owners']),projection_receipt_reference=pin(projection_path),source_files_reference=triple(projection['source_files']))
    plan={'schema':'ROOT_PM7_INDEPENDENT_CACHE32_PLAN_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED',
        'endpoint':'202.38.247.57:22','uid':1278,'molecules':32,'golden':16,'independent':16,'hof_mode':args.hof_mode,
        **refs,'hof_authority_review':None,'full_execution_authorized':False,'common':False,
        'proposed_runtime_status':'APPROVED_BOUNDED32_NOT_FULL',
        'unbound_actual_reference':'Root writes its real approved HOF review first, then inserts its actual SHA triple here. No future hash is generated.'}
    results={'plan_candidate':write(out/'plan_candidate.json',plan),'hof_review_candidate':write(out/'hof_review_candidate.json',hof),
        'quota_review_candidate':write(out/'quota_review_candidate.json',quota),'approved':False,'submitted_jobs':0,
        'existing_Sprime_reserve_bytes':SPRIME_RESERVE,'proposed_total_reserve_bytes':COMBINED_RESERVE}
    print(json.dumps(results,sort_keys=True))


def source_refs(quota_path):
    result=[]
    for name,expected in SOURCE_HASHES.items():
        reference=pin(CACHE/name);need(reference['sha256']==expected,'COPY_FROZEN_PM7_SOURCES_TO_ROOT_FIRST:'+name);result.append(reference)
    formal=REPO/'workflows/data_v1_final/conformers/formal_cpu_auto_v3'
    result.extend(pin(formal/n) for n in ('__init__.py','contract.py','runtime_io.py','plan.py','prepare_batch.py','run_batch.py','finalize.py','identity.py','close_index.py','test_contract.py','README.md','frozen_sources.json','root_review_schemas.json'))
    catalog=load(formal/'frozen_sources.json');result.extend(catalog['references'].values())
    result.extend(pin(PROFILE/n) for n in ('profile_common.py','run_profile.py','prepare_profile.py'))
    result.extend(pin(PROFILE.parent/n) for n in ('common.py','selection.py'))
    mapped=PROFILE.parent/'formal_cpu_auto_prepare_mapping_v1';result.extend(pin(mapped/n) for n in ('__init__.py','mapping.py','prepare_batch.py'))
    # The frozen cache imports these two N1-v4 modules for their read-only IO
    # functions. Binding them adds source integrity, no N1 scientific authority.
    v4=PROFILE.parent/'n1_pprime2_pilot_v4';result.extend(pin(v4/n) for n in ('__init__.py','io.py'))
    result.extend(pin(HERE/n) for n in ('__init__.py','helper.py','README.md'))
    quota=load(quota_path);provider_ref=quota['provider_review_reference'];provider=verify_small(provider_ref)
    result.extend([pin(quota_path),provider_ref,*provider['provider_source_references'],*provider['evidence_references'],provider['marker_reference']])
    if quota.get('provider_actual_launch_reference'):result.append(quota['provider_actual_launch_reference'])
    if quota.get('publisher_identity_reference'):result.append(quota['publisher_identity_reference'])
    for reference in result:need(pin(reference['path'])==triple(reference),'ACTUAL_SMALL_SOURCE_CHANGED')
    return unique(result)


def accounting(path,jid):
    value=load(path);need(value['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and value['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
        and value['query_returncode']==0 and value['uid']==1278 and value['endpoint']=='202.38.247.57:22','REAL_MAIN_PREPARE_ACCOUNTING_REQUIRED')
    r=triple(value['raw_sacct_reference']);need(pin(r['path'])==r,'RAW_SACCT_PIN_CHANGED');actual={}
    rows=csv.DictReader(io.StringIO(raw(r['path']).decode()),delimiter='|')
    need(set(('JobIDRaw','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','UID'))<=set(rows.fieldnames or []),'STANDARD_HEADERED_RAW_SACCT_REQUIRED')
    for row in rows:
        key=row.get('JobIDRaw',row.get('JobID',''))
        if key.isdecimal():need(key not in actual and row['UID']=='1278','UNIQUE_ACTUAL_MAIN_PARENT_ROWS');actual[key]=row
    declared={str(row['job_id']):row for row in value['parents']};need(len(declared)==len(value['parents']) and set(declared)==set(actual) and str(jid) in actual,'EXACT_ALL_PARENT_ACCOUNTING_SET')
    for key,row in declared.items():
        observed=actual[key];need(observed['State'].split()[0]==row['state'] and observed['ExitCode']==row['exit_code']
            and int(observed['AllocCPUS'])==int(row['alloc_cpus'])>=0 and int(observed['ElapsedRaw'])==int(row['elapsed_raw_seconds'])>=0
            and observed['NodeList']==row['node'] and row['state'] in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'},'DECLARED_ACCOUNTING_DIFFERS_FROM_ACTUAL_TERMINAL')
    need(value['allocated_core_seconds']==sum(int(row['alloc_cpus'])*int(row['elapsed_raw_seconds']) for row in declared.values()),'ALL_ACTUAL_PARENT_COSTS_MUST_BE_RETAINED')
    row=declared[str(jid)];need(row['state']=='COMPLETED' and row['exit_code']=='0:0' and int(row['alloc_cpus'])==16 and row['node']=='compute-0-13','ACTUAL_PREPARE_C0_CPU16_NODE13_REQUIRED_NOT_FUTURE_STATUS')
    return pin(path),r


def stage(args,out):
    need(args.plan and args.quota_review and args.stage_output,'ACTUAL_APPROVED_ROOT_PLAN_RESOURCE_AND_NEW_OUTPUT_REQUIRED')
    stage=args.mode;plan=load(args.plan);plan_ref=pin(args.plan);known_refs,_=known()
    need(plan['schema']=='ROOT_PM7_INDEPENDENT_CACHE32_PLAN_V1' and plan['status']=='APPROVED_BOUNDED32_NOT_FULL' and plan['reviewer']=='root'
        and plan['endpoint']=='202.38.247.57:22' and plan['uid']==1278 and plan['hof_mode'] in {'CANONICAL_VERIFIED','GEOMETRY_ONLY_UNVERIFIED'}
        and plan['molecules']==32 and plan['golden']==plan['independent']==16 and plan['common'] is False and plan['full_execution_authorized'] is False
        and all(plan[k]==r for k,r in known_refs.items()),'ONLY_EXISTING_INDEPENDENT_ROOT_APPROVED_EXACT_PLAN')
    hof=verify_small(plan['hof_authority_review']);need(hof['schema']=='ROOT_PM7_CACHE_CANONICAL_HOF_AUTHORITY_V1' and hof['reviewer']=='root'
        and hof['endpoint']=='202.38.247.57:22' and hof['uid']==1278 and hof['status']==('GEOMETRY_ONLY_HOF_UNVERIFIED' if plan['hof_mode']=='GEOMETRY_ONLY_UNVERIFIED' else 'VERIFIED_FROZEN_PM7_B_SCALAR_READER'),'EXISTING_APPROVED_HOF_MODE_REVIEW_REQUIRED')
    quota=load(args.quota_review);need(quota['schema']=='SPRIME_MAIN_ACCOUNT_QUOTA_REUSE_ROOT_REVIEW_V3' and quota['reviewer']=='root' and quota['status']=='APPROVED_RESOURCE_FACT_REUSE_ONLY'
        and quota['endpoint']=='202.38.247.57:22' and quota['uid']==1278 and quota['compute_node']=='compute-0-13'
        and quota['whole_wave_output_reserve_bytes']>=COMBINED_RESERVE,'PRESERVE182CAP_PLUS_PREPARE8G_PLUS_RUN8G_DISK_REVIEW')
    need(BASE in args.stage_output.parents and '..' not in args.stage_output.parts and not args.stage_output.exists()
        and not any(p.is_symlink() for p in (args.stage_output,*args.stage_output.parents)),'LITERAL_NEW_CACHE_OUTPUT_NO_FUTURE_PIN')
    need(1200<=args.wall_seconds<=172800 and args.wall_seconds%60==0,'FINITE_MINUTE_WALL_CEILING_NOT_FORECAST')
    sources=source_refs(args.quota_review)+[plan_ref,plan['mapping_review'],plan['hof_authority_review'],plan['golden_prepared'],plan['golden_profile_receipt'],load(plan['golden_prepared']['path'])['config']]
    mapping=verify_small(plan['mapping_review']);sources.extend(mapping[k] for k in ('formal_source_receipt','prior_cpu_source_validation','same_storage_mapping','quota_provider_review'))
    data=[plan[k] for k in ('formal_source','per_molecule','golden_manifest')]
    if plan['hof_mode']=='CANONICAL_VERIFIED':
        need(hof['registry_id']==60 and hof['unit']=='kcal/mol' and hof['native_energy_fallback_allowed'] is False,'CANONICAL_HOF_UNIT_REGISTRY_AND_NO_NATIVE_FALLBACK')
        sources.append(hof['projection_receipt_reference']);data.append(hof['latest_owner_reference'])
        projection=verify_small(hof['projection_receipt_reference']);data.extend(projection[k] for k in ('catalog','verification','source_files'))
        need(hof['source_files_reference']==projection['source_files'],'REAL_EXACT_HOF_PROJECTION_SOURCE_REF')
    parents=[plan_ref,pin(args.quota_review),plan['mapping_review'],plan['hof_authority_review'],plan['golden_profile_receipt']]
    argv=[PY,'-B',str(CACHE/(stage+'.py')),'--plan',str(args.plan)]
    if stage=='run32':
        need(args.prepared and args.accounting,'FUTURE_RUN_PINS_FORBIDDEN_WAIT_FOR_ACTUAL_PREPARED_C0')
        need(args.prepared.name=='prepared.json' and BASE in args.prepared.parents,'ACTUAL_CACHE_PREPARED_HEADER_ONLY')
        prepared=load(args.prepared);prepared_ref=pin(args.prepared)
        need(prepared['schema']=='PM7_CACHE32_PREPARED_V1' and prepared['status']=='ACTUAL32_FROZEN_NO_GEOMETRY_COMPUTED'
            and prepared['plan_reference']==plan_ref and len(prepared['tasks'])==32,'ACTUAL_SAME_PLAN32_PREPARATION_NOT_A_PREDICTION')
        ar,rr=accounting(args.accounting,prepared['job_id']);sources.extend([prepared_ref,ar,rr]);parents.extend([prepared_ref,ar])
        data.append(prepared['source_authority_reference']);data.extend(row['task_reference'] for row in prepared['tasks']);data.extend(row['reference'] for row in prepared['golden_packet_references'])
        need(len(prepared['golden_packet_references'])==16,'EXACT16_EXISTING_GOLDEN_DATA_REFS')
        argv.extend(['--prepared',str(args.prepared),'--prepare-accounting',str(args.accounting)])
    argv.extend(['--root-preflight','__ROOT_STARTUP_PROOF__','--quota-reuse-review',str(args.quota_review),'--output',str(args.stage_output)])
    authority=pin(REPO/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json')
    proposed={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED',
        'resource_authority_reference':authority,'kind':'analysis','scope_key':'pm7_independent_cache32_v1_'+stage,'scope_parameters':scope(stage),
        'pilot':False,'wall_seconds':args.wall_seconds,'estimated_peak_output_bytes':CAP,'stage_output_cap_bytes':CAP,
        'execution_argv':argv,'source_status_stage':None,'scope_mode':'BOUNDED_METADATA_PREPARATION','parent_evidence_references':unique(parents),
        'root_review_reason':None,'proposed_runtime_status':'APPROVED_FOR_EXACT_STAGE','no_scientific_body_read':True}
    candidate=write(out/'scope_review_candidate.json',proposed);sources=unique(sources);data=unique(data)
    for reference in sources:need(pin(reference['path'])==reference,'CURRENT_SMALL_SOURCE_OR_HEADER_CHANGED')
    need(not({r['path'] for r in sources}&{r['path'] for r in data}),'SCIENTIFIC_DATA_CANNOT_BE_MISCLASSIFIED_AS_SOURCE')
    spec={k:proposed[k] for k in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv','source_status_stage')}
    spec.update(schema='PM7_CACHE32_UNAPPROVED_STAGE_INPUTS_V1',proposed_central_schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',
        cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',source_references=sources,data_references=data,
        scope={'mode':'BOUNDED_METADATA_PREPARATION','review':None,'parent_profile':None},unsigned_scope_candidate_reference=candidate)
    if args.approved_scope_review:
        approved=load(args.approved_scope_review);review_ref=pin(args.approved_scope_review)
        need(approved['schema']==proposed['schema'] and approved['status']=='APPROVED_FOR_EXACT_STAGE' and approved['reviewer']=='root',
            'ONLY_READ_EXISTING_ROOT_APPROVAL_NEVER_SIGN_ON_BEHALF_OF_ROOT')
        for key in ('resource_authority_reference','kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv','source_status_stage','scope_mode','parent_evidence_references'):
            need(approved[key]==proposed[key],'APPROVED_SCOPE_DIFFERS_FROM_ACTUAL_STAGE_INPUT:'+key)
        spec.pop('proposed_central_schema');spec.pop('unsigned_scope_candidate_reference');spec['schema']='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1'
        spec['scope']['review']=review_ref;spec['source_references']=unique([*sources,review_ref])
    result=write(out/('stage_spec.json' if args.approved_scope_review else 'stage_inputs_candidate.json'),spec)
    print(json.dumps({'stage_inputs':result,'root_approved_existing_scope_used':bool(args.approved_scope_review),'new_jobs_submitted':0,'no_scientific_body_read_or_hash':True},sort_keys=True))


def main():
    need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','MAIN_LOGIN_METADATA_ONLY_UID1278')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('candidates','prepare32','run32'));p.add_argument('--output',type=pathlib.Path,required=True)
    p.add_argument('--hof-mode',choices=('GEOMETRY_ONLY_UNVERIFIED','CANONICAL_VERIFIED'),default='GEOMETRY_ONLY_UNVERIFIED')
    for name in ('plan','quota-review','prepared','accounting','stage-output','approved-scope-review'):p.add_argument('--'+name,type=pathlib.Path)
    p.add_argument('--wall-seconds',type=int,default=7200);args=p.parse_args();out=args.output
    need(RUN/'control' in out.parents and '..' not in out.parts and not out.exists() and not any(p.is_symlink() for p in (out,*out.parents)),'NEW_CONTROL_DIRECTORY_NO_OVERWRITE')
    out.mkdir(parents=True,exist_ok=False,mode=0o700)
    if args.mode=='candidates':candidates(args,out)
    else:stage(args,out)


if __name__=='__main__':main()
