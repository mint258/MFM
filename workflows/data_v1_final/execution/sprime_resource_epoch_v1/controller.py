"""Thin resource-epoch binding; inherit v4 scheduler, CG locks, accounting and states."""
import argparse,fcntl,os,pathlib,stat,sys,time
from . import contract as E
V=E.V;W=E.W;G=E.G;F=E.F;C=V.C


class Controller(W.Controller):
    # run/discover/registration core/sacct/account/persist_terminal_costs/owned_pending/
    # transition and its CG outer serialization remain the original objects.
    def __init__(self,args,review,epoch,identity,probe,recovery):
        manifest,plan,_,_=V.fixed_inputs()
        self.args=args;self.review=review;self.review_ref=V.pin(args.review);self.manifest=manifest;self.plan=plan
        self.epoch=epoch;self.probe=probe;self.root=args.state_root;self.entries=recovery.entries
        self.cache={};self.terminal_observations=set();self.recovery=recovery;self.repair=W.ClosurePaths(recovery)
        self.slots={r['batch_id']:r for r in plan['jobs']};self.slots['batch-00096']=recovery.slot
        self.launch=str(time.time_ns())+'_'+str(os.getpid())
        self.deadline=E.deadline(review['deadline_unix_seconds'],identity,time.time())
        self.seq=len(list((self.root/'events').glob('event_*.json')));self.cycle=0
        self.identity_ref=V.write(self.root/'launches'/(self.launch+'.json'),dict(V.process_identity(os.getpid()),
          schema='ACTUAL_FINITE_SPRIME_RESOURCE_EPOCH_CONTROLLER_LAUNCH_V1',review_reference=self.review_ref,
          source_references=[*V.sources(),*W.extra_sources(),*E.sources()],actual_primary=str(E.HERE/'controller.py'),
          complete_argv=[G.PY,'-B','-m','workflows.data_v1_final.execution.sprime_resource_epoch_v1.controller',*sys.argv[1:]],
          endpoint='202.38.247.57:22',node='sonmi',resource_epoch_reference=review['resource_epoch_reference'],
          publisher_identity_reference=epoch['publisher_identity_reference'],deadline_unix_seconds=self.deadline,
          continuation_repair_map_reference=recovery.reference,original_HOLD_reference=review['resume_from_state_reference'],
          resume=args.resume,root_reason=args.reason,single_cycle=args.single_cycle,scientific_dispatch_on_login=False))
        self.event('ACTUAL_NEW_RESOURCE_EPOCH_ADOPTED',resource_epoch_reference=review['resource_epoch_reference'],
          actual_new_epoch_probe_closure_reference=review['probe_closure_reference'],
          original_failed96_accounting_reference=recovery.failed_accounting_reference,
          original_zero_close_accounting_reference=recovery.value['original96_close_accounting_reference'],
          old_history_unchanged=True,new96_already_actually_closed=True,only_future97_through179_may_be_dispatched=True)

    def budget(self):
        V.Controller.budget(self)
        F.need(V.sources()==self.review['source_references'] and W.extra_sources()==self.review['continuation_source_references']
          and E.sources()==self.review['resource_epoch_source_references'],'EXACT_OLD_AND_NEW_METADATA_SOURCES_UNCHANGED')

    def expected_argv(self,bid,stage,request):
        argv=W.Controller.expected_argv(self,bid,stage,request)
        if bid in E.FUTURE or bid=='batch-00096' and stage in {'run','close'}:
            return E.replace_quota(argv,self.manifest['quota_reuse_review_reference']['path'],self.epoch['quota_reuse_review_reference']['path'])
        return argv # actual original1..95 and original96 prepare retain the old epoch.

    def registration(self,bid,stage,entry):
        if bid in E.FUTURE or bid=='batch-00096' and stage in {'run','close'}:
            req=V.load(entry['request_reference']['path'])
            F.need(self.review['resource_epoch_reference'] in req['source_references']
              and self.review['probe_closure_reference'] in req['source_references'],
              'NEW_EPOCH_AND_ACTUAL_CPU_PROBE_DECLARED_IN_FUTURE_REGISTRATION')
        return V.Controller.registration(self,bid,stage,entry)

    def _transition_after_resource_gate(self,bid,stage,stages):
        self.budget();F.need(bid in E.FUTURE,'ONLY_POST96_REVIEWED_INITIAL_STAGES_NOT_A_RETRY')
        # This method is called only inside the unchanged v3 CG guard holding its
        # original outer fd, inherited by both metadata helper and central helper.
        F.need(getattr(self,'outer_submission_fd',None) is not None,'ORIGINAL_CG_OUTER_LOCK_MUST_BE_HELD')
        name,phase,directory=self.stage_paths(bid,stage)
        F.need(not directory.exists(),'EXISTING_STAGE_DIRECTORY_NO_AUTOMATIC_REGENERATION')
        intent=self.root/'intents'/(bid+'_'+stage+'.json')
        F.need(not intent.exists(),'EXISTING_TRANSITION_INTENT_NO_RETRY')
        previous='4521486' if stage=='prepare' else stages[bid]['prepare' if stage=='run' else 'run']['job_id']
        account_ref=self.account(previous,bid+'_'+stage)
        generator=[G.PY,'-B','-m','workflows.data_v1_final.execution.sprime_resource_epoch_v1.metadata','future-stage',
          '--output',str(directory),'--accounting',account_ref['path'],'--root-approve-exact-stage','--root-reason',self.args.reason,
          '--epoch',self.review['resource_epoch_reference']['path'],'--probe-closure',self.review['probe_closure_reference']['path'],
          '--controller-review',str(self.args.review),'--stage',stage,'--batch-id',bid]
        if stage!='prepare':generator.extend(['--prepared',str(G.WAVE2/bid/'prepared_mapping_v1/prepared.json')])
        if stage=='close':
            reg=stages[bid]['run']['registration']
            generator.extend(['--request',reg['request_reference']['path'],'--submission',reg['submission_reference']['path']])
        self.command(generator,'generate_'+bid+'_'+stage)
        sp=V.pin(directory/'stage_spec.json')
        helper=[G.PY,'-B',str(V.HELPER),'--spec',sp['path'],'--node','compute-0-13','--name',name,'--phase',phase]
        V.write(intent,dict(schema='SPRIME_CONTROLLER_SUBMISSION_INTENT_NO_REISSUE_V1',batch_id=bid,stage=stage,
          stage_spec_reference=sp,helper_argv=helper,expected_name=name,expected_phase=phase,actual_job_id=None,
          launch_identity_reference=self.identity_ref,resource_epoch_reference=self.review['resource_epoch_reference'],reason=self.args.reason))
        self.event('SUBMIT_INTENT_DURABLE',batch_id=bid,stage=stage,intent_reference=V.pin(intent))
        self.command(helper,'central_submit_'+bid+'_'+stage,240)
        self.event('HELPER_RETURNED_RECONCILE_ACTUAL_REGISTRATION_NEXT_CYCLE',batch_id=bid,stage=stage)


def main():
    G.on_login();p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--review',type=pathlib.Path,required=True);p.add_argument('--state-root',type=pathlib.Path,required=True)
    p.add_argument('--root-run-reviewed-wave2',action='store_true');p.add_argument('--reason',required=True)
    p.add_argument('--observe-only',action='store_true');p.add_argument('--single-cycle',action='store_true');p.add_argument('--resume',action='store_true')
    p.add_argument('--poll-seconds',type=int,default=15);args=p.parse_args()
    F.need(E.HERE==G.REPO/'workflows/data_v1_final/execution/sprime_resource_epoch_v1'
      and pathlib.Path(sys.modules['__main__'].__file__).absolute()==E.HERE/'controller.py'
      and V.process_identity(os.getpid())['argv']==[G.PY,'-B','-m','workflows.data_v1_final.execution.sprime_resource_epoch_v1.controller',*sys.argv[1:]],
      'ACTUAL_RESOURCE_EPOCH_CONTROLLER_PRIMARY_FULL_ARGV')
    F.need(args.root_run_reviewed_wave2 and args.reason.strip() and 5<=args.poll_seconds<=30,'EXPLICIT_ROOT_FINITE_CONTROLLER_RUN')
    rr=V.pin(args.review);review,epoch,identity,probe,recovery=E.controller_inputs(rr)
    old=E.refread(recovery.hold['launch_identity_reference']);proc=pathlib.Path('/proc',str(old['pid']))
    if proc.exists():
        current=V.process_identity(old['pid'])
        F.need(current['boot_id']!=old['boot_id'] or current['start_ticks']!=old['start_ticks'],'ORIGINAL_EXACT_CONTROLLER_STILL_LIVE')
    root=E.own_path(args.state_root,base=V.BASE)
    if args.resume:
        latest=V.load(root/'latest.json')['state_reference'];previous=E.refread(latest)
        F.need(previous['manifest_reference']==V.MANIFEST and previous['plan_reference']==V.PLAN,'SAME_ORIGINAL179_ON_EPOCH_RESUME')
        if previous['status'].startswith('HOLD') or previous['review_reference']!=rr:
            F.need(review.get('previous_epoch_state_reference')==latest
              and review.get('supersedes_epoch_review_reference')==previous['review_reference']
              and previous['review_reference']!=rr,'HOLD_REQUIRES_NEW_EXPLICIT_ROOT_REVIEW_NOT_ELAPSED_TIME')
    else:
        F.need(not root.exists(),'NEW_EPOCH_STATE_ROOT_OLD_STATE_HISTORY_UNCHANGED');root.mkdir(parents=True,mode=0o700)
    for n in ('events','states','launches','commands','accounts','stages','intents'):(root/n).mkdir(exist_ok=args.resume)
    fd=os.open(V.BASE/'wave2_single_instance.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(fd);F.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and info.st_nlink==1,'ORIGINAL_OWN_SINGLE_INSTANCE_LOCK')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return Controller(args,review,epoch,identity,probe,recovery).run()
    finally:os.close(fd)


if __name__=='__main__':raise SystemExit(main())
