"""Two independent producer schemas, source mapping and startup proof assembly."""
from pathlib import Path
from .common import (ROOT,ENDPOINT,UID,POLICY,need,canonical,sha,ref,load,load_ref,verify,normalized,literal)


def add_reference(refs,value):
    normalized(value);verify(value)
    need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_TARGET_SOURCE_REFERENCE')
    refs[value['path']]=value


def mapping(rows,refs):
    seen=set()
    for row in rows:
        old=row['origin_reference'];new=row.get('secondary_reference',row.get('target_locator'))
        need(isinstance(new,dict) and new['path'] not in seen and old['bytes']==new['bytes'] and old['sha256']==new['sha256'],
             'EXACT_UNIQUE_MAIN_ORIGIN_TO_ALPHA_TARGET_MAPPING_REQUIRED')
        seen.add(new['path']);add_reference(refs,new)
    return seen


def acquisition(input_path,deployment_path,node,seconds,**unused):
    spec=load(input_path);manifest=load(deployment_path);refs={}
    need(spec.get('schema')=='SECONDARY_SOURCE_ACQUISITION_CPU_SPEC_V1' and spec.get('status')=='PREPARED_NOT_SUBMITTED' and
         spec.get('endpoint')==ENDPOINT and spec.get('uid')==UID and spec.get('node')==node and spec.get('partition')=='cpu' and
         spec.get('cpus')==16 and spec.get('memory_policy')==POLICY and spec.get('memory_requested') is False and
         spec.get('exclusive_requested') is False and spec.get('wall_seconds')==seconds and spec.get('automatic_submission') is False and
         spec.get('working_directory')==str(ROOT),'EXACT_REVIEWED_SECONDARY_ACQUISITION_SPEC_REQUIRED')
    need(manifest.get('schema')=='SECONDARY_EXACT_SOURCE_DEPLOYMENT_V1' and manifest.get('endpoint')==ENDPOINT and
         manifest.get('uid')==UID and manifest.get('run_root')==str(ROOT),'EXACT_SECONDARY_DEPLOYMENT_MANIFEST_REQUIRED')
    targets=mapping(manifest['files'],refs)
    need(targets=={r['path'] for r in spec['source_references']} and len(spec['source_references'])==len(targets),
         'DEPLOYMENT_AND_SPEC_SOURCE_SETS_DIFFER')
    for value in spec['source_references']:add_reference(refs,value)
    plan=load_ref(spec['plan_reference']);review=load_ref(spec['root_review_reference'])
    need(plan['plan_path']==spec['plan_reference']['path'] and plan['root_review_reference']==spec['root_review_reference'] and
         plan['execution_argv']==spec['execution_argv'] and plan['startup_proof_path']==spec['startup_proof_path'] and
         plan['node']==node and plan['wall_seconds']==seconds and plan['output_cap_bytes']==spec['output_cap_bytes'],
         'ACQUISITION_PLAN_SPEC_BINDING_DIFFERS')
    need(review.get('schema')=='EXACT_SECONDARY_SOURCE_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and
         review.get('reviewer')=='root','EXACT_ACQUISITION_ROOT_SCOPE_REVIEW_REQUIRED')
    for key in ('stage','source','scope_parameters','wall_seconds','output_cap_bytes','endpoint','uid','run_root','execution_argv','parent_evidence_references'):
        need(plan[key]==review[key],'ACQUISITION_ROOT_SCOPE_DIFFERS:'+key)
    need(review['approved_source_references']==[r for r in plan['source_references'] if r!=plan['root_review_reference']],
         'ACQUISITION_REVIEWED_TARGET_SOURCES_DIFFER')
    argv=spec['execution_argv']
    need(len(argv)==7 and argv[1:3]==['-B',str(ROOT/'workflows/expansion/secondary_source_acquisition_v1/run_v1.py')] and
         argv[3:]==['--plan',plan['plan_path'],'--startup-proof',plan['startup_proof_path']],
         'EXACT_ACQUISITION_PRIMARY_AND_OPTIONS_REQUIRED')
    if plan['stage']=='CSV_ZIP_PROFILE':
        need(plan['source']['source_id']=='coconut_csv_full' and seconds<=3600 and 0<plan['output_cap_bytes']<=1024**3,
             'EXACT_FINITE_FULL_CSV_ZIP_PROFILE_REQUIRED')
    else:
        need(plan['stage']=='PLAIN_SQL_FULL_DOWNLOAD' and plan['source']['source_id']=='coconut_sql' and
             review.get('actual_profile_and_cost_reviewed') is True and
             plan.get('accepted_profile_reference') in plan['parent_evidence_references'],'NO_AUTOMATIC_SQL_PROMOTION')
    need(plan['source']['expected_content_length']+64*1024**2<=plan['output_cap_bytes'],'WHOLE_SOURCE_OUTPUT_CAP_REQUIRED')
    return {'producer':'acquisition','input_reference':ref(input_path),'deployment_reference':ref(deployment_path),
        'producer_argv':argv,'producer_plan_reference':spec['plan_reference'],'producer_review_reference':spec['root_review_reference'],
        'producer_authority_reference':plan['resource_authority_reference'],'source_references':list(refs.values()),
        'data_body_hashes_claimed_by_controller':False,'startup_proof_path':spec['startup_proof_path'],
        'science_output':plan['output_directory'],'output_cap_bytes':plan['output_cap_bytes'],
        'producer_working_directory':str(ROOT),'proof_schema':'SECONDARY_SOURCE_ACQUISITION_STARTUP_V1'}


def portable16(input_path,deployment_path,node,seconds,*,startup_proof,science_output):
    deployment=load(input_path);target=deployment['target'];refs={}
    need(deployment.get('schema')=='PORTABLE_SECONDARY_UFF_CONTROL16_DEPLOYMENT_MAP_V1' and
         target.get('ssh_host')=='218.192.171.238' and target.get('ssh_user')=='alpha' and target.get('uid')==UID and
         target.get('deployment_root')==str(ROOT) and node in target['allowed_cpu_nodes'] and
         deployment.get('endpoint_id')==sha(canonical(target)) and
         deployment.get('mode')=='SECONDARY_SOFTWARE_COMPATIBILITY_CONTROLS_ONLY' and
         deployment.get('formal_generation_authorized') is False and deployment.get('population_members_added')==0 and
         seconds<=deployment['max_wall_seconds'],'EXACT_SECONDARY_EXISTING16_SOFTWARE_QA_MAP_REQUIRED')
    mapping(deployment['science_sources']+deployment['portable_worker_sources'],refs)
    for key in ('target_authority_target_locator','environment_review_target_locator','environment_validation_target_locator',
                'main_preparation_target_locator','control_authorization_target_locator','original_audit_target_locator',
                'original_complete_packages_target_locator','partial_audit_monitor_closure_target_locator',
                'source_catalog_target_locator','recipe_target_locator','original_recipe_target_locator'):
        add_reference(refs,deployment[key])
    environment=load_ref(deployment['environment_review_target_locator'])
    need(environment.get('status')=='READY_FOR_GOLDEN16_COMPATIBILITY_TEST' and
         environment.get('formal_compatibility_passed') is False and environment.get('endpoint_id')==deployment['endpoint_id'] and
         environment.get('python_executable')==deployment['python'],'ENVIRONMENT_READY_IS_NOT_SOFTWARE_PASS')
    prep=load_ref(deployment['main_preparation_target_locator'])
    ids=prep['allowed_original_control_ids'];missing={'principal_01112964','principal_00509656'}
    need(prep.get('endpoint_id')==deployment['endpoint_id'] and prep.get('mode')==deployment['mode'] and
         len(ids)==len(set(ids))==16 and not set(ids)&missing and prep.get('population_members_added')==0 and
         prep.get('main_production_once_ledger_accessed') is False,'EXACT_OLD16_QA_WITH_NO_MISSING_OR_NEW_POPULATION_REQUIRED')
    old,new=deployment['tasks_origin_reference'],deployment['tasks_target_locator']
    need(old['bytes']==new['bytes'] and old['sha256']==new['sha256'] and 0<new['bytes']<=deployment['max_input_bytes'],
         'TASK_BODY_LOCATOR_RELOCATION_DIFFERS')
    literal(new['path']) # No data body open, stat, hash, pickle or science here.
    proof=literal(startup_proof);out=literal(science_output)
    need(ROOT/'outputs' in out.parents,'NEW_ALPHA_SOFTWARE_QA_OUTPUT_CHILD_REQUIRED')
    argv=[deployment['python'],'-B','-m','portable_secondary_uff_v1.worker','--deployment-map',str(Path(input_path)),
          '--startup-proof',str(proof),'--output',str(out)]
    return {'producer':'portable16','input_reference':ref(input_path),'producer_argv':argv,
        'producer_authority_reference':deployment['target_authority_target_locator'],'source_references':list(refs.values()),
        'data_reference_locators_only':[new],'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':deployment['max_output_bytes'],
        'producer_working_directory':str(ROOT/'code'),'endpoint_id':deployment['endpoint_id'],
        'proof_schema':'SECONDARY_PORTABLE_UFF_CONTROL16_STARTUP_V1'}


def scope_for_portable(request):
    return {'schema':'SECONDARY_PORTABLE_UFF_CONTROL16_ROOT_SCOPE_V1','status':'APPROVED_FOR_EXACT_SECONDARY_CONTROL16',
        'reviewer':'root','endpoint_id':request['adapter']['endpoint_id'],
        'deployment_map_reference':request['adapter']['input_reference'],'mode':'SECONDARY_SOFTWARE_COMPATIBILITY_CONTROLS_ONLY',
        'population_members_added':0,'execution_argv':request['adapter']['producer_argv'],'wall_seconds':request['wall_seconds'],
        'script_reference':request['script_reference'],'formal_generation_authorized':False,
        'created_by_explicit_root_controller_invocation':True,'environment_is_ready_only_not_science_pass':True}


def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    base={'schema':adapter['proof_schema'],'uid':UID,'node':request['node'],'boot_id':probe['boot_id'],'job_id':str(jid),
        'observed_unix_seconds':probe['observed_unix_seconds'],'memory_policy':POLICY,'memory_limits_requested':False,
        'exclusive_requested':False,'script_reference':request['script_reference'],
        'controller_evidence':controller_evidence,'source_target_verification':request['verified_target_references'],
        'actual_gate_process':probe['gate_process'],'actual_memory_environment':probe['actual_memory_environment'],
        'scheduler_memory_is_recorded_not_an_admission_threshold':True,'other_jobs_modified':False,'forced_signals_sent':False}
    if adapter['producer']=='acquisition':
        base.update(endpoint=ENDPOINT,hostname=probe['hostname'],plan_reference=adapter['producer_plan_reference'],
            root_review_reference=adapter['producer_review_reference'],job_metadata=raw,
            storage_observation={**storage,'evidence_references':[storage_reference,request['storage_review_reference']]})
    else:
        base.update(endpoint_id=adapter['endpoint_id'],request={'kind':'conformer','pilot':True,'cpus':16,
            'memory_policy':POLICY,'wall_seconds':request['wall_seconds'],'execution_argv':adapter['producer_argv']},
            deployment_map_reference=adapter['input_reference'],root_exact_scope_reviewed=True,
            environment_ready_for_golden16_only=True,execution_admission_granted=True,
            root_scope_review_reference=request['portable_scope_review_reference'],job_metadata=job,
            account_free_bytes=storage['effective_free_bytes'],effective_free_basis=storage['effective_free_basis'],
            storage_observation_reference=storage_reference,quota_raw=canonical(probe['storage']['quota']).decode())
    return base
