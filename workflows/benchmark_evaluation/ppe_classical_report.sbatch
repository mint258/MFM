#!/bin/bash
#SBATCH --job-name=PPE-native-classical-baseline-report
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:15:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/PPE_classical_report_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import csv,json,math,os
from pathlib import Path
from collections import defaultdict
import numpy as np
import pyarrow.parquet as pq
from workflows.benchmark_data.admission import protect
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,16*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe();out=b1/'PPE_classical_report'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
source_path=b1/'PPE_Benson/job_4536988/manifest.json';source=json.loads(source_path.read_text())
rows=pq.read_table(source['records']).to_pylist();records={r['record_id']:r for r in rows}
binding_path=b1/'reference_cv_binding/job_4536997/manifest.json';binding=json.loads(binding_path.read_text());spec=next(s for s in binding['source_groups'] if s['dataset']=='PPE1694')
proof=json.loads(Path(binding['full_inventory_scope_proof']).read_text());assert proof['deferred_registry_full_inventory_verified'] and proof['deferred_endpoint_count']==5
def finite(value):return value is not None and math.isfinite(value)
def eligible(row):return bool(row['retained'] and row['domain_eligible'])
methods={'BensonGA':'BensonGA_DeltaHf_kcal_mol','published_PM7':'published_PM7_DeltaHf_kcal_mol'}
output=[]
# This is the first actual reporting consumer of the native classical predictions.
for name,column in methods.items():
    for population in ('full_source_available','domain_retained_available'):
        selected=[r for r in rows if finite(r['experimental_DeltaHf_kcal_mol']) and finite(r[column]) and (population=='full_source_available' or eligible(r))]
        output.append(dict(dataset='PPE1694',evaluation='native_fixed_classical_baseline',population=population,method=name,target='experimental_DeltaHf',unit='kcal/mol',n_source_rows=len(rows),n_available=len(selected),MAE=float(np.mean([abs(r['experimental_DeltaHf_kcal_mol']-r[column]) for r in selected])) if selected else None,RAE_TRAIN_mean=None,reference_note='No TRAIN fit is used by these published physical predictors; TRAIN-mean RAE is reported separately on fixed CV folds'))
folds=defaultdict(lambda:defaultdict(list))
for row in pq.read_table(spec['scaffold_folds']).to_pylist():folds[(row['repetition'],row['fold'])][row['split']].append(row['record_id'])
for (repetition,fold),membership in sorted(folds.items()):
    for common in (False,True):
        for name,column in methods.items():
            available=lambda row:finite(row['experimental_DeltaHf_kcal_mol']) and finite(row[column]) and (not common or all(finite(row[c]) for c in methods.values()))
            for population in ('full_processable_source','domain_retained'):
                train=[records[k] for k in membership['train'] if available(records[k]) and (population=='full_processable_source' or eligible(records[k]))]
                test=[records[k] for k in membership['test'] if available(records[k]) and (population=='full_processable_source' or eligible(records[k]))]
                if not train or not test:
                    output.append(dict(dataset='PPE1694',evaluation='fixed_scaffold_CV',repetition=repetition,fold=fold,population=population,availability='both_classical_baselines_common' if common else 'native_method_available',method=name,status='EMPTY_NATIVE_POPULATION',n_train=len(train),n_test=len(test)));continue
                mean=float(np.mean([r['experimental_DeltaHf_kcal_mol'] for r in train]))
                errors=np.asarray([abs(r['experimental_DeltaHf_kcal_mol']-r[column]) for r in test]);reference=float(np.sum([abs(r['experimental_DeltaHf_kcal_mol']-mean) for r in test]))
                output.append(dict(dataset='PPE1694',evaluation='fixed_scaffold_CV',repetition=repetition,fold=fold,population=population,availability='both_classical_baselines_common' if common else 'native_method_available',method=name,target='experimental_DeltaHf',unit='kcal/mol',status='OK' if reference>0 else 'ZERO_TRAIN_REFERENCE_ERROR',n_train=len(train),n_test=len(test),training_mean=mean,MAE=float(errors.mean()),RAE_TRAIN_mean=float(errors.sum()/reference) if reference>0 else None))
fields=list(dict.fromkeys(k for row in output for k in row))
with (out/'PPE_native_classical_baselines.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(output)
report=dict(status='PPE_NATIVE_CLASSICAL_BASELINES_REPORTED',job=os.environ['SLURM_JOB_ID'],source_entry=str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),source_classical_predictions=str(source_path),source_cv_binding=str(binding_path),results=str(out/'PPE_native_classical_baselines.csv'),reported_rows=len(output),methods=methods,quantity='Original experimental gas-phase formation enthalpy in kcal/mol',residual_target_binding='B1 retains the original two residual endpoints; this table reports their fixed classical physical reference predictors and adds no candidate endpoint',new_Benson_fit=False,new_PM7_calculations=False,missing_native_predictions_filled=False,statistic_replay_or_independent_QA=False,B1_task_screen_decisions_produced=False)
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('PPE_CLASSICAL_BASELINE_REPORT_CLOSED',json.dumps(report),flush=True)

PY
