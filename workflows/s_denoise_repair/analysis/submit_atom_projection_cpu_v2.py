"""Metadata-only bounded candidate CPU submission, unique receipt through original submitter."""
import hashlib,json,os,socket,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
assert not (R/'submission/atom_projection_cpu_v2.json').exists()
qptr=json.loads((R/'control/live_quota_v1/current.json').read_text())
q=json.loads(Path(qptr['latest_path']).read_text())
assert q['complete'] and q['returncode']==0 and q['owner_uid']==1278 and q['publisher_pid']==184421
assert q['publisher_source_sha256']=='dbdb7a7469b074089235ed4b195ef74b35934367f233a0a74552d4a8e28a829d'
assert 0<=time.time()-q['sampled_unix_seconds']<=90 and q['limit_kib']-q['used_kib']>=4*1024**2
v=os.statvfs(R);assert v.f_bavail*v.f_frsize>=4*1024**3 and v.f_favail>=10000
assert json.loads((R/'reports/source_v4_repository_check_v1.json').read_text())['status']=='PASS'
script=R/'scripts/atom_projection_cpu_v2.sbatch';raw=script.read_bytes()
assert b'\r' not in raw and b'\\"' not in raw
subprocess.run(['bash','-n',str(script)],stdin=subprocess.DEVNULL,check=True)
argv=['python','-B',str(R/'source_v3/workflows/s_denoise/submit.py'),str(script),'--node','compute-0-14','--cpus','16','--mem-gib','64']
run=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
record={'time':time.time(),'argv':argv,'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr,
 'quota_used_kib':q['used_kib'],'quota_limit_kib':q['limit_kib'],'quota_sampled':q['sampled_unix_seconds'],
 'filesystem_free_bytes':v.f_bavail*v.f_frsize,'filesystem_free_inodes':v.f_favail,'estimated_output_max_bytes':2*1024**3}
with (R/'reports/atom_projection_cpu_v2_submission_stdout.json').open('x') as f:json.dump(record,f,indent=2);f.write('\n')
if run.returncode:print(json.dumps(record));raise SystemExit(run.returncode)
receipt=json.loads((R/'submission/atom_projection_cpu_v2.json').read_text())
print(json.dumps({'status':'SUBMITTED_CPU_CANDIDATE_ONLY','job_id':receipt['job_id'],'script_sha256':receipt['sha256']}),flush=True)
