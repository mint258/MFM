import json,os,signal,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,save
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
i=json.loads((ROOT/'report_control/identity_v5.json').read_text());assert i['pid']==42913 and i['uid']==1278
p=Path('/proc')/str(i['pid']);assert p.stat().st_uid==i['uid']
assert (p/'stat').read_text().split()[21]==i['proc_start_ticks']
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==i['boot_id']
assert b's_report_finish_root_v5.py' in (p/'cmdline').read_bytes()
s=json.loads((ROOT/'report_control/status_v5.json').read_text());job=s.get('report_job',{}).get('job_id')
if job:
    q=subprocess.run(['sacct','-j',job,'-n','-P','--format=JobIDRaw,User,State,ExitCode'],capture_output=True,text=True,check=True,timeout=30)
    rows=[line.split('|') for line in q.stdout.splitlines() if line.split('|')[0]==job]
    assert len(rows)==1 and rows[0][1:4]==['zixiao','COMPLETED','0:0'],rows
out=ROOT/'report_control/retired_root_v5_final_report_20261015.json';assert not out.exists();save(out,{'identity':i,'status':s,'timestamp':time.time(),'action':'SIGTERM_VERIFIED_OWN_METADATA_ROOT_ONLY'})
os.kill(i['pid'],signal.SIGTERM)
print('VERIFIED_OWN_REPORT_ROOT_V5_RETIRED_ONLY')
