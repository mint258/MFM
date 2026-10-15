import json,os,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,save,sha
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
job='4515160'
q=subprocess.run(['sacct','-j',job,'-n','-P','--format=JobIDRaw,User,State,ExitCode'],capture_output=True,text=True,check=True,timeout=30)
rows=[line.split('|') for line in q.stdout.splitlines() if line.split('|')[0]==job]
assert len(rows)==1 and rows[0][1:4]==['zixiao','COMPLETED','0:0'],rows
receipt=json.loads((ROOT/'reports/current_experiment/artifact_validation.json').read_text())
tail=json.loads((ROOT/'reports/s_failed_tail_report_validation_v1.json').read_text())
assert receipt['job_id']==job and receipt['status']=='CURRENT_PROGRESS_REPORT_ARTIFACTS_PASS'
assert tail['job_id']==job and tail['status']=='ACTUAL_FAILED_TAIL_RETAINED_AND_COMMITTED_CURVE_EXCLUSION_PASS'
b=json.loads((ROOT/'report_control/binding_v3.json').read_text())
names=['scripts/report_s_experiment_current_v7.py','scripts/s_report_artifact_validate_v4.py','scripts/s_report_finish_root_v4.py','scripts/s_report_accounting_publish_v1.py','scripts/s_current_report_v7.sbatch','scripts/test_s_failed_tail_report_v1.py','scripts/submit.py','configs/s_probe_protocol_v2.json','cuda_recovery_v1/continuation_gate.json']
b['sources']=[{'path':str(ROOT/n),'sha256':sha(ROOT/n)} for n in names]
b['review'].update(actual_report_job=job,actual_state='COMPLETED',actual_exit_code='0:0',artifact_validation=receipt['status'],failed_tail_validation=tail['status'],complete_experiment=False)
p=ROOT/'report_control/binding_v4.json';assert not p.exists();save(p,b)
save(ROOT/'report_control'/('report_job_'+job+'.json'),{'actual_accounting':{'state':'COMPLETED','exit_code':'0:0'},'artifact_validation':receipt,'summary_sha256':sha(ROOT/'reports/current_experiment/summary.json'),'failed_tail_validation':tail})
print('REPORT_V4_BOUND_AFTER_ACTUAL_VALIDATION',job,sha(p))
