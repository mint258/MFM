"""Metadata contracts; no DATA body is opened by draft/finalize helpers."""
import pathlib,re
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as F
from workflows.data_v1_final.execution.sprime_wave2_metadata_v1 import generate as G
from workflows.data_v1_final.conformers.sprime_packed_day_v1 import contract as PACK
ROOT=G.ROOT;REPO=G.REPO;PY=G.PY;HERE=REPO/'workflows/data_v1_final/conformers/postprocess_day_v1'
KEY='conformers_postprocess_day_v1';MODULE='workflows.data_v1_final.conformers.postprocess_day_v1.run'
FILES=('__init__.py','contract.py','io.py','closure.py','common.py','math_bridge.py','hof.py','cache.py','worker.py','statistics.py','run.py','metadata.py','source_inverse.py','test_boundaries.py','README.md')
WALL=86400;DRAIN=900;need=F.need;canonical=F.canonical;q=F.q

def unique(refs):
    out={}
    for r in refs:
        r=F.triple(r);need(r['path'] not in out or out[r['path']]==r,'CONFLICTING_DECLARED_SOURCE_OR_DATA_TRIPLES');out[r['path']]=r
    return list(out.values())
def meta(ref):
    need(G.meta_pin(ref['path'])==F.triple(ref),'EXACT_ACTUAL_SMALL_PARENT_PIN');return G.load(ref['path'])
def parameters(p):
    return {'stage':'COMMON_AND_PM7_SPRIME_STATISTICS_PACKED_DAY','original_config_reference':p['original_config_reference'],
      'packed_receipt_reference':p['packed_receipt_reference'],'cpus':p['cpus'],'node':p['node'],'wall_seconds':WALL,'natural_drain_seconds':DRAIN,
      'whole_output_cap_bytes':p['output_cap_bytes'],'new_QM_calls':0,'new_UFF_calls':0,'new_child_Slurm_jobs':0,
      'PM7_population_molecules':1220466,'PM7_population_records':11231854,'original_supported_deficits':90069,'original_unsupported':9282,
      'fixed_random_seed':20261025,'dedup_threshold_A':0.5,'canonical_HOF_registry':60,'native_energy_is_not_HOF':True,
      'common_conditions':['S','Sprime','P','Pprime','D'],'root_final_release_after_actual_parent_C0':True,
      'original_N1_extras_kept_in_separate_domain':True,'no_scientific_retry_or_once_reset':True}
def sources():
    refs=[G.meta_pin(HERE/n) for n in FILES]
    refs.extend(PACK.sources())
    for package in ('formal_cpu_auto_finalize_mapping_v2','pm7_independent_cache32_v1','pm7_population_cache_v1','pm7_hof_augmentation32_v1','pm7_multinode_compat32_v1'):
        refs.extend(G.meta_pin(p) for p in (HERE.parent/package).glob('*.py'))
    from workflows.data_v1_final.execution.cpu_analysis_day_v1 import contract as Resource
    refs.extend(G.meta_pin(Resource.HERE/n) for n in Resource.FILES)
    return unique(refs)
def inputs(p):
    need(p['schema']=='CONFORMERS_POSTPROCESS_DAY_PLAN_V1' and p['wall_seconds']==WALL and p['drain_seconds']==DRAIN
      and type(p['cpus']) is int and p['cpus']>=16 and p['node'] in ('compute-0-14','compute-0-18')
      and type(p['output_cap_bytes']) is int and p['output_cap_bytes']>=8<<30 and p['scope_parameters']==parameters(p),'ONE_TRUE_ANALYSIS_DAY_PLAN')
    need(all(type(p[k]) is int and p[k]>0 for k in ('algorithm_rss_soft_cap_bytes','minimum_MemAvailable_bytes','exact_quantile_memory_bound_bytes')),'EXPLICIT_POSITIVE_SOFTWARE_RESOURCE_BOUNDS')
    value=F.config(p['original_config_reference']);receipt=meta(p['packed_receipt_reference']);packed=meta(receipt['plan_reference'])
    need(receipt['schema']=='SPRIME_PACKED_DAY_RECEIPT_V1' and receipt['actual_single_parent_job_id']==str(p['packed_parent_job_id'])
      and receipt['all_started_native_tasks_drained'] is True and receipt['child_Slurm_jobs_created']==0
      and receipt['allocated_cpus']==packed['cpus']==64 and packed['original_config_reference']==p['original_config_reference'],
      'REAL_DRAINED_PACKED64_PRODUCER_NOT_FUTURE_OR_OLD16')
    ar,av,row=PACK.packed_account(p['packed_accounting_reference']['path'],p['packed_parent_job_id'],64)
    need(ar==p['packed_accounting_reference'] and row['node']=='compute-0-13','PINNED_ACTUAL_PACKED64_C0_ACCOUNT')
    packed_proof=meta(receipt['startup_proof_reference']);pre=meta(receipt['preflight_reference'])
    need(str(packed_proof['job_id'])==receipt['actual_single_parent_job_id'] and packed_proof['request']['producer_plan_reference']==receipt['plan_reference']
      and packed_proof['request']['scope_key']=='sprime_packed_day_v1' and packed_proof['request']['cpus']==64 and packed_proof['request']['node']=='compute-0-13'
      and pre['tests_run']==9 and pre['failures']==pre['errors']==pre['skips']==pre['expected_failures']==pre['unexpected_successes']==0,'REAL_PACKED64_C0_PROOF_AND_ACTUAL9_PREFLIGHT')
    prior=meta(packed['inputs_review_reference']);original=meta(packed['original_plan_reference']);cache=meta(p['cache_plan_reference'])
    need(cache['schema']=='ROOT_PM7_POPULATION_CACHE_BATCH_PLAN_V1' and cache['status']=='APPROVED_EXACT_WHOLE_MOLECULE_CACHE_BATCH'
      and cache['source_population_molecules']==1220466 and cache['source_population_records']==11231854,'REAL_FULL_PM7_ROSTER_AUTHORITY_NOT_COMMON_FILTER')
    formal_receipt=meta(value['formal_source_receipt']);formal=[r['reference'] for r in formal_receipt['outputs'] if r['name']=='formal_population']
    need(formal_receipt['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED' and len(formal)==1 and cache['formal_source']==formal[0]
      and cache['per_molecule']==value['per_molecule'],'SAME_ORIGINAL_FORMAL_PM7_AND_PER_MOLECULE_AUTHORITY_FOR_ALL_CONDITIONS')
    cost=meta(p['related_parent_review_reference'])
    need(cost['schema']=='ROOT_CONFORMERS_POSTPROCESS_COMPLETE_PARENT_REVIEW_V1' and cost['status']=='APPROVED_ALL_KNOWN_TERMINAL_PARENTS'
      and cost['reviewer']=='root' and cost['complete_owned_master_reviewed'] is True and cost['all_related_known_terminal_parents_included'] is True,
      'ROOT_COMPLETE_COST_CLASSIFICATION_NOT_PARENT_NAME_INFERENCE')
    refs=[p[k] for k in ('original_config_reference','packed_receipt_reference','packed_accounting_reference','cache_plan_reference',
      'related_parent_review_reference','resource_authority_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')]
    refs.extend([receipt['plan_reference'],receipt['startup_proof_reference'],av['raw_sacct_reference'],packed['inputs_review_reference'],packed['original_plan_reference']])
    refs.extend(cost['accounting_references']);refs.append(cost['owned_master_reference'])
    refs.extend(PACK.input_metadata(packed)[3]);refs.extend(cache['metadata_source_references'])
    refs.extend([cache['population_prepared_reference'],cache['base_plan_reference'],cache['hof_authority_review'],cache['future_shards_reference'],cache['geometry32_receipt_reference'],cache['hof32_receipt_reference']])
    roles=meta(value['roles_authority']);role_manifest=meta(roles['source_role_manifest']);refs.extend([value['roles_authority'],roles['source_role_manifest']])
    data=PACK.data_locators(packed,value,original,prior)+cache['data_references']+[receipt['resolution_index_reference'],receipt['complete_errors_reference']]
    data.extend(F.triple(r) for r in role_manifest['outputs'] if '/molecule_roles/' in r['path'])
    for registered in p['cache_registered_parents']:
        req=meta(registered['request_reference']);sub=meta(registered['submission_reference']);acc=meta(registered['accounting_reference'])
        need(sub['request_reference']==registered['request_reference'] and sub['request']==req and sub['sbatch_returncode']==0
          and req['scope_key']=='pm7_population_cache_v1_batch' and req['cpus']==16 and acc['query_returncode']==0,'ACTUAL_REGISTERED_PRIOR_PM7_CACHE')
        refs.extend(registered.values());refs.append(acc['raw_sacct_reference']);refs.extend(req['source_references']);data.extend(req['data_references'])
        rr=meta(registered['receipt_reference']);argv=req['execution_argv']
        need(rr['job_id']==str(sub['job_id']) and argv[:3]==[PY,'-B',str(HERE.parent/'pm7_population_cache_v1/run.py')]
          and len(argv)==11 and argv[3::2]==['--plan','--root-preflight','--quota-reuse-review','--output']
          and rr['plan_reference']['path']==argv[4] and rr['startup_proof_reference']['path']==argv[6]
          and rr['catalog_reference']['path']==str(pathlib.Path(argv[-1])/'molecule_catalog.jsonl.gz'),'REAL_CACHE_RECEIPT_FULL_PRIMARY_AND_FIXED_OUTPUT_CHAIN')
        data.append(rr['catalog_reference'])
    for previous in p.get('previous_postprocess_parents',[]):
        req=meta(previous['request_reference']);sub=meta(previous['submission_reference']);rr=meta(previous['receipt_reference'])
        need(sub['request_reference']==previous['request_reference'] and sub['request']==req and sub['sbatch_returncode']==0
          and req['scope_key']==KEY and req['producer_plan_reference']==rr['plan_reference'],'REAL_PREVIOUS_SAME_SOURCE_ANALYSIS_DAY_REGISTRATION')
        need(G.meta_pin(previous['accounting_reference']['path'])==previous['accounting_reference'],'ACTUAL_PREVIOUS_DAY_ACCOUNTING_PIN')
        _,av,parents=G.account(previous['accounting_reference']['path'],[str(sub['job_id'])]);pr=parents[str(sub['job_id'])]
        need(pr['state']=='COMPLETED' and pr['exit_code']=='0:0' and pr['alloc_cpus']==req['cpus'] and pr['node']==req['node'] and rr['job_id']==str(sub['job_id'])
          and rr['schema']=='CONFORMERS_POSTPROCESS_DAY_RECEIPT_V1','ACTUAL_TECHNICAL_DAY_C0_FOR_SAFE_PREFIX_ADOPTION')
        argv=req['execution_argv'];need(argv[:4]==[PY,'-B','-m',MODULE] and len(argv)==8 and argv[4]=='--plan' and argv[6]=='--startup-proof'
          and argv[5]==rr['plan_reference']['path'] and argv[7]==rr['startup_proof_reference']['path'],'PREVIOUS_DAY_EXACT_MODULE_AND_ORDERED_OPTIONS')
        declared={r['path']:r for r in req['source_references']}
        need(all(declared.get(r['path'])==r for r in sources()),'PREVIOUS_DAY_EXACT_UNCHANGED_SOURCE_BYTES')
        refs.extend(previous.values());refs.append(av['raw_sacct_reference']);data.append(rr['catalog_reference'])
    return value,receipt,packed,original,prior,cache,unique(refs),unique(data)
