"""Metadata-only closure of actual guide fallback guard tests."""
import hashlib,json,os,socket,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
def ref(path):
    p=Path(path);b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
raw=subprocess.check_output(['sacct','-j','4515651','-n','-X','-P','-o','JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS'],stdin=subprocess.DEVNULL,text=True,timeout=30)
rows=[line.strip().split('|') for line in raw.splitlines() if line.strip()];assert len(rows)==1
jid,state,code,elapsed,cpus=rows[0];assert jid=='4515651' and state=='COMPLETED' and code=='0:0' and int(cpus)>=16
result=R/'validation/profile_optional_cosines_job4515651/result.json';out=json.loads(result.read_text())
assert out['status']=='PROFILE_UNDEFINED_COSINE_HANDLING_PASS' and out['tests']==5 and out['failures']==out['errors']==0
snapshot=dict(status='ACTUAL_SONMI_SACCT_SNAPSHOT',host='sonmi',uid=1278,columns=['State','ExitCode','ElapsedRaw','AllocCPUS'],rows={jid:[state,code,elapsed,cpus]},raw_stdout=raw)
path=R/'control/accounting_snapshots/profile_optional_cosine_tests_v1.json'
with path.open('x') as f:json.dump(snapshot,f,indent=2);f.write('\n')
closure=dict(status='ACTUAL_PROFILE_UNDEFINED_COSINES_CLOSED',tests=5,actual_parent=[state,code,elapsed,cpus],actual_parent_snapshot=ref(path),result_reference=ref(result),source_references=[ref(R/part) for part in ['analysis/profile_completed_d3_conditions_v3.py','analysis/test_profile_optional_cosines_v1.py','analysis/run_profile_optional_cosines_v1.py','analysis/dispatch_completed_d3_profiles_v3.py']],
 active_science_source='source_v3',scientific_updates=0,formal_training_authorized=False)
with (R/'configs/profile_optional_cosines_tests_closure_v1.json').open('x') as f:json.dump(closure,f,indent=2);f.write('\n')
print(json.dumps(closure))
