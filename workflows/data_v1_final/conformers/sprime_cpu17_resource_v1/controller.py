"""Thin fixed17 resource context; inherit original v4 discovery and v3 scheduler."""
import argparse,fcntl,os,pathlib,stat,sys,time
from . import contract as F,quota_edge as E,recovery as K,capacity_gate as CG,metadata as M
from workflows.data_v1_final.execution.sprime_wave2_controller_v4 import controller as W
V=W.V;G=V.G;C=V.C;PY=V.PY;ROOT=V.ROOT;REPO=V.REPO
load=V.load;pin=V.pin;write=V.write;read_small=V.read_small
validate_request=V.validate_request;validate_bound_request=V.validate_bound_request


class Paths(K.ClosurePaths):
    def primary(self,bid):return F.HERE/'close.py' if bid in F.FUTURE else super().primary(bid)
    def output(self,bid):return G.WAVE2/bid/'closed_cpu17_v1' if bid in F.FUTURE else super().output(bid)
    def report_path(self,bid):return self.output(bid)/'closed_batch.json' if bid in F.FUTURE else super().report_path(bid)


def inputs(reference):
    r=E.meta(reference);E.root(r,'ROOT_MAIN17_FINITE_REMAINING_CONTROLLER_V1','APPROVED_FINITE_METADATA_CONTROLLER')
    F.need(r['manifest_reference']==V.MANIFEST and r['plan_reference']==V.PLAN and r['source_references']==V.sources()
      and r['node17_source_references']==F.own_sources() and r['maximum_nonterminal_science']==2
      and r['maximum_nonterminal_aux']==1 and r['maximum_owned_data_run_pending']==4
      and r['stop_before_publisher_expiry_seconds']==300 and r['allowed_future_batch_ids']==list(F.FUTURE)
      and r['authorize_exact_metadata_stages_for_listed_future_batches'] is True
      and r['automatic_retry'] is False and r['publisher_auto_renew'] is False,'EXACT_ORIGINAL_SCHEDULER_LIMITS_AND_FROZEN_RESOURCE_WRAPPER')
    execution=E.execution(r['execution_authority_reference']);binding=E.binding(execution['node17_binding_reference'])
    provider,identity=E.provider(binding)
    F.need(r['publisher_identity_reference']==binding['publisher_identity_reference'],'SAME_LOCKED_FINITE_IDENTITY')
    from .test_binding import deadline
    deadline(r['deadline_unix_seconds'],identity,time.time())
    prior=E.meta(r['supersedes_review_reference']);W.prior_review(prior)
    recovery=K.Recovery(r['continuation_repair_map_reference'],r,prior)
    E.account(recovery.value['replacement96_close_accounting_reference'],recovery.parent['job_id'])
    br=r['future_bundle_reference'];b=E.meta(br)
    F.need(b['schema']=='MAIN17_ORIGINAL_REMAINING_METADATA_BUNDLE_V1' and b['batch_ids']==list(F.FUTURE)
      and b['execution_authority_reference']==r['execution_authority_reference']
      and b['actual96_closed_reference']==recovery.report_reference,'SAME_REAL_COMPLETE96_AND_REMAINING83_LINEAGE')
    M.closed96(b['actual96_closed_reference']);plan=E.meta(b['plan_reference']);wave=E.meta(b['replacement_wave_review_reference'])
    F.approve_wave(plan['draft'],E.meta(plan['draft']),b['replacement_wave_review_reference'],plan['config'])
    original=E.meta(V.PLAN)
    F.need(plan==K.derive_plan(original,V.PLAN,b['replacement_wave_review_reference'],wave,b['decision_reference'])
      and [s['batch_id'] for s in plan['jobs']]==list(F.FUTURE),'EXACT_RESOURCE_ONLY_DERIVED83_PLAN')
    old=E.meta(recovery.hold['launch_identity_reference']);proc=pathlib.Path('/proc',str(old['pid']))
    if proc.exists():
        current=V.process_identity(old['pid'])
        F.need(current['boot_id']!=old['boot_id'] or current['start_ticks']!=old['start_ticks'],'OLD_EXACT_CONTROLLER_STILL_LIVE')
    return r,b,plan,binding,identity,recovery


class Controller(W.Controller):
    # run/discover/sacct/account/persist_terminal_costs/owned_pending/snapshot,
    # C.next_stage/capacity/choose and central registration stay original objects.
    def __init__(self,args,review,bundle,future,binding,identity,recovery):
        manifest,original,_,_=V.fixed_inputs()
        self.args=args;self.review=review;self.review_ref=pin(args.review);self.manifest=manifest;self.plan=original
        self.bundle=bundle;self.future_plan=future;self.binding=binding;self.recovery=recovery;self.repair=Paths(recovery)
        self.root=args.state_root;self.entries=recovery.entries;self.cache={};self.terminal_observations=set()
        self.slots={r['batch_id']:r for r in original['jobs']};self.slots[K.BID]=recovery.slot
        self.slots.update({r['batch_id']:r for r in future['jobs']})
        self.launch=str(time.time_ns())+'_'+str(os.getpid());self.deadline=review['deadline_unix_seconds']
        self.seq=len(list((self.root/'events').glob('event_*.json')));self.cycle=0
        self.identity_ref=write(self.root/'launches'/(self.launch+'.json'),dict(V.process_identity(os.getpid()),
          schema='ACTUAL_MAIN17_FINITE_RESOURCE_CONTROLLER_LAUNCH_V1',review_reference=self.review_ref,
          source_references=[*V.sources(),*W.extra_sources(),*F.own_sources()],actual_primary=str(F.HERE/'controller.py'),
          complete_argv=[PY,'-B','-m',F.MODULE+'.controller',*sys.argv[1:]],endpoint='202.38.247.57:22',node='sonmi',
          publisher_identity_reference=binding['publisher_identity_reference'],deadline_unix_seconds=self.deadline,
          continuation_repair_map_reference=recovery.reference,original_HOLD_reference=review['resume_from_state_reference'],
          root_reason=args.reason,resume=args.resume,single_cycle=args.single_cycle,scientific_dispatch_on_login=False))
        self.event('ACTUAL17_RESOURCE_CONTEXT_ADOPTED',original_failed96_accounting_reference=recovery.failed_accounting_reference,
          original_zero_close_accounting_reference=recovery.value['original96_close_accounting_reference'],
          real_original16_compatibility_reference=E.execution(review['execution_authority_reference'])['compatibility_closure_reference'],
          actual96_closed_reference=recovery.report_reference,old_0_through95_recomputed=False,only97_through179_dispatch=True)

    def budget(self):
        V.Controller.budget(self)
        F.need(V.sources()==self.review['source_references'] and F.own_sources()==self.review['node17_source_references'],
          'FROZEN_OLD_AND_NEW_SOURCES_REQUIRED')
        E.current(self.binding)

    def report_plan(self,bid):
        if bid in F.FUTURE:return self.bundle['plan_reference']
        return self.recovery.plan_reference if bid==K.BID else V.PLAN

    def stage_paths(self,bid,stage):
        if bid not in F.FUTURE:return V.Controller.stage_paths(self,bid,stage)
        name=self.slots[bid]['job_name'] if stage=='run' else 'dv1_q_sprime17_b'+bid[6:]+'_'+stage+'_20261027_v1'
        phase='sprime17_b'+bid[6:]+'_'+stage+'_20261027_v1'
        return name,phase,self.root/'stages'/bid/(stage+'_v1')

    def expected_argv(self,bid,stage,request):
        if bid not in F.FUTURE and not(bid==K.BID and stage in {'run','close'}):return W.Controller.expected_argv(self,bid,stage,request)
        b=self.bundle if bid in F.FUTURE else self.recovery.bundle;config=self.manifest['config_reference'];proof=request['startup_proof_path']
        prepared=pin(G.WAVE2/bid/'prepared_cpu17_v1/prepared.json') if bid in F.FUTURE and stage!='prepare' else b['prepared_reference']
        if stage=='prepare':return [PY,'-B',str(F.HERE/'prepare_batch.py'),'--config',config['path'],'--plan',b['plan_reference']['path'],'--batch-id',bid,
          '--root-preflight',proof,'--quota-reuse-review',b['quota_reuse_review_reference']['path'],
          '--source-mapping-review',b['mapping_review_reference']['path'],'--output',str(G.WAVE2/bid/'prepared_cpu17_v1')]
        if stage=='run':return M.expected_run(config,prepared,b['quota_reuse_review_reference'],self.slots[bid],proof)
        argv=request['execution_argv'];F.need('--descriptor' in argv,'ACTUAL_CLOSE_DESCRIPTOR_REQUIRED')
        path=pathlib.Path(argv[argv.index('--descriptor')+1]);F.need(ROOT/'control' in path.parents,'OWN_CONTROL_CLOSE_DESCRIPTOR')
        d=load(path);F.need(d['plan']==b['plan_reference'] and d['prepared']==prepared,'EXACT17_CLOSED_PLAN_HEADER')
        return [PY,'-B',str(F.HERE/'close.py'),'close','--config',config['path'],'--root-preflight',proof,
          '--quota-reuse-review',b['quota_reuse_review_reference']['path'],'--descriptor',str(path),'--output',str(self.repair.output(bid))]

    def registration(self,bid,stage,entry):
        if bid in F.FUTURE or bid==K.BID and stage in {'run','close'}:
            req=load(entry['request_reference']['path'])
            F.need(self.review['execution_authority_reference'] in req['source_references']
              and self.binding['probe_closure_reference'] in req['source_references'],'ACTUAL17_SCIENCE_AND_PROBE_CHAIN_DECLARED')
            return self._fixed17_registration(bid,stage,entry)
        return V.Controller.registration(self,bid,stage,entry)

    def _fixed17_registration(self,bid,stage,entry):
        cache_key=(bid,stage);frames=[]
        for name in ('stage_spec_reference','request_reference','submission_reference','activation_reference','registry_reference'):
            path=pathlib.Path(entry[name]['path']);info=path.stat()
            C.need(not path.is_symlink() and stat.S_ISREG(info.st_mode) and info.st_uid==1278,'OWN_IMMUTABLE_REGISTRATION_METADATA')
            frames.append((str(path),info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_uid))
        if cache_key in self.cache:
            previous=self.cache[cache_key];C.need(previous['entry']==entry and previous['frames']==frames,'IMMUTABLE_REGISTRATION_METADATA_FRAME_CHANGED')
            return dict(previous['value'])
        req=load(entry['request_reference']['path']);sub=load(entry['submission_reference']['path'])
        C.need(pin(entry['request_reference']['path'])==entry['request_reference'] and pin(entry['submission_reference']['path'])==entry['submission_reference'],
            'REGISTERED_METADATA_CHANGED')
        C.need(sub['request']==req and sub['request_reference']==entry['request_reference'] and sub['sbatch_returncode']==0 and sub['uid']==1278,
            'ACTUAL_SUCCESSFUL_MAIN_SUBMISSION_REQUIRED')
        C.need(req['root_review']['stage_spec_reference']==entry['stage_spec_reference']
            and pin(entry['stage_spec_reference']['path'])==entry['stage_spec_reference'],'REGISTERED_STAGE_SPEC_ACTUAL_PIN_CHAIN_REQUIRED')
        C.need(req['execution_argv']==self.expected_argv(bid,stage,req) and req['scope_key']=='sprime_cpu17_resource_v1_'+stage
            and req['scope_parameters']==F.scope(stage,self.manifest['config_reference']) and req['kind']==('conformer' if stage=='run' else 'analysis')
            and req['node']=='compute-0-17' and req['cpus']==16 and req['pilot'] is False and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
            and req['wall_seconds']=={'prepare':14400,'run':28800,'close':7200}[stage],'EXACT_FROZEN_PRIMARY_OPTIONS_SCOPE_RESOURCES_REQUIRED')
        if stage=='run':C.need(req['job_name']==self.slots[bid]['job_name'],'EXACT_APPROVED_SCIENCE_SLOT_NAME')
        validate_request(req,read_small=read_small);validate_bound_request(req,read_small=read_small)
        activation=load(entry['activation_reference']['path']);registry=load(entry['registry_reference']['path'])
        C.need(pin(entry['activation_reference']['path'])==entry['activation_reference'] and pin(entry['registry_reference']['path'])==entry['registry_reference']
            and activation['registry_reference']==entry['registry_reference']
            and any(r['job_id']==sub['job_id'] and r['request_reference']==entry['request_reference'] and r['receipt_reference']==entry['submission_reference'] for r in registry['jobs'])
            and any(str(r['job_id'])==str(sub['job_id']) for r in activation['releases']),'ACTUAL_EXISTING_CENTRAL_ACTIVATION_CHAIN_REQUIRED')
        value={'job_id':str(sub['job_id']),'job_name':req['job_name'],'registration':entry,'terminal':False,'state':'UNOBSERVED','exit_code':None}
        self.cache[cache_key]={'entry':entry,'frames':frames,'value':value};return dict(value)

    def transition(self,bid,stage,stages):
        # The outer lock is distinct from activate's inner registration lock.
        # It covers the real capacity query and the entire unchanged stage
        # transition. No generation/account/submission intent precedes it.
        from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import query
        observed={}
        def read_node():
            argv=['scontrol','show','node','compute-0-17','--oneliner']
            began=time.time();raw=query(argv)
            observed.update(argv=argv,started_unix_seconds=began,finished_unix_seconds=time.time(),
                raw=raw,query_success_validated_by_frozen_shared_query=True)
            return raw
        def action(fd):
            self.outer_submission_fd=fd
            try:return self._transition_after_resource_gate(bid,stage,stages)
            finally:self.outer_submission_fd=None
        def admitted(decision):self.event('ACTUAL_CPU_CAPACITY_ADMITTED',batch_id=bid,stage=stage,observation=observed,capacity=decision)
        result=CG.guarded_transition(read_node,action,
            lambda:CG.serialization_lock(ROOT/'control'/CG.LOCK_NAME),on_capacity=admitted)
        if result['action']=='WAIT_EXISTING_JOBS_OR_CAPACITY':
            self.event('WAIT_EXISTING_JOBS_OR_CAPACITY',batch_id=bid,stage=stage,resource=result,observation=observed,
                transition_intents_created=0,new_jobs_submitted=0)
            self.snapshot('WAIT_EXISTING_JOBS_OR_CAPACITY',stages,dict(batch_id=bid,stage=stage,resource=result))
            return False
        return True

    def _transition_after_resource_gate(self,bid,stage,stages):
        self.budget();F.need(bid in F.FUTURE and getattr(self,'outer_submission_fd',None) is not None,'ONLY_FUTURE_WITH_ORIGINAL_OUTER_LOCK')
        name,phase,directory=self.stage_paths(bid,stage);F.need(not directory.exists(),'NO_STAGE_REGENERATION')
        intent=self.root/'intents'/(bid+'_'+stage+'.json');F.need(not intent.exists(),'NO_TRANSITION_REISSUE')
        previous='4521486' if stage=='prepare' else stages[bid]['prepare' if stage=='run' else 'run']['job_id']
        account_ref=self.account(previous,bid+'_'+stage)
        generator=[PY,'-B','-m',F.MODULE+'.metadata','stage','--output',str(directory),'--accounting',account_ref['path'],
          '--continuation-bundle',self.review['future_bundle_reference']['path'],'--controller-review',str(self.args.review),
          '--batch-id',bid,'--stage',stage,'--root-approve-exact-stage','--root-reason',self.args.reason]
        if stage!='prepare':generator.extend(['--prepared',str(G.WAVE2/bid/'prepared_cpu17_v1/prepared.json')])
        if stage=='close':
            reg=stages[bid]['run']['registration'];generator.extend(['--request',reg['request_reference']['path'],'--submission',reg['submission_reference']['path']])
        self.command(generator,'generate_'+bid+'_'+stage)
        sp=pin(directory/'stage_spec.json');helper=[PY,'-B',str(V.HELPER),'--spec',sp['path'],'--node',F.NODE,'--name',name,'--phase',phase]
        write(intent,dict(schema='SPRIME_CONTROLLER_SUBMISSION_INTENT_NO_REISSUE_V1',batch_id=bid,stage=stage,
          stage_spec_reference=sp,helper_argv=helper,expected_name=name,expected_phase=phase,actual_job_id=None,
          launch_identity_reference=self.identity_ref,reason=self.args.reason))
        self.event('SUBMIT_INTENT_DURABLE',batch_id=bid,stage=stage,intent_reference=pin(intent))
        self.command(helper,'central_submit_'+bid+'_'+stage,240)
        self.event('HELPER_RETURNED_RECONCILE_ACTUAL_REGISTRATION_NEXT_CYCLE',batch_id=bid,stage=stage)


def main():
    G.on_login();p=argparse.ArgumentParser(description=__doc__)
    for k in ('review','state-root'):p.add_argument('--'+k,type=pathlib.Path,required=True)
    p.add_argument('--root-run-reviewed-wave2',action='store_true');p.add_argument('--reason',required=True)
    p.add_argument('--single-cycle',action='store_true');p.add_argument('--observe-only',action='store_true');p.add_argument('--resume',action='store_true')
    p.add_argument('--poll-seconds',type=int,default=15);a=p.parse_args()
    F.need(F.HERE==G.REPO/'workflows/data_v1_final/conformers/sprime_cpu17_resource_v1'
      and pathlib.Path(sys.modules['__main__'].__file__).absolute()==F.HERE/'controller.py'
      and V.process_identity(os.getpid())['argv']==[PY,'-B','-m',F.MODULE+'.controller',*sys.argv[1:]],'ACTUAL_FIXED17_CONTROLLER_PRIMARY_ARGV')
    F.need(a.root_run_reviewed_wave2 and a.reason.strip() and 5<=a.poll_seconds<=30,'EXPLICIT_FINITE_ROOT_CONTROLLER_LAUNCH')
    rr=pin(a.review);r,b,plan,binding,identity,recovery=inputs(rr)
    root=a.state_root;F.need(root.is_absolute() and V.BASE in root.parents and '..' not in root.parts
      and not any(p.is_symlink() for p in (root,*root.parents)),'OWN_INDEPENDENT_OR_RESUMED17_CONTROLLER_STATE')
    if a.resume:
        latest=load(root/'latest.json')['state_reference'];previous=E.meta(latest)
        F.need(previous['manifest_reference']==V.MANIFEST and previous['plan_reference']==V.PLAN,'SAME_ORIGINAL179_HISTORY')
        if previous['status'].startswith('HOLD') or previous['review_reference']!=rr:
            F.need(r.get('previous_node17_state_reference')==latest and r.get('supersedes_node17_review_reference')==previous['review_reference']
              and rr!=previous['review_reference'],'NEW_INDEPENDENT_ROOT_REVIEW_REQUIRED_FOR_HOLD')
    else:F.need(not root.exists(),'FRESH_STATE_OLD_HISTORY_RETAINED');root.mkdir(parents=True,mode=0o700)
    for n in ('events','states','launches','commands','accounts','stages','intents'):(root/n).mkdir(exist_ok=a.resume)
    fd=os.open(V.BASE/'wave2_single_instance.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(fd);F.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and info.st_nlink==1,'ORIGINAL_GLOBAL_OWN_CONTROLLER_LOCK')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return Controller(a,r,b,plan,binding,identity,recovery).run()
    finally:os.close(fd)


if __name__=='__main__':raise SystemExit(main())