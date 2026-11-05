"""Opt-in Root submission and worker admission. Importing this file performs no work."""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import socket
import subprocess
import sys
import time

import abba_contract as c

OUT=c.BASE/'runs/model_v3_20261026/A01_4090_ABBA_outputs_v1'
SOURCE_NAMES={'abba_contract.py','admit_abba.py','A01_4090_ABBA_member_v1.sbatch',
    'test_abba_admission.py','README.md','protocol.json'}
ACCOUNT_COLUMNS='JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS'


class Observe:
    def __init__(self,path):
        self.path=Path(path); self.rows=[]
        with self.path.open('xb'): pass
    def add(self,row):
        raw=c.encoded(row); c.require(self.path.stat().st_size+len(raw)<=2<<20,'Observation journal exceeds2MiB')
        with self.path.open('ab') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        self.rows.append(row)
    def command(self,argv,*,check=True,env=None):
        started=time.time()
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,timeout=45,env=env)
        c.require(len(result.stdout)+len(result.stderr)<=256<<10,'Raw command observation exceeds256KiB')
        row={'argv':argv,'captured_unix':started,'completed_unix':time.time(),'returncode':result.returncode,
            'stdout':result.stdout.decode('utf-8'),'stderr':result.stderr.decode('utf-8')}
        self.add(row)
        if check: c.require(result.returncode==0,'Actual observation failed: '+shlex.join(argv))
        return row


def backend_unavailable(row):
    if row['returncode']==0: return False
    text=(row['stderr']+row['stdout']).lower()
    return any(token in text for token in ('connection refused','unable to contact slurm controller',
        'unable to contact slurmctld','socket timed out','slurm_persist_conn_open',
        'problem talking to the database','slurm_load_node error: unable','slurm_load_jobs error: unable'))


class WorkerObserve:
    """Only failed Slurm transports may reuse the exact fresh Root observation."""
    def __init__(self,own,submitted): self.own,self.submitted=own,submitted
    def command(self,argv,*,check=True,env=None):
        row=self.own.command(argv,check=False,env=env)
        if row['returncode']==0 or not check: return row
        c.require(argv[0] in ('sacct','scontrol','squeue') and backend_unavailable(row),
            'Worker observation failed semantically; no Root substitute permitted')
        matches=[item for item in self.submitted['observations'] if item['argv']==argv]
        c.require(len(matches)==1,'Unique matching successful Root raw observation required')
        c.fresh(matches[0]); reused={**matches[0],'reused_Root_observation':True,'worker_transport_failure':row}
        self.own.add(reused); return reused


def source_pins(digest):
    source_ref=c.ref(c.HERE/'source_pins_v1.json'); c.require(source_ref['sha256']==digest,'Launcher source-pins SHA differs')
    pins=c.read(source_ref)
    c.require(pins['schema']=='model_v3_A01_4090_ABBA_sources_v1' and len(pins['files'])==len(SOURCE_NAMES)
        and {Path(row['path']).name for row in pins['files']}==SOURCE_NAMES,'Complete new source inventory required')
    for row in pins['files']:
        c.require(Path(row['path']).parent==c.HERE,'New source path differs'); c.bind(row)
    protocol=c.read(c.ref(c.HERE/'protocol.json'))
    c.require(protocol['schema']=='model_v3_A01_4090_ABBA_protocol_v1' and protocol['series_id']==c.SERIES
        and protocol['order']==list(c.ORDER) and protocol['source_code_sha']==c.CODE
        and protocol['candidate_options_sha256']==c.OPTIONS_SHA and protocol['gpu_uuid']==c.GPU
        and protocol['node']==c.NODE and protocol['job_wall_seconds']==c.JOB_WALL
        and protocol['requested_memory_MiB']==c.MEMORY_MIB and protocol['requested_cpus']==16
        and protocol['supervisor_wall_seconds']==c.SUPERVISOR_WALL and protocol['rss_limit_bytes']==c.RSS_LIMIT
        and protocol['output_budget_bytes_per_member']==c.OUTPUT_BUDGET
        and protocol['private_budget_bytes_per_member']==c.PRIVATE_BUDGET
        and protocol['warmup_updates']==2 and protocol['measured_updates']==20 and protocol['seed']==0
        and protocol['maximum_submitted_members']==4 and protocol['maximum_admission_attempts']==12,
        'Exact preregistered source/hardware/resource policy required')
    return pins,protocol,source_ref


def verify_gate(protocol,observer):
    """Rehash metadata/support sources, never load/checkpoint-decode weights or labels."""
    values={name:c.read(row) for name,row in protocol['numeric_gate_metadata'].items()}
    receipt=c.numeric_gate(values); config=values['configuration']; source_refs=[]
    provenance,ready=values['provenance'],values['ready']
    c.require(ready['provenance']==protocol['numeric_gate_metadata']['provenance']
        and provenance['gate_and_raw_configuration_files']['configuration']==protocol['numeric_gate_metadata']['configuration'],
        'Original READY/provenance raw metadata binding differs')
    raw_refs=list(provenance['gate_and_raw_configuration_files'].values())+[ready['a_run_configuration']]
    for row in raw_refs: c.bind(row)  # Bounded opaque metadata/history hashing only; no label or weight decoder.
    for name,digest in config['source_sha256'].items():
        c.require(not Path(name).is_absolute() and '..' not in Path(name).parts,'Relative frozen source required')
        row=c.ref(c.REPO/name); c.require(row['sha256']==digest,'Original runtime source bytes changed'); source_refs.append(row)
    options=c.ref(c.REPO/'current/configs/model_v3/performance/a01_backbone_off.json')
    c.require(options['sha256']==c.OPTIONS_SHA,'Original A01 candidate options bytes changed')
    for declared in (config['reference_configuration'],config['a4_configuration']):
        actual=c.ref(declared['path']); c.require(actual['sha256']==declared['sha256'],'Original reference configuration bytes changed')
        source_refs.append(actual)
    c.require(observer.command([str(c.GIT),'-C',str(c.REPO),'rev-parse','HEAD'])['stdout'].strip()==c.CODE,
        'Frozen source Git HEAD differs')
    c.require(observer.command([str(c.GIT),'-C',str(c.REPO),'status','--porcelain=v1','--untracked-files=normal'])['stdout']=='',
        'Frozen source tree must remain clean')
    sdk_refs=[]
    for run_id in protocol['numeric_source_offline_run_ids']:
        matches=list((c.GATE/'wandb').glob('offline-run-*/run-'+run_id+'.wandb'))
        c.require(len(matches)==1,'Unique original numeric SDK raw source required')
        sdk_refs.append(c.ref(matches[0],128<<20))
    receipt.update(source_files_rehashed=source_refs,options=options,numeric_original_SDK_raw_refs=sdk_refs,
        original_gate_history_raw_refs_rehashed=raw_refs,
        checkpoint_weights_opened=False,standalone_speed_inferred=False)
    return receipt,values


def publication(ref,observer,pins):
    value=c.read(ref)
    c.require(value['schema']=='model_v3_exact_tree_publication_receipt_v1' and value['branch']=='model-v3'
        and value['exact_tree_verified'] is True and value['published_head_readback_verified'] is True
        and value['main_modified'] is False and value['formal_pretraining_started'] is False,
        'Root exact-tree publication receipt required before GPU submission')
    for key in ('local_code_sha','github_commit_sha','tree_sha'):
        c.require(re.fullmatch('[0-9a-f]{40}',value[key]),'Complete registration commit/tree required')
    local=value['local_code_sha']
    tree=observer.command([str(c.GIT),'-C',str(c.PUBLIC_REPO),'rev-parse',local+'^{tree}'])['stdout'].strip()
    c.require(tree==value['tree_sha'],'Actual registered local/public tree receipt differs')
    sources=pins['files']+[c.ref(c.HERE/'source_pins_v1.json')]
    for row in sources:
        name=Path(row['path']).name
        path=c.PROTOCOL_PATH if name=='protocol.json' else c.PUBLISHED_PREFIX+name
        raw=observer.command([str(c.GIT),'-C',str(c.PUBLIC_REPO),'show',local+':'+path])['stdout'].encode()
        c.require(raw==Path(row['path']).read_bytes(),'Published protocol/launcher bytes differ')
    return ref


def qa_receipt(ref,observer,pins):
    value=c.read(ref)
    c.require(value['schema']=='model_v3_A01_4090_ABBA_QA_closure_v1','Actual metadata QA closure required')
    unit=c.read(value['unit_result']); counts={'tests':52,'failures':0,'errors':0,'skipped':0}
    expected={row['path']:row['sha256'] for row in pins['files']}
    expected[str(c.HERE/'source_pins_v1.json')]=c.ref(c.HERE/'source_pins_v1.json')['sha256']
    c.require(unit['returncode']==0 and unit['counts']==counts and unit['sources_unchanged'] is True
        and unit['source_hashes_before']==unit['source_hashes_after']
        and all(unit['source_hashes_before'].get(path)==digest for path,digest in expected.items()),
        'Actual full52 metadata QA and exact unchanged source inventory required')
    account=accounting(observer,str(value['job_id']))
    return {'Root_QA_closure':ref,'unit_result':value['unit_result'],'actual_parent':account,'counts':counts}


def accounting(observer,job):
    row=observer.command(['sacct','-X','-n','-P','-j',job,'--format='+ACCOUNT_COLUMNS])
    return c.parent_c0(row['stdout'],job)


def prior_member(position,previous_ref,observer,pins_sha):
    if position==1:
        c.require(previous_ref is None,'Position1 must not borrow another series'); return None
    c.require(previous_ref is not None,'Previous immutable submitted member required')
    previous=c.read(previous_ref)
    c.require(previous['status']=='SUBMITTED' and previous['position']==position-1
        and previous['series_id']==c.SERIES and previous['source_pins_sha256']==pins_sha,
        'Previous source/series/position differs')
    job=previous['actual_job_id']; account=accounting(observer,job)
    root=Path(previous['benchmark_root'])
    files={key:c.ref(root/(key+'.json')) for key in ('summary','run_status','configuration')}
    sup_ref=c.ref(Path(previous['output_root'])/'supervisor.json'); sup=c.read(sup_ref)
    c.member_closed(position-1,*(c.read(files[key]) for key in ('summary','run_status','configuration')),sup,account)
    closure_ref=c.ref(root/'launcher_source_closure.json'); closure=c.read(closure_ref)
    c.require(closure['status']=='UNCHANGED_CHILD_EXIT0' and closure['child_returncode']==0
        and closure['source_sha256']==c.read(files['configuration'])['source_sha256'],
        'Previous launcher/source/child closure required')
    return {'submission':previous_ref,'job_id':job,'actual_parent':account,'files':files,
        'supervisor':sup_ref,'launcher_source_closure':closure_ref}


def observe_resources(observer,original_gpu,*,local=False,known_hosts=None,allocated=False):
    def node_command(argv):
        if local: return observer.command(argv)['stdout']
        c.require(known_hosts is not None,'Explicit strict compute-node known-hosts file required')
        c.bind(known_hosts)
        return observer.command(['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
            '-o','UserKnownHostsFile='+known_hosts['path'],c.NODE,shlex.join(argv)])['stdout']
    c.require(node_command(['hostname','-s']).strip()==c.NODE,'Actual node differs')
    controller=observer.command(['scontrol','show','node',c.NODE])
    queue=observer.command(['squeue','-h','-w',c.NODE,'-o','%i|%u|%t|%m|%C'])
    reused=controller.get('reused_Root_observation',False) or queue.get('reused_Root_observation',False)
    memory=c.node_memory(controller['stdout'],queue['stdout'],already_allocated=allocated and not reused)
    physical=c.physical_memory(node_command(['cat','/proc/meminfo']))
    gpu=c.gpu_idle(node_command(['nvidia-smi','--query-gpu=uuid,name,driver_version,memory.total,memory.free',
        '--format=csv,noheader,nounits']),node_command(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory',
        '--format=csv,noheader,nounits']),original_gpu)
    node_command(['flock','-n',str(c.LOCK),'/bin/true'])
    return {'controller':memory,'controller_scope':'fresh source-bound Root plus new request' if reused else 'live controller',
        'physical':physical,'GPU':gpu,
        'lock_semantics':'probe only; unchanged single_a_benchmark holds actual lifetime nonblocking public UUID lock'}


def own_allocation(raw_job,environ,cgroup,affinity):
    job=environ.get('SLURM_JOB_ID','')
    c.require(job.isdecimal() and environ.get('SLURM_CPUS_PER_TASK')=='16' and len(affinity)>=16
        and environ.get('CUDA_VISIBLE_DEVICES')==c.GPU and re.search(r'job_'+job+r'(?:/|\b)',cgroup),
        'Actual worker env/proc/cgroup/affinity/UUID differs')
    if raw_job is None:
        c.require(environ.get('SLURM_MEM_PER_NODE') in (None,'65536'),'Actual process memory environment contradicts Root64G request')
        return {'job_id':job,'allocated_memory_TRES_readback_claimed':False,'controller_readback':'transport unavailable',
            'requested_memory_from_exact_bound_Root_sbatch_MiB':c.MEMORY_MIB,'actual_process_binding_checked':True}
    c.require(re.search(r'\bJobId='+job+r'(?:\s|$)',raw_job) and re.search(r'\bNodeList='+c.NODE+r'(?:\s|$)',raw_job)
        and re.search(r'\bNumCPUs=16(?:\s|$)',raw_job),'Actual controller job/CPU/node differs')
    memory=[]
    for field in ('AllocTRES','ReqTRES','TRES'):
        groups=re.findall(r'\b'+field+r'=([^\s]+)',raw_job)
        c.require(len(groups)<=1,'Ambiguous controller TRES')
        if groups:
            values=dict(piece.split('=',1) for piece in groups[0].split(',') if '=' in piece)
            if 'cpu' in values: c.require(values['cpu']=='16','Actual controller TRES CPU differs')
            if 'mem' in values:
                c.require(c.memory_mib(values['mem'],16)==c.MEMORY_MIB,'Actual controller TRES memory differs'); memory.append(field)
    minimum=re.findall(r'\bMinMemoryNode=([^\s]+)',raw_job)
    if minimum: c.require(len(minimum)==1 and c.memory_mib(minimum[0],16)==c.MEMORY_MIB,'Actual minimum node memory differs')
    c.require(memory or minimum,'Actual controller memory proof absent')
    return {'job_id':job,'allocated_memory_TRES_readback_claimed':'AllocTRES' in memory,
        'controller_memory_fields':memory,'MinMemoryNode':minimum,'actual_process_binding_checked':True}


def validate_submission(value,position,nonce,pins_sha,job):
    root=OUT/('position'+str(position)+'_'+nonce)
    expected=['sbatch','--parsable','--partition=all','--nodelist='+c.NODE,'--cpus-per-task=16',
        '--mem=64G','--time=00:20:00','--output='+str(root/'slurm.log'),str(c.HERE/'A01_4090_ABBA_member_v1.sbatch')]
    c.require(value['schema']=='model_v3_A01_4090_ABBA_submission_v1' and value['status']=='SUBMITTED'
        and value['actual_job_id']==job and value['nonce']==nonce and value['source_pins_sha256']==pins_sha
        and value['position']==position and value['series_id']==c.SERIES and value['root_uid']==1278
        and not value['root_hostname'].startswith('compute-') and value['submission']['returncode']==0
        and value['submission']['argv']==expected and value['submission']['stdout'].strip().split(';')[0]==job
        and value['output_root']==str(root) and value['benchmark_root']==str(root/'benchmark'),
        'Root actual sbatch/source/nonce/position/output binding differs')


def wait_root_record(path,timeout=30):
    deadline=time.monotonic()+timeout
    while True:
        try:
            row=c.ref(path); value=c.read(row)
            if value.get('status')=='SUBMITTED': return row,value
        except (FileNotFoundError,json.JSONDecodeError): pass
        c.require(time.monotonic()<deadline,'Root actual submission receipt did not close in bounded30s')
        time.sleep(.25)


def worker(args,pins,protocol):
    c.require(socket.gethostname()==c.NODE and os.getuid()==1278,'Worker must run on actual owned node20')
    submission_ref,submitted=wait_root_record(args.record)
    if args.record_sha256: c.require(submission_ref['sha256']==args.record_sha256,'Root submission raw SHA differs')
    job=os.environ.get('SLURM_JOB_ID',''); validate_submission(submitted,args.position,args.nonce,args.source_pins_sha256,job)
    family=Path(submitted['output_root']); observer=Observe(family/'worker.observations.jsonl')
    q=submitted['quota_raw']; c.fresh(q); c.quota(q['stdout'])
    own_row=observer.command(['scontrol','show','job',job],check=False)
    c.require(own_row['returncode']==0 or backend_unavailable(own_row),'Worker own-job controller failed semantically')
    proof=own_allocation(own_row['stdout'] if own_row['returncode']==0 else None,os.environ,
        Path('/proc/self/cgroup').read_text(),os.sched_getaffinity(0))
    observer=WorkerObserve(observer,submitted)
    publication(submitted['publication'],observer,pins)
    qa_receipt(submitted['QA']['Root_QA_closure'],observer,pins)
    gate,values=verify_gate(protocol,observer)
    resources=observe_resources(observer,values['configuration']['gpu'],local=True,allocated=True)
    c.fresh(q)
    root=Path(submitted['benchmark_root']); c.require(not root.exists(),'Fresh standalone output required')
    command=[str(c.PYTHON),'-u','-B',str(c.REPO/'tools/model_v3/run_supervised.py'),
        '--output-root',str(family),'--record',str(family/'supervisor.json'),'--gpu-uuid',c.GPU,
        '--wall-seconds',str(c.SUPERVISOR_WALL),'--rss-limit-bytes',str(c.RSS_LIMIT),
        '--output-budget-bytes',str(c.OUTPUT_BUDGET),'--private-scratch-root','/tmp/mv3n_'+job,
        '--private-storage-budget-bytes',str(c.PRIVATE_BUDGET),'--',str(c.PYTHON),'-u','-B',
        str(c.REPO/'tools/model_v3/single_a_benchmark.py'),'--candidate-options',
        str(c.REPO/'current/configs/model_v3/performance/a01_backbone_off.json'),'--input','native_s','--workers','8',
        '--seed','0','--max-padded-cost','8000000','--expected-gpu','4090','--code-sha',c.CODE,
        '--prereg-sha',c.PREREG,'--shard-snapshot-sha256',values['configuration']['original_shard_snapshot_prejob_sha256'],
        '--deterministic-controls','--output',str(root),'--role',c.ORDER[args.position-1],
        '--abba-position',str(args.position),'--series-id',c.SERIES]
    c.save(family/'prelaunch.json',{'status':'PRELAUNCH_ADMITTED','job_id':job,'submission':submission_ref,
        'position':args.position,'quota_scope':'fresh byte-bound Root login quota; worker quota not claimed',
        'own_allocation':proof,'resources':resources,'numeric_gate':gate,'source_pins_sha256':args.source_pins_sha256})
    result=subprocess.run(command,stdin=subprocess.DEVNULL,cwd=c.REPO)
    changed=[]
    for name,digest in values['configuration']['source_sha256'].items():
        if c.ref(c.REPO/name)['sha256']!=digest: changed.append(name)
    for row in pins['files']: c.bind(row)
    if root.is_dir():
        closure={'status':'UNCHANGED_CHILD_EXIT0' if result.returncode==0 and not changed else 'FAILED_OR_CHANGED',
            'child_returncode':result.returncode,'changed_sources':changed,'source_sha256':values['configuration']['source_sha256'],
            'actual_outer_Slurm_C0_not_asserted_by_child':True,'supervisor_command':command}
        monitor_path=c.REPO/'tools/model_v3/runtime_monitor.py'
        spec=importlib.util.spec_from_file_location('A01_frozen_output_census',monitor_path)
        monitor=importlib.util.module_from_spec(spec); sys.modules[spec.name]=monitor; spec.loader.exec_module(monitor)
        c.require(monitor.owned_output_bytes(family)+len(c.encoded(closure))<=c.OUTPUT_BUDGET,
            'Whole member output including Slurm/SDK/guard/closure exceeds2GiB')
        c.save(root/'launcher_source_closure.json',closure)
        c.require(monitor.owned_output_bytes(family)<=c.OUTPUT_BUDGET,'Final whole member output exceeds2GiB')
    c.require(result.returncode==0 and not changed,'Standalone child failed or actual source bytes changed')
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('mode',choices=('submit','worker'))
    parser.add_argument('--position',type=int,choices=(1,2,3,4),required=True)
    parser.add_argument('--source-pins-sha256',required=True); parser.add_argument('--record',type=Path,required=True)
    parser.add_argument('--record-sha256'); parser.add_argument('--nonce'); parser.add_argument('--publication',type=Path)
    parser.add_argument('--publication-sha256'); parser.add_argument('--known-hosts',type=Path)
    parser.add_argument('--qa',type=Path); parser.add_argument('--qa-sha256')
    parser.add_argument('--previous-submission',type=Path); parser.add_argument('--previous-sha256'); args=parser.parse_args(argv)
    sys.dont_write_bytecode=True; pins,protocol,pins_ref=source_pins(args.source_pins_sha256)
    OUT.mkdir(exist_ok=True)
    if args.mode=='worker':
        return worker(args,pins,protocol)
    c.require(os.getuid()==1278 and not socket.gethostname().startswith('compute-'),'Root login host is the only submitter')
    c.require(args.record.is_absolute() and args.record.parent==OUT and not args.record.exists(),'Fresh bounded attempt receipt in canonical output root required')
    with (OUT/'.series_admission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        management=list(OUT.iterdir())
        c.require(all(not path.is_symlink() and (path.is_dir() or path.is_file()) and path.stat().st_uid==os.getuid()
            for path in management),
            'Unknown management output object')
        directories=[path for path in management if path.is_dir()]
        c.require(len(directories)<=4 and all(re.fullmatch(r'position[1-4]_[0-9a-f]{32}',path.name) for path in directories),
            'Finite four-member owned output-root allowlist differs')
        c.require(sum(path.stat().st_size for path in management if path.is_file())<=60<<20,
            'Finite64MiB management budget lacks next bounded attempt reserve')
        c.require(len(list(OUT.glob('*.ATTEMPT.json')))<12,'Finite12 admission attempts exhausted; preserve history')
        c.save(args.record.with_name(args.record.name+'.ATTEMPT.json'),{'position':args.position,'started_unix':time.time(),'source_pins':pins_ref})
        observer=Observe(args.record.with_name(args.record.name+'.observations.jsonl'))
        status,failure,attempted,job='REJECTED',None,False,None; extra={}
        try:
            c.require(args.publication and args.publication_sha256 and args.known_hosts and args.qa and args.qa_sha256,
                'Registered source/actual metadata QA/strict host evidence required')
            pub=c.ref(args.publication); c.require(pub['sha256']==args.publication_sha256,'Publication raw SHA differs')
            publication(pub,observer,pins)
            qa_ref=c.ref(args.qa); c.require(qa_ref['sha256']==args.qa_sha256,'Actual QA closure raw SHA differs')
            QA=qa_receipt(qa_ref,observer,pins); gate,values=verify_gate(protocol,observer)
            source_parent=accounting(observer,'4520456'); c.supervisor_closed(c.read(protocol['numeric_supervisor']),'4520456')
            previous=None
            if args.previous_submission:
                previous=c.ref(args.previous_submission); c.require(previous['sha256']==args.previous_sha256,'Previous raw submission SHA differs')
            prior=prior_member(args.position,previous,observer,args.source_pins_sha256)
            resources=observe_resources(observer,values['configuration']['gpu'],known_hosts=c.ref(args.known_hosts))
            quota_raw=observer.command(['quota','-v','-u','zixiao']); c.fresh(quota_raw); quota=c.quota(quota_raw['stdout'])
            for observation in observer.rows[-8:]: c.fresh(observation)
            intent=OUT/('position'+str(args.position)+'.SUBMISSION_INTENT.json')
            c.require(not intent.exists(),'Submitted/ambiguous position intent cannot be replayed or reset')
            nonce=secrets.token_hex(16); script=c.ref(c.HERE/'A01_4090_ABBA_member_v1.sbatch')
            family=OUT/('position'+str(args.position)+'_'+nonce); family.mkdir()
            env={**os.environ,'MODEL_V3_ABBA_SOURCE_PINS_SHA':args.source_pins_sha256,
                'MODEL_V3_ABBA_RECORD':str(args.record),'MODEL_V3_ABBA_POSITION':str(args.position),'MODEL_V3_ABBA_NONCE':nonce}
            submission_argv=['sbatch','--parsable','--partition=all','--nodelist='+c.NODE,'--cpus-per-task=16',
                '--mem=64G','--time=00:20:00','--output='+str(family/'slurm.log'),script['path']]
            c.save(intent,{'position':args.position,'nonce':nonce,'record':str(args.record),'script':script,'argv':submission_argv})
            attempted=True; actual=observer.command(submission_argv,check=False,env=env)
            token=actual['stdout'].strip().split(';')[0]; job=token if re.fullmatch('[1-9][0-9]*',token) else None
            extra={'nonce':nonce,'publication':pub,'QA':QA,'numeric_gate':gate,'numeric_parent':source_parent,'previous':prior,
                'resources':resources,'quota_raw':quota_raw,'quota':quota,'script':script,'submission':actual,
                'output_root':str(family),'benchmark_root':str(family/'benchmark'),'actual_job_id':job}
            c.require(actual['returncode']==0 and job is not None,'Ambiguous/failed sbatch; retain intent and inspect, never auto-retry')
            status='SUBMITTED'
        except BaseException as exc:
            failure={'type':type(exc).__name__,'message':str(exc)}
            if attempted: status='SUBMISSION_UNCONFIRMED'
            raise
        finally:
            c.save(args.record,{'schema':'model_v3_A01_4090_ABBA_submission_v1','status':status,'failure':failure,
                'position':args.position,'series_id':c.SERIES,'source_pins_sha256':args.source_pins_sha256,
                'sbatch_attempted':attempted,'root_uid':os.getuid(),'root_hostname':socket.gethostname(),
                'observations':observer.rows,**extra})
        print(json.dumps({'status':status,'job_id':job,'receipt':str(args.record)})); return 0


if __name__=='__main__': raise SystemExit(main())
