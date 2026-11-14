"""Write exactly one registered screening round; fit dependencies stay explicit."""
import argparse,json
from pathlib import Path
from phychem_mfm.phase1.p_recipe_data import read_json
from phychem_mfm.phase1.p_recipe_plan import ROUNDS,LABEL_COMPONENTS,configuration
R=Path('/share/home/zixiao/descriptor_analysis');REPO=Path(__file__).resolve().parents[2]
OUT=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113')


def prepare(round_number,previous=None,*,base_configuration=None,study_directory=None):
 base_path=Path(base_configuration) if base_configuration else REPO/'configs/p_recipe/base.json'
 if not base_path.is_absolute():base_path=REPO/base_path
 base=read_json(base_path);components=set(previous['merged_components']) if previous else set()
 if previous:
  if previous.get('selection_valid') is False:raise ValueError('The user invalidated this previous screening decision')
  if previous.get('study_revision','original_20261113')!=base.get('study_revision','original_20261113'):raise ValueError('Previous decision belongs to a different study revision')
 baseline=('B0','M1','M2')[round_number-1];arms=list(ROUNDS[round_number]);skipped={}
 if round_number==1:
  decision=R/'runs/p_recipe_20261113/D2_decision.json'
  if not read_json(decision).get('A5',False):
   arms.remove('A5');skipped['A5']='D2 did not trigger A5, including an explicitly recorded diagnostic timebox fallback'
 root=Path(study_directory) if study_directory else REPO/'configs/p_recipe'
 if not root.is_absolute():root=REPO/root
 configs=[];fits={};destination=root/('round'+str(round_number))
 if (destination/'plan.json').is_file() and read_json(destination/'plan.json').get('selection_valid') is False:raise ValueError('This archived plan is invalid; use the new study directory')
 destination.mkdir(parents=True,exist_ok=True)
 dispatch=[baseline]+arms
 if round_number==2:dispatch=['B1']+[arm for arm in dispatch if arm!='B1']
 for arm in dispatch:
  selected=components|({arm} if arm!=baseline else set());name=base.get('run_prefix','')+f'round{round_number}_{arm}'
  c=configuration(base,selected,run=name,round_number=round_number,arm=arm,samples=base.get('screening_samples',base.get('samples',1500000)))
  if arm=='B0' and base.get('reuse_baseline_configuration'):
   from reuse_baseline import baseline_configuration
   c=baseline_configuration(base)
  if 'B4' in selected:c['p_recipe']['gamma']=read_json(R/'runs/p_recipe_20261113/D4_gamma.json')['gamma']
  labels=sorted(selected&LABEL_COMPONENTS)
  if labels:
   target=OUT/'label_parameters'/('PM7_'+'_'.join(labels)+'.json');c['label_parameters']=str(target)
   if not target.is_file():fits[str(target)]=str(destination/(arm+'.json'))
  path=destination/(arm+'.json')
  if path.is_file():
   existing=read_json(path)
   c.update({key:existing[key] for key in ('handoff_request','handoff_ack') if key in existing})
   if existing.get('attempt',1)>1:
    c.update({key:existing[key] for key in ('run','output','attempt','batch_size','microbatch_size','resume','resume_samples','handoff_request','handoff_ack') if key in existing})
  path.write_text(json.dumps(c,indent=2)+'\n');configs.append(str(path))
 plan=dict(round=round_number,baseline=baseline,baseline_components=sorted(components),configurations=configs,skipped=skipped,label_parameters_to_fit=fits,batch_size=base.get('batch_size',128),
  study_revision=base.get('study_revision','original_20261113'),results_directory=base.get('results_directory','results/p_recipe'),base_configuration=str(base_path),
  control_directory=base.get('control_directory',str(R/'runs/p_recipe_20261113')),
  batch_size_by_run={read_json(path)['run']:read_json(path)['batch_size'] for path in configs})
 path=destination/'plan.json';path.write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps(plan,indent=2),flush=True);return plan

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--round',type=int,choices=(1,2,3),required=True);p.add_argument('--previous-state');p.add_argument('--base-configuration');p.add_argument('--study-directory');a=p.parse_args()
 if a.round>1 and a.previous_state is None:p.error('--previous-state is required after round1')
 prepare(a.round,read_json(a.previous_state) if a.previous_state else None,base_configuration=a.base_configuration,study_directory=a.study_directory)
