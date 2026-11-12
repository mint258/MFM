"""Prepare only the prescribed pure-S M4 cells after actual C3 view selection."""
import argparse,copy,json,os,socket,subprocess,sys
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
sys.path.insert(0,str(R/'tools/model_v3'))
from v3_prepare_m4_lr_20261113 import LR,read,selected,write,run_ref
from v3_prepare_m4_batch_20261113 import fresh_control_output
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--views',type=Path,default=R/'results/model_v3_c3_views.json')
 parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args()
 if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':
  raise ValueError('Use the existing development node')
 os.chdir(R)
 c1=read(R/'results/model_v3_c1_final.json');t1=read(R/'results/model_v3_t1.json')
 if c1['decision']['selected']!='C1-0' or t1['provisional_latent']!='none' or len(t1['rows'])!=10:
  raise ValueError('Bind the actual completed C1 and original-architecture result')
 views=selected(args.views,'views',{'two','three'})
 c3=read(C/'C3_VIEWS_20261113/plan.json')
 baseline=(copy.deepcopy(c3['reused_three_S']) if views=='three' else
  run_ref(next(row for row in c3['runs'] if row['arm']=='two' and row['condition']=='S'),'C3'))
 baseline.setdefault('new_samples',0)
 output=fresh_control_output(args.output);model_output=B/output.name
 templates={row['name']:row for row in read(R/'configs/model_v3/followon_templates.json')['trials']}
 native=subprocess.check_output(['/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin/git',
  '-c','core.filemode=false','rev-parse','HEAD'],text=True).strip()
 rows=[];panels={}
 for lr in LR:
  candidate='lr'+str(lr)
  if lr==.0003:
   panels[candidate]={'S':baseline['panel']};continue
  name='M4_S_lr'+str(lr)+'_B32_seed0'
  cfg=copy.deepcopy(templates[name]['configuration'])
  cfg.update(output=str(model_output/name),distance_bias='C1-0',views=views,
   latent='none',latent_spec=None,condition='S',stage='M4_LR',arm=candidate,
   microbatch_size=32,code_tag='model-v3:'+native)
  cfg.pop('resume',None)
  cp=output/(name+'.json');write(cp,cfg)
  ep=output/(name+'_dev.json')
  ev=dict(checkpoint=str(Path(cfg['output'])/'samples_6000000.pt'),
   output=str(Path(cfg['output'])/'dev_eval_v2'),panel='v2',
   cache_root=str(B/'LATENT_V3_20261111/readout_cache'))
  write(ep,ev);panels[candidate]={'S':ev['output']+'/R3_summary.json'}
  rows.append(dict(stage='M4_LR',arm=candidate,condition='S',mode='native_selected',
   configuration=str(cp),output=cfg['output'],evaluation_configuration=str(ep),
   evaluation_output=ev['output'],taskbook_stage=6,status='PREPARED_NOT_SUBMITTED',
   scientific_samples=6000000,effective_batch_size=32,microbatch_size=32,seed=0))
 plan=dict(status='M4_S_LOOKAHEAD_CONFIGURATIONS_PREPARED_NOT_SUBMITTED',runs=rows,
  selected_C1='C1-0',selected_latent='none',selected_views=views,selected_head=None,selected_pooling=None,
  head_and_pooling_scientifically_active=False,baseline_S=baseline,panels=panels,
  scientific_grid=dict(learning_rates=list(LR),conditions=['S'],batch_size=32,
   samples=6000000,seed=0,schedule='cosine',clip=1.0),
  selection_sources=dict(C1=str(R/'results/model_v3_c1_final.json'),latent=str(R/'results/model_v3_t1.json'),
   views=str(args.views)),planned_model_output=str(model_output),
  output_registration_and_actual_node_admission_required=True,gpu_jobs_submitted=False,
  model_and_recipe_frozen=False,full_S_P_selection_performed=False,
  next='Submit only these four original S cells when admitted;later full LR matrix links the same actual job handles.')
 write(output/'plan.json',plan)
 print(json.dumps(dict(status=plan['status'],new_S_configurations=len(rows),reused_S_cells=1,
  selected_views=views,head_selected=False,pooling_selected=False,gpu_jobs_submitted=False)))
if __name__=='__main__':main()
