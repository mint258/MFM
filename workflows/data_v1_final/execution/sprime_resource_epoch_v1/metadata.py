"""Root finite resource metadata: no publisher start, submission, science or body reads."""
from __future__ import annotations
import argparse,copy,json,pathlib,re,time
from . import contract as E
from workflows.data_v1_final.execution.sprime_wave2_recovery96_v1 import metadata as M
G=E.G;F=E.F;V=E.V;Q=E.Q;K=E.K;W=E.W


def approved(args):F.need(args.root_approve_exact_stage and args.root_reason.strip(),'ROOT_EXPLICIT_METADATA_DECISION_REQUIRED')


def new_output(path):
    out=E.own_path(path,fresh=True);out.mkdir(parents=True,mode=0o700);return out


def template(args):
    # An explicit request permits drafting only. Root approves the resulting copy separately.
    rr,request=G.metadata(args.root_request,'ROOT_REQUEST_SPRIME_PROVIDER_REVIEW_TEMPLATE_V1')
    F.need(request['status']=='REQUESTED_FOR_REVIEW' and request['requested_by']=='root'
      and request['publisher_output_directory']==str(args.publisher_output),'ROOT_REQUESTED_NEW_PROVIDER_DIRECTORY')
    manifest,_,_,_=V.fixed_inputs();old_reuse=E.refread(manifest['quota_reuse_review_reference'])
    old_ref=old_reuse['provider_review_reference'];old=E.refread(old_ref)
    target=E.own_path(args.publisher_output,fresh=True)
    out=new_output(args.output)
    value=copy.deepcopy(old);value.update(status='PENDING_INDEPENDENT_ROOT_REVIEW',reviewer=None,
      publisher_output_dir=str(target),previous_provider_review_reference=old_ref,
      root_scope_notes='New finite independent publisher directory only. Original mapping, limits, freshness and reserve unchanged. Root must approve; no startup or science authority from this draft.',
      provider_review_template_request_reference=rr)
    ref=G.write_new(out/'provider_review.template.json',value)
    print(json.dumps({'provider_review_template':ref,'publisher_started':False,'approved':False,'runnable_stage_generated':False}),flush=True)


def bind(args):
    approved(args);br,b=G.metadata(args.root_review,E.BIND_SCHEMA)
    E.root(b,E.BIND_SCHEMA,'APPROVED_NEW_FINITE_RESOURCE_FACTS_ONLY')
    manifest,_,old_identity_ref,_=V.fixed_inputs();old_reuse_ref=manifest['quota_reuse_review_reference'];old=E.refread(old_reuse_ref)
    F.need(b['previous_quota_reuse_review_reference']==old_reuse_ref and b['whole_wave_output_reserve_bytes']==G.WAVE_RESERVE
      and b['provider_output_reserve_bytes']==64<<20 and b['admin_output_reserve_bytes']==F.ADMIN
      and b['quota_reserve_bytes']==200000000000 and b['scientific_authority_is_separate'] is True
      and b['publisher_auto_renew'] is False,'EXACT_ROOT_NEW_FINITE_RESOURCE_FACTS_NO_SCIENCE_APPROVAL')
    nr=b['provider_review_reference'];review=Q.load_review(nr)
    E.same_provider_scope(E.refread(old['provider_review_reference']),review)
    F.need(review['previous_provider_review_reference']==old['provider_review_reference'],'EXPLICIT_ORIGINAL_PROVIDER_REVIEW_HISTORY')
    ir=b['publisher_identity_reference'];identity=E.refread(ir,Q.IDENTITY_SCHEMA)
    F.need(ir!=old_identity_ref and pathlib.Path(ir['path'])==pathlib.Path(review['publisher_output_dir'])/'identity.json',
      'ACTUAL_NEW_DISTINCT_PUBLISHER_IDENTITY')
    launch=E.refread(b['publisher_actual_launch_reference'])
    F.need(launch['schema']=='ROOT_ACTUAL_MAIN_N1_V4_FINITE_QUOTA_PUBLISHER_LAUNCH_V1'
      and launch['endpoint']=='202.38.247.57:22' and launch['uid']==1278 and launch['review_reference']==nr
      and launch['actual_pid']==identity['pid'] and launch['actual_start_ticks']==identity['start_ticks']
      and launch['actual_boot_id']==identity['boot_id'] and launch['actual_argv']==identity['execution_argv']
      and launch['science_jobs_launched_by_publisher']==0
      and launch['maximum_runtime_seconds']==identity['expires_unix_seconds']-identity['started_unix_seconds'],
      'ACTUAL_NEW_LAUNCH_RECEIPT_NOT_FUTURE_PID')
    proc=V.process_identity(identity['pid'])
    F.need(proc['start_ticks']==identity['start_ticks'] and proc['boot_id']==identity['boot_id']
      and proc['argv']==identity['execution_argv'] and proc['cgroup']==launch['actual_cgroup'],'ACTUAL_CURRENT_ROOT_PUBLISHER_PROCESS_IDENTITY')
    sr=b['first_healthy_snapshot_reference'];snap=Q.pinned(sr)
    F.need(pathlib.Path(sr['path']).parent==pathlib.Path(review['publisher_output_dir'])
      and re.fullmatch(r'observation_[0-9]{6}\.json',pathlib.Path(sr['path']).name),'ORIGINAL_FINITE_SNAPSHOT_FILENAME')
    Q.validate_observation(snap,identity,ir,review,nr,time.time())
    out=new_output(args.output)
    reuse=copy.deepcopy(old);reuse.update(provider_review_reference=nr,
      provider_actual_launch_reference=b['publisher_actual_launch_reference'],publisher_identity_reference=ir,
      publisher_actual_expiry_unix_seconds=identity['expires_unix_seconds'],previous_resource_review_reference=old_reuse_ref,
      resource_epoch_root_binding_reference=br,publisher_started_or_renewed_by_generator=False,
      root_decision_reason=args.root_reason,
      root_review_notes='Root explicitly supplied an actual new independent finite resource epoch. Old identity/reviews/expiry retained. Original CPU13 map,182 caps/provider/admin/200GB and30/60/120 unchanged. No automatic renewal or science approval.')
    qr=G.write_new(out/'quota_reuse_review.json',reuse)
    e={'schema':E.EPOCH_SCHEMA,'status':'ACTUAL_PUBLISHER_BOUND_CPU_PROBE_STILL_REQUIRED',
      'root_binding_reference':br,'provider_review_reference':nr,'publisher_identity_reference':ir,
      'publisher_actual_launch_reference':b['publisher_actual_launch_reference'],'first_healthy_snapshot_reference':sr,
      'quota_reuse_review_reference':qr,'previous_quota_reuse_review_reference':old_reuse_ref,
      'original_manifest_reference':V.MANIFEST,'original_plan_reference':V.PLAN,
      'source_references':E.sources(),'reused_source_references':V.sources()+W.extra_sources(),'whole_wave_output_reserve_bytes':G.WAVE_RESERVE,
      'provider_output_reserve_bytes':64<<20,'admin_output_reserve_bytes':F.ADMIN,'quota_reserve_bytes':200000000000,
      'no_auto_renew':True,'CPU_probe_C0_claimed':False,'science_stage_generation_authorized':False}
    er=G.write_new(out/'epoch_manifest.json',e);E.epoch_inputs(er)
    print(json.dumps({'epoch_manifest':er,'quota_reuse_review':qr,'CPU_probe_required':True,'science_stages':0,'publisher_started_by_helper':False}),flush=True)


def stage_spec(out,refs,stage,config_ref,argv,parents,args,*,probe=False,delegated=None):
    approved(args)
    authority=F.sources()['resource_authority'];cost=F.sources()['cost_authority']
    pilot_ref=None if probe else refs.small(G.ROOT/'control/sprime_v3_censored_pilot_root_review_v1.json')
    parents=[*parents,cost]
    if pilot_ref is not None:parents.append(pilot_ref)
    if delegated is not None:parents.append(delegated)
    parents=list({r['path']:F.triple(r) for r in parents}.values())
    for ref in parents:refs.add(ref)
    if probe:
        key,params,wall,cap,kind,mode=E.PROBE_KEY,E.PROBE_PARAMS,900,E.PROBE_CAP,'analysis','BOUNDED_METADATA_PREPARATION'
    else:
        key,params='sprime_formal_cpu_auto_v3_'+stage,F.scope(stage,config_ref)
        wall={'prepare':14400,'run':28800,'close':7200}[stage];cap=F.CAP
        kind='conformer' if stage=='run' else 'analysis';mode='FULL_SOURCE_AFTER_PROFILE' if stage=='run' else 'BOUNDED_METADATA_PREPARATION'
    r={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root',
      'resource_authority_reference':authority,'kind':kind,'scope_key':key,'scope_parameters':params,'pilot':False,
      'wall_seconds':wall,'estimated_peak_output_bytes':cap,'stage_output_cap_bytes':cap,'execution_argv':argv,
      'scope_mode':mode,'parent_evidence_references':parents,'root_review_reason':args.root_reason,
      'scientific_quality_thresholds_unchanged':True,'no_scientific_data_read_or_hashed_on_login':True,
      'publisher_started_or_renewed_by_helper':False,'automatic_retry':False,
      'resource_epoch_source_references':E.sources(),'full_forecast_status':F.FORECAST,'estimated_full_core_hours':None,
      'whole_wave_reservation_not_reduced_for_completed_slots':True}
    if delegated is not None:r['explicit_root_controller_delegation_reference']=delegated
    if stage=='run' and not probe:r.update(profile_reviewed=True,approved_profile_reference=pilot_ref)
    rr=G.write_new(out/'scope_review.json',r);refs.add(rr);refs.validate_small_sources()
    s={k:r[k] for k in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv')}
    s.update(schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',
      source_references=list(refs.sources.values()),data_references=list(refs.data.values()),
      scope={'mode':mode,'review':rr,'parent_profile':pilot_ref})
    sp=G.write_new(out/'stage_spec.json',s)
    print(json.dumps({'stage_spec':sp,'scientific_bodies_read':0,'jobs_submitted':0,'publisher_started':False}),flush=True)


def base_refs(args,er,e,pc_ref=None,pc=None):
    config,value,refs,pilot,mapping=G.common_inputs(args)
    E.add_epoch(refs,er,e)
    if pc_ref is not None:E.add_probe(refs,pc_ref,pc)
    for n in M.FILES:refs.small(M.HERE/n)
    for n in ('__init__.py','admission.py','run.py','test_admission.py','README.md'):refs.small(M.CLOSER/n)
    return config,value,refs,pilot,mapping


def probe_stage(args):
    approved(args);er,e=G.metadata(args.epoch,E.EPOCH_SCHEMA);E.epoch_inputs(er)
    config=V.fixed_inputs()[0]['config_reference'];value=F.config(config)
    refs=G.References({'source_references':[],'data_references':[]});G.original_sources(refs)
    refs.add(config)
    for key in ('recipe_config','roles_authority','formal_source_receipt','sprime_manifest'):refs.add(value[key])
    E.add_epoch(refs,er,e)
    output=E.own_path(args.probe_output,base=F.BASE,fresh=True)
    out=new_output(args.output)
    cfg=G.write_new(out/'probe_config.json',{'schema':'SPRIME_NEW_RESOURCE_EPOCH_CPU_PROBE_CONFIG_V1',
      'epoch_reference':er,'quota_reuse_review_reference':e['quota_reuse_review_reference'],
      'original_config_reference':config,'output_directory':str(output),'output_cap_bytes':E.PROBE_CAP})
    refs.add(cfg)
    argv=[G.PY,'-B','-m','workflows.data_v1_final.execution.sprime_resource_epoch_v1.probe',
      '--config',cfg['path'],'--startup-proof',G.PROOF_PLACEHOLDER]
    stage_spec(out,refs,'probe',config,argv,[er,cfg,e['root_binding_reference']],args,probe=True)


def close_probe(args):
    approved(args);er,e=G.metadata(args.epoch,E.EPOCH_SCHEMA);E.epoch_inputs(er,active=False)
    report_ref,report=G.metadata(args.probe_report,'ACTUAL_NEW_SPRIME_RESOURCE_EPOCH_CPU_PROBE_V1')
    proof_ref,proof=G.metadata(args.probe_proof)
    ar,av,_=G.account(args.accounting,[str(proof['job_id'])],c0=[str(proof['job_id'])])
    c={'schema':'ACTUAL_NEW_SPRIME_EPOCH_CPU13_PROBE_CLOSURE_V1','status':'ACTUAL_C0_HEALTHY_NEW_EPOCH_PROBE_CLOSED',
      'epoch_reference':er,'report_reference':report_ref,'startup_proof_reference':proof_ref,
      'request_reference':proof['request_reference'],'accounting_reference':ar,'raw_accounting_reference':av['raw_sacct_reference'],
      'source_references':E.sources(),'new_UFF_QM_calls':0,'scientific_bodies_read':0}
    E.validate_probe_closure(c,er)
    out=new_output(args.output);ref=G.write_new(out/'probe_closure.json',c)
    print(json.dumps({'actual_probe_closure':ref,'science_stages_generated':0}),flush=True)


def science_inputs(args):
    approved(args);er,e=G.metadata(args.epoch,E.EPOCH_SCHEMA);E.epoch_inputs(er)
    pc_ref,_=G.metadata(args.probe_closure,'ACTUAL_NEW_SPRIME_EPOCH_CPU13_PROBE_CLOSURE_V1')
    pc=E.probe_closure(pc_ref,er)
    return er,e,pc_ref,pc


def run96(args):
    er,e,pcr,pc=science_inputs(args)
    dr,d,refs,pr,plan,hr,header,wr,wave,_=M.inputs(args)
    F.need(d['probe_report_reference']==pc['report_reference'] and d['probe_startup_proof_reference']==pc['startup_proof_reference']
      and d['probe_accounting_reference']==pc['accounting_reference']
      and d['storage_review_reference']==e['root_binding_reference'],'EXACT_ACTUAL_NEW_EPOCH96_PROBE_AND_ROOT_STORAGE_DECISION')
    E.add_epoch(refs,er,e);E.add_probe(refs,pcr,pc)
    out=new_output(args.output);derived=K.derive_plan(plan,pr,wr,wave,dr)
    nr=G.write_new(out/'derived_plan.json',derived);nh=G.write_new(out/'derived_prepared.json',K.derive_prepared(header,hr,nr,dr))
    slot=derived['jobs'][0]
    br=G.write_new(out/'continuation_bundle.json',{'schema':'SPRIME96_ORIGINAL500_CONTINUATION_METADATA_V1',
      'decision_reference':dr,'origin_plan_reference':pr,'origin_prepared_reference':hr,'plan_reference':nr,
      'prepared_reference':nh,'replacement_wave_review_reference':wr,'slot':slot,
      'science_primary_reference':G.meta_pin(G.FORMAL/'run_batch.py'),'old_tasks_reference_unchanged':header['tasks'],
      'resource_epoch_reference':er,'probe_closure_reference':pcr,
      'new_task_keys_or_seeds':False,'new_CPU_freeze_or_prepare_claimed':False,'jobs_submitted':0})
    for r in (nr,nh,br):refs.add(r)
    argv=[G.PY,'-B',str(G.FORMAL/'run_batch.py'),'--config',header['config']['path'],'--prepared',nh['path'],
      '--root-preflight',G.PROOF_PLACEHOLDER,'--quota-reuse-review',e['quota_reuse_review_reference']['path'],'--output',slot['output_root']]
    stage_spec(out,refs,'run',header['config'],argv,[dr,wr,nr,nh,br,er,pcr],args)


def close96(args):
    er,e,pcr,pc=science_inputs(args)
    dr,d,refs,pr,plan,hr,header,wr,wave,_=M.inputs(args)
    F.need(d['probe_report_reference']==pc['report_reference'] and d['storage_review_reference']==e['root_binding_reference'],
      'SAME_ACTUAL96_NEW_EPOCH_DECISION')
    br,b=G.metadata(args.continuation_bundle,'SPRIME96_ORIGINAL500_CONTINUATION_METADATA_V1')
    F.need(b['decision_reference']==dr and b['resource_epoch_reference']==er and b['probe_closure_reference']==pcr
      and b['origin_plan_reference']==pr and b['origin_prepared_reference']==hr,'SAME_EXACT96_RESOURCE_BUNDLE')
    nr=b['plan_reference'];nh=b['prepared_reference'];slot=b['slot']
    F.need(E.refread(nr)==K.derive_plan(plan,pr,wr,wave,dr) and E.refread(nh)==K.derive_prepared(header,hr,nr,dr)
      and slot==wave['jobs'][0],'EXACT_REVERSIBLE96_LINEAGE_NO_TASK_CHANGES')
    rq,request=G.metadata(args.request);sr,sub=G.metadata(args.submission,'CPU_AUTO_MEMORY_SUBMISSION_V1')
    ar,av,_=G.account(args.accounting,[str(sub['job_id'])]);G.add_account(refs,ar,av)
    expected=[G.PY,'-B',str(G.FORMAL/'run_batch.py'),'--config',header['config']['path'],'--prepared',nh['path'],
      '--root-preflight',request['startup_proof_path'],'--quota-reuse-review',e['quota_reuse_review_reference']['path'],'--output',slot['output_root']]
    F.need(sub['request_reference']==rq and sub['request']==request and sub['sbatch_returncode']==0 and sub['uid']==1278
      and request['execution_argv']==expected and request['job_name']==slot['job_name'] and er in request['source_references'],
      'ACTUAL_TERMINAL_NEW96_RUN_FULL_RESOURCE_OPTIONS')
    E.add_epoch(refs,er,e);E.add_probe(refs,pcr,pc)
    for r in (br,nr,nh,rq,sr):refs.add(r)
    out=new_output(args.output);descriptor=G.write_new(out/'descriptor.json',{'plan':nr,'prepared':nh,'request':rq,'submission':sr,'accounting':ar});refs.add(descriptor)
    name=d['replacement_closed_directory_name'];F.need(type(name) is str and re.fullmatch('[a-z][a-z0-9_]{1,127}',name),'EXACT_NEW96_CLOSED_DIRECTORY_NAME')
    output=pathlib.Path(slot['output_root']).parent/name
    F.need(output!=pathlib.Path(d['original_closed_reference']['path']).parent and output!=pathlib.Path(slot['output_root']),
      'KEEP_ORIGINAL96_CLOSE_AND_OUTPUT_UNTOUCHED')
    argv=[G.PY,'-B',str(M.CLOSER/'run.py'),'close','--config',header['config']['path'],'--root-preflight',G.PROOF_PLACEHOLDER,
      '--quota-reuse-review',e['quota_reuse_review_reference']['path'],'--descriptor',descriptor['path'],'--output',str(output)]
    stage_spec(out,refs,'close',header['config'],argv,[er,pcr,dr,wr,br,nr,nh,rq,sr,ar,descriptor],args)


def future_stage(args):
    # Root's actual post96 controller review explicitly delegates only these83 stages.
    er,e,pcr,pc=science_inputs(args)
    ctr,review=G.metadata(args.controller_review,E.CONTROLLER_SCHEMA)
    checked,_,_,_,recovery=E.controller_inputs(ctr)
    F.need(checked==review and review['resource_epoch_reference']==er and review['probe_closure_reference']==pcr
      and args.batch_id in E.FUTURE,'ONLY_ROOT_REVIEWED_FUTURE97_THROUGH179')
    config,_,refs,pilot,mapping=base_refs(args,er,e,pcr,pc)
    refs.add(ctr);refs.add(review['continuation_repair_map_reference'])
    for key in ('pure_recovery_cpu_test_reference','pure_epoch_cpu_test_reference'):
        tr=review[key];t=E.refread(tr);refs.add(tr);ar=t['accounting_reference'];av=E.refread(ar);G.add_account(refs,ar,av)
    plan=E.refread(V.PLAN);F.approve_wave(plan['draft'],F.read(plan['draft']),plan['root_review'],config)
    batch=next(b for b in plan['batches'] if b['batch_id']==args.batch_id)
    slot=next(b for b in plan['jobs'] if b['batch_id']==args.batch_id)
    F.need(slot['wall_seconds']==28800 and slot['cpus']==16 and slot['node']=='compute-0-13','ORIGINAL_EXACT_FUTURE_SLOT')
    # New resource binding only: original plan/header/task references remain unchanged.
    for key in ('pilot_imports','original_deficits','unsupported'):refs.add(plan[key],data=True)
    refs.add(batch['tasks'],data=True)
    for r in (V.PLAN,plan['draft'],plan['root_review']):refs.add(r)
    parents=[er,pcr,ctr,V.PLAN,plan['draft'],plan['root_review'],review['continuation_repair_map_reference']]
    prepared_path=G.WAVE2/args.batch_id/'prepared_mapping_v1/prepared.json'
    if args.stage=='prepare':
        ar,av,_=G.account(args.accounting,[str(plan['runtime']['job_id'])],c0=[str(plan['runtime']['job_id'])]);G.add_account(refs,ar,av);parents.append(ar)
        argv=[G.PY,'-B',str(G.MAPPED/'prepare_batch.py'),'--config',config['path'],'--plan',V.PLAN['path'],'--batch-id',args.batch_id,
          '--root-preflight',G.PROOF_PLACEHOLDER,'--quota-reuse-review',e['quota_reuse_review_reference']['path'],
          '--source-mapping-review',mapping['path'],'--output',str(prepared_path.parent)]
    else:
        F.need(args.prepared==prepared_path,'EXACT_ORIGINAL_FUTURE_PREPARED_LOCATOR')
        hr,header=G.metadata(prepared_path,F.SCHEMAS['prepared'])
        F.need(header['status']=='ORIGINAL_BATCH_INPUTS_READY_NOT_GENERATED' and header['config']==config
          and header['plan']==V.PLAN and header['batch']==batch and header['molecules']==batch['molecules']
          and header['kernel_sha256']==F.KERNEL_SHA,'ACTUAL_ORIGINAL_FUTURE_PREPARED_HEADER_NO_REWRITE')
        refs.add(hr);parents.append(hr);refs.add(header['tasks'],data=True)
        for old in header['old_sprime_sources']:refs.add(old['reference'],data=True)
        refs.add(header['formal_source'],data=True)
        if args.stage=='run':
            ar,av,_=G.account(args.accounting,[str(header['runtime']['job_id'])],c0=[str(header['runtime']['job_id'])]);G.add_account(refs,ar,av);parents.append(ar)
            argv=[G.PY,'-B',str(G.FORMAL/'run_batch.py'),'--config',config['path'],'--prepared',str(prepared_path),
              '--root-preflight',G.PROOF_PLACEHOLDER,'--quota-reuse-review',e['quota_reuse_review_reference']['path'],'--output',slot['output_root']]
        else:
            rq,request=G.metadata(args.request);sr,sub=G.metadata(args.submission,'CPU_AUTO_MEMORY_SUBMISSION_V1')
            F.need(args.request==G.ROOT/'control/requests'/(slot['job_name']+'.json')
              and args.submission==G.ROOT/'control/submissions'/(slot['job_name']+'.json'),'EXACT_ORIGINAL_FUTURE_REGISTRATION_LOCATORS')
            ar,av,_=G.account(args.accounting,[str(sub['job_id'])]);G.add_account(refs,ar,av);parents.extend((rq,sr,ar))
            expected=[G.PY,'-B',str(G.FORMAL/'run_batch.py'),'--config',config['path'],'--prepared',str(prepared_path),
              '--root-preflight',request['startup_proof_path'],'--quota-reuse-review',e['quota_reuse_review_reference']['path'],'--output',slot['output_root']]
            F.need(sub['request_reference']==rq and sub['request']==request and sub['sbatch_returncode']==0 and sub['uid']==1278
              and request['execution_argv']==expected and request['job_name']==slot['job_name'] and er in request['source_references'],
              'ACTUAL_NEW_EPOCH_FUTURE_RUN_REQUEST_COMPLETE_OPTIONS')
            out=new_output(args.output)
            descriptor=G.write_new(out/'descriptor.json',{'plan':V.PLAN,'prepared':hr,'request':rq,'submission':sr,'accounting':ar})
            refs.add(descriptor);parents.append(descriptor)
            argv=[G.PY,'-B',str(G.CLOSER/'run.py'),'close','--config',config['path'],'--root-preflight',G.PROOF_PLACEHOLDER,
              '--quota-reuse-review',e['quota_reuse_review_reference']['path'],'--descriptor',descriptor['path'],'--output',str(G.WAVE2/args.batch_id/'closed_v1')]
    if args.stage!='close':out=new_output(args.output)
    stage_spec(out,refs,args.stage,config,argv,parents,args,delegated=ctr)


def controller_template(args):
    er,e,pcr,pc=science_inputs(args)
    mr,m=G.metadata(args.recovery_map,'ROOT_SPRIME96_UNSTARTED_CONTINUATION_ADOPTION_MAP_V4')
    prior_ref,prior=G.metadata(args.prior_controller_review,'ROOT_FINITE_SPRIME_WAVE2_CONTROLLER_REVIEW_V3')
    W.prior_review(prior)
    identity=E.refread(e['publisher_identity_reference'])
    E.deadline(args.deadline_unix_seconds,identity,time.time())
    value={'schema':E.CONTROLLER_SCHEMA,'status':'PENDING_INDEPENDENT_ROOT_REVIEW','reviewer':None,
      'endpoint':'202.38.247.57:22','uid':1278,'manifest_reference':V.MANIFEST,'plan_reference':V.PLAN,
      'adoption_reference':prior['adoption_reference'],'source_references':V.sources(),
      'continuation_source_references':W.extra_sources(),'resource_epoch_source_references':E.sources(),
      'resource_epoch_reference':er,'probe_closure_reference':pcr,'publisher_identity_reference':e['publisher_identity_reference'],
      'continuation_repair_map_reference':mr,'supersedes_review_reference':prior_ref,
      'resume_from_state_reference':m['original_HOLD_reference'],
      'maximum_nonterminal_science':2,'maximum_nonterminal_aux':1,'maximum_owned_data_run_pending':4,
      'stop_before_publisher_expiry_seconds':300,'deadline_unix_seconds':args.deadline_unix_seconds,
      'allowed_future_batch_ids':list(E.FUTURE),'authorize_exact_metadata_stages_for_listed_future_batches':True,
      'automatic_retry':False,'publisher_auto_renew':False,'root_reason':args.root_reason,
      'pure_recovery_cpu_test_reference':G.meta_pin(args.recovery_tests),
      'pure_epoch_cpu_test_reference':G.meta_pin(args.epoch_tests)}
    # Validate the complete actual96/test chain without granting approval to the emitted template.
    check=dict(value,status='APPROVED_FINITE_METADATA_CONTROLLER',reviewer='root')
    E.validate_controller_value(check)
    out=new_output(args.output);ref=G.write_new(out/'controller_review.template.json',value)
    print(json.dumps({'controller_review_template':ref,'approved':False,'controller_started':False}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('provider-template','bind','probe-stage','close-probe','run96','close96','controller-template','future-stage'))
    p.add_argument('--output',type=pathlib.Path,required=True)
    for key in ('root-request','publisher-output','root-review','epoch','probe-output','probe-report','probe-proof','accounting',
      'probe-closure','decision','wave-review','continuation-bundle','request','submission','controller-review','prepared',
      'recovery-map','prior-controller-review','recovery-tests','epoch-tests'):
        p.add_argument('--'+key,type=pathlib.Path)
    p.add_argument('--stage',choices=('prepare','run','close'));p.add_argument('--batch-id')
    p.add_argument('--deadline-unix-seconds',type=float)
    p.add_argument('--root-approve-exact-stage',action='store_true');p.add_argument('--root-reason',default='')
    a=p.parse_args();G.on_login()
    F.need(E.HERE==G.REPO/'workflows/data_v1_final/execution/sprime_resource_epoch_v1','ACTUAL_INTEGRATED_MAIN_METADATA_SOURCE')
    required={'provider-template':('root_request','publisher_output'),'bind':('root_review',),
      'probe-stage':('epoch','probe_output'),'close-probe':('epoch','probe_report','probe_proof','accounting'),
      'run96':('epoch','probe_closure','decision','wave_review'),
      'close96':('epoch','probe_closure','decision','wave_review','continuation_bundle','request','submission','accounting'),
      'controller-template':('epoch','probe_closure','recovery_map','prior_controller_review','recovery_tests','epoch_tests','deadline_unix_seconds'),
      'future-stage':('epoch','probe_closure','controller_review','stage','batch_id','accounting')}
    F.need(all(getattr(a,k) is not None for k in required[a.mode]),'ALL_EXPLICIT_ACTUAL_METADATA_ARGUMENTS_REQUIRED')
    fn={'provider-template':template,'bind':bind,'probe-stage':probe_stage,'close-probe':close_probe,'run96':run96,
      'close96':close96,'controller-template':controller_template,'future-stage':future_stage}[a.mode]
    return fn(a)


if __name__=='__main__':main()
