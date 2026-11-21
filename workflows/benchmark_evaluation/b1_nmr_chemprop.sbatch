#!/bin/bash
#SBATCH --job-name=B1-NMR-Chemprop-atomic
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=4
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=12:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_Chemprop_NMR_%j.log
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
from chemprop.nn.message_passing.mol_atom_bond import MABBondMessagePassing
from rdkit import Chem
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


def eligible(row):return bool(row['retained'] and row['domain_eligible'])
def native_point(row):
    mol=Chem.Mol(row['original_mol_binary']);mol.UpdatePropertyCache(strict=False);Chem.GetSymmSSSR(mol)
    values=np.full((mol.GetNumAtoms(),1),np.nan,dtype=float)
    expected=6 if row['nucleus']=='13C' else 1
    seen=set()
    for atom in row['atoms']:
        index=atom['original_atom_index']
        if index in seen or not 0<=index<mol.GetNumAtoms() or mol.GetAtomWithIdx(index).GetAtomicNum()!=expected:raise ValueError('Invalid original atomic target index')
        seen.add(index);values[index,0]=atom['y']
    return data.MolAtomBondDatapoint(mol=mol,atom_y=values,name=row['record_id'])
def evaluation_binding(rows):
    indices=[];metadata=[];offset=0
    for row in rows:
        n=Chem.Mol(row['original_mol_binary']).GetNumAtoms()
        for atom in row['atoms']:
            index=atom['original_atom_index']
            if not 0<=index<n:raise ValueError('Native atom index outside graph')
            indices.append(offset+index)
            metadata.append(dict(dataset='NMRShiftDB2',task=row['nucleus'],record_id=row['record_id']+':atom:'+str(index),original_spectrum_record_id=row['record_id'],original_atom_index=index,full_inchikey=row['full_inchikey'],y=atom['y'],retained=row['retained'],domain_eligible=row['domain_eligible']))
        offset+=n
    return np.asarray(indices,dtype=np.int64),metadata,offset
def mock_row(smiles,nucleus,index,y,name):
    mol=Chem.AddHs(Chem.MolFromSmiles(smiles))
    return dict(original_mol_binary=mol.ToBinary(),nucleus=nucleus,atoms=[dict(original_atom_index=index,y=y)],record_id=name,full_inchikey=Chem.MolToInchiKey(mol),retained=True,domain_eligible=True)
class NativeAtomInterfaceTests(unittest.TestCase):
    def test_native_explicit_H_indices_and_missing_target_mask_are_preserved(self):
        row=mock_row('CCO','1H',3,2.5,'s1');point=native_point(row)
        self.assertEqual(point.mol.GetAtomWithIdx(3).GetAtomicNum(),1)
        self.assertEqual(point.atom_y.shape,(9,1));self.assertEqual(point.atom_y[3,0],2.5)
        self.assertEqual(np.isfinite(point.atom_y).sum(),1)
    def test_batch_atom_offsets_preserve_duplicate_spectra(self):
        rows=[mock_row('CCO','13C',1,42.,'s1'),mock_row('CCC','13C',0,43.,'s2')]
        indices,metadata,total=evaluation_binding(rows)
        self.assertEqual(indices.tolist(),[1,9])
        self.assertEqual([r['record_id'] for r in metadata],['s1:atom:1','s2:atom:0'])
        self.assertEqual(total,20)
    def test_TRAIN_only_atomic_scaler_ignores_unlabeled_atoms(self):
        rows=[mock_row('CCC','13C',0,2.,'s1'),mock_row('CCO','13C',1,4.,'s2')]
        dataset=data.MolAtomBondDataset([native_point(r) for r in rows])
        scaler=dataset.normalize_targets(key='atom')
        self.assertAlmostEqual(float(scaler.mean_[0]),3.)
        self.assertEqual(np.isfinite(np.concatenate(dataset.atom_Y)).sum(),2)
    def test_official_atom_head_returns_all_native_atoms_without_molecular_prediction(self):
        row=mock_row('CCO','13C',0,12.,'s1')
        dataset=data.MolAtomBondDataset([native_point(row)])
        batch=next(iter(data.build_dataloader(dataset,batch_size=1,shuffle=False,drop_last=False)))
        model=models.MolAtomBondMPNN(MABBondMessagePassing(return_edge_embeddings=False),atom_predictor=nn.RegressionFFN())
        model.eval()
        with torch.inference_mode():outputs=model(batch.bmg,batch.V_d,batch.E_d,batch.X_d)
        self.assertIsNone(outputs[0]);self.assertIsNone(outputs[2])
        self.assertEqual(tuple(outputs[1].shape),(9,1))
tests=unittest.defaultTestLoader.loadTestsFromTestCase(NativeAtomInterfaceTests)
if not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,3*1024**3,quota,own_concurrent_bytes=24*1024**3)
safe();features=b1/'B1_NMR_features/job_4536984';contract=json.loads((features/'manifest.json').read_text())
proof=json.loads(Path(contract['full_inventory_scope_proof']).read_text());assert proof['deferred_registry_full_inventory_verified'] and proof['deferred_endpoint_count']==5
out=b1/'B1_Chemprop_NMR'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
os.environ['TMPDIR']=str(out/'tmp');(out/'tmp').mkdir();import tempfile;tempfile.tempdir=os.environ['TMPDIR']
protocol=dict(model='Chemprop-v2',interface='Official Chemprop 2.2.2 MolAtomBondMPNN with MABBondMessagePassing and atom-only RegressionFFN',source_graph='Original Jonas2019 RDKit graph binary, native explicit hydrogen atom order',seed=SEED,epochs=50,batch_size=64,message_passing_hidden_size=300,message_passing_depth=3,FFN='Official RegressionFFN defaults',optimizer='Official Adam/Noam-like defaults init_lr=1e-4,max_lr=1e-3,final_lr=1e-4,warmup_epochs=2',checkpoint_selection='Fixed final epoch, no validation or TEST selection',target_normalization='Original TRAIN labeled atomic values only; unlabeled native atoms remain NaN masks',reference_predictor='Arithmetic mean of original unscaled labeled TRAIN atomic values',full_filter_impact='Separate full-source TRAIN fit, full/retained/excluded TEST',paired_bootstrap='1000 full-molecule-group draws',hyperparameter_search=False,default_seed_count=1)
(out/'protocol_before_fitting.json').write_text(json.dumps(protocol,indent=2)+'\n')
class DiskGuard(Callback):
    def on_train_epoch_start(self,trainer,module):safe()
    def on_train_epoch_end(self,trainer,module):print('B1_NMR_CHEMPROP_EPOCH',self.task,self.population,trainer.current_epoch+1,flush=True)
def train_predict(train_rows,test_rows,checkpoint_dir,task,population):
    pl.seed_everything(SEED,workers=True,verbose=False)
    training=data.MolAtomBondDataset([native_point(r) for r in train_rows]);testing=data.MolAtomBondDataset([native_point(r) for r in test_rows])
    training.cache=True;testing.cache=True
    scaler=training.normalize_targets(key='atom')
    predictor=nn.RegressionFFN(output_transform=nn.UnscaleTransform.from_standard_scaler(scaler))
    model=models.MolAtomBondMPNN(MABBondMessagePassing(return_edge_embeddings=False),atom_predictor=predictor)
    loader=data.build_dataloader(training,batch_size=64,num_workers=0,seed=SEED,shuffle=True)
    testloader=data.build_dataloader(testing,batch_size=64,num_workers=0,shuffle=False,drop_last=False)
    guard=DiskGuard();guard.task=task;guard.population=population
    checkpoint=ModelCheckpoint(dirpath=checkpoint_dir,save_last=True,save_top_k=0,every_n_epochs=1,enable_version_counter=False)
    trainer=pl.Trainer(accelerator='cpu',devices=1,max_epochs=50,logger=False,enable_checkpointing=True,callbacks=[guard,checkpoint],enable_progress_bar=False,enable_model_summary=False,num_sanity_val_steps=0,limit_val_batches=0,default_root_dir=checkpoint_dir,log_every_n_steps=50)
    trainer.fit(model,loader)
    with torch.inference_mode():
        outputs=trainer.predict(model,testloader)
        all_atoms=torch.cat([batch[1] for batch in outputs],dim=0).reshape(-1).detach().cpu().numpy().astype(float)
    indices,metadata,expected_atoms=evaluation_binding(test_rows)
    if len(all_atoms)!=expected_atoms:raise ValueError('Official atom output lost native graph/atom correspondence')
    prediction=all_atoms[indices]
    if not np.isfinite(prediction).all():raise ValueError('Nonfinite experimental-atom predictions')
    fitmeta=dict(completed_epochs=trainer.current_epoch,model_hyperparameters=str(model.hparams),target_scaler_mean=scaler.mean_.tolist(),target_scaler_scale=scaler.scale_.tolist(),final_checkpoint=str(checkpoint_dir/'last.ckpt'),predicted_native_atom_count=expected_atoms,scored_original_experimental_atom_count=len(indices))
    del trainer,model,training,testing,loader,testloader,outputs,all_atoms;gc.collect()
    return prediction,metadata,fitmeta
prediction_schema=pa.schema([('dataset',pa.string()),('task',pa.string()),('model',pa.string()),('fit_population',pa.string()),('record_id',pa.string()),('original_spectrum_record_id',pa.string()),('original_atom_index',pa.int32()),('full_inchikey',pa.string()),('y_true',pa.float64()),('prediction',pa.float64()),('training_mean',pa.float64()),('retained',pa.bool_()),('domain_eligible',pa.bool_())])
results=[];failures=[];coverage=[]
for nucleus in ('13C','1H'):
    rows=[]
    for batch in pq.ParquetFile(features/(nucleus+'.parquet')).iter_batches(batch_size=256):
        rows.extend(r for r in batch.to_pylist() if r['atoms'])
    train=[r for r in rows if r['official_split']=='train'];test=[r for r in rows if r['official_split']=='test']
    coverage.append(dict(dataset='NMRShiftDB2',task=nucleus,train_original_spectra=len(train),test_original_spectra=len(test),filtered_total_labeled_points=sum(len(r['atoms']) for r in rows if eligible(r))))
    safe();taskdir=out/nucleus;taskdir.mkdir();reuse=None;task_predictions=[];task_results=[];fit_metadata=[]
    try:
        for fit_population in ('retained','full'):
            train_pop=[r for r in train if eligible(r)] if fit_population=='retained' else train
            test_pop=[r for r in test if eligible(r)] if fit_population=='retained' else test
            if not train_pop or not test_pop:raise ValueError('Empty original NMR train/test population')
            if fit_population=='full' and reuse is not None and len(train_pop)==reuse[0] and len(test_pop)==reuse[1]:
                prediction,metadata,fitmeta=reuse[2:]
                fitmeta=dict(fitmeta,fit_reused_identical_source_population=True)
            else:
                prediction,metadata,fitmeta=train_predict(train_pop,test_pop,taskdir/fit_population,nucleus,fit_population)
            if fit_population=='retained':reuse=(len(train_pop),len(test_pop),prediction,metadata,fitmeta)
            train_mean=float(np.mean([atom['y'] for r in train_pop for atom in r['atoms']]))
            fit_metadata.append(dict(fit_population=fit_population,**fitmeta))
            indices=np.arange(len(metadata))
            populations={'retained':indices} if fit_population=='retained' else {'full':indices,'retained':np.array([i for i,r in enumerate(metadata) if eligible(r)],dtype=int),'excluded':np.array([i for i,r in enumerate(metadata) if not eligible(r)],dtype=int)}
            for evaluation_population,index in populations.items():
                if not len(index):
                    task_results.append(dict(dataset='NMRShiftDB2',task=nucleus,model='Chemprop-v2',fit_population=fit_population,evaluation_population=evaluation_population,metric_status='EMPTY_EVALUATION_POPULATION',n_test_rows=0));continue
                subset=[metadata[i] for i in index]
                metric=score([r['y'] for r in subset],prediction[index],train_mean,[r['full_inchikey'] for r in subset])
                task_results.append(dict(dataset='NMRShiftDB2',task=nucleus,model='Chemprop-v2',task_type='atom_regression',fit_population=fit_population,evaluation_population=evaluation_population,seed=SEED,n_train=sum(len(r['atoms']) for r in train_pop),training_mean=train_mean,**metric))
            task_predictions.extend([dict(dataset='NMRShiftDB2',task=nucleus,model='Chemprop-v2',fit_population=fit_population,record_id=r['record_id'],original_spectrum_record_id=r['original_spectrum_record_id'],original_atom_index=r['original_atom_index'],full_inchikey=r['full_inchikey'],y_true=r['y'],prediction=float(p),training_mean=train_mean,retained=r['retained'],domain_eligible=r['domain_eligible']) for r,p in zip(metadata,prediction)])
        safe();pq.write_table(pa.Table.from_pylist(task_predictions,schema=prediction_schema),taskdir/'Chemprop-v2_predictions.parquet',compression='zstd')
        (taskdir/'Chemprop-v2_results.json').write_text(json.dumps(dict(dataset='NMRShiftDB2',task=nucleus,model='Chemprop-v2',results=task_results,fits=fit_metadata,protocol=protocol),indent=2)+'\n')
        results.extend(task_results);print('B1_NMR_CHEMPROP_TASK_CLOSED',nucleus,flush=True)
    except Exception as error:
        failures.append(dict(dataset='NMRShiftDB2',task=nucleus,model='Chemprop-v2',status='UNRESOLVED',error=repr(error)));traceback.print_exc()
    del rows,train,test,reuse,task_predictions;gc.collect()
fields=list(dict.fromkeys(k for result in results for k in result))
with (out/'B1_Chemprop_NMR_partial_results.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields or ['task']);writer.writeheader();writer.writerows(results)
report=dict(status='B1_NMR_CHEMPROP_ATOMIC_SOURCE_CLOSED',job=os.environ['SLURM_JOB_ID'],source_contract=str(features/'manifest.json'),tasks_expected=2,tasks_completed=sum(r.get('fit_population')=='retained' and r.get('evaluation_population')=='retained' for r in results),failures=failures,coverage=coverage,protocol=protocol,new_unit_tests=suite.countTestCases()+tests.countTestCases(),task_screen_decisions_produced=False,experimental_labels_not_averaged=True,atom_indices_not_permuted=True,model_and_hyperparameter_selection_used_TEST=False,independent_numeric_readback=False)
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('B1_NMR_CHEMPROP_SOURCE_CLOSED',out/'manifest.json','tasks',report['tasks_completed'],'failures',len(failures),flush=True)

PY
