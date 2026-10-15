"""Root metadata wait/submit of the bounded five-dataset probe input smoke job."""
import fcntl,json,os,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha
from s_convergence_root_v1 import resource_ready,query

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    folder=ROOT/'probe_preparation_control';folder.mkdir(exist_ok=True)
    lock=(folder/'root.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    sources={str(ROOT/'scripts'/n):sha(ROOT/'scripts'/n) for n in ['prepare_s_probe_data_v1.py','s_probe_data_smoke_v1.sbatch','s_probe_prepare_root_v1.py']}
    save(folder/'identity.json',{'pid':os.getpid(),'uid':os.getuid(),'started':time.time(),
        'proc_start_ticks':Path('/proc/self/stat').read_text().split()[21],
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'sources':sources,'max_hours':72})
    deadline=time.monotonic()+72*3600;submitted=None
    while time.monotonic()<deadline:
        assert all(sha(path)==value for path,value in sources.items()),'Probe draft sources changed; stop metadata waiter for review'
        if submitted:
            raw=query(['sacct','-j',submitted,'-n','-P','--format=JobIDRaw,User,State,ExitCode'])
            rows=[r.split('|') for r in raw.splitlines() if r.split('|')[0]==submitted]
            if rows and rows[0][2].split()[0] in ['COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL']:
                save(folder/'terminal.json',{'job_id':submitted,'actual_parent_accounting':rows[0],'timestamp':time.time(),
                    'status':'SMOKE_TERMINAL_REQUIRES_ACTUAL_ROW_REVIEW_BEFORE_FORMAL_PROBE_INPUTS'})
                return
        else:
            for node in ['compute-0-2','compute-0-8','compute-0-9','compute-0-10','compute-0-11','compute-0-12']:
                observation=resource_ready(node)
                # resource_ready conservatively checks a64GiB envelope although this bounded test requests32GiB.
                if not observation['eligible']:continue
                name='s_probe_data_smoke_v1_node'+node.rsplit('-',1)[1]
                script=ROOT/'scripts'/(name+'.sbatch');receipt=ROOT/'submission'/(name+'.json')
                if receipt.exists():
                    value=json.loads(receipt.read_text());submitted=value.get('job_id');break
                if not script.exists():
                    text=(ROOT/'scripts/s_probe_data_smoke_v1.sbatch').read_text()
                    text=text.replace('sconv_probe_data_smoke_v1','sconv_probe_data_smoke_v1_node'+node.rsplit('-',1)[1])
                    text=text.replace('#SBATCH --nodelist=compute-0-2','#SBATCH --nodelist='+node)
                    script.write_text(text)
                run=subprocess.run(['python',str(ROOT/'scripts/submit.py'),str(script),'--node',node,'--cpus','16','--mem-gib','32'],
                    cwd=PROJECT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
                save(folder/'submission_attempt.json',{'node':node,'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr,'timestamp':time.time()})
                if run.returncode==0:submitted=json.loads(receipt.read_text())['job_id'];break
            save(folder/'status.json',{'status':'WAITING_FOR_FREE_CPU_NODE' if submitted is None else 'ACTUAL_SMOKE_SUBMITTED',
                'job_id':submitted,'timestamp':time.time(),'formal_geometry_generation_started':False})
        time.sleep(60)
    save(folder/'status.json',{'status':'BOUNDED_METADATA_WAIT_EXPIRED','timestamp':time.time()})

if __name__=='__main__':main()
