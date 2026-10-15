import json,os,socket,subprocess
from prepare import ROOT,save,sha
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
job='4515296'
q=subprocess.run(['sacct','-j',job,'-n','-P','--format=JobIDRaw,User,State,ExitCode'],capture_output=True,text=True,check=True,timeout=30)
rows=[line.split('|') for line in q.stdout.splitlines() if line.split('|')[0]==job]
assert len(rows)==1 and rows[0][1:4]==['zixiao','COMPLETED','0:0'],rows
receipt=json.loads((ROOT/'reports/current_experiment/artifact_validation.json').read_text())
tail=json.loads((ROOT/'reports/s_failed_tail_report_validation_v3.json').read_text())
estimate=json.loads((ROOT/'reports/s_epoch_estimate_validation_v1.json').read_text())
assert receipt['job_id']==job and receipt['status']=='CURRENT_PROGRESS_REPORT_ARTIFACTS_PASS'
assert tail['job_id']==job and tail['status']=='ACTUAL_FAILED_TAIL_RETAINED_AND_COMMITTED_CURVE_EXCLUSION_PASS'
assert estimate['job_id']==job and estimate['status']=='S_CURVE_ESTIMATE_BOUNDARIES_AND_UNCHANGED_SCIENTIFIC_JUDGMENT_PASS'
b=json.loads((ROOT/'report_control/binding_v5.json').read_text())
names=['scripts/report_s_experiment_current_v9.py','scripts/s_epoch_estimate_v1.py','scripts/s_report_artifact_validate_v6.py','scripts/s_report_finish_root_v6.py','scripts/s_report_accounting_publish_v1.py','scripts/s_current_report_v9.sbatch','scripts/test_s_failed_tail_report_v3.py','scripts/test_s_epoch_estimate_v1.py','scripts/submit.py','configs/s_probe_protocol_v2.json','cuda_recovery_v1/continuation_gate.json','scripts/check_s_report_publication_race_guard_v1.py','reports/s_report_publication_race_guard_validation_v1.json']
b['sources']=[{'path':str(ROOT/n),'sha256':sha(ROOT/n)} for n in names]
b['review'].update(actual_report_job=job,actual_state='COMPLETED',actual_exit_code='0:0',artifact_validation=receipt['status'],failed_tail_validation=tail['status'],epoch_estimation_validation=estimate['status'],first_page_visual_review='Five required items, readable, no overlap in actual first_page.png; final still requires final artifact review',complete_experiment=False)
p=ROOT/'report_control/binding_v6.json';assert not p.exists();save(p,b)
save(ROOT/'report_control'/('report_job_'+job+'.json'),{'actual_accounting':{'state':'COMPLETED','exit_code':'0:0'},'artifact_validation':receipt,'summary_sha256':sha(ROOT/'reports/current_experiment/summary.json'),'failed_tail_validation':tail,'epoch_estimation_validation':estimate})
print('REPORT_V6_BOUND_AFTER_ACTUAL_VALIDATION',job)
