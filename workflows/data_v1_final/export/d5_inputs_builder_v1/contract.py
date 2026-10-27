"""Actual ordinary-source parents, explicit bounded stages and no future DATA."""
from __future__ import annotations
from pathlib import Path
from workflows.data_v1_final.export.d5_materialize_cpu_v1 import contract as D
Q=D.Q;ROOT=D.ROOT;REPO=D.REPO;PY=D.PY;need=D.need;meta=D.meta;reference=D.reference;unique=D.unique
HERE=REPO/'workflows/data_v1_final/export/d5_inputs_builder_v1'
MODULE='workflows.data_v1_final.export.d5_inputs_builder_v1.run'
FILES=('__init__.py','contract.py','metadata.py','io.py','prepare.py','reader.py','geometry.py','children.py','build.py','verify.py','run.py','test_v1.py','frozen_sources.json','README.md')
MODES=('prepare','base','merge','verify','final')
OUTPUT=ROOT/'artifacts/labels/source_status_v1/d5_inputs_builder_v1';ORDER_SEED=20261025;BATCH=512;MAX_PARENTS=32
COMMON_KEYS=('common_closure_references','hof_authority_reference','ordinary_source_review_reference','ordinary_N1_preparation_policy_reference')


def parameters(plan):
    return {'mode':plan['mode'],'purpose':plan['purpose'],'order_seed':ORDER_SEED,'workers':16,'pending':32,
        'logical_range':plan.get('logical_range'),'maximum_batch_molecules':BATCH,'maximum_merge_parents':MAX_PARENTS,
        'logical_partition_molecules':plan['logical_partition_molecules'],
        'original_selection_rmsd_seed_objects':True,'original_PM7_payload_reader':True,'new_QM_UFF_calls':0,
        'all_actual_direct_children_required_for_final':True,'N1_parent_collection_is_child':False,
        'three_boundaries_before_DATA':True,'whole_output_cap_bytes':plan['output_cap_bytes'],'wall_seconds':plan['wall_seconds'],
        'D5_jointly_frozen':False,'cost_policy':'REPORT_AND_CONTINUE'}


def source_check():
    value=Q.load(HERE/'frozen_sources.json')
    need(value['schema']=='D5_INPUT_BUILDER_ORIGINAL_SOURCE_BINDINGS_V1','EXACT_SOURCE_BOUNDARIES')
    for ref in value['references'].values():need(Q.pin(ref['path'])==ref,'UNCHANGED_ORIGINAL_SOURCE:'+ref['path'])
    D.original_source_check();return value['references']


def source_paths():
    refs=source_check()
    return sorted(set([*(HERE/n for n in FILES),*D.source_paths(),*(Path(r['path']) for r in refs.values())]))


def limits(plan):
    need(plan['mode'] in MODES and plan['purpose'] in ('pilot512','full','technical'), 'EXACT_STAGE_AND_PURPOSE')
    need(type(plan['wall_seconds']) is int and 600<=plan['wall_seconds']<=172800
        and type(plan['output_cap_bytes']) is int and 32<<30<=plan['output_cap_bytes']<=1<<40,
        'ROOT_EXPLICIT_FINITE_MAX48H_AND_OUTPUT_CAP_WITH16GIB_DRAIN_RESERVE')
    need(plan['order_seed']==ORDER_SEED,'ORIGINAL_ORDER_SEED_NO_NEW_DEFAULT')
    need(type(plan['logical_partition_molecules']) is int and 1<=plan['logical_partition_molecules']<=BATCH,
        'EXPLICIT_FIXED_LOGICAL_PARTITION_BEFORE_CPU_NOT_WORKER_DEPENDENT')
    if plan['mode']!='prepare':
        lo,hi=plan['logical_range'];need(type(lo) is type(hi) is int and 0<=lo<hi,'EXACT_NONEMPTY_LOGICAL_INTERVAL')
        if plan['purpose']!='full':need(hi-lo<=BATCH,'NONFULL_TECHNICAL_OR_PILOT_CANNOT_BYPASS512_TO_FULL_GATE')


def common(plan):
    m,refs=D.common_parent(plan['common_closure_references'])
    review=meta(plan['ordinary_source_review_reference']);policy=meta(plan['ordinary_N1_preparation_policy_reference'])
    for value in (review,policy):
        need(value['reviewer']=='root' and value['common_manifest_reference']==plan['common_closure_references']['manifest'],
            'INDEPENDENT_SAME_ACTUAL_COMMON_ORDINARY_REVIEW')
    need(review['schema']=='ROOT_D5_ORDINARY_BASE_SOURCE_REVIEW_V1'
        and review['status']=='ROOT_REVIEWED_EXACT_ORDINARY_BASE_SOURCES'
        and review['ordinary_physical_tables']==m['physical_geometry_tables']
        and review['no_N1_extras_or_perturbed_children_in_ordinary_bases'] is True
        and review['finalizer_actual_source_and_attempt_chains_reviewed'] is True,'ACTUAL_ORDINARY_SOURCE_CHAIN_NOT_N1_OR_LABEL_SUCCESS_FILTER')
    need(policy['schema']=='ROOT_D5_ORDINARY_N1_PREPARATION_POLICY_V1'
        and policy['status']=='ROOT_REVIEWED_ORDINARY_N1_INPUT_PREPARATION_ONLY'
        and policy['ordinary_counts_unchanged'] is True and policy['N1_less_than_two_remains_pending'] is True
        and policy['Pprime_generation_or_QM_authorized'] is False,'N1_PREPARATION_SCOPE_NOT_FINAL_N1_EXTRA_AUTHORITY')
    formal=meta(m['formal_population_authority_receipt']);rows=[r for r in formal['outputs'] if r['name']=='formal_population']
    need(formal['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED' and len(rows)==1,'EXACT_CLOSED_CANONICAL_POINTER_POPULATION')
    validation=meta(review['canonical_node13_source_validation_reference'])
    observed=[r for r in validation['inputs'] if r['reference']==rows[0]['reference']]
    need(validation['status']=='ALL_ACTUAL_SOURCE_SHA_VERIFIED' and len(observed)==1
        and observed[0]['actual']==rows[0]['reference'] and observed[0]['status']=='ACTUAL_FULL_SHA_MATCH'
        and observed[0]['uid']==rows[0]['after']['uid']==1278
        and observed[0]['inode']==rows[0]['after']['inode'] and observed[0]['mtime_ns']==rows[0]['after']['mtime_ns'],
        'REAL_PRIOR_CPU13_CANONICAL_SOURCE_FRAME_NOT_ASSUMED_CROSS_NODE_DEVICE')
    hof=meta(plan['hof_authority_reference']);projection=meta(hof['projection_receipt_reference'])
    need(hof['schema']=='ROOT_PM7_CACHE_CANONICAL_HOF_AUTHORITY_V1' and hof['reviewer']=='root'
        and hof['status']=='VERIFIED_FROZEN_PM7_B_SCALAR_READER' and hof['registry_id']==60
        and hof['unit']=='kcal/mol' and hof['native_energy_fallback_allowed'] is False
        and projection['status']=='CATALOG_METADATA_PROJECTION_VERIFIED'
        and hof['source_files_reference']==projection['source_files'],'ORIGINAL_REGISTRY60_HOF_OWNER_AUTHORITY')
    data=unique([*m['membership_tables'],*m['physical_geometry_tables'],reference(rows[0]['reference']),
        reference(hof['latest_owner_reference']),reference(projection['source_files'])])
    refs=unique([*refs,plan['ordinary_source_review_reference'],plan['ordinary_N1_preparation_policy_reference'],
        plan['hof_authority_reference'],hof['projection_receipt_reference'],m['formal_population_authority_receipt'],m['old_sprime_manifest'],m['config'],
        review['canonical_node13_source_validation_reference']])
    return m,rows[0]['reference'],hof,data,refs


def actual(chain):
    need(type(chain) is dict and set(chain)=={'receipt','startup_proof','accounting'},'EXACT_REAL_BUILDER_C0_CHAIN')
    r=meta(chain['receipt']);p=meta(chain['startup_proof']);plan=meta(r['plan_reference'])
    need(r['schema']=='D5_INPUT_BUILDER_STAGE_RECEIPT_V1' and r['status']=='COMPLETE_TECHNICAL_STAGE_REQUIRES_ROOT_REVIEW'
        and r['error'] is None and r['held_molecules']==0 and r['D5_jointly_frozen'] is False
        and str(r['job_id'])==str(p['job_id']) and p['uid']==1278 and r['node']==p['request']['node']
        and p['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and p['request']['partition']=='cpu'
        and meta(p['request_reference'])==p['request']
        and p['request']['scope_key']=='d5_inputs_builder_'+plan['mode']+'_v1'
        and p['request']['scope_parameters']==parameters(plan) and p['request']['cpus']==16
        and p['request']['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and p['request']['execution_argv']==[PY,'-B','-m',MODULE,'--plan',r['plan_reference']['path'],'--startup-proof',chain['startup_proof']['path']]
        and r['plan_reference'] in p['request']['source_references']
        and plan['data_references']==p['request']['data_references']
        and Path(chain['receipt']['path'])==Path(plan['output_directory'])/'receipt.json','ACTUAL_SAME_TECHNICAL_STAGE_NOT_PROFILE_OR_PARTIAL')
    gate=meta(r['source3_reference']);mem=meta(r['resource_observation_reference'])
    need(gate['tests_run']==3 and all(gate[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes'))
        and mem['status']=='RESOURCE_OBSERVATION_CLOSED' and mem['soft_stop_requested'] is False
        and mem['job_id']==str(p['job_id']) and mem['startup_proof_request_reference']==p['request_reference'],'ACTUAL_SOURCE3_RESOURCE_CLOSURE')
    raw=D.account(chain['accounting'],r['job_id'],r['node'])
    return r,plan,unique([*chain.values(),raw,r['plan_reference'],r['source3_reference'],r['resource_observation_reference'],p['request_reference']])


def pending(request):
    missing=[k for k in COMMON_KEYS if request.get(k) is None]
    for k in ('resource_authority_reference','cost_decision_reference','quota_reuse_reference'):
        if request.get(k) is None:missing.append(k)
    mode=request.get('mode')
    if mode=='base' and request.get('prepared_range_reference') is None:missing.append('actual_prepared_range_reference')
    if mode=='base' and request.get('preparation_closure_references') is None:missing.append('actual_preparation_C0')
    if mode=='base' and request.get('range_registry_page_reference') is None:missing.append('actual_range_registry_page_reference')
    if mode in ('merge','verify','final') and not request.get('input_closure_references'):missing.append('actual_input_C0_chains')
    if mode=='final':
        for k in ('actual_child_input_authority_reference','N1_final_policy_reference'):
            if request.get(k) is None:missing.append(k)
    if request.get('purpose')=='full' and mode!='prepare' and request.get('actual512_review_reference') is None:missing.append('actual512_C0_parity_and_independent_Root_review')
    return {'schema':'D5_INPUT_BUILDER_PENDING_V1','status':'NONEXECUTABLE_PENDING_ACTUAL_PARENTS','missing':missing,
        'stage_spec_generated':False,'scientific_DATA_opened_statted_or_hashed':False,'D5_jointly_frozen':False}


def inputs(plan):
    limits(plan);m,formal,hof,data,refs=common(plan);mode=plan['mode'];parents=[]
    if mode=='base':
        r,p,more=actual(plan['preparation_closure_references']);need(p['mode']=='prepare'
            and p['common_closure_references']==plan['common_closure_references'],'SAME_REAL_PREPARATION')
        batch=meta(plan['prepared_range_reference'])
        page=meta(plan['range_registry_page_reference'])
        need(plan['range_registry_page_reference'] in r['range_registry_page_references']
            and plan['prepared_range_reference'] in page['range_manifest_references'] and page['job_id']==r['job_id']
            and batch['job_id']==r['job_id']
            and batch['schema']=='D5_INPUTS_ACTUAL_RANGE_LOCATORS_V1' and batch['logical_range']==plan['logical_range']
            and plan['logical_partition_molecules']==p['logical_partition_molecules']
            and 0<batch['molecules']<=plan['logical_partition_molecules'],'ONLY_ACTUAL_CPU_FROZEN_RANGE_NOT_LOGIN_SELECTION')
        data=unique([batch['descriptor_reference'],*batch['data_references']]);refs+=more+[plan['prepared_range_reference'],plan['range_registry_page_reference']]
        if plan['purpose']=='pilot512':need(batch['molecules']==512 and batch['logical_range'][0]==0,'EXACT_REAL_FIRST512_WHOLE_MOLECULE_PILOT')
    elif mode in ('merge','verify','final'):
        need(1<=len(plan['input_closure_references'])<=(MAX_PARENTS if mode=='merge' else 1),'FINITE_CLOSED_INPUT_SET')
        data=[]
        for chain in plan['input_closure_references']:
            r,p,more=actual(chain);need(p['common_closure_references']==plan['common_closure_references'],'SAME_ORDINARY_COMMON_LINEAGE')
            need(p['mode'] in ('base','merge','verify','final') and r['table_domain'] in ('BASE_ONLY','BASE_WITH_ALL_ACTUAL_CHILDREN'), 'ACTUAL_TYPED_TABLE_PARENT')
            parents.append(r);data.extend(r['table_references'].values());refs+=more
        if mode=='merge':
            need(all(r['full_typed_source_order_identity_parity'] is True for r in parents),'ONLY_REAL_VERIFIED_TYPED_PARENTS_MERGE')
            ordered=sorted(parents,key=lambda r:r['logical_range'][0]);need(ordered==parents
                and len({r['table_domain'] for r in parents})==1
                and all(a['logical_range'][1]==b['logical_range'][0] for a,b in zip(parents,parents[1:]))
                and plan['logical_range']==[parents[0]['logical_range'][0],parents[-1]['logical_range'][1]],'EXACT_ADJACENT_RANGES_NO_DUP_OR_GAP')
        else:need(parents[0]['logical_range']==plan['logical_range'],'EXACT_SAME_INPUT_INTERVAL')
        if mode=='verify':
            data += [*m['physical_geometry_tables'],*m['membership_tables'],*parents[0].get('worker_packet_references',[])]
        if mode=='final':
            need(parents[0]['table_domain']=='BASE_ONLY','ADD_REAL_CHILDREN_ONLY_TO_CLOSED_BASE_TABLES')
            need(parents[0]['molecules']<=BATCH,'FINAL_CHILD_STAGE_BOUNDED_WHOLE_MOLECULE_RANGE_MAX512')
            child=meta(plan['actual_child_input_authority_reference']);policy=meta(plan['N1_final_policy_reference'])
            need(child['schema']=='ROOT_D5_ACTUAL_CHILD_INPUT_AUTHORITY_V1' and child['status']=='ROOT_REVIEWED_COMPLETE_ACTUAL_INPUT_EVIDENCE'
                and child['reviewer']=='root' and child['common_manifest_reference']==plan['common_closure_references']['manifest']
                and child['logical_range']==plan['logical_range'] and child['source_domains']==['pm7','uff_sprime']
                and child['all_actual_direct_children_covered'] is True and child['unobserved_future_calls_included'] is False
                and child['reconstruction_not_relabelled_observation'] is True
                and child['complete_required_training_task_domain_reviewed'] is True
                and child['retained_raw_failure_and_audit_evidence_reviewed'] is True
                and child['independent_diagnostic_calls_used_as_production_children'] is False
                and type(child['actual_direct_child_count']) is int and child['actual_direct_child_count']>=0
                and all(type(child[k]) is int and child[k]==0 for k in ('missing_input_hash_count','unknown_call_domain_count','unverified_call_count')),
                'ACTUAL_CHILD_CALL_DOMAIN_NOT_FUTURE_RENDER_OR_N1_PARENT_COLLECTION')
            need(policy['status']=='ROOT_REVIEWED_N1_N2_ORDINARY_D5_POLICY' and policy['reviewer']=='root'
                and policy['common_manifest_reference']==plan['common_closure_references']['manifest']
                and policy['ordinary_sprime_count_unchanged'] is True and policy['Pprime_extra_not_ordinary'] is True,'SEPARATE_FINAL_N1_N2_POLICY')
            need(child['evidence_format']=='ORIGINAL_B32_AND_PPRIME_STAGING_V1'
                and type(child['actual_parent_chains']) is list and child['actual_parent_chains'], 'EXACT_IMPLEMENTED_ORIGINAL_EVIDENCE_FORMAT_AND_REAL_PRODUCERS')
            # No claim that the original 32-record producer covers another domain.
            for c in child['actual_parent_chains']:
                proof=meta(c['startup_proof']);manifest=meta(c['manifest'])
                env=manifest.get('runtime',manifest)
                need(c['uid']==proof['uid']==1278 and str(c['job_id'])==str(proof['job_id'])==str(env['job_id'])
                    and c['node']==proof['request']['node'] and c['manifest_status']==manifest['status']
                    and not any(v in manifest['status'].upper() for v in ('INCOMPLETE','SOURCE_ONLY','HOLD','PENDING_EXECUTION','FIXTURE')),'EXACT_REAL_CHILD_PRODUCER')
                refs += [c['startup_proof'],c['manifest'],c['accounting'],D.account(c['accounting'],c['job_id'],c['node'])]
            data += [reference(child['binding_index_reference']),*[reference(r) for r in child['evidence_DATA_references']]]
            refs += [plan['actual_child_input_authority_reference'],plan['N1_final_policy_reference'],*child['protocol_source_references']]
    if plan['purpose']=='full' and mode!='prepare':
        review=meta(plan['actual512_review_reference']);r,p,more=actual(review['pilot_closure_references'])
        need(review['schema']=='ROOT_D5_INPUTS_ACTUAL512_REVIEW_V1' and review['status']=='APPROVED_EXACT_ORDINARY_SOURCE_PARITY'
            and review['reviewer']=='root' and p['purpose']=='pilot512' and p['mode']=='verify'
            and p['common_closure_references']==plan['common_closure_references'] and r['molecules']==512
            and r['full_typed_source_order_identity_parity'] is True and review['all_original_quality_gates_unchanged'] is True,
            'ACTUAL512_VERIFIED_AND_REVIEWED_BEFORE_FULL')
        refs += [plan['actual512_review_reference'],*more]
    need(all(reference(r) for r in data),'ALL_SCIENTIFIC_DATA_POSITIVE_LARGE_REFERENCES')
    return m,formal,hof,unique(data),unique(refs),parents
