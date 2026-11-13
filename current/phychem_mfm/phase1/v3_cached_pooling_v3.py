"""T0-2 new target,seven-task report;reuse all unchanged four-statistics probes."""
import json,os,time
from pathlib import Path
import torch
from .v3_cached_pooling import four_statistics
from .v3_dev_membership import GroupedTrainingView
from .v3_dev_evaluation import TaskSpec,task_rows,ridge_probe,mlp_pooled_probe,compare_panel,error
from .v3_dev_evaluation_v2 import REPO,DATASETS,_cached_rows,_save_once,_pack,_unpack,_json,ProbeHistory
from .v3_downstream_targets import ATOMIZATION_TASK_ID,PRIMARY_TASK_IDS,atomization_rows,compare_report_only_panel
from .v3_latent_training import TrainingHistory
def read(path):return json.loads(Path(path).read_text())
def evaluate_cached_pooling_v3(c,*,store_factory):
 output=Path(c['output']);output.mkdir(parents=True,exist_ok=False)
 _json(c,output/'configuration.json')
 policy=read(REPO/'configs/dev_panel_v3.json')
 if policy['authority']['retrospective_scope']!='REEVALUATE_C1_T0_T1':
  raise ValueError('Actual retrospective scope required')
 store=store_factory(c['store'])
 views={d:GroupedTrainingView(store,d,'official' if d=='expansionrx' else '0',store.group_map) for d in DATASETS}
 tasks=[TaskSpec(**{key:t[key] for key in ('task_id','dataset_id','field','output_level','error_metric','pooling')})
  for t in policy['tasks']]
 torch.set_num_threads(max(1,min(16,int(os.environ.get('SLURM_CPUS_PER_TASK','8')))))
 owner=TrainingHistory(output,dict(c,selection_use=False))
 history=ProbeHistory(owner.stream,owner.run);started=time.monotonic();success=False
 packets={};files={}
 try:
  for label in ('reference','S','P'):
   packets[label]={'R1':{},'R2':{}};files[label]={}
   for task in (t for t in tasks if t.output_level=='graph'):
    for name in ('R1','R2'):
     path=Path(c['reuse_four_statistics_output'])/label/'probes'/(task.task_id.replace('.','_')+'__'+name+'.pt')
     if task.task_id==ATOMIZATION_TASK_ID:
      payload=torch.load(Path(c['cache_directories'][label])/'qm9.pt',map_location='cpu',weights_only=True)
      cached=_cached_rows(payload);view=views['qm9']
      train=four_statistics(atomization_rows(view,cached,task,role='train'),payload['n_ref'])
      held=four_statistics(atomization_rows(view,cached,task,role='train_inner_validation'),payload['n_ref'])
      history.cell=label+'/v3/'+task.task_id+'/'+name
      if name=='R1':prediction,detail=ridge_probe(train,held,task)
      else:prediction,detail=mlp_pooled_probe(train,held,task,n_ref=payload['n_ref'],
       seed=0,device='cpu',tracker=history)
      path=output/label/'probes'/(task.task_id.replace('.','_')+'__'+name+'.pt')
      _save_once(dict(prediction=_pack(prediction),detail=detail),path)
      history.log({'readout/native_error':error(prediction)},step=detail.get('updates',0),commit=True)
     else:
      if not path.is_file():raise ValueError('Original unchanged four-statistics probe missing;do not silently refit')
      prediction=_unpack(torch.load(path,map_location='cpu',weights_only=True)['prediction'])
     packets[label][name][task.task_id]=prediction
     files[label][task.task_id+'/'+name]=str(path)
   _json(dict(panel='v3',files=files[label],selection_use=False),output/label/'predictions.json')
  rows=[]
  for label in ('S','P'):
   x=read(c['existing_v2_predictions'][label]);random=read(c['existing_v2_predictions']['reference'])
   for task in (t for t in tasks if t.output_level=='atom'):
    key=task.task_id+'/R2'
    packets[label]['R2'][task.task_id]=_unpack(torch.load(x['files'][key],map_location='cpu',weights_only=True)['prediction'])
    packets['reference']['R2'][task.task_id]=_unpack(torch.load(random['files'][key],map_location='cpu',weights_only=True)['prediction'])
   scores={}
   for name in ('R1','R2'):
    kwargs=dict(architecture_sha256='C1-0:three:four_statistics',
     reference_architecture_sha256='C1-0:three:four_statistics',retain_paired_samples=True)
    if name=='R2':summary=compare_report_only_panel(packets[label][name],packets['reference'][name],**kwargs)
    else:
     summary=compare_panel(packets[label][name],packets['reference'][name],**kwargs)
     legacy=read(c['legacy_summaries'][label])
     som={key.rsplit('/',1)[0]:value for key,value in legacy['tasks'].items()
      if key.startswith('cyp.') and key.endswith('/ridge')}
     summary.update(panel='v3',primary_task_ids=list(PRIMARY_TASK_IDS),SoM_selection_use=False,
      report_only=dict(selection_use=False,tasks=som,source_summary=c['legacy_summaries'][label],
       note='Original per-task SoM ridge metrics/intervals retained;no new atom probe'))
    summary['selection_use']=False
    _json(summary,output/(label+'_'+name+'_summary.json'));scores[name]=summary['mean_normalized_improvement']
   rows.append(dict(condition=label,**scores))
  _json(dict(status='T0_2_FOUR_STATISTICS_COMPLETE_PANEL_V3',panel='v3',rows=rows,selection_use=False,
   source_roles=['train','train_inner_validation'],downstream_TEST_read=False,
   seconds=time.monotonic()-started),output/'summary.json')
  success=True
 finally:owner.close(success)

 # Cached reporting can be the last missing T0 result;consume it in this allocation.
 import subprocess,sys
 plan=REPO.parent/'runs/model_v31_20261105/RETROSPECTIVE_PANEL_V3_20261113/plan.json'
 if plan.is_file():
  result=subprocess.run([sys.executable,'-B',str(REPO/'tools/model_v3/v3_finish_reselection_20261113.py'),
   '--plan',str(plan),'--evaluation-output',str(output)],cwd=REPO,capture_output=True,text=True)
  if result.returncode:
   with (plan.parent/'aggregation_failures.jsonl').open('a') as stream:
    stream.write(json.dumps(dict(output=str(output),returncode=result.returncode,
     stdout=result.stdout,stderr=result.stderr,completed_cached_report_retained=True))+'\n')
