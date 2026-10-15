"""C3 k=24 native node probe, exact-job process memory and scratch observations.

Only Root submits. Work repeats within one node's deterministic molecule bucket
for 1--2 h; buckets across nodes never overlap. This is an authorized engineering
remeasurement, not another formal pilot or any change to source LMDB.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
HERE=Path(__file__).absolute().parent
PAGE=os.sysconf('SC_PAGE_SIZE')
HZ=os.sysconf('SC_CLK_TCK')

def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1<<20),b''):value.update(block)
    return value.hexdigest()

def save(path,value):
    pending=Path(str(path)+'.pending')
    pending.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    pending.replace(path)

def proc(pid):
    base=Path('/proc')/str(pid)
    try:
        if base.stat().st_uid!=os.getuid():return None
        text=(base/'stat').read_text(); end=text.rfind(')'); fields=text[end+2:].split()
        return {'pid':pid,'uid':os.getuid(),'comm':text[text.find('(')+1:end],
            'state':fields[0],'ppid':int(fields[1]),'start_ticks':int(fields[19]),
            'rss_bytes':max(0,int(fields[21]))*PAGE,
            'cpu_ticks':int(fields[11])+int(fields[12]),
            'blkio_delay_ticks':int(fields[39]) if len(fields)>39 else None,
            'cgroups':(base/'cgroup').read_text()}
    except (FileNotFoundError,ProcessLookupError,PermissionError,ValueError):return None

def job_scoped(groups,job):
    return any(re.search(r'(?:^|/)(?:job_|job)'+re.escape(job)+r'(?:/|$)',line.split(':',2)[-1]) for line in groups.splitlines())

def same_identity(left,right):
    return right is not None and all(left[key]==right[key] for key in ('pid','uid','start_ticks','cgroups'))

def scoped_memory(groups,job):
    measurements={}
    for line in groups.splitlines():
        parts=line.split(':',2)
        if len(parts)!=3 or not job_scoped(line,job):continue
        hierarchy,controllers,relative=parts
        directory=Path('/sys/fs/cgroup')/relative.lstrip('/') if hierarchy=='0' else Path('/sys/fs/cgroup/memory')/relative.lstrip('/')
        if hierarchy!='0' and 'memory' not in controllers.split(','):continue
        names=('memory.current','memory.peak') if hierarchy=='0' else ('memory.usage_in_bytes','memory.max_usage_in_bytes')
        for name in names:
            try:measurements[str(directory/name)]=int((directory/name).read_text().strip())
            except (OSError,ValueError):measurements[str(directory/name)]=None
    return measurements

def sample_job(root_identity,job,last_io,cumulative):
    candidates={}
    for directory in Path('/proc').iterdir():
        if directory.name.isdigit():
            item=proc(int(directory.name))
            if item is not None:candidates[item['pid']]=item
    root=candidates.get(root_identity['pid'])
    if not same_identity(root_identity,root):return {'root_identity_verified':False}
    isolated=job_scoped(root['cgroups'],job)
    if isolated:
        included={pid for pid,item in candidates.items() if job_scoped(item['cgroups'],job)}
        scope='SAME_UID_EXACT_SLURM_JOB_CGROUP'
    else:
        included={root['pid']}
        while True:
            added={pid for pid,item in candidates.items() if item['ppid'] in included and item['start_ticks']>=root['start_ticks']}
            if added<=included:break
            included|=added
        scope='SAME_UID_VERIFIED_ROOT_PROCESS_TREE_CGROUP_NOT_ISOLATED'
    rss=pss=0; pss_missing=0; identities=[]; cpu=delay=0
    for pid in sorted(included):
        item=candidates[pid]
        if item['state']=='Z':continue
        observed_pss=None; io={}
        try:
            match=re.search(r'^Pss:\s+(\d+)\s+kB$',(Path('/proc')/str(pid)/'smaps_rollup').read_text(),re.M)
            if match:observed_pss=int(match.group(1))*1024
        except (OSError,ValueError):pass
        try:
            for line in (Path('/proc')/str(pid)/'io').read_text().splitlines():
                key,value=line.split(':',1);io[key]=int(value.strip())
        except (OSError,ValueError):pass
        if not same_identity(item,proc(pid)):continue
        rss+=item['rss_bytes'];cpu+=item['cpu_ticks'];delay+=item['blkio_delay_ticks'] or 0
        if observed_pss is None:pss_missing+=1
        else:pss+=observed_pss
        identity=(pid,item['start_ticks'])
        previous=last_io.get(identity,{})
        for key in ('read_bytes','write_bytes','rchar','wchar'):
            if key in io:cumulative[key]=cumulative.get(key,0)+max(0,io[key]-previous.get(key,0))
        last_io[identity]=io
        identities.append({key:item[key] for key in ('pid','ppid','comm','start_ticks','rss_bytes')})
    return {'root_identity_verified':True,'process_scope':scope,'processes':identities,
        'total_concurrent_RSS_bytes':rss,'total_concurrent_PSS_bytes':pss if not pss_missing else None,
        'known_PSS_bytes':pss,'PSS_unavailable_processes':pss_missing,
        'active_processes':len(identities),'current_cpu_seconds':cpu/HZ,'current_blkio_delay_seconds':delay/HZ,
        'sampled_cumulative_own_process_io':dict(cumulative),'exact_job_cgroup_memory':scoped_memory(root['cgroups'],job)}

class Sampler:
    def __init__(self,path,job,interval):
        self.path=path;self.job=job;self.interval=interval;self.stop=threading.Event()
        self.root=proc(os.getpid());self.samples=0;self.max_rss=0;self.max_pss=None
        self.max_processes=0;self.max_python_children=0;self.io={};self.missing_pss_samples=0;self.scope=None
        self.last={};self.memory={};self.start=time.monotonic()
        self.thread=threading.Thread(target=self.loop,name='owned_job_sampler',daemon=True)
    def loop(self):
        with self.path.open('w') as stream:
            while not self.stop.is_set():
                value=sample_job(self.root,self.job,self.last,self.io)
                value['elapsed_seconds']=time.monotonic()-self.start
                self.samples+=1;self.scope=value.get('process_scope',self.scope)
                self.max_rss=max(self.max_rss,value.get('total_concurrent_RSS_bytes',0))
                measured=value.get('total_concurrent_PSS_bytes')
                if measured is not None:self.max_pss=max(self.max_pss or 0,measured)
                else:self.missing_pss_samples+=1
                self.max_processes=max(self.max_processes,value.get('active_processes',0))
                # This includes engine/monitor Python and multiprocessing helpers;
                # it is a process observation, not the scientific worker count.
                self.max_python_children=max(self.max_python_children,sum('python' in item['comm'].lower() for item in value.get('processes',[])))
                for key,amount in value.get('exact_job_cgroup_memory',{}).items():
                    if amount is not None:self.memory[key]=max(self.memory.get(key,0),amount)
                stream.write(json.dumps(value,separators=(',',':'))+'\n');stream.flush()
                self.stop.wait(self.interval)
    def begin(self):self.thread.start()
    def finish(self):
        self.stop.set();self.thread.join(timeout=60)
        if self.thread.is_alive():raise RuntimeError('Owned sampler did not close')
        return {'sample_interval_seconds':self.interval,'samples':self.samples,'process_scope':self.scope,
            'observed_peak_concurrent_RSS_bytes':self.max_rss,'observed_peak_concurrent_PSS_bytes':self.max_pss,
            'PSS_unavailable_samples':self.missing_pss_samples,'observed_max_active_processes':self.max_processes,
            'observed_max_Python_processes':self.max_python_children,'sampled_cumulative_own_process_io':self.io,
            'exact_job_cgroup_peak_observations':self.memory or None,
            'sampling_limit':'Concurrent RSS/PSS observed every interval, not an unsampled mathematical peak. PSS adjusts shared pages; RSS may double-count shared mappings. IO of children exiting between samples can be missed; native byte totals are separate.',
            'sacct_MaxRSS':'Collected separately from actual sacct output; unavailable fields stay null. No two-times-single-process RSS heuristic used.'}

def scratch_probe(base):
    descriptor,name=tempfile.mkstemp(prefix='c3_own_io_'+os.environ['SLURM_JOB_ID']+'_',dir=base)
    path=Path(name);block=os.urandom(1<<20);amount=128*(1<<20)
    try:
        begin=time.monotonic()
        with os.fdopen(descriptor,'wb') as stream:
            for _ in range(128):stream.write(block)
            stream.flush();os.fsync(stream.fileno())
        write=time.monotonic()-begin;begin=time.monotonic();read=0
        with path.open('rb') as stream:
            for part in iter(lambda:stream.read(1<<20),b''):read+=len(part)
        elapsed=time.monotonic()-begin
        return {'bytes':amount,'write_fsync_seconds':write,'write_MiB_s':amount/(1<<20)/write,
            'read_seconds':elapsed,'read_MiB_s':read/(1<<20)/elapsed,
            'read_policy':'Immediate buffered re-read; page cache is present, not a cold disk bandwidth claim.'}
    finally:
        if path.exists() and path.lstat().st_uid==os.getuid():path.unlink()

def accounting(job):
    command=['sacct','-j',job,'--units=K','--parsable2','--noheader',
        '--format=JobIDRaw,State,ElapsedRaw,AllocCPUS,MaxRSS,MaxRSSNode,MaxRSSTask,TotalCPU,MaxDiskRead,MaxDiskWrite']
    try:
        result=subprocess.run(command,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=30)
        return {'argv':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
            'note':'In-job snapshot may be unavailable or unfinished. Root should obtain final sacct after closure; blank MaxRSS is not zero.'}
    except Exception as exc:return {'argv':command,'returncode':None,'error':str(exc),'MaxRSS':None}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design-node-index',dest='node_index',type=int)
    parser.add_argument('--actual-node-index',type=int)
    parser.add_argument('--runtime-seconds',type=int,default=5400)
    parser.add_argument('--sample-seconds',type=float,default=2);parser.add_argument('--output')
    parser.add_argument('--output-cap-bytes',type=int,default=12_000_000_000);parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.check:
        for path in (Path(__file__),HERE/'c_engineering_native_nopolar.py'):ast.parse(path.read_text())
        config=json.loads((HERE/'c_engineering_native_nopolar_config.json').read_text())
        task=next(item for item in config['tasks'] if item['name']=='pm7_B')
        assert 'POLAR(' not in task['keywords'] and 'static_polar_block' not in task['required_values'] and task['polar_enabled'] is False
        print(json.dumps({'status':'AST_AND_NOPOLAR_CONFIG_PASS','QM_started':False,'LMDB_opened':False}));return 0
    hostname=socket.gethostname().split('.')[0]
    actual=args.actual_node_index if args.actual_node_index is not None else args.node_index
    authorized={(14,14),(15,15),(15,12),(16,16),(16,13),(17,17),(18,18),(19,19)}
    if (args.node_index,actual) not in authorized or hostname!=f'compute-0-{actual}':
        raise ValueError('C3 actual node must match exact original or user-authorized 15->12 /16->13 mapping')
    if int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<24 or not os.environ.get('SLURM_JOB_ID'):raise ValueError('C3 requires k=24 Slurm allocation')
    if not 3600<=args.runtime_seconds<=7200:raise ValueError('Authorized node short test is 1--2 hours')
    output=Path(args.output).absolute()
    if not output.is_relative_to(ROOT/'c_engineering') or output.exists():raise ValueError('Fresh own C3 output directory required')
    output.mkdir(parents=True);job=os.environ['SLURM_JOB_ID'];start=time.monotonic()
    sampler=Sampler(output/'process_memory_io_samples.jsonl',job,args.sample_seconds);sampler.begin()
    rounds=[];before=scratch_probe('/tmp');end=start+args.runtime_seconds
    try:
        ordinal=0
        while end-time.monotonic()>180:
            destination=output/f'round_{ordinal:03d}'
            command=[sys.executable,'-B',str(HERE/'c_engineering_native_nopolar.py'),
                '--panel',str(OLD/'wp4_native_panel/pilot_panel.parquet'),
                '--panel-manifest',str(OLD/'wp4_native_panel/pilot_panel_manifest.json'),
                '--record-index',str(OLD/'record_index.parquet'),'--output',str(destination),
                '--workers','24','--bucket-count','6','--bucket',str(args.node_index-14),
                '--wall-seconds',str(max(151,end-time.monotonic()))]
            launched=time.monotonic()
            with (output/f'round_{ordinal:03d}.stdout').open('w') as stdout, (output/f'round_{ordinal:03d}.stderr').open('w') as stderr:
                process=subprocess.Popen(command,stdout=stdout,stderr=stderr,stdin=subprocess.DEVNULL)
                code=process.wait()
            path=destination/f'job_{job}_summary.json'
            data=json.loads(path.read_text()) if path.is_file() else None
            rounds.append({'round':ordinal,'returncode':code,'elapsed_seconds':time.monotonic()-launched,
                'summary_path':str(path),'summary_sha256':sha(path) if path.is_file() else None,
                'summary':data})
            ordinal+=1
            size=sum(path.stat().st_size for path in output.rglob('*') if path.is_file())
            save(output/'progress.json',{'rounds':ordinal,'elapsed_seconds':time.monotonic()-start,'output_bytes':size,'last_returncode':code})
            if size>=args.output_cap_bytes or code or data is None:break
            # Fast completion repeats only this node's disjoint bucket; each
            # round is explicitly recorded as benchmark work, never new data.
        after=scratch_probe('/tmp')
    finally:memory=sampler.finish()
    pids=sorted({pid for item in rounds if item['summary'] for pid in item['summary'].get('actual_worker_pids',[])})
    report={'status':'C3_NODE_RESOURCE_TEST_CLOSED','scope':'AUTHORIZED_K24_NATIVE_ENGINEERING_REMEASUREMENT',
        'job_id':job,'hostname':hostname,'design_node':f'compute-0-{args.node_index}',
        'design_node_index':args.node_index,'actual_node':hostname,'actual_node_index':actual,
        'execution_is_user_authorized_substitution':actual!=args.node_index,
        'authorization_scope':'User explicitly approved this round design15 on actual12 and design16 on actual13; other original nodes unchanged.',
        'bucket':args.node_index-14,'bucket_count':6,
        'cross_node_rule':'Molecule sha256 modulo6 by design node14..19 bucket0..5. Actual12 executes design15 bucket1; actual13 executes design16 bucket2. Repeats only within the same cohort; original physical15/16 are not measured by substitution.',
        'k':24,'requested_runtime_seconds':args.runtime_seconds,'actual_seconds':time.monotonic()-start,
        'declared_memory_MiB':int(os.environ['SLURM_MEM_PER_NODE']) if os.environ.get('SLURM_MEM_PER_NODE','').isdigit() else None,
        'script_sha256':sha(__file__),'native_sha256':sha(HERE/'c_engineering_native_nopolar.py'),
        'config_sha256':sha(HERE/'c_engineering_native_nopolar_config.json'),'memory':memory,
        'actual_scientific_worker_pids':pids,'scratch_before':before,'scratch_after':after,
        'sacct_in_job_snapshot':accounting(job),'rounds':rounds,
        'QM_remeasurement_started':True,'LMDB_options':{'readonly':True,'lock':False,'create':False},
        'original_data_written':False,'lmdb_1_created':False,
        'node_slots_at_k24':8 if args.node_index==17 else 5 if args.node_index==19 else 4,
        'node_slots_scope':'Original planned WP5 node14..19 slots; execution-node capacity is reported separately by Root resource snapshot.',
        'all_six_nodes_slots':29,
        'memory_note':'Measured own-process RSS/PSS belongs to actual execution node. Proxy physical12/13 does not measure original physical15/16. Multiplying by original planned slots is a planning extrapolation, not observed full29-slot memory.',
        'scratch_note':'Actual native scratch creation, QM writes, parsing, serialization, archive reads/writes and cleanup are exercised. Proc IO/blkio observations plus 128MiB fsync scratch probes are diagnostic, not isolated cold-disk bandwidth.',
        'issues':[{'round':item['round'],'returncode':item['returncode']} for item in rounds if item['returncode']!=0]}
    if len(pids)<24:report['issues'].append({'type':'FEWER_THAN_24_CLOSED_OUTCOME_WORKERS','observed':len(pids)})
    if report['actual_seconds']<3600:report['issues'].append({'type':'LESS_THAN_1_HOUR_ACTUAL_WORK','seconds':report['actual_seconds']})
    save(output/'node_probe_report.json',report)
    print(json.dumps({'status':report['status'],'job_id':job,'seconds':report['actual_seconds'],'worker_pids':len(pids),'issues':report['issues']}))
    return 0

if __name__=='__main__':raise SystemExit(main())
