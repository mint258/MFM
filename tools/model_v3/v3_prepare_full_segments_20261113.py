"""Prepare actual M4-confirmed full-D6 S/P segments without resetting the64M clock."""
import argparse,copy,json,os,socket,subprocess,sys
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
ENDPOINTS=(1000000,2000000,4000000,8000000,16000000,32000000,64000000)
def read(path):return json.loads(Path(path).read_text())
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def closed_evaluation(output):
 root=Path(output)
 marker=read(root/'producer_complete.json')
 if (marker.get('status')!='PREDICTIONS_COMPLETE'
     or marker.get('statistics_complete') is not True or marker.get('panel')!='v3'):
  raise ValueError('Require the original completed v2 evaluation')
 return str(root/'R3_summary.json')
def prepare_row(config,output,condition,endpoint):
 name=condition+'_until_'+str(endpoint)
 model_output=B/output.name/name
 config['output']=str(model_output)
 cp=output/(name+'.json');write(cp,config)
 ep=output/(name+'_dev.json')
 ev=dict(checkpoint=str(model_output/('samples_'+str(endpoint)+'.pt')),
  output=str(model_output/'dev_eval_v3'),panel='v3',evaluation_scope='forward',
  cache_root=str(B/'LATENT_V3_20261111/readout_cache'))
 write(ep,ev)
 return dict(stage='FULL_TRAIN',arm=condition,condition=condition,mode='selected',
  configuration=str(cp),output=str(model_output),evaluation_configuration=str(ep),
  evaluation_output=ev['output'],taskbook_stage=6,status='PREPARED_NOT_SUBMITTED',
  schedule_budget=64000000,run_until_samples=endpoint,seed=0,
  expected_molecules=1194551,effective_batch_size=config['batch_size'],
  microbatch_size=config['microbatch_size'])
def fresh(path):
 sys.path.insert(0,str(R/'tools/model_v3'))
 from v3_prepare_m4_batch_20261113 import fresh_control_output
 return fresh_control_output(path)
def first(args):
 source=read(args.sdp_configuration)
 summary=read(Path(source['output'])/'summary.json')
 panel=closed_evaluation(args.sdp_evaluation)
 if (source.get('stage')!='M4_SDP' or source.get('condition')!='SDP' or source.get('samples')!=6000000
     or source.get('expected_molecules')!=240000 or source.get('latent')!='none'
     or summary.get('status')!='TRAINING_COMPLETE_DEV_EVALUATION_PENDING'
     or summary.get('samples')!=6000000):
  raise ValueError('Require the actual completed prescribed6M SDP recipe confirmation')
 # Common recipe comes from SDP confirmation; S/P thresholds come from their own trials.
 sys.path.insert(0,str(R/'tools/model_v3'))
 from v3_prepare_condition_clip_20261113 import condition_clip,recipe_from_configuration
 recipe=recipe_from_configuration(source)
 evidence_paths={'S':args.s_clip_evidence,'P':args.p_clip_evidence}
 condition_clips={condition:condition_clip(read(path),condition,recipe)
  for condition,path in evidence_paths.items()}
 output=fresh(args.output)
 native=subprocess.check_output(['/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin/git',
  '-c','core.filemode=false','rev-parse','HEAD'],text=True).strip()
 rows=[];curves={condition:{} for condition in ('S','P')};planned_points={}
 for condition in ('S','P'):
  cfg=copy.deepcopy(source)
  cfg.pop('resume',None)
  cfg.update(condition=condition,clip=condition_clips[condition],samples=64000000,run_until_samples=1000000,
   expected_molecules=1194551,subset_path=None,stage='FULL_TRAIN',arm=condition,
   candidate='M4_full_'+condition+'_seed0',seed=0,code_tag='model-v3:'+native,
   microbatch_size=min(32,cfg['batch_size']))
  row=prepare_row(cfg,output,condition,1000000)
  rows.append(row);planned_points[condition]={'1000000':row['evaluation_output']+'/R3_summary.json'}
 manifest=dict(kind='convergence',group='Full D6 S P B star',curves=curves,
  schedule_budget=64000000,expected_molecules=1194551)
 write(output/'curve_manifest.json',manifest)
 plan=dict(status='FULL_D6_FIRST_SEGMENT_CONFIGURATIONS_PREPARED_NOT_SUBMITTED',
  runs=rows,expected_molecules=1194551,subset_path=None,schedule_budget=64000000,
  endpoints=list(ENDPOINTS),initial_endpoint=1000000,
  recipe_source_configuration=str(args.sdp_configuration),recipe_source_summary=str(Path(source['output'])/'summary.json'),
  recipe_source_panel=panel,clip_source_policy='per_condition_and_trial',condition_clips=condition_clips,
  condition_clip_evidence={key:str(value) for key,value in evidence_paths.items()},curve_manifest=str(output/'curve_manifest.json'),
  planned_curve_points=planned_points,only_completed_readouts_enter_actual_curve=True,
  initial_optimizer='fresh_seed0_random_initialization',model_and_recipe_frozen=False,B_star=None,
  output_registration_and_actual_node_admission_required=True,gpu_jobs_submitted=False,
  estimated_full_GPU_hours=380,report_above_GPU_hours=570,ask_above_GPU_hours=1140,
  native_S_proxy_not_substituted_for_full_MFM4_population=True,
  next='Only after the actual endpoint evaluation and registered plateau decision,prepare the next sequential segment.')
 write(output/'plan.json',plan)
 print(json.dumps(dict(status=plan['status'],new_training_configurations=2,
  expected_molecules=1194551,schedule_budget=64000000,endpoint=1000000,gpu_jobs_submitted=False)))
def next_segment(args):
 previous=read(args.previous_configuration)
 summary=read(Path(previous['output'])/'summary.json')
 decision=read(args.budget_decision)
 condition=previous['condition'];endpoint=summary['samples']
 if (condition not in ('S','P') or previous.get('samples')!=64000000
     or previous.get('expected_molecules')!=1194551 or previous.get('subset_path') is not None
     or previous.get('stage')!='FULL_TRAIN' or endpoint not in ENDPOINTS):
  raise ValueError('Require the actual full D6 condition and registered endpoint')
 panel=closed_evaluation(args.previous_evaluation)
 manifest=read(decision['input_manifest'])
 if (manifest.get('kind')!='convergence'
     or manifest['curves'][condition].get(str(endpoint))!=panel
     or decision.get('schedule_budget')!=64000000):
  raise ValueError('Bind this actual endpoint panel to the registered full-curve decision')
 observed=decision['conditions'][condition]
 if observed['status']=='OBSERVED_PLATEAU':
  print(json.dumps(dict(status='OBSERVED_PLATEAU_NO_NEXT_SEGMENT',condition=condition,
   budget=observed['budget'],shared_B_star=decision.get('B_star'))));return
 if observed['status']=='CEILING_REACHED_WITHOUT_OBSERVED_PLATEAU':
  print(json.dumps(dict(status='CEILING_WITHOUT_PLATEAU_NO_NEXT_SEGMENT',condition=condition,
   B_star=None,ceiling_is_not_plateau=True)));return
 if (observed['status']!='MORE_CHECKPOINTS_REQUIRED' or observed.get('tested_limit')!=endpoint
     or endpoint==64000000 or endpoint!=previous['run_until_samples']
     or summary['status']!='SEGMENT_COMPLETE_DEV_EVALUATION_PENDING'):
  raise ValueError('Require the actual newest closed sequential endpoint and its plateau decision')
 checkpoint=Path(previous['output'])/('samples_'+str(endpoint)+'.pt')
 if not checkpoint.is_file():raise ValueError('Preserve and use the original complete endpoint checkpoint')
 next_endpoint=ENDPOINTS[ENDPOINTS.index(endpoint)+1]
 output=fresh(args.output)
 # Exactly the existing trainer resume contract: no changes to scientific fields/code tag/candidate.
 cfg=copy.deepcopy(previous)
 cfg.update(resume=str(checkpoint),run_until_samples=next_endpoint)
 row=prepare_row(cfg,output,condition,next_endpoint)
 plan=dict(status='FULL_D6_NEXT_SEGMENT_CONFIGURATION_PREPARED_NOT_SUBMITTED',runs=[row],
  condition=condition,previous_configuration=str(args.previous_configuration),previous_panel=panel,
  previous_endpoint=endpoint,run_until_samples=next_endpoint,schedule_budget=64000000,
  next_planned_curve_point={condition:{str(next_endpoint):row['evaluation_output']+'/R3_summary.json'}},
  expected_molecules=1194551,budget_decision=str(args.budget_decision),
  resume_checkpoint=str(checkpoint),restore=['model','AdamW','sampling_RNG','CPU_RNG','CUDA_RNG',
   'sample_clock','optimizer_update_clock','TRAIN_preclip_history','elapsed_seconds'],
  preserved_scientific_configuration=True,warmup_restarted=False,model_and_recipe_frozen=False,
  output_registration_and_actual_node_admission_required=True,gpu_jobs_submitted=False)
 write(output/'plan.json',plan)
 print(json.dumps(dict(status=plan['status'],condition=condition,previous_endpoint=endpoint,
  next_endpoint=next_endpoint,schedule_budget=64000000,gpu_jobs_submitted=False)))
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('command',choices=['first','next'])
 parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--sdp-configuration',type=Path)
 parser.add_argument('--sdp-evaluation',type=Path)
 parser.add_argument('--s-clip-evidence',type=Path)
 parser.add_argument('--p-clip-evidence',type=Path)
 parser.add_argument('--previous-configuration',type=Path)
 parser.add_argument('--previous-evaluation',type=Path)
 parser.add_argument('--budget-decision',type=Path)
 args=parser.parse_args()
 if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':
  raise ValueError('Use the existing development node')
 os.chdir(R)
 if args.command=='first':
  if any(value is None for value in (args.sdp_configuration,args.sdp_evaluation,args.s_clip_evidence,args.p_clip_evidence)):
   parser.error('first requires actual SDP configuration/evaluation and separate S/P TRAIN clip evidence')
  first(args)
 else:
  if args.previous_configuration is None or args.previous_evaluation is None or args.budget_decision is None:
   parser.error('next requires actual previous configuration/evaluation and budget decision')
  next_segment(args)
if __name__=='__main__':main()
