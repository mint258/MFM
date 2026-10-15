"""Publish actual sonmi Slurm timing; compute report jobs cannot query sacct."""
import hashlib,json,os,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,save,sha

def publish():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    jobs=[];registrations=[]
    for path in (ROOT/'submission').glob('formal_s_*.json'):
        value=json.loads(path.read_text())
        if value.get('job_id'):jobs.append(value['job_id']);registrations.append({'path':str(path),'sha256':sha(path)})
    assert jobs
    command=['sacct','-j',','.join(jobs),'-n','-P','--format=JobIDRaw,User,Start,End,ElapsedRaw,State,ExitCode,NodeList']
    query=subprocess.run(command,capture_output=True,text=True,check=True,timeout=30)
    parents={}
    for line in query.stdout.splitlines():
        fields=line.split('|')
        if fields[0] not in jobs:continue
        assert fields[1]=='zixiao'
        parents[fields[0]]={'user':fields[1],'start':fields[2],'end':fields[3],'elapsed_seconds':int(fields[4]),
            'state':fields[5].split()[0],'exit_code':fields[6],'node':fields[7]}
    assert set(parents)==set(jobs),'Actual registered parent timing is not yet published'
    result={'status':'ACTUAL_SONMI_REGISTERED_S_PARENT_TIMING_PUBLISHED','timestamp':time.time(),
        'publisher_uid':os.getuid(),'publisher_hostname':socket.gethostname(),'publisher_source_sha256':sha(__file__),
        'parents':parents,'registration_references':registrations,'raw_sacct_stdout':query.stdout,
        'raw_sacct_stdout_sha256':hashlib.sha256(query.stdout.encode()).hexdigest(),'query_exit_code':query.returncode}
    save(ROOT/'formal_s/report_accounting_latest.json',result)
    print(json.dumps({'status':result['status'],'registered_parents':len(parents)}),flush=True)

def main():
    save(ROOT/'formal_s/report_accounting_publisher_identity_v1.json',{'pid':os.getpid(),'uid':os.getuid(),
        'proc_start_ticks':Path('/proc/self/stat').read_text().split()[21],'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'source_sha256':sha(__file__),'max_hours':21*24,'interval_seconds':600})
    deadline=time.monotonic()+21*86400
    while time.monotonic()<deadline:
        try:publish()
        except Exception as exc:print('ACTUAL_TIMING_PUBLISH_FAILED '+repr(exc),flush=True)
        time.sleep(600)

if __name__=='__main__':main()
