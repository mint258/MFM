"""Root explicit actual95/96 adoption; inherit frozen v3 scheduling and science."""
import argparse,fcntl,json,os,pathlib,stat,sys,time
from .recovery import Recovery,ClosurePaths,exact
from workflows.data_v1_final.execution.sprime_wave2_controller_v3 import controller as V
from workflows.data_v1_final.execution.sprime_wave2_controller_v3 import capacity_gate as CG
from workflows.data_v1_final.execution.sprime_wave2_recovery96_v1 import metadata as M

HERE=pathlib.Path(__file__).absolute().parent
FILES=('controller.py','recovery.py','test_recovery.py','README.md')
ROOT=V.ROOT;REPO=V.REPO;PY=V.PY;PLAN=V.PLAN;MANIFEST=V.MANIFEST;G=V.G;C=V.C;F=V.F
load=V.load;pin=V.pin;write=V.write;process_identity=V.process_identity


def extra_sources():return [pin(HERE/name) for name in FILES]+[pin(M.HERE/name) for name in M.FILES]


def prior_review(prior):
    C.need(prior['schema']=='ROOT_FINITE_SPRIME_WAVE2_CONTROLLER_REVIEW_V3'
      and prior['status']=='APPROVED_FINITE_METADATA_CONTROLLER' and prior['reviewer']=='root'
      and prior['source_references']==V.sources(),'ORIGINAL_REVIEWED_V3_SOURCE_AUTHORITY_UNCHANGED')
    required=CG.recovery_inputs(pin,load,ROOT)
    C.need(all(prior.get(k)==v for k,v in required.items()),'ORIGINAL_ACTUAL33_AND59_METADATA_REPAIRS_RETAINED')
    for key,count in (('prior_state_repair_cpu_test_reference',12),):
        report=exact(required[key]);C.need(report['status']=='PASS' and report['tests_run']==count
          and report['failures']==report['errors']==0
          and report['source_references']==[pin(V.HERE.parent/'sprime_wave2_controller_v2'/name)
            for name in ('__init__.py','contract.py','controller.py','repair.py','test_state.py','test_repair.py','README.md')],
          'ORIGINAL_ACTUAL_STATE_TEST_EVIDENCE')
        parent=F.accounting(report['accounting_reference'],[str(report['job_id'])])[str(report['job_id'])]
        C.need(parent['state']=='COMPLETED' and parent['exit_code']=='0:0' and int(parent['alloc_cpus'])==16,'ORIGINAL_TEST_PARENT_C0')
    report=exact(prior['pure_state_cpu_test_reference'])
    C.need(report['status']=='PASS' and report['tests_run']==4 and report['failures']==report['errors']==0
      and report['source_references']==[pin(V.HERE/name) for name in V.FILES],'ORIGINAL_FOUR_CAPACITY_TESTS_NOT_RERUN')
    parent=F.accounting(report['accounting_reference'],[str(report['job_id'])])[str(report['job_id'])]
    C.need(parent['state']=='COMPLETED' and parent['exit_code']=='0:0' and int(parent['alloc_cpus'])==16,'ORIGINAL_CAPACITY_TEST_PARENT_C0')


class Controller(V.Controller):
    def __init__(self,args,review,manifest,plan,identity_ref,identity,recovery):
        self.args=args;self.review=review;self.review_ref=pin(args.review);self.manifest=manifest;self.plan=plan
        self.root=args.state_root;self.entries=recovery.entries;self.cache={};self.terminal_observations=set()
        self.recovery=recovery;self.repair=ClosurePaths(recovery)
        self.slots={r['batch_id']:r for r in plan['jobs']};self.slots['batch-00096']=recovery.slot
        self.launch=str(time.time_ns())+'_'+str(os.getpid());self.deadline=min(time.time()+args.max_seconds,identity['expires_unix_seconds']-300)
        C.need(time.time()<self.deadline,'EXISTING_PROVIDER_LEASE_HAS_NO_CONTROLLER_TIME_NO_RENEWAL')
        self.seq=len(list((self.root/'events').glob('event_*.json')));self.cycle=0
        self.identity_ref=write(self.root/'launches'/(self.launch+'.json'),dict(process_identity(os.getpid()),
          schema='ACTUAL_FINITE_SPRIME_WAVE2_CONTROLLER_LAUNCH_V4',review_reference=self.review_ref,
          source_references=[*V.sources(),*extra_sources()],actual_primary=str(HERE/'controller.py'),
          complete_argv=[PY,'-B','-m','workflows.data_v1_final.execution.sprime_wave2_controller_v4.controller',*sys.argv[1:]],
          endpoint='202.38.247.57:22',node='sonmi',publisher_identity_reference=identity_ref,deadline_unix_seconds=self.deadline,
          resume=args.resume,root_reason=args.reason,single_cycle=args.single_cycle,scientific_dispatch_on_login=False,
          continuation_repair_map_reference=recovery.reference,original_HOLD_reference=review['resume_from_state_reference']))
        self.event('ACTUAL95_AND96_ROOT_EXPLICIT_CONTINUATION_ADOPTED',repair_map_reference=recovery.reference,
          old_history_unchanged=True,old_failed96_cost_retained=True,new96_already_actually_closed=True,
          original_failed96_accounting_reference=recovery.failed_accounting_reference,
          original_zero_close_accounting_reference=recovery.value['original96_close_accounting_reference'],
          only_future97_through179_may_be_dispatched=True)

    def budget(self):
        super().budget()
        C.need(extra_sources()==self.review['continuation_source_references'],'NEW_RECOVERY_SOURCE_CHANGED_HOLD')

    def report_plan(self,bid):return self.recovery.plan_reference if bid=='batch-00096' else PLAN

    def expected_argv(self,bid,stage,request):
        if bid!='batch-00096' or stage=='prepare':return super().expected_argv(bid,stage,request)
        proof=request['startup_proof_path'];quota=self.manifest['quota_reuse_review_reference']['path'];config=self.manifest['config_reference']['path']
        prepared=self.recovery.prepared_reference['path']
        if stage=='run':return [PY,'-B',str(G.FORMAL/'run_batch.py'),'--config',config,'--prepared',prepared,
          '--root-preflight',proof,'--quota-reuse-review',quota,'--output',self.slots[bid]['output_root']]
        argv=request['execution_argv'];C.need('--descriptor' in argv,'ACTUAL_CLOSE_DESCRIPTOR_REQUIRED')
        path=pathlib.Path(argv[argv.index('--descriptor')+1]);C.need(ROOT/'control' in path.parents,'ONLY_ROOT_CONTROL_CLOSE_DESCRIPTOR')
        descriptor=load(path);C.need(descriptor['plan']==self.recovery.plan_reference
          and descriptor['prepared']==self.recovery.prepared_reference,'EXACT96_NEW_PLAN_AND_ORIGINAL_TASK_HEADER')
        return [PY,'-B',str(self.repair.primary(bid)),'close','--config',config,'--root-preflight',proof,
          '--quota-reuse-review',quota,'--descriptor',str(path),'--output',str(self.repair.output(bid))]

    def discover(self):
        stages={bid:{} for bid in G.BATCHES}
        for bid in G.BATCHES:
            for stage in C.STAGES:
                entry=self.entries.get((bid,stage));name,phase,directory=self.stage_paths(bid,stage)
                intent=self.root/'intents'/(bid+'_'+stage+'.json')
                if entry is None:
                    rp=ROOT/'control/requests'/(name+'.json');sp=ROOT/'control/submissions'/(name+'.json')
                    if intent.exists() or rp.exists() or sp.exists():
                        sub=load(sp) if sp.exists() else None;ap=ROOT/'control/cpu_auto_memory_activations'/(phase+'.json');reg=ROOT/'control/cpu_auto_memory_registries'/(phase+'.json')
                        resolution=C.submission_resolution(intent.exists(),rp.exists(),sub,ap.exists() and reg.exists())
                        if resolution!='REGISTERED':stages[bid][stage]={'ambiguous':True,'reason':resolution};continue
                        entry=dict(stage_spec_reference=pin(directory/'stage_spec.json'),request_reference=pin(rp),submission_reference=pin(sp),activation_reference=pin(ap),registry_reference=pin(reg))
                if entry is not None:stages[bid][stage]=self.registration(bid,stage,entry)
        known=[row for s in stages.values() for row in s.values() if row.get('job_id')]
        if known:
            argv,raw,parents=self.sacct([r['job_id'] for r in known],'all_registered_stages')
            for row in known:
                actual=parents[row['job_id']];row.update(state=actual['State'].split()[0],exit_code=actual['ExitCode'],
                    terminal=actual['State'].split()[0] in C.TERMINAL,actual_parent=actual)
        for bid,s in stages.items():
            if C.c0(s.get('close')):
                path=self.repair.report_path(bid);report=load(path)
                C.need(report['batch_id']==bid and report['actual_parent_job_id']==s['run']['job_id'] and report['plan']==self.report_plan(bid),
                    'ACTUAL_CLOSE_OUTPUT_CHAIN_MISMATCH')
                s['close']['report']=report;s['close']['report_reference']=pin(path)
        return stages




def main():
    V.on_login();p=argparse.ArgumentParser(description=__doc__)
    for key in ('review','recovery-map','state-root'):p.add_argument('--'+key,type=pathlib.Path,required=True)
    p.add_argument('--root-run-reviewed-wave2',action='store_true');p.add_argument('--reason',required=True)
    p.add_argument('--observe-only',action='store_true');p.add_argument('--single-cycle',action='store_true');p.add_argument('--resume',action='store_true')
    p.add_argument('--max-seconds',type=int,default=3600);p.add_argument('--poll-seconds',type=int,default=15);args=p.parse_args()
    C.need(HERE==REPO/'workflows/data_v1_final/execution/sprime_wave2_controller_v4'
      and pathlib.Path(sys.modules['__main__'].__file__).absolute()==HERE/'controller.py'
      and process_identity(os.getpid())['argv']==[PY,'-B','-m','workflows.data_v1_final.execution.sprime_wave2_controller_v4.controller',*sys.argv[1:]],
      'ACTUAL_V4_PRIMARY_AND_COMPLETE_CONTROLLER_ARGV')
    C.need(args.root_run_reviewed_wave2 and args.reason.strip(),'EXPLICIT_ROOT_FINITE_REVIEW_REQUIRED')
    review=load(args.review);manifest,plan,identity_ref,identity=V.fixed_inputs()
    C.need(review['schema']=='ROOT_FINITE_SPRIME_WAVE2_CONTROLLER_REVIEW_V4'
      and review['status']=='APPROVED_FINITE_METADATA_CONTROLLER' and review['reviewer']=='root'
      and review['endpoint']=='202.38.247.57:22' and review['uid']==1278 and review['manifest_reference']==MANIFEST
      and review['plan_reference']==PLAN and review['source_references']==V.sources()
      and review['continuation_source_references']==extra_sources() and review['publisher_identity_reference']==identity_ref
      and review['continuation_repair_map_reference']==pin(args.recovery_map)
      and review['maximum_nonterminal_science']==2 and review['maximum_nonterminal_aux']==1
      and review['maximum_owned_data_run_pending']==4 and review['stop_before_publisher_expiry_seconds']==300
      and 1<=args.max_seconds<=review['maximum_seconds']<=86400 and 5<=args.poll_seconds<=30,
      'EXACT_INDEPENDENT_V4_ROOT_SOURCE_SCOPE_AND_ORIGINAL_LIMITS')
    prior=exact(review['supersedes_review_reference']);prior_review(prior)
    C.need(review['adoption_reference']==prior['adoption_reference'],'ORIGINAL_FOUR_INITIAL_REGISTRATIONS_RETAINED')
    recovery=Recovery(pin(args.recovery_map),review,prior)
    old_launch=exact(recovery.hold['launch_identity_reference']);old_proc=pathlib.Path('/proc',str(old_launch['pid']))
    if old_proc.exists():
        current=process_identity(old_launch['pid'])
        C.need(current['boot_id']!=old_launch['boot_id'] or current['start_ticks']!=old_launch['start_ticks'],
          'OLD_EXACT_CONTROLLER_STILL_LIVE_NO_SECOND_CONTROLLER')
    tests=exact(review['pure_recovery_cpu_test_reference'])
    C.need(tests['status']=='PASS' and tests['tests_run']==3 and tests['failures']==tests['errors']==0
      and tests['source_references']==[pin(HERE/name) for name in FILES],'THREE_ACTUAL_NEW_PURE_RECOVERY_TESTS_REQUIRED')
    row=F.accounting(tests['accounting_reference'],[str(tests['job_id'])])[str(tests['job_id'])]
    C.need(row['state']=='COMPLETED' and row['exit_code']=='0:0' and int(row['alloc_cpus'])==16,'ACTUAL_NEW_RECOVERY_TEST_C0')
    root=args.state_root;C.need(V.BASE in root.parents and '..' not in root.parts
      and not any(q.is_symlink() for q in (root,*root.parents)),'NEW_OR_REVIEWED_RESUMED_V4_STATE_ROOT')
    if args.resume:
        latest=load(root/'latest.json')['state_reference'];previous=exact(latest)
        C.need(previous['manifest_reference']==MANIFEST and previous['plan_reference']==PLAN,'SAME_ORIGINAL179_ON_V4_RESUME')
        if previous['status'].startswith('HOLD') or previous['review_reference']!=pin(args.review):
            C.need(review.get('previous_v4_state_reference')==latest and review.get('supersedes_v4_review_reference')==previous['review_reference']
              and previous['review_reference']!=pin(args.review),'NEW_ROOT_REVIEW_MUST_BIND_EXACT_V4_HOLD')
    else:C.need(not root.exists(),'NEW_V4_ROOT_REQUIRED_OLD_STATE_NEVER_REWRITTEN');root.mkdir(parents=True,mode=0o700)
    for name in ('events','states','launches','commands','accounts','stages','intents'):(root/name).mkdir(exist_ok=args.resume)
    lock=V.BASE/'wave2_single_instance.lock';fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(fd);C.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and info.st_nlink==1,'OWN_ORIGINAL_SINGLE_INSTANCE_LOCK')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return Controller(args,review,manifest,plan,identity_ref,identity,recovery).run()
    finally:os.close(fd)


if __name__=='__main__':raise SystemExit(main())
