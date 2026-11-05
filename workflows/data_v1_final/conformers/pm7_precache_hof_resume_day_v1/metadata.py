"""Stdlib-only Root candidates; scientific JSON/roster/packets are DATA."""
import argparse,copy,csv,hashlib,io,json,os,pathlib,socket,stat
from workflows.data_v1_final.conformers.pm7_precache_day_v1 import metadata as ORIGINAL
RUN=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository'
HERE=REPO/'workflows/data_v1_final/conformers/pm7_precache_hof_resume_day_v1'
KEY='pm7_precache_hof_resume_day_v1';MODULE='workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1.run'
BASE=RUN/'artifacts/conformers/pm7_population_cache_v1/day_v1';FILES=('__init__.py','metadata.py','io.py','run.py','hof_resume.py','worker_context.py','test_boundaries.py','source_origin.json','README.md')
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python';CAP=64<<30;WALL=86400
ANALYSIS_NODES=('compute-0-2','compute-0-8','compute-0-9','compute-0-10','compute-0-11','compute-0-12','compute-0-13','compute-0-14','compute-0-15','compute-0-16','compute-0-17','compute-0-18','compute-0-19')
PLAN='ROOT_PM7_PRECACHE_HOF_RESUME_DAY_PLAN_V1';STATUS='APPROVED_WHOLE_ROSTER_TECHNICAL_CACHE_NOT_COMMON'

def need(ok,message):
    if not ok:raise ValueError(message)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def shape(ref):
    need(type(ref)is dict and set(ref)=={'path','bytes','sha256'} and type(ref['path'])is str and pathlib.Path(ref['path']).is_absolute()
        and '..' not in pathlib.Path(ref['path']).parts and type(ref['bytes'])is int and ref['bytes']>=0
        and type(ref['sha256'])is str and len(ref['sha256'])==64 and all(c in '0123456789abcdef' for c in ref['sha256']),'EXACT_LITERAL_REFERENCE')
    return ref
def small(path):
    path=pathlib.Path(path);need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)),'LITERAL_SMALL_SOURCE')
    with path.open('rb') as f:
        a=os.fstat(f.fileno());need(stat.S_ISREG(a.st_mode) and a.st_uid==1278 and a.st_size<=2<<20,'OWN_SMALL_METADATA_NOT_DATA')
        raw=f.read((2<<20)+1);b=os.fstat(f.fileno())
    need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns) and len(raw)==a.st_size,'SAME_SMALL_SOURCE_EOF')
    return raw,{'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def pin(path):return small(path)[1]
def meta(ref):
    shape(ref);raw,actual=small(ref['path']);need(actual==ref,'ACTUAL_SMALL_PIN');return json.loads(raw)
def unique(refs):
    result={}
    for ref in refs:shape(ref);need(ref['path'] not in result or result[ref['path']]==ref,'CONFLICTING_REFERENCE');result[ref['path']]=ref
    return list(result.values())
def write(path,value):
    raw=canonical(value)+b'\n';path=pathlib.Path(path);fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def parameters(p):
    return {'stage':'PM7_INDEPENDENT_WHOLE_ROSTER_DAY','node':p['node'],'cpus':16,'wall_seconds':WALL,'drain_seconds':900,
        'output_directory':p['output_directory'],'whole_output_cap_bytes':CAP,'population_molecules':1220466,'population_records':11231854,
        'existing_descriptors':247,'base_cache_plan_reference':p['base_cache_plan_reference'],
        'source_mapping_review_reference':p['source_mapping_review_reference'],
        'all_known_cache_parent_review_reference':p['all_known_cache_parent_review_reference'],
        'pilot_priority_review_reference':p.get('pilot_priority_review_reference'),'old_complete_pilot_is_scheduling_only':True,
        'hof_closed_prefix_reuse_review_reference':p['hof_closed_prefix_reuse_review_reference'],
        'original_180_closed_sources_not_reprojected':True,'resume_needed_sources_then_original55k_priority':True,
        'then_frozen_global20k_candidates_minus55k_then_original_remainder':True,
        'full_roster_technical_cache_authorized':True,'old32_permissions_not_rewritten':True,'Common_or_Sprime_predicate':False,
        'original_fixed_native_ID_seed':20261025,'rmsd_A':0.5,'canonical_HOF_registry':60,'native_energy_fallback':False,
        'maximum_workers':16,'persistent_pool':True,'internal_shards_are_not_Slurm_jobs':True,'new_QM_calls':0,'new_UFF_calls':0,
        'full_cache_or_Common_or_D7_release':False,'unknown_cache_claims_are_not_retried':True}
def source_paths():
    paths=[HERE/n for n in FILES]
    for name in ('pm7_population_cache_v1','pm7_independent_cache32_v1','pm7_hof_augmentation32_v1','postprocess_day_v1',
        'pm7_multinode_compat32_v1','formal_cpu_auto_v3','formal_cpu_auto_finalize_mapping_v2','formal_cpu_auto_prepare_mapping_v1',
        'n1_pprime2_pilot_v4','sprime_packed_day_v1'):
        paths.extend(p for p in (HERE.parent/name).iterdir() if p.is_file() and p.suffix in ('.py','.json','.md'))
    for name in ('cpu_auto_memory_queue_v2','queue_v1','cpu_packed_day_v1','cpu_packed_day_v2','cpu_analysis_day_v1'):
        paths.extend(p for p in (REPO/'workflows/data_v1_final/execution'/name).iterdir() if p.is_file() and p.suffix in ('.py','.json','.md'))
    for name in ('pipeline_v1','wire_v1'):
        paths.extend(p for p in (REPO/'workflows/data_v1_final/export'/name).iterdir() if p.is_file() and p.suffix=='.py')
    paths.extend([REPO/'workflows/data_v1_final/execution/finite_quota_observation_guard_v1.py',
        REPO/'workflows/data_v1_final/labels/normalization_compact_runtime_v2/runtime.py',
        REPO/'workflows/data_v1_final/conformers/statistics_v1/profile_common.py'])
    paths.extend(ORIGINAL.source_paths())
    paths.extend(REPO/'workflows/data_v1_final/execution/cpu_analysis_general_nodes_v1'/name for name in ('__init__.py','contract.py','quota_provider.py'))
    paths.extend(REPO/'workflows/data_v1_final/execution/cpu_analysis_cpu19_v1'/name for name in ('__init__.py','contract.py','quota_provider.py'))
    paths.extend(p for p in (REPO/'workflows/data_v1_final/labels/existing_sprime_pilot_day_v1').iterdir()
        if p.is_file() and p.suffix in ('.py','.json','.md'))
    return list(dict.fromkeys(paths))
def registration(entry,kind):
    old_request=meta(entry['request_reference'])
    if old_request.get('scope_key')==ORIGINAL.KEY and str(meta(entry['submission_reference'])['job_id'])=='4524738':
        # This closed receipt is a scientific container, never login metadata.
        # Keep all original request/proof/raw/account checks, defer its contents.
        stripped=dict(entry,receipt_reference=None);row=ORIGINAL.registration(stripped,kind)
        row['entry']=entry;row['receipt_DATA_reference']=entry['receipt_reference'];return row
    if kind=='legacy' or old_request.get('scope_key')==ORIGINAL.KEY:return ORIGINAL.registration(entry,kind)
    req=meta(entry['request_reference']);sub=meta(entry['submission_reference']);account=meta(entry['accounting_reference'])
    jid=str(sub['job_id']);need(sub['request_reference']==entry['request_reference'] and sub['request']==req and sub['sbatch_returncode']==0
        and sub['uid']==1278 and req['cpus']==16 and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and req['kind']=='analysis' and account['endpoint']=='202.38.247.57:22' and account['uid']==1278 and account['query_returncode']==0,
        'REAL_REGISTERED_MAIN_CPU16_CACHE_PARENT')
    raw=account['raw_sacct_reference'];shape(raw);body,actual_raw=small(raw['path']);need(actual_raw==raw,'ACTUAL_RAW_ACCOUNT_PIN')
    raw_rows={r['JobIDRaw']:r for r in csv.DictReader(io.StringIO(body.decode()),delimiter='|') if r['JobIDRaw'].isdecimal()}
    declared={str(r['job_id']):r for r in account['parents']};need(set(raw_rows)==set(declared),'RAW_AND_DECLARED_PARENT_SET')
    for job,row in declared.items():
        r=raw_rows[job];need(r['UID']=='1278' and r['State'].split()[0]==row['state'] and r['ExitCode']==row['exit_code']
            and int(r['AllocCPUS'])==row['alloc_cpus'] and int(r['ElapsedRaw'])==row['elapsed_raw_seconds'] and r['NodeList']==row['node'],
            'EXACT_ACTUAL_RAW_PARENT_COST_STATE_UID_NODE')
    need(account['allocated_core_seconds']==sum(r['alloc_cpus']*r['elapsed_raw_seconds'] for r in declared.values()),'ALL_ACTUAL_PARENT_COSTS_RETAINED')
    parent=next(r for r in account['parents'] if str(r['job_id'])==jid)
    need(parent['state'] in ('COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED')
        and parent['alloc_cpus']==16 and parent['node']==req['node'],'TERMINAL_CACHE_PARENT_ACTUAL_CPU_NODE')
    argv=req['execution_argv']
    if kind=='legacy':need(req['node']=='compute-0-13' and req['scope_key']=='pm7_population_cache_v1_batch' and argv[:3]==[PY,'-B',str(HERE.parent/'pm7_population_cache_v1/run.py')]
        and len(argv)==11 and argv[3::2]==['--plan','--root-preflight','--quota-reuse-review','--output'],'EXACT_LEGACY_PRIMARY_OPTIONS')
    else:need(req['node'] in ANALYSIS_NODES and req['scope_key']==KEY and argv[:4]==[PY,'-B','-m',MODULE] and len(argv)==10 and argv[4::2]==['--plan','--root-preflight','--output'],
        'EXACT_NEW_DAY_PRIMARY_NOT_A_LEGACY_PARENT')
    root=pathlib.Path(argv[-1]);need(RUN/'artifacts/conformers/pm7_population_cache_v1' in root.parents and '..' not in root.parts,'EXACT_REGISTERED_CACHE_ROOT')
    proof_ref=entry.get('proof_reference') or pin(argv[argv.index('--root-preflight')+1]);proof=meta(proof_ref)
    need(proof['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and str(proof['job_id'])==jid
        and proof['uid']==1278 and proof['node']==req['node'] and proof['request_reference']==entry['request_reference']
        and proof['request']==req,'ACTUAL_REGISTERED_PROOF_REQUEST_PARENT_NOT_RECEIPT_ONLY')
    receipt=meta(entry['receipt_reference']) if entry.get('receipt_reference')is not None else None
    if receipt is not None:need(str(receipt['job_id'])==jid and receipt['startup_proof_reference']['path']==argv[argv.index('--root-preflight')+1],
        'RECEIPT_SAME_ACTUAL_PARENT_PROOF')
    return {'entry':entry,'request':req,'submission':sub,'account':account,'actual':parent,'job_id':jid,'root':str(root),'receipt':receipt,'kind':kind,'proof_reference':proof_ref,'proof':proof}
def inputs(p):
    need(p['schema']==PLAN and p['status']==STATUS and p['reviewer']=='root' and p['node'] in ANALYSIS_NODES and p['cpus']==16
        and p['wall_seconds']==WALL and p['output_cap_bytes']==CAP and p['full_roster_technical_cache_authorized']is True
        and p['old32_permissions_not_rewritten']is True and p['common']is False and p['scope_parameters']==parameters(p),'INDEPENDENT_ROOT_WHOLE_ROSTER_PERMISSION')
    base=meta(p['base_cache_plan_reference']);need(base['schema']=='ROOT_PM7_POPULATION_CACHE_BATCH_PLAN_V1'
        and base['status']=='APPROVED_EXACT_WHOLE_MOLECULE_CACHE_BATCH' and base['source_population_molecules']==1220466
        and base['source_population_records']==11231854,'EXISTING_FULL_ROSTER_AUTHORITY_NOT_NEW_SELECTION')
    review=meta(p['all_known_cache_parent_review_reference']);known=[];registered=[]
    need(review['schema']=='ROOT_PM7_PRECACHE_ALL_KNOWN_PARENT_REVIEW_V1' and review['status']=='APPROVED_EXACT_TERMINAL_CACHE_INVENTORY'
        and review['reviewer']=='root' and review['no_unlisted_claim_owner_inference']is True,'ROOT_COMPLETE_KNOWN_CACHE_REGISTRATIONS')
    for key,kind in (('legacy_cache_parents','legacy'),('previous_precache_parents','day')):
        for entry in p[key]:registered.append(registration(entry,kind));known.append(registered[-1]['job_id'])
    need(len(known)==len(set(known)) and set(known)==set(review['registered_cache_producer_job_ids']),'EXACT_REGISTERED_CACHE_PARENT_SET_NO_SUCCESS_ONLY_INVENTORY')
    from workflows.data_v1_final.conformers.pm7_precache_day_v1 import pilot_prepare
    pilot_prepare.policy(p.get('pilot_priority_review_reference'),base)
    hof_reuse(p,registered)
    return base,registered

def hof_reuse(p,registered=None):
    """Pure Root/CPU-QA header only. DB/observations/preselection stay DATA."""
    ref=p['hof_closed_prefix_reuse_review_reference'];v=meta(ref)
    need(v['schema']=='ROOT_FAILED_PM7_HOF_CLOSED_PREFIX_REUSE_V1' and v['status']=='APPROVED_EXACT_CPU_REVALIDATION_NO_OLD_C0'
      and v['reviewer']=='root' and v['original_FAILED_and_reader_complete_false_preserved'] is True
      and v['whole_current_FD_SHA_SQL_source_prefix_and_owner_validation_required'] is True
      and v['no_reprojection_of_closed_sources'] is True and v['no_new_QM_UFF_or_scientific_retry'] is True,
      'EXACT_ROOT_FAILED_HOF_PREFIX_AUTHORITY_NOT_A_C0_CLAIM')
    entry=v['failed_parent_registration'];old=registration(entry,'day');qa=meta(v['actual_CPU_SQL_QA_reference'])
    need(old['job_id']==qa['producer_job_id']=='4524738' and old['actual']['state']=='FAILED'
      and old.get('receipt_DATA_reference')==entry['receipt_reference']==v['failed_receipt_reference'],
      'EXACT_FAILED738_RECEIPT_IS_DECLARED_DATA_NOT_LOGIN_OPENED')
    for key in ('closed_state_reference','observations_reference','failed_receipt_reference'):
        shape(v[key]);need(v[key]['bytes']>0,'POSITIVE_ACTUAL_REUSE_DATA_REFERENCE')
    need(qa['schema']=='ROOT_FAILED738_CLOSED_HOF_SQL_CPU_READBACK_QA_V1'
      and qa['original_reader_complete_flag'] is False and qa['source_status_counts']=={'ORIGINAL_SCALAR_READER_CLOSED':180}
      and qa['source_observations']==qa['observed_source_groups']==180 and qa['needed_owner_source_groups']==184
      and qa['missing_needed_source_groups']==4 and qa['unexpected_source_groups']==0
      and qa['old_FAILED_and_original_flag_unchanged'] is True and qa['new_QM_UFF_calls']==0
      and qa['scientific_IDs_or_values_exported'] is False,'ACTUAL_CLOSED_SQL_QA_COUNTS_NOT_FULL_HOF_ACCEPTANCE')
    need(qa['closed_state_reference']==v['closed_state_reference']
      and qa['observations_reference']==v['observations_reference'],
      'ACTUAL_OLD_PRODUCER_DATA_TRIPLES_NOT_LATE_OR_FUTURE_HASH')
    oldargv=old['request']['execution_argv'];planpath=oldargv[oldargv.index('--plan')+1]
    planrefs=[r for r in old['request']['source_references'] if r['path']==planpath]
    need(len(planrefs)==1,'UNIQUE_ACTUAL_OLD_PLAN_PIN_IN_OLD_PROOF');oldplan=meta(planrefs[0])
    need(oldplan['base_cache_plan_reference']==p['base_cache_plan_reference']
      and oldplan['pilot_priority_review_reference']==p['pilot_priority_review_reference'],
      'SAME_BASE_CANONICAL_HOF_AND_FROZEN55K_PRIORITY')
    from workflows.data_v1_final.conformers.pm7_population_cache_v1 import io as POPIO
    ac=meta(v['actual_CPU_QA_accounting_reference']);jid=str(v['actual_CPU_QA_job_id'])
    parents=POPIO.F.accounting(v['actual_CPU_QA_accounting_reference'],[jid]);actual=parents[jid]
    need(jid=='4525023' and actual['state']=='COMPLETED' and actual['exit_code']=='0:0' and actual['alloc_cpus']==16
      and actual['node'] in ('compute-0-14','compute-0-18'),'ACTUAL_CPU_QA_C0_NOT_FAILED_PRODUCER_C0')
    need(v['actual_CPU_QA_parent_references'],'ACTUAL_CPU_QA_PARENT_CHAIN_REQUIRED')
    for item in v['actual_CPU_QA_parent_references']:need(pin(item['path'])==item,'ACTUAL_QA_SMALL_PARENT_OR_RAW_PIN')
    startup=meta(v['actual_CPU_QA_startup_reference']);receipt=meta(v['actual_CPU_QA_receipt_reference'])
    need(all(ref in v['actual_CPU_QA_parent_references'] for ref in
      (v['actual_CPU_QA_startup_reference'],v['actual_CPU_QA_receipt_reference'],startup['plan_reference'],startup['script_reference']))
      and str(startup['job_id'])==jid and startup['uid']==1278 and startup['node']==actual['node'] and startup['cpus']==16,
      'ACTUAL_ROOT_CPU_QA_STARTUP_PLAN_DRIVER_NOT_FABRICATED_GENERIC_ADMISSION')
    need(receipt['schema']=='ROOT_PENDING_SOURCE_GROUPCHECK_RECEIPT_V1' and receipt['status']=='PASS'
      and str(receipt['actual_job_id'])==jid and receipt['node']==actual['node'] and receipt['cpus']==16
      and [(r['stage'],r['returncode']) for r in receipt['results']]==[('pilot_preflight',0),('closed_parent_diagnostic',0),('repository',0)]
      and receipt['stop'] is None and receipt['new_QM_UFF_calls']==0 and receipt['all_started_subprocesses_drained'] is True,
      'ACTUAL5023_SOURCE_READBACK_REPOSITORY_PASS_NOT_OLD738_C0')
    need(v['allow_only_old_preselection_table_refs_from_this_parent'] is True
      and v['old_output_root']==old['root'] and v['pilot_preselection_locator']==str(pathlib.Path(old['root'])/'pilot_preselection/preselection.json'),
      'EXACT_FINITE_TRANSITIVE_PRESELECTION_TABLE_AUTHORITY')
    if registered is not None:
        matches=[r for r in registered if r['job_id']==old['job_id']]
        need(len(matches)==1 and matches[0]['entry']==entry,'FAILED_HOF_OWNER_EXACT_ENTRY_IN_COMPLETE_PRIOR_CENSUS')
    return v,qa,old
def candidate(request_path,out):
    request_ref=pin(request_path);v=meta(request_ref);need(v['schema']=='ROOT_REQUESTED_PM7_PRECACHE_HOF_RESUME_DAY_V1' and v['requested_by']=='root'
        and v['status']=='REQUESTED_FOR_REVIEW','ROOT_ACTUAL_INPUT_NOT_PROXY_SIGNED')
    base=meta(v['base_cache_plan_reference']);source=[request_ref,v['base_cache_plan_reference'],*v['source_references'],*(pin(path) for path in source_paths())]
    data=[*v['data_references'],*base['data_references']]
    reuse_header=meta(v['hof_closed_prefix_reuse_review_reference'])
    data.append(reuse_header['failed_receipt_reference'])
    # These original scientific containers remain DATA, even if old plans
    # incorrectly put their small locators in a metadata list. Never open them.
    data.extend(base[k] for k in ('population_prepared_reference','geometry32_receipt_reference','hof32_receipt_reference'))
    pure_known=[base[k] for k in ('base_plan_reference','hof_authority_review','population_prepare_accounting_reference','geometry32_accounting_reference','hof32_accounting_reference')]
    source.extend(pure_known);data_paths={r['path'] for r in data}
    for ref in base['metadata_source_references']:
        if ref['path'] in data_paths:data.append(ref)
        elif pathlib.Path(ref['path']).suffix in ('.py','.md') or REPO/'configs' in pathlib.Path(ref['path']).parents or RUN/'control' in pathlib.Path(ref['path']).parents:source.append(ref)
        else:data.append(ref) # Unclassified historical payload is never login-read.
    p={k:copy.deepcopy(v[k]) for k in ('base_cache_plan_reference','legacy_cache_parents','previous_precache_parents','all_known_cache_parent_review_reference',
        'provider_review_reference','provider_identity_reference','provider_launch_reference','resource_carveout_reference','source_mapping_review_reference','node','output_directory')}
    p['pilot_priority_review_reference']=copy.deepcopy(v.get('pilot_priority_review_reference'))
    p['hof_closed_prefix_reuse_review_reference']=copy.deepcopy(v['hof_closed_prefix_reuse_review_reference'])
    from workflows.data_v1_final.conformers.pm7_precache_day_v1 import pilot_prepare
    _,priority_source,priority_data=pilot_prepare.policy(p['pilot_priority_review_reference'],base)
    source.extend(priority_source);data.extend(priority_data)
    p.update(schema=PLAN,status='ROOT_REVIEW_REQUIRED',reviewer=None,cpus=16,wall_seconds=WALL,output_cap_bytes=CAP,
        full_roster_technical_cache_authorized=True,old32_permissions_not_rewritten=True,common=False)
    for key in ('all_known_cache_parent_review_reference','provider_review_reference','provider_identity_reference','provider_launch_reference','resource_carveout_reference','source_mapping_review_reference'):source.append(p[key])
    provider=meta(p['provider_review_reference']);source.extend([*provider['provider_source_references'],*provider['evidence_references'],provider['marker_reference'],provider['count_correction_authority_reference']])
    mapping=meta(p['source_mapping_review_reference']);source.extend(mapping[k] for k in ('historical_node13_source_mapping_reference','formal_source_receipt','prior_cpu_source_validation','same_storage_mapping','quota_provider_review'))
    for key in ('population_prepare_accounting_reference','geometry32_accounting_reference','hof32_accounting_reference'):
        a=meta(base[key]);source.append(a['raw_sacct_reference'])
    for key,kind in (('legacy_cache_parents','legacy'),('previous_precache_parents','day')):
        for entry in p[key]:
            row=registration(entry,kind);source.extend(ref for ref in entry.values() if type(ref)is dict and set(ref)=={'path','bytes','sha256'}
                and ref!=reuse_header['failed_receipt_reference'])
            source.extend([row['account']['raw_sacct_reference'],row['proof_reference']]);data.extend(row['request']['data_references'])
            for ref in row['request']['source_references']:
                if ref['path'] in data_paths:data.append(ref)
                elif pathlib.Path(ref['path']).suffix in ('.py','.md') or REPO/'configs' in pathlib.Path(ref['path']).parents or RUN/'control' in pathlib.Path(ref['path']).parents:source.append(ref)
                else:data.append(ref)
            if row['receipt']is not None:
                data.extend(row['receipt'][key] for key in ('catalog_reference',) if row['receipt'].get(key)is not None)
                data.extend(row['receipt'].get('catalog_part_references',[]))
                data.extend(row['receipt'][key] for key in ('closed_state_reference','hof_projection_reference') if row['receipt'].get(key)is not None)
    p['cache_registered_parents']=[entry for entry in p['legacy_cache_parents'] if (lambda row:row['receipt']is not None
        and row['actual']['state']=='COMPLETED' and row['actual']['exit_code']=='0:0'
        and row['receipt']['unknown_molecules']==row['receipt']['unstarted_molecules']==0)(registration(entry,'legacy'))]
    reuse,qa,origin=hof_reuse(p)
    source.extend([p['hof_closed_prefix_reuse_review_reference'],reuse['actual_CPU_SQL_QA_reference'],
      reuse['actual_CPU_QA_accounting_reference'],*reuse['actual_CPU_QA_parent_references']])
    source.append(meta(reuse['actual_CPU_QA_accounting_reference'])['raw_sacct_reference'])
    data.extend(reuse[k] for k in ('closed_state_reference','observations_reference','failed_receipt_reference'))
    p['scope_parameters']=parameters(p);p['source_references']=unique(source);p['data_references']=unique(data)
    declared_source_paths={str(path) for path in source_paths()}
    p['data_references']=[r for r in p['data_references'] if r['path'] not in declared_source_paths]
    data_paths={r['path'] for r in p['data_references']};p['source_references']=[r for r in p['source_references'] if r['path'] not in data_paths]
    for ref in p['source_references']:need(pin(ref['path'])==ref,'CURRENT_SOURCE_OR_DECLARED_SMALL_CONTROL')
    return write(out/'plan_candidate.json',p)
def stage(plan_path,out,scope_review=None):
    plan_ref=pin(plan_path);p=meta(plan_ref);base,_=inputs(p);argv=[PY,'-B','-m',MODULE,'--plan',str(plan_path),'--root-preflight','__ROOT_STARTUP_PROOF__','--output',p['output_directory']]
    authority=pin(REPO/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json')
    parents=[p['base_cache_plan_reference'],p['all_known_cache_parent_review_reference'],p['resource_carveout_reference'],
        base['population_prepare_accounting_reference'],base['geometry32_accounting_reference'],base['hof32_accounting_reference']]
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':None,
        'resource_authority_reference':authority,'kind':'analysis','scope_key':KEY,'scope_parameters':parameters(p),'pilot':False,'wall_seconds':WALL,
        'estimated_peak_output_bytes':CAP,'stage_output_cap_bytes':CAP,'execution_argv':argv,'source_status_stage':None,
        'scope_mode':'BOUNDED_METADATA_PREPARATION','parent_evidence_references':unique(parents),'root_review_reason':None}
    source=unique([*p['source_references'],plan_ref]);data=p['data_references'];template=write(out/'scope_candidate.json',review)
    spec={k:review[k] for k in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv','source_status_stage')}
    spec.update(schema='UNSIGNED_PM7_PRECACHE_DAY_STAGE_INPUTS_V1',cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',source_references=source,data_references=data,
        scope={'mode':'BOUNDED_METADATA_PREPARATION','review':None,'parent_profile':None},unsigned_scope_candidate_reference=template)
    if scope_review is not None:
        ref=pin(scope_review);approved=meta(ref)
        for key,value in review.items():
            if key not in ('status','reviewer','root_review_reason'):need(approved[key]==value,'EXACT_SCOPE_FIELD:'+key)
        need(approved['status']=='APPROVED_FOR_EXACT_STAGE' and approved['reviewer']=='root' and approved['root_review_reason'],'INDEPENDENT_ROOT_SCOPE_REVIEW')
        spec.update(schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1');spec['scope']['review']=ref;spec['source_references']=unique([*source,ref]);spec.pop('unsigned_scope_candidate_reference')
    return write(out/('stage_spec.json' if scope_review else 'stage_inputs_candidate.json'),spec)
def close(entry_path,out):
    entry_ref=pin(entry_path);entry=meta(entry_ref);origin=registration(entry,'day');r=origin['receipt']
    need(origin['actual']['state']=='COMPLETED' and origin['actual']['exit_code']=='0:0' and r is not None
        and r['schema']=='PM7_PRECACHE_DAY_RECEIPT_V1' and r['status'] in ('ACTUAL_DAY_DURABLE_PARTIAL_PREFIX_NOT_FULL','FULL_ROSTER_TECHNICAL_CACHE_ROOT_REVIEW_REQUIRED')
        and not r['unknown'] and r['fatal']is None,'ACTUAL_C0_VALIDATED_PREFIX_NOT_SOURCE_ONLY_OR_FAILED')
    return write(out/'prefix_acceptance_candidate.json',{'schema':'ROOT_ACCEPTED_PM7_PRECACHE_DAY_PREFIX_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':None,
        'proposed_runtime_status':'ACTUAL_C0_READONLY_CACHE_PREFIX_ACCEPTED_NOT_COMMON','registration_reference':entry_ref,
        'request_reference':entry['request_reference'],'submission_reference':entry['submission_reference'],'accounting_reference':entry['accounting_reference'],
        'raw_accounting_reference':origin['account']['raw_sacct_reference'],'receipt_reference':entry['receipt_reference'],'proof_reference':origin['proof_reference'],
        'job_id':origin['job_id'],'catalog_part_references':r['catalog_part_references'],'closed_state_reference':r['closed_state_reference'],
        'common_or_final_D7_or_physical_ID_release':False,'root_reason':None})
def pilot_policy_candidate(config_path,out):
    from workflows.data_v1_final.conformers.pm7_precache_day_v1 import pilot_prepare as P
    reference=pin(config_path);config=meta(reference);roles=meta(config['roles_authority'])
    need(config['schema']=='DATA_V1_SPRIME_FORMAL_CPU_AUTO_V3','ORIGINAL_BASELINE_SOURCE_CONFIG')
    # Only original declared manifests: no scientific role/geometry/task body.
    meta(config['sprime_manifest']);meta(roles['source_role_manifest'])
    return write(out/'pilot_priority_policy.UNSIGNED.json',{'schema':P.POLICY,'status':'ROOT_REVIEW_REQUIRED','reviewer':None,
        'original_config_reference':reference,'old_sprime_manifest_reference':config['sprime_manifest'],
        'roles_authority_reference':config['roles_authority'],'old_complete_Sprime_acceptance_reference':None,
        'evidence_references':[config['formal_source_receipt'],roles['actual_closure']],
        'seed':20261025,'nested_train_counts':list(P.SIZES),'pilot_train':50000,'pilot_val':5000,
        'strict_usable_counts_from_original_accepted_audit':True,'old_geometry_and_records_not_replaced':True,
        'scheduling_priority_only':True,'full_Common_or_D4_D5_D3_release':False,'root_reason':None})

def main():
    need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','MAIN_LOGIN_SMALL_METADATA_ONLY')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('candidate','stage','close','pilot-policy'))
    for name in ('request','plan','scope-review','registration','baseline-config','output'):parser.add_argument('--'+name,type=pathlib.Path,required=name=='output')
    a=parser.parse_args();need(RUN/'control' in a.output.parents and not a.output.exists() and '..' not in a.output.parts,'FRESH_CONTROL_DIRECTORY');a.output.mkdir(mode=0o700,parents=True)
    print(pilot_policy_candidate(a.baseline_config,a.output) if a.action=='pilot-policy' else (candidate(a.request,a.output) if a.action=='candidate' else (close(a.registration,a.output) if a.action=='close' else stage(a.plan,a.output,a.scope_review))))
if __name__=='__main__':main()
