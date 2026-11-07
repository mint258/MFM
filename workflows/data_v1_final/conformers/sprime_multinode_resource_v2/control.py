"""Finite manual resource epoch;reuse old state/accounting/registration primitives."""
import argparse,fcntl,json,os,pathlib,stat,sys,time
from . import contract as C,edge as E,cutover
from workflows.data_v1_final.execution.sprime_resource_epoch_v1 import controller as OLD
from workflows.data_v1_final.execution.sprime_wave2_controller_v3 import capacity_gate as CG
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import free_cpu_observation,fields
V=OLD.V;W=OLD.W;G=OLD.G;F=OLD.F
def choose_node(raw_by_node,limits,science_by_node,maximum,nonterminal_science,*,old_live=False,lock_busy=False,reserved_free=0):
    if old_live:return {'action':'WAIT','reason':'OLD_METADATA_STILL_LIVE','intents':0}
    if lock_busy:return {'action':'WAIT','reason':'SERIALIZATION_LOCK_BUSY','intents':0}
    if nonterminal_science>=maximum:return {'action':'WAIT','reason':'GLOBAL_NONTERMINAL_SCIENCE_LIMIT','intents':0}
    candidates=[];total_free=0
    for node in sorted(limits):
        C.node(node);raw=raw_by_node[node]
        try:obs=free_cpu_observation({'node':node,'cpus':16},raw)
        except ValueError as exc:
            if str(exc)!='WAIT_ACTUAL16_FREE_CPU_REQUIRED':raise
            row=fields(raw) if isinstance(raw,str) else raw;total=int(row['CPUTot']);allocated=int(row['CPUAlloc'])
            C.need(0<=allocated<=total and 0<=total-allocated<16,'ONLY_ACTUAL_LOW_CAPACITY_IS_WAIT');total_free+=total-allocated;continue
        total_free+=obs['free_cpus']
        if science_by_node.get(node,0)<limits[node]:candidates.append(obs)
    if total_free-16<reserved_free:return {'action':'WAIT','reason':'EXPLICIT_ROOT_FREE_CPU_RESERVE','intents':0}
    if not candidates:return {'action':'WAIT','reason':'CURRENT_CAPACITY_OR_NODE_LOCAL_LIMIT','intents':0}
    choice=min(candidates,key=lambda r:(-r['free_cpus'],r['node']));return {'action':'PROCEED','node':choice['node'],'actual_capacity':choice,'intents':0}

class Controller(OLD.Controller):
    # discover/cost/sacct/command/snapshot and historical recovery remain the
    # actual old method objects,with only explicit registration/path adapters.
    def __init__(self,args,review,resource,old_review,old_epoch,identity,probe,recovery):
        manifest,plan,_,_=V.fixed_inputs();self.args=args;self.review=review;self.review_ref=V.pin(args.review);self.manifest=manifest;self.plan=plan
        self.resource=resource;self.old_review=old_review;self.epoch=old_epoch;self.probe=probe;self.root=args.state_root;self.recovery=recovery;self.repair=W.ClosurePaths(recovery)
        self.entries=dict(recovery.entries);adoption=E.meta(resource['adoption_reference']);self.adopted={};self.new_nodes={}
        for row in adoption['registrations']:
            key=(row['batch_id'],row['stage']);C.need(key not in self.adopted,'ONE_ACTUAL_ADOPTED_STAGE_NO_DUPLICATE_NATIVE_PARENT')
            self.adopted[key]=row;self.entries[key]=row['registration']
        self.cache={};self.terminal_observations=set();self.slots={r['batch_id']:r for r in plan['jobs']};self.slots['batch-00096']=recovery.slot
        self.launch=str(time.time_ns())+'_'+str(os.getpid());self.deadline=min(resource['deadline_unix_seconds'],identity['expires_unix_seconds']-300)
        C.need(time.time()<self.deadline and self.deadline-resource['started_unix_seconds']<=72000,'FINITE20H_AND_EXISTING_PROVIDER_EXPIRY_NO_RENEW')
        self.seq=len(list((self.root/'events').glob('event_*.json')));self.cycle=0
        self.identity_ref=V.write(self.root/'launches'/(self.launch+'.json'),dict(V.process_identity(os.getpid()),schema='ACTUAL_SPRIME_MULTINODE_METADATA_CONTROLLER_V2',
            source_references=C.own_sources(),actual_primary=str(C.HERE/'control.py'),complete_argv=[G.PY,'-B','-m',C.MODULE+'.control',*sys.argv[1:]],
            endpoint='202.38.247.57:22',node='sonmi',resource_epoch_reference=review['resource_epoch_reference'],deadline_unix_seconds=self.deadline,
            old_controller_reference=resource['old_controller_identity_reference'],publisher_identity_reference=old_epoch['publisher_identity_reference'],
            resume=args.resume,scientific_dispatch_on_login=False))
        self.verify_adoption_paths();self.event('EXPLICIT_POSTSTOP_MULTINODE_ADOPTION',epoch_reference=review['resource_epoch_reference'],old_files_unchanged=True,scientific_release=False)
    def verify_adoption_paths(self):
        # All179 old canonical names are examined after the original global
        # controller lock was acquired. Missing/partial/unknown registrations
        # cannot be bypassed by this new metadata namespace.
        C.need(cutover.no_live_old(cutover.old_identity(self.resource['old_controller_identity_reference'])),'OLD_CONTROLLER_SAME_IDENTITY_STILL_LIVE')
        for bid in G.BATCHES:
            for stage in ('prepare','run','close'):
                original_name=self.slots[bid]['job_name'] if stage=='run' else 'dv1_q_sprime_v3_w2_ctl_b'+bid[6:]+'_'+stage+'_20261027_v1'
                req=G.ROOT/'control/requests'/(original_name+'.json');sub=G.ROOT/'control/submissions'/(original_name+'.json')
                if req.exists() or sub.exists():
                    if (bid,stage) not in self.adopted and req.exists() and sub.exists():
                        q=V.load(req);intent=self.root/'intents'/(bid+'_'+stage+'.json')
                        if q.get('scope_key')=='sprime_multinode_resource_v2_'+stage and intent.exists():
                            i=V.load(intent);C.need(i['stage_spec_reference']==q['root_review']['stage_spec_reference']
                                and self.review['resource_epoch_reference'] in q['source_references'],'ONLY_THIS_EPOCH_ACTUAL_DURABLE_INTENT_MAY_EXTEND_OLD_PATHS')
                            continue
                    C.need((bid,stage) in self.adopted,'ACTUAL_OLD_REGISTRATION_NOT_IN_ROOT_POSTSTOP_ADOPTION')
                    row=self.adopted[(bid,stage)]['registration'];C.need(req.exists() and sub.exists() and V.pin(req)==row['request_reference']
                        and V.pin(sub)==row['submission_reference'],'PARTIAL_OR_UNRECONCILED_OLD_REGISTRATION_HOLD')
    def budget(self):
        V.Controller.budget(self);C.need(C.own_sources()==self.resource['own_source_references'],'NEW_RESOURCE_CODE_CHANGED')
        C.need(time.time()<self.resource['deadline_unix_seconds'],'MANUAL_EPOCH_ENDED_NO_AUTO_RENEW')
    def stage_paths(self,bid,stage):
        key=(bid,stage)
        if key in self.adopted:
            req=V.load(self.adopted[key]['registration']['request_reference']['path']);name=req['job_name'];phase=req.get('phase',self.adopted[key].get('phase','adopted_no_new_transition'))
        else:
            name=self.slots[bid]['job_name'] if stage=='run' else 'dv1_q_sprime_mn_'+bid[6:]+'_'+stage+'_v1'
            phase='sprime_mn_'+bid[6:]+'_'+stage+'_v1'
        return name,phase,self.root/'stages'/bid/(stage+'_v1')
    def expected_argv(self,bid,stage,request):
        if request['scope_key'].startswith('sprime_multinode_resource_v2_'):
            argv=request['execution_argv'];C.need(argv[0:3]==[G.PY,'-B',str(C.HERE/('run_batch.py' if stage=='run' else 'prepare_batch.py' if stage=='prepare' else 'close.py'))],'EXACT_NEW_RESOURCE_PRIMARY')
            return argv
        return OLD.Controller.expected_argv(self,bid,stage,request)
    def registration(self,bid,stage,entry):
        req=V.load(entry['request_reference']['path'])
        if not req['scope_key'].startswith('sprime_multinode_resource_v2_'):
            adopted=self.adopted.get((bid,stage));C.need(adopted is not None and adopted['registration']==entry,'ONLY_ROOT_EXACT_OLD_ADOPTION')
            if adopted.get('held_without_activation'):
                C.need(adopted['pending_action']=='KEEP_EXISTING_HELD_NO_MODIFICATION','NO_AUTOMATIC_PENDING_RELEASE_OR_REPLACEMENT')
                sub=V.load(entry['submission_reference']['path']);C.need(sub['request']==req and sub['uid']==1278 and sub['sbatch_returncode']==0,'ACTUAL_EXISTING_HELD_SUBMISSION')
                return {'job_id':str(sub['job_id']),'job_name':req['job_name'],'registration':entry,'terminal':False,'state':'UNOBSERVED','exit_code':None,'adopted_held':True}
            if bid in OLD.E.FUTURE or bid=='batch-00096' and stage in ('run','close'):
                C.need(self.old_review['resource_epoch_reference'] in req['source_references'] and self.old_review['probe_closure_reference'] in req['source_references'],'ADOPTED_ACTUAL_OLD_EPOCH_NOT_NEW_NODE_PROOF')
            return V.Controller.registration(self,bid,stage,entry)
        # The original exact registry/activation/central request validators are
        # used,with only this explicit namespace and actual node predicate.
        from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_request,validate_bound_request
        for r in entry.values():C.need(V.pin(r['path'])==r,'REGISTERED_SOURCE_BYTES_CHANGED')
        sub=V.load(entry['submission_reference']['path']);spec=V.load(entry['stage_spec_reference']['path'])
        C.need(sub['request']==req and sub['request_reference']==entry['request_reference'] and sub['sbatch_returncode']==0 and sub['uid']==1278
            and req['root_review']['stage_spec_reference']==entry['stage_spec_reference'],'EXACT_ACTUAL_NEW_SUBMISSION_SPEC_CHAIN')
        C.need(req['scope_key']=='sprime_multinode_resource_v2_'+stage and req['scope_parameters']==C.scope(stage,self.manifest['config_reference'])
            and req['node'] in self.resource['node_binding_references'] and req['cpus']==16 and req['pilot'] is False
            and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['wall_seconds']=={'prepare':14400,'run':28800,'close':7200}[stage],
            'EXACT_NEW_STAGE_KIND_SCOPE_RESOURCES')
        validate_request(req,read_small=C.Q.read_small);validate_bound_request(req,read_small=C.Q.read_small)
        from .metadata import expected_science_argv
        C.need(req['execution_argv']==expected_science_argv(stage,bid,req['startup_proof_path'],req['source_references'],self.resource),'EXACT_ORIGINAL_TASK_PLAN_OUTPUT_AND_NODE_RESOURCE_OPTIONS')
        activation=V.load(entry['activation_reference']['path']);registry=V.load(entry['registry_reference']['path'])
        C.need(activation['registry_reference']==entry['registry_reference'] and any(str(r['job_id'])==str(sub['job_id']) for r in activation['releases'])
            and any(str(r['job_id'])==str(sub['job_id']) and r['request_reference']==entry['request_reference'] and r['receipt_reference']==entry['submission_reference'] for r in registry['jobs']),'ACTUAL_ACTIVATION_AND_REGISTRY_NO_FAKE_RELEASE')
        return {'job_id':str(sub['job_id']),'job_name':req['job_name'],'registration':entry,'terminal':False,'state':'UNOBSERVED','exit_code':None}
    def transition(self,bid,stage,stages):
        manager=CG.serialization_lock(G.ROOT/'control'/CG.LOCK_NAME)
        try:fd=manager.__enter__()
        except BlockingIOError:return False
        try:
            self.verify_adoption_paths();raw={n:C.Q.query(['scontrol','show','node',n,'--oneliner']) for n in self.resource['maximum_science_per_node']}
            by={n:0 for n in raw};by_aux={n:0 for n in raw};sci=0
            for items in stages.values():
                if items.get('run') and not items['run'].get('terminal'):
                    sci+=1;req=V.load(items['run']['registration']['request_reference']['path']);by[req['node']]=by.get(req['node'],0)+1
                for k,row in items.items():
                    if k!='run' and not row.get('terminal') and row.get('registration'):
                        req=V.load(row['registration']['request_reference']['path']);by_aux[req['node']]=by_aux.get(req['node'],0)+1
            limits=self.resource['maximum_science_per_node'] if stage=='run' else {n:max(1,v) for n,v in self.resource['maximum_aux_per_node'].items()}
            decision=choose_node(raw,limits,by if stage=='run' else by_aux,self.resource['maximum_nonterminal_science'] if stage=='run' else 100000,
                sci if stage=='run' else 0,reserved_free=self.resource['minimum_reserved_free_CPU_total'])
            if decision['action']!='PROCEED':self.event('WAIT_ACTUAL_NODE_CAPACITY',decision=decision,raw_scontrol=raw);return False
            node=decision['node'];self.outer_submission_fd=fd;self.new_nodes[(bid,stage)]=node
            name,phase,directory=self.stage_paths(bid,stage);intent=self.root/'intents'/(bid+'_'+stage+'.json')
            C.need(not directory.exists() and not intent.exists(),'EXISTING_METADATA_INTENT_NEVER_REISSUED')
            previous='4521486' if stage=='prepare' else stages[bid]['prepare' if stage=='run' else 'run']['job_id'];account=self.account(previous,bid+'_'+stage)
            generator=[G.PY,'-B','-m',C.MODULE+'.metadata','delegated-stage','--epoch',self.review['resource_epoch_reference']['path'],'--controller-review',str(self.args.review),
                '--node',node,'--stage',stage,'--batch-id',bid,'--accounting',account['path'],'--output',str(directory)]
            if stage=='close':generator.extend(['--registration',str(self.root/'close_run_registration_'+bid+'.json')]);V.write(self.root/('close_run_registration_'+bid+'.json'),stages[bid]['run']['registration'])
            self.command(generator,'generate_'+bid+'_'+stage)
            spec=V.pin(directory/'stage_spec.json');helper=[G.PY,'-B',str(V.HELPER),'--spec',spec['path'],'--node',node,'--name',name,'--phase',phase]
            V.write(intent,{'schema':'SPRIME_CONTROLLER_SUBMISSION_INTENT_NO_REISSUE_V2','batch_id':bid,'stage':stage,'stage_spec_reference':spec,
                'helper_argv':helper,'expected_name':name,'expected_phase':phase,'actual_job_id':None,'launch_identity_reference':self.identity_ref,'actual_capacity_before_transition':decision,'reason':self.args.reason})
            self.command(helper,'central_submit_'+bid+'_'+stage,240);return True
        finally:self.outer_submission_fd=None;manager.__exit__(None,None,None)
    def run(self):
        stages={}
        while time.time()<self.deadline:
            try:
                self.budget();stages=self.discover();self.persist_terminal_costs(stages);pending=self.owned_pending()
                decisions={b:V.C.next_stage(s) for b,s in stages.items()};holds={}
                for bid,decision in decisions.items():
                    if decision['action']!='HOLD':continue
                    accepted=self.resource.get('preserved_HOLD_dispositions',{}).get(bid)
                    if accepted:
                        actual=stages[bid].get(accepted['stage'],{});C.need(str(actual.get('job_id'))==str(accepted['job_id']) and actual.get('state')==accepted['state']
                            and actual.get('terminal') is True,'PRESERVED_HOLD_MUST_MATCH_CURRENT_ACTUAL_PARENT_NO_AUTOMATIC_CAUSE_INFERENCE')
                    else:holds[bid]=decision
                if holds:self.snapshot('HOLD_ROOT_REVIEW_NO_AUTOMATIC_RETRY',stages,holds);return 3
                if all(r['action']=='DONE' for r in decisions.values()):self.snapshot('ALL179_CLOSED_NOT_SCIENCE_OR_COMMON_RELEASE',stages);return 0
                if all(decisions[b]['action']=='DONE' for b in self.resource['allowed_initial_batch_ids']):
                    self.snapshot('ALL_APPROVED_INDEPENDENT_BATCHES_CLOSED_PRESERVED_HOLD_NO_FULL_RELEASE',stages,self.resource.get('preserved_HOLD_dispositions',{}));return 0
                sci=sum(not r.get('terminal') for s in stages.values() for k,r in s.items() if k=='run');aux=sum(not r.get('terminal') for s in stages.values() for k,r in s.items() if k!='run')
                candidates=[{'batch_id':b,'stage':r['action']} for b,r in decisions.items() if b in self.resource['allowed_initial_batch_ids'] and r['action'] in V.C.STAGES
                    and pending<self.resource['maximum_owned_data_run_pending'] and (sci<self.resource['maximum_nonterminal_science'] if r['action']=='run' else aux<self.resource['maximum_nonterminal_aux'])]
                selected=V.C.choose(candidates);self.snapshot('OBSERVED_NEXT_RESOURCE_TRANSITION' if selected else 'WAIT_ACTUAL_EXISTING_JOBS_OR_LIMITS',stages,selected)
                if selected and not self.args.observe_only:self.transition(selected['batch_id'],selected['stage'],stages)
                if self.args.single_cycle:return 0
                time.sleep(min(self.args.poll_seconds,max(0,self.deadline-time.time())))
            except Exception as exc:self.snapshot('HOLD_ROOT_REVIEW_NO_AUTO_REISSUE',stages,repr(exc));return 3
        self.snapshot('FINITE20H_EPOCH_ENDED_NO_SCIENCE_SIGNALS_OR_RENEWAL',stages);return 0

def main():
    C.Q.on_login();p=argparse.ArgumentParser(description=__doc__)
    for k in ('review','state-root'):p.add_argument('--'+k,type=pathlib.Path,required=True)
    p.add_argument('--root-run-reviewed-wave2',action='store_true');p.add_argument('--reason',required=True);p.add_argument('--observe-only',action='store_true');p.add_argument('--single-cycle',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--poll-seconds',type=int,default=15);a=p.parse_args()
    C.need(a.root_run_reviewed_wave2 and a.reason.strip() and 5<=a.poll_seconds<=30,'EXPLICIT_ROOT_FINITE_METADATA_ACTION')
    rr=C.ref(a.review);review=E.meta(rr);C.root(review,'ROOT_SPRIME_MULTINODE_CONTROLLER_REVIEW_V2','APPROVED_FINITE_METADATA_CONTROLLER');resource=C.epoch(review['resource_epoch_reference'],active=True)
    C.need(set(review['quota_reuse_references'])==set(resource['node_binding_references']),'EXACT_ENABLED_NODE_QUOTA_REVIEWS')
    for n,r in review['quota_reuse_references'].items():
        q=E.meta(r);C.need(q['epoch_reference']==review['resource_epoch_reference'] and q['node_binding_reference']==resource['node_binding_references'][n],'ROOT_CONTROLLER_POSTEPOCH_QUOTA_BINDING_NO_REFERENCE_CYCLE')
    resource=dict(resource,quota_reuse_references=review['quota_reuse_references'])
    old_review,old_epoch,identity,probe,recovery=OLD.E.controller_inputs(resource['old_controller_review_reference'],active=False)
    C.need(review['source_references']==C.own_sources() and review['adoption_reference']==resource['adoption_reference']
        and pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'control.py','EXACT_NEW_PRIMARY_SOURCE')
    root=a.state_root;C.need(C.META in root.parents and '..' not in root.parts and not any(x.is_symlink() for x in (root,*root.parents)),'OWN_NEW_METADATA_STATE_ROOT')
    if a.resume:
        previous=E.meta(E.meta(C.ref(root/'latest.json'))['state_reference'])
        C.need(review.get('resume_from_state_reference')==C.ref(root/'latest.json') and review.get('supersedes_review_reference')==previous['review_reference'],'MANUAL_RESUME_REQUIRES_NEW_EXACT_ROOT_REVIEW')
    else:C.need(not root.exists(),'NEW_ROOT_NO_HOTPATCH_OR_STATE_ESCAPE');root.mkdir(parents=True)
    for name in ('events','states','launches','commands','accounts','stages','intents'):(root/name).mkdir(exist_ok=a.resume)
    fd=os.open(V.BASE/'wave2_single_instance.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        st=os.fstat(fd);C.need(stat.S_ISREG(st.st_mode) and st.st_uid==1278 and st.st_nlink==1,'ORIGINAL_MAIN_CONTROLLER_LOCK')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);return Controller(a,review,resource,old_review,old_epoch,identity,probe,recovery).run()
    finally:os.close(fd)
if __name__=='__main__':raise SystemExit(main())
