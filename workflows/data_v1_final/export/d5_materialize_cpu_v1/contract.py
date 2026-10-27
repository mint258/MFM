"""Small authority seams; DATA locators are never opened on the login node."""
from __future__ import annotations
import csv,io,re,time
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q

ROOT=Q.ROOT;REPO=Q.REPO;PY=Q.PY
HERE=REPO/'workflows/data_v1_final/export/d5_materialize_cpu_v1'
EXPORT=REPO/'workflows/data_v1_final/export'
MODULE='workflows.data_v1_final.export.d5_materialize_cpu_v1.run'
FILES=('__init__.py','contract.py','metadata.py','resources.py','produce.py','readback.py','run.py','test_boundaries.py','frozen_sources.json','README.md')
COUNTS={'nested_TRAIN':[120000,240000,600000],'pilot_TRAIN':50000,'pilot_ROUTINE_VAL':5000,'diagnostic_TRAIN':20000}
PARENTS=('roles_authority','common_manifest','order_manifest','geometry_authority',
         'atom_counts_authority','N1_policy','input_view_review')
TABLES=('roles','common','geometries','orders','features','atom_counts')
COLUMNS={'roles':('molecule_id','effective_role','source_role'),
    'common':('molecule_id','common_population'),
    'geometries':('geometry_id','molecule_id','geometry_source','native_record_id','sprime_conf_idx','parent_geometry_id','view_id'),
    'orders':('molecule_id','geometry_source','order_type','rank','geometry_id'),
    'features':('molecule_id','element_z','heavy_atoms','scaffold_id'),'atom_counts':('geometry_id','n_atoms')}
WALL={'materialize':7200,'readback':7200}
CAP={'materialize':64<<30,'readback':2<<30}
RELEASE_SCHEMA='ROOT_D5_ORDINARY_FINAL_INPUT_RELEASE_V1'
need=Q.need


def reference(v,*,source=False):
    need(type(v) is dict and set(v)>={'path','bytes','sha256'},'EXACT_REFERENCE_REQUIRED')
    p=v['path'];need(type(p) is str and p.startswith('/') and '..' not in p.split('/') and '\\' not in p,'ABSOLUTE_LITERAL_MAIN_REFERENCE')
    need(type(v['bytes']) is int and v['bytes']>=(0 if source else 1),'POSITIVE_DATA_NOT_BOOL_SOURCE_MAY_BE_ZERO')
    need(type(v['sha256']) is str and re.fullmatch('[0-9a-f]{64}',v['sha256']) is not None,'EXACT64_LOWERCASE_SHA256')
    if v['bytes']==0:need(v['sha256']=='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855','EXACT_EMPTY_SOURCE_SHA')
    return {k:v[k] for k in ('path','bytes','sha256')}


def unique(refs):
    out={}
    for raw in refs:
        r=reference(raw,source=True)
        need(r['path'] not in out or out[r['path']]==r,'CONFLICTING_REFERENCE_FOR_SAME_PATH')
        out[r['path']]=r
    return [out[k] for k in sorted(out)]


def meta(ref):
    ref=reference(ref,source=True);need(ref['bytes']<=2<<20,'SMALL_METADATA_ONLY_NOT_DATA')
    need(Q.pin(ref['path'])==ref,'ACTUAL_SMALL_METADATA_CHANGED')
    return Q.load(ref['path'])


def parameters(mode,seed):
    need(mode in WALL and type(seed) is int and 0<=seed<2**63,'EXACT_MODE_AND_REVIEWED_SEED')
    return {'mode':mode,'seed':seed,'counts':COUNTS,'sampling_algorithm':'SHA256-uniform-order-v1',
        'ordinary_sources':['pm7','uff_sprime'],'worker_processes':16,'maximum_pending_row_groups':32,
        'source_boundary_methods':3,'new_QM_UFF_calls':0,'original_selection_function_object':True,
        'Pprime_extra_in_ordinary_sprime':False,'diagnostic_excludes_base_and_all_direct_children':True,
        'minimum_energy':'retained energy training_rank=0','D5_jointly_frozen':False,
        'wall_seconds':WALL[mode],'whole_output_cap_bytes':CAP[mode]}


def pending(request):
    supplied=request.get('parent_references',{})
    need(type(supplied) is dict and set(supplied)<=set(PARENTS),'UNKNOWN_D5_PARENT')
    for r in supplied.values():reference(r)
    absent=sorted(set(PARENTS)-set(supplied))
    if type(request.get('seed')) is not int or not 0<=request['seed']<2**63:absent.append('independently_reviewed_fixed_seed')
    if not request.get('final_input_release_reference'):absent.append('independent_Root_final_input_release')
    for key in ('quota_reuse_reference','resource_authority_reference','cost_decision_reference'):
        if not request.get(key):absent.append(key)
    if request.get('mode')=='readback' and not request.get('materialize_closure_references'):absent.append('actual_materialize_C0_closure')
    return {'schema':'D5_CPU_MATERIALIZER_PENDING_V1','status':'NONEXECUTABLE_PENDING_ACTUAL_PARENTS',
        'missing_parents':absent,'parent_references':supplied,'stage_spec_generated':False,
        'scientific_DATA_opened_statted_or_hashed':False,'D5_jointly_frozen':False,'new_QM_UFF_calls':0}


def account(ref,job,node):
    a=meta(ref);raw=reference(a['raw_sacct_reference']);body=Q.read_small(raw['path'])
    need(Q.pin(raw['path'])==raw,'ACTUAL_ACCOUNT_RAW_CHANGED')
    rows=[r for r in csv.DictReader(io.StringIO(body.decode()),delimiter='|') if '.' not in r['JobIDRaw']]
    need(a['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and a['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
        and a['endpoint']=='202.38.247.57:22' and a['uid']==1278 and a['query_returncode']==0
        and a['failed_timeout_startup_cleanup_elapsed_retained'] is True,'ACTUAL_MAIN_ACCOUNT_CLOSURE')
    by={r['JobIDRaw']:r for r in rows};need(len(by)==len(rows)==len(a['parents']),'EXACT_ACCOUNT_PARENT_SET')
    total=0
    for p in a['parents']:
        r=by[p['job_id']]
        need(p['state']==r['State'] and p['exit_code']==r['ExitCode'] and p['node']==r['NodeList']
            and p['alloc_cpus']==int(r['AllocCPUS']) and p['elapsed_raw_seconds']==int(r['ElapsedRaw'])
            and r['UID']=='1278','ACCOUNT_RAW_AND_PARENT_AGREE')
        total+=p['alloc_cpus']*p['elapsed_raw_seconds']
    need(total==a['allocated_core_seconds'],'ALL_ACTUAL_COST_RETAINED')
    r=by[str(job)];need(r['State']=='COMPLETED' and r['ExitCode']=='0:0' and r['NodeList']==node
        and int(r['AllocCPUS'])==16,'ACTUAL_PARENT_C0_CPU16')
    return raw


def common_parent(chain):
    need(type(chain) is dict and set(chain)=={'manifest','entry','accounting'},'EXACT_COMMON_PARENT_CHAIN')
    m=meta(chain['manifest']);e=meta(chain['entry']);p=meta(e['startup_proof_reference']);env=m['runtime']
    out=Path(chain['entry']['path']).parent
    need(m['schema']==m['status']=='COMMON_POPULATION_V1_FROZEN' and m['pilot_only'] is False
        and env['uid']==1278 and env['cpus']==16,'ACTUAL_FULL_COMMON_NOT_PROFILE_OR_CANDIDATE')
    need(Path(chain['entry']['path']).name=='finalizer_entry_adaptation.json' and Path(chain['manifest']['path'])==out/'manifest.json'
        and Path(e['actual_fixture_reference']['path']).parent==out and Path(e['source_inverse_reference']['path']).parent==out
        and e['schema']=='SPRIME_FINALIZER_EXACT_MOUNT_ENTRY_ADAPTATION_V2'
        and str(e['job_id'])==str(env['job_id'])==str(p['job_id']) and e['uid']==p['uid']==1278
        and e['node']==env['node']==p['request']['node'],'SAME_ACTUAL_COMMON_ENTRY_AND_PROOF')
    f=meta(e['actual_fixture_reference']);s=meta(e['source_inverse_reference'])
    need(f['status']=='PASS' and f['tests_run']==8 and s['status']=='EXACT_SOURCE_INVERSE_AND_SCIENCE_AST_EQUAL'
        and s['entire_file_inverse_equal'] is True and s['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COMMON_SOURCE_AND8_BOUNDARIES')
    need(all(r in p['request']['source_references'] for r in e['actual_new_source_references']),'ACTUAL_COMMON_SOURCE_PINS')
    raw=account(chain['accounting'],env['job_id'],env['node'])
    need(len(m['membership_tables'])==16 and len(m['physical_geometry_tables'])==32,'WHOLE_COMMON16_AND_PHYSICAL32')
    refs=[*chain.values(),raw,e['startup_proof_reference'],e['actual_fixture_reference'],e['source_inverse_reference']]
    return m,refs


def derive(plan):
    release=meta(plan['final_input_release_reference']);parents=plan['parent_references']
    need(set(parents)==set(PARENTS) and release['schema']==RELEASE_SCHEMA
        and release['status']=='ROOT_APPROVED_EXACT_ORDINARY_D5_INPUTS' and release['reviewer']=='root'
        and release['parent_references']==parents,'INDEPENDENT_EXACT_ROOT_D5_INPUT_RELEASE')
    need(release['guide_counts']==COUNTS and release['seed']==plan['seed']
        and release['sampling_algorithm']=='SHA256-uniform-order-v1','ORIGINAL_COUNTS_RANDOM_ALGORITHM_AND_SEED')
    for flag in ('scientific_quality_thresholds_unchanged','Se_exception_only','ROUTINE_molecule_VAL_all_geometries',
                 'ordinary_sprime_only','no_extra_N1_inflation_of_diagnostic_eligibility',
                 'all_actual_perturbation_children_in_geometry_authority','no_Pprime_values_required_or_substituted',
                 'N1_N2_and_insufficient_k_policy_reviewed','source_ownership_and_parent_chains_reviewed'):
        need(release.get(flag) is True,'ROOT_D5_INPUT_BOUNDARY:'+flag)
    common,more=common_parent(release['common_closure_references'])
    need(release['common_closure_references']['manifest']==parents['common_manifest'],'SAME_RELEASE_COMMON')
    roles=meta(parents['roles_authority']);source_roles=meta(roles['source_role_manifest'])
    need(roles['status']=='FROZEN' and roles['validation_source']=='ROUTINE' and roles['all_conformers_same_role'] is True
        and source_roles['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN'
        and common['roles_manifest']==roles['source_role_manifest']
        and common['roles_manifest_sha256']==roles['source_role_manifest']['sha256'],'WHOLE_ROUTINE_ROLES_NOT_RECORD_SUBSET')
    order=meta(parents['order_manifest']);geo=meta(parents['geometry_authority']);atoms=meta(parents['atom_counts_authority'])
    policy=meta(parents['N1_policy']);views=meta(parents['input_view_review'])
    need(order['status']=='CONFORMER_ORDER_V1_FROZEN' and order['common_population_manifest_sha256']==parents['common_manifest']['sha256']
        and order['roles_manifest_sha256']==roles['source_role_manifest']['sha256'] and order['rank_base']==0
        and set(order['order_types'])=={'fixed_random','energy','diversity'},'ACTUAL_FULL_ORDERS_NOT_COMMON_ORDERS_FALSE')
    need(geo['status']=='ROOT_REVIEWED_ACTUAL_D5_GEOMETRY_TABLES' and geo['reviewer']=='root'
        and geo['common_manifest_reference']==parents['common_manifest'] and geo['ordinary_physical_tables']==common['physical_geometry_tables']
        and geo['geometry_tables']==order['source_geometry_tables'],'ROOT_ACTUAL_BASE_ALL_CHILD_GEOMETRY_AUTHORITY')
    need(atoms['status']=='ROOT_REVIEWED_ACTUAL_D5_ATOM_COUNTS' and atoms['reviewer']=='root'
        and atoms['geometry_authority_reference']==parents['geometry_authority'],'ACTUAL_NATIVE_ATOM_COUNTS_NOT_INFERRED')
    need(policy['status']=='ROOT_REVIEWED_N1_N2_ORDINARY_D5_POLICY' and policy['reviewer']=='root'
        and policy['common_manifest_reference']==parents['common_manifest'] and policy['ordinary_sprime_count_unchanged'] is True
        and policy['Pprime_extra_not_ordinary'] is True,'INDEPENDENT_N1_ORDINARY_DOMAIN_POLICY')
    need(views['status']=='ROOT_REVIEWED_EXACT_D5_INPUT_COLUMNS' and views['reviewer']=='root'
        and views['common_manifest_reference']==parents['common_manifest'],'ACTUAL_INPUT_COLUMN_VIEW_REVIEW')
    need('feature_filter_column' in views and (views['feature_filter_column'] is None or
        type(views['feature_filter_column']) is str and bool(views['feature_filter_column'])),'EXPLICIT_FEATURE_FILTER_NOT_GUESSED')
    for authority in (geo,atoms,order,policy):
        need(type(authority.get('actual_parent_chains')) is list and authority['actual_parent_chains'],'REAL_CLOSED_PARENT_CHAIN_REQUIRED')
        for c in authority['actual_parent_chains']:
            m=meta(c['manifest']);p=meta(c['startup_proof']);env=m.get('runtime',m)
            need(str(c['job_id'])==str(p['job_id'])==str(env['job_id']) and p['uid']==1278
                and c['node']==p['request']['node'] and c['manifest_status']==m['status']
                and not any(w in m['status'].upper() for w in ('CANDIDATE','SOURCE_ONLY','FIXTURE','PROFILE','PENDING','HOLD','INCOMPLETE')),'TRUE_PARENT_NOT_SOURCE_OR_PARTIAL')
            more += [*([c[k] for k in ('manifest','startup_proof','accounting')]),account(c['accounting'],c['job_id'],c['node'])]
    role_tables=[reference(r) for r in source_roles['outputs'] if '/molecule_roles/' in r['path']]
    need(len(role_tables)==16,'ALL16_AUTHORITY_MOLECULE_ROLE_PARTS')
    tables={'roles':role_tables,'common':[reference(r) for r in common['membership_tables']],
        'geometries':[reference(r) for r in geo['geometry_tables']],'orders':[reference(r) for r in order['order_tables']],
        'features':[reference(r) for r in views['feature_tables']],'atom_counts':[reference(r) for r in atoms['tables']]}
    need(all(tables.values()) and set(views['columns'])==set(TABLES),'ALL_REVIEWED_TABLES_AND_LITERAL_COLUMN_MAPS')
    for kind,refs in tables.items():need(len({r['path'] for r in refs})==len(refs),'NO_REPEATED_PHYSICAL_TABLE_WITHIN_KIND:'+kind)
    for kind,names in COLUMNS.items():
        mapping=views['columns'][kind]
        need(type(mapping) is dict and set(mapping)==set(names) and all(type(v) is str and v for v in mapping.values())
            and len(set(mapping.values()))==len(mapping),'EXACT_REVERSIBLE_INPUT_COLUMN_NAMES:'+kind)
    boundary=Q.load(HERE/'frozen_sources.json')
    selection=next(r for r in boundary['files'] if r['relative_path']=='workflows/data_v1_final/conformers/selection.py')
    selection_ref={'path':str(REPO/selection['relative_path']),'bytes':selection['bytes'],'sha256':selection['sha256']}
    expected_order_sources=unique([selection_ref,*boundary['external_scientific_sources']])
    need(unique(views['original_order_source_references'])==expected_order_sources
        and views['original_order_function_objects_verified'] is True
        and type(views['conformer_order_seed']) is int and 0<=views['conformer_order_seed']<2**63
        and order['order_seed']==views['conformer_order_seed']
        and views['order_identity']=={'pm7':'native_record_id','uff_sprime':'sprime_conf_idx_int64'}
        and views['distance_policy']=='FIXED_SOURCE_ATOM_MAPPING_HEAVY_ATOMS_PROPER_KABSCH'
        and views['energy_policy']=={'pm7':'PM7_HOF_kcal_mol','uff_sprime':'UFF_energy_kcal_mol'},'ORIGINAL_THREE_ORDER_SCIENCE_SOURCE_SEED_AND_PHYSICAL_IDENTITIES')
    for ref in expected_order_sources:need(Q.pin(ref['path'])==ref,'ACTUAL_ORIGINAL_ORDER_SOURCE_BYTES')
    data=unique([r for refs in tables.values() for r in refs]+[reference(r) for r in common['physical_geometry_tables']])
    sources=unique([plan['final_input_release_reference'],*parents.values(),roles['source_role_manifest'],*more,*expected_order_sources])
    return release,tables,views['columns'],data,sources


def materialize_parent(chain,mode='materialize'):
    need(type(chain) is dict and set(chain)=={'receipt','startup_proof','accounting'},'EXACT_ACTUAL_MATERIALIZE_C0_CHAIN')
    r=meta(chain['receipt']);p=meta(chain['startup_proof']);plan=meta(r['plan_reference'])
    expected='ORDINARY_D5_LISTS_WRITTEN_READBACK_REQUIRED' if mode=='materialize' else 'ORDINARY_D5_FULL_READBACK_OBSERVED_ROOT_PUBLICATION_PENDING'
    need(r['schema']=='D5_CPU_LISTS_RECEIPT_V1' and r['status']==expected
        and r['mode']==mode and str(r['job_id'])==str(p['job_id']) and p['uid']==1278
        and r['node']==p['request']['node'] and r['startup_proof_reference']==chain['startup_proof']
        and p['request']['scope_key']=='d5_ordinary_'+mode+'_cpu_v1'
        and p['request']['scope_parameters']==parameters(mode,plan['seed'])
        and r['plan_reference'] in p['request']['source_references']
        and Path(chain['receipt']['path'])==Path(plan['output_directory'])/'receipt.json','ACTUAL_SAME_MATERIALIZER_PLAN_AND_STARTUP')
    f=meta(r['source3_reference']);o=meta(r['resource_observation_reference'])
    need(f['tests_run']==3 and all(f[k]==0 for k in ('failures','errors','skips'))
        and o['status']=='RESOURCE_OBSERVATION_CLOSED' and o['soft_stop_requested'] is False
        and str(o['job_id'])==str(r['job_id']) and r['error'] is None,'ACTUAL_SOURCE3_RESOURCE_AND_COMPLETE_PARENT')
    raw=account(chain['accounting'],r['job_id'],r['node'])
    return r,plan,unique([*chain.values(),raw,r['plan_reference'],r['source3_reference'],r['resource_observation_reference']])


def inputs(plan):
    release,tables,columns,data,parents=derive(plan)
    quota=meta(plan['quota_reuse_reference'])
    from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import quota_provider as P
    reviewed=P.load_review(quota['provider_review_reference'])
    need(quota['schema']=='ROOT_D5_QUOTA_FACT_REUSE_REVIEW_V1' and quota['status']=='APPROVED_RESOURCE_FACT_REUSE_ONLY'
        and quota['reviewer']=='root' and quota['compute_node']=='compute-0-13'
        and type(quota['whole_wave_output_reserve_bytes']) is int and quota['whole_wave_output_reserve_bytes']>=0,
        'REAL_CPU13_STORAGE_ACCOUNT_PROVIDER_AND_WHOLE_WAVE_RESERVE')
    identity=meta(quota['publisher_identity_reference']);first=meta(quota['first_healthy_snapshot_reference'])
    meta(quota['provider_actual_launch_reference'])
    need(identity['schema']==P.IDENTITY_SCHEMA and identity['review_reference']==quota['provider_review_reference']
        and first['observed_unix_seconds']<=time.time()
        and quota['actual_publisher_identity_launch_first_health_reviewed'] is True,'ACTUAL_FINITE_ROOT_APPROVED_PUBLISHER_CHAIN')
    # This verifies a historical source fact only; actual runtime still calls the
    # unmodified Client with real current time and locks this same identity.
    P.validate_observation(first,identity,quota['publisher_identity_reference'],reviewed,
        quota['provider_review_reference'],first['observed_unix_seconds'])
    parents += [plan['quota_reuse_reference'],quota['publisher_identity_reference'],quota['first_healthy_snapshot_reference'],
        quota['provider_actual_launch_reference'],*P.references(quota['provider_review_reference'])]
    old=None
    if plan['mode']=='readback':
        r,pp,more=materialize_parent(plan['materialize_closure_references'])
        need(pp['final_input_release_reference']==plan['final_input_release_reference']
            and pp['parent_references']==plan['parent_references'] and pp['seed']==plan['seed'],'SAME_ACTUAL_MATERIALIZED_INPUTS')
        old=r;parents+=more;data=unique([*data,*[reference(v) for v in r['artifacts'].values()]])
    return release,tables,columns,data,unique(parents),old


def source_paths():
    paths=[HERE/n for n in FILES]
    frozen=Q.load(HERE/'frozen_sources.json')
    paths += [REPO/r['relative_path'] for r in frozen['files']]
    paths += [Path(r['path']) for r in frozen['external_scientific_sources']]
    for folder in ('workflows/data_v1_final/export/pipeline_v1','workflows/data_v1_final/export/wire_v1',
                   'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2','workflows/data_v1_final/execution/queue_v1',
                   'workflows/data_v1_final/conformers/n1_pprime2_pilot_v4','workflows/data_v1_final/conformers/n1_pprime2_pilot_v3',
                   'workflows/data_v1_final/conformers/n1_pprime2_pilot_v2','workflows/data_v1_final/conformers/n1_pprime2_generation_v1'):
        paths += list((REPO/folder).glob('*.py'))+list((REPO/folder).glob('frozen_sources.json'))
    obs=REPO/'workflows/data_v1_final/labels/source_status_cpu_auto_memory_v1'
    paths += [obs/'support.py',obs/'resource_runtime.py']
    return sorted(set(paths))


def original_source_check():
    f=Q.load(HERE/'frozen_sources.json')
    need(f['schema']=='D5_ORIGINAL_SCIENTIFIC_SOURCE_BOUNDARIES_V1','EXACT_SOURCE_BOUNDARY_MANIFEST')
    for row in f['files']:
        need(Q.pin(REPO/row['relative_path'])=={'path':str(REPO/row['relative_path']),'bytes':row['bytes'],'sha256':row['sha256']},'UNCHANGED_ORIGINAL_SCIENCE_OR_MODEL_PINNED_CODEC')
    for ref in f['external_scientific_sources']:need(Q.pin(ref['path'])==ref,'UNCHANGED_ORIGINAL_PROPER_KABSCH_SOURCE')
    return f
