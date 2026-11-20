#!/bin/bash
#SBATCH --job-name=C1-Pprime_plus_D-pka-LightGBM
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=01:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_Pprime_plus_D_pKa_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import csv,json,math,os,unittest
from pathlib import Path
from collections import Counter,defaultdict
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

entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,256*1024**2,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'C1_Pprime_plus_D_LGBM'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
binding_path=b1/'pKa_macro/job_4536926/manifest.json';binding=json.loads(binding_path.read_text())
assert binding['status']=='MACRO_ENDPOINT_BINDING_FROZEN_BEFORE_FITS'
labels=pq.read_table(binding['records']).to_pylist();wanted={row['record_id'] for row in labels}
feature_root=b1/'C1_Pprime_features/job_4537124/Pprime_plus_D';native={}
for batch in pq.ParquetFile(feature_root/'pKahub.parquet').iter_batches(batch_size=2048):
    for row in batch.to_pylist():
        if row['record_id'] in wanted:
            if row['record_id'] in native:raise ValueError('Duplicate B0 native feature record identity')
            native[row['record_id']]=row
tasks=defaultdict(list);coverage=defaultdict(Counter)
for row in labels:
    endpoint=row['endpoint'];counts=coverage[endpoint];counts[row['fit_role']+'_source_labels']+=1
    feature=native.get(row['record_id'])
    if feature is None:counts['missing_native_Pprime_plus_D_source_link']+=1;continue
    if not (feature['retained'] and feature['domain_eligible']):counts['outside_domain']+=1;continue
    if feature['features'] is None or not any(feature['valid_mask'] or []):counts['missing_native_Pprime_plus_D']+=1;continue
    tasks[endpoint].append(dict(row,features=feature['features']))
results=[];failures=[]
pred_schema=pa.schema([('task',pa.string()),('challenge',pa.string()),('record_id',pa.string()),('rawdataID',pa.string()),('challenge_compound_id',pa.string()),('full_inchikey',pa.string()),('y_true',pa.float64()),('prediction',pa.float64()),('training_mean',pa.float64())])
for endpoint in ('acid','base'):
    rows=tasks[endpoint];train=[row for row in rows if row['fit_role']=='TRAIN'];test=[row for row in rows if row['fit_role']=='EXTERNAL_TEST']
    if not train or not test:
        failures.append({'endpoint':endpoint,'status':'EMPTY_TRAIN_OR_EXTERNAL_TEST'});continue
    safe();x=np.asarray([r['features'] for r in train],float);y=np.asarray([r['y'] for r in train],float)
    mean=float(y.mean());model=LGBMRegressor(random_state=SEED,n_jobs=1,verbosity=-1);model.fit(x,y)
    prediction=np.asarray(model.predict(np.asarray([r['features'] for r in test],float)),float)
    records=[{'task':endpoint,'challenge':r['challenge'],'record_id':r['record_id'],'rawdataID':r['rawdataID'],'challenge_compound_id':r['challenge_compound_id'],'full_inchikey':r['full_inchikey'],'y_true':r['y'],'prediction':float(p),'training_mean':mean} for r,p in zip(test,prediction)]
    safe();pq.write_table(pa.Table.from_pylist(records,schema=pred_schema),out/(endpoint+'_test_predictions.parquet'),compression='zstd')
    model.booster_.save_model(str(out/(endpoint+'_model.txt')))
    for challenge in ['SAMPL6_7_combined']+sorted({r['challenge'] for r in test}):
        selected=[i for i,r in enumerate(test) if challenge=='SAMPL6_7_combined' or r['challenge']==challenge]
        subset=[test[i] for i in selected]
        metric=score([r['y'] for r in subset],prediction[selected],mean,[r['full_inchikey'] for r in subset])
        results.append(dict(dataset='pKahub',task=endpoint,evaluation=challenge,model='LightGBM',feature_group='Pprime_plus_D',seed=SEED,n_train=len(train),feature_count=x.shape[1],**metric))
    print('C1_Pprime_plus_D_PKA_LGBM_ENDPOINT_CLOSED',endpoint,'n_train',len(train),'external_test',len(test),flush=True)
fields=list(dict.fromkeys(k for row in results for k in row))
with (out/'C1_Pprime_plus_D_LGBM_pKa_partial_results.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields or ['task']);writer.writeheader();writer.writerows(results)
report={'status':'C1_Pprime_plus_D_PKA_MACRO_LGBM_CLOSED','job':os.environ['SLURM_JOB_ID'],'infrastructure_continuation_of_job':4536932,'source_binding':str(binding_path),'native_Pprime_plus_D_source':str(feature_root/'manifest.json'),'macro_endpoints_expected':2,'macro_endpoints_completed':len({r['task'] for r in results}),'failures':failures,'coverage':{k:dict(v) for k,v in coverage.items()},'TRAIN_blind_overlap_exclusions':binding['TRAIN_exclusions'],'external_split':'Original SAMPL6 and SAMPL7; challenge + rawdataID link, full molecular InChIKey training exclusion','selection_used_TEST':False,'hyperparameter_search':False,'no_missing_native_Pprime_plus_D_imputation':True,'unit_tests':suite.countTestCases(),'C1_final_table':False,'atom_site_task_ready':False,'B1_task_screen_produced':False}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('C1_Pprime_plus_D_PKA_LGBM_CLOSED',out/'manifest.json',flush=True)

PY
