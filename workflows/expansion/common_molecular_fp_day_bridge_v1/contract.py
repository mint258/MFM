"""Small-parent contracts and exact existing Main startup/source interfaces."""
import csv,io
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
from workflows.expansion.marcel_drugs_keys_main_v1 import contract as D
from workflows.expansion.common_molecular_fp_candidate_v1 import contracts as P
from workflows.data_v1_final.execution.cpu_packed_day_v1 import quota_provider as Provider
from workflows.data_v1_final.export.common_day_parent_v1 import parent as Bridge
from workflows.expansion.common_molecular_fp_main_v1 import contract as OLD

HERE=Q.REPO/'workflows/expansion/common_molecular_fp_day_bridge_v1'
MODULE='workflows.expansion.common_molecular_fp_day_bridge_v1.run'
STAGE='FINAL_COMMON_ORIGINAL_SOURCE_GRAPH_STRUCTURAL_FEATURES'
FILES=('__init__.py','contract.py','resources.py','run.py','materialize.py','finalize.py','source_inverse.py','test_v1.py','README.md')
PROFILE_PER_ROLE=256;SEED=20261027
def meta(r):
    P.reference(r,small=True);Q.need(Q.pin(r['path'])==r,'ACTUAL_SMALL_METADATA_PIN');return Q.load(r['path'])
def unique(refs):return D.unique(refs)
def triple(r):return P.data_reference({k:r[k] for k in ('path','bytes','sha256')})
def profile_output_projection(profile):
    r=profile['result'];total=0
    for role in ('TRAIN','VAL'):
        n=r['selected_census']['molecules_by_role'][role];population=r['expected_all_common_census']['molecules_by_role'][role]
        size=sum(r[k][role] for k in ('source_journal_actual_bytes_by_role','graph_journal_actual_bytes_by_role','strict5_actual_bytes_by_role'))
        Q.need(type(n)is int and n>0 and type(population)is int and population>=n,'ACTUAL_PROFILE_ROLE_DENOMINATORS')
        total+=(size*population+n-1)//n
    journals=sum(r[k]['bytes'] for k in ('source_journal_reference','graph_result_journal_reference','strict5_projection_reference'))
    fixed=profile['owned_output_bytes_before_receipt']-journals;Q.need(fixed>=0,'ACTUAL_NONJOURNAL_PROFILE_BYTES')
    return total,fixed
def key(mode):Q.need(mode in ('profile','full'),'EXACT_MODE');return 'common_molecular_fp_day_bridge_v1_'+mode
def parameters(mode,cap):
    Q.need(mode in ('profile','full') and type(cap) is int and (cap==2<<30 if mode=='profile' else 2<<30<=cap<=128<<30),'EXACT_REVIEWED_FINITE_CAP')
    return {'mode':mode,'worker_processes':16,'maximum_pending_MIDs':32,'worker_native_threads':1,
        'profile_MIDs_per_role':PROFILE_PER_ROLE if mode=='profile' else None,'profile_seed':SEED if mode=='profile' else None,
        'profile_selection':'SHA256(common-molecular-fp-profile-v1:{seed}:{MID}) within role' if mode=='profile' else 'ALL_TRUE_FINAL_COMMON_TRAIN_VAL_MIDs',
        'all_membership_role_and_formal_bodies_full_SHA_and_EOF':True,'whole_common_MID_role_record_census_even_in_profile':True,
        'source_selector':'ORIGINAL_CREATOR_SMILES_STRIP_TEMPLATE_V1','canonical_smiles_nonisomeric_not_selected':True,
        'historical_keys_and_accepted_differences_retained_without_new_equality_gate':True,'CID_invented':False,
        'distinct_MIDs_same_graph_preserved':True,'multiple_graphs_UNKNOWN_and_technical_failure_retained_HOLD':True,
        'original_feature_function_objects':True,'fingerprint_recipe':P.FINGERPRINT_RECIPE,'RDKit_version':'2025.09.5',
        'maximum_variant_bytes_per_MID':4<<20,'maximum_single_source_SMILES_bytes':1<<20,'maximum_variants_per_MID':4096,
        'source_before_dispatch_result_before_derived_projection':True,'pure_methods':6,'all6_before_DATA_and_monitor':True,
        'output_cap_bytes':cap,'actual_quota_provider_poll_seconds':60,'quota_freshness_seconds':120,
        'account_quota_and_physical_free_separate':True,'whole_wave_reserve_plus_own_remaining_cap_plus200GB':True,
        'memory_requested':False,'cost_overrun_action':'REPORT_AND_CONTINUE','new_UFF_QM_network_calls':0,
        'Root_final_graph_review_required_before_consumer_manifest':True,'baseline1M_NN_pool_training_release':False}

def account(ref,job_id,node):
    a=meta(ref);raw=a['raw_sacct_reference'];body=Q.read_small(raw['path']);Q.need(Q.pin(raw['path'])==raw,'ACTUAL_RAW_ACCOUNTING_PIN')
    rows=[r for r in csv.DictReader(io.StringIO(body.decode()),delimiter='|') if '.' not in r['JobIDRaw']]
    Q.need(a['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and a['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
        and a['endpoint']=='202.38.247.57:22' and a['uid']==1278 and a['query_returncode']==0
        and a['failed_timeout_startup_cleanup_elapsed_retained'] is True,'ACTUAL_MAIN_PARENT_ACCOUNTING')
    by={r['JobIDRaw']:r for r in rows};Q.need(len(by)==len(rows)==len(a['parents']),'EXACT_PARENT_ACCOUNTING_SET')
    total=0
    for p in a['parents']:
        r=by[p['job_id']];Q.need(p['state']==r['State'] and p['exit_code']==r['ExitCode']
            and p['node']==r['NodeList'] and p['alloc_cpus']==int(r['AllocCPUS'])
            and p['elapsed_raw_seconds']==int(r['ElapsedRaw']) and r['UID']=='1278','ACCOUNTING_ROWS_MATCH_RAW')
        total+=p['alloc_cpus']*p['elapsed_raw_seconds']
    Q.need(total==a['allocated_core_seconds'],'ACCOUNTING_COMPLETE_ACTUAL_COST')
    r=by[str(job_id)];Q.need(r['State']=='COMPLETED' and r['ExitCode']=='0:0' and r['NodeList']==node
        and int(r['AllocCPUS'])==16,'EXACT_ACCEPTED_PARENT_C0_NODE_CPU16')
    return a,raw

def inputs(plan,*,check_profile=True):
    common,bridge_refs=Bridge.common_parent({'manifest':plan['common_manifest_reference'],'entry':plan['common_entry_reference'],'accounting':plan['common_accounting_reference']})
    env=common['runtime'];entry=meta(plan['common_entry_reference']);proof=meta(entry['startup_proof_reference'])
    _,raw=Bridge.account(plan['common_accounting_reference'],env['job_id'],env['node'],env['cpus'])
    formal_ref=common['formal_population_authority_receipt'];formal=meta(formal_ref)
    Q.need(formal['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED','CANONICAL_FULL_SHA_AUTHORITY')
    f=[r['reference'] for r in formal['outputs'] if r['name']=='formal_population'];Q.need(len(f)==1,'ONE_FORMAL_RECORD_INDEX')
    members=[triple(r) for r in common['membership_tables']];Q.need(len(members)==16,'ALL16_COMMON_PARTS')
    roles_ref=common['roles_manifest'];roles=meta(roles_ref);Q.need(roles['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN'
        and common['roles_manifest_sha256']==roles_ref['sha256'],'EXACT_FROZEN_WHOLE_ROLE_AUTHORITY')
    role_parts=[triple(r) for r in roles['outputs'] if '/molecule_roles/' in r['path']];Q.need(len(role_parts)==16,'ALL16_WHOLE_ROLE_PARTS')
    writer=meta(plan['formal_writer_order_review_reference']);wm=meta(writer['original_writer_manifest_reference'])
    Q.need(writer['schema']=='ROOT_FORMAL_RECORD_INDEX_WRITER_ORDER_REVIEW_V1' and writer['status']=='APPROVED_ACTUAL_WRITER_AND_ORDER'
        and writer['reviewer']=='root' and writer['formal_reference']==f[0]
        and writer['record_order']==['file_group','molecule_id','conformer_id','record_id']
        and writer['MID_whole_file_group'] is True and writer['not_inferred_from_prefix'] is True
        and wm['status']=='WP5_FORMAL_POPULATION_CLOSED' and wm['outputs']['record_index']==f[0]['path'],'ORIGINAL_ACTUAL_WRITER_ORDER_AUTHORITY')
    Q.need(Q.pin(writer['writer_source_reference']['path'])==writer['writer_source_reference']
        and writer['writer_source_reference']['path'].endswith('/workflows/wp5/scripts/wp5_population.py'),'ORIGINAL_WRITER_SOURCE_PIN')
    graph=meta(plan['graph_policy_reference']);Q.need(graph['schema']=='COMMON_SOURCE_GRAPH_SELECTION_REVIEW_V1'
        and graph['status']=='ROOT_REVIEWED_SOURCE_ONLY' and graph['selected_source_field']=='smiles'
        and all(graph[k] is True for k in ('original_creator_strip_then_parse','canonical_smiles_nonisomeric_not_full_graph',
             'accepted_historical_key_differences_preserved','multiple_graphs_hold_without_representative')),'ROOT_ORIGINAL_GRAPH_SEMANTIC_REVIEW')
    quota=meta(plan['quota_reuse_reference']);provider=quota['provider_review_reference'];Provider.load_review(provider)
    Q.need(quota['schema']=='SPRIME_MAIN_ACCOUNT_QUOTA_REUSE_ROOT_REVIEW_V3' and quota['status']=='APPROVED_RESOURCE_FACT_REUSE_ONLY'
        and quota['reviewer']=='root' and quota['compute_node']=='compute-0-13'
        and type(quota['whole_wave_output_reserve_bytes']) is int and quota['whole_wave_output_reserve_bytes']>=0,'ACTUAL_CPU13_ACCOUNT_QUOTA_AND_WAVE_RESERVE')
    parents=[plan[k] for k in ('common_manifest_reference','common_entry_reference','common_accounting_reference',
        'formal_writer_order_review_reference','graph_policy_reference','quota_reuse_reference')]
    parents += [*bridge_refs,raw,formal_ref,roles_ref,
        writer['original_writer_manifest_reference'],writer['writer_source_reference'],*Provider.references(provider),
        quota['provider_actual_launch_reference'],quota['publisher_identity_reference'],quota['resource_epoch_root_binding_reference']]
    data=unique([*members,*role_parts,triple(f[0])]);Q.need(len(data)==33,'EXACT33_CANONICAL_AND_WHOLE_POPULATION_BODIES')
    if plan['mode']=='full' and check_profile:
        p=meta(plan['accepted_profile_receipt_reference']);_,pr=account(plan['accepted_profile_accounting_reference'],p['job_id'],p['node'])
        review=meta(plan['profile_root_review_reference'])
        Q.need(p['schema']=='COMMON_MOLECULAR_FP_CPU_RECEIPT_V1' and p['mode']=='profile'
            and p['status']=='SELECTED_MOLECULAR_GRAPH_AUDIT_COMPLETE_PENDING_ROOT_FINAL_REVIEW'
            and p['common_manifest_reference']==plan['common_manifest_reference'] and p['data_references']==data
            and p['result']['selected_MIDs']==2*PROFILE_PER_ROLE and p['result']['HOLD_MIDs']==0,'REAL_SAME_INPUT_COMPLETE512_PROFILE')
        pp=meta(p['plan_reference']);ps=meta(p['startup_proof_reference'])
        Q.need(Path(plan['accepted_profile_receipt_reference']['path'])==Path(pp['output_directory'])/'receipt.json',
            'PROFILE_RECEIPT_IN_ACTUAL_PLANNED_OUTPUT')
        Q.need(pp['mode']=='profile' and pp['common_manifest_reference']==plan['common_manifest_reference']
            and ps['uid']==1278 and str(ps['job_id'])==str(p['job_id']) and ps['request']['node']==p['node']
            and ps['request']['scope_key']==key('profile') and ps['request']['scope_parameters']==pp['scope_parameters']==parameters('profile',2<<30)
            and p['plan_reference'] in ps['request']['source_references'],'REAL_PROFILE_PLAN_STARTUP_AND_PROTOCOL')
        for path in source_paths():Q.need(Q.pin(path) in ps['request']['source_references'],'FULL_SAME_FROZEN_PROFILE_SOURCE_BYTES')
        Q.need(review['schema']=='ROOT_COMMON_FP_PROFILE_COST_QUALITY_REVIEW_V1' and review['status']=='APPROVED_FULL_GRAPH_AUDIT'
            and review['reviewer']=='root' and review['profile_receipt_reference']==plan['accepted_profile_receipt_reference']
            and review['profile_accounting_reference']==plan['accepted_profile_accounting_reference']
            and review['actual_cost_storage_and_UNKNOWN_reviewed'] is True
            and review['output_cap_bytes']==plan['output_cap_bytes'] and review['wall_seconds']==plan['wall_seconds']
            and review['descriptive_not_worst_case_output_budget_reviewed'] is True
            and review['NN_1M_pool_release_authorized'] is False,'REAL_ROOT_PROFILE_AND_FULL_BUDGET_REVIEW')
        variable,fixed=profile_output_projection(p);factor=review['descriptive_output_expansion_factor'];extra=review['additional_full_scalar_index_allowance_bytes']
        Q.need(type(factor)is int and factor>=1 and type(extra)is int and extra>=0
            and review['actual_role_weighted_journal_projection_bytes']==variable and review['observed_profile_nonjournal_bytes']==fixed
            and plan['output_cap_bytes']>=variable*factor+fixed+extra+(258<<20)+(16<<20),'ACTUAL_PROFILE_BYTES_PLUS_EXPLICIT_INDEX_DRAIN_ADMIN_BUDGET')
        parents += [plan['accepted_profile_receipt_reference'],plan['accepted_profile_accounting_reference'],pr,plan['profile_root_review_reference'],p['plan_reference'],p['startup_proof_reference']]
    return common,members,role_parts,triple(f[0]),data,unique(parents)

def source_paths():
    paths=[*(HERE/n for n in FILES),*(OLD.HERE/n for n in OLD.FILES),*(Path(r['path']) for r in Bridge.sources()),*(D.HERE/n for n in D.FILES),*D.OLD]
    candidate=Q.REPO/'workflows/expansion/common_molecular_fp_candidate_v1'
    paths += list(candidate.glob('*.py'))+[candidate/'source_evidence_v1.json',candidate/'README.md']
    paths += [Q.REPO/n for n in P.KERNEL_PATHS]
    for relative in ('workflows/data_v1_final/execution/cpu_auto_memory_queue_v2','workflows/data_v1_final/execution/queue_v1'):
        paths += list((Q.REPO/relative).glob('*.py'))
    paths += [Provider.HERE/'quota_provider.py',Provider.HERE/'contract.py']
    return sorted(set(paths))
