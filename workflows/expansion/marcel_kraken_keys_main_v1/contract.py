"""Actual primitive-parent evidence, fixed profile and separately reviewed full."""
from pathlib import Path
from workflows.expansion.marcel_kraken_primitive_structure_v1 import contract as S
from workflows.expansion.marcel_drugs_keys_main_v1 import contract as D
Q=S.Q;M=S.M;HERE=Q.REPO/'workflows/expansion/marcel_kraken_keys_main_v1'
FILES=('__init__.py','contract.py','source.py','kernel.py','run.py','test_v1.py','materialize.py','README.md')
OLD=tuple(S.HERE/n for n in S.FILES)+S.OLD+tuple(D.HERE/n for n in D.FILES)+D.OLD
MODULE='workflows.expansion.marcel_kraken_keys_main_v1.run';STAGE='MARCEL_KRAKEN_NATIVE_SMILES_AND_ALL_CONFORMER_GRAPH_IDENTITY_UNIONS'
ROOT_N=1552;CONF_N=21287;PILOT_N=1000;SEED=20261027
unique=D.unique;account=D.account


def scope_key(mode):Q.need(mode in ('profile','full'),'EXACT_MODE');return 'marcel_kraken_keys_main_v1_'+mode


def parameters(mode,cap):
    Q.need(mode in ('profile','full') and type(cap) is int and (cap==512<<20 if mode=='profile' else 512<<20<=cap<=4<<30),'EXACT_MODE_CAP')
    return {'mode':mode,'source_id':'marcel_kraken_zip','actual_structure_parent_job_id':'4521767','decoded_member_bytes':94805786,
        'all_native_root_SMILES':ROOT_N,'all_native_conformer_MolBlocks':CONF_N,'all_source_relationships':ROOT_N+CONF_N,
        'selected_root_SMILES':ROOT_N,'selected_MolBlocks':PILOT_N if mode=='profile' else CONF_N,
        'uniform_conformer_without_replacement_seed':SEED if mode=='profile' else None,
        'all_native_IDs_assignment_ordinals_and_relationships_logged':True,'native_unicode_keys_not_int_converted_or_prefixed':True,
        'source_scope':'ALL_ORIGINAL_ARCHIVE_ASSIGNMENTS_NO_SPLIT_FILTER_OR_NEW_ROLE_ASSIGNMENT',
        'primitive_reader_and_structure_function_objects_reused':True,'decoded_metadata_equals_actual1767':True,
        'pickle_load_Unpickler_GLOBAL_REDUCE_BUILD_or_payload_constructors':False,
        'source_SMILES_frozen_function_objects':True,'RDKit_version':'2025.09.5','sampler_python':'3.11.14',
        'MolBlock_author_parser':{'removeHs':False,'sanitize':'AUTHOR_DEFAULT_TRUE','strictParsing':'AUTHOR_DEFAULT_TRUE'},
        'MolBlock_to_key':'AUTHOR_MolFromMolBlock_THEN_MolToInchiKey_THEN_FROZEN_full_keys_AND_wp5_key',
        'MolToSmiles_roundtrip_or_SMILES_graph_repair':False,'representative_conformer_choice':False,
        'root_SMILES_and_each_MolBlock_key_mismatch_and_unknown_separate':True,'per_root_key_policy':'CONSERVATIVE_UNION_ALL_OBSERVED_SOURCE_KEYS',
        'assay_weight_or_property_float_values_persisted':False,'new_pure_fixture_methods':3,'all3_before_archive_and_inventory_bodies':True,
        'workers':16,'maximum_pending_rows':32,'worker_native_threads':1,'durable_source_before_dispatch_and_result_before_aggregate':True,
        'parent_and_direct_children_RSS_soft_cap_bytes':16<<30,'minimum_MemAvailable_bytes':4<<30,
        'output_cap_bytes':cap,'drain_reserve_bytes':256<<20,'unknown_is_chemical_exclusion':False,
        'new_network_UFF_QM_calls':0,'global_decontamination_pool_training_or_source_acceptance':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def inputs(plan):
    b=M.meta(plan['accepted_structure_receipt_reference']);Q.need(b['schema']=='MARCEL_KRAKEN_PRIMITIVE_STRUCTURE_RECEIPT_V1'
        and b['status']=='STRUCTURE_EVIDENCE_COMPLETE_SEMANTICS_AND_KEYS_PENDING' and str(b['job_id'])=='4521767'
        and b['uid']==1278 and b['endpoint']=='202.38.247.57:22' and b['normalized_key_calls']==0
        and b['fixtures']['tests_run']==3 and all(b['fixtures'][k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
        'ACTUAL_STRUCTURE_C0_WITH3_PURE_PASS_NOT_KEY_ACCEPTANCE')
    old=M.meta(b['plan_reference']);proof=M.meta(b['startup_proof_reference']);_,parents=S.inputs(old)
    Q.need(old['scope_parameters']==S.PARAMETERS==proof['request']['scope_parameters'] and proof['uid']==1278
        and str(proof['job_id'])==str(b['job_id']) and proof['request']['node']==b['node'] and proof['request']['scope_key']==S.KEY
        and b['plan_reference'] in proof['request']['source_references'] and plan['archive_reference']==old['archive_reference']
        and plan['inventory_reference']==old['inventory_reference'],'ACTUAL_STRUCTURE_PLAN_PROOF_AND_CURRENT_BODY_LOCATORS')
    for path in [*(S.HERE/n for n in S.FILES),*S.OLD]:Q.need(Q.pin(path) in proof['request']['source_references'],'EXACT_FROZEN_PRIMITIVE_PRODUCER_SOURCE')
    ref=b['result']['structure_observation_reference'];o=M.meta(ref);shape=o['structure'];decoder=o['decoder']
    Q.need(o['status']==shape['status']=='ALL_SOURCE_ASSIGNMENTS_STRUCTURALLY_OBSERVED_SEMANTICS_PENDING' and o['decoder_problem'] is None
        and o['archive_reference']==plan['archive_reference'] and o['producer_inventory_reference']==plan['inventory_reference']
        and o['member_current_EOF_CRC_SHA']['EOF_CRC_SHA_complete'] is True and o['member_current_EOF_CRC_SHA']['decoded_bytes']==94805786
        and shape['top_source_assignments']==shape['top_tuple3_values']==ROOT_N
        and shape['secondary_source_assignments']==shape['secondary_tuple3_expected_type_matches']==CONF_N
        and shape['shape_issue_counts']=={} and shape['matches_author_loader_expected_tuple_positions'] is True
        and all(shape['primitive_graph'][k]==0 for k in ('reused_container_edges','cycle_edges','depth_bound_hits'))
        and decoder['PROTO']==4 and decoder['STOP_at_EOF'] is True and decoder['decoded_bytes']==94805786
        and decoder['payload_globals_imported_or_executed'] is False and decoder['pickle_load_Unpickler_or_constructor_dispatch_used'] is False,
        'ACTUAL_FULL_SOURCE_PRIMITIVE_SHAPE_AND_PROTOCOL_NOT_NORMALIZED_KEY_PASS')
    _,raw=account(plan['accepted_structure_accounting_reference'],b)
    refs=[*parents,plan['accepted_structure_receipt_reference'],plan['accepted_structure_accounting_reference'],raw,b['plan_reference'],b['startup_proof_reference'],ref]
    if plan['mode']=='full':
        p=M.meta(plan['accepted_profile_receipt_reference']);_,ar=account(plan['accepted_profile_accounting_reference'],p)
        Q.need(p['schema']=='MARCEL_KRAKEN_KEYS_RECEIPT_V1' and p['mode']=='profile'
            and p['status']=='EXACT_SELECTED_SOURCE_KEYS_OBSERVED_UNKNOWNS_AND_MISMATCHES_RETAINED'
            and p['archive_reference']==plan['archive_reference'] and p['inventory_reference']==plan['inventory_reference']
            and p['complete_source_relationship_rows']==ROOT_N+CONF_N and p['completed_by_kind']=={'root_SMILES':ROOT_N,'conformer_MolBlock':PILOT_N},
            'ACTUAL_SAME_SOURCE_EXACT_BOUNDED_PROFILE_CLOSURE')
        pp=M.meta(p['plan_reference']);ps=M.meta(p['startup_proof_reference'])
        Q.need(pp['scope_parameters']==parameters('profile',512<<20)==ps['request']['scope_parameters']
            and str(ps['job_id'])==str(p['job_id']) and ps['uid']==1278 and ps['request']['node']==p['node']
            and p['plan_reference'] in ps['request']['source_references'],'REAL_PROFILE_PLAN_PROOF')
        for path in [*(HERE/n for n in FILES),*OLD]:Q.need(Q.pin(path) in ps['request']['source_references'],'FULL_SAME_FROZEN_PROFILE_SOURCES')
        r=M.meta(plan['profile_root_review_reference']);by=p['selected_journal_bytes_by_kind']
        Q.need(sum(by.values())==p['selected_result_journal_reference']['bytes'],'EXACT_SEPARATE_ROOT_AND_CONFORMER_PROFILE_JOURNAL_BYTES')
        projected=by['root_SMILES']+(by['conformer_MolBlock']*CONF_N+PILOT_N-1)//PILOT_N
        Q.need(r['schema']=='ROOT_KRAKEN_IDENTITY_PROFILE_COST_QUALITY_REVIEW_V1' and r['status']=='APPROVED_FOR_FULL_IDENTITY_PROJECTION'
            and r['reviewer']=='root' and r['actual_profile_receipt_reference']==plan['accepted_profile_receipt_reference']
            and r['actual_profile_accounting_reference']==plan['accepted_profile_accounting_reference']
            and r['actual_profile_cost_unknowns_and_SMILES_graph_mismatches_reviewed'] is True
            and r['all_original_root_SMILES_and_every_conformer_authorized'] is True and r['candidate_or_pool_release_authorized'] is False
            and r['wall_seconds']==plan['wall_seconds'] and r['output_cap_bytes']==plan['output_cap_bytes']
            and r['conformer_journal_projection_is_uniform_descriptive_not_worst_case'] is True
            and r['root_plus_uniform_conformer_journal_projection_bytes']==projected
            and r['observed_profile_nonjournal_bytes']==p['owned_output_bytes_before_receipt']-p['selected_result_journal_reference']['bytes']
            and r['output_cap_bytes']>=projected+r['observed_profile_nonjournal_bytes']+(256<<20),
            'ROOT_ACTUAL_PROFILE_COST_UNKNOWNS_MISMATCHES_AND_DESCRIPTIVE_OUTPUT_CAP_REVIEW')
        refs.extend([plan['accepted_profile_receipt_reference'],plan['accepted_profile_accounting_reference'],ar,p['plan_reference'],p['startup_proof_reference'],plan['profile_root_review_reference']])
    return b,o,unique(refs)
