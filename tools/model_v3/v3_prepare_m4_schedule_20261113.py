"""Prepare only prescribed WSD S/P trials; reuse the measured selected cosine cells."""
import argparse,copy,json,os,socket,sys
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
def read(path):return json.loads(Path(path).read_text())
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--joint-selection',type=Path,required=True)
 parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args()
 if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':
  raise ValueError('Use the existing development node')
 os.chdir(R)
 joint=read(args.joint_selection)
 if (joint.get('status')!='M4_LR_BATCH_SELECTED' or joint.get('learning_rate') not in (.0001,.0003,.0006,.001,.002)
     or joint.get('batch_size') not in (32,64) or joint.get('selected_latent')!='none'):
  raise ValueError('Require the actual complete measured LR/batch choice')
 initial=read(joint['initial_plan']);doubled=read(joint['batch_plan'])
 candidate=joint['selected_candidate'];batch=joint['batch_size']
 # Registry/heads/pooling were chosen before M4; no new model default is assigned.
 bases={condition:read(next(row for row in initial['runs'] if row['condition']==condition)['configuration'])
        for condition in ('S','P')}
 cosine={}
 for condition in ('S','P'):
  if batch==64:
   row=next(row for row in doubled['runs'] if row['arm']==candidate and row['condition']==condition)
   cosine[condition]=dict(run_id=str(row.get('job',Path(row['output']).name)),original_stage='M4_BATCH',
    checkpoint=str(Path(row['output'])/'samples_6000000.pt'),
    panel=row['evaluation_output']+'/R3_summary.json',new_training_samples=0)
  else:
   prior=next((row for row in initial['reused_cells'] if row['candidate']==candidate and row['condition']==condition),None)
   if prior is not None:
    cosine[condition]=copy.deepcopy(prior['source'])
    cosine[condition]['new_training_samples']=0
   else:
    row=next(row for row in initial['runs'] if row['arm']==candidate and row['condition']==condition)
    cosine[condition]=dict(run_id=str(row.get('job',Path(row['output']).name)),original_stage='M4_LR',
     checkpoint=str(Path(row['output'])/'samples_6000000.pt'),
     panel=row['evaluation_output']+'/R3_summary.json',new_training_samples=0)
 sys.path.insert(0,str(R/'tools/model_v3'))
 from v3_prepare_m4_batch_20261113 import fresh_control_output
 output=fresh_control_output(args.output)
 model_output=B/output.name;rows=[]
 panels=dict(cosine={condition:source['panel'] for condition,source in cosine.items()},wsd={})
 for condition in ('S','P'):
  name='M4_'+condition+'_wsd_seed0'
  cfg=copy.deepcopy(bases[condition])
  cfg.update(output=str(model_output/name),lr=joint['learning_rate'],batch_size=batch,microbatch_size=32,
   schedule='wsd',stage='M4_SCHEDULE',arm='wsd',candidate=name)
  cfg.pop('resume',None)
  cp=output/(name+'.json');write(cp,cfg)
  ep=output/(name+'_dev.json')
  ev=dict(checkpoint=str(Path(cfg['output'])/'samples_6000000.pt'),
   output=str(Path(cfg['output'])/'dev_eval_v2'),panel='v2',
   cache_root=str(B/'LATENT_V3_20261111/readout_cache'))
  write(ep,ev);panels['wsd'][condition]=ev['output']+'/R3_summary.json'
  rows.append(dict(stage='M4_SCHEDULE',arm='wsd',condition=condition,
   mode='native_selected' if condition=='S' else 'selected',configuration=str(cp),output=cfg['output'],
   evaluation_configuration=str(ep),evaluation_output=ev['output'],taskbook_stage=6,
   status='PREPARED_NOT_SUBMITTED',scientific_samples=6000000,effective_batch_size=batch,
   microbatch_size=32,seed=0))
 manifest=dict(kind='candidate_set',group='M4 cosine WSD schedules',comparison='schedule',
  simplicity_order=['cosine','wsd'],panels=panels,selection_source=str(args.joint_selection))
 write(output/'decision_manifest.json',manifest)
 plan=dict(status='M4_WSD_CONFIGURATIONS_PREPARED_NOT_SUBMITTED',runs=rows,reused_cosine_cells=cosine,
  selected_C1=joint['selected_C1'],selected_latent=joint['selected_latent'],selected_views=joint['selected_views'],
  selected_head=joint['selected_head'],selected_pooling=joint['selected_pooling'],
  learning_rate=joint['learning_rate'],batch_size=batch,clip_during_schedule_scan=1.0,
  warmup_fraction=.02,wsd_final_linear_decay_fraction=.20,scientific_sample_budget=6000000,
  joint_selection=str(args.joint_selection),decision_manifest=str(output/'decision_manifest.json'),
  planned_model_output=str(model_output),output_registration_and_actual_node_admission_required=True,
  gpu_jobs_submitted=False,new_probe_scores_computed=False,model_and_recipe_frozen=False,
  next='Use the original schedule decision,then registered TRAIN preclip p99 and one SDP confirmation before full S/P.')
 write(output/'plan.json',plan)
 print(json.dumps(dict(status=plan['status'],new_training_configurations=2,reused_cosine_cells=2,
  gpu_jobs_submitted=False,model_and_recipe_frozen=False)))
if __name__=='__main__':main()
