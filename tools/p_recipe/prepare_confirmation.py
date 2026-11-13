"""Prepare exactly the six confirmation runs and conditional common-field T7."""
import argparse,json
from pathlib import Path
from phychem_mfm.phase1.p_recipe_data import read_json
from phychem_mfm.phase1.p_recipe_plan import LABEL_COMPONENTS,configuration,runner_up_components
R=Path('/share/home/zixiao/descriptor_analysis');REPO=Path(__file__).resolve().parents[2]
OUT=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113')


def prepare(state):
 base=read_json(REPO/'configs/p_recipe/base.json');final=set(state['merged_components'])
 third=state['adopted_winners'] if state['round']==3 else []
 runner=runner_up_components(final,third,state['merge_base_components'],state['component_evidence'])
 scope=read_json(R/'runs/p_recipe_20261113/D6_metadata.json');p=set(scope['P_enabled']);prime=set(scope['Pprime_enabled']);common=sorted(p&prime)
 lost=len(p)-len(common);need_t7=20*lost>len(p)
 specifications=[('T1',set(),'PM7',None,None),('T2',final,'PM7',None,None),('T3',runner,'PM7',None,None),
  ('T4',final,'UFF',None,common),('T5',final,'PM7',250000,None),('T6',final,'PM7',500000,None)]
 if need_t7:specifications.append(('T7',final,'PM7',None,common))
 destination=REPO/'configs/p_recipe/confirmation';destination.mkdir(parents=True,exist_ok=True);configs=[];fits={}
 for arm,components,source,count,fields in specifications:
  c=configuration(base,components,run='confirmation_'+arm,round_number=0,arm=arm,samples=4500000,stage=3)
  c.update(source=source,condition='Pprime' if source=='UFF' else 'P',subset_molecules=count,subset_seed=20261112)
  if fields is not None:c['fields']=fields
  if 'B4' in components:c['p_recipe']['gamma']=read_json(R/'runs/p_recipe_20261113/D4_gamma.json')['gamma']
  labels=sorted(components&LABEL_COMPONENTS)
  if labels:
   path=OUT/'label_parameters'/(source+'_'+'_'.join(labels)+'.json');c['label_parameters']=str(path)
   if not path.is_file():fits[str(path)]=str(destination/(arm+'.json'))
  path=destination/(arm+'.json')
  if path.is_file():
   existing=read_json(path)
   if existing.get('attempt',1)>1:
    c.update({key:existing[key] for key in ('run','output','attempt','batch_size','microbatch_size')})
  path.write_text(json.dumps(c,indent=2)+'\n');configs.append(str(path))
 m2=state['merge_base_components'] if state['round']==3 else state['merged_components'] if state['round']==2 else None
 plan=dict(configurations=configs,final_components=sorted(final),runner_up_components=sorted(runner),
  M2_components=m2,M2_after_rollback=bool(state['round']==3 and state['merge_rollback']),
  P_fields=len(p),Pprime_fields=len(prime),common_fields=common,lost_P_fields=lost,lost_P_fraction=lost/len(p),
  Pprime_comparator='T7' if need_t7 else 'T2',T7_required=need_t7,T7_queue_after_initial_six=need_t7,
  label_parameters_to_fit=fits,batch_size=base.get('batch_size',128),
  batch_size_by_run={read_json(path)['run']:read_json(path)['batch_size'] for path in configs},samples_per_run=4500000)
 (destination/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps(plan,indent=2),flush=True);return plan

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--state',required=True);a=p.parse_args();prepare(read_json(a.state))
