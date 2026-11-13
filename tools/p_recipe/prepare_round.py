"""Write exactly one registered screening round; fit dependencies stay explicit."""
import argparse,json
from pathlib import Path
from phychem_mfm.phase1.p_recipe_data import read_json
from phychem_mfm.phase1.p_recipe_plan import ROUNDS,LABEL_COMPONENTS,configuration
R=Path('/share/home/zixiao/descriptor_analysis');REPO=Path(__file__).resolve().parents[2]
OUT=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113')


def prepare(round_number,previous=None):
 base=read_json(REPO/'configs/p_recipe/base.json');components=set(previous['merged_components']) if previous else set()
 baseline=('B0','M1','M2')[round_number-1];arms=list(ROUNDS[round_number]);skipped={}
 if round_number==1:
  decision=R/'runs/p_recipe_20261113/D2_decision.json'
  if not read_json(decision).get('A5',False):
   arms.remove('A5');skipped['A5']='D2 did not trigger A5, including an explicitly recorded diagnostic timebox fallback'
 configs=[];fits={};destination=REPO/'configs/p_recipe'/('round'+str(round_number));destination.mkdir(parents=True,exist_ok=True)
 for arm in [baseline]+arms:
  selected=components|({arm} if arm!=baseline else set());name=f'round{round_number}_{arm}'
  c=configuration(base,selected,run=name,round_number=round_number,arm=arm)
  if 'B4' in selected:c['p_recipe']['gamma']=read_json(R/'runs/p_recipe_20261113/D4_gamma.json')['gamma']
  labels=sorted(selected&LABEL_COMPONENTS)
  if labels:
   target=OUT/'label_parameters'/('PM7_'+'_'.join(labels)+'.json');c['label_parameters']=str(target)
   if not target.is_file():fits[str(target)]=str(destination/(arm+'.json'))
  path=destination/(arm+'.json');path.write_text(json.dumps(c,indent=2)+'\n');configs.append(str(path))
 plan=dict(round=round_number,baseline=baseline,baseline_components=sorted(components),configurations=configs,skipped=skipped,label_parameters_to_fit=fits,batch_size=128)
 path=destination/'plan.json';path.write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps(plan,indent=2),flush=True);return plan

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--round',type=int,choices=(1,2,3),required=True);p.add_argument('--previous-state');a=p.parse_args()
 if a.round>1 and a.previous_state is None:p.error('--previous-state is required after round1')
 prepare(a.round,read_json(a.previous_state) if a.previous_state else None)