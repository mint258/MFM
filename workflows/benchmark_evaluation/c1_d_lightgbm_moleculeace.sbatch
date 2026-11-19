#!/bin/bash
#SBATCH --job-name=C1-D-LGBM-MoleculeACE
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_D_LGBM_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import csv,json,math,os,unittest,importlib.metadata
from collections import defaultdict
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from lightgbm import LGBMRegressor
from workflows.benchmark_data.admission import protect
SEED=20261025
def score(y,prediction,train_mean,groups,draws=1000):
    y=np.asarray(y,float);prediction=np.asarray(prediction,float);groups=np.asarray(groups)
    if y.ndim!=1 or y.shape!=prediction.shape or y.shape!=groups.shape or not len(y):raise ValueError('Unaligned evaluation rows')
    if not np.isfinite(y).all() or not np.isfinite(prediction).all() or not math.isfinite(train_mean):raise ValueError('Nonfinite labels or predictions')
    unique,inverse=np.unique(groups,return_inverse=True)
    error=np.abs(y-prediction);reference=np.abs(y-train_mean)
    numerator=np.bincount(inverse,weights=error,minlength=len(unique))
    denominator=np.bincount(inverse,weights=reference,minlength=len(unique))
    total=float(denominator.sum())
    result={'MAE':float(error.mean()),'RAE':None,'RAE_CI95_low':None,'RAE_CI95_high':None,'n_test_rows':len(y),'n_test_molecules':len(unique),'bootstrap_draws':draws,'undefined_bootstrap_draws':0}
    if total<=0:return dict(result,metric_status='ZERO_TRAIN_MEAN_REFERENCE_ERROR')
    result['RAE']=float(numerator.sum()/total)
    rng=np.random.default_rng(SEED);values=[]
    for _ in range(draws):
        sample=rng.integers(0,len(unique),size=len(unique));divisor=float(denominator[sample].sum())
        if divisor<=0:result['undefined_bootstrap_draws']+=1
        else:values.append(float(numerator[sample].sum()/divisor))
    if result['undefined_bootstrap_draws']:return dict(result,metric_status='UNDEFINED_BOOTSTRAP_REFERENCE_DRAWS')
    result['RAE_CI95_low'],result['RAE_CI95_high']=map(float,np.quantile(values,[.025,.975]))
    return dict(result,metric_status='OK')
class StatisticTests(unittest.TestCase):
    def test_atom_or_repeat_rows_cluster_by_molecule(self):
        y=np.tile([0.,2.],40);prediction=y+.2;groups=np.repeat(np.arange(40),2)
        result=score(y,prediction,1.,groups)
        self.assertEqual(result['n_test_molecules'],40)
        self.assertAlmostEqual(result['RAE'],.2)
        self.assertAlmostEqual(result['RAE_CI95_low'],.2)
        self.assertAlmostEqual(result['RAE_CI95_high'],.2)
    def test_zero_reference_is_not_fabricated(self):
        result=score([1.,1.],[1.1,1.2],1.,['a','b'])
        self.assertIsNone(result['RAE'])
        self.assertEqual(result['metric_status'],'ZERO_TRAIN_MEAN_REFERENCE_ERROR')
    def test_missing_prediction_does_not_change_population(self):
        with self.assertRaises(ValueError):score([1.],[float('nan')],0.,['a'])
    def test_training_mean_is_used_without_test_refitting(self):
        result=score([2.,4.],[1.,3.],0.,['a','b'])
        self.assertAlmostEqual(result['RAE'],1/3)
suite=unittest.defaultTestLoader.loadTestsFromTestCase(StatisticTests)
if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())
root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,256*1024**2,quota,own_concurrent_bytes=24*1024**3)
safe()
feature_root=b1/'C1_D_features/job_4536892'
feature_contract=json.loads((feature_root/'manifest.json').read_text())
assert feature_contract['model_fits_run'] is False
proof=json.loads(Path(feature_contract['full_inventory_scope_proof']).read_text())
assert proof['deferred_registry_full_inventory_verified']
out=b1/'C1_D_LGBM'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
models=out/'models';models.mkdir()
tasks=defaultdict(list);coverage=defaultdict(lambda:defaultdict(int))
for batch in pq.ParquetFile(feature_root/'MoleculeACE.parquet').iter_batches(batch_size=2048):
    for row in batch.to_pylist():
        task=row['source_file'];coverage[task]['source_rows']+=1
        if not row['retained'] or not row['domain_eligible']:coverage[task]['outside_domain']+=1;continue
        if row['features'] is None or not any(row['valid_mask'] or []):coverage[task]['missing_native_D']+=1;continue
        raw=json.loads(row['original_fields_json'])
        try:y=float(raw['y'])
        except (ValueError,TypeError,KeyError):coverage[task]['missing_or_unparsed_target']+=1;continue
        if not math.isfinite(y):coverage[task]['missing_or_unparsed_target']+=1;continue
        if not row['full_inchikey']:coverage[task]['unresolved_molecule_identity']+=1;continue
        split=str(row['official_split'] or '').strip().casefold()
        if split not in ('train','test'):coverage[task]['unresolved_official_split']+=1;continue
        tasks[task].append(dict(row,y=y,split=split))
expected=proof['candidate_counts_by_source_group']['MoleculeACE']
assert len(coverage)==expected
results=[];failures=[]
prediction_schema=pa.schema([('task',pa.string()),('record_id',pa.string()),('full_inchikey',pa.string()),('y_true',pa.float64()),('prediction',pa.float64()),('training_mean',pa.float64())])
with pq.ParquetWriter(out/'test_predictions.parquet',prediction_schema,compression='zstd') as sink:
    for task in sorted(coverage):
        safe();rows=tasks.get(task,[])
        train=[r for r in rows if r['split']=='train'];test=[r for r in rows if r['split']=='test']
        if not train or not test:
            failures.append({'task':task,'status':'UNRESOLVED_OFFICIAL_LABEL_OR_FEATURE_BINDING','coverage':dict(coverage[task])});continue
        x_train=np.asarray([r['features'] for r in train],dtype=np.float64)
        y_train=np.asarray([r['y'] for r in train],dtype=np.float64)
        x_test=np.asarray([r['features'] for r in test],dtype=np.float64)
        y_test=np.asarray([r['y'] for r in test],dtype=np.float64)
        model=LGBMRegressor(random_state=SEED,n_jobs=2,verbosity=-1)
        model.fit(x_train,y_train)
        prediction=np.asarray(model.predict(x_test),dtype=np.float64)
        training_mean=float(y_train.mean())
        metrics=score(y_test,prediction,training_mean,[r['full_inchikey'] for r in test])
        result=dict(task=task,dataset='MoleculeACE',model='LightGBM',feature_group='D',seed=SEED,n_train=len(train),feature_count=x_train.shape[1],**metrics)
        results.append(result)
        safe()
        sink.write_table(pa.Table.from_pylist([{'task':task,'record_id':r['record_id'],'full_inchikey':r['full_inchikey'],'y_true':r['y'],'prediction':float(p),'training_mean':training_mean} for r,p in zip(test,prediction)],schema=prediction_schema))
        model.booster_.save_model(str(models/(Path(task).stem+'.txt')))
        print('C1_D_LGBM_TASK_CLOSED',task,json.dumps(result),flush=True)
with (out/'C1_D_LGBM_MoleculeACE_partial_results.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(results[0]) if results else ['task']);writer.writeheader();writer.writerows(results)
report={'status':'C1_D_LGBM_MOLECULEACE_SOURCE_CLOSED','job':os.environ['SLURM_JOB_ID'],'unit_tests':suite.countTestCases(),'source_contract':str(feature_root/'manifest.json'),'model_version':importlib.metadata.version('lightgbm'),'default_model_parameters':LGBMRegressor(random_state=SEED,n_jobs=2,verbosity=-1).get_params(),'tasks_expected':expected,'tasks_completed':len(results),'task_failures':failures,'coverage':{k:dict(v) for k,v in coverage.items()},'selection_used_TEST':False,'hyperparameter_search':False,'missing_feature_imputation':False,'training_mean_source':'C1 eligible original official TRAIN rows only','statistics':'1000 molecule-clustered bootstrap draws, no test-mean normalization','C1_final_table':False,'B1_task_screen_decisions_produced':False}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('C1_D_LGBM_SOURCE_CLOSED',out/'manifest.json','completed',len(results),'of',expected,flush=True)
PY
