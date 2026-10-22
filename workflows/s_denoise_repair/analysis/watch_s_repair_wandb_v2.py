"""24-hour own metadata archive watcher; only closed SDK logs, no science."""
from datetime import datetime,timezone,timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
CONTROL=ROOT/'control/wandb_archive_service_v1'
PYTHON=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python')
ARCHIVER=ROOT/'analysis/archive_s_repair_wandb_v3.py'
TZ=timezone(timedelta(hours=8))


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,data):
    temp=path.with_name(path.name+'.pending')
    temp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');temp.replace(path)


def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    CONTROL.mkdir(exist_ok=True)
    with (CONTROL/'service.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        started=time.time();pid=os.getpid();token=str(pid)+'_'+str(int(started))
        directory=CONTROL/token;directory.mkdir(exist_ok=False)
        identity=dict(pid=pid,uid=os.getuid(),host=socket.gethostname(),
            start_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],
            boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            argv=[sys.executable,'-B',str(Path(__file__).absolute())],source_sha256=sha(__file__),
            archiver_sha256=sha(ARCHIVER),started_unix_seconds=started,expires_unix_seconds=started+86400,
            maximum_runtime_seconds=86400,interval_seconds=600,scientific_processes_started=0,
            role='Closed S-repair W&B archive metadata only')
        save(directory/'identity.json',identity)
        save(CONTROL/'current.json',dict(identity_path=str(directory/'identity.json'),identity_sha256=sha(directory/'identity.json')))
        stop=False
        def stop_request(signum,frame):
            nonlocal stop
            stop=True
        signal.signal(signal.SIGTERM,stop_request);signal.signal(signal.SIGINT,stop_request)
        iteration=0
        while time.time()<identity['expires_unix_seconds'] and not stop:
            if sha(__file__)!=identity['source_sha256'] or sha(ARCHIVER)!=identity['archiver_sha256']:
                save(directory/'status.json',dict(status='ARCHIVE_SERVICE_SOURCE_CHANGED',timestamp=time.time()));return
            receipt=ROOT/'reports'/('wandb_archive_service_'+token+'_pass'+str(iteration).zfill(4)+'.json')
            command=[str(PYTHON),'-B',str(ARCHIVER),'--receipt',str(receipt)]
            with (directory/('pass'+str(iteration).zfill(4)+'.log')).open('x') as log:
                result=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
            report=json.loads(receipt.read_text()) if receipt.exists() else None
            success=result.returncode==0 and report is not None and report.get('errors')==[]
            status=dict(status='ARCHIVE_SERVICE_HEALTHY' if success else 'ARCHIVE_SERVICE_ATTENTION',
                iteration=iteration,returncode=result.returncode,receipt_path=str(receipt),
                receipt_sha256=sha(receipt) if receipt.exists() else None,
                updated_at_Asia_Shanghai=datetime.now(TZ).isoformat(timespec='seconds'),timestamp=time.time(),
                expires_unix_seconds=identity['expires_unix_seconds'],scientific_processes_started=0)
            save(directory/'status.json',status)
            iteration+=1
            deadline=min(time.time()+600,identity['expires_unix_seconds'])
            while time.time()<deadline and not stop:
                if (directory/'STOP_REQUEST.json').exists():stop=True;break
                time.sleep(min(5,max(0,deadline-time.time())))
        save(directory/'closed.json',dict(status='ARCHIVE_SERVICE_STOPPED' if stop else 'ARCHIVE_SERVICE_EXPIRED',
            timestamp=time.time(),last_iteration=iteration,identity_sha256=sha(directory/'identity.json')))


if __name__=='__main__':main()
