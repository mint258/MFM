"""Start a private copy of the verified Stage59 24h quota publisher; metadata only."""
import argparse,fcntl,hashlib,json,os
from pathlib import Path
import socket,subprocess,time
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
CONTROL=ROOT/'control/live_quota_v1'
PYTHON='/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
SOURCE_SHA='dbdb7a7469b074089235ed4b195ef74b35934367f233a0a74552d4a8e28a829d'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):
    raw=(json.dumps(d,indent=2,allow_nan=False)+'\n').encode()
    q=p.with_name(p.name+'.pending')
    with q.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    q.replace(p)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--lease',required=True);args=parser.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert args.lease.startswith('lease') and args.lease[5:].isdecimal()
    with (CONTROL/'root_service.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        current=CONTROL/'current.json'
        if current.exists():
            old=json.loads(current.read_text());assert sha(old['identity_path'])==old['identity_sha256']
            previous=json.loads(Path(old['identity_path']).read_text());proc=Path('/proc')/str(previous['pid'])
            if proc.exists():
                ticks=proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]
                assert ticks!=str(previous['start_ticks']),'Existing exact own publisher still live; retire it by verified identity first'
        directory=CONTROL/args.lease;script=directory/'publish_quota.py'
        assert script.is_file() and not script.is_symlink() and script.stat().st_uid==1278 and sha(script)==SOURCE_SHA
        assert not (directory/'identity.json').exists() and not (directory/'latest.json').exists()
        command=[PYTHON,'-B',str(script)];began=time.time()
        with (directory/'stdout.log').open('xb') as stdout,(directory/'stderr.log').open('xb') as stderr:
            child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
        time.sleep(.5);assert child.poll() is None,'Publisher failed before identity capture; preserve stderr'
        proc=Path('/proc')/str(child.pid);tail=proc.joinpath('stat').read_text().rsplit(')',1)[1].split()
        assert proc.stat().st_uid==1278
        argv=[x.decode() for x in proc.joinpath('cmdline').read_bytes().split(b'\0') if x];assert argv==command
        identity=dict(pid=child.pid,uid=1278,host='sonmi',start_ticks=tail[19],boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            argv=argv,source_path=str(script),source_sha256=SOURCE_SHA,started_unix_seconds=began,expires_unix_seconds=began+86400,
            maximum_runtime_seconds=86400,refresh_seconds=30,role='S_REPAIR_PRIVATE_COPY_OF_VERIFIED_STAGE59_QUOTA_PUBLISHER',scientific_processes_started=0)
        save(directory/'identity.json',identity)
        save(current,dict(identity_path=str(directory/'identity.json'),identity_sha256=sha(directory/'identity.json'),latest_path=str(directory/'latest.json')))
        print('S_REPAIR_QUOTA_SERVICE_STARTED',child.pid,args.lease,'EXPIRES',identity['expires_unix_seconds'])

if __name__=='__main__':main()
