sbatch --parsable --dependency=afterok:4537317 <<'NMRNATIVEORDERBASELINES'
#!/bin/bash
#SBATCH --job-name=B1-NMR-correct-original-atoms-RF-LGBM
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=12:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_RF_LGBM_NMR_%j.log
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


entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())
root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,3*1024**3,quota,own_concurrent_bytes=24*1024**3)
def eligible(row):return bool(row['retained'] and row['domain_eligible'])
def unfold(row):
    for atom in row['atoms']:
        yield dict(dataset='NMRShiftDB2',task=row['nucleus'],record_id=row['record_id']+':atom:'+str(atom['original_atom_index']),original_spectrum_record_id=row['record_id'],original_atom_index=atom['original_atom_index'],full_inchikey=row['full_inchikey'],y=atom['y'],split=row['official_split'],retained=row['retained'],domain_eligible=row['domain_eligible'],ecfp4_2048_packed=atom['ecfp4_2048_packed'],rdkit_2d=row['rdkit_2d']+atom['rdkit_atom37'])
class AtomRowTests(unittest.TestCase):
    def test_repeated_spectra_preserve_molecule_groups_and_native_atom_ids(self):
        source=dict(nucleus='13C',record_id='spectrum1',full_inchikey='FULL-KEY',official_split='test',retained=True,domain_eligible=True,rdkit_2d=[1.,float('nan')],atoms=[dict(original_atom_index=5,y=42.,ecfp4_2048_packed=bytes(256),rdkit_atom37=[2.]*37)])
        row=list(unfold(source))[0]
        self.assertEqual(row['record_id'],'spectrum1:atom:5')
        self.assertEqual(row['full_inchikey'],'FULL-KEY')
        self.assertEqual(row['y'],42.)
        self.assertTrue(math.isnan(row['rdkit_2d'][1]))
        self.assertEqual(len(row['rdkit_2d']),39)
    def test_empty_labels_are_not_fabricated(self):
        self.assertEqual(list(unfold({'atoms':[]})),[])
atomtests=unittest.defaultTestLoader.loadTestsFromTestCase(AtomRowTests)
if not unittest.TextTestRunner(verbosity=2).run(atomtests).wasSuccessful():raise SystemExit(1)
safe();out=b1/'B1_RF_LGBM_NMR'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
features=b1/'B1_NMR_features_native_order/job_4537317';contract=json.loads((features/'manifest.json').read_text())
proof=json.loads(Path(contract['full_inventory_scope_proof']).read_text());assert proof['deferred_registry_full_inventory_verified'] and proof['deferred_endpoint_count']==5
prediction_schema=pa.schema([('dataset',pa.string()),('task',pa.string()),('model',pa.string()),('fit_population',pa.string()),('record_id',pa.string()),('original_spectrum_record_id',pa.string()),('original_atom_index',pa.int32()),('full_inchikey',pa.string()),('y_true',pa.float64()),('prediction',pa.float64()),('training_mean',pa.float64()),('retained',pa.bool_()),('domain_eligible',pa.bool_())])
results=[];failures=[];coverage=[]
for nucleus in ('13C','1H'):
    safe();rows=[]
    for batch in pq.ParquetFile(features/(nucleus+'.parquet')).iter_batches(batch_size=256):
        for source in batch.to_pylist():rows.extend(unfold(source))
    train=[r for r in rows if r['split']=='train'];test=[r for r in rows if r['split']=='test']
    coverage.append(dict(dataset='NMRShiftDB2',task=nucleus,train_atomic_points=len(train),test_atomic_points=len(test),retained_train_atomic_points=sum(eligible(r) for r in train),retained_test_atomic_points=sum(eligible(r) for r in test),filtered_total_labeled_points=sum(eligible(r) for r in rows)))
    taskdir=out/nucleus;safe();taskdir.mkdir()
    def matrix(population,model_name):
        if model_name=='RF-ECFP4':
            return np.asarray([np.unpackbits(np.frombuffer(r['ecfp4_2048_packed'],dtype=np.uint8),bitorder='little') for r in population],dtype=np.uint8)
        return np.asarray([r['rdkit_2d'] for r in population],dtype=np.float64)
    for model_name in ('RF-ECFP4','LightGBM-RDKit2D'):
        started=time.monotonic()
        try:
            factory=RandomForestRegressor if model_name=='RF-ECFP4' else LGBMRegressor
            parameters={'random_state':SEED,'n_jobs':2}
            if model_name=='LightGBM-RDKit2D':parameters['verbosity']=-1
            model_records=[];fit_metrics=[];reuse=None
            for fit_population in ('retained','full'):
                safe()
                train_pop=[r for r in train if eligible(r)] if fit_population=='retained' else train
                test_pop=[r for r in test if eligible(r)] if fit_population=='retained' else test
                if not train_pop or not test_pop:raise ValueError('Empty official NMR atom population')
                xtrain=matrix(train_pop,model_name);ytrain=np.array([r['y'] for r in train_pop],float);xtest=matrix(test_pop,model_name)
                if fit_population=='full' and reuse is not None and len(train_pop)==reuse[0]:model=reuse[1]
                else:
                    model=factory(**parameters);model.fit(xtrain,ytrain)
                if fit_population=='retained':reuse=(len(train_pop),model)
                train_mean=float(ytrain.mean());prediction=np.asarray(model.predict(xtest),float)
                if not np.isfinite(prediction).all():raise ValueError('Nonfinite original-atom predictions')
                indices=np.arange(len(test_pop))
                populations={'retained':indices} if fit_population=='retained' else {'full':indices,'retained':np.array([i for i,r in enumerate(test_pop) if eligible(r)],dtype=int),'excluded':np.array([i for i,r in enumerate(test_pop) if not eligible(r)],dtype=int)}
                for evaluation_population,index in populations.items():
                    if not len(index):
                        fit_metrics.append(dict(dataset='NMRShiftDB2',task=nucleus,model=model_name,fit_population=fit_population,evaluation_population=evaluation_population,metric_status='EMPTY_EVALUATION_POPULATION',n_test_rows=0));continue
                    subset=[test_pop[i] for i in index]
                    metric=score([r['y'] for r in subset],prediction[index],train_mean,[r['full_inchikey'] for r in subset])
                    fit_metrics.append(dict(dataset='NMRShiftDB2',task=nucleus,model=model_name,feature_group='atom_centered_ECFP4' if model_name=='RF-ECFP4' else 'RDKit2D_plus_RDKit_atom37',task_type='atom_regression',fit_population=fit_population,evaluation_population=evaluation_population,seed=SEED,n_train=len(train_pop),feature_count=xtrain.shape[1],training_mean=train_mean,**metric))
                model_records.extend([dict(dataset='NMRShiftDB2',task=nucleus,model=model_name,fit_population=fit_population,record_id=r['record_id'],original_spectrum_record_id=r['original_spectrum_record_id'],original_atom_index=r['original_atom_index'],full_inchikey=r['full_inchikey'],y_true=r['y'],prediction=float(p),training_mean=train_mean,retained=r['retained'],domain_eligible=r['domain_eligible']) for r,p in zip(test_pop,prediction)])
                if model_name=='LightGBM-RDKit2D':
                    safe();model.booster_.save_model(str(taskdir/(model_name+'_'+fit_population+'.txt')))
                del xtrain,xtest
            safe();pq.write_table(pa.Table.from_pylist(model_records,schema=prediction_schema),taskdir/(model_name+'_predictions.parquet'),compression='zstd')
            report=dict(dataset='NMRShiftDB2',task=nucleus,model=model_name,parameters=factory(**parameters).get_params(),elapsed_seconds=time.monotonic()-started,results=fit_metrics,full_inchikey_grouped_bootstrap_draws=1000,full_training_fit_used_for_filter_impact=True,random_forest_saved=False)
            (taskdir/(model_name+'_results.json')).write_text(json.dumps(report,indent=2)+'\n');results.extend(fit_metrics)
            print('B1_NMR_ATOM_MODEL_CLOSED',nucleus,model_name,'seconds',round(report['elapsed_seconds'],2),'n_train',len(train),'n_test',len(test),flush=True)
            del model_records,reuse,model
        except Exception as error:
            failure=dict(dataset='NMRShiftDB2',task=nucleus,model=model_name,status='UNRESOLVED',error=repr(error));failures.append(failure);traceback.print_exc();print('B1_NMR_ATOM_FAILURE',json.dumps(failure),flush=True)
    del rows,train,test
fields=list(dict.fromkeys(k for result in results for k in result))
with (out/'B1_RF_LGBM_NMR_partial_results.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields or ['task']);writer.writeheader();writer.writerows(results)
report=dict(status='B1_NMR_TWO_ATOMIC_BASELINES_CLOSED',job=os.environ['SLURM_JOB_ID'],source_contract=str(features/'manifest.json'),tasks_expected=2,required_task_model_pairs=4,successful_task_model_pairs=sum(r.get('fit_population')=='retained' and r.get('evaluation_population')=='retained' for r in results),failures=failures,coverage=coverage,versions={name:importlib.metadata.version(name) for name in ('scikit-learn','lightgbm','numpy')},new_unit_tests=suite.countTestCases()+atomtests.countTestCases(),original_split_unchanged=True,experimental_labels_not_averaged=True,native_explicit_hydrogen_atom_order=True,hyperparameter_search=False,model_and_hyperparameter_selection_used_TEST=False,task_screen_decisions_produced=False,Chemprop_still_required=True)
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('B1_NMR_RF_LGBM_SOURCE_CLOSED',out/'manifest.json','pairs',report['successful_task_model_pairs'],'failures',len(failures),flush=True)

PY
NMRNATIVEORDERBASELINES
