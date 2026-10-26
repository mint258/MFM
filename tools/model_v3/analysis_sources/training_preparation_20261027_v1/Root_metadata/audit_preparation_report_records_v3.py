import csv,hashlib,json,pathlib
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';O=B/'runs/model_v3_20261025';W=B/'MFM_model_v3_reporting_v3';R=W/'docs/model_v3/reports/training_preparation_20261027_v1'
def read(p):return json.loads(p.read_bytes())
def ref(p):
 d=p.read_bytes();return dict(path=str(p),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())
rows=list(csv.DictReader((N/'reporting_draft_native_S_observations_v1.csv').open()));assert len(rows)==2
ledger=read(O/'job_ledger_model_v3_active_v14.json');actual={x['job_id']:x for x in ledger['jobs']}
for row in rows:
 slot=1 if row['job_id']=='4521411' else 2;phase=N/'native_S_B20k_v3';frame=read(phase/f'control/attempts/slot_{slot:03d}.submitted.json');cfg=read(phase/f'slots/slot_{slot:03d}/child/configuration.json')
 assert row['job_id']==frame['actual_sbatch_job_id'] and row['config_sha256']==frame['configuration']['sha256']==ref(phase/'control/configuration.json')['sha256']
 assert row['operational_source_sha']==frame['package_manifest']['sha256'] and row['execution_code_sha']==frame['science_code_sha'] and row['public_scientific_sha']==frame['science_prereg_sha']
 assert row['data_manifest_sha']==cfg['source_inputs']['TRAIN']['manifest_sha256'] and row['wandb_run_id']==cfg['tracker']['id'] and row['seed']==str(frame['seed']) and row['precision']==frame['precision']
 assert row['gpu_uuid']==frame['native_member']['runtime']['gpu_uuid']
 found=False
 with (phase/f'slots/slot_{slot:03d}/child/history.jsonl').open() as stream:
  for text in stream:
   value=json.loads(text)['row']
   if value.get('event')=='TRAIN' and value.get('optimizer_updates')==int(row['observed_updates']):
    assert value['samples_consumed']==int(row['observed_base_samples']);found=True
    if row['last_train_loss_observed']:assert value['loss']==float(row['last_train_loss_observed'])
    break
 assert found and row['accepted_closed_segment_updates']=='0'
 if slot==1:assert actual[row['job_id']]['State']=='FAILED' and actual[row['job_id']]['ExitCode']==row['exit_code']=='1:0' and str(actual[row['job_id']]['elapsed_seconds'])==row['elapsed_parent_seconds']
qa=read(N/'native_S_B20k_v3/slots/slot_002/management/metadata_QA.json');assert qa['status']=='PASS_PENDING_SAME_MODEL_PARENT_TERMINAL' and qa['counts']==dict(tests=8,failures=0,errors=0,skipped=0) and ref(pathlib.Path(qa['actual_command']['path']))==qa['actual_command'] and read(pathlib.Path(qa['actual_command']['path']))['returncode']==0 and qa['sources_before']==qa['sources_after']
full=read(R/'evidence/numeric_full_regression_4521421_actual_closure_v1.json');assert full['test_counts']==dict(tests=2639,failures=0,errors=0,skipped=3) and full['passed']==2636
mat=read(R/'evidence/numeric_GPU_1429_1435_actual_closure_v1.json');assert mat['counts']==dict(tests=48,failures=38,errors=0,skipped=0) and mat['passed']==10 and mat['candidate_adopted'] is False
sync=read(R/'evidence/WandB_sync50_final_Root_closure.json');assert sync['accepted_count']==50 and sync['remaining_count']==0
import importlib.util
spec=importlib.util.spec_from_file_location('model_v3_repository_summary_format',W/'tools/check_repository.py');checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
typed_path=W/'docs/model_v3/results/native_S_segment_observations_20261027_v1.csv';assert checker.model_summary_csv(str(typed_path.relative_to(W)),typed_path.read_bytes())
typed=list(csv.DictReader(typed_path.open()));assert len(typed)==2
for original,row in zip(rows,typed):
 assert row['run_id']==original['wandb_run_id'] and row['stage']=='2' and row['config_sha256']==original['config_sha256'] and row['code_sha']==original['execution_code_sha'] and row['preregistration_sha']==original['public_scientific_sha'] and row['data_version']=='existing_native_S:'+original['data_manifest_sha'] and row['seed']==original['seed'] and row['gpu_uuid']==original['gpu_uuid']
 actual_row=actual[original['job_id']];assert row['status']==actual_row['State'] and float(row['elapsed_seconds'])==actual_row['elapsed_seconds'] and float(row['allocated_cpu_seconds'])==actual_row['allocated_cpu_seconds'] and row['metric__observed_optimizer_updates']==original['observed_updates'] and row['metric__observed_base_samples']==original['observed_base_samples'] and row['metric__accepted_closed_segment_updates']=='0' and row['metric__SDK_full_readback_verified']=='0'
old=read(N/'training_preparation_report_records_actual_v1.json');draft=N/'reporting_draft_native_S_observations_v1.csv';assert (ref(draft)['bytes'],ref(draft)['sha256'])==(old['training_CSV']['bytes'],old['training_CSV']['sha256'])
out=N/'training_preparation_report_records_actual_v2.json';v=dict(status='ACTUAL_METADATA_AND_TRAINING_CSV_VERIFIED',training_rows=2,full_counts=full['test_counts'],matrix_counts=mat['counts'],sync_verified=50,active_segment_has_no_C0_claim=True,report=ref(R/'PROGRESS.md'),training_CSV=ref(typed_path),preserved_checked_draft=ref(draft),prior_QA_snapshot=ref(N/'training_preparation_report_records_actual_v1.json'))
with out.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
print(json.dumps(v))