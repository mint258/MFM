#!/bin/bash
#SBATCH --job-name=C1-D-LGBM-TDC-ASAP
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_D_TDC_ASAP_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import csv,json,math,os,unittest,importlib.metadata,ast,urllib.request,traceback
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from lightgbm import LGBMRegressor,LGBMClassifier
from sklearn.metrics import roc_auc_score,average_precision_score
from scipy.stats import spearmanr
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

def normalize_split(value):
    token=str(value or '').strip().casefold()
    return 'train' if token in ('train','train_val') else 'test' if token=='test' else None
def tdc_task(source_file):
    parts=Path(source_file).parts
    if len(parts)!=3 or parts[0]!='admet_group' or parts[2] not in ('train_val.csv','test.csv'):raise ValueError('Unexpected TDC source member')
    return parts[1]
def numeric(value):
    try:value=float(value)
    except (ValueError,TypeError):return None
    return value if math.isfinite(value) else None
def endpoint_allowed(endpoint,source_row,masks):return source_row not in masks.get(endpoint,[])
class EndpointTests(unittest.TestCase):
    def test_official_trainval_is_training_without_test_use(self):
        self.assertEqual(normalize_split('train_val'),'train');self.assertIsNone(normalize_split('validation'))
    def test_TDC_members_join_same_endpoint(self):
        self.assertEqual(tdc_task('admet_group/example/train_val.csv'),tdc_task('admet_group/example/test.csv'))
    def test_censored_label_is_not_silently_parsed(self):
        self.assertIsNone(numeric('<0.3'));self.assertEqual(numeric('0'),0.)
    def test_ASAP_mask_is_endpoint_specific(self):
        masks={'HLM':[519]}
        self.assertFalse(endpoint_allowed('HLM',519,masks));self.assertTrue(endpoint_allowed('KSOL',519,masks))
bindings=unittest.defaultTestLoader.loadTestsFromTestCase(EndpointTests)
if not unittest.TextTestRunner(verbosity=2).run(bindings).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,256*1024**2,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'C1_D_LGBM'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
feature_root=b1/'C1_D_features/job_4536892'
feature_contract=json.loads((feature_root/'manifest.json').read_text())
proof=json.loads(Path(feature_contract['full_inventory_scope_proof']).read_text());assert proof['deferred_registry_full_inventory_verified']
manifest=json.loads(Path(entry['manifest']).read_text())
def fetch_json(url):
    with urllib.request.urlopen(url,timeout=60) as response:return json.load(response)
commit=fetch_json('https://api.github.com/repos/mims-harvard/TDC/commits/main')['sha']
with urllib.request.urlopen('https://raw.githubusercontent.com/mims-harvard/TDC/'+commit+'/tdc/metadata.py',timeout=60) as response:metadata_source=response.read()
safe();(out/'TDC_official_metadata.py').write_bytes(metadata_source)
assignments=[node for node in ast.parse(metadata_source.decode()).body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='admet_metrics' for target in node.targets)]
if len(assignments)!=1:raise ValueError('Official TDC metric metadata interface changed')
official_metrics=ast.literal_eval(assignments[0].value)
asap_spec=manifest['source_groups']['ASAP_Polaris2025']
asap_domain=json.loads(Path(asap_spec['domain_manifest']).read_text())
asap_masks=asap_domain['endpoint_evaluation_exclusions']
asap_ordinals={r['record_id']:r['source_row'] for r in pq.read_table(asap_spec['records'],columns=['record_id','source_row']).to_pylist()}
all_results=[];failures=[];coverage_report=[];task_index=0
pred_schema=pa.schema([('dataset',pa.string()),('task',pa.string()),('record_id',pa.string()),('full_inchikey',pa.string()),('y_true',pa.float64()),('prediction',pa.float64()),('training_mean',pa.float64()),('blind_fallback',pa.bool_())])
for group in ('TDC_ADMET','ASAP_Polaris2025'):
    tasks=defaultdict(list);coverage=defaultdict(Counter)
    for batch in pq.ParquetFile(feature_root/(group+'.parquet')).iter_batches(batch_size=2048):
        for row in batch.to_pylist():
            raw=json.loads(row['original_fields_json']);split=normalize_split(row['official_split'])
            endpoints=[tdc_task(row['source_file'])] if group=='TDC_ADMET' else ['HLM','MLM','KSOL','LogD','MDR1-MDCKII']
            for endpoint in endpoints:
                counts=coverage[endpoint];counts['source_rows']+=1
                if split is None:counts['unresolved_official_split']+=1;continue
                if group=='ASAP_Polaris2025' and split=='test' and not endpoint_allowed(endpoint,asap_ordinals[row['record_id']],asap_masks):
                    counts['official_endpoint_evaluation_mask']+=1;continue
                y=numeric(raw.get('Y' if group=='TDC_ADMET' else endpoint))
                if y is None:counts['unparsed_or_missing_target']+=1;continue
                outside=not (row['retained'] and row['domain_eligible'])
                missing=row['features'] is None or not any(row['valid_mask'] or [])
                if group=='TDC_ADMET' and outside:counts['outside_domain']+=1;continue
                if missing:counts['missing_native_D']+=1;continue
                if not row['full_inchikey']:counts['unresolved_identity']+=1;continue
                tasks[endpoint].append(dict(row,y=y,split=split,blind_fallback=outside))
    assert len(coverage)==proof['candidate_counts_by_source_group'][group]
    for endpoint in sorted(coverage):
        task_index+=1;taskdir=out/('task_%03d'%task_index);safe();taskdir.mkdir()
        rows=tasks.get(endpoint,[]);train=[r for r in rows if r['split']=='train' and not r['blind_fallback']];test=[r for r in rows if r['split']=='test']
        classifier=group=='TDC_ADMET' and official_metrics.get(endpoint) in ('roc-auc','pr-auc')
        coverage_report.append({'dataset':group,'task':endpoint,'counts':dict(coverage[endpoint]),'n_train':len(train),'n_test':len(test)})
        try:
            if not train or not test:raise ValueError('Empty official TRAIN/TEST')
            if group=='TDC_ADMET' and official_metrics.get(endpoint) not in ('mae','spearman','roc-auc','pr-auc'):raise ValueError('Unknown official task type')
            y_train=np.array([r['y'] for r in train],float);y_test=np.array([r['y'] for r in test],float)
            if classifier and (set(y_train)!={0.,1.} or set(y_test)-{0.,1.}):raise ValueError('Nonbinary official class labels')
            x_train=np.asarray([r['features'] for r in train],float);train_mean=float(y_train.mean())
            model=(LGBMClassifier if classifier else LGBMRegressor)(random_state=SEED,n_jobs=2,verbosity=-1)
            model.fit(x_train,y_train)
            prediction=np.full(len(test),train_mean,float)
            in_domain=[i for i,r in enumerate(test) if not r['blind_fallback']]
            if in_domain:
                values=np.asarray([test[i]['features'] for i in in_domain],float)
                prediction[in_domain]=model.predict_proba(values)[:,list(model.classes_).index(1.)] if classifier else model.predict(values)
            metrics=score(y_test,prediction,train_mean,[r['full_inchikey'] for r in test])
            recommended=official_metrics.get(endpoint) if group=='TDC_ADMET' else 'mae'
            if recommended=='roc-auc' and len(set(y_test))==2:official_score=float(roc_auc_score(y_test,prediction))
            elif recommended=='pr-auc' and len(set(y_test))==2:official_score=float(average_precision_score(y_test,prediction))
            elif recommended=='spearman':official_score=float(spearmanr(y_test,prediction).statistic)
            elif recommended=='mae':official_score=metrics['MAE']
            else:official_score=None
            result=dict(dataset=group,task=endpoint,model='LightGBM',feature_group='D',task_type='binary_classification' if classifier else 'regression',seed=SEED,n_train=len(train),feature_count=x_train.shape[1],blind_mean_fallback_count=sum(r['blind_fallback'] for r in test),official_recommended_metric=recommended,official_metric_value=official_score,**metrics)
            safe()
            pq.write_table(pa.Table.from_pylist([{'dataset':group,'task':endpoint,'record_id':r['record_id'],'full_inchikey':r['full_inchikey'],'y_true':r['y'],'prediction':float(p),'training_mean':train_mean,'blind_fallback':r['blind_fallback']} for r,p in zip(test,prediction)],schema=pred_schema),taskdir/'predictions.parquet',compression='zstd')
            model.booster_.save_model(str(taskdir/'model.txt'))
            (taskdir/'result.json').write_text(json.dumps(result,indent=2)+'\n');all_results.append(result)
            print('C1_D_LGBM_TASK_CLOSED',group,endpoint,'n_train',len(train),'n_test',len(test),flush=True)
        except Exception as error:
            failures.append({'dataset':group,'task':endpoint,'status':'FIRST_ATTEMPT_FAILED','error':repr(error)});traceback.print_exc()
fields=list(dict.fromkeys(key for row in all_results for key in row))
with (out/'C1_D_LGBM_TDC_ASAP_partial_results.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields or ['task']);writer.writeheader();writer.writerows(all_results)
report={'status':'C1_D_LGBM_TDC_ASAP_CLOSED','job':os.environ['SLURM_JOB_ID'],'source_contract':str(feature_root/'manifest.json'),'tasks_expected':23,'tasks_completed':len(all_results),'failures':failures,'coverage':coverage_report,'TDC_task_type_metadata_commit':commit,'unit_tests':suite.countTestCases()+bindings.countTestCases(),'selection_used_TEST':False,'hyperparameter_search':False,'ASAP_official_evaluation_masks_source':asap_spec['domain_manifest'],'blind_test_rows_not_domain_filtered':True,'no_native_feature_imputation':True,'C1_final_table':False,'B1_task_screen_decisions_produced':False}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('C1_D_LGBM_TDC_ASAP_CLOSED',out/'manifest.json','completed',len(all_results),'of',23,flush=True)

PY
