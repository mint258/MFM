"""Metadata-only close of actual source3 formal CPU scheduler tests, no training authorization."""
import hashlib,json,os,socket,subprocess
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
def ref(path):
    p=Path(path);b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
raw=subprocess.check_output(['sacct','-j','4515656','-n','-X','-P','-o','JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS'],stdin=subprocess.DEVNULL,text=True,timeout=30)
rows=[line.strip().split('|') for line in raw.splitlines() if line.strip()];assert len(rows)==1
jid,state,code,elapsed,cpus=rows[0];assert jid=='4515656' and state=='COMPLETED' and code=='0:0' and int(cpus)>=16
path=R/'validation/formal_cpu_pool_job4515656/result.json';result=json.loads(path.read_text())
assert result['status']=='FORMAL_EXPANDED_CPU_POOL_PASS' and result['tests']==18 and result['failures']==result['errors']==0
snapshot=dict(status='ACTUAL_SONMI_SACCT_SNAPSHOT',host='sonmi',uid=1278,columns=['State','ExitCode','ElapsedRaw','AllocCPUS'],rows={jid:[state,code,elapsed,cpus]},raw_stdout=raw)
snap=R/'control/accounting_snapshots/formal_cpu_pool_tests_v1.json'
with snap.open('x') as f:json.dump(snapshot,f,indent=2);f.write('\n')
doc=dict(status='FORMAL_COORDINATION_V10_EXPANDED_CPU_POOL_TESTS_PASS',job_id=jid,tests=18,
 source_references=[ref(R/part) for part in ['formal_workflows_v4/full_coordinator_v10.py','formal_workflows_v4/test_full_coordinator_v10.py','analysis/run_formal_cpu_pool_tests_v1.py']],
 checks=[dict(name='16 inherited resource/paired-H0 cases plus 2 CPU-pool scope and byte-equivalence cases',returncode=0)],
 result_reference=ref(path),actual_parent_snapshot=ref(snap),actual_parent=[state,code,elapsed,cpus],
 CPU_nodes=['compute-0-'+str(n) for n in range(8,20)],GPU_nodes=['compute-0-20','compute-0-21','compute-0-22'],
 all_other_Root9_bytes_identical=True,scientific_updates=0,formal_training_authorized=False)
with (R/'configs/formal_cpu_pool_tests_closure_v1.json').open('x') as f:json.dump(doc,f,indent=2);f.write('\n')
print(json.dumps(doc))
