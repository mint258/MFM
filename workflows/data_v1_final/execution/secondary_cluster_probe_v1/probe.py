"""CPU allocation-only environment preflight for the user-authorized secondary cluster."""
import hashlib,json,os,pathlib,platform,shutil,socket,subprocess,sys,time
ROOT=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def main():
    jid=os.environ.get('SLURM_JOB_ID','');node=socket.gethostname().split('.')[0]
    need(os.getuid()==1264 and jid.isdecimal() and node in {'compute-0-1','compute-0-3','compute-0-4','compute-0-5','compute-0-6','sonmi1'},'ACTUAL_SECONDARY_CPU_NODE_UID_JOB')
    need(os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('CUDA_VISIBLE_DEVICES')=='','CPU16_ONLY')
    started=time.monotonic();rows=[]
    code="import importlib,json,platform,sys; r={'python':platform.python_version(),'executable':sys.executable,'modules':{}}\nfor name in ('rdkit','numpy','scipy','pyarrow','lmdb','pandas'):\n try:\n  m=importlib.import_module(name);r['modules'][name]={'version':getattr(m,'__version__',None),'file':getattr(m,'__file__',None)}\n except Exception as e:r['modules'][name]={'error_type':type(e).__name__,'message':str(e)[:512]}\nprint(json.dumps(r,sort_keys=True))"
    base=pathlib.Path('/share/home/alpha/miniconda3')
    for label in ('base','deepchem_env','mopac','psi'):
        executable=base/'bin/python' if label=='base' else base/'envs'/label/'bin/python'
        if not executable.exists():
            rows.append({'environment':label,'python_exists':False});continue
        proc=subprocess.run([str(executable),'-B','-c',code],stdin=subprocess.DEVNULL,capture_output=True,text=True)
        need(len(proc.stdout.encode())+len(proc.stderr.encode())<1<<20,'BOUNDED_ENVIRONMENT_METADATA')
        rows.append({'environment':label,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
    disk=shutil.disk_usage(ROOT)
    raw=subprocess.run(['scontrol','show','job',jid,'--oneliner'],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True).stdout
    result={'schema':'SECONDARY_CLUSTER_CPU_ENVIRONMENT_PREFLIGHT_V1','status':'ENVIRONMENT_PROBED_NO_SCIENCE','endpoint':'218.192.171.238:22','user':'alpha','uid':os.getuid(),'node':node,'job_id':jid,'cpus':16,'job_metadata':raw,'source_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'python_environments':rows,'platform':platform.platform(),'machine':platform.machine(),'disk_path':str(ROOT),'filesystem_free_bytes':disk.free,'filesystem_total_bytes':disk.total,'quota_visibility':'share account over limit; gfshome separate filesystem reported no quota enabled; no scientific storage admission asserted','actual_memory_environment':{k:os.environ.get(k) for k in ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')},'memory_requested':False,'no_UFF_QM_or_scientific_data_calls':True,'forced_signals_sent':False,'elapsed_seconds':time.monotonic()-started}
    payload=(json.dumps(result,indent=2,sort_keys=True)+'\n').encode();need(len(payload)<2<<20,'SMALL_RESULT_ONLY')
    output=ROOT/('environment_'+jid+'.json')
    with output.open('xb') as stream:stream.write(payload)
    print(json.dumps({'job_id':jid,'node':node,'status':result['status'],'result':str(output),'result_sha256':hashlib.sha256(payload).hexdigest()}))
if __name__=='__main__':main()
