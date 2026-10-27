"""Root finite login metadata controller; all project science stays in Slurm."""
from __future__ import annotations
import argparse,csv,fcntl,hashlib,io,json,os,pathlib,stat,subprocess,sys,time
REPO_PATH=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO_PATH));sys.dont_write_bytecode=True
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import ROOT,REPO,PY,on_login,write_new,read_small
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.registry import process_identity
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_bound_request,validate_request
from workflows.data_v1_final.execution.sprime_wave2_metadata_v1 import generate as G
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as F
from workflows.data_v1_final.execution.sprime_wave2_controller_v2 import contract as C,repair as RP
from workflows.data_v1_final.execution.sprime_wave2_controller_v3 import capacity_gate as CG

HERE=pathlib.Path(__file__).absolute().parent
FILES=('__init__.py','controller.py','capacity_gate.py','test_capacity.py','README.md')
MANIFEST={'path':str(ROOT/'control/sprime_v3_wave2_freeze_stage_v1/wave2_manifest.json'),'bytes':5821,'sha256':'4320aa98c09684e7bd4fbc2392a4c73df9f991d9fa998ba40fc56844436ddf40'}
PLAN={'path':str(G.WAVE2/'frozen_v1/plan.json'),'bytes':124998,'sha256':'d2f592f2dcb0bd8a3d2d62e368da998adec4901ae11126149906f1f268a83827'}
HELPER=ROOT/'control/submit_one_queued_cpu_stage_20261026_v2.py'
HELPER_SHA='9aea8fe7ef8714b1dfa713e241f29a155a4e8b27d776c85948c58fcb7c676980'
GEN_SHA={'__init__.py':'ab05b070d58d2f54ba64f0abb24a50ed6abd8a3a70ce75fe35a0f3265f2177ad',
    'generate.py':'eb67b2ce4c10e8c1c07b89e74edf8f637790aab3a743290924499e3e93241675',
    'README.md':'acfb7f1a09a26e5050ec4e1c7c8b19c8dd33b5dd06369c2a8207447a9a506963'}
BASE=ROOT/'control/sprime_wave2_controller_v1';CAP=8<<30
REQUIRED_ADOPTION={('batch-00001','prepare'):'4521489',('batch-00002','prepare'):'4521490',
    ('batch-00001','run'):'4521493',('batch-00002','run'):'4521494'}


def fsync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def write(path,value):
    reference=write_new(path,value);fsync_dir(pathlib.Path(path).parent);return reference


def pin(path):return G.meta_pin(path)
def load(path):return G.metadata(path)[1]


def sources():
    old=HERE.parent/'sprime_wave2_controller_v1'
    prior=HERE.parent/'sprime_wave2_controller_v2'
    values=[pin(HERE/n) for n in FILES]+[pin(prior/n) for n in ('__init__.py','contract.py','controller.py','repair.py','test_state.py','test_repair.py','README.md')]+[pin(old/n) for n in ('__init__.py','contract.py','controller.py','test_state.py','README.md')]+[pin(G.HERE/n) for n in G.FILES]+[pin(HELPER)]
    C.need(values[-1]['sha256']==HELPER_SHA,'FROZEN_CENTRAL_HELPER_CHANGED')
    for name,sha in GEN_SHA.items():C.need(pin(G.HERE/name)['sha256']==sha,'FROZEN_GENERATOR_CHANGED:'+name)
    queue=REPO/'workflows/data_v1_final/execution'
    for path in sorted((queue/'cpu_auto_memory_queue_v2').glob('*.py')):values.append(pin(path))
    values.extend(pin(queue/name) for name in ('queued_cpu_submit_v1.py','queue_v1/__init__.py','queue_v1/shared.py','queue_v1/queue_contract.py'))
    return list({r['path']:r for r in values}.values())


def fixed_inputs():
    C.need(pin(MANIFEST['path'])==MANIFEST and pin(PLAN['path'])==PLAN,'ACTUAL_FROZEN_WAVE2_MANIFEST_PLAN_PINS_CHANGED')
    manifest,plan=load(MANIFEST['path']),load(PLAN['path'])
    C.need(plan['runtime']['job_id']=='4521486' and plan['imports320_durably_verified'] is True
        and plan['maximum_concurrent_jobs']==2 and manifest['whole_wave_output_reserve_bytes']==G.WAVE_RESERVE,
        'REAL_1486_FROZEN179_WAVE_ONLY')
    F.approve_wave(plan['draft'],F.read(plan['draft']),plan['root_review'],manifest['config_reference'])
    quota=load(manifest['quota_reuse_review_reference']['path']);identity_ref=quota['publisher_identity_reference'];identity=load(identity_ref['path'])
    C.need(pin(identity_ref['path'])==identity_ref and identity['uid']==1278 and identity['endpoint']=='202.38.247.57:22',
        'ACTUAL_FINITE_MAIN_PUBLISHER_IDENTITY')
    return manifest,plan,identity_ref,identity


def review_inputs(adoption_path):
    manifest,plan,identity_ref,identity=fixed_inputs()
    return {'schema':'SPRIME_WAVE2_CONTROLLER_REVIEW_INPUT_LOCATORS_ONLY_V1','manifest_reference':MANIFEST,'plan_reference':PLAN,
        'adoption_reference':pin(adoption_path),'source_references':sources(),'publisher_identity_reference':identity_ref,
        'controller_deadline_maximum_unix_seconds':identity['expires_unix_seconds']-300,'maximum_seconds':86400,
        'maximum_nonterminal_science':2,'maximum_nonterminal_aux':1,'maximum_owned_data_run_pending':4,
        'no_scientific_bodies_read':True,'jobs_submitted':0,'approved':False}


def validate_adoption(reference):
    value=load(reference['path']);C.need(pin(reference['path'])==reference,'ADOPTION_REFERENCE_CHANGED')
    C.need(value['schema']=='ROOT_SPRIME_WAVE2_CONTROLLER_ADOPTION_V1' and value['reviewer']=='root'
        and value['endpoint']=='202.38.247.57:22' and value['uid']==1278 and value['manifest_reference']==MANIFEST
        and value['plan_reference']==PLAN and value['all_manual_known_registrations_included'] is True,'ROOT_EXPLICIT_COMPLETE_MANUAL_ADOPTION_REQUIRED')
    entries={}
    for entry in value['entries']:
        key=(entry['batch_id'],entry['stage']);C.need(key[0] in G.BATCHES and key[1] in C.STAGES and key not in entries,'EXACT_UNIQUE_ADOPTED_BATCH_STAGE')
        for name in ('stage_spec_reference','request_reference','submission_reference','activation_reference','registry_reference'):
            C.need(pin(entry[name]['path'])==entry[name],'ACTUAL_ADOPTION_METADATA_PIN_CHANGED:'+name)
        entries[key]=entry
    C.need(set(REQUIRED_ADOPTION)<=set(entries),'ALL_FOUR_ALREADY_ACTUAL_MANUAL_PREPARE_AND_RUN_REGISTRATIONS_MUST_BE_ADOPTED')
    for key,jid in REQUIRED_ADOPTION.items():C.need(str(load(entries[key]['submission_reference']['path'])['job_id'])==jid,'EXACT_ACTUAL_MANUAL_PARENT_ID_REQUIRED')
    return entries


class Controller:
    def __init__(self,args,review,manifest,plan,identity_ref,identity):
        self.args=args;self.review=review;self.review_ref=pin(args.review);self.manifest=manifest;self.plan=plan
        self.root=args.state_root;self.entries=validate_adoption(review['adoption_reference']);self.cache={};self.terminal_observations=set()
        self.repair=RP.Repair(review['repair_map_reference'],review);self.entries[(RP.BID,'close')]=self.repair.entry
        self.slots={r['batch_id']:r for r in plan['jobs']};self.launch=str(time.time_ns())+'_'+str(os.getpid())
        self.deadline=min(time.time()+args.max_seconds,identity['expires_unix_seconds']-300)
        C.need(time.time()<self.deadline,'EXISTING_PROVIDER_LEASE_HAS_NO_CONTROLLER_TIME_NO_RENEWAL')
        self.seq=len(list((self.root/'events').glob('event_*.json')));self.cycle=0
        self.identity_ref=write(self.root/'launches'/(self.launch+'.json'),dict(process_identity(os.getpid()),
            schema='ACTUAL_FINITE_SPRIME_WAVE2_CONTROLLER_LAUNCH_V1',review_reference=self.review_ref,
            source_references=sources(),actual_primary=str(HERE/'controller.py'),complete_argv=[PY,'-B',str(HERE/'controller.py'),*sys.argv[1:]],
            endpoint='202.38.247.57:22',node='sonmi',publisher_identity_reference=identity_ref,deadline_unix_seconds=self.deadline,
            resume=args.resume,root_reason=args.reason,single_cycle=args.single_cycle,scientific_dispatch_on_login=False))

    def event(self,kind,**fields):
        self.seq+=1
        return write(self.root/'events'/('event_%08d.json'%self.seq),dict(schema='SPRIME_CONTROLLER_IMMUTABLE_EVENT_V1',
            sequence=self.seq,unix_seconds=time.time(),kind=kind,launch_identity_reference=self.identity_ref,**fields))

    def budget(self):
        C.need(time.time()<self.deadline,'FINITE_CONTROLLER_DEADLINE_REACHED_NO_FURTHER_TRANSITION')
        total=0
        for path in self.root.rglob('*'):
            C.need(not path.is_symlink(),'NO_CONTROLLER_METADATA_SYMLINK')
            total+=path.stat().st_size
        C.need(total+(64<<20)<=CAP,'CONTROLLER8GIB_METADATA_CAP_STOP')

    def command(self,argv,label,max_wait=180):
        """No signal on a hung helper/query: retain intent, PID and HOLD."""
        self.budget();token=self.launch+'_'+str(self.seq+1)
        stdout=self.root/'commands'/(token+'.stdout');stderr=self.root/'commands'/(token+'.stderr')
        self.event('METADATA_COMMAND_INTENT',argv=argv,label=label)
        with stdout.open('xb') as out,stderr.open('xb') as err:
            inherited=() if getattr(self,'outer_submission_fd',None) is None else (self.outer_submission_fd,)
            child=subprocess.Popen(argv,cwd=REPO,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True,pass_fds=inherited)
        try:actual=process_identity(child.pid)
        except (OSError,ValueError) as exc:actual={'pid':child.pid,'proc_identity_unavailable':repr(exc),'identity_not_fabricated':True}
        self.event('ACTUAL_METADATA_CHILD',argv=argv,pid=child.pid,process=actual,stdout_path=str(stdout),stderr_path=str(stderr))
        until=min(self.deadline,time.time()+max_wait)
        while child.poll() is None and time.time()<until:time.sleep(.2)
        if child.poll() is None:
            self.event('METADATA_CHILD_UNRESOLVED_NO_SIGNAL_SENT',pid=child.pid,argv=argv)
            raise ValueError('HOLD_METADATA_CHILD_STILL_LIVE_NO_AUTOMATIC_REISSUE')
        out=read_small(stdout).decode();err=read_small(stderr).decode()
        self.event('METADATA_COMMAND_TERMINAL',argv=argv,returncode=child.returncode,stdout_reference=pin(stdout),stderr_reference=pin(stderr))
        C.need(child.returncode==0,'HOLD_METADATA_COMMAND_FAILED_NO_AUTOMATIC_RETRY:'+label+':'+err[-1000:])
        return out

    def sacct(self,ids,label):
        C.need(ids and all(str(j).isdecimal() for j in ids),'ONLY_ACTUAL_REGISTERED_JOB_IDS_QUERYABLE')
        argv=['sacct','-j',','.join(sorted(set(map(str,ids)))),'--parsable2','--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,UID']
        raw=self.command(argv,label,45);rows={}
        for row in csv.DictReader(io.StringIO(raw),delimiter='|'):
            jid=row.get('JobIDRaw','')
            if not jid.isdecimal():continue
            C.need(jid in set(map(str,ids)) and jid not in rows and row['UID']=='1278','EXACT_ACTUAL_MAIN_PARENT_ACCOUNTING_REQUIRED')
            rows[jid]=row
        C.need(set(rows)==set(map(str,ids)),'ACTUAL_PARENT_ACCOUNTING_NOT_YET_VISIBLE_HOLD')
        return argv,raw,rows

    def account(self,jid,key):
        argv,raw,rows=self.sacct([jid],'terminal_account_'+key);r=rows[str(jid)]
        C.need(r['State'].split()[0] in C.TERMINAL,'ACTUAL_TERMINAL_PARENT_REQUIRED')
        directory=self.root/'accounts'/key;directory.mkdir(exist_ok=False)
        raw_path=directory/'sacct.txt'
        with raw_path.open('xb') as stream:stream.write(raw.encode());stream.flush();os.fsync(stream.fileno())
        fsync_dir(directory)
        parent=dict(job_id=str(jid),state=r['State'].split()[0],exit_code=r['ExitCode'],alloc_cpus=int(r['AllocCPUS']),elapsed_raw_seconds=int(r['ElapsedRaw']),node=r['NodeList'])
        reference=write(directory/'accounting.json',dict(schema='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1',status='ACTUAL_PARENT_ACCOUNTING_CLOSED',
            query_returncode=0,endpoint='202.38.247.57:22',uid=1278,query_argv=argv,raw_sacct_reference=pin(raw_path),parents=[parent],
            allocated_core_seconds=parent['alloc_cpus']*parent['elapsed_raw_seconds'],actual_cost_is_point_in_time_not_final_pipeline=True))
        F.accounting(reference,[jid]);return reference

    def stage_paths(self,bid,stage):
        slot=self.slots[bid];name=slot['job_name'] if stage=='run' else 'dv1_q_sprime_v3_w2_ctl_b'+bid[6:]+'_'+stage+'_20261027_v1'
        phase='sprime_v3_w2_ctl_b'+bid[6:]+'_'+stage+'_20261027_v1'
        return name,phase,self.root/'stages'/bid/(stage+'_v1')

    def expected_argv(self,bid,stage,request):
        proof=request['startup_proof_path'];quota=self.manifest['quota_reuse_review_reference']['path'];config=self.manifest['config_reference']['path']
        prepared=G.WAVE2/bid/'prepared_mapping_v1/prepared.json'
        if stage=='prepare':return [PY,'-B',str(G.MAPPED/'prepare_batch.py'),'--config',config,'--plan',PLAN['path'],'--batch-id',bid,
            '--root-preflight',proof,'--quota-reuse-review',quota,'--source-mapping-review',self.manifest['mapping_review_reference']['path'],
            '--output',str(prepared.parent)]
        if stage=='run':return [PY,'-B',str(G.FORMAL/'run_batch.py'),'--config',config,'--prepared',str(prepared),
            '--root-preflight',proof,'--quota-reuse-review',quota,'--output',self.slots[bid]['output_root']]
        argv=request['execution_argv'];C.need('--descriptor' in argv,'ACTUAL_CLOSE_DESCRIPTOR_REQUIRED')
        descriptor_path=pathlib.Path(argv[argv.index('--descriptor')+1]);C.need(ROOT/'control' in descriptor_path.parents,'ONLY_ROOT_CONTROL_CLOSE_DESCRIPTOR')
        descriptor=load(descriptor_path)
        C.need(descriptor['plan']==PLAN and descriptor['prepared']==pin(prepared),'ACTUAL_CLOSE_PLAN_AND_PREPARED_BINDING')
        return [PY,'-B',str(self.repair.primary(bid)),'close','--config',config,'--root-preflight',proof,'--quota-reuse-review',quota,
            '--descriptor',str(descriptor_path),'--output',str(self.repair.output(bid))]

    def registration(self,bid,stage,entry):
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
        C.need(req['execution_argv']==self.expected_argv(bid,stage,req) and req['scope_key']=='sprime_formal_cpu_auto_v3_'+stage
            and req['scope_parameters']==F.scope(stage,self.manifest['config_reference']) and req['kind']==('conformer' if stage=='run' else 'analysis')
            and req['node']=='compute-0-13' and req['cpus']==16 and req['pilot'] is False and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
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
                C.need(report['batch_id']==bid and report['actual_parent_job_id']==s['run']['job_id'] and report['plan']==PLAN,
                    'ACTUAL_CLOSE_OUTPUT_CHAIN_MISMATCH')
                s['close']['report']=report;s['close']['report_reference']=pin(path)
        return stages

    def persist_terminal_costs(self,stages):
        for items in stages.values():
            for row in items.values():
                if not row.get('terminal'):continue
                parent=row['actual_parent'];signature=tuple(parent[k] for k in ('JobIDRaw','State','ExitCode','AllocCPUS','ElapsedRaw'))
                if signature in self.terminal_observations:continue
                reference=self.account(row['job_id'],'observed_'+row['job_id']+'_'+str(time.time_ns()))
                self.event('ACTUAL_TERMINAL_PARENT_COST_RETAINED',job_id=row['job_id'],accounting_reference=reference,
                    producer_state_not_upgraded_to_C0=parent['State'],point_in_time_cost_requires_final_owned_master_append=True)
                self.terminal_observations.add(signature)

    def owned_pending(self):
        raw=self.command(['squeue','-h','-u','zixiao','-o','%i|%j|%T'],'owned_registration_pending',45);count=0
        expected={s['job_name'] for s in self.slots.values()};adopted={load(e['request_reference']['path'])['job_name'] for e in self.entries.values()}
        for line in raw.splitlines():
            jid,name,state=line.split('|');rp=ROOT/'control/requests'/(name+'.json');sp=ROOT/'control/submissions'/(name+'.json')
            if state=='PENDING' and rp.exists() and sp.exists():
                sub=load(sp)
                if sub.get('uid')==1278 and str(sub.get('job_id'))==jid:count+=1
            if name in expected or name in adopted:
                C.need(rp.exists() and sp.exists(),'UNKNOWN_WAVE2_LIVE_JOB_REQUIRES_ROOT_REVIEW')
        return count

    def transition(self,bid,stage,stages):
        # The outer lock is distinct from activate's inner registration lock.
        # It covers the real capacity query and the entire unchanged stage
        # transition. No generation/account/submission intent precedes it.
        from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import query
        observed={}
        def read_node():
            argv=['scontrol','show','node','compute-0-13','--oneliner']
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
        self.budget();C.need(sources()==self.review['source_references'],'ROOT_REVIEWED_CONTROLLER_OR_HELPER_SOURCE_CHANGED')
        name,phase,directory=self.stage_paths(bid,stage)
        C.need(not directory.exists(),'EXISTING_STAGE_DIRECTORY_NO_AUTOMATIC_REGENERATION')
        intent=self.root/'intents'/(bid+'_'+stage+'.json');C.need(not intent.exists(),'EXISTING_TRANSITION_INTENT_NO_RETRY')
        previous='4521486' if stage=='prepare' else stages[bid]['prepare' if stage=='run' else 'run']['job_id']
        account_ref=self.account(previous,bid+'_'+stage)
        generator=[PY,'-B',str(G.HERE/'generate.py'),stage,'--output',str(directory),'--accounting',account_ref['path'],
            '--root-approve-exact-stage','--root-reason',self.args.reason,'--manifest',MANIFEST['path'],'--plan',PLAN['path'],'--batch-id',bid]
        if stage!='prepare':generator.extend(['--prepared',str(G.WAVE2/bid/'prepared_mapping_v1/prepared.json')])
        if stage=='close':
            reg=stages[bid]['run']['registration'];generator.extend(['--request',reg['request_reference']['path'],'--submission',reg['submission_reference']['path']])
        # A metadata-generation failure leaves its existing directory intact and
        # requires Root review; it is never regenerated over partial files.
        self.command(generator,'generate_'+bid+'_'+stage)
        spec_ref=pin(directory/'stage_spec.json');helper=[PY,'-B',str(HELPER),'--spec',spec_ref['path'],'--node','compute-0-13','--name',name,'--phase',phase]
        write(intent,dict(schema='SPRIME_CONTROLLER_SUBMISSION_INTENT_NO_REISSUE_V1',batch_id=bid,stage=stage,
            stage_spec_reference=spec_ref,helper_argv=helper,expected_name=name,expected_phase=phase,actual_job_id=None,
            launch_identity_reference=self.identity_ref,reason=self.args.reason))
        self.event('SUBMIT_INTENT_DURABLE',batch_id=bid,stage=stage,intent_reference=pin(intent))
        self.command(helper,'central_submit_'+bid+'_'+stage,240)
        self.event('HELPER_RETURNED_RECONCILE_ACTUAL_REGISTRATION_NEXT_CYCLE',batch_id=bid,stage=stage)

    def snapshot(self,status,stages,reason=None):
        compact={}
        for bid,items in stages.items():
            compact[bid]={}
            for stage,row in items.items():
                record={k:row[k] for k in ('job_id','job_name','terminal','state','exit_code','ambiguous','reason','report_reference') if k in row}
                if row.get('registration'):
                    record['actual_registered_references']=row['registration']
                if row.get('report'):
                    report=row['report'];record['closure_counts']={k:report[k] for k in ('valid_packets','execution_unresolved','unstarted_count','consumed_outcomes')}
                    record['closure_errors_count']=len(report['errors']);record['consumed_elsewhere_count']=len(report['consumed_elsewhere'])
                compact[bid][stage]=record
        self.cycle+=1;value=dict(schema='FINITE_SPRIME_WAVE2_CONTROLLER_STATE_V1',status=status,reason=reason,
            review_reference=self.review_ref,adoption_reference=self.review['adoption_reference'],manifest_reference=MANIFEST,plan_reference=PLAN,
            launch_identity_reference=self.identity_ref,cycle=self.cycle,unix_seconds=time.time(),deadline_unix_seconds=self.deadline,
            stages=compact,automatic_retry=False,source_population_release=False,common_frozen=False,scientific_quality_release=False)
        reference=write(self.root/'states'/(self.launch+'_%06d.json'%self.cycle),value)
        temp=self.root/('latest_'+self.launch+'_'+str(self.cycle)+'.json');write(temp,{'state_reference':reference})
        os.replace(temp,self.root/'latest.json');fsync_dir(self.root);return reference

    def run(self):
        stages={};self.event('FINITE_CONTROLLER_STARTED',adoption_reference=self.review['adoption_reference'],repair_map_reference=self.repair.reference,failed_metadata_parent=self.repair.failed,replacement_metadata_parent=self.repair.parent,old_failure_cost_retained=True)
        while time.time()<self.deadline:
            try:
                self.budget();stages=self.discover();self.persist_terminal_costs(stages);pending=self.owned_pending()
                decisions={bid:C.next_stage(s) for bid,s in stages.items()};holds={b:r for b,r in decisions.items() if r['action']=='HOLD'}
                if holds:
                    ref=self.snapshot('HOLD_ROOT_REVIEW_REQUIRED_NO_NEW_DISPATCH',stages,holds);print(json.dumps({'status':'HOLD','state':ref}));return 3
                if all(r['action']=='DONE' for r in decisions.values()):
                    ref=self.snapshot('ALL179_INITIAL_BATCHES_CLOSED_NOT_GLOBAL_QUALITY_RELEASE',stages);print(json.dumps({'status':'INITIAL179_CLOSED','state':ref}));return 0
                sci=sum(not r.get('terminal') for s in stages.values() for k,r in s.items() if k=='run')
                aux=sum(not r.get('terminal') for s in stages.values() for k,r in s.items() if k!='run')
                candidates=[dict(batch_id=b,stage=r['action']) for b,r in decisions.items() if r['action'] in C.STAGES
                    and C.capacity(r['action'],nonterminal_science=sci,nonterminal_aux=aux,owned_run_pending=pending)]
                selected=C.choose(candidates);self.snapshot('OBSERVED_BOUNDED_NEXT_TRANSITION' if selected else 'WAIT_EXISTING_JOBS_OR_CAPACITY',stages,selected)
                if selected and not self.args.observe_only:self.transition(selected['batch_id'],selected['stage'],stages)
                if self.args.single_cycle:return 0
                time.sleep(min(self.args.poll_seconds,max(0,self.deadline-time.time())))
            except Exception as exc:
                ref=self.snapshot('HOLD_ROOT_REVIEW_REQUIRED_NO_NEW_DISPATCH',stages,repr(exc));print(json.dumps({'status':'HOLD','error':repr(exc),'state':ref}));return 3
        self.snapshot('FINITE_CONTROLLER_LEASE_ENDED_NO_SIGNALS_OR_RENEWAL',stages);return 0


def main():
    on_login();p=argparse.ArgumentParser(description=__doc__);p.add_argument('--print-review-inputs',action='store_true')
    p.add_argument('--adoption',type=pathlib.Path,required=True);p.add_argument('--review',type=pathlib.Path)
    p.add_argument('--repair-map',type=pathlib.Path,required=True)
    p.add_argument('--state-root',type=pathlib.Path);p.add_argument('--root-run-reviewed-wave2',action='store_true');p.add_argument('--reason',default='')
    p.add_argument('--single-cycle',action='store_true');p.add_argument('--resume',action='store_true')
    p.add_argument('--observe-only',action='store_true',help='Metadata/accounting observation only; never generate/submit a new stage.')
    p.add_argument('--max-seconds',type=int,default=3600);p.add_argument('--poll-seconds',type=int,default=15);args=p.parse_args()
    C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==HERE/'controller.py'
        and process_identity(os.getpid())['argv']==[PY,'-B',str(HERE/'controller.py'),*sys.argv[1:]],
        'ACTUAL_PRIMARY_AND_COMPLETE_CONTROLLER_ARGV_REQUIRED')
    if args.print_review_inputs:
        value=review_inputs(args.adoption);repair_map=load(args.repair_map)
        value.update(repair_map_reference=pin(args.repair_map),repair_original_hold_reference=repair_map['resume_state_reference'],
            required_new_pure_capacity_test_count=4,**CG.recovery_inputs(pin,load,ROOT))
        print(json.dumps(value,indent=2));return 0
    C.need(args.root_run_reviewed_wave2 and args.reason.strip() and args.review and args.state_root,'EXPLICIT_ROOT_REVIEWED_FINITE_CONTROLLER_LAUNCH_REQUIRED')
    review=load(args.review);manifest,plan,identity_ref,identity=fixed_inputs()
    C.need(review['schema']=='ROOT_FINITE_SPRIME_WAVE2_CONTROLLER_REVIEW_V3' and review['status']=='APPROVED_FINITE_METADATA_CONTROLLER'
        and review['reviewer']=='root' and review['endpoint']=='202.38.247.57:22' and review['uid']==1278
        and review['manifest_reference']==MANIFEST and review['plan_reference']==PLAN and review['adoption_reference']==pin(args.adoption)
        and review['repair_map_reference']==pin(args.repair_map)
        and review['source_references']==sources() and review['publisher_identity_reference']==identity_ref
        and review['maximum_nonterminal_science']==2 and review['maximum_nonterminal_aux']==1 and review['maximum_owned_data_run_pending']==4
        and review['stop_before_publisher_expiry_seconds']==300 and 1<=args.max_seconds<=review['maximum_seconds']<=86400
        and 5<=args.poll_seconds<=30,'EXACT_ROOT_CONTROLLER_SOURCE_SCOPE_LIMITS_REVIEW_REQUIRED')
    recovery=CG.recovery_inputs(pin,load,ROOT)
    C.need(all(review.get(k)==v for k,v in recovery.items()),'EXACT_ACTUAL59_MANUAL_RECOVERY_AND_RESOURCE_GATE_BINDING')
    previous_tests=load(recovery['prior_state_repair_cpu_test_reference']['path'])
    C.need(pin(recovery['prior_state_repair_cpu_test_reference']['path'])==recovery['prior_state_repair_cpu_test_reference']
        and previous_tests['status']=='PASS' and previous_tests['tests_run']==12 and previous_tests['failures']==previous_tests['errors']==0
        and previous_tests['source_references']==[pin(HERE.parent/'sprime_wave2_controller_v2'/n) for n in ('__init__.py','contract.py','controller.py','repair.py','test_state.py','test_repair.py','README.md')],
        'EXISTING_ACTUAL_TWELVE_UNCHANGED_V2_STATE_REPAIR_TESTS_NOT_RERUN_OR_RELABELED')
    prior_jid=str(previous_tests['job_id']);prior_parent=F.accounting(previous_tests['accounting_reference'],[prior_jid])[prior_jid]
    C.need(prior_parent['state']=='COMPLETED' and prior_parent['exit_code']=='0:0' and int(prior_parent['alloc_cpus'])==16,'ACTUAL_PRIOR_CPU_TEST_C0')
    tests=load(review['pure_state_cpu_test_reference']['path'])
    C.need(pin(review['pure_state_cpu_test_reference']['path'])==review['pure_state_cpu_test_reference'] and tests['status']=='PASS'
        and tests['tests_run']==4 and tests['failures']==0 and tests['errors']==0 and tests['source_references']==[pin(HERE/n) for n in FILES],
        'ACTUAL_CPU_FOUR_NEW_PURE_CAPACITY_TESTS_WITH_EXACT_SOURCE_PINS_REQUIRED')
    test_jid=str(tests['job_id']);test_account=load(tests['accounting_reference']['path'])
    C.need(test_jid.isdecimal() and test_account['endpoint']=='202.38.247.57:22' and test_account['uid']==1278,'ACTUAL_MAIN_CPU_TEST_ACCOUNTING_REQUIRED')
    test_parents=F.accounting(tests['accounting_reference'],[test_jid]);test_parent=test_parents[test_jid]
    C.need(test_parent['state']=='COMPLETED' and test_parent['exit_code']=='0:0' and int(test_parent['alloc_cpus'])==16,'ACTUAL_CPU_TEST_PARENT_C0_REQUIRED')
    root=args.state_root;C.need(BASE in root.parents and '..' not in root.parts and not any(x.is_symlink() for x in (root,*root.parents)),'NEW_OR_RESUMED_OWN_CONTROLLER_CONTROL_DIRECTORY')
    if args.resume:
        previous=load(load(root/'latest.json')['state_reference']['path'])
        C.need(previous['manifest_reference']==MANIFEST and previous['plan_reference']==PLAN,'SAME_FROZEN_POPULATION_ON_RESUME')
        if previous['review_reference']!=pin(args.review):C.need(review.get('supersedes_review_reference')==previous['review_reference']
            and review.get('resume_from_state_reference')==load(root/'latest.json')['state_reference'],'NEW_ROOT_REVIEW_MUST_BIND_EXACT_PRIOR_HOLD')
        elif previous['status'].startswith('HOLD'):raise ValueError('HOLD_NEEDS_NEW_INDEPENDENT_ROOT_REVIEW_NOT_ELAPSED_TIME')
    else:C.need(not root.exists(),'EXISTING_STATE_REQUIRES_EXPLICIT_RESUME');root.mkdir(parents=True,mode=0o700)
    for name in ('events','states','launches','commands','accounts','stages','intents'):(root/name).mkdir(exist_ok=args.resume)
    lock=BASE/'wave2_single_instance.lock';BASE.mkdir(parents=True,exist_ok=True)
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(fd);C.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and info.st_nlink==1,'OWN_SINGLE_INSTANCE_LOCK')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return Controller(args,review,manifest,plan,identity_ref,identity).run()
    finally:os.close(fd)


if __name__=='__main__':raise SystemExit(main())
