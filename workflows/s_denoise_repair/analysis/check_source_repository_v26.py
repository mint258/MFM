"""Sonmi source-only pre-submission repository check; no model/data computation."""
import json,os,socket,subprocess,hashlib
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016');source=R/'source_v3'
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
out=R/'reports/source_v3_repository_check_v26.json';assert not out.exists()
run=subprocess.run(['python','-B','tools/check_repository.py'],cwd=source,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
with out.open('x') as f:f.write(run.stdout)
receipt=dict(argv=['python','-B','tools/check_repository.py'],cwd=str(source),returncode=run.returncode,stderr=run.stderr,
 output=dict(path=str(out),sha256=hashlib.sha256(out.read_bytes()).hexdigest()))
with (R/'reports/source_v3_repository_check_v26_receipt.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
assert run.returncode==0,receipt
doc=json.loads(run.stdout);assert doc['status']=='PASS',doc
print(json.dumps(dict(status=doc['status'],output=receipt['output'])))
