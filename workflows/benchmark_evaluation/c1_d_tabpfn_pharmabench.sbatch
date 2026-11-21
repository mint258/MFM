#!/bin/bash
#SBATCH --job-name=C1-D-TabPFN-PharmaBench
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_D_TABPFN_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export TABPFN_ALLOW_CPU_LARGE_DATASET=1 LOKY_MAX_CPU_COUNT=2
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/tabpfn_job_4536852/venv/bin/python -B - <<'PY'
import csv,json,math,os,unittest,importlib.metadata
from collections import defaultdict
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch,gc,tempfile,threading,time,signal
from tabpfn import TabPFNRegressor,TabPFNClassifier
from tabpfn.constants import ModelVersion
torch.set_num_threads(2)
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
def safe():protect(root,1024**3,quota,own_concurrent_bytes=24*1024**3)
safe()
feature_root=b1/'C1_D_features/job_4536892'
feature_contract=json.loads((feature_root/'manifest.json').read_text())
assert feature_contract['model_fits_run'] is False
proof=json.loads(Path(feature_contract['full_inventory_scope_proof']).read_text())
assert proof['deferred_registry_full_inventory_verified']
out=b1/'C1_D_TABPFN'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
temp=out/'tmp';temp.mkdir();os.environ['TMPDIR']=str(temp);tempfile.tempdir=str(temp)
checkpoint=b1/'smoke100/job_4536865/model_cache/tabpfn-v2-regressor.ckpt'
def capacity_watch():
    while True:
        time.sleep(10)
        try:safe()
        except BaseException:
            print('C1_CAPACITY_STOP_OWN_PROCESS',flush=True);os.kill(os.getpid(),signal.SIGTERM)
threading.Thread(target=capacity_watch,daemon=True).start()

import urllib.request,urllib.error
classifier_checkpoint=out/'tabpfn-v2-classifier.ckpt'
classifier_access=[]
for host in ('https://huggingface.co','https://hf-mirror.com'):
    try:
        safe()
        url=host+'/Prior-Labs/TabPFN-v2-clf/resolve/main/tabpfn-v2-classifier.ckpt'
        with urllib.request.urlopen(url,timeout=60) as response:
            size=response.headers.get('Content-Length')
            if size is not None and int(size)>512*1024**2:raise ValueError('Classifier checkpoint exceeds forecast')
            partial=out/('classifier_'+str(len(classifier_access))+'.partial')
            with partial.open('xb') as stream:
                total=0
                while True:
                    block=response.read(4*1024**2)
                    if not block:break
                    total+=len(block)
                    if total>512*1024**2:raise ValueError('Classifier checkpoint exceeds forecast')
                    safe();stream.write(block)
        partial.rename(classifier_checkpoint)
        classifier_access.append({'host':host,'status':'DOWNLOADED','bytes':total});break
    except Exception as error:classifier_access.append({'host':host,'status':'FAILED','error_type':type(error).__name__})
print('TABPFN_V2_CLASSIFIER_WEIGHT_ACCESS',json.dumps(classifier_access),flush=True)
tasks=defaultdict(list);coverage=defaultdict(lambda:defaultdict(int))
for batch in pq.ParquetFile(feature_root/'PharmaBench.parquet').iter_batches(batch_size=2048):
    for row in batch.to_pylist():
        task=row['source_file'];coverage[task]['source_rows']+=1
        if not row['retained'] or not row['domain_eligible']:coverage[task]['outside_domain']+=1;continue
        if row['features'] is None or not any(row['valid_mask'] or []):coverage[task]['missing_native_D']+=1;continue
        raw=json.loads(row['original_fields_json'])
        try:y=float(raw['value'])
        except (ValueError,TypeError,KeyError):coverage[task]['missing_or_unparsed_target']+=1;continue
        if not math.isfinite(y):coverage[task]['missing_or_unparsed_target']+=1;continue
        if not row['full_inchikey']:coverage[task]['unresolved_molecule_identity']+=1;continue
        split=str(row['official_split'] or '').strip().casefold()
        if split not in ('train','test'):coverage[task]['unresolved_official_split']+=1;continue
        tasks[task].append(dict(row,y=y,split=split))
expected=proof['candidate_counts_by_source_group']['PharmaBench']
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
        subsample = len(train)>10000
        classifier='_cls_' in Path(task).name
        if classifier and (not classifier_checkpoint.is_file() or set(y_train)!={0.,1.} or set(y_test)-{0.,1.}):
            failures.append({'task':task,'status':'UNRESOLVED_CLASSIFIER_WEIGHTS_OR_BINARY_LABEL_BINDING'});continue
        model=(TabPFNClassifier if classifier else TabPFNRegressor).create_default_for_version(ModelVersion.V2,device='cpu',model_path=str(classifier_checkpoint if classifier else checkpoint),random_state=SEED,n_preprocessing_jobs=2,inference_config={'SUBSAMPLE_SAMPLES':10000} if subsample else None,ignore_pretraining_limits=subsample)
        model.fit(x_train,y_train)
        prediction=np.asarray(model.predict_proba(x_test)[:,list(model.classes_).index(1.)] if classifier else model.predict(x_test),dtype=np.float64)
        training_mean=float(y_train.mean())
        metrics=score(y_test,prediction,training_mean,[r['full_inchikey'] for r in test])
        result=dict(task=task,dataset='PharmaBench',model='TabPFN-V2',feature_group='D',seed=SEED,n_train=len(train),feature_count=x_train.shape[1],subsampling_ensemble=subsample,context_cap=10000 if subsample else len(train),task_type='binary_classification' if classifier else 'regression',**metrics)
        results.append(result)
        safe()
        sink.write_table(pa.Table.from_pylist([{'task':task,'record_id':r['record_id'],'full_inchikey':r['full_inchikey'],'y_true':r['y'],'prediction':float(p),'training_mean':training_mean} for r,p in zip(test,prediction)],schema=prediction_schema))
        del model;gc.collect()
        print('C1_D_TABPFN_TASK_CLOSED',task,json.dumps(result),flush=True)
with (out/'C1_D_TABPFN_PharmaBench_partial_results.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(results[0]) if results else ['task']);writer.writeheader();writer.writerows(results)
report={'status':'C1_D_TABPFN_MOLECULEACE_SOURCE_CLOSED','job':os.environ['SLURM_JOB_ID'],'unit_tests':suite.countTestCases(),'source_contract':str(feature_root/'manifest.json'),'model_version':importlib.metadata.version('tabpfn'),'checkpoint_release':'V2','regression_checkpoint':str(checkpoint),'classifier_checkpoint':str(classifier_checkpoint),'classifier_weight_access_attempts':classifier_access,'default_model_parameters':'Official V2 defaults, random_state=20261025, CPU; official per-estimator SUBSAMPLE_SAMPLES=10000 ensemble only if training population exceeds the V2 context limit','tasks_expected':expected,'tasks_completed':len(results),'task_failures':failures,'coverage':{k:dict(v) for k,v in coverage.items()},'selection_used_TEST':False,'hyperparameter_search':False,'missing_feature_imputation':False,'training_mean_source':'C1 eligible original official TRAIN rows only','statistics':'1000 molecule-clustered bootstrap draws, no test-mean normalization','C1_final_table':False,'B1_task_screen_decisions_produced':False}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('C1_D_TABPFN_SOURCE_CLOSED',out/'manifest.json','completed',len(results),'of',expected,flush=True)
PY
