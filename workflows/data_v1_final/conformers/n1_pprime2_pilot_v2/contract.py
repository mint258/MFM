"""N1 identities, immutable source bindings and pure selection boundaries."""
from __future__ import annotations
import copy,hashlib,importlib.util,json,math,pathlib,re

SEED_DOMAIN='sprime-ETKDGv3-v1-n1-pprime2:'
SOURCE_N=1;UFF_DESIRED=2;CANDIDATES=10;MAX_CANDIDATES=300;THRESHOLD_A=0.5;ORDER_SEED=20261025
SCOPE_KEY='n1_pprime2_pilot32_v2'
SCOPE={'source_pm7_n1_mother_population':5040,'pilot_molecules':32,'PM7_source_count':1,
    'retained_baseline_count':1,'UFF_desired_count':2,'candidate_requested_per_molecule':10,
    'max_candidate_cap':300,'seed_domain':SEED_DOMAIN,'rdkit_version':'2025.09.5',
    'dedup_rmsd_A':0.5,'uff_max_iterations':2000,'uff_energy_tolerance':1e-6,
    'uff_force_tolerance':1e-4,'new_QM_calls':0,'automatic_retry':False,
    'same_geometry_SHA_cannot_create_second_row':True,'production_population_release':False,
    'source_population_authority':'ORIGINAL_N1_ROLES_AND_VERIFIED_BASELINE',
    'final_common_authority_required':False,'common':False,'pilot_membership':False,
    'whole_output_cap_bytes':8589934592}
PREP_SCOPE_KEY='n1_pprime2_prepare32_v2'
PREP_SCOPE={'source_pm7_n1_mother_population':5040,'pilot_molecules':32,'new_UFF_calls':0,'new_QM_calls':0,
    'source_payload_graph_stereo_checks':True,'source_pointers_from_bound_canonical_index_only':True,
    'final_common_authority_required':False,'common':False,'pilot_membership':False,
    'whole_output_cap_bytes':8589934592}


def need(value,message):
    if not value:raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def sha_value(value):return hashlib.sha256(canonical(value)).hexdigest()


def proposed_seed(mid):
    need(isinstance(mid,str) and mid,'MOLECULE_ID_REQUIRED')
    value=int.from_bytes(hashlib.sha256((SEED_DOMAIN+mid).encode()).digest()[:4],'big')
    return max(value&0x7fffffff,1)


def task_key(mid):
    return hashlib.sha256(('n1-pprime2-once-generation-v1:'+mid).encode()).hexdigest()


def reference_shape(ref):
    need(isinstance(ref,dict) and set(ref)=={'path','bytes','sha256'},'EXACT_REFERENCE_TRIPLE_REQUIRED')
    need(isinstance(ref['path'],str) and pathlib.Path(ref['path']).is_absolute()
        and '..' not in pathlib.Path(ref['path']).parts,'ABSOLUTE_LITERAL_REFERENCE_REQUIRED')
    need(type(ref['bytes']) is int and ref['bytes']>0 and isinstance(ref['sha256'],str)
        and re.fullmatch('[0-9a-f]{64}',ref['sha256']),'POSITIVE_BYTES_AND_EXACT_SHA_REQUIRED')
    return ref


def pinned_small(ref):
    reference_shape(ref);need(ref['bytes']<=1<<20,'SMALL_SOURCE_METADATA_ONLY')
    path=pathlib.Path(ref['path']);need(path.is_file() and not path.is_symlink(),'REGULAR_PINNED_SOURCE_REQUIRED')
    with path.open('rb') as stream:body=stream.read((1<<20)+1)
    need(len(body)==ref['bytes'] and hashlib.sha256(body).hexdigest()==ref['sha256'],'FROZEN_SMALL_SOURCE_CHANGED')
    return path


def module_from_pin(name,ref):
    path=pinned_small(ref);spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def load_catalog(ref):
    value=json.loads(pinned_small(ref).read_text(encoding='utf-8'))
    need(value.get('schema')=='N1_PPRIME2_PILOT_DEPENDENCIES_V2','FROZEN_SOURCE_CATALOG_REQUIRED')
    need(value.get('seed_domain')==SEED_DOMAIN and value.get('source_N')==1
        and value.get('uff_desired_count')==2 and value.get('candidate_requested')==10
        and value.get('cap')==300 and value.get('rdkit_version')=='2025.09.5'
        and value.get('expected_source_pm7_n1_molecules')==5040,'N1_SCIENCE_SCOPE_CHANGED')
    expected={'io','selection','original_fill_reference_only','graph_stereo_rmsd',
        'legacy_prepare_import','recipe','proposal_source_reference_only','proposal_config_reference_only'}
    need(set(value['references'])==expected,'EXACT_FROZEN_DEPENDENCY_ROLES_REQUIRED')
    for item in value['references'].values():pinned_small(item)
    need(len(value['inherited_v1_sources'])==6,'UNCHANGED_V1_SIX_SOURCES_REQUIRED')
    for item in value['inherited_v1_sources']:pinned_small(item)
    return value


def validate_task(task,source_population_authority_reference):
    """Prepared metadata is trusted only through Root's pinned CPU preparation.

    The core still rechecks actual source graph, atom order, stereo, baseline
    geometry/energy and payload SHA. A True membership flag alone is no authority.
    """
    need(task.get('schema')=='N1_PPRIME2_PILOT_TASK_V2','NEW_N1_PREPARED_TASK_REQUIRED')
    meta=task['meta'];mid=meta['molecule_id'];seed=proposed_seed(mid)
    need(task['task_key']==task_key(mid),'NEW_INDEPENDENT_ONCE_TASK_KEY_REQUIRED')
    for key,value in (('PM7_source_count',1),('source_N',1),('accepted_baseline_count',1),('UFF_desired_count',2)):
        need(type(meta.get(key)) is int and meta[key]==value,'SOURCE_N1_AND_UFF_TARGET2_MUST_BE_SEPARATE:'+key)
    need(len(task['records'])==1 and len(task['existing_conformers'])==1,'ONE_PM7_POINTER_AND_ONE_ACCEPTED_BASELINE_REQUIRED')
    need(meta.get('final_common_member') is False and meta.get('common') is False
        and meta.get('pilot_membership') is False and meta.get('production_membership') is False
        and task.get('final_common_reference') is None and meta.get('effective_role') in {'TRAIN','VAL'}
        and meta.get('Sprime_status')!='UFF_UNSUPPORTED','PILOT_ONLY_FROZEN_ROLES_NO_FAKE_FINAL_COMMON')
    refs=task['authority_references']
    need(set(refs)=={'source_population_authority','source_pointer_manifest','accepted_baseline_evidence','roles_manifest'},
        'COMPLETE_PREPARATION_PARENT_REFERENCES_REQUIRED')
    for ref in refs.values():reference_shape(ref)
    need(refs['source_population_authority']==source_population_authority_reference,'ACTUAL_SOURCE_POPULATION_AUTHORITY_REQUIRED')
    pointer=task['records'][0];baseline=task['existing_conformers'][0]
    need(pointer['molecule_id']==mid and baseline['molecule_id']==mid,'MOLECULE_POINTER_BASELINE_ID_MISMATCH')
    need(baseline['status']=='SUCCESS' and baseline['converged'] is True
        and type(baseline['sprime_conf_idx']) is int and baseline['sprime_conf_idx']==0,'ONE_VALID_ORIGINAL_BASELINE_REQUIRED')
    need(type(baseline['seed']) is int and baseline['seed']!=seed,'NEW_PROPOSAL_SEED_MUST_DIFFER_FROM_BASELINE')
    need(task['baseline_row_sha256']==sha_value(baseline),'BASELINE_FULL_ROW_CANONICAL_SHA_CHANGED')
    need(isinstance(task.get('baseline_geometry_id'),str) and task['baseline_geometry_id'], 'ORIGINAL_BASELINE_GEOMETRY_ID_REQUIRED')
    return meta,pointer,baseline,seed


def select_real_second(mid,baseline,candidates,distance,selection):
    """Pure admission/selection of core-produced events, not proof of real calls.

    Original identity SHA is protected. Different SHA but RMSD<0.5 remains the
    frozen select_fill fallback. All input rows/events are left unchanged.
    """
    need(baseline['origin']=='accepted_sprime' and baseline['geometry_sha256'], 'VALIDATED_REAL_BASELINE_REQUIRED')
    need(len(candidates)<=CANDIDATES,'SOURCE_N1_CANNOT_EXCEED10_OPTIMIZATION_EVENTS')
    seen_keys={baseline['candidate_key']};seen_ids=set();seen_sha={baseline['geometry_sha256']}
    seed=proposed_seed(mid);eligible=[];excluded=[];valid=[]
    for candidate in candidates:
        row=copy.deepcopy(candidate)
        need(row['origin']=='data_v1_n1_pprime2' and row['seed']==seed and row['seed']!=baseline['seed'],
            'ORIGINAL_PROPOSAL_SEED_AND_NEW_CANDIDATE_ORIGIN_REQUIRED')
        need(type(row['candidate_id']) is int and row['candidate_id']>=0,'REAL_NATIVE_CANDIDATE_ID_REQUIRED')
        need(row['candidate_key'] not in seen_keys and row['candidate_id'] not in seen_ids,'DUPLICATE_NATIVE_CANDIDATE_ID')
        seen_keys.add(row['candidate_key']);seen_ids.add(row['candidate_id'])
        need(row.get('optimizer_called') is True and row.get('optimization_finished') is True,
            'ACTUAL_FINISHED_OPTIMIZATION_EVENT_REQUIRED')
        if row.get('finite') is not True or type(row.get('optimizer_code')) is not int or row['optimizer_code']!=0 or row.get('stereo_valid') is not True:
            excluded.append({'candidate_key':row['candidate_key'],'reason':'NOT_FINITE_CONVERGED_AND_STEREO_VALID'});continue
        need(math.isfinite(float(row['energy'])),'FINITE_UFF_ENERGY_REQUIRED')
        sha=row['geometry_sha256'];need(isinstance(sha,str) and re.fullmatch('[0-9a-f]{64}',sha),'ACTUAL_GEOMETRY_SHA_REQUIRED')
        valid.append(row)
    # Same-identity events stay in the audit. A representative follows the
    # frozen energy/candidate-key ordering rather than raw event arrival order.
    for row in sorted(valid,key=lambda item:(item['energy'],item['candidate_key'])):
        sha=row['geometry_sha256']
        if sha in seen_sha:
            excluded.append({'candidate_key':row['candidate_key'],'reason':'GEOMETRY_SHA_ALREADY_PRESENT'});continue
        seen_sha.add(sha);eligible.append(row)
    selected=selection.select_fill([baseline],eligible,UFF_DESIRED,distance,THRESHOLD_A)
    pool=selection.select_fill([baseline],eligible,1+len(eligible),distance,THRESHOLD_A)
    second=selected[1] if len(selected)==2 else None
    return {'second':second,'eligible_geometry_candidates':len(eligible),'identity_or_quality_exclusions':excluded,
        'candidate_pool_unique_at_0p5_A':sum(not row['below_dedup_threshold'] for row in pool),
        'selected_unique_at_0p5_A':sum(not row['below_dedup_threshold'] for row in selected),
        'Pprime_actual_records':len(selected),'status':'REAL_SECOND_GEOMETRY_SELECTED' if second else 'PPRIME2_PENDING_NO_SECOND_REAL_GEOMETRY'}


def expanded_orders(mid,baseline,second,distance,selection):
    need(second is not None and second['geometry_sha256']!=baseline['geometry_sha256'],'SECOND_REAL_GEOMETRY_IDENTITY_REQUIRED')
    rows=[dict(baseline,conformer_id=0),dict(second,conformer_id=f"n1p2:{second['seed']}:{second['candidate_id']}")]
    return selection.conformer_orders(rows,distance,mid,'uff_sprime',ORDER_SEED)


def pilot32(rows,selection):
    """Only a deterministic subset helper; no parent table/common scan is implied."""
    mids=[row['meta']['molecule_id'] for row in rows]
    need(len(mids)==len(set(mids)),'DUPLICATE_PILOT_MOLECULE')
    ordered=sorted(rows,key=lambda row:(selection.stable_key(ORDER_SEED,row['meta']['molecule_id'],'n1_pprime2_pilot',0),row['meta']['molecule_id']))
    return {'status':'EXACT32_AVAILABLE' if len(ordered)>=32 else 'INSUFFICIENT32_NO_AUTOMATIC_WIDENING',
        'eligible_count':len(rows),'tasks':ordered[:32] if len(ordered)>=32 else []}
