"""One-time metadata watcher bootstrap. Refuses a duplicate launch request."""
import hashlib,json,os
from pathlib import Path
import socket,subprocess,time
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
control=ROOT/'control/wandb_archive_service_v1';control.mkdir(exist_ok=True)
with (control/'bootstrap_request_v1.json').open('x') as stream:
 json.dump(dict(status='UNIQUE_LAUNCH_REQUEST',timestamp=time.time(),uid=os.getuid()),stream);stream.write('\n')
python='/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
source=ROOT/'analysis/watch_s_repair_wandb_v1.py'
with (control/'service.stdout').open('x') as output:
 child=subprocess.Popen([python,'-B',str(source)],stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(pid=child.pid,source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),scientific_processes_started=0)))
