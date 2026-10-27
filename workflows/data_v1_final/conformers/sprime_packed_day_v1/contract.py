"""Root authority and immutable original-science metadata; DATA stays declarative."""
import csv,io,pathlib,re
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as F
from workflows.data_v1_final.execution.sprime_wave2_metadata_v1 import generate as G
ROOT=G.ROOT;REPO=G.REPO;PY=G.PY
HERE=REPO/'workflows/data_v1_final/conformers/sprime_packed_day_v1'
FILES=('__init__.py','contract.py','runtime.py','census.py','prepare.py','worker.py','run.py','metadata.py','test_boundaries.py','README.md')
KEY='sprime_packed_day_v1';MODULE='workflows.data_v1_final.conformers.sprime_packed_day_v1.run'
STAGE='SPRIME_ORIGINAL_WAVE2_REMAINDER_PACKED_DAY'
WALL=86400;DRAIN=900
need=F.need;meta=G.metadata;small_pin=G.meta_pin


def unique(refs):return list({r['path']:F.triple(r) for r in refs}.values())


def metadata_ref(ref):
    need(small_pin(ref['path'])==ref,'ACTUAL_SMALL_METADATA_PIN');return G.load(ref['path'])


def packed_account(path,jid,cpus):
    ar,a=meta(path,'DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1');raw=a['raw_sacct_reference']
    need(small_pin(raw['path'])==raw and a['endpoint']=='202.38.247.57:22' and a['uid']==1278 and a['query_returncode']==0,'ACTUAL_PACKED_RAW_ACCOUNTING')
    rows={r['JobIDRaw']:r for r in csv.DictReader(io.StringIO(G.read_small(raw['path']).decode()),delimiter='|') if r['JobIDRaw'].isdecimal()}
    parents={r['job_id']:r for r in a['parents']};need(set(rows)==set(parents) and str(jid) in parents,'REAL_ACCOUNTING_PARENT_SET')
    for key,p in parents.items():
        r=rows[key];need(p['state']==r['State'].split()[0] and p['exit_code']==r['ExitCode'] and p['alloc_cpus']==int(r['AllocCPUS'])
            and p['elapsed_raw_seconds']==int(r['ElapsedRaw']) and p['node']==r['NodeList'] and r['UID']=='1278','EXACT_RAW_ACTUAL_CPUS_ELAPSED_COST')
    p=parents[str(jid)];need(p['alloc_cpus']==cpus and p['state']=='COMPLETED' and p['exit_code']=='0:0'
        and a['allocated_core_seconds']==sum(v['alloc_cpus']*v['elapsed_raw_seconds'] for v in parents.values()),'ACTUAL64_PARENT_C0_NOT_OLD16_PREDICATE')
    return ar,a,p


def parameters(plan):
    return {'original_plan_reference':plan['original_plan_reference'],'inputs_review_reference':plan['inputs_review_reference'],
        'cpus':plan['cpus'],'wall_seconds':WALL,'stop_dispatch_before_wall_seconds':DRAIN,'whole_output_cap_bytes':plan['output_cap_bytes'],
        'one_true_parent_no_child_sbatch_srun_or_child_C0':True,'internal500_checkpoint_is_not_a_Slurm_job':True,
        'original_kernel_seed_graph_stereo_RMSD_and_shared_once':True,'new_QM_calls':0,'ordinary_N1_extra_not_counted':True,
        'root_role_scope':'FROZEN_ORIGINAL_PLAN_ROLES_NO_REASSIGNMENT','source_census_before_any_new_science':True,
        'fresh_quota_age_seconds':120,'quota_reserve_bytes':200000000000,'scientific_retry_or_claim_reset':False}


def sources():
    values=[small_pin(HERE/name) for name in FILES]
    values.extend(small_pin(G.FORMAL/name) for name in ('__init__.py','contract.py','runtime_io.py','plan.py','prepare_batch.py','run_batch.py','close_index.py','frozen_sources.json','root_review_schemas.json'))
    values.extend(F.sources().values())
    values.extend(small_pin(G.MAPPED/name) for name in ('__init__.py','mapping.py','prepare_batch.py'))
    # Direct clock functions are reused; no invented Unix proof field.
    clock=REPO/'workflows/data_v1_final/labels/normalization_compact_runtime_v2'
    values.extend(small_pin(p) for p in clock.glob('*.py'))
    for package in ('cpu_packed_day_v1','cpu_auto_memory_queue_v2','sprime_wave2_metadata_v1'):
        values.extend(small_pin(p) for p in (REPO/'workflows/data_v1_final/execution'/package).glob('*.py'))
    return unique(values)


def reference_shape(ref):
    need(type(ref) is dict and {'path','bytes','sha256'}<=set(ref) and type(ref['bytes']) is int and ref['bytes']>=0
        and type(ref['sha256']) is str and re.fullmatch('[0-9a-f]{64}',ref['sha256']),'EXACT_DECLARED_DATA_LOCATOR')
    p=pathlib.Path(ref['path']);need(p.is_absolute() and '..' not in p.parts,'ABSOLUTE_DATA_LOCATOR');return F.triple(ref)


def input_metadata(plan):
    config=F.config(plan['original_config_reference']);original=metadata_ref(plan['original_plan_reference'])
    review=metadata_ref(plan['inputs_review_reference'])
    need(original['schema']==F.SCHEMAS['plan'] and original['status']=='BOUNDED_WAVE_FROZEN_IMPORTS_CLOSED'
        and original['config']==plan['original_config_reference'] and original['imports320_durably_verified'] is True,
        'ORIGINAL_REAL_FROZEN_PLAN_NOT_A_REPLACEMENT_POPULATION')
    need(review['schema']=='ROOT_REVIEWED_SPRIME_PACKED_INPUTS_V1' and review['status']=='APPROVED_COMPLETE_ORDINARY_SOURCE_INVENTORY'
        and review['reviewer']=='root' and review['frozen_plan_reference']==plan['original_plan_reference']
        and review['original_sprime_manifest_reference']==config['sprime_manifest']
        and review['all_known_ordinary_sources_declared'] is True and review['all_prior_science_parents_terminal'] is True
        and review['ordinary_N1_extra_not_counted'] is True,'ROOT_COMPLETE_EXISTING_SOURCE_INVENTORY_AND_TERMINAL_PARENTS')
    bids=review['candidate_batch_ids'];known={b['batch_id'] for b in original['batches']}
    need(type(bids) is list and bids and len(bids)==len(set(bids)) and set(bids)<=known
        and all(re.fullmatch('batch-00(?:1[1-7][0-9])',b) and 114<=int(b[6:])<=179 for b in bids),'EXACT_ROOT_REMAINDER_DESCRIPTOR_SCOPE_NOT_A_CENSUS_COUNT')
    need(plan['schema']=='SPRIME_PACKED_DAY_PLAN_V1' and type(plan['cpus']) is int and 16<=plan['cpus']<=96
        and plan['wall_seconds']==WALL and plan['stop_dispatch_before_wall_seconds']==DRAIN
        and type(plan['output_cap_bytes']) is int and 8<<30<=plan['output_cap_bytes']<=G.WAVE_RESERVE
        and plan['scope_parameters']==parameters(plan),'EXACT_REAL_CPU_DAY_RESOURCE_BINDING_AND_CARVEOUT_CEILING')
    refs=[plan['original_config_reference'],plan['original_plan_reference'],plan['inputs_review_reference'],plan['source_mapping_review_reference'],
        plan['resource_authority_reference'],plan['quota_provider_review_reference'],plan['quota_provider_identity_reference'],plan['root_carveout_review_reference'],
        original['draft'],original['root_review'],config['sprime_manifest'],review['historical_pilot_review_reference'],config['formal_source_receipt'],
        config['roles_authority'],config['recipe_config']]
    mapping=metadata_ref(plan['source_mapping_review_reference'])
    refs.extend(mapping[k] for k in ('formal_source_receipt','prior_cpu_source_validation','same_storage_mapping','quota_provider_review'))
    metadata_ref(config['sprime_manifest'])
    for row in review['registered_runs']:
        request=metadata_ref(row['request_reference']);sub=metadata_ref(row['submission_reference'])
        need(small_pin(row['accounting_reference']['path'])==row['accounting_reference'],'ACTUAL_ORIGINAL_ACCOUNTING_REFERENCE_PIN')
        ar,av,parents=G.account(row['accounting_reference']['path'],[str(sub['job_id'])])
        argv=request['execution_argv'];formal=argv[:3]==[PY,'-B',str(G.FORMAL/'run_batch.py')]
        legacy=argv[:4]==[PY,'-B','-m','workflows.data_v1_final.conformers.recovery_auto_memory_v1.run_recovery_auto']
        need(sub['request_reference']==row['request_reference'] and sub['request']==request and sub['sbatch_returncode']==0 and sub['uid']==1278
            and (formal or legacy) and request['kind']=='conformer' and request['node'] in {'compute-0-'+str(n) for n in range(11,20)} and request['cpus']==16,
            'ACTUAL_ORIGINAL_REGISTERED_SCIENCE_ROOT_AND_REAL_TERMINAL_ACCOUNT')
        need(argv.count('--output')==1 and (argv.count('--prepared')==1 if formal else argv.count('--plan')==1),'EXACT_OLD_RUN_INPUT_OUTPUT_OPTIONS')
        output=pathlib.Path(request['execution_argv'][request['execution_argv'].index('--output')+1])
        need(ROOT/'artifacts/conformers' in output.parents and '..' not in output.parts,'DECLARED_REGISTERED_TRANSITIVE_OUTPUT_AUTHORITY')
        refs.extend((row['request_reference'],row['submission_reference'],ar,av['raw_sacct_reference']))
    for item in review.get('ordinary_additional_parquet_sources',[]):
        need(item['native_index_domain']=='ORIGINAL_SPRIME_V6','NO_INVENTED_LATE_PHYSICAL_INDEX_MAPPING')
        reference_shape(item['reference']);metadata_ref(item['authority_reference']);refs.append(item['authority_reference'])
    return config,original,review,unique(refs)


def data_locators(plan,config,original,review):
    refs=[original['original_deficits'],original['unsupported'],original['pilot_imports']]
    refs.extend(b['tasks'] for b in original['batches'])
    manifest=metadata_ref(config['sprime_manifest'])
    refs.extend(F.triple(r) for r in manifest['references'] if r['kind'] in ('conformers','molecules'))
    refs.extend(item['reference'] for item in review.get('ordinary_additional_parquet_sources',[]))
    receipt=metadata_ref(config['formal_source_receipt'])
    refs.extend(row['reference'] for row in receipt['outputs'] if row['name']=='formal_population')
    # Prepared task JSONL is scientifically DATA even when tiny; inherit only.
    for row in review['registered_runs']:
        request=metadata_ref(row['request_reference']);argv=request['execution_argv']
        if '--prepared' in argv:
            path=argv[argv.index('--prepared')+1];_,header=meta(path,F.SCHEMAS['prepared']);refs.append(header['tasks'])
    pilot=metadata_ref(review['historical_pilot_review_reference'])
    refs.extend(pilot[k] for k in ('pilot_tasks','terminal_outcomes'))
    for row in review.get('existing_prepared_headers',[]):
        header=metadata_ref(row['prepared_reference']);refs.append(header['tasks'])
    return unique(reference_shape(r) for r in refs)
