#!/bin/bash
#SBATCH --job-name=B1-Chemprop-v2-official40
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-10
#SBATCH --cpus-per-task=4
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=12:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_Chemprop_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import csv,json,math,os,time,unittest,importlib.metadata,traceback,gc
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch
from lightning import pytorch as pl
from lightning.pytorch.callbacks import Callback,ModelCheckpoint
from chemprop import data,featurizers,nn,models
from workflows.benchmark_data.admission import protect
torch.set_num_threads(4);torch.set_num_interop_threads(1)
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

entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())
root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,2*1024**3,quota,own_concurrent_bytes=24*1024**3)
safe()
features=b1/'B1_molecular_features/job_4536908'
contract=json.loads((features/'manifest.json').read_text())
proof=json.loads(Path(contract['scope_proof']).read_text())
assert proof['deferred_registry_full_inventory_verified']
out=b1/'B1_Chemprop'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
os.environ['TMPDIR']=str(out/'tmp');(out/'tmp').mkdir();import tempfile;tempfile.tempdir=os.environ['TMPDIR']
protocol={'authority':'USER_DIRECTIVE_20261119 and BENCHMARK_PLAN 2.2/4.3','model':'Chemprop v2 graph only','chemprop_version':importlib.metadata.version('chemprop'),'seed':SEED,'epochs':50,'checkpoint_selection':'Fixed final epoch; no validation or TEST selection','official_TRAIN_usage':'All eligible official TRAIN rows for primary fit, all processable official TRAIN rows for full-population diagnostic','hyperparameters':'Official defaults: BondMessagePassing d_h=300 depth=3, MeanAggregation, default one-task FFN, batch_size=64, warmup=2epochs, init_lr=1e-4 max_lr=1e-3 final_lr=1e-4','target_normalization':'Regression fit on TRAIN only; inverse transformed in prediction. Binary classifier predicts class-1 probability','reference_predictor':'Arithmetic mean/prevalence of original unscaled labels for the fit TRAIN population','full_filter_impact':'Separate full-TRAIN fit; evaluate full/retained/excluded official TEST','training_checkpoints':'One last.ckpt per fit population, at every completed epoch','default_seed_count':1,'no_PRETRAINING':True}
(out/'protocol_before_fitting.json').write_text(json.dumps(protocol,indent=2)+'\n')
class DiskGuard(Callback):
    def on_train_epoch_start(self,trainer,module):safe()
    def on_train_epoch_end(self,trainer,module):
        print('B1_CHEMPROP_EPOCH',self.task,self.population,trainer.current_epoch+1,flush=True)
def train_predict(train_rows,test_rows,classifier,checkpoint_dir,task,population):
    pl.seed_everything(SEED,workers=True,verbose=False)
    train_points=[data.MoleculeDatapoint.from_smi(r['feature_smiles'],[r['y']]) for r in train_rows]
    test_points=[data.MoleculeDatapoint.from_smi(r['feature_smiles'],[r['y']]) for r in test_rows]
    featurizer=featurizers.SimpleMoleculeMolGraphFeaturizer()
    training=data.MoleculeDataset(train_points,featurizer);testing=data.MoleculeDataset(test_points,featurizer)
    training.cache=True;testing.cache=True
    if classifier:
        predictor=nn.BinaryClassificationFFN()
        target_scaler=None
    else:
        target_scaler=training.normalize_targets()
        predictor=nn.RegressionFFN(output_transform=nn.UnscaleTransform.from_standard_scaler(target_scaler))
    mp=nn.BondMessagePassing();mpnn=models.MPNN(mp,nn.MeanAggregation(),predictor)
    loader=data.build_dataloader(training,batch_size=64,num_workers=0,seed=SEED,shuffle=True)
    testloader=data.build_dataloader(testing,batch_size=64,num_workers=0,shuffle=False,drop_last=False)
    guard=DiskGuard();guard.task=task;guard.population=population
    checkpoint=ModelCheckpoint(dirpath=checkpoint_dir,save_last=True,save_top_k=0,every_n_epochs=1,enable_version_counter=False)
    trainer=pl.Trainer(accelerator='cpu',devices=1,max_epochs=50,logger=False,enable_checkpointing=True,callbacks=[guard,checkpoint],enable_progress_bar=False,enable_model_summary=False,num_sanity_val_steps=0,limit_val_batches=0,default_root_dir=checkpoint_dir,log_every_n_steps=50)
    trainer.fit(mpnn,loader)
    with torch.inference_mode():
        prediction=torch.cat(trainer.predict(mpnn,testloader),dim=0).reshape(-1).detach().cpu().numpy().astype(float)
    if len(prediction)!=len(test_rows) or not np.isfinite(prediction).all():raise ValueError('Unaligned or nonfinite Chemprop predictions')
    fitmeta={'completed_epochs':trainer.current_epoch,'model_hyperparameters':str(mpnn.hparams),'target_scaler_mean':target_scaler.mean_.tolist() if target_scaler is not None else None,'target_scaler_scale':target_scaler.scale_.tolist() if target_scaler is not None else None,'final_checkpoint':str(checkpoint_dir/'last.ckpt')}
    del trainer,mpnn,training,testing,loader,testloader
    gc.collect()
    return prediction,fitmeta
class TrainingBindingTests(unittest.TestCase):
    def test_training_scale_excludes_test_labels(self):
        points=[data.MoleculeDatapoint.from_smi('CCO',[value]) for value in (0.,2.)]
        ds=data.MoleculeDataset(points,featurizers.SimpleMoleculeMolGraphFeaturizer())
        scaler=ds.normalize_targets()
        self.assertAlmostEqual(float(scaler.mean_[0]),1.)
        self.assertAlmostEqual(float(scaler.scale_[0]),1.)
    def test_scored_targets_keep_original_units(self):
        rows=[{'original_fields_json':json.dumps({'y':'4.2'})}]
        self.assertEqual(target_value('MoleculeACE',json.loads(rows[0]['original_fields_json'])),4.2)
binding_suite=unittest.defaultTestLoader.loadTestsFromTestCase(TrainingBindingTests)
if not unittest.TextTestRunner(verbosity=2).run(binding_suite).wasSuccessful():raise SystemExit(1)
prediction_schema=pa.schema([('dataset',pa.string()),('task',pa.string()),('model',pa.string()),('fit_population',pa.string()),('record_id',pa.string()),('full_inchikey',pa.string()),('y_true',pa.float64()),('prediction',pa.float64()),('training_mean',pa.float64()),('retained',pa.bool_()),('domain_eligible',pa.bool_())])
results=[];failures=[];coverage_report=[];task_index=0
for group in ('MoleculeACE','PharmaBench'):
    tasks=defaultdict(list);coverage=defaultdict(Counter)
    for batch in pq.ParquetFile(features/(group+'.parquet')).iter_batches(batch_size=2048):
        for row in batch.to_pylist():
            task=row['source_file'];counts=coverage[task];counts['source_rows']+=1
            split=str(row['official_split'] or '').strip().casefold()
            if split not in ('train','test'):counts['unresolved_official_split']+=1;continue
            counts[split+'_full_source']+=1
            counts[split+('_retained_source' if eligible(row) else '_excluded_source')]+=1
            y=target_value(group,json.loads(row['original_fields_json']))
            if y is None:counts['unparsed_target']+=1;continue
            if row['ecfp4_2048_packed'] is None or not row['full_inchikey']:counts['unresolved_graph_or_identity']+=1;continue
            tasks[task].append(dict(row,y=y,split=split));counts[split+'_processable']+=1
    assert len(coverage)==proof['candidate_counts_by_source_group'][group]
    for task in sorted(coverage):
        task_index+=1;safe();taskdir=out/('task_%03d'%task_index);taskdir.mkdir()
        rows=tasks.get(task,[]);train=[r for r in rows if r['split']=='train'];test=[r for r in rows if r['split']=='test']
        classifier=group=='PharmaBench' and '_cls_' in Path(task).name
        coverage_report.append({'dataset':group,'task':task,'counts':dict(coverage[task])})
        if classifier and (set(r['y'] for r in train)!={0.,1.} or set(r['y'] for r in test)-{0.,1.}):
            failures.append({'dataset':group,'task':task,'status':'UNRESOLVED_NON_BINARY_CLASS_LABELS'});continue
        taskmetrics=[];fit_metadata=[];previous=None;started=time.monotonic()
        try:
            for population in ('retained','full'):
                fitrows=[r for r in train if eligible(r)] if population=='retained' else train
                evalrows=[r for r in test if eligible(r)] if population=='retained' else test
                if not fitrows or not evalrows:raise ValueError('Empty official train/test population')
                checkpoint_dir=taskdir/population;checkpoint_dir.mkdir();safe()
                # Identical populations reuse the already completed final model and predictions.
                if previous is not None and len(fitrows)==previous[0] and len(evalrows)==previous[1]:
                    prediction=previous[2];fitmeta={'reused_retained_fit':True}
                else:
                    prediction,fitmeta=train_predict(fitrows,evalrows,classifier,checkpoint_dir,task,population)
                if population=='retained':previous=(len(fitrows),len(evalrows),prediction)
                fit_metadata.append(dict(fit_population=population,**fitmeta))
                train_mean=float(np.mean([r['y'] for r in fitrows]))
                indices=np.arange(len(evalrows))
                populations={'retained':indices} if population=='retained' else {'full':indices,'retained':np.array([i for i,r in enumerate(evalrows) if eligible(r)],dtype=int),'excluded':np.array([i for i,r in enumerate(evalrows) if not eligible(r)],dtype=int)}
                fitmetrics=[]
                for evaluation_population,index in populations.items():
                    if not len(index):
                        fitmetrics.append({'dataset':group,'task':task,'model':'Chemprop-v2','fit_population':population,'evaluation_population':evaluation_population,'metric_status':'EMPTY_EVALUATION_POPULATION','n_test_rows':0});continue
                    subset=[evalrows[i] for i in index]
                    metric=score([r['y'] for r in subset],prediction[index],train_mean,[r['full_inchikey'] for r in subset])
                    fitmetrics.append(dict(dataset=group,task=task,model='Chemprop-v2',feature_group='2D_graph',task_type='binary_classification' if classifier else 'regression',fit_population=population,evaluation_population=evaluation_population,seed=SEED,n_train=len(fitrows),training_mean=train_mean,**metric))
                safe()
                records=[{'dataset':group,'task':task,'model':'Chemprop-v2','fit_population':population,'record_id':r['record_id'],'full_inchikey':r['full_inchikey'],'y_true':r['y'],'prediction':float(p),'training_mean':train_mean,'retained':r['retained'],'domain_eligible':r['domain_eligible']} for r,p in zip(evalrows,prediction)]
                pq.write_table(pa.Table.from_pylist(records,schema=prediction_schema),taskdir/(population+'_predictions.parquet'),compression='zstd')
                (taskdir/(population+'_results.json')).write_text(json.dumps({'results':fitmetrics,'fit_metadata':fitmeta},indent=2)+'\n')
                taskmetrics.extend(fitmetrics);results.extend(fitmetrics)
                print('B1_CHEMPROP_TASK_FIT_CLOSED',group,task,population,'seconds',round(time.monotonic()-started,2),flush=True)
            (taskdir/'task_metadata.json').write_text(json.dumps({'dataset':group,'task':task,'fit_metadata':fit_metadata,'elapsed_seconds':time.monotonic()-started},indent=2)+'\n')
        except Exception as error:
            failure={'dataset':group,'task':task,'status':'UNRESOLVED','error':repr(error)}
            failures.append(failure);traceback.print_exc();print('B1_CHEMPROP_FAILURE',json.dumps(failure),flush=True)
fields=list(dict.fromkeys(k for result in results for k in result))
with (out/'B1_Chemprop_partial_results.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields or ['task']);writer.writeheader();writer.writerows(results)
report={'status':'B1_CHEMPROP_INITIAL_OFFICIAL_SOURCE_GROUPS_CLOSED','job':os.environ['SLURM_JOB_ID'],'protocol':protocol,'source_contract':str(features/'manifest.json'),'tasks_expected':40,'tasks_seen':task_index,'successful_task_models':sum(r.get('fit_population')=='retained' and r.get('evaluation_population')=='retained' for r in results),'failures':failures,'coverage':coverage_report,'new_unit_tests':suite.countTestCases()+binding_suite.countTestCases(),'model_selection_used_TEST':False,'hyperparameter_search':False,'task_screen_decisions_produced':False,'other_source_groups_still_required':True}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('B1_CHEMPROP_SOURCE_CLOSED',out/'manifest.json','models',report['successful_task_models'],'failures',len(failures),flush=True)

PY
