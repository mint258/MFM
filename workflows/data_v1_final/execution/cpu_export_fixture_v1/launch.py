"""Run one finite CPU test with cooperative live-memory monitoring; never kill it."""
from __future__ import annotations
import argparse,datetime,json,os,pathlib,subprocess,sys,threading,time
from . import policy,runtime
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
        now=time.time();r=self.proof['request'];reason=None;observation=None;rss=0;count=0
        try:
            observation=sample();rss,count=runtime.own_tree_rss(os.getpid())
            reason=runtime.memory_denial(observation,self.proof['node_memory_limit_bytes'],self.proof['reserved_positive_other_bytes'],r['memory_gib']*1024**3,rss)
        except BaseException as e:reason='MEMORY_SAMPLE_FAILURE:'+repr(e)
        h={'schema':'CPU_SMALL_TEST_MONITOR_V1','observed_unix_seconds':now,'observed_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'uid':1278,'node':r['node'],'job_id':self.job_id,'intent_reference':self.intent,'monitor_pid':os.getpid(),'monitor_start_ticks':runtime._stat_start(os.getpid()),'state':'ALLOW','sample':observation,'own_tree_rss_bytes':rss,'own_processes':count}
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
            if sum(p.stat().st_size for p in self.directory.iterdir() if p.is_file())>policy.GUARD_CAP:raise ValueError('MONITOR32MIB_OUTPUT_CAP')
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
    os.environ['DATA_V1_CPU_INTENT']=str(a.intent);os.environ['DATA_V1_CPU_GUARD_DIR']=str(directory)
    monitor=Monitor(proof,a.intent,directory);child=None;code=1;failure=None
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
        monitor.new('closure.json',result)
        print(json.dumps(result),flush=True)
    return 0 if result['status']=='COMPLETED_NO_MEMORY_DENIAL' else 1
if __name__=='__main__':sys.exit(main())
