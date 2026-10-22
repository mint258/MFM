"""Start the bounded v3 watcher only after the former own watcher has closed."""
import hashlib,json,os
from pathlib import Path
import socket,subprocess,time
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
CONTROL=ROOT/'control/wandb_archive_service_v1'
PYTHON='/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    old_ref=json.loads((CONTROL/'current.json').read_text());old_path=Path(old_ref['identity_path'])
    assert sha(old_path)==old_ref['identity_sha256']
    old=json.loads(old_path.read_text());closed=old_path.with_name('closed.json')
    for _ in range(40):
        if closed.exists():break
        time.sleep(.5)
    document=json.loads(closed.read_text());assert document['status']=='ARCHIVE_SERVICE_STOPPED'
    assert document['identity_sha256']==old_ref['identity_sha256']
    proc=Path('/proc')/str(old['pid'])
    if proc.exists():
        fields=proc.joinpath('stat').read_text().rsplit(')',1)[1].split()
        assert fields[19]!=str(old['start_ticks']) or fields[0]=='Z','Previous exact watcher has not exited'
    script=ROOT/'analysis/watch_s_repair_wandb_v3.py'
    token=str(int(time.time()));stdout=ROOT/'logs'/('archive_watcher_v3_'+token+'.stdout')
    with stdout.open('xb') as output,stdout.with_suffix('.stderr').open('xb') as error:
        child=subprocess.Popen([PYTHON,'-B',str(script)],stdin=subprocess.DEVNULL,stdout=output,stderr=error,start_new_session=True)
    for _ in range(40):
        assert child.poll() is None,'New watcher failed; preserve stdout/stderr'
        ref=json.loads((CONTROL/'current.json').read_text());path=Path(ref['identity_path'])
        identity=json.loads(path.read_text())
        if identity['pid']==child.pid:break
        time.sleep(.25)
    assert identity['pid']==child.pid and identity['uid']==1278 and sha(path)==ref['identity_sha256']
    assert identity['source_sha256']==sha(script) and identity['archiver_sha256']==sha(ROOT/'analysis/archive_s_repair_wandb_v4.py')
    receipt=dict(status='OWN_WANDB_WATCHER_UPGRADED_AFTER_ACTUAL_CLOSED_OLD_SERVICE',old_identity=old_ref,
        old_closed_reference=dict(path=str(closed),sha256=sha(closed)),new_identity=ref,new_pid=child.pid,
        maximum_runtime_seconds=86400,no_scientific_process_signalled=True,timestamp=time.time())
    with (ROOT/'reports'/('archive_watcher_upgrade_v3_'+token+'.json')).open('x') as stream:json.dump(receipt,stream,indent=2);stream.write('\n')
    print('NEW_METADATA_WATCHER_STARTED',child.pid,'EXPIRES',identity['expires_unix_seconds'])

if __name__=='__main__':main()
