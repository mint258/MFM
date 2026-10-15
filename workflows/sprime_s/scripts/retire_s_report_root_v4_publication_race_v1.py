import json,os,signal,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,save
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
i=json.loads((ROOT/'report_control/identity_v4.json').read_text());assert i['pid']==4080070 and i['uid']==1278
p=Path('/proc')/str(i['pid']);assert p.stat().st_uid==i['uid']
assert (p/'stat').read_text().split()[21]==i['proc_start_ticks']
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==i['boot_id']
assert b's_report_finish_root_v4.py' in (p/'cmdline').read_bytes()
s=json.loads((ROOT/'report_control/status_v4.json').read_text());assert s['status']=='ROOT_REPAIR_REQUIRED_REPORT_JOB' and s['report_job']['job_id']=='4515189'
q=subprocess.run(['sacct','-j','4515189','-n','-P','--format=JobIDRaw,User,State,ExitCode'],capture_output=True,text=True,check=True,timeout=30)
assert '4515189|zixiao|FAILED|1:0' in q.stdout
out=ROOT/'report_control/retired_root_v4_publication_race_20261015.json';assert not out.exists();save(out,{'identity':i,'status':s,'actual_failed_job_sacct':q.stdout,'timestamp':time.time(),'action':'SIGTERM_VERIFIED_OWN_METADATA_ROOT_ONLY'})
os.kill(i['pid'],signal.SIGTERM)
print('VERIFIED_OWN_REPORT_ROOT_V4_RETIRED_ONLY')
