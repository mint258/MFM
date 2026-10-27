"""New20 is not the old20 record audit or the previous authorized15 QA."""
import hashlib
from pathlib import Path
from workflows.data_v1_final.pprime.strict_numerics15_qa_v1 import contract as S
from workflows.expansion.common_molecular_fp_main_v1 import contract as F
Q=S.Q;meta=S.meta;unique=S.unique;O=S.O
HERE=Q.REPO/'workflows/data_v1_final/pprime/strict_numerics20_prepare_v1'
FILES=('__init__.py','contract.py','inputs.py','prepare.py','proposal.py','execution_contract.py','metadata.py','test_v1.py','README.md')
MODULE='workflows.data_v1_final.pprime.strict_numerics20_prepare_v1.prepare'
KEY='pprime_strict20_all12_zero_invoke_prepare_v1';STAGE='PPRIME_NEW20_ALL12_INPUTS_PREPARE_NO_INVOKE'
N=20;TASKS=S.P.NAMES;ARMS=O.ARMS;MAX_CALLS=N*len(TASKS)*len(ARMS);SEED=20261010
PREP_CAP=1<<30;EXEC_CAP=31<<30;WHOLE_CAP=32<<30;CLOSED_CALL_CAP=25<<20;UNRESOLVED_CALL_CAP=112<<20;EXEC_PARENT_CAP=256<<20
PARAMETERS={'new_unique_MIDs':N,'source_original_molecules':1000,'source_original_pairs':2000,'QA_minimum_atoms':1,'QA_maximum_atoms':80,
    'selection_seed':SEED,'selection_domain':'pprime-strict20-all12-selection-v1','chosen_UFF_geometry_per_MID':1,
    'chosen_geometry':'original_fixed_random_rank0','all_task_names':list(TASKS),'arms':list(ARMS),
    'maximum_later_QM_calls_requiring_new_user_authorization':MAX_CALLS,'this_stage_new_QM_calls':0,'this_stage_native_invoke_calls':0,
    'original_protocol_only_initialize_for_readers':True,'candidate_protocol_render_only':True,'same_three_protocol_diffs_only':True,
    'P1_P2_are_exact_P90_coordinate_axis_transform_not_atom_permutation':True,'source_atom_order_never_shuffled':True,
    'source_full_three_orders_read_only_QA_provenance_not_final_Common':True,'full_original_pair_file_SHA_before_parse':True,
    'original_LMDB_payload_SHA_and_selected_Sprime_row_atom_geometry_SHA':True,'old5_Sprime_SHA_inherited_current_frame_and_selected_rows_verified':True,
    'new_pure_methods':3,'all3_before_scientific_DATA':True,'cpus':16,'memory_requested':False,'prepare_wall_seconds':7200,
    'prepare_shared_output_cap_bytes':PREP_CAP,'execution_NOT_implemented_in_this_package':True,
    'old15FAIL_and_2000_full_HOLD_preserved':True,'new_tolerance_or_SCF_success_claim':False}

def select_mid_key(mid):return hashlib.sha256(f'pprime-strict20-all12-selection-v1:{SEED}:{mid}'.encode()).hexdigest()

def choose20(pairs):
    Q.need(len(pairs)==2000 and len({p['record_id'] for p in pairs})==2000,'EXACT_ORIGINAL2000_UNIQUE_PAIR_RECORDS')
    grouped={}
    for pair in pairs:
        Q.need(isinstance(pair['record_id'],str) and pair['record_id'] and isinstance(pair['molecule_id'],str) and pair['molecule_id']
            and type(pair['random_order_rank']) is int,'EXACT_ORIGINAL_LITERAL_MID_RECORD_ID_AND_INTEGER_RANK')
        grouped.setdefault(pair['molecule_id'],[]).append(pair)
    Q.need(len(grouped)==1000 and all(len(v)==2 and {p['random_order_rank'] for p in v}=={0,1} for v in grouped.values()),'EXACT1000_UNIQUE_MIDs_WITH_ORIGINAL_TWO_RANKS')
    first=[next(p for p in values if p['random_order_rank']==0) for values in grouped.values()]
    Q.need(all(type(p['source']['total_atoms']) is int for p in first),'ORIGINAL_POSITIVE_INTEGER_ATOM_COUNTS_NOT_BOOL_OR_FLOAT')
    eligible=[p for p in first if 1<=p['source']['total_atoms']<=80]
    Q.need(len(eligible)>=20,'QA_HAS_FEWER20_ELIGIBLE_NO_RESAMPLING_OR_ATOM_TRUNCATION')
    selected=sorted(eligible,key=lambda p:(select_mid_key(p['molecule_id']),p['molecule_id']))[:20]
    return selected,{'original_unique_MIDs':1000,'eligible_MIDs_1to80_atoms':len(eligible),
        'QA_unavailable_over80_atoms':sum(p['source']['total_atoms']>80 for p in first),
        'invalid_source_below1_atom':sum(p['source']['total_atoms']<1 for p in first),
        'selected_unique_MIDs':20,'selection_is_target_independent':True,'original20_audit_records_reused_as20_MIDs':False}

def parents(plan):
    old,new,diff=S.protocol(plan)
    Q.need(plan['candidate_protocol_reference']['bytes']==19218 and plan['candidate_protocol_reference']['sha256']=='f72bb07780b28026df5931478b50495d3cb4d75fe5edecac7593b90af9356302','SAME_ACTUAL_FROZEN_STRICT15_CANDIDATE_BYTES')
    review=meta(plan['prior_strict15_root_review_reference']);receipt=meta(review['producer_receipt_reference'])
    Q.need(review['schema']=='ROOT_ACTUAL_APPROVED_STRICT15_LIMITED_DIAGNOSTIC_REVIEW_V1'
        and review['status']=='ACTUAL15_LIMITED_PREDECLARED_QA_PASSED_FULL_RECIPE_REMAINS_UNAPPROVED'
        and review['actual_job_id']=='4523473' and review['actual_calls']==15
        and review['all25_vector_checks_pass_original_tolerances'] is True and review['all_same_geometry_companions_pass'] is True
        and review['scientific_PASS_claimed'] is False and review['pilot2000_and_full_release']=='HOLD','REAL_PRIOR15_LIMITED_PASS_ONLY')
    _,raw=F.account(review['actual_terminal_accounting_reference'],receipt['job_id'],receipt['node'])
    closure=meta(plan['original_preparation_closure_reference']);prepared=meta(plan['original_prepared_reference'])
    Q.need(closure['status']=='ROOT_PPRIME_INPUT_PREPARATION_ACTUAL_COMPLETED_READBACK_CLOSED'
        and closure['prepared']==plan['original_prepared_reference'] and closure['actual_parent']['JobIDRaw']=='4520345'
        and closure['actual_parent']['State']=='COMPLETED' and closure['actual_parent']['ExitCode']=='0:0'
        and closure['molecules']==prepared['molecules']==1000 and closure['conformers']==prepared['conformers']==2000
        and prepared['status']=='PPRIME_PAIRS_READY_NOT_QM_EXECUTED' and closure['QM_started'] is False,'ACTUAL_ORIGINAL1000_2000_INPUT_CLOSURE')
    source=meta(plan['source_context_reference'])
    Q.need(source['schema']=='ROOT_PPRIME_CAUSAL15_SOURCE_PLAN_V1' and source['status']=='APPROVED_FIXED6_SOURCE_PREPARATION_NOT_QM'
        and source['reviewer']=='root' and source['protocol']==plan['original_protocol_reference']
        and source['pilot_config']==prepared['config'],'OLD_CONTEXT_REUSED_FOR_FROZEN_SOFTWARE_ONLY_NOT_NEW20_AUTHORITY')
    pair_refs=[r for r in prepared['outputs'] if Path(r['path']).name=='pairs.jsonl']
    Q.need(len(pair_refs)==1 and type(pair_refs[0]['bytes'])is int and pair_refs[0]['bytes']==19385976,'SOLE_ORIGINAL19MB_PAIRS_DATA_NOT_SMALL_METADATA')
    pair=O.triple(pair_refs[0]);sprime=[O.triple(r) for r in prepared['source_sprime_references']];Q.need(len(sprime)==5,'ALL5_ORIGINAL_SPRIME_LOCATORS')
    audit=meta(source['audit_config']);Q.need(audit['maximum_atoms']==80,'ORIGINAL_BOUNDED_BRIDGE_ATOM_SCOPE')
    recipe=meta(plan['original_sprime_recipe_reference'])
    Q.need(plan['original_sprime_recipe_reference']=={'path':str(Q.REPO/'configs/data_v1/conformers/pilot_v1.json'),'bytes':3629,'sha256':'cfd153fb524ad823d3903b0ff7d78e402bbbcb74e124136b4bfeb3035279407a'}
        and recipe['order_seed']==20261025 and recipe['rdkit_version']=='2025.09.5' and len(recipe['science_source_pins'])==2,'ORIGINAL_SPRIME_RECIPE_AND_FIXED_KABSCH_OBJECTS')
    quota=meta(plan['quota_reuse_reference']);F.Provider.load_review(quota['provider_review_reference'])
    Q.need(quota['compute_node']=='compute-0-13' and quota['status']=='APPROVED_RESOURCE_FACT_REUSE_ONLY','ACTUAL_MAIN13_PROVIDER_REUSE')
    refs=[plan[k] for k in ('prior_strict15_root_review_reference','original_preparation_closure_reference','original_prepared_reference',
        'source_context_reference','original_protocol_reference','candidate_protocol_reference','quota_reuse_reference','original_sprime_recipe_reference')]
    refs += [review['producer_receipt_reference'],review['actual_terminal_accounting_reference'],raw,source['audit_config'],source['pilot_config'],
        source['legacy_contract'],*source['source_references'],*F.Provider.references(quota['provider_review_reference']),
        quota['publisher_identity_reference'],quota['provider_actual_launch_reference'],quota['resource_epoch_root_binding_reference'],*recipe['science_source_pins'],closure['readback']]
    pilot=meta(source['pilot_config']);lmdb_source_plan=meta(pilot['source_plan'])
    entries=lmdb_source_plan['sources'];Q.need(len(entries)==11 and {s['shard_id'] for s in entries}==set(range(11)),'ORIGINAL11_CLOSED_LMDB_MANIFEST_LOCATORS')
    lmdb=[O.triple({'path':s['path'],'bytes':s['source_size'],'sha256':s['file_sha256']}) for s in entries]
    refs.append(pilot['source_plan'])
    data=unique([pair,*sprime,*lmdb,*source['execution_asset_references']])
    return old,new,diff,source,prepared,pair,sprime,data,unique(refs)

def sources():
    paths=[*(HERE/n for n in FILES),*(S.HERE/n for n in S.FILES),*(S.P.HERE/n for n in S.P.FILES),*F.source_paths()]
    base=Q.REPO/'workflows/data_v1_final'
    paths += [base/'pprime'/n for n in ('common.py','geometry.py','prepare_pilot.py')]
    paths += [base/'conformers'/n for n in ('common.py','selection.py')]
    paths += list((base/'pprime/causal15_main_v1').glob('*.py'))+list((base/'pprime/vector_audit').glob('*.py'))
    return sorted(set(paths))
