"""Prepare the one prescribed M4 SDP confirmation from actual recipe and TRAIN p99."""
import argparse,copy,json,math,os,socket,subprocess,sys
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
def read(path):return json.loads(Path(path).read_text())
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--joint-selection',type=Path,required=True)
 parser.add_argument('--schedule-selection',type=Path,required=True)
 parser.add_argument('--clip-evidence',type=Path,required=True)
 parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args()
 if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':
  raise ValueError('Use the existing development node')
 os.chdir(R)
 joint=read(args.joint_selection);schedule=read(args.schedule_selection);clip=read(args.clip_evidence)
 if joint.get('status')!='M4_LR_BATCH_SELECTED' or joint.get('selected_latent')!='none':
  raise ValueError('Require the actual measured LR/batch choice and completed latent=none result')
 if (schedule.get('status')!='CANDIDATE_GROUP_SELECTED' or schedule.get('comparison')!='schedule'
     or schedule.get('selected') not in ('cosine','wsd')):
  raise ValueError('Require the actual completed schedule choice')
 recipe={key:joint[key] for key in ('selected_C1','selected_latent','selected_views',
  'selected_head','selected_pooling','learning_rate','batch_size')}
 recipe.update(schedule=schedule['selected'],samples=6000000,seed=0)
 # The producer's original statistic is consumed,not independently recomputed.
 if (clip.get('schema')!='MODEL_V3_TRAIN_PRECLIP_P99_V1'
     or clip.get('quantile')!=.99 or clip.get('method')!='linear'
     or clip.get('population')!='all_effective_TRAIN_updates' or clip.get('recipe')!=recipe):
  raise ValueError('Require actual selected-recipe TRAIN p99 evidence and an explicit population')
 conditions=clip.get('source_conditions',[]);sources=clip.get('source_runs',[])
 if (not conditions or len(conditions)!=len(set(conditions)) or not set(conditions)<={'S','P'}
     or len(sources)!=len(conditions) or {row['condition'] for row in sources}!=set(conditions)
     or any(row['scientific_samples']!=6000000 for row in sources)):
  raise ValueError('Use the explicitly defined complete logical S/P TRAIN sources; no implicit mixture')
 value=float(clip['p99'])
 if not math.isfinite(value) or value<=0:raise ValueError('Use the actual finite positive TRAIN p99')
 # No source condition or pooled statistic is chosen by this configurator.
 sys.path.insert(0,str(R/'tools/model_v3'))
 from v3_prepare_m4_batch_20261113 import fresh_control_output
 output=fresh_control_output(args.output)
 template=next(row for row in read(R/'configs/model_v3/followon_templates.json')['trials']
  if row['name']=='M4_SDP_confirmation_seed0')
 cfg=copy.deepcopy(template['configuration']);model_output=B/output.name/'SDP_confirmation_seed0'
 native=subprocess.check_output(['/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin/git',
  '-c','core.filemode=false','rev-parse','HEAD'],text=True).strip()
 cfg.update(output=str(model_output),condition='SDP',distance_bias=joint['selected_C1'],
  latent='none',latent_spec=None,views=joint['selected_views'],head_form=joint['selected_head'],
  pooling=joint['selected_pooling'],lr=joint['learning_rate'],batch_size=joint['batch_size'],
  microbatch_size=min(32,joint['batch_size']),schedule=schedule['selected'],clip=value,
  stage='M4_SDP',arm='confirmation',code_tag='model-v3:'+native)
 cfg.pop('resume',None)
 cp=output/'SDP_confirmation_seed0.json';write(cp,cfg)
 ep=output/'SDP_confirmation_seed0_dev.json'
 ev=dict(checkpoint=str(model_output/'samples_6000000.pt'),output=str(model_output/'dev_eval_v2'),
  panel='v2',cache_root=str(B/'LATENT_V3_20261111/readout_cache'))
 write(ep,ev)
 row=dict(stage='M4_SDP',arm='confirmation',condition='SDP',mode='selected',
  configuration=str(cp),output=str(model_output),evaluation_configuration=str(ep),evaluation_output=ev['output'],
  taskbook_stage=6,status='PREPARED_NOT_SUBMITTED',scientific_samples=6000000,seed=0,
  effective_batch_size=cfg['batch_size'],microbatch_size=cfg['microbatch_size'])
 plan=dict(status='M4_SDP_CONFIGURATION_PREPARED_NOT_SUBMITTED',runs=[row],
  selected_recipe=recipe,clip=value,clip_evidence=str(args.clip_evidence),
  explicit_clip_source_conditions=conditions,joint_selection=str(args.joint_selection),
  schedule_selection=str(args.schedule_selection),source_roles=['train','train_inner_validation'],
  downstream_TEST_read=False,output_registration_and_actual_node_admission_required=True,
  gpu_jobs_submitted=False,new_probe_scores_computed=False,model_and_recipe_frozen=False,
  next='Actual SDP6M training and v2 evaluation precede full-D6 first segments.')
 write(output/'plan.json',plan)
 print(json.dumps(dict(status=plan['status'],new_training_configurations=1,
  clip=value,source_conditions=conditions,gpu_jobs_submitted=False,model_and_recipe_frozen=False)))
if __name__=='__main__':main()
