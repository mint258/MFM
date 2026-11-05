"""Three actually closed Native S training rows; TRAIN/VAL fields kept separate."""
from pathlib import Path
import csv,hashlib,json,subprocess
B=Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';O=B/'runs/model_v3_20261025';W=B/'MFM_model_v3_reporting_v3'
def read(p):return json.loads(p.read_bytes())
def ref(p):
 d=p.read_bytes();return dict(path=str(p),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())
def main():
 target=W/'docs/model_v3/results/native_S_segment_observations_20261027_v2.csv';proof=N/'native_S_closed_rows_20261027_v2_actual.json'
 assert not target.exists() and not proof.exists()
 source=W/'docs/model_v3/results/native_S_segment_observations_20261027_v1.csv'
 with source.open() as f:base=list(csv.DictReader(f))[1]
 argv=['sacct','-X','-n','-P','-j','4521438,4521459,4521485','--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
 r=subprocess.run(argv,capture_output=True,text=True,check=True,timeout=30);account={p[0]:p for line in r.stdout.splitlines() if (p:=line.split('|'))}
 rows=[];evidence=[]
 for slot,job,start,end in ((2,'4521438',0,1000),(3,'4521459',1000,2000),(4,'4521485',2000,3000)):
  root=N/f'native_S_B20k_v3/slots/slot_{slot:03d}';child=root/'child';closure=read(root/'management/ROOT_LONG_SEGMENT_CLOSURE.json');m=read(child/'member_result.json');summary=read(child/'SDK_expected_summary.json')
  vpath=N/f'native_S_slot{slot:03d}_SDK_actual_v2/0/VERIFICATION.json';v=read(vpath)
  a=account[job];assert a[:4]==[job,'zixiao','COMPLETED','0:0'] and a[5:7]==['16','compute-0-21']
  assert closure['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING' and closure['failure'] is None and closure['optimizer_updates']==end
  assert m['optimizer_updates']==end and m['tracker']['id']==v['run_id'] and v['status']=='ALL_SAVED_SCIENTIFIC_LOG_FIELDS_MATCHED' and v['full_config_summary_typed_exact'] is True
  val=m['validation'][str(end)]['metrics'];sup=read(root/'management/supervisor.json');assert sup['gpu_uuid']==base['gpu_uuid']
  row=dict(base);row.update(run_id=m['tracker']['id'],elapsed_seconds=a[4],status='COMPLETED',allocated_cpu_seconds=str(int(a[4])*int(a[5])),allocated_gpu_seconds=a[4],metric__job_id=job,metric__observed_optimizer_updates=end,metric__observed_base_samples=m['samples_consumed'],metric__accepted_closed_segment_updates=end-start,metric__observed_last_train_loss=summary['loss'],metric__SDK_full_readback_verified=1,metric__history_is_startup_observation=0,metric__segment_start_update=start,metric__segment_base_samples=m['segment_throughput']['base_records'],metric__val_noise_RMSE=val['s_noise/RMSE'],metric__val_noise_R2=val['s_noise/R2'],metric__val_noise_MAE=val['s_noise/MAE'],metric__val_element_accuracy=val['s_element/accuracy'],metric__val_bond_accuracy=val['s_bond/accuracy'],metric__segment_base_records_per_second=m['segment_throughput']['base_records_per_second'])
  assert summary['fields']['s_noise']['RMSE']==val['s_noise/RMSE']
  rows.append(row);evidence.append(dict(job_id=job,member=ref(child/'member_result.json'),validation_endpoint=str(end),expected_summary=ref(child/'SDK_expected_summary.json'),full_SDK_verification=ref(vpath),supervisor=ref(root/'management/supervisor.json'),closure=ref(root/'management/ROOT_LONG_SEGMENT_CLOSURE.json')))
 with target.open('x',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 result=dict(schema='model_v3_closed_native_S_rows_actual_v2',status='THREE_CLOSED_SEGMENTS_WITH_FULL_LOG_PROOFS',original_snapshot=ref(source),new_csv=ref(target),actual_accounting=dict(argv=argv,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr),evidence=evidence,semantic_note='VAL fields are member.validation[str(endpoint)].metrics, never merged top-level W&B summary TRAIN keys. Prior FAILED and startup snapshot preserved.',old_files_rewritten=False,scientific_B_acceptance=False)
 with proof.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(dict(csv=ref(target),proof=ref(proof),runs=[row['run_id'] for row in rows])))
if __name__=='__main__':main()