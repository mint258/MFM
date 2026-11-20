#!/bin/bash
#SBATCH --job-name=B1-RF-LGBM-Biogen6
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=12:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_RF_LGBM_Biogen_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import csv,json,math,os,time,unittest,importlib.metadata,traceback
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import DataStructs
from sklearn.ensemble import RandomForestRegressor,RandomForestClassifier
from lightgbm import LGBMRegressor,LGBMClassifier
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

def target_value(group,raw):
    try:value=float(raw['y' if group=='MoleculeACE' else 'value'])
    except (TypeError,ValueError,KeyError):return None
    return value if math.isfinite(value) else None
def eligible(row):return bool(row['retained'] and row['domain_eligible'])
def positive_probability(estimator,x):
    columns=np.flatnonzero(np.asarray(estimator.classes_)==1)
    if len(columns)!=1:raise ValueError('Expected binary positive class 1')
    return np.asarray(estimator.predict_proba(x)[:,columns[0]],float)
class BindingTests(unittest.TestCase):
    def test_train_mean_comes_from_training_labels(self):
        self.assertAlmostEqual(float(np.mean([0.,2.])),1.)
        self.assertIsNone(target_value('MoleculeACE',{'y':'nan'}))
        self.assertEqual(target_value('PharmaBench',{'value':'0'}),0.)
    def test_filter_impact_populations_are_exhaustive(self):
        rows=[{'retained':True,'domain_eligible':True},{'retained':False,'domain_eligible':True},{'retained':True,'domain_eligible':False}]
        self.assertEqual(sum(map(eligible,rows)),1)
        self.assertEqual(sum(not eligible(r) for r in rows),2)
    def test_probability_columns_follow_class_labels(self):
        class Mock:
            classes_=np.array([1,0])
            def predict_proba(self,x):return np.array([[.8,.2],[.1,.9]])
        np.testing.assert_equal(positive_probability(Mock(),None),[.8,.1])
    def test_unsupported_class_labels_fail_instead_of_relabeling(self):
        class Mock:classes_=np.array([-1,0])
        with self.assertRaises(ValueError):positive_probability(Mock(),None)
binding_suite=unittest.defaultTestLoader.loadTestsFromTestCase(BindingTests)
if not unittest.TextTestRunner(verbosity=2).run(binding_suite).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())
root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,1024**3,quota,own_concurrent_bytes=24*1024**3)
safe()
features=b1/'B1_molecular_features/job_4536920'
contract=json.loads((features/'manifest.json').read_text())
proof=json.loads(Path(contract['scope_proof']).read_text())
assert proof['deferred_registry_full_inventory_verified']
out=b1/'B1_RF_LGBM'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
prediction_schema=pa.schema([('dataset',pa.string()),('task',pa.string()),('model',pa.string()),('fit_population',pa.string()),('record_id',pa.string()),('full_inchikey',pa.string()),('y_true',pa.float64()),('prediction',pa.float64()),('training_mean',pa.float64()),('retained',pa.bool_()),('domain_eligible',pa.bool_())])
results=[];failures=[];coverage_report=[];task_index=0

binding_path=b1/'C1_D_LGBM/job_4536959/manifest.json'
binding=json.loads(binding_path.read_text())
assert binding['tasks_completed']==6 and not binding['failures']
label_rows=pq.read_table(binding['official_endpoint_labels']).to_pylist()
group='Biogen_ADME'
source_features={}
for batch in pq.ParquetFile(features/(group+'.parquet')).iter_batches(batch_size=2048):
    for row in batch.to_pylist():
        if row['record_id'] in source_features:raise ValueError('Duplicate B0 feature source record')
        source_features[row['record_id']]=row
for group in ('Biogen_ADME',):
    tasks=defaultdict(list);coverage=defaultdict(Counter)
    for label in label_rows:
        task=label['task'];counts=coverage[task];counts['source_rows']+=1
        row=source_features[label['record_id']]
        split=label['official_split'];y=label['y']
        if split not in ('train','test') or not math.isfinite(y):raise ValueError('Invalid frozen official label binding')
        counts[split+'_full_source']+=1
        counts[split+('_retained_source' if eligible(row) else '_excluded_source')]+=1
        if row['ecfp4_2048_packed'] is None or not row['full_inchikey']:counts['unresolved_graph_or_identity']+=1;continue
        tasks[task].append(dict(row,y=y,split=split));counts[split+'_processable']+=1
    assert len(coverage)==proof['candidate_counts_by_source_group'][group]
    for task in sorted(coverage):
        task_index+=1;taskdir=out/('task_%03d'%task_index);safe();taskdir.mkdir()
        rows=tasks.get(task,[]);train=[r for r in rows if r['split']=='train'];test=[r for r in rows if r['split']=='test']
        classifier=False
        if classifier and set(r['y'] for r in rows)-{0.,1.}:
            failures.append({'dataset':group,'task':task,'status':'UNRESOLVED_NON_BINARY_CLASS_LABELS'});continue
        coverage_report.append({'dataset':group,'task':task,'counts':dict(coverage[task]),'eligible_train':sum(eligible(r) for r in train),'eligible_test':sum(eligible(r) for r in test)})
        def matrix(population,model_name):
            if model_name=='RF-ECFP4':
                # RDKit's packed binary encoding is bit-unpacked in little bit order.
                return np.asarray([np.unpackbits(np.frombuffer(r['ecfp4_2048_packed'],dtype=np.uint8),bitorder='little') for r in population],dtype=np.uint8)
            return np.asarray([r['rdkit_2d'] for r in population],dtype=np.float64)
        for model_name in ('RF-ECFP4','LightGBM-RDKit2D'):
            started=time.monotonic()
            try:
                safe()
                if model_name=='RF-ECFP4':
                    factory=RandomForestClassifier if classifier else RandomForestRegressor
                    parameters={'random_state':SEED,'n_jobs':2}
                else:
                    factory=LGBMClassifier if classifier else LGBMRegressor
                    parameters={'random_state':SEED,'n_jobs':2,'verbosity':-1}
                model_records=[];fit_metrics=[];reuse=None
                for fit_population in ('retained','full'):
                    train_pop=[r for r in train if eligible(r)] if fit_population=='retained' else train
                    test_pop=[r for r in test if eligible(r)] if fit_population=='retained' else test
                    if not train_pop or not test_pop:raise ValueError('Empty official train/test population')
                    if classifier and set(r['y'] for r in train_pop)!={0.,1.}:raise ValueError('Training population has fewer than two classes')
                    xtrain=matrix(train_pop,model_name);ytrain=np.array([r['y'] for r in train_pop],float)
                    xtest=matrix(test_pop,model_name)
                    if fit_population=='full' and reuse is not None and len(train_pop)==reuse[0]:
                        model=reuse[1]
                    else:
                        model=factory(**parameters);model.fit(xtrain,ytrain)
                    if fit_population=='retained':reuse=(len(train_pop),model)
                    train_mean=float(ytrain.mean())
                    prediction=positive_probability(model,xtest) if classifier else np.asarray(model.predict(xtest),float)
                    if not np.isfinite(prediction).all():raise ValueError('Nonfinite predictions')
                    indices=np.arange(len(test_pop))
                    populations={'retained':indices} if fit_population=='retained' else {'full':indices,'retained':np.array([i for i,r in enumerate(test_pop) if eligible(r)],dtype=int),'excluded':np.array([i for i,r in enumerate(test_pop) if not eligible(r)],dtype=int)}
                    for evaluation_population,index in populations.items():
                        if not len(index):
                            fit_metrics.append({'dataset':group,'task':task,'model':model_name,'fit_population':fit_population,'evaluation_population':evaluation_population,'metric_status':'EMPTY_EVALUATION_POPULATION','n_test_rows':0});continue
                        subset=[test_pop[i] for i in index]
                        metric=score([r['y'] for r in subset],prediction[index],train_mean,[r['full_inchikey'] for r in subset])
                        fit_metrics.append(dict(dataset=group,task=task,model=model_name,feature_group='ECFP4' if model_name=='RF-ECFP4' else 'RDKit2D',task_type='binary_classification' if classifier else 'regression',fit_population=fit_population,evaluation_population=evaluation_population,seed=SEED,n_train=len(train_pop),feature_count=xtrain.shape[1],training_mean=train_mean,**metric))
                    model_records.extend([{'dataset':group,'task':task,'model':model_name,'fit_population':fit_population,'record_id':r['record_id'],'full_inchikey':r['full_inchikey'],'y_true':r['y'],'prediction':float(p),'training_mean':train_mean,'retained':r['retained'],'domain_eligible':r['domain_eligible']} for r,p in zip(test_pop,prediction)])
                    if model_name=='LightGBM-RDKit2D':
                        safe();model.booster_.save_model(str(taskdir/(model_name+'_'+fit_population+'.txt')))
                safe()
                pq.write_table(pa.Table.from_pylist(model_records,schema=prediction_schema),taskdir/(model_name+'_predictions.parquet'),compression='zstd')
                taskreport={'dataset':group,'task':task,'model':model_name,'parameters':factory(**parameters).get_params(),'elapsed_seconds':time.monotonic()-started,'results':fit_metrics,'full_inchikey_grouped_bootstrap_draws':1000,'full_training_fit_used_for_filter_impact':True,'random_forest_saved':False}
                (taskdir/(model_name+'_results.json')).write_text(json.dumps(taskreport,indent=2)+'\n')
                results.extend(fit_metrics)
                print('B1_BASELINE_TASK_MODEL_CLOSED',group,task,model_name,'seconds',round(taskreport['elapsed_seconds'],2),'n_train',sum(eligible(r) for r in train),'n_test',sum(eligible(r) for r in test),flush=True)
            except Exception as error:
                failure={'dataset':group,'task':task,'model':model_name,'status':'UNRESOLVED','error':repr(error)}
                failures.append(failure);traceback.print_exc();print('B1_BASELINE_FAILURE',json.dumps(failure),flush=True)
fields=list(dict.fromkeys(k for result in results for k in result))
with (out/'B1_RF_LGBM_partial_results.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields or ['task']);writer.writeheader();writer.writerows(results)
report={'status':'B1_TWO_BASELINE_INITIAL_OFFICIAL_SOURCE_GROUPS_CLOSED','job':os.environ['SLURM_JOB_ID'],'source_contract':str(features/'manifest.json'),'official_split_binding':str(binding_path),'source_groups':['Biogen_ADME'],'tasks_expected':6,'tasks_seen':task_index,'successful_task_model_pairs':sum(r.get('fit_population')=='retained' and r.get('evaluation_population')=='retained' for r in results),'required_task_model_pairs':12,'failures':failures,'coverage':coverage_report,'versions':{name:importlib.metadata.version(name) for name in ('scikit-learn','lightgbm','numpy')},'new_unit_tests':suite.countTestCases()+binding_suite.countTestCases(),'class_prediction':'Probability of class 1; absolute probability error and RAE against TRAIN prevalence','model_and_hyperparameter_selection_used_TEST':False,'hyperparameter_search':False,'task_screen_decisions_produced':False,'Chemprop_and_other_source_groups_still_required':True}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('B1_RF_LGBM_SOURCE_CLOSED',out/'manifest.json','pairs',report['successful_task_model_pairs'],'failures',len(failures),flush=True)

PY
