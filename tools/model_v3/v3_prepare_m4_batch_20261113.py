"""Prepare top-two B64 cells and select the measured M4 LR/batch combination."""
import argparse,copy,json,os,socket,sys
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
sys.path.insert(0,str(R/'current'))
ORDER=['lr0.0001','lr0.0003','lr0.0006','lr0.001','lr0.002']
def read(path):return json.loads(Path(path).read_text())
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def closed_initial(plan_path,selection_path):
 plan=read(plan_path);decision=read(selection_path)
 if (decision.get('status')!='CANDIDATE_GROUP_SELECTED' or decision.get('comparison')!='learning_rate'
     or set(decision.get('ranked',[]))!=set(ORDER) or len(decision['ranked'])!=5):
  raise ValueError('Require the actual complete five-rate S/P selection')
 if (plan['scientific_grid']['learning_rates']!=[.0001,.0003,.0006,.001,.002]
     or plan['scientific_grid']['conditions']!=['S','P'] or plan['scientific_grid']['batch_size']!=32
     or plan['selected_latent']!='none'):
  raise ValueError('Retain the actual original B32 grid and selected model')
 return plan,decision
def fresh_control_output(path):
 import importlib.util
 spec=importlib.util.spec_from_file_location('actual_model_metadata_guard',R/'tools/model_v3/v2_diagnosis_disk.py')
 guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
 guard.m.require_capacity(guard.m.filesystem_status('/'),0,0)
 guard.m.require_capacity(guard.m.filesystem_status(C),4*1024**2,1000)
 guard.m.quota_headroom(C/'share_quota_available_v3.json','/share',4*1024**2,guard.remaining_nfs_other())
 output=path.resolve()
 if output.exists() or not output.is_relative_to(C.resolve()):
  raise ValueError('Use fresh actual control-directory output; retain existing products')
 output.mkdir();return output
def prepare(args,initial,selection):
 top=selection['ranked'][:2]
 output=fresh_control_output(args.output)
 model_output=B/output.name
 rows=[];panels={}
 # Copy an actual generated config for each condition; reused3e-4 needs no duplicate B32 config.
 physical_initial=initial['runs']+initial.get('existing_S_cells',[])
 bases={condition:read(next(row for row in physical_initial if row['condition']==condition)['configuration'])
        for condition in ('S','P')}
 for candidate in top:
  panels[candidate]={}
  for condition in ('S','P'):
   name='M4_'+condition+'_'+candidate+'_B64_seed0'
   cfg=copy.deepcopy(bases[condition])
   cfg.update(output=str(model_output/name),lr=float(candidate[2:]),batch_size=64,
    microbatch_size=32,stage='M4_BATCH',arm=candidate,candidate=name)
   cfg.pop('resume',None)
   cp=output/(name+'.json');write(cp,cfg)
   ep=output/(name+'_dev.json')
   ev=dict(checkpoint=str(Path(cfg['output'])/'samples_6000000.pt'),
    output=str(Path(cfg['output'])/'dev_eval_v3'),panel='v3',evaluation_scope='forward',
    cache_root=str(B/'LATENT_V3_20261111/readout_cache'))
   write(ep,ev)
   panels[candidate][condition]=ev['output']+'/R3_summary.json'
   rows.append(dict(stage='M4_BATCH',arm=candidate,condition=condition,
    mode='native_selected' if condition=='S' else 'selected',
    configuration=str(cp),output=cfg['output'],evaluation_configuration=str(ep),
    evaluation_output=ev['output'],taskbook_stage=6,status='PREPARED_NOT_SUBMITTED',
    scientific_samples=6000000,effective_batch_size=64,microbatch_size=32,seed=0))
 plan=dict(status='M4_TOP_TWO_B64_CONFIGURATIONS_PREPARED_NOT_SUBMITTED',
  initial_plan=str(args.initial_plan),initial_selection=str(args.initial_selection),
  initial_top_two=top,initial_panels=read(initial['decision_manifest'])['panels'],
  B64_panels=panels,runs=rows,selected_C1=initial['selected_C1'],
  selected_latent=initial['selected_latent'],selected_views=initial['selected_views'],
  selected_head=initial['selected_head'],selected_pooling=initial['selected_pooling'],
  planned_model_output=str(model_output),output_registration_and_actual_node_admission_required=True,
  gpu_jobs_submitted=False,new_probe_scores_computed=False,model_and_recipe_frozen=False)
 write(output/'plan.json',plan)
 print(json.dumps(dict(status=plan['status'],new_training_configurations=len(rows),top_two=top,gpu_jobs_submitted=False)))
def select_batch(args,initial,selection):
 from phychem_mfm.phase1.v3_followon_decisions import candidate_set
 from phychem_mfm.phase1.v3_dev_evaluation_v2 import _json
 batches=read(args.batch_plan)
 if batches['initial_top_two']!=selection['ranked'][:2]:
  raise ValueError('B64 results must be exactly the original ranked top two')
 source=read(initial['decision_manifest'])['panels']
 if batches['initial_panels']!=source:
  raise ValueError('Retain the original B32 panel paths')
 cache={}
 def load_panel(path):
  if path not in cache:cache[path]=read(path)
  return cache[path]
 retained={candidate:{condition:load_panel(path) for condition,path in values.items()}
           for candidate,values in source.items()}
 decisions={};batch_by_rate={candidate:32 for candidate in ORDER}
 for candidate in batches['initial_top_two']:
  full64={condition:load_panel(path) for condition,path in batches['B64_panels'][candidate].items()}
  decisions[candidate]=candidate_set({'B32':retained[candidate],'B64':full64},
   ['B32','B64'],comparison='batch')
  if decisions[candidate]['selected']=='B64':
   retained[candidate]=full64;batch_by_rate[candidate]=64
 final=candidate_set(retained,ORDER,comparison='learning_rate')
 rate=final['selected']
 result=dict(status='M4_LR_BATCH_SELECTED',learning_rate=float(rate[2:]),batch_size=batch_by_rate[rate],
  selected_candidate=rate,batch_decisions=decisions,retained_batches=batch_by_rate,
  learning_rate_decision=final,initial_plan=str(args.initial_plan),
  initial_selection=str(args.initial_selection),batch_plan=str(args.batch_plan),
  selected_C1=initial['selected_C1'],selected_latent=initial['selected_latent'],
  selected_views=initial['selected_views'],selected_head=initial['selected_head'],
  selected_pooling=initial['selected_pooling'],panel='v3',evaluation_scope='forward',primary='R3',
  source_roles=['train','train_inner_validation'],downstream_TEST_read=False,
  model_and_recipe_frozen=False)
 _json(result,args.results)
 print(json.dumps(dict(status=result['status'],learning_rate=result['learning_rate'],
  batch_size=result['batch_size'],results=str(args.results))))
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('command',choices=['prepare','select'])
 parser.add_argument('--initial-plan',type=Path,required=True)
 parser.add_argument('--initial-selection',type=Path,required=True)
 parser.add_argument('--output',type=Path)
 parser.add_argument('--batch-plan',type=Path)
 parser.add_argument('--results',type=Path)
 args=parser.parse_args()
 if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':
  raise ValueError('Use the existing development node')
 os.chdir(R)
 initial,selection=closed_initial(args.initial_plan,args.initial_selection)
 if args.command=='prepare':
  if args.output is None:parser.error('prepare requires --output')
  prepare(args,initial,selection)
 else:
  if args.batch_plan is None or args.results is None:parser.error('select requires --batch-plan and --results')
  if args.results.exists():raise FileExistsError('Retain the original actual joint decision')
  select_batch(args,initial,selection)
if __name__=='__main__':main()
