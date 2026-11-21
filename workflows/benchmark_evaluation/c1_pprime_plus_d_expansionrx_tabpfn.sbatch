#!/bin/bash
#SBATCH --job-name=C1-Pprime_plus_D-expansionrx-TabPFN
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_Pprime_plus_D_ExpansionRx_%j.log
set -euo pipefail
export C1_MODEL=TabPFN-V2
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export TABPFN_ALLOW_CPU_LARGE_DATASET=1 LOKY_MAX_CPU_COUNT=2
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/tabpfn_job_4536852/venv/bin/python -B - <<'PY'
import csv,json,math,os,time,signal,threading,tempfile,gc,unittest,traceback,importlib.metadata
from pathlib import Path
from collections import defaultdict,Counter
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


def eligible(row):return bool(row['retained'] and row['domain_eligible'])
def has_native_Pprime_plus_D(row):return row['features'] is not None and any(row['valid_mask'] or [])
def prediction_policy(rows):
    native=[];outside=[];missing=[]
    for index,row in enumerate(rows):
        if not eligible(row):outside.append(index)
        elif not has_native_Pprime_plus_D(row):missing.append(index)
        else:native.append(index)
    return native,outside,missing
class BlindNativeFeatureTests(unittest.TestCase):
    def test_all_blind_TEST_rows_have_an_explicit_prediction_policy(self):
        rows=[dict(retained=True,domain_eligible=True,features=[1.,float('nan')],valid_mask=[True,False]),dict(retained=True,domain_eligible=False,features=None,valid_mask=None),dict(retained=True,domain_eligible=True,features=None,valid_mask=None)]
        self.assertEqual(prediction_policy(rows),([0],[1],[2]))
    def test_partial_native_Pprime_plus_D_is_not_replaced_or_imputed(self):
        row=dict(retained=True,domain_eligible=True,features=[1.,float('nan')],valid_mask=[True,False])
        self.assertTrue(has_native_Pprime_plus_D(row));self.assertTrue(math.isnan(row['features'][1]))
tests=unittest.defaultTestLoader.loadTestsFromTestCase(BlindNativeFeatureTests)
if not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,1024**3,quota,own_concurrent_bytes=40*1024**3)
safe();out=b1/'C1_Pprime_plus_D_ExpansionRx'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
tmp=out/'tmp';tmp.mkdir();os.environ['TMPDIR']=str(tmp);tempfile.tempdir=str(tmp)
def watch():
    while True:
        time.sleep(10)
        try:safe()
        except BaseException:os.kill(os.getpid(),signal.SIGTERM)
threading.Thread(target=watch,daemon=True).start()
model_name=os.environ.get('C1_MODEL','LightGBM')
if model_name not in ('LightGBM','TabPFN-V2'):raise ValueError('Unknown C1 model')
binding_path=b1/'ExpansionRx_release_binding/job_4537017/manifest.json';binding=json.loads(binding_path.read_text())
proof=json.loads(Path(binding['scope_proof']).read_text());assert proof['deferred_registry_full_inventory_verified'] and proof['deferred_endpoint_count']==5
feature_root=b1/'C1_Pprime_features/job_4537124/Pprime_plus_D';features={r['record_id']:r for r in pq.read_table(feature_root/'ExpansionRx.parquet').to_pylist()}
tasks=defaultdict(list)
for label in pq.read_table(binding['official_endpoint_labels']).to_pylist():
    row=features[label['record_id']]
    tasks[label['task']].append(dict(row,y=label['y'],split=label['official_split'],full_inchikey=label['original_full_inchikey']))
assert len(tasks)==9
schema=pa.schema([('dataset',pa.string()),('task',pa.string()),('model',pa.string()),('feature_group',pa.string()),('record_id',pa.string()),('full_inchikey',pa.string()),('y_true',pa.float64()),('prediction',pa.float64()),('training_mean',pa.float64()),('retained',pa.bool_()),('domain_eligible',pa.bool_()),('prediction_origin',pa.string())])
results=[];failures=[];coverage=[];failure_count=0
for task in sorted(tasks):
    rows=tasks[task];train=[r for r in rows if r['split']=='train' and eligible(r) and has_native_Pprime_plus_D(r)];test=[r for r in rows if r['split']=='test']
    native,outside,missing=prediction_policy(test);coverage.append(dict(task=task,original_blind_TEST_points=len(test),C1_TRAIN_points=len(train),TEST_native_feature_points=len(native),TEST_outside_mean_fallback_points=len(outside),TEST_missing_native_Pprime_plus_D_points=len(missing)))
    if failure_count>=2:failures.append(dict(task=task,status='UNRESOLVED_AFTER_TWO_MODEL_TASK_FAILURES'));continue
    try:
        if not train or not test:raise ValueError('Empty fixed official C1 train or test')
        x=np.asarray([r['features'] for r in train],float);y=np.asarray([r['y'] for r in train],float);mean=float(y.mean());subsample=False
        if model_name=='LightGBM':model=LGBMRegressor(random_state=SEED,n_jobs=2,verbosity=-1)
        else:
            from tabpfn import TabPFNRegressor
            from tabpfn.constants import ModelVersion
            checkpoint=b1/'smoke100/job_4536865/model_cache/tabpfn-v2-regressor.ckpt';subsample=len(train)>10000
            model=TabPFNRegressor.create_default_for_version(ModelVersion.V2,device='cpu',model_path=str(checkpoint),random_state=SEED,n_preprocessing_jobs=2,inference_config={'SUBSAMPLE_SAMPLES':10000} if subsample else None,ignore_pretraining_limits=subsample)
        safe();model.fit(x,y);prediction=np.full(len(test),np.nan,float);prediction[outside]=mean
        if native:prediction[native]=np.asarray(model.predict(np.asarray([test[i]['features'] for i in native],float)),float)
        available=np.asarray(native+outside,dtype=int)
        if len(available) and not np.isfinite(prediction[available]).all():raise ValueError('Nonfinite C1 prediction on native features or fixed fallback')
        metric=score([test[i]['y'] for i in available],prediction[available],mean,[test[i]['full_inchikey'] for i in available]) if len(available) else dict(metric_status='NO_AVAILABLE_C1_PREDICTIONS')
        result=dict(dataset='ExpansionRx',task=task,model=model_name,feature_group='Pprime_plus_D',seed=SEED,n_train=len(train),feature_count=x.shape[1],original_blind_TEST_points=len(test),n_TEST_missing_native_Pprime_plus_D=len(missing),n_TEST_outside_mean_fallback=len(outside),official_blind_population_complete=not missing,evaluation_population='blind_full' if not missing else 'AVAILABLE_C1_FEATURES_PARTIAL_DIAGNOSTIC',subsampling_ensemble=subsample,context_cap=10000 if subsample else len(train),**metric)
        if missing:result['metric_status']='PARTIAL_C1_NATIVE_FEATURES_MISSING_NOT_IMPUTED'
        records=[]
        for index,row in enumerate(test):
            origin='OUTSIDE_DOMAIN_TRAIN_MEAN' if index in outside else 'C1_NATIVE_FEATURES_MISSING' if index in missing else 'MODEL_NATIVE_D'
            records.append(dict(dataset='ExpansionRx',task=task,model=model_name,feature_group='Pprime_plus_D',record_id=row['record_id'],full_inchikey=row['full_inchikey'],y_true=row['y'],prediction=None if index in missing else float(prediction[index]),training_mean=mean,retained=row['retained'],domain_eligible=row['domain_eligible'],prediction_origin=origin))
        safe();taskdir=out/('task_%02d'%len(results));taskdir.mkdir()
        pq.write_table(pa.Table.from_pylist(records,schema=schema),taskdir/'predictions.parquet',compression='zstd')
        (taskdir/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        if model_name=='LightGBM':model.booster_.save_model(str(taskdir/'model.txt'))
        results.append(result);del model;gc.collect();print('C1_Pprime_plus_D_EXPANSIONRX_TASK_CLOSED',model_name,task,'TEST_points',len(test),'native_Pprime_plus_D_missing',len(missing),flush=True)
    except Exception as error:
        failure_count+=1;failures.append(dict(task=task,status='UNRESOLVED',error=repr(error)));traceback.print_exc()
fields=list(dict.fromkeys(k for row in results for k in row))
with (out/'C1_Pprime_plus_D_ExpansionRx_partial_results.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields or ['task']);writer.writeheader();writer.writerows(results)
report=dict(status='C1_Pprime_plus_D_EXPANSIONRX_OFFICIAL_NINE_ENDPOINTS_CLOSED',job=os.environ['SLURM_JOB_ID'],model=model_name,source_entry=str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),source_binding=str(binding_path),native_Pprime_plus_D_source=str(feature_root/'manifest.json'),tasks_expected=9,tasks_completed=len(results),failures=failures,coverage=coverage,new_unit_tests=suite.countTestCases()+tests.countTestCases(),TEST_rows_preserved_in_prediction_artifacts=True,TEST_domain_filter_applied=False,missing_native_features_not_imputed=True,missing_in_domain_native_Pprime_plus_D_predictions='Null with explicit availability; only partial diagnostic score, no claim of a complete leaderboard result',outside_domain_fallback='Arithmetic mean of eligible available-feature original TRAIN labels',statistics='1000 full-molecule grouped bootstrap draws, original units and TRAIN-mean reference; official log/TEST-mean metrics remain separate',hyperparameter_search=False,TEST_used_for_selection=False,C1_final_table=False,B1_task_screen_decisions_produced=False,independent_numeric_readback=False)
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('C1_Pprime_plus_D_EXPANSIONRX_SOURCE_CLOSED',out/'manifest.json','tasks',len(results),'failures',len(failures),flush=True)

PY
