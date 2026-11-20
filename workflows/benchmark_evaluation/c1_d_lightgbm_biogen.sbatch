#!/bin/bash
#SBATCH --job-name=C1-D-LGBM-Biogen-official
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_D_Biogen_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
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

def parse_split(value):
    if not isinstance(value,list) or len(value)!=2:raise ValueError('Expected published Polaris [TRAIN, TEST] split')
    train=value[0];test=value[1]
    if isinstance(test,dict):
        if set(test)!={'test'}:raise ValueError('Multiple official test sets must not be merged implicitly')
        test=test['test']
    if not isinstance(train,list) or not isinstance(test,list):raise ValueError('Expected explicit official index lists')
    if any(type(index) is not int or index<0 for index in train+test):raise ValueError('Non-integer or negative source position')
    if len(set(train))!=len(train) or len(set(test))!=len(test) or set(train)&set(test):raise ValueError('Duplicate or overlapping official positions')
    return set(train),set(test)
class SplitTests(unittest.TestCase):
    def test_named_and_plain_test_lists_bind_identically(self):
        self.assertEqual(parse_split([[0,2],{'test':[1,3]}]),parse_split([[0,2],[1,3]]))
    def test_overlap_is_rejected(self):
        with self.assertRaises(ValueError):parse_split([[0,1],[1,2]])
    def test_boolean_masks_are_not_misread_as_indices(self):
        with self.assertRaises(ValueError):parse_split([[True],[False]])
    def test_unregistered_multiple_test_sets_are_rejected(self):
        with self.assertRaises(ValueError):parse_split([[0],{'test':[1],'extra':[2]}])
bindings=unittest.defaultTestLoader.loadTestsFromTestCase(SplitTests)
if not unittest.TextTestRunner(verbosity=2).run(bindings).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,128*1024**2,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'C1_D_LGBM'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
proof=json.loads((b1/'endpoint_catalog/job_4536889/manifest.json').read_text());assert proof['deferred_registry_full_inventory_verified']
manifest=json.loads(Path(entry['manifest']).read_text());spec=manifest['source_groups']['Biogen_ADME']
ordinals={row['record_id']:row['source_row'] for row in pq.read_table(spec['records'],columns=['record_id','source_row']).to_pylist()}
features=pq.read_table(b1/'C1_D_features/job_4536892/Biogen_ADME.parquet').to_pylist()
files=('adme-fang-hclint-reg-v1.json','adme-fang-rclint-reg-v1.json','adme-fang-perm-reg-v1.json','adme-fang-hppb-reg-v1.json','adme-fang-rppb-reg-v1.json','adme-fang-solu-reg-v1.json')
tasks=[];label_rows=[];results=[];coverage=[];failures=[]
for filename in files:
    source=root/'raw/Biogen_ADME'/filename;benchmark=json.loads(source.read_text())
    if len(benchmark['targetCols'])!=1:raise ValueError('Expected a published single-target official benchmark')
    target=benchmark['targetCols'][0]
    if benchmark['targetTypes'][target].casefold()!='regression':raise ValueError('Unexpected official target type')
    train_set,test_set=parse_split(benchmark['split'])
    if (train_set|test_set)-set(ordinals.values()):raise ValueError('Official split position absent from the unchanged B0 table')
    task_rows=[];counts=Counter()
    for row in features:
        position=ordinals[row['record_id']]
        split='train' if position in train_set else 'test' if position in test_set else None
        if split is None:counts['not_in_official_endpoint_split']+=1;continue
        raw=json.loads(row['original_fields_json'])
        try:y=float(raw[target])
        except (KeyError,ValueError,TypeError):counts['missing_or_unparsed_target']+=1;continue
        if not math.isfinite(y):counts['missing_or_unparsed_target']+=1;continue
        label={'dataset':'Biogen_ADME','task':target,'target':target,'record_id':row['record_id'],'full_inchikey':row['full_inchikey'],'source_row':position,'official_split':split,'y':y,'domain_eligible':row['domain_eligible'],'retained':row['retained'],'official_split_source':str(source)}
        label_rows.append(label)
        if not(row['domain_eligible'] and row['retained']):counts['outside_domain']+=1;continue
        if row['features'] is None or not any(row['valid_mask'] or []):counts['missing_native_D']+=1;continue
        if not row['full_inchikey']:counts['unresolved_identity']+=1;continue
        task_rows.append(dict(label,features=row['features']));counts[split+'_C1_D_rows']+=1
    tasks.append((target,task_rows));coverage.append({'task':target,'counts':dict(counts),'official_split_source':str(source),'official_train_positions':len(train_set),'official_test_positions':len(test_set)})
assert len(tasks)==proof['candidate_counts_by_source_group']['Biogen_ADME']
safe();pq.write_table(pa.Table.from_pylist(label_rows),out/'Biogen_official_endpoint_rows.parquet',compression='zstd')
prediction_schema=pa.schema([('task',pa.string()),('record_id',pa.string()),('full_inchikey',pa.string()),('y_true',pa.float64()),('prediction',pa.float64()),('training_mean',pa.float64())])
for target,rows in tasks:
    train=[row for row in rows if row['official_split']=='train'];test=[row for row in rows if row['official_split']=='test']
    if not train or not test:failures.append({'task':target,'reason':'EMPTY_OFFICIAL_TRAIN_OR_TEST'});continue
    safe();x=np.asarray([row['features'] for row in train],float);y=np.asarray([row['y'] for row in train],float);mean=float(y.mean())
    model=LGBMRegressor(random_state=SEED,n_jobs=2,verbosity=-1);model.fit(x,y)
    prediction=np.asarray(model.predict(np.asarray([row['features'] for row in test],float)),float)
    metric=score([row['y'] for row in test],prediction,mean,[row['full_inchikey'] for row in test])
    result=dict(dataset='Biogen_ADME',task=target,model='LightGBM',feature_group='D',seed=SEED,n_train=len(train),feature_count=x.shape[1],**metric);results.append(result)
    safe();pq.write_table(pa.Table.from_pylist([{'task':target,'record_id':row['record_id'],'full_inchikey':row['full_inchikey'],'y_true':row['y'],'prediction':float(p),'training_mean':mean} for row,p in zip(test,prediction)],schema=prediction_schema),out/(target+'_predictions.parquet'),compression='zstd')
    model.booster_.save_model(str(out/(target+'_model.txt')))
    print('C1_D_BIOGEN_LGBM_TASK_CLOSED',target,'n_train',len(train),'n_test',len(test),flush=True)
fields=list(dict.fromkeys(key for row in results for key in row))
with (out/'C1_D_LGBM_Biogen_partial_results.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields or ['task']);writer.writeheader();writer.writerows(results)
report={'status':'C1_D_LGBM_BIOGEN_CLOSED','job':os.environ['SLURM_JOB_ID'],'source_entry':str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),'native_D_source':str(b1/'C1_D_features/job_4536892/manifest.json'),'official_endpoint_labels':str(out/'Biogen_official_endpoint_rows.parquet'),'tasks_expected':6,'tasks_completed':len(results),'failures':failures,'coverage':coverage,'unit_tests':suite.countTestCases()+bindings.countTestCases(),'official_source_split_used':True,'hyperparameter_search':False,'TEST_used_for_selection':False,'missing_native_features_not_filled':True,'C1_final_table':False,'B1_task_screen_decisions_produced':False}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('C1_D_LGBM_BIOGEN_CLOSED',out/'manifest.json','completed',len(results),'of',6,flush=True)

PY
