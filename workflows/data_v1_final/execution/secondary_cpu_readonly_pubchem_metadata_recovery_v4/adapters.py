"""Single fixed source3 protocol, using the frozen generic Alpha gate."""
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
ROOT=Q.ROOT;ENDPOINT=Q.ENDPOINT;UID=Q.UID;POLICY=Q.POLICY
STORAGE_SCOPE=ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'
FIXTURE_KEY='pubchem_c_metadata_recovery_source3_alpha_v4'
PROTOCOLS={FIXTURE_KEY:{'plan':'SECONDARY_PUBCHEM_C_METADATA_RECOVERY_SOURCE3_PLAN_V4',
 'proof':'SECONDARY_PUBCHEM_C_METADATA_RECOVERY_SOURCE3_STARTUP_V4',
 'module':'pubchem_c_metadata_recovery_v4.fixture_cpu','pilot':False}}

def fixture_readonly(input_path,deployment_path,node,seconds):
    from pubchem_c_metadata_recovery_v4 import fixture_cpu as F
    Q.need(deployment_path is None,'NO_SOURCE3_DEPLOYMENT_OR_DYNAMIC_MODULE_WRAPPER');plan=Q.load(input_path);F.validate_metadata(plan)
    Q.need(plan['node']==node and node in Q.NODES and seconds==600 and plan['data_references']==[],'FIXED_SOURCE3_NODE_WALL_NO_DATA')
    out=Q.literal(plan['output_directory']);proof=Q.literal(plan['startup_proof_path'])
    Q.need(ROOT/'artifacts/pubchem_metadata_recovery_source3_alpha_v4' in out.parents and not out.exists(),'NEW_FIXED_SOURCE3_OUTPUT')
    argv=[plan['python'],'-B','-m',F.MODULE,'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    Q.need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_ONLY_SOURCE3_PRIMARY_ALL_OPTIONS')
    refs={r['path']:r for r in [*plan['source_references'],Q.ref(input_path),plan['root_review_reference']]}
    for r in refs.values():Q.verify(r)
    return {'producer':'readonly','input_reference':Q.ref(input_path),'producer_argv':argv,'producer_plan_reference':Q.ref(input_path),
        'producer_review_reference':plan['root_review_reference'],'producer_authority_reference':plan['resource_authority_reference'],
        'source_references':list(refs.values()),'data_reference_locators_only':[],'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':F.CAP,'producer_working_directory':str(ROOT/'code'),
        'proof_schema':F.PROOF,'request_kind':'analysis','pilot':False,'scope_key':FIXTURE_KEY,'scope_parameters':F.PARAMETERS,
        'stage':F.STAGE,'scope_mode':F.MODE,'performance_profile':False,
        'fixed_archive_authority':{'only_source3':True,'tested_metadata_sources':9,'range_authority_required':False,'Budget_or_DATA_or_claim_or_pool':False}}


def fixture_startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    from pubchem_c_metadata_recovery_v4 import fixture_cpu as F
    a=request['adapter'];Q.need(a['scope_key']==request['scope_key']==FIXTURE_KEY and a['producer_argv'][3]==F.MODULE
        and request['kind']==a['request_kind']=='analysis' and request['pilot'] is a['pilot'] is False
        and request['scope_parameters']==a['scope_parameters']==F.PARAMETERS and request['wall_seconds']==600
        and a['output_cap_bytes']==F.CAP and a['data_reference_locators_only']==[] and request['stage']==a['stage']==F.STAGE
        and request['scope_mode']==a['scope_mode']==F.MODE and request['performance_profile'] is a['performance_profile'] is False,
        'ONLY_FIXED_THREE_METADATA_TESTS_NOT_ARBITRARY_READONLY_CODE')
    Q.need(storage['storage_scope_review_reference']['path']==str(STORAGE_SCOPE),'EXACT_FRESH_STORAGE7_FOR_SOURCE3')
    return {'schema':F.PROOF,'endpoint':ENDPOINT,'uid':UID,'node':request['node'],'boot_id':probe['boot_id'],'job_id':str(jid),
        'observed_unix_seconds':probe['observed_unix_seconds'],'memory_policy':POLICY,'memory_limits_requested':False,'exclusive_requested':False,
        'script_reference':request['script_reference'],'controller_evidence':controller_evidence,'source_target_verification':request['verified_target_references'],
        'actual_gate_process':probe['gate_process'],'actual_memory_environment':probe['actual_memory_environment'],
        'other_jobs_modified':False,'forced_signals_sent':False,'job_metadata':raw,
        'request':{'kind':'analysis','pilot':False,'cpus':16,'memory_policy':POLICY,'wall_seconds':600,'execution_argv':a['producer_argv']},
        'plan_reference':a['producer_plan_reference'],'root_review_reference':a['producer_review_reference'],'account_free_bytes':storage['effective_free_bytes'],
        'effective_free_basis':storage['effective_free_basis'],'storage_observation_reference':storage_reference,'storage_observation':storage,
        'scope_key':FIXTURE_KEY,'stage':F.STAGE,'scope_mode':F.MODE,'performance_profile':False,'state_only_no_science_or_range':True}

readonly=fixture_readonly
startup_proof=fixture_startup_proof
