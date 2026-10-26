"""Stdlib Main-login candidates/stage inputs; never sign Root reviews or submit."""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,socket,sys
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO))
from workflows.data_v1_final.pprime.causal15_main_v1 import contract as C


def safe(path):
    p=pathlib.Path(path);C.need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'LITERAL_METADATA_FILE')
    C.need(p.suffix in {'.py','.md','.json','.txt','.csv','.sbatch'} and '/run/case-' not in str(p)
        and not any(v in p.parts for v in ('tasks','targets','original_evidence')),'NO_SCIENTIFIC_BODY_READ_ON_LOGIN')
    C.need(p.stat().st_size<=1<<20,'SMALL_METADATA_OR_SOURCE_ONLY');return p


def pin(path):
    p=safe(path)
    with p.open('rb') as f:
        a=os.fstat(f.fileno());raw=f.read((1<<20)+1);b=os.fstat(f.fileno())
    C.need(len(raw)==a.st_size and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'METADATA_CHANGED')
    return {'path':str(p),'bytes':len(raw),'sha256':C.sha(raw)}


def load(path):safe(path);return json.loads(pathlib.Path(path).read_text())
def actual(reference):C.need(pin(reference['path'])==C.triple(reference),'ACTUAL_METADATA_PIN_CHANGED');return load(reference['path'])


def unique(refs):
    result={}
    for ref in refs:
        r=C.triple(ref);C.need(r['path'] not in result or result[r['path']]==r,'CONFLICTING_LOCATORS');result[r['path']]=r
    return list(result.values())


def declared(reference,path_key='path'):
    # Declared original scientific/software payload SHA + current stat only;
    # never read or hash the body here, including small scientific JSON.
    locator=reference[path_key];C.need(type(locator) is str and locator and '\\' not in locator,'ORIGINAL_POSIX_ASSET_LOCATOR_REQUIRED')
    p=pathlib.Path(locator);C.need('..' not in p.parts,'NO_PARENT_TRAVERSAL_IN_DECLARED_ASSET')
    if not p.is_absolute():
        # Frozen engine hashes these original relative assets from PROJECT;
        # central-v2 executes the producer with that exact workdir. Never use
        # this metadata helper's cwd, never rewrite the frozen manifest.
        project=C.RUN.parents[1];p=project/p
        C.need(project in p.parents,'RELATIVE_ASSET_MUST_STAY_WITHIN_ORIGINAL_PROJECT')
    if path_key=='source_path':
        # A pinned manifest expectation for the actual compute filesystem;
        # login-node /usr/lib64 bytes are not evidence for compute-0-13.
        # Frozen execute.initialize_worker still hashes every source asset
        # before invoke. Zero-QM prepare does not prove this compatibility.
        C.need('bytes' in reference,'PINNED_MANIFEST_SOURCE_EXPECTATION_NEEDS_BYTES')
        return C.triple({'path':str(p),'bytes':reference['bytes'],'sha256':reference['sha256']})
    C.need(p.is_file(),'EVERY_ARCHIVED_OR_OTHER_DECLARED_ASSET_MUST_EXIST_NO_SKIP')
    size=p.stat().st_size
    C.need('bytes' not in reference or reference['bytes']==size,'DECLARED_ASSET_STAT_SIZE_MISMATCH')
    return C.triple({'path':str(p),'bytes':reference.get('bytes',size),'sha256':reference['sha256']})


def write(path,value):
    raw=C.canonical(value)+b'\n';C.need(len(raw)<=1<<20,'BOUNDED_METADATA_OUTPUT')
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return pin(path)


def sources():
    refs=[pin(C.HERE/n) for n in C.FILES]+[pin(pathlib.Path(__file__).absolute())]
    formal=C.PPRIME.parent/'conformers/formal_cpu_auto_v3'
    names=('__init__.py','contract.py','runtime_io.py','plan.py','prepare_batch.py','run_batch.py','finalize.py','identity.py','close_index.py','test_contract.py','README.md','frozen_sources.json','root_review_schemas.json')
    refs.extend(pin(formal/n) for n in names);refs.extend(load(formal/'frozen_sources.json')['references'].values())
    refs.extend(pin(C.PPRIME/n) for n in ('common.py','raw_archive.py','cpu_auto_memory_v1/memory.py','vector_audit/math_v1.py','vector_audit/read_outputs_v1.py',
        'vector_audit/evaluate_v1.py','vector_audit/prepare_v1.py','frame_native_precision_diagnosis_v2/raw_reader.py','frame_native_precision_diagnosis_v2/precision.py'))
    return unique(refs)


def resource_refs(path):
    review=load(path);C.need(review['schema']=='SPRIME_MAIN_ACCOUNT_QUOTA_REUSE_ROOT_REVIEW_V3'
        and review['status']=='APPROVED_RESOURCE_FACT_REUSE_ONLY' and review['reviewer']=='root'
        and review['compute_node']=='compute-0-13' and review['uid']==1278,'ACTUAL_ROOT_RESOURCE_FACT_REUSE')
    provider_ref=review['provider_review_reference'];provider=actual(provider_ref)
    refs=[pin(path),provider_ref,*provider['provider_source_references'],*provider['evidence_references'],provider['marker_reference']]
    for key in ('provider_actual_launch_reference','publisher_identity_reference'):
        if review.get(key):refs.append(review[key])
    if review.get('prior_resource_review_reference'):refs.append(review['prior_resource_review_reference'])
    return unique(refs)


def candidate(args,out):
    inventory=actual(C.INVENTORY);audit_ref=pin(C.AUDIT);audit=load(C.AUDIT);pilot_ref=audit['pilot_config'];pilot=actual(pilot_ref)
    contract_ref=pilot['legacy_contract'];contract=actual(contract_ref);protocol_ref=pin(contract['protocol']['path']);protocol=load(protocol_ref['path'])
    C.need(protocol_ref['sha256']==contract['protocol']['sha256'] and protocol['timeout_seconds']==900,'REAL_FROZEN_PROTOCOL900')
    closed_ref=next(C.triple(r['origin']) for r in inventory['entries'] if r['kind']=='small_metadata' and r['origin']['path']==str(C.OLD/'run/run_closed.json'))
    closed=actual(closed_ref);prepared_ref=closed['prepared'];prepared=actual(prepared_ref);membership_ref=prepared['audit_membership'];membership=actual(membership_ref)
    results=[]
    for case_id in [c for pair in C.CASES.values() for c in pair]:
        path=str(C.OLD/'run'/case_id/'result.json');matches=[C.triple(r['origin']) for r in inventory['entries'] if r['kind']=='pinned_case_result_metadata' and r['origin']['path']==path]
        C.need(len(matches)==1 and matches[0] in closed['results'],'KNOWN_ORIGINAL_CLOSED_SIX_RESULT_LOCATORS');results.append(matches[0])
    refs=sources()+[C.INVENTORY,audit_ref,pilot_ref,contract_ref,protocol_ref,closed_ref,prepared_ref,membership_ref,pin(pilot['source_plan']['path'])]
    names={'wp5_engine_v3.py','wp5_parser_v2.py','wp5_parser.py','wp5_parquet_v2.py','wp5_archive_v5.py','wp5_archive_v4.py','wp5_scf_metadata_v2.py','wp5_registry_coverage_v2.py'}
    selected=[r for r in contract['sources'] if pathlib.Path(r['path']).name in names]
    C.need({pathlib.Path(r['path']).name for r in selected}==names and len(selected)==len(names),'EXACT_FROZEN_IMPORTED_ENGINE_MODULES')
    for r in [*selected,*protocol['frozen_dependencies'].values(),protocol['registry']]:
        actual_ref=pin(r['path']);C.need(actual_ref['sha256']==r['sha256'],'FROZEN_SOURCE_CODE_SHA_CHANGED');refs.append(actual_ref)
    pkg_ref=contract['reproduction_package'];pkg=actual(pkg_ref);refs.append(pkg_ref)
    assets=[declared(membership['selected_records'])]
    for asset in pkg['assets']:
        for key in ('source_path','path'):
            if asset.get(key):assets.append(declared(asset,key))
    env_ref=pin(pkg['environment']['path']);C.need(env_ref['sha256']==pkg['environment']['sha256'],'ORIGINAL_ENVIRONMENT_LOCK');refs.append(env_ref)
    env=load(env_ref['path']);assets.append({'path':env['python_executable'],'bytes':pathlib.Path(env['python_executable']).stat().st_size,'sha256':env['python_executable_sha256']})
    account_ref=pin(args.original_accounting);account=load(args.original_accounting)
    C.need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['endpoint']=='202.38.247.57:22' and account['uid']==1278
        and account['query_returncode']==0 and any(str(r['job_id'])=='4521124' for r in account['parents']),'ACTUAL_ORIGINAL4521124_ACCOUNTING_NOT_FUTURE_OR_ASSUMED_C0')
    refs.extend([account_ref,account['raw_sacct_reference'],*resource_refs(args.quota_review)]);refs=unique(refs)
    for r in refs:C.need(pin(r['path'])==C.triple(r),'ACTUAL_SMALL_SOURCE_OR_METADATA_SHA')
    source_paths={r['path'] for r in refs};assets=unique(r for r in assets if r['path'] not in source_paths)
    value={'schema':'ROOT_PPRIME_CAUSAL15_SOURCE_PLAN_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED',
        'proposed_runtime_status':'APPROVED_FIXED6_SOURCE_PREPARATION_NOT_QM','endpoint':'202.38.247.57:22','uid':1278,
        'source_cases':[c for pair in C.CASES.values() for c in pair],'origin_inventory_reference':C.INVENTORY,'audit_config':audit_ref,
        'pilot_config':pilot_ref,'legacy_contract':contract_ref,'protocol':protocol_ref,'audit_membership':membership_ref,
        'original_accounting_reference':account_ref,'original_closed_reference':closed_ref,'case_result_references':results,
        'source_references':refs,'execution_asset_references':assets,'frozen_timeout_seconds':900,
        'execution_asset_verification_context':{
            'manifest_reference':pkg_ref,'source_path_registration':'EXPECTED_COMPUTE_LOCAL_LOCATOR',
            'source_path_expectations':[{'manifest_asset_index':i,'original_manifest_locator':asset['source_path'],
                'reference':declared(asset,'source_path')} for i,asset in enumerate(pkg['assets']) if asset.get('source_path')],
            'relative_locator_base':str(C.RUN.parents[1]),'source_path_login_stat_or_body_verification_claimed':False,
            'archived_asset_path_current_login_stat_size_required':True,'prepare_C0_proves_system_library_compatibility':False,
            'admit_asset_body_hash_claimed':False,
            'actual_validation_stage':'EXECUTE_WORKER_INITIALIZE_BEFORE_INVOKE',
            'frozen_validation_function':'wp5_engine_v3.load_production_metadata',
            'source_and_archive_whole_SHA_validation_remains_mandatory':True,
            'compute_mismatch_behavior':'PRESERVE_CLAIM_AND_ACTUAL_FAILURE_ZERO_QM_NO_AUTOMATIC_RETRY'},
        'timeout_correction':'Earlier prose200 was unverified; actual frozen protocol/default invoke900. No task override, no previously executed QM changed.',
        'fixed_six_transitive_authority':'Only exact original per-call raw SQLite/stat locators and actual input leaves from these six pinned results, checked against fixed origin inventory; no fabricated DB wholeSHA.',
        'original15FAIL_preserved':True,'full_or2000_release':'HOLD','execute_authorized':False}
    result=write(out/'source_plan_candidate.json',value)
    old_quota=load(args.quota_review);quota=dict(old_quota,status='ROOT_REVIEW_REQUIRED',reviewer='UNSIGNED',
        proposed_runtime_status='APPROVED_RESOURCE_FACT_REUSE_ONLY',prior_resource_review_reference=pin(args.quota_review),
        whole_wave_output_reserve_bytes=old_quota['whole_wave_output_reserve_bytes']+2*C.CAP,
        preserved_previous_reserve_bytes=old_quota['whole_wave_output_reserve_bytes'],additional_QA_prepare_execute_caps_bytes=2*C.CAP,
        publisher_started_or_renewed=False)
    print(json.dumps({'source_plan_candidate':result,'quota_candidate':write(out/'quota_candidate.json',quota),'approved':False,'new_jobs':0}))


def stage(args,out):
    plan=load(args.plan);plan_ref=pin(args.plan)
    C.need(plan['status']=='APPROVED_FIXED6_SOURCE_PREPARATION_NOT_QM' and plan['reviewer']=='root','ROOT_INDEPENDENT_APPROVED_SOURCE_PLAN')
    stage=args.stage;sources_refs=unique([*sources(),*plan['source_references'],*resource_refs(args.quota_review),plan_ref]);data=unique([*plan['case_result_references'],*plan['execution_asset_references']])
    argv=[C.PY,'-B',str(C.HERE/(stage+'.py')),'--plan',str(args.plan)];parents=[plan_ref,plan['original_accounting_reference'],pin(args.quota_review)]
    if stage=='execute':
        C.need(args.prepared and args.prepare_accounting and args.execute_review,'ACTUAL_PREPARE_C0_AND_ROOT_EXECUTE_REVIEW_REQUIRED_NO_FUTURE_PINS')
        prepared=load(args.prepared);prepared_ref=pin(args.prepared);account_ref=pin(args.prepare_accounting);account=load(args.prepare_accounting)
        C.need(prepared['status']=='ACTUAL15_EXACT_INPUTS_PREPARED_ZERO_QM' and len(prepared['tasks'])==15 and prepared['plan_reference']==plan_ref,'ACTUAL_SAME_PLAN15_PREPARED')
        C.need(any(str(r['job_id'])==str(prepared['job_id']) and r['state']=='COMPLETED' and r['exit_code']=='0:0' for r in account['parents']),'ACTUAL_PREPARE_C0_ONLY')
        review_ref=pin(args.execute_review);review=load(args.execute_review)
        C.need(review['reviewer']=='root' and review['status']=='APPROVED_EXACT15_QA_AFTER_ACTUAL_PREPARE_C0'
            and review['prepared_reference']==prepared_ref and review['prepare_accounting_reference']==account_ref,'INDEPENDENT_ACTUAL_EXECUTE_APPROVAL')
        sources_refs=unique([*sources_refs,prepared_ref,account_ref,account['raw_sacct_reference'],review_ref]);parents.extend([prepared_ref,account_ref,review_ref])
        for row in prepared['tasks']:data.extend([row['task_reference'],row['original_evidence_reference'],*row['target_input_references']])
        argv.extend(['--prepared',str(args.prepared),'--prepare-accounting',str(args.prepare_accounting),'--execute-review',str(args.execute_review)])
    C.need(C.BASE in args.stage_output.parents and not args.stage_output.exists() and 1200<=args.wall_seconds<=172800,'NEW_OWN_OUTPUT_AND_FINITE_WALL')
    argv.extend(['--root-preflight','__ROOT_STARTUP_PROOF__','--quota-reuse-review',str(args.quota_review),'--output',str(args.stage_output)])
    authority=pin(C.REPO/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json')
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED',
        'resource_authority_reference':authority,'kind':'analysis' if stage=='prepare' else 'qm','scope_key':'pprime_causal15_main_v1_'+stage,
        'scope_parameters':C.parameters(stage),'pilot':False,'wall_seconds':args.wall_seconds,'estimated_peak_output_bytes':C.CAP,
        'stage_output_cap_bytes':C.CAP,'execution_argv':argv,'source_status_stage':None,'scope_mode':'BOUNDED_METADATA_PREPARATION',
        'parent_evidence_references':unique(parents),'root_review_reason':None,'proposed_runtime_status':'APPROVED_FOR_EXACT_STAGE'}
    candidate_ref=write(out/'scope_candidate.json',review)
    spec={key:review[key] for key in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv','source_status_stage')}
    for r in sources_refs:C.need(pin(r['path'])==C.triple(r),'CURRENT_SMALL_SOURCE_PIN')
    data=unique(data);C.need(not({r['path'] for r in sources_refs}&{r['path'] for r in data}),'DISJOINT_DATA_SOURCE')
    spec.update(schema='PPRIME_CAUSAL15_UNSIGNED_STAGE_INPUTS_V1',source_references=sources_refs,data_references=data,cpus=16,
        memory_policy='SLURM_DEFAULT_UNSPECIFIED',scope={'mode':'BOUNDED_METADATA_PREPARATION','review':None,'parent_profile':None},unsigned_scope_candidate_reference=candidate_ref)
    if args.scope_review:
        approved=load(args.scope_review);C.need(approved['status']=='APPROVED_FOR_EXACT_STAGE' and approved['reviewer']=='root','NO_PROXY_ROOT_SIGNING')
        for key in ('schema','resource_authority_reference','kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv','source_status_stage','scope_mode','parent_evidence_references'):
            C.need(approved[key]==review[key],'EXACT_ACTUAL_ROOT_SCOPE_BINDING:'+key)
        rr=pin(args.scope_review);spec['schema']='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1';spec['scope']['review']=rr
        spec['source_references']=unique([*sources_refs,rr]);spec.pop('unsigned_scope_candidate_reference')
    print(json.dumps({'stage_inputs':write(out/('stage_spec.json' if args.scope_review else 'stage_inputs_candidate.json'),spec),'submitted':False}))


def execute_candidate(args,out):
    C.need(args.plan and args.prepared and args.prepare_accounting,'ACTUAL_PREPARE_HEADERS_REQUIRED')
    plan_ref=pin(args.plan);prepared_ref=pin(args.prepared);prepared=load(args.prepared);account_ref=pin(args.prepare_accounting);account=load(args.prepare_accounting)
    C.need(prepared['status']=='ACTUAL15_EXACT_INPUTS_PREPARED_ZERO_QM' and prepared['plan_reference']==plan_ref and len(prepared['tasks'])==15,'ACTUAL_PREPARED15_ONLY')
    C.need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['query_returncode']==0
        and any(str(r['job_id'])==str(prepared['job_id']) and r['state']=='COMPLETED' and r['exit_code']=='0:0' and r['alloc_cpus']==16 for r in account['parents']),
        'EXISTING_STANDARD_PREPARE_C0_HEADER_REQUIRED')
    raw_ref=C.triple(account['raw_sacct_reference']);C.need(pin(raw_ref['path'])==raw_ref,'ACTUAL_RAW_ACCOUNT_PIN')
    value={'schema':'ROOT_PPRIME_CAUSAL15_EXECUTE_REVIEW_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED',
        'proposed_runtime_status':'APPROVED_EXACT15_QA_AFTER_ACTUAL_PREPARE_C0','plan_reference':plan_ref,'prepared_reference':prepared_ref,
        'prepare_accounting_reference':account_ref,'maximum_new_QM_calls':15,'task_timeout_seconds':900,'full_or2000_release':'HOLD',
        'automatic_retry':False,'new_source_references':[pin(C.HERE/n) for n in C.FILES],'Root_reason':None,
        'original15FAIL_preserved':True,'no_production_once_ledger':True,'actual_scientific_quality_PASS_claimed':False}
    print(json.dumps({'execute_review_candidate':write(out/'execute_review_candidate.json',value),'approved':False,'submitted':False}))


def main():
    C.need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','MAIN_LOGIN_STDLIB_METADATA_ONLY')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('candidate','stage','execute-review-candidate'));p.add_argument('--stage',choices=('prepare','execute'))
    for name in ('plan','quota-review','original-accounting','prepared','prepare-accounting','execute-review','scope-review','stage-output','output'):
        p.add_argument('--'+name,type=pathlib.Path,required=name in {'quota-review','output'})
    p.add_argument('--wall-seconds',type=int,default=14400);args=p.parse_args()
    C.need(C.RUN/'control' in args.output.parents and not args.output.exists(),'NEW_METADATA_OUTPUT_NO_OVERWRITE')
    args.output.mkdir(parents=True,exist_ok=False,mode=0o700)
    if args.mode=='candidate':C.need(args.original_accounting is not None,'ACTUAL_ORIGINAL_PARENT_ACCOUNTING');candidate(args,args.output)
    elif args.mode=='execute-review-candidate':execute_candidate(args,args.output)
    else:C.need(args.stage and args.plan and args.stage_output,'EXACT_STAGE_METADATA_OPTIONS');stage(args,args.output)


if __name__=='__main__':main()
