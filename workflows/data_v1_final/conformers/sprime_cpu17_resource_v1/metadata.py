"""Root-only fixed Main17 metadata; stat/closed metadata only, never DATA bodies."""
import argparse,copy,json,pathlib,re,time
from . import contract as C,quota_edge as E,recovery as K
from . import probe as P,compat16 as QA,test_binding as T
from workflows.data_v1_final.execution.sprime_wave2_controller_v3 import controller as V
from workflows.data_v1_final.execution.sprime_wave2_metadata_v1 import generate as G
from workflows.data_v1_final.execution.sprime_resource_epoch_v1 import metadata as OLD_E


class References(G.References):
    """Only empty SOURCE init bridges old positive-DATA collector; no reclassification."""
    def add(self,value,*,data=False):
        if data or G.is_data(value['path']):return super().add(value,data=True)
        reference=C.source_triple(value)
        if reference['bytes']>0:return super().add(reference,data=False)
        C.source_pinned(reference);path=reference['path']
        C.need(path not in self.data,'EMPTY_SOURCE_CANNOT_BE_DATA')
        C.need(path not in self.sources or self.sources[path]==reference,'CONFLICTING_EMPTY_SOURCE_PIN')
        self.sources[path]=reference

    def validate_small_sources(self):
        for r in self.sources.values():
            if r['bytes']==0:C.source_pinned(r)
        return super().validate_small_sources()

def approved(a):C.need(a.root_approve_exact_stage and a.root_reason.strip(),'EXPLICIT_ROOT_METADATA_APPROVAL_AND_REASON')

def fresh(path,base=G.ROOT/'control'):
    path=pathlib.Path(path);C.need(path.is_absolute() and base in path.parents and '..' not in path.parts
      and not any(p.is_symlink() for p in (path,*path.parents)) and not path.exists(),'FRESH_LITERAL_OWN_METADATA_OR_OUTPUT_DIRECTORY')
    return path


def out(a):
    p=fresh(a.output);p.mkdir(parents=True,mode=0o700);return p


def read(path,schema=None):return G.metadata(path,schema)


def actual(r):return E.meta(r)


def add(refs,values):
    for r in values:refs.add(r,data=G.is_data(r['path']))


def sources(refs):
    G.original_sources(refs)
    for r in C.own_sources():refs.add(r)
    for row in json.loads((C.HERE/'adaptation_manifest.json').read_text())['files']:refs.add(row['origin'])
    for package in ('sprime_wave2_controller_v4','sprime_resource_epoch_v1'):
        for p in sorted((G.REPO/'workflows/data_v1_final/execution'/package).glob('*.py')):refs.small(p)
    for name in ('__init__.py','contract.py','bridge.py','source_catalog.json'):refs.small(G.FORMAL.parent/'portable_secondary_uff_v1'/name)
    for name in ('__init__.py','admission.py','run.py','test_admission.py','README.md'):refs.small(G.FORMAL.parent/'formal_cpu_auto_close_index_v2'/name)
    for p in sorted((G.REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py')):refs.small(p)


def refs_base():
    refs=References({'source_references':[],'data_references':[]});sources(refs)
    config=G.meta_pin(G.CONFIG);v=C.config(config);refs.add(config)
    refs.add(V.MANIFEST);refs.add(actual(V.MANIFEST)['quota_reuse_review_reference'])
    for k in ('recipe_config','roles_authority','formal_source_receipt','sprime_manifest'):refs.add(v[k])
    refs.add(v['per_molecule'],data=True)
    return config,v,refs


def spec(a,directory,refs,key,params,argv,wall,cap,kind,parents,mode='BOUNDED_METADATA_PREPARATION',profile=None):
    approved(a);parents=[*parents,C.sources()['cost_authority']]
    if profile is not None:parents.append(profile)
    parents=list({r['path']:C.triple(r) for r in parents}.values())
    C.need(all(not G.is_data(r['path']) for r in parents),'PARENT_EVIDENCE_IS_SMALL_METADATA_ONLY')
    add(refs,parents)
    value={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root',
      'resource_authority_reference':C.sources()['resource_authority'],'kind':kind,'scope_key':key,'scope_parameters':params,
      'pilot':False,'wall_seconds':wall,'estimated_peak_output_bytes':cap,'stage_output_cap_bytes':cap,
      'execution_argv':argv,'scope_mode':mode,'parent_evidence_references':parents,'root_review_reason':a.root_reason,
      'scientific_quality_thresholds_unchanged':True,'no_scientific_data_read_or_hashed_on_login':True,
      'publisher_started_or_renewed_by_helper':False,'automatic_retry':False,'whole182_reserve_unchanged':True,
      'bounded_batch_limits_reviewed':mode=='BOUNDED_PERFORMANCE_BATCH'}
    if profile is not None:value.update(profile_reviewed=True,approved_profile_reference=profile)
    rr=G.write_new(directory/'scope_review.json',value);refs.add(rr);refs.validate_small_sources()
    s={k:value[k] for k in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv')}
    s.update(schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',
      source_references=list(refs.sources.values()),data_references=list(refs.data.values()),scope={'mode':mode,'review':rr,'parent_profile':profile})
    result=G.write_new(directory/'stage_spec.json',s)
    print(json.dumps({'stage_spec':result,'node_required':C.NODE,'jobs_submitted':0,'DATA_bodies_read_or_hashed':0,'publisher_started':False}),flush=True)
    return result


def source_stage(a):
    approved(a);config,v,refs=refs_base();directory=out(a);output=fresh(a.compute_output,C.BASE)
    plan=G.write_new(directory/'source3_plan.json',{'schema':'ROOT_MAIN17_SOURCE3_PLAN_V1','mode':'source3','source_references':C.own_sources()})
    refs.add(plan);argv=[G.PY,'-B','-m',C.MODULE+'.test_binding','--plan',plan['path'],'--root-preflight',G.PROOF_PLACEHOLDER,'--output',str(output)]
    spec(a,directory,refs,T.KEY,T.PARAMS,argv,900,C.PROBE_CAP,'analysis',[plan])


def probe_stage(a):
    approved(a);rr,request=read(a.root_request,'ROOT_REQUEST_MAIN17_ZERO_SCI_PROBE_V1')
    C.need(request['requested_by']=='root' and request['status']=='REQUESTED_FOR_REVIEW' and request['node']==C.NODE,'EXPLICIT_NODE17_PROBE_REQUEST')
    facts=request['provider_facts'];E.provider(facts)
    config,v,refs=refs_base();receipt=actual(v['formal_source_receipt']);row=next(r for r in receipt['outputs'] if r['name']=='formal_population')
    canonical=C.triple(row['reference']);refs.add(canonical,data=True);add(refs,[rr,*E.Q.references(facts['provider_review_reference']),
      facts['publisher_identity_reference'],facts['publisher_actual_launch_reference']])
    directory=out(a);output=fresh(a.compute_output,C.BASE)
    plan=G.write_new(directory/'probe_plan.json',{'schema':'ROOT_MAIN17_ZERO_SCI_PLAN_V1','mode':'probe','provider_facts':facts,
      'canonical_reference':canonical,'formal_source_receipt':v['formal_source_receipt'],'source_references':C.own_sources()})
    refs.add(plan);argv=[G.PY,'-B','-m',C.MODULE+'.probe','--plan',plan['path'],'--root-preflight',G.PROOF_PLACEHOLDER,'--output',str(output)]
    spec(a,directory,refs,P.KEY,P.PARAMS,argv,900,C.PROBE_CAP,'analysis',[rr,plan,v['formal_source_receipt']])


def close_probe(a):
    approved(a);rr,p=read(a.receipt,'ACTUAL_MAIN17_ZERO_SCI_STORAGE_ENV_PROBE_V1');proof=actual(p['startup_proof_reference'])
    E.validate_probe(p,proof);ar=G.meta_pin(a.accounting);E.account(ar,p['job_id'])
    directory=out(a);r=G.write_new(directory/'probe_closure.json',{'schema':'ROOT_ACTUAL_MAIN17_ZERO_SCI_PROBE_CLOSURE_V1',
      'status':'ACTUAL_C0_CLOSED_NOT_COMPATIBILITY_PASS','receipt_reference':rr,'accounting_reference':ar})
    E.probe_closure(r);print(json.dumps({'actual_probe_closure':r,'compatibility_claimed':False}),flush=True)


def binding_template(a):
    approved(a);cr=G.meta_pin(a.probe_closure);c,p,proof=E.probe_closure(cr);tr,t=read(a.source_check)
    ar=G.meta_pin(a.accounting);E.account(ar,t['job_id'])
    C.need(t['status']=='PASS' and t['tests_run']==3 and t['failures']==t['errors']==0
      and t['source_references']==C.own_sources(),'ACTUAL_SAME_SOURCE3_CPU_PASS')
    value={'schema':'ROOT_MAIN17_ACTUAL_STORAGE_EDGE_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW','reviewer':None,
      'endpoint':'202.38.247.57:22','uid':1278,'node':C.NODE,'probe_closure_reference':cr,
      'source_check_reference':tr,'source_check_accounting_reference':ar,'compute_mount':p['storage']['mount'],
      'canonical_reference':p['canonical_reference'],'canonical_expected_frame':p['canonical_stat'],'environment':p['environment'],
      'whole_wave_output_reserve_bytes':C.WAVE_RESERVE,'provider_reserve_bytes':E.CAP,'admin_reserve_bytes':C.ADMIN,
      'quota_reserve_bytes':200000000000,'scientific_authority_is_separate':True,'automatic_renewal':False}
    for k in ('provider_review_reference','publisher_identity_reference','publisher_actual_launch_reference'):value[k]=p['provider_facts'][k]
    directory=out(a);r=G.write_new(directory/'node17_binding.template.json',value);print(json.dumps({'template':r,'approved':False}),flush=True)


def quota(refs,directory,br,execution=None):
    b=E.binding(br);v={'schema':'ROOT_MAIN17_SPRIME_QUOTA_REUSE_V1','status':'APPROVED_RESOURCE_FACTS_ONLY','reviewer':'root',
      'endpoint':'202.38.247.57:22','uid':1278,'node':C.NODE,'compute_node':C.NODE,'provider_source_reference':C.sources()['quota_provider'],
      'node17_binding_reference':br,'execution_authority_reference':execution,'provider_review_reference':b['provider_review_reference'],
      'publisher_identity_reference':b['publisher_identity_reference'],'whole_wave_output_reserve_bytes':C.WAVE_RESERVE,
      'scientific_authority_is_separate':True,'N1_population_authority_is_not_Sprime_authority':True,'no_auto_renew':True}
    r=G.write_new(directory/'quota_reuse_review.json',v);add(refs,[r,*E.references(br)])
    if execution is not None:add(refs,E.execution_references(execution))
    return r


def qa_stage(a):
    approved(a);br=G.meta_pin(a.binding);E.binding(br);pr,prep=read(a.controls_preparation);E.PC.prep_metadata(prep)
    config,v,refs=refs_base();directory=out(a);qr=quota(refs,directory,br)
    refs.add(pr);refs.add(prep['tasks_reference'],data=True);refs.add(prep['original_complete_packages_reference'],data=True)
    for k in ('original_audit_reference','partial_audit_monitor_closure_reference','root_control_authorization_reference','qa_slice_marker_reference','selection_report_reference'):refs.add(prep[k])
    refs.small(G.FORMAL.parent/'portable_secondary_uff_v1/prepare_existing_controls.py')
    catalog=G.meta_pin(G.FORMAL.parent/'portable_secondary_uff_v1/source_catalog.json');catalog_value=actual(catalog)
    expected={r['basename']:r['origin_reference'] for r in catalog_value['sources']};qa={k:expected[k+'.py'] for k in ('run_pilot','statistics_tools')}
    add(refs,[catalog,*qa.values()]);qa_authority=G.meta_pin(a.root_review);auth=actual(qa_authority)
    E.root(auth,'ROOT_MAIN17_ORIGINAL_CONTROL16_QA_AUTHORIZATION_V1','APPROVED_EXACT_ORIGINAL16_COMPATIBILITY_ONLY')
    C.need(auth['controls_preparation_reference']==pr and auth['node17_binding_reference']==br
      and auth['allowed_original_control_ids']==prep['molecule_ids'] and auth['formal_generation_authorized'] is False,
      'ROOT_NEW_MAIN17_QA_ONLY_AUTHORITY_NOT_SECONDARY_FORMAL_SCOPE')
    prepproof=actual(prep['root_preflight_reference']);preprequest=actual(prepproof['request_reference'])
    C.need(prepproof['request']==preprequest and str(prepproof['job_id'])==prep['main_preparation_runtime']['job_id']
      and preprequest['node']==prep['main_preparation_runtime']['node'],'ACTUAL_OLD_CONTROL16_PRODUCER_REQUEST')
    E.account(auth['controls_preparation_accounting_reference'],prepproof['job_id'],node=preprequest['node'])
    add(refs,[prep['root_preflight_reference'],prepproof['request_reference'],auth['controls_preparation_accounting_reference'],
      actual(auth['controls_preparation_accounting_reference'])['raw_sacct_reference']])
    refs.add(qa_authority);output=fresh(a.compute_output,C.BASE)
    plan=G.write_new(directory/'compat16_plan.json',{'schema':'ROOT_MAIN17_ORIGINAL16_PLAN_V1','mode':'compat16','config_reference':config,
      'controls_preparation_reference':pr,'node17_binding_reference':br,'quota_reuse_review_reference':qr,'qa_sources':qa,
      'qa_authority_reference':qa_authority,'transitive_input_authority':'EXACT_ORIGINAL16_TASK_POINTERS_AND_ACTUAL334_BASELINES',
      'whole_LMDB_SHA':'WHOLE_LMDB_SHA_NOT_ORIGINALLY_AVAILABLE_NOT_CLAIMED','source_references':C.own_sources()})
    refs.add(plan);argv=[G.PY,'-B','-m',C.MODULE+'.compat16','--plan',plan['path'],'--root-preflight',G.PROOF_PLACEHOLDER,'--output',str(output)]
    spec(a,directory,refs,QA.KEY,QA.PARAMS,argv,C.QA_WALL,C.QA_CAP,'conformer',[pr,br,plan,qa_authority,prep['root_preflight_reference']],mode='BOUNDED_PERFORMANCE_BATCH')


def close_qa(a):
    approved(a);rr,p=read(a.receipt,'MAIN17_ORIGINAL_UFF_CONTROL16_RECEIPT_V1');ar=G.meta_pin(a.accounting);E.account(ar,p['job_id'])
    directory=out(a);r=G.write_new(directory/'compat16_closure.json',{'schema':'ROOT_MAIN17_CONTROL16_ACTUAL_CLOSURE_V1',
      'status':'ACTUAL_C0_CONTROL16_EXACT_MATCH','receipt_reference':rr,'accounting_reference':ar})
    E.compatibility(r);print(json.dumps({'actual_compatibility_closure':r,'formal_generation_authorized':False}),flush=True)


def lineage(a,refs):
    dr,d=read(a.decision,'ROOT_MAIN17_ORIGINAL96_UNSTARTED_RESOURCE_DECISION_V1')
    E.root(d,'ROOT_MAIN17_ORIGINAL96_UNSTARTED_RESOURCE_DECISION_V1','APPROVED_ORIGINAL_UNSTARTED500_RESOURCE_MOVE_ONLY')
    C.need(d['automatic_retry'] is False and d['once_keys_removed_or_changed'] is False
      and d['original_scientific_recipe_taskkeys_seeds_unchanged'] is True,'NO_NEW_LOGICAL_ATTEMPT_OR_SCIENCE_DELTA')
    closed=actual(d['original_closed_reference']);hold=actual(d['original_HOLD_reference']);pr=closed['plan'];hr=closed['prepared']
    C.need(pr==V.PLAN and hold['stages'][K.BID]['close']['report_reference']==d['original_closed_reference']
      and hold['stages'][K.BID]['run']['job_id']==K.FAILED_RUN,'SAME_ACTUAL_FAILED96_HOLD')
    plan=actual(pr);header=actual(hr);K.zero_consumption(closed,header,pr)
    spec_ref=hold['stages'][K.BID]['run']['actual_registered_references']['stage_spec_reference'];original_spec=actual(spec_ref)
    for r in original_spec['source_references']:refs.add(r,data=G.is_data(r['path']))
    for r in original_spec.get('data_references',[]):refs.add(r,data=True)
    for ref,ids,c0 in ((closed['accounting'],[K.FAILED_RUN],[]),(d['original_close_accounting_reference'],[K.OLD_CLOSE],[K.OLD_CLOSE]),
      (d['original_prepare_accounting_reference'],[K.PREPARE],[K.PREPARE])):
        ar,av,rows=G.account(pathlib.Path(ref['path']),ids,c0=c0);C.need(ar==ref,'EXACT_OLD_ACCOUNTING');G.add_account(refs,ar,av)
    add(refs,[dr,d['original_closed_reference'],d['original_HOLD_reference'],pr,hr,spec_ref])
    refs.add(header['tasks'],data=True)
    return dr,d,pr,plan,hr,header


def closed96(reference):
    v=actual(reference);req=actual(v['request']);sub=actual(v['submission']);E.account(v['accounting'],v['actual_parent_job_id'])
    K.complete(v,K.BID,v['actual_parent_job_id'],v['plan'],v['prepared'])
    C.need(req['node']==C.NODE and req['scope_key']=='sprime_cpu17_resource_v1_run' and sub['request']==req
      and sub['request_reference']==v['request'] and str(sub['job_id'])==v['actual_parent_job_id'],'ACTUAL_NODE17_96_COMPLETE_BEFORE97')
    return v


def wave_template(a):
    approved(a);config,v,refs=refs_base();dr,d,pr,plan,hr,header=lineage(a,refs);er=G.meta_pin(a.execution_authority);execution=E.execution(er)
    ids=[K.BID] if a.batch_id==K.BID else list(C.FUTURE)
    C.need(a.batch_id in {K.BID,'remaining97_179'},'EXACT_ONE96_OR_REMAINING83_WAVE')
    prior96=None
    if ids!=[K.BID]:prior96=G.meta_pin(a.closed96);closed96(prior96)
    jobs=[]
    for old in plan['jobs']:
        if old['batch_id'] not in ids:continue
        jobs.append(dict(old,node=C.NODE,job_name='dv1_q_sprime17_b'+old['batch_id'][6:]+'_20261027_v1',
          output_root=str(G.WAVE2/old['batch_id']/'generation_cpu17_v1')))
    value={'schema':C.SCHEMAS['wave_review'],'status':'PENDING_INDEPENDENT_ROOT_REVIEW','reviewer':None,'draft_reference':plan['draft'],
      'config_reference':config,'jobs':jobs,'maximum_concurrent_jobs':1 if ids==[K.BID] else 2,
      'requested_allocation_core_seconds_ceiling':len(jobs)*16*28800,'approved_over_500_core_hours':True,
      'full_forecast_status':C.FORECAST,'estimated_full_core_hours':None,'ceiling_is_not_full_forecast_or_actual_cost_guarantee':True,
      'scientific_quality_thresholds_unchanged':True,'resource_authority':C.sources()['resource_authority'],'cost_authority':C.sources()['cost_authority'],
      'execution_authority_reference':er,'resource_decision_reference':dr,'actual96_closed_reference':prior96,'automatic_retry':False,
      'old_tasks_seeds_once_unchanged':True,'new_CPU_freeze_claimed':False}
    directory=out(a);r=G.write_new(directory/'wave_review.template.json',value);print(json.dumps({'template':r,'approved':False}),flush=True)


def derivation(a,refs,directory,*,future=False):
    dr,d,pr,plan,hr,header=lineage(a,refs);wr,wave=read(a.wave_review,C.SCHEMAS['wave_review'])
    C.approve_wave(plan['draft'],actual(plan['draft']),wr,header['config']);er=wave['execution_authority_reference'];E.execution(er)
    C.need(wave['resource_decision_reference']==dr and [s['batch_id'] for s in wave['jobs']]==(list(C.FUTURE) if future else [K.BID]),'EXACT_ROOT_REMAINING_WAVE')
    if future:closed96(wave['actual96_closed_reference']);refs.add(wave['actual96_closed_reference'])
    derived=K.derive_plan(plan,pr,wr,wave,dr);npr=G.write_new(directory/'derived_plan.json',derived);nhr=None
    if not future:nhr=G.write_new(directory/'derived_prepared.json',K.derive_prepared(header,hr,npr,dr))
    qr=quota(refs,directory,E.execution(er)['node17_binding_reference'],er)
    binding=E.binding(E.execution(er)['node17_binding_reference']);mapping={'schema':'ROOT_MAIN17_CANONICAL_SOURCE_MAPPING_V1',
      'status':'APPROVED_ACTUAL_CANONICAL_MAPPING','reviewer':'root','endpoint':'202.38.247.57:22','uid':1278,'node':C.NODE,
      'node17_binding_reference':E.execution(er)['node17_binding_reference'],'formal_source_receipt':C.config(header['config'])['formal_source_receipt']}
    mr=G.write_new(directory/'canonical_mapping_review.json',mapping)
    bundle={'schema':'MAIN17_ORIGINAL_REMAINING_METADATA_BUNDLE_V1','origin_plan_reference':pr,'origin_prepared_reference':hr,
      'decision_reference':dr,'plan_reference':npr,'prepared_reference':nhr,'replacement_wave_review_reference':wr,
      'quota_reuse_review_reference':qr,'mapping_review_reference':mr,'execution_authority_reference':er,
      'old_tasks_reference_unchanged':header['tasks'],'actual96_closed_reference':wave.get('actual96_closed_reference'),
      'slot':None if future else derived['jobs'][0],'batch_ids':list(C.FUTURE) if future else [K.BID],'new_CPU_freeze_or_prepare_claimed':False,'new_task_keys_or_seeds':False}
    br=G.write_new(directory/'continuation_bundle.json',bundle);add(refs,[npr,wr,br,mr,er])
    if nhr is not None:refs.add(nhr)
    return br,bundle,derived,header


def science_refs(a,refs,bundle):
    config=C.config(G.meta_pin(G.CONFIG));add(refs,[bundle['plan_reference'],bundle['replacement_wave_review_reference'],bundle['decision_reference'],
      bundle['quota_reuse_review_reference'],bundle['mapping_review_reference'],bundle['execution_authority_reference'],
      *E.execution_references(bundle['execution_authority_reference'])])
    add(refs,E.references(E.execution(bundle['execution_authority_reference'])['node17_binding_reference']))
    for k in ('recipe_config','roles_authority','formal_source_receipt','sprime_manifest'):refs.add(config[k])
    refs.add(config['per_molecule'],data=True)
    plan=actual(bundle['plan_reference']);refs.add(plan['draft'])
    for k in ('pilot_imports','original_deficits','unsupported'):refs.add(plan[k],data=True)
    original=actual(config['formal_source_receipt']);refs.add(next(r['reference'] for r in original['outputs'] if r['name']=='formal_population'),data=True)
    for r in actual(config['sprime_manifest'])['references']:
        if r['kind']=='conformers':refs.add(C.triple(r),data=True)


def expected_run(config,prepared,quota_ref,slot,proof):
    return [G.PY,'-B',str(C.HERE/'run_batch.py'),'--config',config['path'],'--prepared',prepared['path'],
      '--root-preflight',proof,'--quota-reuse-review',quota_ref['path'],'--output',slot['output_root']]


def single96(a):
    approved(a);config,v,refs=refs_base();directory=out(a)
    br,bundle,plan,header=derivation(a,refs,directory);science_refs(a,refs,bundle)
    pilot=refs.small(G.ROOT/'control/sprime_v3_censored_pilot_root_review_v1.json');slot=plan['jobs'][0]
    argv=expected_run(config,bundle['prepared_reference'],bundle['quota_reuse_review_reference'],slot,G.PROOF_PLACEHOLDER)
    spec(a,directory,refs,'sprime_cpu17_resource_v1_run',C.scope('run',config),argv,28800,C.CAP,'conformer',
      [br,bundle['decision_reference'],bundle['execution_authority_reference']],mode='FULL_SOURCE_AFTER_PROFILE',profile=pilot)


def future_plan(a):
    approved(a);config,v,refs=refs_base();directory=out(a);br,bundle,plan,header=derivation(a,refs,directory,future=True)
    print(json.dumps({'future_bundle':br,'runnable_stages':0,'actual96_required':bundle['actual96_closed_reference']}),flush=True)


def stage(a):
    approved(a);config,v,refs=refs_base();br,bundle=read(a.continuation_bundle,'MAIN17_ORIGINAL_REMAINING_METADATA_BUNDLE_V1')
    science_refs(a,refs,bundle);refs.add(br);plan=actual(bundle['plan_reference'])
    C.need(a.batch_id in bundle['batch_ids'] and a.stage in {'prepare','run','close'},'ONLY_REVIEWED_REMAINING_BATCH_STAGE')
    if a.batch_id==K.BID:C.need(a.stage=='close','96_HAS_NO_NEW_PREPARE_OR_AUTOMATIC_RUN')
    else:
        closed96(bundle['actual96_closed_reference']);ctr=G.meta_pin(a.controller_review);review=actual(ctr)
        E.root(review,'ROOT_MAIN17_FINITE_REMAINING_CONTROLLER_V1','APPROVED_FINITE_METADATA_CONTROLLER')
        C.need(review['future_bundle_reference']==br and review['authorize_exact_metadata_stages_for_listed_future_batches'] is True
          and a.batch_id in review['allowed_future_batch_ids'],'EXACT_ROOT_CONTROLLER_METADATA_DELEGATION')
        identity=E.provider(E.binding(E.execution(bundle['execution_authority_reference'])['node17_binding_reference']))[1]
        T.deadline(review['deadline_unix_seconds'],identity,time.time());refs.add(ctr)
    slot=next(s for s in plan['jobs'] if s['batch_id']==a.batch_id);directory=out(a)
    parents=[br,bundle['execution_authority_reference']]
    if a.batch_id!=K.BID:parents.append(ctr)
    if a.stage=='prepare':
        ar,av,rows=G.account(a.accounting,['4521486'],c0=['4521486']);G.add_account(refs,ar,av);parents.append(ar)
        batch=next(b for b in plan['batches'] if b['batch_id']==a.batch_id);refs.add(batch['tasks'],data=True)
        argv=[G.PY,'-B',str(C.HERE/'prepare_batch.py'),'--config',config['path'],'--plan',bundle['plan_reference']['path'],'--batch-id',a.batch_id,
          '--root-preflight',G.PROOF_PLACEHOLDER,'--quota-reuse-review',bundle['quota_reuse_review_reference']['path'],
          '--source-mapping-review',bundle['mapping_review_reference']['path'],'--output',str(G.WAVE2/a.batch_id/'prepared_cpu17_v1')]
    else:
        hr=bundle['prepared_reference'] if a.batch_id==K.BID else G.meta_pin(a.prepared);header=actual(hr)
        C.need(header['plan']==bundle['plan_reference'] and header['config']==config and header['batch']['batch_id']==a.batch_id
          and header['kernel_sha256']==C.KERNEL_SHA,'EXACT_ACTUAL_TASK_HEADER_LINEAGE')
        refs.add(hr);refs.add(header['tasks'],data=True)
        for r in header['old_sprime_sources']:refs.add(r['reference'],data=True)
        refs.add(header['formal_source'],data=True)
        if a.stage=='run':
            ar,av,rows=G.account(a.accounting,[header['runtime']['job_id']],c0=[header['runtime']['job_id']]);G.add_account(refs,ar,av);parents.append(ar)
            E.account(ar,header['runtime']['job_id'])
            argv=expected_run(config,hr,bundle['quota_reuse_review_reference'],slot,G.PROOF_PLACEHOLDER)
        else:
            rq,request=read(a.request);sr,sub=read(a.submission,'CPU_AUTO_MEMORY_SUBMISSION_V1')
            C.need(sub['request']==request and sub['request_reference']==rq and sub['uid']==1278 and sub['sbatch_returncode']==0
              and request['execution_argv']==expected_run(config,hr,bundle['quota_reuse_review_reference'],slot,request['startup_proof_path'])
              and request['node']==C.NODE and request['scope_key']=='sprime_cpu17_resource_v1_run','ACTUAL_REGISTERED_NODE17_RUN_ALL_OPTIONS')
            ar,av,rows=G.account(a.accounting,[str(sub['job_id'])]);G.add_account(refs,ar,av);E.account(ar,sub['job_id'],c0=False)
            descriptor=G.write_new(directory/'descriptor.json',{'plan':bundle['plan_reference'],'prepared':hr,'request':rq,'submission':sr,'accounting':ar})
            add(refs,[rq,sr,descriptor]);parents.extend([rq,sr,ar,descriptor])
            argv=[G.PY,'-B',str(C.HERE/'close.py'),'close','--config',config['path'],'--root-preflight',G.PROOF_PLACEHOLDER,
              '--quota-reuse-review',bundle['quota_reuse_review_reference']['path'],'--descriptor',descriptor['path'],
              '--output',str(G.WAVE2/a.batch_id/'closed_cpu17_v1')]
    pilot=refs.small(G.ROOT/'control/sprime_v3_censored_pilot_root_review_v1.json') if a.stage=='run' else None
    spec(a,directory,refs,'sprime_cpu17_resource_v1_'+a.stage,C.scope(a.stage,config),argv,
      {'prepare':14400,'run':28800,'close':7200}[a.stage],C.CAP,'conformer' if a.stage=='run' else 'analysis',parents,
      mode='FULL_SOURCE_AFTER_PROFILE' if a.stage=='run' else 'BOUNDED_METADATA_PREPARATION',profile=pilot)


def controller_template(a):
    approved(a);br,b=read(a.continuation_bundle,'MAIN17_ORIGINAL_REMAINING_METADATA_BUNDLE_V1')
    C.need(b['batch_ids']==list(C.FUTURE),'ONLY_ACTUAL_POST96_REMAINING83_BUNDLE');closed96(b['actual96_closed_reference'])
    er=b['execution_authority_reference'];execution=E.execution(er);binding=E.binding(execution['node17_binding_reference'])
    provider,identity=E.provider(binding);T.deadline(a.deadline_unix_seconds,identity,time.time())
    mr,m=read(a.recovery_map,'ROOT_MAIN17_SPRIME96_ACTUAL_CONTINUATION_ADOPTION_V1')
    prior_ref,prior=read(a.prior_controller_review,'ROOT_FINITE_SPRIME_WAVE2_CONTROLLER_REVIEW_V3')
    from workflows.data_v1_final.execution.sprime_wave2_controller_v4.controller import prior_review
    prior_review(prior)
    value={'schema':'ROOT_MAIN17_FINITE_REMAINING_CONTROLLER_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW','reviewer':None,
      'endpoint':'202.38.247.57:22','uid':1278,'node':C.NODE,'manifest_reference':V.MANIFEST,'plan_reference':V.PLAN,
      'source_references':V.sources(),'node17_source_references':C.own_sources(),'adoption_reference':prior['adoption_reference'],
      'supersedes_review_reference':prior_ref,'resume_from_state_reference':m['original_HOLD_reference'],
      'continuation_repair_map_reference':mr,'future_bundle_reference':br,'execution_authority_reference':er,
      'publisher_identity_reference':binding['publisher_identity_reference'],'deadline_unix_seconds':a.deadline_unix_seconds,
      'maximum_nonterminal_science':2,'maximum_nonterminal_aux':1,'maximum_owned_data_run_pending':4,
      'stop_before_publisher_expiry_seconds':300,'allowed_future_batch_ids':list(C.FUTURE),
      'authorize_exact_metadata_stages_for_listed_future_batches':True,'automatic_retry':False,'publisher_auto_renew':False,
      'old_history_and_all_failed_cost_retained':True,'new_science_0_through95_authorized':False,'root_reason':a.root_reason}
    recovery=K.Recovery(mr,value,prior)
    C.need(recovery.report_reference==b['actual96_closed_reference'],'EXACT_ACTUAL_NEW96_CONTROLLER_ADOPTION')
    E.account(m['replacement96_close_accounting_reference'],recovery.parent['job_id'])
    directory=out(a);r=G.write_new(directory/'controller_review.template.json',value)
    print(json.dumps({'template':r,'approved':False,'controller_started':False,'science_submitted':0}),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('provider-template','source3-stage','probe-stage','close-probe','binding-template','qa-stage','close-qa','wave-template','run96','future-plan','stage','controller-template'))
    p.add_argument('--output',type=pathlib.Path,required=True)
    for k in ('root-request','publisher-output','compute-output','receipt','accounting','probe-closure','source-check','binding',
      'controls-preparation','root-review','execution-authority','decision','wave-review','closed96','continuation-bundle',
      'controller-review','prepared','request','submission','recovery-map','prior-controller-review'):p.add_argument('--'+k,type=pathlib.Path)
    p.add_argument('--deadline-unix-seconds',type=float);p.add_argument('--batch-id');p.add_argument('--stage',choices=('prepare','run','close'))
    p.add_argument('--root-approve-exact-stage',action='store_true');p.add_argument('--root-reason',default='');a=p.parse_args()
    G.on_login();C.need(C.HERE==G.REPO/'workflows/data_v1_final/conformers/sprime_cpu17_resource_v1','ACTUAL_INTEGRATED_MAIN17_METADATA_SOURCE')
    required={'provider-template':('root_request','publisher_output'),'source3-stage':('compute_output',),'probe-stage':('root_request','compute_output'),
      'close-probe':('receipt','accounting'),'binding-template':('probe_closure','source_check','accounting'),
      'qa-stage':('binding','controls_preparation','root_review','compute_output'),'close-qa':('receipt','accounting'),
      'wave-template':('decision','execution_authority','batch_id'),'run96':('decision','wave_review'),
      'future-plan':('decision','wave_review'),'controller-template':('continuation_bundle','recovery_map','prior_controller_review','deadline_unix_seconds'),'stage':('continuation_bundle','batch_id','stage','accounting')}
    C.need(all(getattr(a,k) is not None for k in required[a.mode]),'EXPLICIT_ACTUAL_METADATA_ARGUMENTS_REQUIRED')
    fn={'provider-template':OLD_E.template,'source3-stage':source_stage,'probe-stage':probe_stage,'close-probe':close_probe,
      'binding-template':binding_template,'qa-stage':qa_stage,'close-qa':close_qa,'wave-template':wave_template,'run96':single96,
      'future-plan':future_plan,'stage':stage,'controller-template':controller_template}[a.mode]
    return fn(a)


if __name__=='__main__':main()