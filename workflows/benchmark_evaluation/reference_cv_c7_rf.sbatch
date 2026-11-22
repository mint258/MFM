#!/bin/bash
#SBATCH --job-name=B1-C7-RF-scaffold25
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=12:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_reference_CV_models_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import csv,json,math,os,time,traceback,importlib.metadata,gc,unittest
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from lightgbm import LGBMRegressor
from sklearn.ensemble import RandomForestRegressor
from workflows.benchmark_data.admission import protect
SEED=20261025
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,4*1024**3,quota,own_concurrent_bytes=40*1024**3)
safe();binding_job=os.environ.get('REFERENCE_BINDING_JOB','4536995');model_name=os.environ.get('BENCHMARK_MODEL','RF-ECFP4')
if model_name not in ('RF-ECFP4','LightGBM-RDKit2D','Chemprop-v2','C1-LightGBM-D'):raise ValueError('Unregistered reference model')
cpus=int(os.environ['SLURM_CPUS_PER_TASK']);binding_path=b1/('reference_cv_binding/job_'+binding_job)/'manifest.json';binding=json.loads(binding_path.read_text())
proof=json.loads(Path(binding['full_inventory_scope_proof']).read_text());assert proof['deferred_registry_full_inventory_verified'] and proof['deferred_endpoint_count']==5
out=b1/'reference_cv_models'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
tmp=out/'tmp';tmp.mkdir();os.environ['TMPDIR']=str(tmp);import tempfile;tempfile.tempdir=str(tmp)
protocol=dict(seed=SEED,model=model_name,fold_binding=str(binding_path),cv='Pre-frozen five repetitions of five scaffold folds',hyperparameter_search=False,all_missing_native_features_filled=False,TEST_model_selection=False,reference_predictor='Mean of original unscaled TRAIN labels separately within each fold and fit population',statistics='Per-fold MAE/RAE for 25-fold Tukey HSD; whole-molecule paired bootstrap and one-time screening only after all three B1 models are complete',partial_fit_resume='Closed per-fold result/prediction files are preserved; no completed fit is overwritten or silently repeated',full_filter_impact=model_name!='C1-LightGBM-D')
if model_name=='Chemprop-v2':protocol.update(epochs=50,architecture='Chemprop 2.2.2 BondMessagePassing 300/depth3, MeanAggregation, default RegressionFFN',optimizer='Official Adam/Noam-like init_lr=1e-4,max_lr=1e-3,final_lr=1e-4,warmup2',batch_size=64,checkpoint_selection='Final epoch only; last.ckpt saved every completed epoch')
safe();(out/'protocol_before_fitting.json').write_text(json.dumps(protocol,indent=2)+'\n')
def eligible(row):return bool(row['retained'] and row['domain_eligible'])
def matrix(rows):
    if model_name=='RF-ECFP4':return np.asarray([np.unpackbits(np.frombuffer(r['ecfp4_2048_packed'],dtype=np.uint8),bitorder='little') for r in rows],dtype=np.uint8)
    return np.asarray([r['D_features'] if model_name=='C1-LightGBM-D' else r['rdkit_2d'] for r in rows],dtype=float)
def mean_reference_metrics(y,prediction,training_mean):
    y=np.asarray(y,float);prediction=np.asarray(prediction,float)
    if y.shape!=prediction.shape or not len(y) or not np.isfinite(y).all() or not np.isfinite(prediction).all():raise ValueError('Invalid fixed fold population')
    numerator=float(np.abs(y-prediction).sum());denominator=float(np.abs(y-training_mean).sum())
    return dict(MAE=numerator/len(y),RAE=numerator/denominator if denominator>0 else None,n_test_rows=len(y),metric_status='OK' if denominator>0 else 'ZERO_TRAIN_MEAN_REFERENCE_ERROR')
def fixed_population(membership,values,split,population):
    if split not in ('train','test') or population not in ('retained','full'):raise ValueError('Unknown fixed population')
    return [values[key] for key in membership[split] if key in values and (population=='full' or eligible(values[key]))]
class FixedCVInterfaceTests(unittest.TestCase):
    def test_filtering_does_not_move_test_molecules_into_training(self):
        membership={'train':['inside','outside'],'test':['heldout']}
        values={'inside':dict(retained=True,domain_eligible=True),'outside':dict(retained=False,domain_eligible=False),'heldout':dict(retained=True,domain_eligible=True)}
        self.assertEqual(len(fixed_population(membership,values,'train','retained')),1)
        self.assertEqual(len(fixed_population(membership,values,'train','full')),2)
        self.assertTrue(all(row is not values['heldout'] for row in fixed_population(membership,values,'train','full')))
    def test_RAE_uses_frozen_fold_training_mean(self):
        metric=mean_reference_metrics([2.,4.],[1.,3.],0.)
        self.assertAlmostEqual(metric['RAE'],1/3)
    def test_nonfinite_predictions_do_not_shrink_the_fixed_fold(self):
        with self.assertRaises(ValueError):mean_reference_metrics([1.,2.],[1.,float('nan')],0.)
tests=unittest.defaultTestLoader.loadTestsFromTestCase(FixedCVInterfaceTests)
if not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful():raise SystemExit(1)
def fit_predict(train,test,directory,tag):
    if model_name=='Chemprop-v2':
        import torch
        from lightning import pytorch as pl
        from lightning.pytorch.callbacks import Callback,ModelCheckpoint
        from chemprop import data,nn,models
        torch.set_num_threads(cpus)
        pl.seed_everything(SEED,workers=True,verbose=False)
        training=data.MoleculeDataset([data.MoleculeDatapoint.from_smi(r['feature_smiles'],[r['y']]) for r in train]);testing=data.MoleculeDataset([data.MoleculeDatapoint.from_smi(r['feature_smiles'],[r['y']]) for r in test])
        training.cache=True;testing.cache=True;scaler=training.normalize_targets()
        predictor=nn.RegressionFFN(output_transform=nn.UnscaleTransform.from_standard_scaler(scaler))
        model=models.MPNN(nn.BondMessagePassing(),nn.MeanAggregation(),predictor)
        loader=data.build_dataloader(training,batch_size=64,num_workers=0,seed=SEED,shuffle=True)
        testloader=data.build_dataloader(testing,batch_size=64,num_workers=0,shuffle=False,drop_last=False)
        class Guard(Callback):
            def on_train_epoch_start(self,trainer,module):safe()
            def on_train_epoch_end(self,trainer,module):print('REFERENCE_CV_CHEMPROP_EPOCH',tag,trainer.current_epoch+1,flush=True)
        checkpoint=ModelCheckpoint(dirpath=directory,save_last=True,save_top_k=0,every_n_epochs=1,enable_version_counter=False)
        trainer=pl.Trainer(accelerator='cpu',devices=1,max_epochs=50,logger=False,enable_checkpointing=True,callbacks=[Guard(),checkpoint],enable_progress_bar=False,enable_model_summary=False,num_sanity_val_steps=0,limit_val_batches=0,default_root_dir=directory)
        trainer.fit(model,loader)
        with torch.inference_mode():prediction=torch.cat(trainer.predict(model,testloader),dim=0).reshape(-1).cpu().numpy().astype(float)
        meta=dict(completed_epochs=trainer.current_epoch,target_scaler_mean=scaler.mean_.tolist(),target_scaler_scale=scaler.scale_.tolist(),final_checkpoint=str(directory/'last.ckpt'))
        del model,training,testing,trainer,loader,testloader;gc.collect()
        return prediction,meta
    parameters=dict(random_state=SEED,n_jobs=cpus)
    if model_name!='RF-ECFP4':parameters['verbosity']=-1
    factory=RandomForestRegressor if model_name=='RF-ECFP4' else LGBMRegressor
    model=factory(**parameters);xtrain=matrix(train);xtest=matrix(test);model.fit(xtrain,np.asarray([r['y'] for r in train],float))
    prediction=np.asarray(model.predict(xtest),float);meta=dict(parameters=model.get_params(),feature_count=xtrain.shape[1],random_forest_saved=False)
    if model_name!='RF-ECFP4':
        safe();model.booster_.save_model(str(directory/'model.txt'))
    del model,xtrain,xtest;gc.collect()
    return prediction,meta
pred_schema=pa.schema([('dataset',pa.string()),('task',pa.string()),('model',pa.string()),('feature_group',pa.string()),('repetition',pa.int32()),('fold',pa.int32()),('fit_population',pa.string()),('record_id',pa.string()),('original_record_id',pa.string()),('full_inchikey',pa.string()),('y_true',pa.float64()),('prediction',pa.float64()),('training_mean',pa.float64()),('retained',pa.bool_()),('domain_eligible',pa.bool_())])
results=[];failures=[];coverage=[];completed_fits=0
for spec in binding['source_groups']:
    if spec['status']!='FIXED_FIVE_BY_FIVE_SCAFFOLD_FOLDS_CLOSED':failures.append(dict(dataset=spec['dataset'],status=spec['status']));continue
    group=spec['dataset'];features={r['record_id']:r for r in pq.read_table(spec['features']).to_pylist()}
    labels=pq.read_table(spec['official_endpoint_labels']).to_pylist();tasks=defaultdict(dict)
    for label in labels:
        row=features[label['record_id']]
        if model_name=='C1-LightGBM-D' and (row['D_features'] is None or not np.isfinite(np.asarray(row['D_features'],float)).any()):continue
        tasks[label['task']][label['record_id']]=dict(row,y=label['y'])
    folds=defaultdict(lambda:defaultdict(list))
    for row in pq.read_table(spec['scaffold_folds']).to_pylist():folds[(row['repetition'],row['fold'])][row['split']].append(row['record_id'])
    if set(folds)!={(r,f) for r in range(5) for f in range(5)}:raise ValueError('Incomplete fixed 25-fold binding')
    for task,values in sorted(tasks.items()):
        coverage.append(dict(dataset=group,task=task,model=model_name,source_endpoint_binding=spec['official_endpoint_labels'],n_total_labeled_feature_available_points=len(values),filtered_labeled_feature_available_points=sum(eligible(r) for r in values.values())))
        safe();taskdir=out/group/task;taskdir.mkdir(parents=True)
        task_failure_count=0
        for (repetition,fold),membership in sorted(folds.items()):
            if task_failure_count>=2:break
            reuse=None
            for fit_population in (('retained',) if model_name=='C1-LightGBM-D' else ('retained','full')):
                started=time.monotonic();fitdir=taskdir/('r%d_f%d_%s'%(repetition,fold,fit_population));safe();fitdir.mkdir()
                try:
                    train=fixed_population(membership,values,'train',fit_population)
                    test=fixed_population(membership,values,'test',fit_population)
                    if not train or not test:raise ValueError('Empty fixed scaffold population; no split substitution')
                    mean=float(np.mean([r['y'] for r in train]))
                    if fit_population=='full' and reuse is not None and len(train)==reuse[0] and len(test)==reuse[1]:
                        prediction=reuse[2];fitmeta=dict(reused_identical_retained_fit=True)
                    else:prediction,fitmeta=fit_predict(train,test,fitdir,group+':'+task+':r'+str(repetition)+':f'+str(fold)+':'+fit_population)
                    if fit_population=='retained':reuse=(len(train),len(test),prediction)
                    if len(prediction)!=len(test) or not np.isfinite(prediction).all():raise ValueError('Prediction does not cover the fixed fold population')
                    pops={'retained':list(range(len(test)))} if fit_population=='retained' else {'full':list(range(len(test))),'retained':[i for i,r in enumerate(test) if eligible(r)],'excluded':[i for i,r in enumerate(test) if not eligible(r)]}
                    metrics=[]
                    for name,indices in pops.items():
                        base=dict(dataset=group,task=task,model=model_name,feature_group='D' if model_name=='C1-LightGBM-D' else ('ECFP4' if model_name=='RF-ECFP4' else 'RDKit2D' if model_name=='LightGBM-RDKit2D' else '2D_graph'),repetition=repetition,fold=fold,fit_population=fit_population,evaluation_population=name,seed=SEED,n_train=len(train),training_mean=mean)
                        metric=mean_reference_metrics([test[i]['y'] for i in indices],prediction[indices],mean) if indices else dict(metric_status='EMPTY_EVALUATION_POPULATION',n_test_rows=0)
                        metrics.append(dict(base,**metric))
                    predictions=[dict(dataset=group,task=task,model=model_name,feature_group='D' if model_name=='C1-LightGBM-D' else 'B1',repetition=repetition,fold=fold,fit_population=fit_population,record_id=r['record_id']+'::repeat:'+str(repetition),original_record_id=r['record_id'],full_inchikey=r['full_inchikey'],y_true=r['y'],prediction=float(p),training_mean=mean,retained=r['retained'],domain_eligible=r['domain_eligible']) for r,p in zip(test,prediction)]
                    safe();pq.write_table(pa.Table.from_pylist(predictions,schema=pred_schema),fitdir/'predictions.parquet',compression='zstd')
                    record=dict(dataset=group,task=task,model=model_name,repetition=repetition,fold=fold,fit_population=fit_population,elapsed_seconds=time.monotonic()-started,results=metrics,fit_metadata=fitmeta)
                    (fitdir/'results.json').write_text(json.dumps(record,indent=2)+'\n');results.extend(metrics);completed_fits+=1
                    print('REFERENCE_CV_MODEL_FIT_CLOSED',group,task,model_name,repetition,fold,fit_population,'seconds',round(record['elapsed_seconds'],2),flush=True)
                except Exception as error:
                    failure=dict(dataset=group,task=task,model=model_name,repetition=repetition,fold=fold,fit_population=fit_population,status='UNRESOLVED',error=repr(error));failures.append(failure);traceback.print_exc();safe();(fitdir/'failure.json').write_text(json.dumps(failure,indent=2)+'\n')
                    task_failure_count+=1
                    if task_failure_count>=2:
                        print('REFERENCE_CV_TASK_UNRESOLVED_AFTER_TWO_FIT_FAILURES',group,task,model_name,flush=True);break
            del reuse;gc.collect()
fields=list(dict.fromkeys(k for row in results for k in row))
with (out/'reference_CV_partial_results.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields or ['task']);writer.writeheader();writer.writerows(results)
report=dict(status='REFERENCE_CV_MODEL_FITS_CLOSED',job=os.environ['SLURM_JOB_ID'],model=model_name,source_binding=str(binding_path),protocol=protocol,closed_fit_populations=completed_fits,primary_task_folds_completed=sum(r['fit_population']=='retained' and r['evaluation_population']=='retained' for r in results),coverage=coverage,failures=failures,versions={name:importlib.metadata.version(name) for name in ('scikit-learn','lightgbm','numpy')},new_unit_tests=tests.countTestCases(),task_screen_decisions_produced=False,independent_numeric_readback=False)
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('REFERENCE_CV_MODEL_SOURCE_CLOSED',out/'manifest.json','primary_folds',report['primary_task_folds_completed'],'failures',len(failures),flush=True)

PY
