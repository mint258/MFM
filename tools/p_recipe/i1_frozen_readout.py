"""I1 frozen readouts: original R3 on GPU and original ridge on CPU."""
from dataclasses import replace
import json,os,time
from pathlib import Path
import torch
import evaluate as native
from finetune_statistics_entry import atomic_json

def panel_tasks():
 panel=json.loads((native.REPO/'configs/dev_panel_v3.json').read_text())
 return [replace(native.TaskSpec(**{k:t[k] for k in ('task_id','dataset_id','field','output_level','error_metric','pooling')}),pooling='mean') for t in panel['tasks']]

def views(c):
 store=native.TrainOnlyPackedStore(c['store'],verify_digests=False)
 return {d:native.GroupedTrainingView(store,d,'official' if d=='expansionrx' else '0',store.group_map) for d in ('expansionrx','cyp_isoform','qm9')}

def save_prediction(path,prediction,detail):
 temporary=path.with_name(path.name+'.new')
 torch.save(dict(prediction=native._pack(prediction),detail=detail),temporary)
 os.replace(temporary,path)

def gpu_r3(c):
 output=Path(c['output']);output.mkdir(parents=True,exist_ok=True)
 tasks=panel_tasks();history=native.History(output/'probe_history.jsonl')
 torch.set_num_threads(16);torch.set_float32_matmul_precision('highest')
 torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 files,details,label_stds={},{},{}
 for dataset,view in views(c).items():
  memory=native.produce_missing_features(c,dataset,view)
  payload=torch.load(native.feature_path(c,dataset),map_location='cpu',weights_only=True) if memory is None else memory
  cached=native.cached_rows(payload)
  for task in (t for t in tasks if t.dataset_id==dataset):
   maker=native.atomization_rows if task.task_id==native.ATOMIZATION_TASK_ID else native.task_rows
   train=maker(view,cached,task,role='train');validation=maker(view,cached,task,role='train_inner_validation')
   labels=torch.cat([r.targets[r.supervision_mask&r.candidate_mask].double() for r in train])
   label_stds[task.task_id]=float(labels.std(unbiased=False))
   key=task.task_id+'/R3';path=output/(task.task_id.replace('.','_')+'__R3.pt')
   if not path.exists():
    history.cell=key
    prediction,detail=native.run_probe(train,validation,task,readout='R3',n_ref=payload['n_ref'],seed=0,device='cuda',tracker=history,relative_std_floor=True,internal_epoch_selection=True)
    save_prediction(path,prediction,detail)
   saved=torch.load(path,map_location='cpu',weights_only=True)
   details[key]={k:v for k,v in saved['detail'].items() if k!='state_dict'};files[key]=str(path)
   print(json.dumps(dict(run=c['run'],cell=key,error=native.error(native._unpack(saved['prediction'])),removed_dimensions=details[key].get('removed_dimensions',0))),flush=True)
 manifest=dict(run=c['run'],files=files,details=details,label_stds=label_stds,stage=c.get('stage',0),round=c.get('round',0),arm=c['arm'],samples=c['samples'],protocol='p_recipe',source_roles=['train','train_inner_validation'],R1_deferred_to_CPU=True)
 atomic_json(output/'predictions.json',manifest)
 return manifest

def complete_r1(c,should_stop):
 output=Path(c['output']);path=output/'predictions.json';manifest=json.loads(path.read_text())
 tasks=panel_tasks()
 if manifest['run']!=c['run'] or manifest['samples']!=3000000:raise ValueError('I1 readout identity differs')
 if {t.task_id+'/R3' for t in tasks}-set(manifest['files']):raise ValueError('Original GPU R3 coverage incomplete')
 for dataset,view in views(c).items():
  if should_stop():return False
  payload=torch.load(native.feature_path(c,dataset),map_location='cpu',weights_only=True)
  cached=native.cached_rows(payload)
  for task in (t for t in tasks if t.dataset_id==dataset):
   if should_stop():return False
   key=task.task_id+'/R1'
   if key in manifest['files']:continue
   maker=native.atomization_rows if task.task_id==native.ATOMIZATION_TASK_ID else native.task_rows
   train=maker(view,cached,task,role='train');validation=maker(view,cached,task,role='train_inner_validation')
   result=output/(task.task_id.replace('.','_')+'__R1.pt')
   if not result.exists():
    prediction,detail=native.ridge_probe(train,validation,task,relative_std_floor=True)
    save_prediction(result,prediction,detail)
   saved=torch.load(result,map_location='cpu',weights_only=True)
   manifest['files'][key]=str(result);manifest['details'][key]={k:v for k,v in saved['detail'].items() if k!='state_dict'}
   atomic_json(path,manifest)
 assert len(manifest['files'])==18
 manifest['R1_deferred_to_CPU']=False;manifest['R1_CPU_complete']=True;atomic_json(path,manifest)
 return True
