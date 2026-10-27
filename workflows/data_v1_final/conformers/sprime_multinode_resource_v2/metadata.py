"""Source/small metadata only;no science bodies,no submission,no invented approval."""
import argparse,copy,json,pathlib
from . import contract as C,edge as E
from workflows.data_v1_final.conformers.sprime_cpu17_resource_v1 import metadata as EXISTING
from workflows.data_v1_final.execution.sprime_resource_epoch_v1 import metadata as OLD_META
from workflows.data_v1_final.execution.sprime_wave2_metadata_v1 import generate as G
from workflows.data_v1_final.execution.sprime_wave2_controller_v3 import controller as V
def references():
    refs=EXISTING.References({'source_references':[],'data_references':[]});EXISTING.sources(refs)
    for r in C.own_sources():refs.add(r)
    from workflows.data_v1_final.conformers.sprime_multinode_resource_v1 import contract as LC
    for r in LC.own_sources():refs.add(r)
    for r in C.sources().values():refs.add(r)
    from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as loc
    manifest,plan,_,_=V.fixed_inputs();oldquota=manifest['quota_reuse_review_reference']
    inputs=loc.input_locators(G.CONFIG,oldquota['path'])
    for r in inputs['source_references']+inputs['input_references']:refs.add(r,data=G.is_data(r['path']))
    for r in (V.MANIFEST,V.PLAN,plan['draft'],plan['root_review']):refs.add(r)
    for k in ('pilot_imports','original_deficits','unsupported'):refs.add(plan[k],data=True)
    return refs,manifest,plan
def add(refs,values,*,data=False):
    for r in values:refs.add(r,data=data or G.is_data(r['path']))
def fresh(path):
    p=pathlib.Path(path);C.need(C.Q.ROOT/'control' in p.parents and not p.exists() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'FRESH_SMALL_ROOT_CONTROL_DIRECTORY')
    p.mkdir(parents=True);return p
def diagnostic_draft(request_path,output):
    req=C.Q.load(request_path);C.need(req['schema']=='ROOT_REQUESTED_SPRIME_MULTINODE_DIAGNOSTIC_V2' and req['requested_by']=='root'
        and req['status']=='REQUESTED_FOR_REVIEW','ROOT_REQUEST_NOT_CHILD_APPROVAL')
    mode=req['mode'];node=C.node(req['node']);C.parameters(mode,node);out=fresh(output);refs,manifest,_=references();add(refs,[C.ref(request_path)])
    need=['output_directory']+([] if mode=='source3' else ['source3_reference'])
    if mode=='probe':need+=['provider_facts','canonical_reference','formal_source_receipt']
    if mode=='qa_prepare':need+=['node_binding_reference','quota_reuse_review_reference','original_audit_reference','excluded_mid_authority_reference']
    if mode=='compat32':need+=['node_binding_reference','quota_reuse_review_reference','qa_preparation_closure_reference','diagnostic_authorization_reference','qa_sources','excluded_mid_authority_reference']
    missing=[k for k in need if req.get(k) is None]
    if missing:return C.Q.write_new(out/'NONEXECUTABLE.json',{'status':'NONEXECUTABLE_MISSING_ACTUAL_PARENTS','missing':missing,'stage_spec_written':False,'science_or_submission_called':False})
    plan={k:v for k,v in req.items() if k not in ('schema','status','requested_by')};plan.update(schema='SPRIME_MULTINODE_DIAGNOSTIC_PLAN_V2',config_reference=manifest['config_reference'],source_references=C.own_sources())
    parents=[C.ref(request_path)];data=[]
    if mode!='source3':E.source3(req['source3_reference']);parents.append(req['source3_reference'])
    if mode=='probe':
        facts=req['provider_facts'];E.provider(facts,active=False)
        parents += [facts[k] for k in ('provider_review_reference','publisher_identity_reference','publisher_actual_launch_reference')]+[req['formal_source_receipt']]
        add(refs,E.Q.references(facts['provider_review_reference']))
    if mode in ('qa_prepare','compat32'):
        parents += E.exclusion_references(req['excluded_mid_authority_reference'])
        E.binding(req['node_binding_reference']);add(refs,E.references(req['node_binding_reference']));parents += [req['node_binding_reference'],req['quota_reuse_review_reference']]
        if mode=='qa_prepare':
            audit=E.meta(req['original_audit_reference']);parents.append(req['original_audit_reference']);data=[audit['tasks_reference'],next(r for r in audit['outputs'] if pathlib.Path(r['path']).name=='complete_packages.json')]
        else:
            close,prep=E.preparation_closure(req['qa_preparation_closure_reference'])
            C.need(prep['status']=='ORIGINAL32_TASKS_AND_BASELINES_CLOSED_NO_UFF','ACTUAL32_PREPARE_NOT_PLANNED_DATA')
            parents += [req['qa_preparation_closure_reference'],close['receipt_reference'],close['accounting_reference'],E.meta(close['accounting_reference'])['raw_sacct_reference'],req['diagnostic_authorization_reference'],*req['qa_sources'].values()]
            parents += [prep['startup_proof_reference'],E.meta(prep['startup_proof_reference'])['request_reference'],prep['plan_reference']]
            data=[prep['tasks_reference']]
    add(refs,parents);add(refs,data,data=True);pr=C.Q.write_new(out/'diagnostic_plan.json',plan);refs.add(pr)
    argv=[G.PY,'-B','-m',C.MODULE+'.'+('test_v1' if mode=='source3' else mode),'--plan',pr['path'],'--root-preflight',G.PROOF_PLACEHOLDER,'--output',req['output_directory']]
    cap={'source3':128<<20,'probe':128<<20,'qa_prepare':1<<30,'compat32':8<<30}[mode];wall={'source3':900,'probe':900,'qa_prepare':3600,'compat32':14400}[mode]
    return exact_draft(out,refs,'sprime_multinode_resource_'+mode+'_v2',C.parameters(mode,node),argv,wall,cap,'conformer' if mode=='compat32' else 'analysis',parents,pilot=mode=='compat32')
def exact_draft(out,refs,key,params,argv,wall,cap,kind,parents,*,pilot=False,profile=None,delegation=None):
    parents=list({r['path']:r for r in [*parents,C.sources()['cost_authority'],*([profile] if profile else [])]}.values());add(refs,parents)
    if profile is not None:refs.add(profile)
    refs.validate_small_sources()
    mode='BOUNDED_PERFORMANCE_BATCH' if pilot else 'FULL_SOURCE_AFTER_PROFILE' if profile else 'BOUNDED_METADATA_PREPARATION'
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,'resource_authority_reference':C.sources()['resource_authority'],
        'kind':kind,'scope_key':key,'scope_parameters':params,'pilot':pilot,'wall_seconds':wall,'estimated_peak_output_bytes':cap,'stage_output_cap_bytes':cap,
        'execution_argv':argv,'scope_mode':mode,'parent_evidence_references':parents,'approved_source_references':list(refs.sources.values()),'data_references':list(refs.data.values()),
        'bounded_batch_limits_reviewed':pilot,'original_scientific_quality_recipe_seed_orders_once_unchanged':True,'memory_gpu_exclusive_requested':False}
    if profile:review.update(profile_reviewed=True,approved_profile_reference=profile)
    template=C.Q.write_new(out/'root_review.template.json',review)
    draft=C.Q.write_new(out/'draft_receipt.json',{'schema':'SPRIME_MULTINODE_EXACT_STAGE_DRAFT_V2','review_template_reference':template,'profile_reference':profile,
        'fields':{k:review[k] for k in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv')},
        'source_references':list(refs.sources.values()),'data_references':list(refs.data.values()),'source_or_DATA_rewritten':False,'submitted_jobs':0})
    if delegation is not None:
        review.update(status='APPROVED_FOR_EXACT_STAGE',reviewer='root',explicit_root_controller_delegation_reference=delegation)
        approved=C.Q.write_new(out/'delegated_scope_review.json',review);return finalize(draft['path'],approved['path'],delegated=True)
    return draft
def finalize(draft_path,review_path,*,delegated=False):
    d=C.Q.load(draft_path);template=E.meta(d['review_template_reference']);rr=C.ref(review_path);root=E.meta(rr)
    C.need(rr!=d['review_template_reference'] and root['status']=='APPROVED_FOR_EXACT_STAGE' and root['reviewer']=='root','INDEPENDENT_ROOT_EXACT_SCOPE_REVIEW')
    for k,v in template.items():
        if k not in ('status','reviewer'):C.need(root[k]==v,'EXACT_REVIEW_FIELD:'+k)
    if not delegated:C.need('explicit_root_controller_delegation_reference' not in root,'NO_CHILD_OR_UNVALIDATED_DELEGATION')
    for r in d['source_references']:C.need(C.Q.pin(r['path'])==r,'SOURCE_METADATA_CHANGED_BEFORE_SPEC')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'source_references':[*d['source_references'],rr],'data_references':d['data_references'],'scope':{'mode':template['scope_mode'],'review':rr,'parent_profile':d['profile_reference']}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,C.sources()['resource_authority'],read_small=C.Q.read_small);return C.Q.write_new(pathlib.Path(draft_path).parent/'stage_spec.json',spec)
def expected_science_argv(stage,bid,proof_path,source_refs,resource):
    candidates=[]
    for r in source_refs:
        if pathlib.Path(r['path']).name=='stage_binding.json':
            b=E.meta(r)
            if b['stage']==stage and b['batch_id']==bid and b['epoch_reference']['path']==resource['_reference']['path']:candidates.append(b)
    C.need(len(candidates)==1,'ONE_CURRENT_EXACT_RESOURCE_STAGE_BINDING');b=candidates[0];config=b['config_reference']['path'];quota=b['quota_reuse_review_reference']['path']
    if stage=='prepare':return [G.PY,'-B',str(C.HERE/'prepare_batch.py'),'--config',config,'--plan',V.PLAN['path'],'--batch-id',bid,'--root-preflight',proof_path,'--quota-reuse-review',quota,'--output',str(G.WAVE2/bid/'prepared_mapping_v1')]
    if stage=='run':return [G.PY,'-B',str(C.HERE/'run_batch.py'),'--config',config,'--prepared',b['prepared_reference']['path'],'--root-preflight',proof_path,'--quota-reuse-review',quota,'--output',b['original_slot']['output_root']]
    return [G.PY,'-B',str(C.HERE/'close.py'),'close','--config',config,'--root-preflight',proof_path,'--quota-reuse-review',quota,'--descriptor',b['descriptor_reference']['path'],'--output',str(G.WAVE2/bid/'closed_v1')]
def delegated_stage(a):
    er=C.ref(a.epoch);resource=C.epoch(er,active=True);review=E.meta(C.ref(a.controller_review));resource=dict(resource,quota_reuse_references=review['quota_reuse_references'])
    C.root(review,'ROOT_SPRIME_MULTINODE_CONTROLLER_REVIEW_V2','APPROVED_FINITE_METADATA_CONTROLLER')
    C.need(review['resource_epoch_reference']==er and review['authorize_exact_metadata_stages_for_listed_future_batches'] is True and review['source_references']==C.own_sources()
        and a.batch_id in resource['allowed_initial_batch_ids'] and a.node in resource['node_binding_references'],'ACTUAL_EXPLICIT_ROOT_STAGE_DELEGATION_NOT_NEW_APPROVAL')
    refs,manifest,plan=references();out=fresh(a.output);stage=a.stage;bid=a.batch_id
    binding_ref=resource['node_binding_references'][a.node];add(refs,E.references(binding_ref));add(refs,[er,C.ref(a.controller_review),resource['adoption_reference'],resource['cutover_reference'],resource['whole_wave_reservation_inventory_reference']])
    quota=E.meta(resource['quota_reuse_references'][a.node]);C.need(quota['epoch_reference']==er and quota['node_binding_reference']==binding_ref,'SAME_ACTUAL_EPOCH_NODE_QUOTA_BINDING')
    refs.add(resource['quota_reuse_references'][a.node]);slot=next(s for s in plan['jobs'] if s['batch_id']==bid)
    parents=[er,C.ref(a.controller_review),binding_ref,resource['node_compat32_closure_references'][a.node],resource['quota_reuse_references'][a.node]]
    for n,r in resource['node_binding_references'].items():
        add(refs,E.references(r));add(refs,E.compatibility_references(resource['node_compat32_closure_references'][n],r))
    b={'schema':'SPRIME_MULTINODE_STAGE_BINDING_V2','epoch_reference':er,'stage':stage,'batch_id':bid,'node':a.node,'config_reference':manifest['config_reference'],
        'quota_reuse_review_reference':resource['quota_reuse_references'][a.node],'original_slot':slot,'prepared_reference':None,'descriptor_reference':None}
    ar,av,rows=G.account(a.accounting);G.add_account(refs,ar,av);parents.append(ar)
    if stage=='prepare':
        C.need('4521486' in rows and rows['4521486']['state']=='COMPLETED' and rows['4521486']['exit_code']=='0:0','ORIGINAL_FREEZE_ACTUAL_C0')
        refs.add(next(x for x in plan['batches'] if x['batch_id']==bid)['tasks'],data=True)
    else:
        hr=G.meta_pin(G.WAVE2/bid/'prepared_mapping_v1/prepared.json');header=E.meta(hr);C.need(header['plan']==V.PLAN and header['batch']['batch_id']==bid
            and header['config']==manifest['config_reference'] and header['kernel_sha256']==C.KERNEL_SHA,'ACTUAL_UNCHANGED_PREPARED_ORIGINAL_BATCH')
        b['prepared_reference']=hr;refs.add(hr);refs.add(header['tasks'],data=True);refs.add(header['formal_source'],data=True)
        for r in header['old_sprime_sources']:refs.add(r['reference'],data=True)
        if stage=='run':C.need(str(header['runtime']['job_id']) in rows and rows[str(header['runtime']['job_id'])]['state']=='COMPLETED' and rows[str(header['runtime']['job_id'])]['exit_code']=='0:0','ACTUAL_PREPARE_C0_BEFORE_NATIVE')
        else:
            entry=C.Q.load(a.registration);rq=E.meta(entry['request_reference']);sub=E.meta(entry['submission_reference']);jid=str(sub['job_id'])
            C.need(jid in rows and sub['request']==rq and sub['uid']==1278 and sub['sbatch_returncode']==0,'ACTUAL_TERMINAL_ORIGINAL_RUN_ACCOUNTING_NOT_FUTURE')
            descriptor=C.Q.write_new(out/'descriptor.json',{'plan':V.PLAN,'prepared':hr,'request':entry['request_reference'],'submission':entry['submission_reference'],'accounting':ar})
            b['descriptor_reference']=descriptor;add(refs,[descriptor,entry['request_reference'],entry['submission_reference']]);proof_ref=C.Q.pin(rq['startup_proof_path']);refs.add(proof_ref)
    br=C.Q.write_new(out/'stage_binding.json',b);refs.add(br);argv=expected_science_argv(stage,bid,G.PROOF_PLACEHOLDER,[br],resource)
    pilot=G.meta_pin(G.ROOT/'control/sprime_v3_censored_pilot_root_review_v1.json') if stage=='run' else None
    return exact_draft(out,refs,'sprime_multinode_resource_v2_'+stage,C.scope(stage,manifest['config_reference']),argv,{'prepare':14400,'run':28800,'close':7200}[stage],C.CAP,
        'conformer' if stage=='run' else 'analysis',parents,profile=pilot,delegation=C.ref(a.controller_review))
def template(a):
    request=C.Q.load(a.request);C.need(request.get('requested_by')=='root','ROOT_SUPPLIED_ACTUAL_TEMPLATE_INPUTS_ONLY');out=fresh(a.output)
    mode=a.template_kind;common={'status':'PENDING_INDEPENDENT_ROOT_REVIEW','reviewer':None,'endpoint':'202.38.247.57:22','uid':1278}
    if mode=='failed-compat-exclusions':
        value={**request,**common,'schema':'ROOT_SPRIME_COMPAT32_FAILED_START_EXCLUSION_V2',**E.exclusion_facts(request),
            'authorize_new_independent32_only_from_remaining33':False,'automatic_retry_old_started16':False};value.pop('requested_by',None)
    elif mode=='node-binding':
        if 'legacy_node_binding_reference' in request:
            from workflows.data_v1_final.conformers.sprime_multinode_resource_v1 import edge as L,contract as LC
            old=L.binding(request['legacy_node_binding_reference']);sc=request['source3_reference'];E.source3(sc)
            value={**old,**common,'schema':'ROOT_MAIN_SPRIME_NODE_RESOURCE_EDGE_V2','source3_reference':sc,'source_references':C.own_sources(),
                'legacy_node_binding_reference':request['legacy_node_binding_reference'],'legacy_source_context_references':LC.own_sources(),
                'resource_probe_origin_namespace':'sprime_multinode_resource_v1'}
            return C.Q.write_new(out/(mode+'_review.template.json'),value)
        sc=request['source3_reference'];E.source3(sc);close=E.meta(request['probe_closure_reference']);p=E.meta(close['receipt_reference']);proof=E.meta(p['startup_proof_reference'])
        E.validate_probe(p,proof);E.account(close['accounting_reference'],p['job_id'],p['node'])
        value={**common,'schema':'ROOT_MAIN_SPRIME_NODE_RESOURCE_EDGE_V2','node':p['node'],'source3_reference':sc,'probe_closure_reference':request['probe_closure_reference'],
            **p['provider_facts'],'compute_mount':p['storage']['mount'],'canonical_reference':p['canonical_reference'],'canonical_expected_frame':p['canonical_stat'],
            'environment':p['environment'],'source_references':C.own_sources(),'whole_wave_output_reserve_bytes':C.WAVE_RESERVE,'quota_reserve_bytes':200000000000,
            'provider_reserve_bytes':E.CAP,'admin_reserve_bytes':C.ADMIN}
    elif mode=='quota-reuse':
        r=request['node_binding_reference'];b=E.binding(r);er=request.get('epoch_reference')
        if er is not None:C.epoch(er,active=False)
        value={**common,'schema':'ROOT_SPRIME_MULTINODE_QUOTA_REUSE_V2','compute_node':b['node'],'node_binding_reference':r,'epoch_reference':er,
            'provider_review_reference':b['provider_review_reference'],'provider_source_reference':C.sources()['quota_provider'],'whole_wave_output_reserve_bytes':C.WAVE_RESERVE,
            'scientific_authority_is_separate':True}
    elif mode=='adoption':
        cut=E.meta(request['cutover_reference']);C.need(cut['status']=='OLD_METADATA_STOPPED_LOCKS_OBSERVED_ADOPTION_PENDING_ROOT','ACTUAL_CUTOVER_NOT_INTENDED_STOP')
        value={**common,'schema':'ROOT_SPRIME_MULTINODE_ACTUAL_ADOPTION_V2','cutover_reference':request['cutover_reference'],'old_latest_state_reference':cut['old_latest_state_reference'],
            'registrations':cut['observed_old_registrations'],'all_179_stage_paths_reconciled_after_old_stop':False,'running_science_untouched':True,'pending_actions_only_explicit_keep_existing':False,
            'Root_must_reconcile_current_req_sub_activation_registry_and_preserve_all_costs':True}
    elif mode=='controller':
        er=request['resource_epoch_reference'];resource=C.epoch(er,active=False)
        value={**common,'schema':'ROOT_SPRIME_MULTINODE_CONTROLLER_REVIEW_V2','resource_epoch_reference':er,'adoption_reference':resource['adoption_reference'],
            'source_references':C.own_sources(),'quota_reuse_references':request['quota_reuse_references'],'authorize_exact_metadata_stages_for_listed_future_batches':False,
            'automatic_retry_or_lease_renewal':False,'manual_start_required':True}
    elif mode=='epoch':
        # Inputs are actual Root-collected references and explicit numeric
        # choices,not a generated publisher/probe/compatibility or future pin.
        value={**request,**common,'schema':'ROOT_MAIN_MULTINODE_SPRIME_EPOCH_V2','original_manifest_reference':V.MANIFEST,'original_plan_reference':V.PLAN,
            'own_source_references':C.own_sources(),'original_batch_ids':list(G.BATCHES),'whole_wave_output_reserve_bytes':C.WAVE_RESERVE,
            'production_once_namespace_changed':False,'automatic_retry_or_lease_renewal':False}
        value.pop('requested_by',None)
        for n,r in value.get('node_binding_references',{}).items():E.binding(r);E.compatibility(value['node_compat32_closure_references'][n],r)
        absent=[k for k in ('cutover_reference','adoption_reference','whole_wave_reservation_inventory_reference','old_controller_identity_reference','old_controller_review_reference',
            'node_binding_references','node_compat32_closure_references','maximum_science_per_node','maximum_aux_per_node','maximum_nonterminal_science','maximum_nonterminal_aux',
            'maximum_owned_data_run_pending','minimum_reserved_free_CPU_total','allowed_initial_batch_ids','maximum_seconds','started_unix_seconds','deadline_unix_seconds') if value.get(k) is None]
        if absent:return C.Q.write_new(out/'NONEXECUTABLE.json',{'status':'NONEXECUTABLE_MISSING_ACTUAL_EPOCH_PARENTS_OR_EXPLICIT_LIMITS','missing':absent,'no_future_refs_or_approval_created':True})
    else:raise ValueError('EXACT_TEMPLATE_KIND')
    return C.Q.write_new(out/(mode+'_review.template.json'),value)
def main():
    C.Q.on_login();p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    d=sub.add_parser('draft-diagnostic');d.add_argument('--request',type=pathlib.Path,required=True);d.add_argument('--output',type=pathlib.Path,required=True)
    f=sub.add_parser('finalize');f.add_argument('--draft',type=pathlib.Path,required=True);f.add_argument('--root-review',type=pathlib.Path,required=True)
    s=sub.add_parser('delegated-stage')
    for k in ('epoch','controller-review','accounting','output'):s.add_argument('--'+k,type=pathlib.Path,required=True)
    s.add_argument('--node',required=True);s.add_argument('--stage',choices=('prepare','run','close'),required=True);s.add_argument('--batch-id',required=True);s.add_argument('--registration',type=pathlib.Path)
    t=sub.add_parser('template');t.add_argument('--template-kind',choices=('failed-compat-exclusions','node-binding','quota-reuse','adoption','epoch','controller'),required=True);t.add_argument('--request',type=pathlib.Path,required=True);t.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args();print(diagnostic_draft(a.request,a.output) if a.action=='draft-diagnostic' else finalize(a.draft,a.root_review) if a.action=='finalize' else template(a) if a.action=='template' else delegated_stage(a))
if __name__=='__main__':main()
