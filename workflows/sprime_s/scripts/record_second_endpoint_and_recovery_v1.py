import json,os,socket,subprocess,time
from prepare import ROOT,save,sha
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
point='B3_seed0_e0p5'
hpath=ROOT/'probe_h0_v1'/point/'receipt.json';lpath=ROOT/'probe_results_v2'/point/'receipt.json'
h=json.loads(hpath.read_text());lp=json.loads(lpath.read_text())
assert h['status']=='ALL_FIVE_FROZEN_H0_DATASETS_CLOSED' and not h['development_only']
assert h['encoder_parameters_and_buffers_unchanged']
assert lp['status']=='ALL_FORTY_ONE_FROZEN_LINEAR_PROBE_CELLS_CLOSED'
assert len(lp['cells'])==41 and len(lp['aggregate'])==35 and lp['primary_tasks']==32
assert all(row['primary_metric'] is not None for row in lp['aggregate'])
assert lp['expansion_official_test_rows_used_for_training'] is False
checkpoint=lp['encoder_checkpoint'];assert sha(checkpoint['path'])==checkpoint['sha256']
assert checkpoint==h['checkpoint_reference'] and checkpoint['consumed_records']==5552386
jobs=['4515159',h['job_id'],lp['job_id'],'4515172']
q=subprocess.run(['sacct','-j',','.join(jobs),'-n','-P','--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,NodeList'],capture_output=True,text=True,check=True,timeout=30)
parents={r[0]:r for line in q.stdout.splitlines() if (r:=line.split('|'))[0] in jobs}
assert set(parents)==set(jobs)
assert all(r[1:4]==['zixiao','COMPLETED','0:0'] for r in parents.values())
s=json.loads((ROOT/'s_training/B1_seed1/segment_4515159/summary.json').read_text())
assert s['consumed_records']==6440960 and s['optimizer_updates']==15812 and not s['scientific_stop']
assert sha(s['final_checkpoint']['path'])==s['final_checkpoint']['sha256']
report=json.loads((ROOT/'reports/current_experiment/summary.json').read_text())
assert report['one_epoch_judgment']=='NOT_YET_EVALUABLE'
validation=json.loads((ROOT/'reports/current_experiment/artifact_validation.json').read_text())
assert validation['job_id']=='4515172' and validation['status']=='CURRENT_PROGRESS_REPORT_ARTIFACTS_PASS'
out=ROOT/'reports/second_formal_probe_and_cuda_recovery_closed_20261014_v1.json';assert not out.exists()
save(out,{'status':'SECOND_REAL_PROBE_ENDPOINT_AND_AUDITED_CUDA_RECOVERY_SEGMENT_CLOSED','timestamp':time.time(),'endpoint':point,'checkpoint':checkpoint,'h0_receipt':{'path':str(hpath),'sha256':sha(hpath)},'linear_receipt':{'path':str(lpath),'sha256':sha(lpath)},'cells':41,'all_tasks':35,'primary_tasks':32,'missing_task_aggregates':0,'actual_sacct_parents':parents,'recovered_B1_seed1':{'records':6440960,'optimizer_updates':15812,'checkpoint':s['final_checkpoint'],'scientific_stop':False},'one_epoch_judgment':report['one_epoch_judgment'],'complete_experiment':False,'report_validation':validation})
print('SECOND_REAL_ENDPOINT_AND_RECOVERY_SEGMENT_CLOSED_NOT_FULL_EXPERIMENT')
