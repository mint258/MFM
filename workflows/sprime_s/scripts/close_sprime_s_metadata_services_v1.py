"""Close actual accounting and only this experiment's verified metadata publisher."""
import json,os,signal,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,save,sha
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
accepted=json.loads((ROOT/'reports/final_experiment_acceptance.json').read_text());assert accepted['status']=='FULL_EXPERIMENT_ACCEPTED'
ids=set()
for path in (ROOT/'submission').glob('*.json'):
    value=json.loads(path.read_text())
    if isinstance(value,dict) and value.get('job_id'):ids.add(str(value['job_id']))
q=subprocess.run(['sacct','-j',','.join(sorted(ids)),'-n','-P','--format=JobIDRaw,User,Start,End,ElapsedRaw,State,ExitCode,AllocCPUS,NodeList'],capture_output=True,text=True,check=True,timeout=60)
parents={row[0]:row for line in q.stdout.splitlines() if (row:=line.split('|'))[0] in ids}
assert set(parents)==ids and all(row[1]=='zixiao' for row in parents.values())
terminal={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}
assert all(row[5].split()[0] in terminal for row in parents.values())
out=ROOT/'reports/final_sacct_timing_snapshot_20261015.json';assert not out.exists()
save(out,{'status':'ACTUAL_ALL_TASK_REGISTERED_SLURM_PARENTS_TERMINAL','timestamp':time.time(),'parents':parents,'raw_sacct_stdout':q.stdout,'allocated_core_hours_all_registered_work_including_failures':sum(int(row[4])*int(row[7])/3600 for row in parents.values()),'source_sha256':sha(__file__)})
i=json.loads((ROOT/'formal_s/report_accounting_publisher_identity_v1.json').read_text());assert i['pid']==4014920 and i['uid']==1278
p=Path('/proc')/str(i['pid']);assert p.stat().st_uid==i['uid']
assert (p/'stat').read_text().split()[21]==i['proc_start_ticks']
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==i['boot_id']
assert b's_report_accounting_publish_v1.py' in (p/'cmdline').read_bytes()
assert sha(ROOT/'scripts/s_report_accounting_publish_v1.py')==i['source_sha256']
snapshot=ROOT/'formal_s/report_accounting_final_snapshot.json';assert not snapshot.exists();snapshot.write_bytes((ROOT/'formal_s/report_accounting_latest.json').read_bytes())
os.kill(i['pid'],signal.SIGTERM)
save(ROOT/'reports/own_metadata_services_closed_20261015.json',{'status':'EXPERIMENT_ACCEPTED_OWN_METADATA_PUBLISHER_RETIRED','timestamp':time.time(),'publisher_identity':i,'actual_terminal_accounting_snapshot':str(out),'frozen_last_publication_sha256':sha(snapshot),'training_probe_report_roots_completed_normally':True,'other_project_tasks_or_mounts_touched':False})
print('ALL_TASK_REGISTERED_SLURM_PARENTS_TERMINAL_OWN_PUBLISHER_RETIRED',len(parents))
