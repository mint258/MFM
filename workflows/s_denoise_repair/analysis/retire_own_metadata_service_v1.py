"""Inspect/stop/confirm one exact own S-repair metadata service; never a model process."""
import argparse,fcntl,hashlib,json,os,signal,socket,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
EXPECTED={'quota':'dbdb7a7469b074089235ed4b195ef74b35934367f233a0a74552d4a8e28a829d','archive':'47d7b4bb000b91149af53f79fe05a28eb18ac2406ffd4ed1d81838e2616e7356'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--role',choices=['quota','archive'],required=True);ap.add_argument('--expected-pid',type=int,required=True)
    ap.add_argument('--action',choices=['inspect','stop','confirm'],default='inspect');ap.add_argument('--reason',choices=['lease-renewal','task-stop'],required=True);a=ap.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    control=R/'control'/('live_quota_v1' if a.role=='quota' else 'wandb_archive_service_v1')
    ptr=json.loads((control/'current.json').read_text());identity_path=Path(ptr['identity_path'])
    assert identity_path.is_relative_to(control) and not identity_path.is_symlink() and sha(identity_path)==ptr['identity_sha256']
    identity=json.loads(identity_path.read_text());assert identity['pid']==a.expected_pid and identity['uid']==1278 and identity['scientific_processes_started']==0
    assert identity['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert identity['role']==('S_REPAIR_PRIVATE_COPY_OF_VERIFIED_STAGE59_QUOTA_PUBLISHER' if a.role=='quota' else 'Closed S-repair W&B archive metadata only')
    script=Path(identity['argv'][-1]);assert script.is_relative_to(control if a.role=='quota' else R/'analysis') and script.stat().st_uid==1278 and not script.is_symlink()
    assert sha(script)==identity['source_sha256']==EXPECTED[a.role]
    def state():
        p=Path('/proc')/str(a.expected_pid)
        if not p.exists():return {'exact_process_live':False,'state':'ABSENT'}
        tail=p.joinpath('stat').read_text().rsplit(')',1)[1].split()
        if str(tail[19])!=str(identity['start_ticks']):return {'exact_process_live':False,'state':'PID_REUSED_DIFFERENT_START_TICKS','observed_start_ticks':tail[19]}
        assert p.stat().st_uid==1278
        if tail[0]=='Z':return {'exact_process_live':False,'state':'ZOMBIE_EXITED'}
        argv=[b.decode() for b in p.joinpath('cmdline').read_bytes().split(b'\0') if b];assert argv==identity['argv']
        return {'exact_process_live':True,'state':tail[0],'argv':argv,'start_ticks':tail[19]}
    proof={'role':a.role,'pid':a.expected_pid,'reason':a.reason,'identity_reference':ptr,'source_reference':ref(script),'before':state(),
        'timestamp_unix':time.time(),'no_scientific_process_signalled':True,'metadata_role_whitelist_verified':True}
    if a.action=='inspect':
        proof['status']='EXACT_OWN_METADATA_SERVICE_INSPECTED_NO_ACTION';print(json.dumps(proof));return
    directory=R/'control/service_retirements';directory.mkdir(exist_ok=True)
    with (directory/'root.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.action=='stop' and state()['exact_process_live']:
            if a.role=='archive':
                request=identity_path.with_name('STOP_REQUEST.json')
                if request.exists():
                    old=json.loads(request.read_text());assert old['identity_reference']==ptr
                else:
                    with request.open('x') as f:json.dump(dict(reason=a.reason,identity_reference=ptr,timestamp=time.time(),no_scientific_process_signalled=True),f,indent=2);f.write('\n')
                proof['action']='WRITE_EXACT_OWN_ARCHIVE_METADATA_STOP_REQUEST'
            else:
                # Recheck the exact original process immediately before signalling this PID only.
                assert state()['exact_process_live'];os.kill(a.expected_pid,signal.SIGTERM);proof['action']='SIGTERM_EXACT_OWN_QUOTA_METADATA_PID_ONLY'
            deadline=time.monotonic()+20
            while state()['exact_process_live'] and time.monotonic()<deadline:time.sleep(.25)
        after=state();proof['after']=after
        proof['status']='EXACT_OWN_METADATA_SERVICE_ACTUALLY_EXITED' if not after['exact_process_live'] else 'EXACT_OWN_METADATA_SERVICE_STOP_REQUEST_PENDING'
        if a.role=='archive' and not after['exact_process_live']:
            closed=identity_path.with_name('closed.json');d=json.loads(closed.read_text());assert d['identity_sha256']==ptr['identity_sha256'] and d['status'] in ['ARCHIVE_SERVICE_STOPPED','ARCHIVE_SERVICE_EXPIRED'];proof['closed_reference']=ref(closed)
        out=directory/(a.role+'_'+str(a.expected_pid)+'_'+a.action+'_'+str(time.time_ns())+'.json')
        with out.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
        print(json.dumps(dict(status=proof['status'],role=a.role,pid=a.expected_pid,output=str(out))))
if __name__=='__main__':main()
