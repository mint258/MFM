"""CPU launcher v2: node-local monotonic signals, durable export after natural child completion."""
from __future__ import annotations
import argparse,datetime,hashlib,json,os,pathlib,subprocess,sys,threading,time
from . import policy,runtime_v2 as runtime
from .probe_memory import sample

class Monitor:
    def __init__(self,proof,intent,directory):
        self.proof=proof;self.intent=policy.ref(intent);self.directory=directory
        self.job_id=os.environ['SLURM_JOB_ID'];self.first_denial=None;self.samples=0
        self.done=threading.Event();self.thread=None;self.io_failure=None
    def new(self,name,value):
        p=self.directory/name
        with p.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    def tick(self):
        sample_started=time.monotonic();now=time.time();r=self.proof['request'];reason=None;observation=None;rss=0;count=0
        try:
            observation=sample();rss,count=runtime.own_tree_rss(os.getpid())
            reason=runtime.memory_denial(observation,self.proof['node_memory_limit_bytes'],self.proof['reserved_positive_other_bytes'],r['memory_gib']*1024**3,rss)
            if time.monotonic()-sample_started>2:reason='MEMORY_SAMPLE_DURATION_OVER2SECONDS'
        except BaseException as e:reason='MEMORY_SAMPLE_FAILURE:'+repr(e)
        h={'schema':'CPU_SMALL_TEST_MONITOR_V1','observed_unix_seconds':now,'observed_monotonic_seconds':time.monotonic(),'memory_sample_started_monotonic_seconds':sample_started,'boot_id':self.proof['memory_observation']['boot_id'],'observed_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'uid':1278,'node':r['node'],'job_id':self.job_id,'intent_reference':self.intent,'monitor_pid':os.getpid(),'monitor_start_ticks':runtime._stat_start(os.getpid()),'state':'ALLOW','sample':observation,'own_tree_rss_bytes':rss,'own_processes':count}
        if reason and self.first_denial is None:
            self.first_denial={**h,'state':'STOP','reason':reason}
            try:self.new('STOP.json',self.first_denial)
            except BaseException as e:self.io_failure=repr(e)
        if self.first_denial:h.update(state='STOP',first_denial=self.first_denial['reason'])
        try:
            p=self.directory/'heartbeat.tmp'
            with p.open('w',encoding='utf-8') as f:json.dump(h,f);f.write('\n')
            os.replace(p,self.directory/'heartbeat.json')
            line=json.dumps(h,separators=(',',':'))+'\n'
            with (self.directory/'samples.jsonl').open('a',encoding='utf-8') as f:f.write(line)
            self.samples+=1
            if sum(p.stat().st_size for p in self.directory.iterdir() if p.is_file())>policy.GUARD_CAP//2-1024**2:raise ValueError('MONITOR32MIB_OUTPUT_CAP')
        except BaseException as e:
            self.io_failure=repr(e)
            if self.first_denial is None:
                self.first_denial={**h,'state':'STOP','reason':'MONITOR_OUTPUT_FAILURE:'+repr(e)}
                try:self.new('STOP.json',self.first_denial)
                except BaseException:pass
        return self.first_denial is None
    def loop(self):
        while not self.done.wait(1):self.tick()
    def start(self):
        self.thread=threading.Thread(target=self.loop,name='cpu-memory-monitor',daemon=False);self.thread.start()
    def close(self):
        self.done.set()
        if self.thread:self.thread.join()
        self.tick()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--intent',required=True,type=pathlib.Path);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    command=a.command
    if command and command[0]=='--':command=command[1:]
    policy.require(command and pathlib.Path(command[0])==pathlib.Path('/share/home/zixiao/.conda/envs/chemprop/bin/python'),'FROZEN_LOGICAL_PYTHON_ENTRY_REQUIRED')
    proof=runtime._proof(a.intent,pinned_path=pathlib.Path(__file__),verify_sources=True)
    r=proof['request'];name=policy.job_name(r)
    directory=policy.ROOT/'artifacts/cpu_analysis_guards'/name
    policy.require(not directory.exists(),'OWN_MONITOR_OUTPUT_ALREADY_EXISTS_NO_RETRY')
    directory.parent.mkdir(parents=True,exist_ok=True);directory.mkdir()
    local=runtime.local_guard_directory(name,os.environ['SLURM_JOB_ID'])
    policy.require(not local.exists() and not local.is_symlink(),'NEW_OWN_NODE_LOCAL_GUARD_REQUIRED')
    local.mkdir(mode=0o700)
    location={'schema':'CPU_NODE_LOCAL_GUARD_LOCATION_V2','node':r['node'],'job_id':os.environ['SLURM_JOB_ID'],'uid':1278,'local_directory':str(local),'intent_reference':policy.ref(a.intent),'memory_monitor_signals_are_node_local':True}
    with (directory/'guard_location.json').open('x') as f:json.dump(location,f);f.write('\n')
    os.environ['DATA_V1_CPU_INTENT']=str(a.intent);os.environ['DATA_V1_CPU_GUARD_DIR']=str(directory);os.environ['DATA_V1_CPU_LOCAL_GUARD_DIR']=str(local)
    monitor=Monitor(proof,a.intent,local);child=None;code=1;failure=None
    try:
        if monitor.tick():
            monitor.start();runtime.checkpoint()
            child=subprocess.Popen(command,stdin=subprocess.DEVNULL)
            # Deliberately natural drain: no signal, terminate, timeout kill or retry.
            code=child.wait()
    except BaseException as e:
        failure=repr(e)
        if child is not None:code=child.wait()
    finally:
        monitor.close()
        result={'schema':'CPU_BOUNDED_TEST_MONITOR_CLOSURE_V1','status':'COMPLETED_NO_MEMORY_DENIAL' if code==0 and monitor.first_denial is None and failure is None else 'TEST_NOT_ACCEPTED_MEMORY_OR_RUNTIME_FAILURE','job_id':os.environ['SLURM_JOB_ID'],'scope_key':r['scope_key'],'intent_reference':policy.ref(a.intent),'command':command,'child_returncode':code,'failure':failure,'first_denial':monitor.first_denial,'monitor_io_failure':monitor.io_failure,'samples':monitor.samples,'signals_sent':False,'formal_generation_authorized':False,'monitor_thread_closed':monitor.thread is None or not monitor.thread.is_alive()}
        result['local_guard_directory']=str(local);result['heartbeat_clock']='BOOT_MONOTONIC';result['evidence_exports']=[]
        try:
            for source in sorted(local.iterdir()):
                if not source.is_file() or source.is_symlink() or source.name.endswith('.tmp'):continue
                before=source.stat();h=hashlib.sha256();dest=directory/source.name
                with source.open('rb') as inp,dest.open('xb') as out:
                    for block in iter(lambda:inp.read(1<<20),b''):h.update(block);out.write(block)
                after=source.stat()
                policy.require((before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'LOCAL_MONITOR_EVIDENCE_CHANGED_DURING_EXPORT')
                result['evidence_exports'].append({'path':str(dest),'bytes':before.st_size,'sha256':h.hexdigest()})
            result['durable_evidence_exported']=True
        except BaseException as e:
            result.update(status='TEST_NOT_ACCEPTED_MEMORY_OR_RUNTIME_FAILURE',durable_evidence_exported=False,evidence_export_failure=repr(e))
        monitor.new('closure.json',result)
        with (directory/'closure.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
        print(json.dumps(result),flush=True)
    return 0 if result['status']=='COMPLETED_NO_MEMORY_DENIAL' else 1
if __name__=='__main__':sys.exit(main())
