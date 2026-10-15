import json,os,signal,subprocess,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013')
identity_path=root/'report_control/identity_v3.json'
identity=json.loads(identity_path.read_text())
assert identity['pid']==4050319 and identity['uid']==os.getuid()==1278
p=Path('/proc')/str(identity['pid'])
assert p.stat().st_uid==1278
assert (p/'stat').read_text().split()[21]==identity['proc_start_ticks']
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==identity['boot_id']
assert b's_report_finish_root_v3.py' in (p/'cmdline').read_bytes()
status=json.loads((root/'report_control/status_v3.json').read_text())
job=status.get('report_job',{}).get('job_id')
if job:
    q=subprocess.run(['sacct','-j',job,'-n','-P','--format=JobIDRaw,User,State,ExitCode'],capture_output=True,text=True,check=True,timeout=30)
    rows=[line.split('|') for line in q.stdout.splitlines() if line.split('|')[0]==job]
    assert len(rows)==1 and rows[0][1:4]==['zixiao','COMPLETED','0:0'],rows
archive=root/'cuda_recovery_v1/retired_report_root_v3_identity.json'
assert not archive.exists()
archive.write_text(json.dumps({'identity':identity,'last_status':status,'timestamp':time.time(),'action':'SIGTERM_VERIFIED_OWN_METADATA_ROOT_ONLY'},indent=2)+'\n')
os.kill(identity['pid'],signal.SIGTERM)
print('OLD_REPORT_METADATA_ROOT_RETIRED',identity['pid'],'active_report_job',job)
