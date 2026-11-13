"""Prepare the prescribed M4 five-LR S/P grid from actual closed model decisions."""
import argparse,copy,json,os,socket,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
LR=(.0001,.0003,.0006,.001,.002)
def read(path):
 return json.loads(Path(path).read_text())
def selected(path,comparison,allowed):
 result=read(path)
 if (result.get('status')!='CANDIDATE_GROUP_SELECTED' or result.get('panel')!='v3' or result.get('comparison')!=comparison
     or result.get('selected') not in allowed):
  raise ValueError('Require the actual closed '+comparison+' selection: '+str(path))
 return result['selected']
def write(path,value):
 path.write_text(json.dumps(value,indent=2)+'\n')
def run_ref(row,stage):
 return dict(run_id=str(row.get('job',Path(row['output']).name)),original_stage=stage,
  output=row['output'],checkpoint=str(Path(row['output'])/'samples_6000000.pt'),
  panel=row['evaluation_output']+'/R3_summary.json',scientific_samples=6000000,new_samples=0)
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--views',type=Path,default=R/'results/model_v3_c3_views.json')
 parser.add_argument('--heads',type=Path,default=R/'results/model_v3_heads.json')
 parser.add_argument('--pooling',type=Path,default=R/'results/model_v3_pooling.json')
 parser.add_argument('--s-lookahead-plan',type=Path)
 parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args()
 if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':
  raise ValueError('Configuration preparation belongs on the existing development node')
 os.chdir(R)
 c1=read(R/'results/model_v3_c1_panel_v3.json')
 t1=read(R/'results/model_v3_t1_panel_v3.json')
 if c1['status']!='C1_SELECTED_PANEL_V3_SEED0' or c1['decision']['selected']!='C1-0':
  raise ValueError('Bind the actual completed C1 choice')
 if t1['provisional_latent']!='none' or len(t1['rows'])!=10:
  raise ValueError('This continuation binds the actual completed latent=none result')
 views=selected(args.views,'views',{'two','three'})
 head=selected(args.heads,'heads',{'H1','H2','H3'})
 pooling=selected(args.pooling,'pooling',{'registry','learned'})
 c3=read(C/'C3_VIEWS_20261113/plan.json')
 heads=read(C/'HEADS_V3_20261113/plan.json')
 pool=read(C/'HEADS_V3_20261113/pooling_plan.json')
 if c3['selected_C1']!='C1-0' or heads.get('selected_views')!=views:
  raise ValueError('Use the actual chosen C3 view and complete head-stage metadata')
 existing_s=[]
 lookahead_path=args.s_lookahead_plan or C/'M4_V3_S_LOOKAHEAD_20261113/plan.json'
 if args.s_lookahead_plan is not None and not lookahead_path.is_file():
  raise ValueError('Require the actual S lookahead plan supplied by the coordinator')
 if lookahead_path.is_file():
  lookahead=read(lookahead_path)
  if (lookahead['selected_C1']!='C1-0' or lookahead['selected_latent']!='none'
      or lookahead['selected_views']!=views or len(lookahead['runs'])!=4
      or lookahead['scientific_grid']!=dict(learning_rates=list(LR),conditions=['S'],batch_size=32,
       samples=6000000,seed=0,schedule='cosine',clip=1.0)
      or any(r['condition']!='S' or r['mode']!='native_selected' for r in lookahead['runs'])
      or {r['arm'] for r in lookahead['runs']}!={'lr0.0001','lr0.0006','lr0.001','lr0.002'}
      or any(type(r.get('job')) is not int or type(r.get('evaluation_job')) is not int
             or r['job']<=0 or r['evaluation_job']<=0
             for r in lookahead['runs'])):
   raise ValueError('Link the four actual submitted matching S cells;never duplicate unsubmitted lookahead')
  existing_s=copy.deepcopy(lookahead['runs'])
 # Reuse only logical cells whose effective scientific configuration is identical.
 # Pure S has no P/D heads; pure P never invokes structural views.
 baseline_s=(copy.deepcopy(c3['reused_three_S']) if views=='three' else
  run_ref(next(row for row in c3['runs'] if row['arm']=='two' and row['condition']=='S'),'C3'))
 baseline_s.setdefault('new_samples',0)
 baseline_p=None
 if pooling=='registry':
  baseline_p=(copy.deepcopy(heads['H1_P_reuse']) if head=='H1' else
   run_ref(next(row for row in heads['runs'] if row['arm']==head and row['condition']=='P'),'HEADS'))
 elif head=='H1':
  baseline_p=run_ref(next(row for row in pool['runs'] if row['arm']=='learned' and row['condition']=='P'),'POOLING')
 if baseline_p is not None:baseline_p.setdefault('new_samples',0)
 # Metadata/configuration output only; no training,probe fit or numerical readback.
 import importlib.util
 spec=importlib.util.spec_from_file_location('actual_model_metadata_guard',R/'tools/model_v3/v2_diagnosis_disk.py')
 guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
 guard.m.require_capacity(guard.m.filesystem_status('/'),0,0)
 guard.m.require_capacity(guard.m.filesystem_status(C),4*1024**2,1000)
 guard.m.quota_headroom(C/'share_quota_available_v3.json','/share',4*1024**2,guard.remaining_nfs_other())
 output=args.output.resolve()
 if output.exists() or not output.is_relative_to(C.resolve()):
  raise ValueError('Use a fresh owned control-directory output; preserve prior configurations')
 output.mkdir()
 templates={row['name']:row for row in read(R/'configs/model_v3/followon_templates.json')['trials']}
 native=subprocess.check_output(['/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin/git',
  '-c','core.filemode=false','rev-parse','HEAD'],text=True).strip()
 model_output=B/output.name
 rows=[];reused=[];panels={}
 for lr in LR:
  candidate='lr'+str(lr)
  panels[candidate]={}
  for condition in ('S','P'):
   if condition=='S' and lr!=.0003 and existing_s:
    linked=next(r for r in existing_s if r['arm']==candidate)
    panels[candidate][condition]=linked['evaluation_output']+'/R3_summary.json'
    continue
   baseline=baseline_s if condition=='S' else baseline_p
   if lr==.0003 and baseline is not None:
    # Upstream result use is the acceptance; no extra model/data audit is added.
    panels[candidate][condition]=baseline['panel']
    reused.append(dict(stage='M4_LR',candidate=candidate,condition=condition,
     reason='Identical effective6M seed0/B32/lr3e-4/cosine/clip1 configuration',
     source=baseline,new_training_samples=0))
    continue
   name='M4_'+condition+'_lr'+str(lr)+'_B32_seed0'
   cfg=copy.deepcopy(templates[name]['configuration'])
   cfg.update(output=str(model_output/name),distance_bias='C1-0',views=views,
    latent='none',latent_spec=None,condition=condition,stage='M4_LR',arm=candidate,
    microbatch_size=32,code_tag='model-v3:'+native)
   cfg.pop('resume',None)
   if condition=='P':cfg.update(head_form=head,pooling=pooling)
   configuration=output/(name+'.json');write(configuration,cfg)
   evaluation=output/(name+'_dev.json')
   ev=dict(checkpoint=str(Path(cfg['output'])/'samples_6000000.pt'),
    output=str(Path(cfg['output'])/'dev_eval_v3'),panel='v3',evaluation_scope='forward',
    cache_root=str(B/'LATENT_V3_20261111/readout_cache'))
   write(evaluation,ev)
   panels[candidate][condition]=ev['output']+'/R3_summary.json'
   rows.append(dict(stage='M4_LR',arm=candidate,condition=condition,
    mode='native_selected' if condition=='S' else 'selected',
    configuration=str(configuration),output=cfg['output'],
    evaluation_configuration=str(evaluation),evaluation_output=ev['output'],
    taskbook_stage=6,status='PREPARED_NOT_SUBMITTED',scientific_samples=6000000,
    effective_batch_size=32,microbatch_size=32,seed=0))
 manifest=dict(kind='candidate_set',group='M4 five learning rates B32',comparison='learning_rate',
  simplicity_order=['lr'+str(lr) for lr in LR],panels=panels,
  selected_C1='C1-0',selected_latent='none',selected_views=views,
  selected_head=head,selected_pooling=pooling)
 write(output/'decision_manifest.json',manifest)
 plan=dict(status='M4_LR_CONFIGURATIONS_PREPARED_NOT_SUBMITTED',runs=rows,reused_cells=reused,existing_S_cells=existing_s,
  S_lookahead_plan=str(lookahead_path) if existing_s else None,
  scientific_grid=dict(learning_rates=list(LR),conditions=['S','P'],batch_size=32,
   samples=6000000,seed=0,schedule='cosine',clip=1.0),
  selected_C1='C1-0',selected_latent='none',selected_views=views,selected_head=head,selected_pooling=pooling,
  selection_sources=dict(C1=str(R/'results/model_v3_c1_panel_v3.json'),latent=str(R/'results/model_v3_t1_panel_v3.json'),
   views=str(args.views),heads=str(args.heads),pooling=str(args.pooling)),
  decision_manifest=str(output/'decision_manifest.json'),planned_model_output=str(model_output),
  output_registration_and_actual_node_admission_required=True,gpu_jobs_submitted=False,
  new_probe_scores_computed=False,model_and_recipe_frozen=False,
  next='After all ten logical S/P cells complete,use original paired decision and ranked top2 for B64; no seed1.',
  estimated_M4_GPU_hours=280,report_above_GPU_hours=420,ask_above_GPU_hours=840)
 write(output/'plan.json',plan)
 print(json.dumps(dict(status=plan['status'],output=str(output),new_training_configurations=len(rows),
  reused_cells=len(reused),gpu_jobs_submitted=False,model_and_recipe_frozen=False)))
if __name__=='__main__':
 main()
