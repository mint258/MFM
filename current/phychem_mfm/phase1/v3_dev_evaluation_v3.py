"""New seven-task/atomization evaluation; historical v2 production stays unchanged."""
from __future__ import annotations
import fcntl,json,os,time
from pathlib import Path
import torch
from .v2_s_training import s_model
from .v3_dev_membership import GroupedTrainingView
from .v3_dev_evaluation import TaskSpec,task_rows,error
from .v3_dev_evaluation_v2 import (_json,_pack,_unpack,ProbeHistory,BASE,REPO,DATASETS)
from .v3_latent_evaluation import (_probe,feature_cache,cached_rows,z_rows)
from .v3_latent_training import TrainingHistory
from .v3_downstream_targets import (ATOMIZATION_TASK_ID,atomization_rows,
 compare_report_only_panel,PRIMARY_TASK_IDS,evaluation_scope_ready)

def rows_for(view,cached,task,role):
 return (atomization_rows if task.task_id==ATOMIZATION_TASK_ID else task_rows)(
  view,cached,task,role=role)

def load_files(path):
 path=Path(path)
 return json.loads(path.read_text()).get('files',{}) if path.is_file() else {}

def probe_path(directory,task,name):
 return Path(directory)/'probes'/(task.task_id.replace('.','_')+'__'+name+'.pt')

def reusable(files,task,name):
 # Only the exact new task ID can reuse atomization predictions; no U0 alias fallback.
 value=files.get(task.task_id+'/'+name)
 return value if value and Path(value).is_file() else None

def ensure_features(config,spec,views,encode,caches,needed,*,checkpoint=None):
 missing={dataset:view for dataset,view in views.items()
  if dataset in needed and not caches[dataset].is_file()}
 if not missing:return
 reference=checkpoint is None
 if reference:torch.manual_seed(20261025)
 model,_=s_model(config['distance_bias'],config['views'],
  latent='none' if spec is None else spec['kind'],latent_config=spec)
 if not reference:
  state=checkpoint['model']
  if any(key.startswith('structural.') for key in state):
   state={key.removeprefix('structural.'):value for key,value in state.items()
    if key.startswith('structural.')}
  model.load_state_dict(state)
 model=model.cuda().eval()
 for dataset,view in missing.items():
  feature_cache(model,{dataset:view},encode,caches[dataset].parent)
 del model
 torch.cuda.empty_cache()

def reference_files(config,spec,views,tasks,root,encode,history):
 architecture=config['distance_bias']
 has_z=spec is not None and spec['kind'] in ('pma','lite','lite_rec')
 groups=[('X',None,('R1','R2','R3'))]
 if has_z:
  profile=('pma' if spec['kind']=='pma' else 'lite')+'_k'+str(spec['k'])+'_write'+str(int(spec['write_back']))
  groups.append((profile,spec,('R1z','R2z')))
 result={}
 for profile,reference_spec,names in groups:
  destination=root/'panel_v3_references'/architecture/profile
  destination.mkdir(parents=True,exist_ok=True)
  with (destination/'producer.lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX)
   manifest=destination/'predictions.json'
   if manifest.is_file():
    result.update(load_files(manifest));continue
   if reference_spec is None:
    old=load_files(BASE/'reference'/architecture/'predictions.json')
    if architecture=='C1-0':old.update(load_files(root/'base_reference_R1/predictions.json'))
    cache_candidates=[BASE/'h0_cache'/('random__'+architecture+'__three'),
     root/('random__'+architecture+'__three')]
   else:
    legacy=root/('reference_z_'+profile)
    old=load_files(legacy/'predictions.json')
    cache_candidates=[legacy/'features']
   caches={dataset:next((path/(dataset+'.pt') for path in cache_candidates
    if (path/(dataset+'.pt')).is_file()),destination/'features'/(dataset+'.pt')) for dataset in DATASETS}
   relevant=[task for task in tasks if reference_spec is None or task.output_level=='graph']
   needed={task.dataset_id for task in relevant for name in names
    if not (name=='R3' and task.output_level=='atom') and not reusable(old,task,name)
    and not probe_path(destination,task,name).is_file()}
   reference_config=dict(config,views='three',seed=20261025)
   ensure_features(reference_config,reference_spec,views,encode,caches,needed)
   files={}
   for dataset,view in views.items():
    selected=[task for task in relevant if task.dataset_id==dataset]
    if not selected:continue
    payload=None;cached=None
    for task in selected:
     for name in names:
      key=task.task_id+'/'+name
      if name=='R3' and task.output_level=='atom':
       files[key]=files[task.task_id+'/R2'];continue
      reuse=reusable(old,task,name)
      if reuse:
       files[key]=reuse;continue
      path=probe_path(destination,task,name)
      if not path.is_file():
       if payload is None:
        payload=torch.load(caches[dataset],map_location='cpu',weights_only=True)
        cached=cached_rows(payload)
       train=rows_for(view,cached,task,'train')
       held=rows_for(view,cached,task,'train_inner_validation')
       if name.endswith('z'):train,held=z_rows(train,cached),z_rows(held,cached)
       history.cell='reference/v3/'+architecture+'/'+profile+'/'+key
       _probe(name,train,held,task,payload['n_ref'],history,path)
      files[key]=str(path)
   _json(dict(panel='v3',files=files,architecture=architecture,profile=profile,
    seed=20261025,random_reference_shared_across_conditions=True,
    source_roles=['train','train_inner_validation'],downstream_TEST_read=False),manifest)
   result.update(files)
 for task in tasks:
  if task.output_level=='atom' and has_z:
   result[task.task_id+'/R1z']=result[task.task_id+'/R1']
   result[task.task_id+'/R2z']=result[task.task_id+'/R2']
 return result

def evaluate(args,*,store_factory,encode):
 panel=json.loads((REPO/'configs/dev_panel_v3.json').read_text())
 scope=panel['authority']['retrospective_scope']
 if not evaluation_scope_ready(panel,getattr(args,'evaluation_scope',None)):
  raise ValueError('Retrospective scope is pending; only explicitly requested forward evaluation is active')
 from importlib.util import spec_from_file_location,module_from_spec
 spec_loader=spec_from_file_location('existing_development_registry',REPO/'tools/model_v3/v2_run_development.py')
 registry=module_from_spec(spec_loader);spec_loader.loader.exec_module(registry)
 budget=json.loads(registry.REGISTRY.read_text())
 for path in (args.output,args.cache_root):registry.require_registered_output(path,budget)
 output,root=Path(args.output),Path(args.cache_root)
 complete=output/'producer_complete.json'
 if complete.is_file():
  marker=json.loads(complete.read_text())
  if marker.get('panel')!='v3' or not marker.get('statistics_complete'):
   raise ValueError('Preserve a different existing producer; use a new output directory')
  return
 checkpoint=torch.load(args.checkpoint,map_location='cpu',weights_only=True)
 config=dict(checkpoint['configuration']);architecture=checkpoint['architecture']
 condition=config.get('condition') or getattr(args,'condition',None)
 if not condition or (getattr(args,'condition',None) is not None and args.condition!=condition):
  raise ValueError('Bind the actual checkpoint condition explicitly; do not infer it from a filename')
 config['condition']=condition
 if getattr(args,'reference_only',False):
  raise ValueError('Panel v3 produces shared random references inside the real checkpoint evaluation')
 spec=architecture['backbone'].get('v3_latent')
 has_z=spec is not None and spec['kind'] in ('pma','lite','lite_rec')
 stage=config.get('stage','C1');arm=config.get('arm',config['distance_bias'])
 output.mkdir(parents=True,exist_ok=True)
 _json(dict(checkpoint=str(args.checkpoint),panel='v3',retrospective_scope=scope,
  stage=stage,arm=arm,condition=config['condition'],cache_root=str(root),
  evaluation_scope=getattr(args,'evaluation_scope',None)),output/'configuration.json')
 store=store_factory(args.store)
 views={dataset:GroupedTrainingView(store,dataset,
  'official' if dataset=='expansionrx' else '0',store.group_map) for dataset in DATASETS}
 tasks=[TaskSpec(**{key:item[key] for key in
  ('task_id','dataset_id','field','output_level','error_metric','pooling')}) for item in panel['tasks']]
 owner=TrainingHistory(output,dict(checkpoint=str(args.checkpoint),panel='v3',
  stage=stage,condition=config['condition'],arm=arm,pretrained_encoder_frozen=True))
 history=ProbeHistory(owner.stream,owner.run)
 torch.set_num_threads(16);torch.set_float32_matmul_precision('highest')
 torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 started=time.monotonic();success=False
 try:
  references=reference_files(config,spec,views,tasks,root,encode,history)
  legacy=getattr(args,'reuse_predictions',None)
  old=load_files(legacy) if legacy else load_files(Path(args.checkpoint).parent/'dev_eval_v2/predictions.json')
  key=Path(args.checkpoint).parent.name+'__'+Path(args.checkpoint).stem
  candidates=[root/key,BASE/'h0_cache'/key]
  caches={dataset:next((path/(dataset+'.pt') for path in candidates
   if (path/(dataset+'.pt')).is_file()),root/key/(dataset+'.pt')) for dataset in DATASETS}
  names=('R1','R2','R3')+(('R1z','R2z') if has_z else ())
  needed={task.dataset_id for task in tasks for name in names
   if not (task.output_level=='atom' and name in ('R3','R1z','R2z'))
   and not reusable(old,task,name) and not probe_path(output,task,name).is_file()}
  ensure_features(config,spec,views,encode,caches,needed,checkpoint=checkpoint)
  files={}
  for dataset,view in views.items():
   payload=None;cached=None
   for task in (task for task in tasks if task.dataset_id==dataset):
    for name in names:
     cell=task.task_id+'/'+name
     if task.output_level=='atom' and name in ('R3','R1z','R2z'):
      files[cell]=files[task.task_id+('/R1' if name=='R1z' else '/R2')];continue
     reuse=reusable(old,task,name)
     if reuse:
      files[cell]=reuse;continue
     path=probe_path(output,task,name)
     if not path.is_file():
      if payload is None:
       payload=torch.load(caches[dataset],map_location='cpu',weights_only=True);cached=cached_rows(payload)
      train=rows_for(view,cached,task,'train');held=rows_for(view,cached,task,'train_inner_validation')
      if name.endswith('z'):train,held=z_rows(train,cached),z_rows(held,cached)
      history.cell=stage+'/'+arm+'/'+config['condition']+'/v3/'+cell
      _probe(name,train,held,task,payload['n_ref'],history,path)
     files[cell]=str(path)
  _json(dict(panel='v3',files=files,reference_files=references,architecture=architecture,
   checkpoint=str(args.checkpoint),condition=config['condition'],stage=stage,arm=arm,
   has_z=has_z,primary='R2z' if has_z else 'R3',source_roles=['train','train_inner_validation'],
   downstream_TEST_read=False,retrospective_scope=scope),output/'predictions.json')
  summaries={}
  for name in names:
   path=output/(name+'_summary.json')
   if path.is_file():
    summaries[name]=json.loads(path.read_text());continue
   actual,random={},{}
   for task in tasks:
    cell=task.task_id+'/'+name
    actual[task.task_id]=_unpack(torch.load(files[cell],map_location='cpu',weights_only=True)['prediction'])
    random[task.task_id]=_unpack(torch.load(references[cell],map_location='cpu',weights_only=True)['prediction'])
   identity=config['distance_bias']+':matched-initial-encoder-function:'+name
   summary=compare_report_only_panel(actual,random,architecture_sha256=identity,
    reference_architecture_sha256=identity,retain_paired_samples=True,retain_task_samples=True)
   summary.update(readout=name,primary=name==('R2z' if has_z else 'R3'),downstream_TEST_read=False)
   _json(summary,path);summaries[name]=summary
  primary='R2z' if has_z else 'R3'
  _json(dict(panel='v3',stage=stage,arm=arm,condition=config['condition'],primary=primary,
   primary_task_ids=list(PRIMARY_TASK_IDS),SoM_selection_use=False,
   means={name:value['mean_normalized_improvement'] for name,value in summaries.items()},
   source_roles=['train','train_inner_validation'],downstream_TEST_read=False),output/'summary.json')
  success=True
 finally:
  owner.close(success)
 _json(dict(status='PREDICTIONS_COMPLETE',panel='v3',statistics_complete=True,
  seconds=time.monotonic()-started),complete)
 # The last real retrospective evaluation consumes its group's new summaries once.
 retrospective_plan=REPO.parent/'runs/model_v31_20261105/RETROSPECTIVE_PANEL_V3_20261113/plan.json'
 if retrospective_plan.is_file():
  import subprocess,sys
  attempt=subprocess.run([sys.executable,'-B',str(REPO/'tools/model_v3/v3_finish_reselection_20261113.py'),
   '--plan',str(retrospective_plan),'--evaluation-output',str(output)],
   cwd=REPO,capture_output=True,text=True)
  if attempt.returncode:
   with (retrospective_plan.parent/'aggregation_failures.jsonl').open('a') as stream:
    stream.write(json.dumps(dict(output=str(output),returncode=attempt.returncode,
     stdout=attempt.stdout,stderr=attempt.stderr,completed_panel_retained=True))+'\n')
 if stage in ('HEADS','POOLING'):
  from .v3_latent_evaluation import finish_heads_pooling_if_ready
  finish_heads_pooling_if_ready(output)
 print(json.dumps(dict(status='PREDICTIONS_COMPLETE',panel='v3',output=str(output),
  primary_task_count=7,SoM_selection_use=False)),flush=True)
