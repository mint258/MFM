"""Stdlib Main-login unsigned metadata; no DATA stat/hash, queue or approval."""
import argparse,json,os,pathlib,socket
from . import contract as C,resources as R


def candidate(a,out):
    control=C.controls();refs=[];value={'schema':C.SCHEMA,'status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED',
        'proposed_runtime_status':'APPROVED_QA_ONLY','root_review_reason':None,'mode':a.mode,'endpoint':C.ENDPOINT,'uid':1278,'node':C.NODE,
        'compatibility_controls_only':True,'full_dispatch_authorized':False,'production_ledger_opened':False,'new_population_rows':0,
        'new_UFF_calls':0,'new_QM_calls':0,'original_control_references':control['references'],'cost_policy':'REPORT_AND_CONTINUE',
        'original_failed_and_success_parent_accounts_not_rewritten':True,'sources_scientific_inheritance_checked_on_CPU':True}
    if a.mode=='probe':
        C.need(a.provider_review and a.publisher_identity and a.other_future_output_reserve_bytes is not None
            and a.other_future_output_reserve_bytes>=0,'ACTUAL_EXISTING_PROVIDER_AND_ROOT_OTHER_FUTURE_RESERVATION')
        provider_ref=C.M.pin(a.provider_review);identity_ref=C.M.pin(a.publisher_identity)
        _,_,refs=R.provider_resources(provider_ref,identity_ref)
        value.update(provider_review_reference=provider_ref,publisher_identity_reference=identity_ref,
            other_future_output_reserve_bytes=a.other_future_output_reserve_bytes)
        data=[control['base']['formal_source']]
    else:
        C.need(a.resource_binding is not None,'ACTUAL_NODE19_PROBE_C0_THEN_INDEPENDENT_ROOT_BINDING_REQUIRED')
        reference=C.M.pin(a.resource_binding);binding,_,_,refs=R.binding(reference)
        value.update(resource_binding_reference=reference,other_future_output_reserve_bytes=binding['other_future_output_reserve_bytes'])
        data=control['data_references']
    prior=[]
    for path in a.prior_accounting:
        r=C.M.pin(path);v=C.meta(r);C.need(v['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'
            and v['endpoint']==C.ENDPOINT and v['uid']==1278 and v['query_returncode']==0,'ACTUAL_PRIOR_COST_CLOSURE_NOT_FORECAST')
        prior.append(r);refs.extend((r,v['raw_sacct_reference']))
    sources=C.unique([*C.request_sources(control),*refs]);paths={r['path'] for r in sources}
    C.need(not paths.intersection(r['path'] for r in data),'SOURCE_DATA_REFS_DISJOINT_NO_LOGIN_DATA_HASH')
    value.update(source_references=sources,data_references=data,additional_prior_accounting_references=prior)
    print(json.dumps({'plan_candidate':C.M.write(out/'plan_candidate.json',value),'approved':False,'submitted':False}))


def binding_candidate(a,out):
    C.need(a.probe_receipt and a.probe_accounting and a.provider_review and a.publisher_identity
        and a.other_future_output_reserve_bytes is not None and a.other_future_output_reserve_bytes>=0,'ONLY_ACTUAL_PROBE_AND_EXISTING_PROVIDER')
    probe_ref=C.M.pin(a.probe_receipt);probe=C.meta(probe_ref);account_ref=C.M.pin(a.probe_accounting)
    raw=C.actual_account(account_ref,probe['job_id']);provider_ref=C.M.pin(a.provider_review);identity_ref=C.M.pin(a.publisher_identity)
    provider,_,refs=R.provider_resources(provider_ref,identity_ref);mount=R.validate_edge(probe,provider)
    proof,plan=R.probe_chain(probe,probe_ref)
    C.need(proof['job_id']==probe['job_id'] and proof['uid']==1278 and proof['request']['node']==C.NODE
        and proof['request']['scope_key']==C.key('probe') and proof['request']['scope_parameters']==C.scope('probe')
        and plan['schema']==C.SCHEMA and plan['mode']=='probe' and plan['status']=='APPROVED_QA_ONLY' and plan['reviewer']=='root'
        and plan['provider_review_reference']==provider_ref and plan['publisher_identity_reference']==identity_ref
        and plan['other_future_output_reserve_bytes']==a.other_future_output_reserve_bytes,'REAL_ORIGINAL_PROBE_REGISTERED_CHAIN')
    control=C.controls();C.need(probe['canonical_reference']==control['base']['formal_source']
        and probe['canonical_body_opened_or_hashed'] is False,'OBSERVED_STAT_IS_NOT_WHOLE_DATA_SHA')
    value={'schema':C.BINDING,'status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED','proposed_runtime_status':C.RESOURCE_STATUS,
        'root_review_reason':None,'endpoint':C.ENDPOINT,'uid':1278,'node':C.NODE,'compatibility_controls_only':True,
        'full_dispatch_authorized':False,'QA_output_cap_bytes':C.CAP,'other_future_output_reserve_bytes':a.other_future_output_reserve_bytes,
        'provider_review_reference':provider_ref,'publisher_identity_reference':identity_ref,'probe_receipt_reference':probe_ref,
        'probe_accounting_reference':account_ref,'compute_mount':mount,'canonical_reference':probe['canonical_reference'],
        'canonical_expected_frame':probe['canonical_stat'],'canonical_whole_SHA_required_later_on_actual_CPU':True,
        'source_evidence_references':C.unique([*refs,probe_ref,account_ref,raw,probe['startup_proof_reference'],probe['plan_reference']]),
        'does_not_modify_original_node13_review':True,'publisher_started_or_renewed':False,'new_population_or_full_writer_authorized':False}
    print(json.dumps({'resource_binding_candidate':C.M.write(out/'resource_binding_candidate.json',value),'approved':False}))


def stage(a,out):
    C.need(a.plan and a.stage_output and a.wall_seconds is not None,'ACTUAL_APPROVED_PLAN_NEW_OUTPUT_FINITE_WALL')
    ref=C.M.pin(a.plan);plan=C.meta(ref);mode=plan['mode'];control=C.controls()
    C.need(plan['schema']==C.SCHEMA and plan['status']=='APPROVED_QA_ONLY' and plan['reviewer']=='root'
        and plan['endpoint']==C.ENDPOINT and plan['uid']==1278 and plan['node']==C.NODE
        and plan['compatibility_controls_only'] is True and plan['full_dispatch_authorized'] is False
        and plan['production_ledger_opened'] is False and plan['new_population_rows']==0
        and plan['original_control_references']==control['references'],'ROOT_APPROVED_EXACT_COMPAT_ONLY_PLAN')
    cap=C.PROBE_CAP if mode=='probe' else C.CAP
    C.need((600<=a.wall_seconds<=900 if mode=='probe' else 1200<=a.wall_seconds<=7200)
        and a.stage_output.is_absolute() and C.BASE in a.stage_output.parents and '..' not in a.stage_output.parts
        and not a.stage_output.exists(),'NEW_OWN_QA_OUTPUT_AND_REQUEST_WALL_ONLY_NOT_FORECAST')
    if mode=='probe':
        _,_,refs=R.provider_resources(plan['provider_review_reference'],plan['publisher_identity_reference']);data=[control['base']['formal_source']]
    else:
        _,_,_,refs=R.binding(plan['resource_binding_reference']);data=control['data_references']
    C.need(plan['data_references']==data,'FROZEN_EXACT_DATA_DECLARATION_WITHOUT_LOGIN_BODY_READ')
    source=C.unique([*C.request_sources(control),*refs,*plan['source_references'],ref])
    for r in source:C.need(C.M.pin(r['path'])==r,'CURRENT_SMALL_METADATA_OR_SOURCE_PIN')
    C.need(not {r['path'] for r in source}.intersection(r['path'] for r in data),'NO_DATA_IN_SOURCE_HASH_SET')
    module='workflows.data_v1_final.conformers.pm7_multinode_compat32_v1.'+('resources' if mode=='probe' else 'run')
    argv=[R.Q.PY,'-B','-m',module,'--plan',str(a.plan),'--root-preflight','__ROOT_STARTUP_PROOF__','--output',str(a.stage_output)]
    authority=C.M.pin(C.REPO/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json')
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED',
        'proposed_runtime_status':'APPROVED_FOR_EXACT_STAGE','resource_authority_reference':authority,'kind':'analysis','scope_key':C.key(mode),
        'scope_parameters':C.scope(mode),'pilot':False,'wall_seconds':a.wall_seconds,'estimated_peak_output_bytes':cap,'stage_output_cap_bytes':cap,
        'execution_argv':argv,'source_status_stage':None,'scope_mode':'BOUNDED_METADATA_PREPARATION',
        'parent_evidence_references':C.unique([ref,*control['references'].values(),*plan['additional_prior_accounting_references']]),
        'root_review_reason':None}
    candidate_ref=C.M.write(out/'scope_candidate.json',review)
    spec={k:review[k] for k in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv','source_status_stage')}
    spec.update(schema='UNSIGNED_PM7_MULTINODE_COMPAT32_STAGE_INPUTS_V1',cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',
        source_references=C.unique([*source,authority]),data_references=data,
        scope={'mode':'BOUNDED_METADATA_PREPARATION','review':None,'parent_profile':None},unsigned_scope_candidate_reference=candidate_ref)
    if a.scope_review:
        approved=C.M.load(a.scope_review);C.need(approved['status']=='APPROVED_FOR_EXACT_STAGE' and approved['reviewer']=='root','INDEPENDENT_ROOT_EXACT_SCOPE_APPROVAL')
        for k in ('schema','resource_authority_reference','kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes',
            'execution_argv','source_status_stage','scope_mode','parent_evidence_references'):C.need(approved[k]==review[k],'EXACT_ROOT_REVIEW_FIELD:'+k)
        spec.update(schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1');spec['scope']['review']=C.M.pin(a.scope_review)
        spec['source_references']=C.unique([*spec['source_references'],spec['scope']['review']]);spec.pop('unsigned_scope_candidate_reference')
    print(json.dumps({'stage_inputs':C.M.write(out/('stage_spec.json' if a.scope_review else 'stage_inputs_candidate.json'),spec),'submitted':False}))


def main():
    C.need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','MAIN_LOGIN_STDLIB_METADATA_ONLY')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('candidate','binding-candidate','stage'))
    p.add_argument('--mode',choices=('probe','compat32'),default='probe')
    for name in ('provider-review','publisher-identity','resource-binding','probe-receipt','probe-accounting','plan','scope-review','stage-output','output'):
        p.add_argument('--'+name,type=pathlib.Path,required=name=='output')
    p.add_argument('--other-future-output-reserve-bytes',type=int);p.add_argument('--wall-seconds',type=int)
    p.add_argument('--prior-accounting',type=pathlib.Path,action='append',default=[]);a=p.parse_args()
    C.need(a.output.is_absolute() and C.RUN/'control' in a.output.parents and '..' not in a.output.parts
        and not a.output.exists() and not any(v.is_symlink() for v in (a.output,*a.output.parents)),'NEW_LITERAL_CONTROL_ONLY')
    a.output.mkdir(parents=True,mode=0o700)
    if a.command=='candidate':candidate(a,a.output)
    elif a.command=='binding-candidate':binding_candidate(a,a.output)
    else:stage(a,a.output)


if __name__=='__main__':main()
