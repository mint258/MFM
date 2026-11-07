"""Main-side small-source staging only; no transfer, tasks read, SSH or submission."""
import argparse,json,os
from pathlib import Path
from .contract import canonical,sha,need,read_small,ref,load,verify,prep_metadata,recipe_equivalence,ORIGINAL_RECIPE_BYTES,ORIGINAL_RECIPE_SHA,CONTROL_MODE,environment_for_controls


def write_new(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('target-authority','environment-review','main-preparation','original-recipe','staging-directory'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--reviewer',required=True);a=parser.parse_args()
    need(a.reviewer=='root' and os.name=='posix','ROOT_MAIN_METADATA_PREPARATION_REQUIRED')
    here=Path(__file__).absolute().parent;catalog=json.loads(read_small(here/'source_catalog.json'))
    authority=json.loads(read_small(a.target_authority.absolute()));target=authority['target']
    need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_FREE_CPU_UFF_V1' and authority.get('status')=='USER_AUTHORIZED' and
         authority.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED' and authority.get('formal_generation_authorized') is False,
         'ACTUAL_SECONDARY_USER_AUTHORITY_GOLDEN_ONLY_REQUIRED')
    need(target['ssh_host']=='218.192.171.238' and target['ssh_user']=='alpha' and target['uid']==1264 and
         target['deployment_root']=='/gfshome/alpha/codex_data_v1_20261026' and target['allowed_cpu_nodes'],
         'EXACT_SECONDARY_ENDPOINT_AND_ACTUAL_ALLOWED_CPU_NODES_REQUIRED')
    endpoint=sha(canonical(target));root=Path(target['deployment_root'])
    prep=json.loads(read_small(a.main_preparation.absolute()));prep_metadata(prep)
    need(prep['endpoint_id']==endpoint,'MAIN_QA_EXPORT_FOR_DIFFERENT_ENDPOINT')
    environment_input=json.loads(read_small(a.environment_review.absolute()));environment_origin=ref(a.environment_review.absolute())
    environment=environment_for_controls(environment_input,environment_origin,endpoint,target)
    need(environment.get('schema')=='SECONDARY_UFF_ENVIRONMENT_ROOT_REVIEW_V1' and
         environment.get('status')=='READY_FOR_GOLDEN16_COMPATIBILITY_TEST' and environment.get('reviewer')=='root' and
         environment.get('endpoint_id')==endpoint and environment.get('formal_compatibility_passed') is False,
         'ACTUAL_ENVIRONMENT_REVIEW_READY_FOR_TEST_NOT_FORMAL_PASS_REQUIRED')
    versions=environment['expected_versions']
    need(versions['rdkit']=='2025.09.5' and versions['numpy']=='2.2.6' and versions['python']=='3.11.14' and
         versions.get('torch')=='2.5.1+cpu' and versions.get('torch_geometric')=='2.7.0' and
         environment.get('torch_build_identical_to_main') is False and environment.get('main_torch_version_provenance') and
         environment.get('probe_evidence_references'),
         'EXACT_RDKIT_NUMPY_PYTHON_AND_OBSERVED_TORCH_ENVIRONMENT_METADATA_REQUIRED')
    original=json.loads(read_small(a.original_recipe.absolute()))
    original_ref=ref(a.original_recipe.absolute())
    need(original_ref['bytes']==ORIGINAL_RECIPE_BYTES and original_ref['sha256']==ORIGINAL_RECIPE_SHA,
         'EXACT_FROZEN_ORIGINAL_MAIN_RECIPE_REQUIRED')
    out=a.staging_directory.absolute()
    need(not out.exists() and not any(p.is_symlink() for p in (out,*out.parents)),'NEW_LITERAL_STAGING_DIRECTORY_REQUIRED')
    sources=[];mapping={};origin_bodies={}
    for entry in catalog['sources']:
        origin=entry['origin_reference'];body=read_small(origin['path'])
        need(len(body)==origin['bytes'] and sha(body)==origin['sha256'],'ACTUAL_ORIGINAL_SCIENCE_SOURCE_PIN_CHANGED')
        local={'path':str(root/'legacy_sources'/entry['basename']),'bytes':len(body),'sha256':sha(body)}
        mapping[origin['path']]=local;origin_bodies[entry['basename']]=body
        sources.append({'basename':entry['basename'],'origin_reference':origin,'target_locator':local,
            'target_is_planned_locator_not_installed_proof':True})
    deployed=json.loads(json.dumps(original))
    deployed['science_source_pins']=[dict(pin,path=mapping[pin['path']]['path']) for pin in original['science_source_pins']]
    deployed['external_output_root']=str(root/'outputs')
    equivalence=recipe_equivalence(original,deployed,mapping,root/'outputs')
    need(type(authority['max_wall_seconds']) is int and 0<authority['max_wall_seconds']<=172800 and
         original['max_output_bytes']==8<<30 and original['quota_reserve_bytes']==200000000000,
         'FINITE_ROOT_GOLDEN_WALL_OUTPUT_AND_QUOTA_REQUIRED')
    out.mkdir(parents=True,mode=0o700)
    for name,body in origin_bodies.items():write_new(out/'legacy_sources'/name,body)
    worker_sources=[]
    for source in sorted(here.glob('*.py')):
        body=read_small(source);write_new(out/'code/portable_secondary_uff_v1'/source.name,body)
        worker_sources.append({'basename':source.name,'origin_reference':ref(source),
            'target_locator':{'path':str(root/'code/portable_secondary_uff_v1'/source.name),'bytes':len(body),'sha256':sha(body)},
            'target_is_planned_locator_not_installed_proof':True})
    def stage_metadata(name,origin):
        body=read_small(origin);write_new(out/'metadata'/name,body)
        return {'path':str(root/'metadata'/name),'bytes':len(body),'sha256':sha(body)}
    prep_target=stage_metadata('main_preparation.json',a.main_preparation.absolute())
    authority_target=stage_metadata('secondary_authority.json',a.target_authority.absolute())
    raw_environment_target=stage_metadata('environment_input_original.json',a.environment_review.absolute())
    env_body=(json.dumps(environment,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    write_new(out/'metadata/environment_review.json',env_body)
    env_target={'path':str(root/'metadata/environment_review.json'),'bytes':len(env_body),'sha256':sha(env_body)}
    original_target=stage_metadata('original_recipe.json',a.original_recipe.absolute())
    catalog_target=stage_metadata('source_catalog.json',here/'source_catalog.json')
    control_auth_target=stage_metadata('control_authorization.json',verify(prep['root_control_authorization_reference']))
    audit_target=stage_metadata('original_audit.json',verify(prep['original_audit_reference']))
    closed_target=stage_metadata('original_complete_packages.json',verify(prep['original_complete_packages_reference']))
    monitor_target=stage_metadata('partial_audit_monitor_closure.json',verify(prep['partial_audit_monitor_closure_reference']))
    recipe_raw=(json.dumps(deployed,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    write_new(out/'metadata/deployed_recipe.json',recipe_raw)
    task=prep['tasks_reference']
    need(type(task['bytes']) is int and 0<task['bytes']<=1<<30,'BOUNDED_GOLDEN16_TASK_EXPORT_REQUIRED')
    deployment={'schema':'PORTABLE_SECONDARY_UFF_CONTROL16_DEPLOYMENT_MAP_V1','status':'STAGED_METADATA_NOT_INSTALLED_NOT_EXECUTED',
        'target':target,'endpoint_id':endpoint,'mode':CONTROL_MODE,'formal_generation_authorized':False,
        'python':environment['python_executable'],'max_wall_seconds':authority['max_wall_seconds'],
        'main_torch_version_provenance':environment['main_torch_version_provenance'],'torch_build_identical_to_main_claimed':False,
        'max_output_bytes':original['max_output_bytes'],'max_input_bytes':1<<30,'soft_min_mem_available_bytes':2<<30,
        'science_sources':sources,'portable_worker_sources':worker_sources,'original_recipe_reference':original_ref,
        'original_recipe_target_locator':original_target,'source_catalog_target_locator':catalog_target,
        'original_recipe_value':original,'recipe_equivalence':equivalence,
        'recipe_target_locator':{'path':str(root/'metadata/deployed_recipe.json'),'bytes':len(recipe_raw),'sha256':sha(recipe_raw)},
        'main_preparation_origin_reference':ref(a.main_preparation.absolute()),'main_preparation_target_locator':prep_target,
        'control_authorization_target_locator':control_auth_target,'original_audit_target_locator':audit_target,
        'original_complete_packages_target_locator':closed_target,'partial_audit_monitor_closure_target_locator':monitor_target,
        'target_authority_origin_reference':ref(a.target_authority.absolute()),'target_authority_target_locator':authority_target,
        'environment_input_origin_reference':environment_origin,'environment_validation_target_locator':raw_environment_target,
        'environment_review_target_locator':env_target,
        'environment_input_explicitly_converted_to_new_root_review':environment_input['schema']=='SECONDARY_OFFLINE_ENVIRONMENT_VALIDATION_V1',
        'tasks_origin_reference':task,'tasks_target_locator':dict(task,path=str(root/'inputs'/('control16_'+sha(prep['slice_id'].encode())+'.jsonl'))),
        'main_only_authority_locators_not_deployed':[original.get(k) for k in ('authority_pins','per_molecule','molecule_index','record_index','sprime_manifest')],
        'main_lmdb_paths_not_deployed_or_opened':True,'main_production_once_ledger_never_opened':True,
        'population_members_added':0,'new_main_science_baseline_computed':False,
        'scientific_core_bytes_changed':False,'original_pickle_bytes_reencoded_as_numbers':False,
        'actual_target_installed':False,'environment_golden_compatibility_passed':False,'scheduler_calls':False}
    write_new(out/'metadata/deployment_map.json',(json.dumps(deployment,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
    receipt={'status':'SOURCE_AND_METADATA_STAGED_REQUIRES_ROOT_TRANSFER_AND_ACTUAL_CPU_SOFTWARE_QA16',
        'deployment_map_staged_reference':ref(out/'metadata/deployment_map.json'),'recipe_equivalence':equivalence,
        'tasks_body_read_or_copied':False,'pickle_decoded':False,'scheduler_or_network_calls':False,
        'target_existence_claimed':False,'formal_generation_authorized':False}
    write_new(out/'staging_receipt.json',(json.dumps(receipt,indent=2)+'\n').encode());print(json.dumps(receipt))


if __name__=='__main__':main()
