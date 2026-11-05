"""The original closed1000x2 pilot, independent of final Common and QA domains."""
import hashlib,json,pathlib,re
from workflows.data_v1_final.pprime.strict_numerics20_prepare_v1 import inputs as OriginalInputs
from workflows.data_v1_final.pprime.strict_numerics15_qa_v1 import contract as S
from workflows.expansion.moleculenet17_hold21_readonly_v1 import run as ResourceOrigin
from workflows.data_v1_final.pprime import common as O
Q=S.Q;need=Q.need;meta=S.meta;unique=S.unique
HERE=Q.REPO/'workflows/data_v1_final/pprime/pilot2000_prepare_day_v1'
FILES=('contract.py','prepare.py','metadata.py','test_v1.py','README.md')
KEY='pprime_original2000_zero_invoke_preparation_v1';MODULE='workflows.data_v1_final.pprime.pilot2000_prepare_day_v1.prepare'
CAP=2<<30;WALL=7200;NODES=('compute-0-13','compute-0-14','compute-0-18','compute-0-19')
PARAMETERS={'original_closed_preparation_job':'4520345','unique_MIDs':1000,'UFF_geometries':2000,'all_tasks':list(O.TASKS),
 'new_QM_calls':0,'new_UFF_calls':0,'original_only_reader_initialize':True,'candidate_protocol_initialize':False,
 'no_new_atom_count_filter':True,'original_fixed_random_first2':True,'selection_seed':2026102504,'order_seed':20261025,
 'old1000_not_final_Common':True,'no_reselection_from_active_Sprime':True,'original5_Sprime_and_selected_payload_checks':True,
 'same3_candidate_differences_render_only_not_production_permission':True,'methods':3,'cpus':16,'wall_seconds':WALL,'output_cap_bytes':CAP}

def parameters(node):
    need(node in NODES,'REAL_EXISTING_RESOURCE_MAPPING');return dict(PARAMETERS,node=node)

def triple(ref):return OriginalInputs.C.O.triple({k:ref[k] for k in ('path','bytes','sha256')})

SOFTWARE_ORIGINAL_PATHS={
 '/share/home/zixiao/.conda/envs/mopac/lib/'+name for name in ('libgfortran.so.5.0.0','libmopac.so.2','libopenblasp-r0.3.28.so','libomp.so','libquadmath.so.0.0.0','libgcc_s.so.1')}
SOFTWARE_ORIGINAL_PATHS.update('/usr/lib64/'+name for name in ('ld-linux-x86-64.so.2','libm.so.6','librt.so.1','libpthread.so.0','libc.so.6','libdl.so.2'))
SOFTWARE_ORIGINAL_PATHS.update(('/share/home/zixiao/.conda/envs/mopac/bin/mopac','/share/home/zixiao/.conda/envs/chemprop/bin/python'))

def software_original_specs(context):
    """Register exact14 aliases from frozen software metadata; bodies/hash stay CPU-only."""
    import sys
    refs=[triple(r) for r in context['execution_asset_references']]
    outside={r['path']:r for r in refs if not r['path'].startswith('/share/home/zixiao/descriptor_analysis/')}
    need(set(outside)==SOFTWARE_ORIGINAL_PATHS,'EXACT14_DECLARED_SOFTWARE_ORIGINALS_NO_DATA_PATH_RELAXATION')
    authority=context['execution_asset_verification_context'];manifest_ref=authority['manifest_reference'];package=meta(manifest_ref)
    need(package['schema']=='WP5_REPRODUCTION_PACKAGE_V1' and package['status']=='REPRODUCTION_PACKAGE_CLOSED'
      and authority['frozen_validation_function']=='wp5_engine_v3.load_production_metadata','EXACT_ORIGINAL_SOFTWARE_REPRODUCTION_VALIDATOR')
    expectations=[e['reference'] for e in authority['source_path_expectations']]
    env=package['environment'];matches=[triple(r) for r in context['source_references'] if r['path']==env['path'] and r['sha256']==env['sha256']]
    need(len(matches)==1,'EXACT_DECLARED_FROZEN_ENVIRONMENT_LOCK');lock=meta(matches[0]);result={}
    for path,ref in outside.items():
        if path==lock['python_executable']:
            need(ref['sha256']==lock['python_executable_sha256'] and sys.executable==path and sys.prefix==lock['conda_prefix']
              and sys.version==lock['python_version'],'FROZEN_INTERPRETER_ALIAS_PREFIX_VERSION_AND_FULL_SHA')
            result[path]={'reference':ref,'source_uid':None,'mode':None,'resolved_source_path':None,'role':'FROZEN_PYTHON_INTERPRETER',
              'environment_lock_reference':matches[0],'manifest_reference':manifest_ref,'historical_owner_frozen':False,'historical_link_chain_recorded':False};continue
        need(ref in expectations,'EXACT_REGISTERED_COMPUTE_LOCAL_SOFTWARE_EXPECTATION')
        rows=[a for a in package['assets'] if a.get('source_path')==path and a['sha256']==ref['sha256'] and a['bytes']==ref['bytes']]
        need(rows and len({(a['source_uid'],a['mode'],a.get('resolved_source_path')) for a in rows})==1,'FROZEN_SOFTWARE_SOURCE_UID_MODE_RESOLVED_CONSENSUS')
        row=rows[0];need(row['source_uid'] in (0,1278) and type(row['mode'])is int,'ORIGINAL_SYSTEM_ROOT_OR_MAIN_USER_SOFTWARE_OWNER')
        result[path]={'reference':ref,'source_uid':row['source_uid'],'mode':row['mode'],'resolved_source_path':row.get('resolved_source_path'),
          'role':row['role'],'manifest_reference':manifest_ref,'historical_owner_frozen':True,'historical_link_chain_recorded':False}
    return result

def distinct_geometry(a,b):
    need(all(type(v)is str and re.fullmatch('[0-9a-f]{64}',v) is not None for v in (a,b)) and a!=b,'EXACT_SAME_GEOMETRY_SHA_IS_NOT_SECOND_GEOMETRY_NO_RESAMPLING')

def pairs_matrix(pairs):
    need(len(pairs)==2000 and len({p['record_id'] for p in pairs})==2000,'EXACT_ORIGINAL2000_UNIQUE_RECORDS')
    grouped={}
    for pair in pairs:
        need(pair['geometry_source']=='uff_sprime' and type(pair['random_order_rank'])is int
          and type(pair['conformer']['sprime_conf_idx'])is int and pair['conformer']['sprime_conf_idx']>=0,'REAL_PHYSICAL_UFF_ID_NOT_RANK_ALIAS')
        grouped.setdefault(pair['molecule_id'],[]).append(pair)
    need(len(grouped)==1000 and all(len(v)==2 and {p['random_order_rank'] for p in v}=={0,1}
      and len({p['conformer']['sprime_conf_idx'] for p in v})==2 for v in grouped.values()),'TRUE1000_MIDs_TWO_DISTINCT_PHYSICAL_IDS')
    return grouped

def parents(plan):
    old,new,diff=S.protocol(plan)
    need(plan['candidate_protocol_reference']['bytes']==19218 and plan['candidate_protocol_reference']['sha256']=='f72bb07780b28026df5931478b50495d3cb4d75fe5edecac7593b90af9356302','SAME_FROZEN_3_DIFFERENCE_DIAGNOSTIC_PROTOCOL_NOT_PRODUCTION_PERMISSION')
    need(tuple(t['name'] for t in old['tasks'])==O.TASKS and old['timeout_seconds']==900
      and old['seed']==20261010 and old['perturb_sigma_A']==0.1,'EXACT_ORIGINAL12_METHOD_VERSION_KEYWORDS900')
    saved=meta(plan['original_prepared_reference']);closed=meta(plan['original_preparation_closure_reference'])
    need(saved['status']=='PPRIME_PAIRS_READY_NOT_QM_EXECUTED' and saved['molecules']==1000 and saved['conformers']==2000
      and closed['status']=='ROOT_PPRIME_INPUT_PREPARATION_ACTUAL_COMPLETED_READBACK_CLOSED'
      and closed['prepared']==plan['original_prepared_reference'] and closed['actual_parent']['JobIDRaw']=='4520345'
      and closed['actual_parent']['State']=='COMPLETED' and closed['actual_parent']['ExitCode']=='0:0' and closed['QM_started'] is False,
      'TRUE_EXISTING_345_C0_PREPARED1000X2_NOT_FUTURE_OR_QA_SELECTION')
    context=meta(plan['source_context_reference']);pilot=meta(context['pilot_config']);roles=meta(pilot['role_manifest'])
    need(context['schema']=='ROOT_PPRIME_CAUSAL15_SOURCE_PLAN_V1' and context['reviewer']=='root'
      and context['protocol']==plan['original_protocol_reference'] and context['pilot_config']==saved['config']
      and pilot['selection_seed']==2026102504 and pilot['order_seed']==20261025
      and pilot['minimum_success_rate']==.995 and pilot['maximum_allocated_core_seconds_per_conformer']==11.7,
      'OLD_CONTEXT_SOFTWARE_ONLY_ORIGINAL2000_AND_ORIGINAL_GATES')
    legacy=meta(pilot['legacy_contract']);need(legacy['protocol']=={k:plan['original_protocol_reference'][k] for k in ('path','sha256')},'EXACT_PRODUCTION_PROTOCOL_NOT_DIAGNOSTIC')
    pair=[r for r in saved['outputs'] if pathlib.Path(r['path']).name=='pairs.jsonl'];need(len(pair)==1 and pair[0]['bytes']==19385976,'REAL_LARGE_PAIR_DATA_NOT_SMALL_METADATA')
    sprime=[triple(r) for r in saved['source_sprime_references']];need(len(sprime)==5,'ALL_ORIGINAL5_CLOSED_SPRIME_SOURCES')
    plan0=meta(pilot['source_plan']);need(len(plan0['sources'])==11 and {r['shard_id'] for r in plan0['sources']}==set(range(11)),'ALL11_ORIGINAL_SOURCE_SHARDS')
    lmdb=[triple({'path':r['path'],'bytes':r['source_size'],'sha256':r['file_sha256']}) for r in plan0['sources']]
    population=[]
    for field in ('per_molecule','molecule_index'):
        matches=[r for r in pilot['small_authority_pins'] if r['path']==pilot[field]]
        need(len(matches)==1,'ACTUAL_ORIGINAL_POPULATION_LOCATOR_'+field);population.append(triple(matches[0]))
    val=[r for r in roles['outputs'] if pathlib.Path(r['path']).name=='validation_molecules.parquet'];need(len(val)==1,'EXACT_ORIGINAL_ROUTINE_VAL_MEMBERSHIP')
    need(roles['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN' and roles['roles']['VAL']=={'molecules':7610,'records':72525},'UNCHANGED_OLD_TRAIN_VAL_ROLE_AUTHORITY')
    retention=meta(plan['retention_policy_reference']);need(retention['schema']=='PPRIME_STABLE_RAW_RETENTION_POLICY_V1'
      and retention['seed']==20261010 and retention['basis_points']==100 and retention['modulus']==10000
      and retention['pilot_config']==context['pilot_config'],'ORIGINAL_ROOT_ACCEPTED_STABLE1_PERCENT_RAW_POLICY')
    recipe=meta(plan['original_sprime_recipe_reference']);need(plan['original_sprime_recipe_reference']=={'path':str(Q.REPO/'configs/data_v1/conformers/pilot_v1.json'),
      'bytes':3629,'sha256':'cfd153fb524ad823d3903b0ff7d78e402bbbcb74e124136b4bfeb3035279407a'}
      and recipe['order_seed']==20261025 and len(recipe['science_source_pins'])==2,'ORIGINAL_THREE_ORDER_RMSD_OBJECTS')
    refs=unique([*(plan[k] for k in ('original_prepared_reference','original_preparation_closure_reference','source_context_reference',
      'original_protocol_reference','candidate_protocol_reference','retention_policy_reference','original_sprime_recipe_reference')),
      context['pilot_config'],pilot['legacy_contract'],pilot['role_manifest'],pilot['source_plan'],closed['readback'],
      *context['source_references'],*recipe['science_source_pins'],retention['selector'],*retention['parent_source_pins'],
      *(r for r in saved['outputs'] if pathlib.Path(r['path']).suffix=='.json')])
    for ref in refs:need(Q.pin(ref['path'])==ref,'SMALL_FROZEN_AUTHORITY_CURRENT_BYTES')
    data=unique([triple(pair[0]),*sprime,*lmdb,*population,triple(val[0]),
      *(triple(r) for r in saved['outputs'] if pathlib.Path(r['path']).suffix=='.parquet'),*context['execution_asset_references']])
    return old,new,diff,context,pilot,saved,triple(pair[0]),sprime,population,triple(val[0]),data,refs

def sources(plan):
    *_,context,pilot,saved,pair,sprime,population,val,data,parents0=parents(plan)
    paths=[*(HERE/n for n in FILES),*OriginalInputs.C.sources()]
    base=Q.REPO/'workflows/data_v1_final/pprime'
    paths += [base/n for n in ('engine_adapter.py','raw_archive.py','export_families.py','close_pilot.py')]
    paths += [base/'retention_v1'/n for n in ('retention_policy_v1.py','prepare_v1.py','run_pilot_v1.py')]
    paths += [Q.REPO/'workflows/expansion/moleculenet17_hold21_readonly_v1'/n for n in ('run.py','test_v1.py')]
    paths += [Q.REPO/'workflows/data_v1_final/execution'/namespace/n for namespace in ('cpu_packed_day_v1','cpu_analysis_day_v1','cpu_analysis_cpu19_v1') for n in ('contract.py','quota_provider.py')]
    paths += [Q.REPO/'workflows/data_v1_final/execution/cpu_analysis_cpu19_v1/__init__.py']
    return unique([*(Q.pin(p) for p in sorted(set(paths))),*context['source_references']])

def proposal(prepared_reference=None):
    return {'schema':'PPRIME2000_LIMITED_PRODUCTION_PRECISION_CHOICE_PROPOSAL_V1','status':'REQUIRES_REAL_INPUT_CLOSURE_AND_ROOT_REVIEW_NOT_EXECUTION_AUTHORITY',
      'actual_prepared2000_reference':prepared_reference,'MIDs':1000,'geometries':2000,'tasks_per_geometry':12,'maximum_native_calls':24000,
      'arms_per_geometry':1,'no_rotation_or_new_diagnostic_calls':True,'timeout_seconds_per_call':900,'new_tolerance':False,
      'original_option':'ORIGINAL_WP5_PROTOCOL_ONLY_GUIDE_AUTHORITY_WITH_EXACT_ROOT_STAGE_REVIEW',
      'tighter_option':'NEW_EXPLICIT_USER_AUTHORIZED_PPRIME2000_TIGHTER_PILOT_V1_REQUIRED_NOT_OLD15_OR1200',
      'candidate_differences_only':{'pm7_B':'SCFCRT=1.D-9','xtb_singlepoint':'--acc 0.01','xtb_perturbed_gradient':'--acc 0.01'},
      'other9_tasks_unchanged':True,'minimum_all12_successful_records':1990,'minimum_record_success_rate':.995,
      'maximum_actual_allocated_core_seconds_per_requested_record':11.7,'historical_WP5_core_seconds_per_record':7.8,'factor':1.5,
      'allocation_denominator_includes_all_requested2000_and_all_failures':True,'full_release_not_authorized':True,
      'old15FAIL_and_original_precision_general_rotation_evidence_not_erased':True,
      'diagnostic_precision_PASS_is_not_production_permission_or_universal_physical_PASS':True,
      'proposed_execution_cpus':16,'memory_requested':False,'proposed_maximum_wall_seconds':86400,
      'proposed_shared_output_cap_bytes':32<<30,'output_cap_is_stop_bound_not_worst_case_success_guarantee':True,
      'production_executor_is_separate_source_delivery_before_any_user_execution_approval':True}
