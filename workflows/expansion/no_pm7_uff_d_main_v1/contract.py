"""Metadata/source authority only;missing future R/N parents is NONEXECUTABLE."""
import hashlib,json,re
from pathlib import Path
from workflows.expansion.common_molecular_fp_main_v1 import contract as F
Q=F.Q;meta=F.meta;unique=F.unique;triple=F.triple
HERE=Q.REPO/'workflows/expansion/no_pm7_uff_d_main_v1';MODULE='workflows.expansion.no_pm7_uff_d_main_v1.run'
FILES=('__init__.py','contract.py','io.py','core.py','source.py','families.py','worker.py','run.py','closure.py','metadata.py','test_v1.py','README.md')
BASE=Q.ROOT/'artifacts/expansion/no_pm7_uff_d_main_v1';CACHE=BASE/'native_cache'
RECIPE=Q.REPO/'configs/data_v1/conformers/pilot_v1.json';WIRE=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/scripts/c_engineering_wire.py')
RECIPE_SHA256='cfd153fb524ad823d3903b0ff7d78e402bbbcb74e124136b4bfeb3035279407a'
MODES=('source','compat','profile','full','resume','coverage');TARGET=2500000;EACH=1250000;PROFILE=10000;SEED=20261025
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def key(mode):Q.need(mode in MODES,'EXACT_STAGE');return 'no_pm7_uff_d_main_v1_'+mode
def parameters(mode,lower,upper,cap):
    Q.need(mode in MODES and type(cap)is int and 2<<30<=cap<=128<<30 and type(lower)is int and type(upper)is int
        and (0<=lower<upper<=TARGET if mode in ('full','resume') else lower==upper==0),'EXACT_FINITE_STAGE_OR_FULL_INTERVAL')
    Q.need(mode!='full' or upper-lower<=1024,'FULL_IS_BOUNDED_MUTUALLY_EXCLUSIVE_INTERVAL_NOT_2P5M_ONE_JOB')
    Q.need(mode not in ('compat','profile','full') or cap>=16<<30,'32_PENDING_PRIVATE256M_PLUS_PARENT_DRAIN_REQUIRE_FINITE16GIB_MINIMUM')
    return {'mode':mode,'lower_inclusive':lower,'upper_exclusive':upper,'output_cap_bytes':cap,'workers':16,'maximum_pending_molecules':32,
        'first_batch_R':EACH,'first_batch_N':EACH,'first_batch_total':TARGET,'compat_molecules':32,'profile_molecules':PROFILE,
        'profile_selection':'one Random(20261025),sample5000 R then5000 N from range1250000;sampling order retained separately',
        'embedding_seed':'original science.seed_for(newMID,False)','order_seed':SEED,'desired_real_conformers':10,'candidate_requested':100,'maximum_candidates':300,
        'UFF':'original ETKDGv3/native UFF MinimizeTrajectory snapshot1/maxIts2000/energyTol1e-6/forceTol1e-4',
        'dedup_RMSD_A':0.5,'original_select_fill_and_three_orders_objects':True,'only_original_zero_return_embedding_fallback':True,
        'new_retry_or_PM7_QM_UFF_recipe_change':False,'PM7_pointers_HOF_coordinates_or_stereo_truth_fabricated':False,
        'unassigned_stereo':'TECHNICAL_UNKNOWN_NO_PM7_REFERENCE_NO_CHEMICAL_EXCLUSION','D20_original_objects_float64_no_Kappa':True,
        'D3_original_corrected_base':'6molecular_fields_plus_atom_SASA','modes_share_same_once_domain':True,
        'three_pure_methods_before_DATA_or_Budget':True,'dataset_version':'v2_candidate','training_eligible':False,'pool_release':False,
        'parent_family_packet_batch_maximum':128,'parent_family_serialized_buffer_soft_bytes':32<<20,
        'cost_overrun':'REPORT_AND_CONTINUE_QUALITY_UNCHANGED','quota_reserve_bytes':200000000000,'SBATCH_memory_requested':False}
def new_mid(version,cid,full_key):
    Q.need(isinstance(version,str) and version and type(cid)is int and 0<cid<2**63 and re.fullmatch('[A-Z]{14}-[A-Z]{10}-[A-Z]',full_key),'EXACT_PUBCHEM_SOURCE_IDENTITY')
    return 'expansion-pubchem:'+version+':'+str(cid)+':'+full_key
def once(population,recipe,source):return sha(canonical(['new-pubchem-no-pm7-UFF-D-v1',population,recipe,source['pubchem_version'],source['cid'],source['full_key'],source['source_row_sha256']]))
def source_parents(plan):
    rank=meta(plan['ranking_receipt_reference']);filtered=meta(rank['filtered_pool']);novel=meta(rank['novelty_receipt'])
    from workflows.expansion.ranking import release_gate
    screen=meta(filtered['screen']);regression=meta(filtered['regression']);release_gate(screen_receipt=screen,regression_receipt=regression,decontamination_receipt=filtered,novelty_receipt=novel)
    Q.need(rank['schema']=='expansion_nested_queues_v1' and rank['status']=='CANDIDATE_ORDER_COMPLETE_NO_CONFORMERS_COMPUTED'
        and rank['seed']==SEED and rank['queue_molecules_each']==5000000 and rank['first_batch_molecules_each']==EACH
        and rank['downstream_features_used'] is False,'REAL_FROZEN10M_ORDER_FIRST2P5M_NOT_PROPOSED_POOL')
    review=meta(plan['graph_source_review_reference']);Q.need(review['schema']=='ROOT_EXPANSION_PUBCHEM_GRAPH_SOURCE_REVIEW_V1'
        and review['status']=='APPROVED_FROZEN_SOURCE_GRAPH' and review['reviewer']=='root'
        and review['ranking_receipt_reference']==plan['ranking_receipt_reference'] and review['filtered_database_reference']==filtered['database']
        and review['feature_graph_field']=='isomeric_smiles' and review['preserve_source_smiles'] is True
        and review['same_actual_screen_producer_graph_semantics_reviewed'] is True,'ROOT_ACTUAL_FEATURE_CREATOR_STEREO_GRAPH_AUTHORITY_NOT_NAME_GUESS')
    Q.need(review['pubchem_version'] and review['pubchem_raw_source_reference']==screen['source'],'PUBCHEM_VERSION_AND_ORIGINAL_SOURCE_RECEIPT_BOUND')
    Q.need(review['MID_namespace']=='expansion-pubchem' and review['MID_formula']=='expansion-pubchem:{pubchem_version}:{cid}:{full_key}','ROOT_FROZEN_MID_FORMULA_CONTENT_ONLY_HASH_PATHS')
    parents=unique([plan['ranking_receipt_reference'],rank['filtered_pool'],rank['novelty_receipt'],filtered['screen'],filtered['regression'],
        filtered['exclusion_index'],plan['graph_source_review_reference'],review['pubchem_raw_source_reference']])
    return rank,filtered,review,unique([triple(rank['batch1']),triple(filtered['database'])]),parents
def catalog_paths():
    con=Q.REPO/'workflows/data_v1_final/conformers'
    return {'seed_science':con/'science.py','conformer_common':con/'common.py','selection':con/'selection.py','embedding':con/'n1_pprime2_pilot_v4/core.py',
        'generator':Q.REPO/'legacy/descriptor/dataset/rdkit_descriptor_generator.py','generator_schema':Q.REPO/'legacy/descriptor/dataset/descriptor_schema.py',
        'wire':WIRE,'D_names':Q.REPO/'workflows/data_v1_final/labels/common.py','family_writer':Q.REPO/'workflows/wp5/scripts/wp5_parquet_v2.py',
        'wire_runtime_schema':Path('/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime/phychem_mfm/data/descriptor_schema.py'),
        'wire_runtime_phase1_specs':Path('/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime/phychem_mfm/model/phase1_specs.py')}
def sources():
    labels=Q.REPO/'workflows/data_v1_final/labels';legacy=Q.REPO/'legacy/descriptor/dataset'
    return sorted(set([*(HERE/n for n in FILES),*F.source_paths(),*catalog_paths().values(),RECIPE,
        *labels.glob('*.py'),*(labels/'streaming_cpu_v1').glob('*.py'),
        *(p for p in (Q.REPO/'legacy/__init__.py',Q.REPO/'legacy/descriptor/__init__.py',legacy/'__init__.py') if p.is_file()),
        Q.REPO/'workflows/expansion/ranking.py',Q.REPO/'workflows/expansion/external_sort.py',Q.REPO/'workflows/expansion/common.py']))

def quality_reference(plan):
    """Optional real TRAIN reference;absence keeps full1.5 acceptance open."""
    ref=plan.get('quality_reference_review_reference')
    if ref is None:return None,[]
    review=meta(ref);Q.need(review['schema']=='ROOT_NO_PM7_UFF_D_MATCHED_TRAIN_REFERENCE_V1' and review['status']=='APPROVED_REFERENCE_APPLICATION_ONLY'
        and review['reviewer']=='root' and review['R_N_fit_as_TRAIN'] is False and review['same_D_function_units_and_family_field_map_reviewed'] is True
        and review['UFF_D3_vs_original_TRAIN_domain_difference_reviewed'] is True,'REAL_ROOT_MATCHED_REFERENCE_DOMAIN_NOT_RN_PSEUDOTRAIN')
    fields=meta(review['field_map_reference']);cfg=meta(review['original_mask_config_reference']);parents=[ref,review['field_map_reference'],review['original_mask_config_reference']]
    d=[f for f in fields if f['task'] in ('D20','D3')]
    from workflows.data_v1_final.labels.common import D20_NAMES
    # The actual name sets are checked by original task_components in the CPU
    # quality workers. No molecule/target values are inspected by this helper.
    Q.need(len(d)==27 and len({f['field_id'] for f in d})==27
        and {f['source_path'] for f in d if f['task']=='D20'}==set(D20_NAMES)
        and {f['source_path'] for f in d if f['task']=='D3'}=={'PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2','SASA_atom_A2'},'ACTUAL20_PLUS7_D_FAMILY_FIELD_MAP')
    for pin in cfg['adapter_source_pins']:Q.need(Q.pin(pin['path'])==pin,'ORIGINAL_MASK_SOURCE_PINS');parents.append(pin)
    if review.get('TRAIN_calibration_reference'):
        calibration=meta(review['TRAIN_calibration_reference']);domain=meta(review['TRAIN_reference_domain_reference'])
        Q.need(calibration['fit_role']=='TRAIN_ONLY' and domain['calibration_reference']==review['TRAIN_calibration_reference']
            and domain['coverage_fingerprint']==calibration['coverage_fingerprint'] and domain['fit_role']=='TRAIN_ONLY'
            and domain['actual_source_and_role_census_closed'] is True,'TRUE_TRAIN_PARENT_ROLE_AND_SOURCE_CENSUS_NOT_NEW_RN_FIT')
        Q.need(all(str(f['field_id']) in calibration['fields'] for f in d),'ALL27_ACTUAL_TRAIN_CALIBRATION_FIELDS')
        parents += [review['TRAIN_calibration_reference'],review['TRAIN_reference_domain_reference']]
    return review,unique(parents)

def fingerprint(catalog):
    return sha(canonical({'domain':'original-no-PM7-UFF-D-science-v1','source_sha256':{k:r['sha256'] for k,r in catalog['references'].items()},
        'original_science_sha256':[r['sha256'] for r in catalog['science_source_pins']],
        'recipe_sha256':catalog['recipe_reference']['sha256'],'python':'3.11.14','rdkit':'2025.09.5','target':10,'order_seed':SEED}))
def input_parents(plan):
    if plan['mode']=='resume':Q.need(plan['resume_selection_mode'] in ('compat','profile','full')
        and (plan['resume_selection_mode']=='full' or (plan['lower_inclusive']==0 and plan['upper_exclusive']==TARGET)),'EXACT_RESUME_SCOPE_NO_UNDECLARED_SELECTION_MODE')
    rank,filtered,review,source_data,parents=source_parents(plan);catalog=meta(plan['kernel_catalog_reference'])
    Q.need(catalog['schema']=='NO_PM7_UFF_D_ORIGINAL_KERNEL_CATALOG_V1' and catalog['recipe_reference']==Q.pin(RECIPE)
        and catalog['recipe_reference']['sha256']==RECIPE_SHA256
        and catalog['references']['wire']['sha256']=='ce9bbdf15459e647fc21592941c99664141b7d7a4442619f433c88a3536d99a1','ORIGINAL_FIXED_WIRE_AND_KERNEL_CATALOGUE')
    for name,path in catalog_paths().items():Q.need(catalog['references'][name]==Q.pin(path),'ORIGINAL_KERNEL_SOURCE_PIN:'+name)
    oldrecipe=meta(catalog['recipe_reference']);Q.need(catalog['science_source_pins']==oldrecipe['science_source_pins'],'ACTUAL_ORIGINAL_GRAPH_STEREO_RMSD_AND_PREPARE_PINS')
    for ref in catalog['science_source_pins']:Q.need(Q.pin(ref['path'])==ref,'FROZEN_OLD_GRAPH_STEREO_RMSD_SOURCE')
    parents=unique([*parents,plan['kernel_catalog_reference'],catalog['recipe_reference'],*catalog['references'].values(),*catalog['science_source_pins']])
    manifest=None;data=source_data
    if plan['mode']!='source':
        receipt=meta(plan['source_preparation_receipt_reference']);manifest_ref=receipt['source_manifest_reference'];manifest=meta(manifest_ref)
        Q.need(receipt['status']=='ORDERED_SOURCE_PREPARATION_COMPLETE_NO_UFF' and receipt['mode']=='source'
            and receipt['new_UFF_calls']==0 and manifest['status']=='ALL2500000_ORDERED_SOURCE_GRAPHS_PROJECTED_NO_UFF'
            and manifest['counts']=={'R':EACH,'N':EACH} and manifest['ranking_receipt_reference']==plan['ranking_receipt_reference']
            and manifest['graph_source_review_reference']==plan['graph_source_review_reference'] and manifest['pubchem_version']==review['pubchem_version']
            and manifest['recipe_reference']==catalog['recipe_reference'],'ACTUAL_COMPLETE_SOURCE_PRODUCER_NOT_PLACEHOLDER')
        _,raw=F.account(plan['source_preparation_accounting_reference'],receipt['job_id'],receipt['node'])
        proof=meta(receipt['startup_proof_reference']);Q.need(proof['request']['scope_key']==key('source') and receipt['uid']==proof['uid']==1278
            and str(proof['job_id'])==str(receipt['job_id']) and receipt['plan_reference'] in proof['request']['source_references'],'ACTUAL_MAIN_SOURCE_PREPARE_IDENTITY')
        parents=unique([*parents,plan['source_preparation_receipt_reference'],plan['source_preparation_accounting_reference'],raw,manifest_ref,receipt['startup_proof_reference'],receipt['plan_reference']])
        mode=plan.get('resume_selection_mode','full') if plan['mode']=='resume' else 'full' if plan['mode']=='coverage' else plan['mode']
        selected=set(manifest['compat_sample_order'] if mode=='compat' else manifest['profile_sample_order']) if mode in ('compat','profile') else None
        lower,upper=(0,TARGET) if plan['mode']=='coverage' else (plan['lower_inclusive'],plan['upper_exclusive'])
        parts=[p for p in manifest['parts'] if any(p['lower_inclusive']<=i<p['upper_exclusive'] for i in selected)] if selected is not None else [p for p in manifest['parts'] if p['lower_inclusive']<upper and p['upper_exclusive']>lower]
        data=[triple(p['reference']) for p in parts]
    if plan['mode'] in ('profile','full'):
        prev='compat' if plan['mode']=='profile' else 'profile';r=meta(plan['accepted_previous_receipt_reference'])
        _,raw=F.account(plan['accepted_previous_accounting_reference'],r['job_id'],r['node']);root=meta(plan['previous_stage_root_review_reference'])
        Q.need(r['schema']=='NO_PM7_UFF_D_COMPUTE_RECEIPT_V1' and r['mode']==prev and r['status']=='ALL_SELECTED_MOLECULES_TERMINAL_RECORDED_NO_RELEASE'
            and r['requested']==(32 if prev=='compat' else PROFILE) and r['source_preparation_receipt_reference']==plan['source_preparation_receipt_reference']
            and r['recipe_fingerprint']==fingerprint(catalog)
            and root['schema']=='ROOT_NO_PM7_UFF_D_PREVIOUS_STAGE_REVIEW_V1' and root['status']=='APPROVED_NEXT_BOUNDED_STAGE'
            and root['reviewer']=='root' and root['actual_receipt_reference']==plan['accepted_previous_receipt_reference']
            and root['actual_accounting_reference']==plan['accepted_previous_accounting_reference'] and root['UNKNOWN_failures_and_source_seam_reviewed'] is True
            and root['new_forcefield_stereo_or_chemical_rule'] is False,'REAL_COMPAT32_OR_PROFILE10000_COST_QUALITY_REVIEW')
        Q.need(r['compatibility_checked_conformers']>0 and r['compatibility_mismatches']==0,'ACTUAL_DIRECT_ORIGINAL_D3_VS_WIRE_SEAM_REQUIRED')
        oldproof=meta(r['startup_proof_reference']);Q.need(oldproof['uid']==1278 and str(oldproof['job_id'])==str(r['job_id'])
            and oldproof['request']['scope_key']==key(prev) and r['plan_reference'] in oldproof['request']['source_references'],'ACTUAL_PREVIOUS_STAGE_PRIMARY_STARTUP_IDENTITY')
        if prev=='profile':
            factor=root['descriptive_output_expansion_factor'];Q.need(type(factor)is int and factor>=1,'EXPLICIT_PROFILE_DERIVED_OUTPUT_BUDGET')
            observed=r['profile_variable_output_bytes'];per=(observed+9999)//10000
            Q.need(root['profile_variable_output_bytes']==observed and plan['output_cap_bytes']>=per*(plan['upper_exclusive']-plan['lower_inclusive'])*factor+(9<<30),
                'ACTUAL10000_BYTES_PLUS32_PRIVATE256M_AND1G_DRAIN_NOT_WORST_BOUND')
            Q.need(root['large_compute_over500_corehours_reviewed'] is True and root['first_batch_total']==TARGET and root['first_batch_R']==root['first_batch_N']==EACH,'ROOT_FULL2P5M_RANGE_COST_CONFIRMATION')
            actual_account=meta(plan['accepted_previous_accounting_reference']);actual_parent=next(p for p in actual_account['parents'] if p['job_id']==str(r['job_id']))
            actual_seconds=actual_parent['elapsed_raw_seconds']*actual_parent['alloc_cpus']
            Q.need(root['profile_actual_allocated_core_seconds']==actual_seconds and root['cost_projection_denominator_molecules']==PROFILE
                and root['observed_native_and_UNKNOWN_failure_counts']==r['molecule_states'] and root['observed_label_states']==r['label_states']
                and root['descriptive_not_worst_bound'] is True,
                'ACTUAL_10K_PARENT_COST_AND_ALL_UNKNOWN_STATES_IN_FULL_REVIEW')
        parents=unique([*parents,plan['accepted_previous_receipt_reference'],plan['accepted_previous_accounting_reference'],raw,plan['previous_stage_root_review_reference'],r['startup_proof_reference'],r['plan_reference']])
    if plan.get('reuse_snapshot_reference'):
        snap=meta(plan['reuse_snapshot_reference']);Q.need(snap['schema']=='NO_PM7_UFF_D_CLOSED_CACHE_SNAPSHOT_V1'
            and snap['ranking_receipt_reference']==plan['ranking_receipt_reference'] and snap['recipe_fingerprint']==fingerprint(catalog),'SAME_POPULATION_RECIPE_ACTUAL_CLOSED_REUSE_SNAPSHOT')
        _,snapraw=F.account(plan['reuse_accounting_reference'],snap['job_id'],snap['node']);sp=meta(snap['startup_proof_reference'])
        Q.need(sp['uid']==1278 and str(sp['job_id'])==str(snap['job_id']) and sp['request']['scope_key']==key('resume'),'ACTUAL_CPU_RESUME_C0_PROOF_REQUIRED_NOT_HANDWRITTEN_CACHE_INDEX')
        if plan['mode']=='coverage':Q.need(snap['selection_mode']=='full' and snap['lower_inclusive']==0 and snap['upper_exclusive']==TARGET
            and snap['checked_source_molecules']==TARGET,'COVERAGE_REQUIRES_WHOLE2P5M_ACTUAL_RESUME_CENSUS')
        data=unique([*data,*(triple(p['reference']) for p in snap['parts']),triple(snap['verified_parent_metadata_DATA_reference'])])
        parents=unique([*parents,plan['reuse_snapshot_reference'],plan['reuse_accounting_reference'],snapraw,snap['startup_proof_reference'],*snap['parent_metadata_references']])
    elif plan['mode'] in ('profile','full','coverage'):Q.need(False,'CLOSED_CACHE_CPU_RESUME_SNAPSHOT_REQUIRED_BEFORE_EXISTING_ONCE_REUSE')
    if plan['mode']=='resume':
        runs=meta(plan['prior_runs_reference']);Q.need(runs['schema']=='ROOT_NO_PM7_UFF_D_ACTUAL_PRIOR_RUNS_V1' and runs['reviewer']=='root'
            and runs['status']=='TERMINAL_ACCOUNTING_LOCATORS_ONLY_NOT_PACKET_ACCEPTANCE','REAL_TERMINAL_PARENT_LOCATORS')
        parents=unique([*parents,plan['prior_runs_reference'],*runs.get('parts',[])])
    quota=meta(plan['quota_reuse_reference']);F.Provider.load_review(quota['provider_review_reference'])
    parents=unique([*parents,plan['quota_reuse_reference'],*F.Provider.references(quota['provider_review_reference']),quota['provider_actual_launch_reference'],quota['publisher_identity_reference'],quota['resource_epoch_root_binding_reference']])
    _,qrefs=quality_reference(plan);parents=unique([*parents,*qrefs])
    return manifest,catalog,review,unique(data),parents
