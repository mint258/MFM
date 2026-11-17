"""Prepare exactly the six confirmation runs and conditional common-field T7."""
import argparse,json
from pathlib import Path
from phychem_mfm.phase1.p_recipe_data import read_json
from phychem_mfm.phase1.p_recipe_plan import LABEL_COMPONENTS,configuration,runner_up_components
R=Path('/share/home/zixiao/descriptor_analysis');REPO=Path(__file__).resolve().parents[2]
OUT=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113')


def approved_switch_snapshot(state,base):
 """Freeze the user-confirmed delivery in future confirmation configs."""
 policy_path=REPO/'configs/p_recipe/user_directive_20261117.json'
 if base.get('study_revision')!='fixed_20261115':return None
 policy=read_json(policy_path)['confirmation']
 if state['round']!=3:raise ValueError('Confirmation waits for the completed round3 decision')
 if not policy.get('perf_gpu_delivery_received'):raise ValueError('Confirmation waits for the perf GPU delivery')
 proposal=read_json(REPO/policy['switch_proposal'])
 if proposal.get('status')!='USER_CONFIRMED' or not proposal.get('user_confirmation'):
  raise ValueError('Confirmation waits for explicit user switch confirmation')
 recommendation=proposal['recommendation']
 if any(recommendation['new_perf_switches'].values()) or recommendation.get('S8_composed_new_switches'):
  raise ValueError('The current recipe runner has not adopted new perf-line switches')
 for key in ('batch_size','workers','activation_checkpointing','gradient_accumulation_steps'):
  if base.get(key)!=recommendation[key]:raise ValueError(f'Approved runtime differs from base: {key}')
 if recommendation['precision']!='FP32' or recommendation['TF32'] is not False:
  raise ValueError('Current confirmation runner requires FP32 with TF32 disabled')
 return dict(source=policy['switch_proposal'],user_confirmation=proposal['user_confirmation'],
             gpu_delivery=proposal['gpu_delivery'],recommendation=recommendation,
             frozen_for_entire_run=True)


def prepare(state,*,base_configuration=None,study_directory=None):
 if state.get('selection_valid') is False:raise ValueError('The user invalidated this screening decision')
 base_path=Path(base_configuration) if base_configuration else REPO/'configs/p_recipe/base.json'
 if not base_path.is_absolute():base_path=REPO/base_path
 base=read_json(base_path);final=set(state['merged_components'])
 screening_samples=base.get('screening_samples',base.get('samples',3000000))
 confirmation_samples=3*screening_samples
 if state.get('study_revision','original_20261113')!=base.get('study_revision','original_20261113'):raise ValueError('Screening decision belongs to a different study revision')
 switch_snapshot=approved_switch_snapshot(state,base)
 third=state['adopted_winners'] if state['round']==3 else []
 runner=set(state['merge_base_components']) if state['round']==3 else set(state['merged_components']) if state['round']==2 else runner_up_components(final,third,state['merge_base_components'],state['component_evidence'])
 scope=read_json(R/'runs/p_recipe_20261113/D6_metadata.json');p=set(scope['P_enabled']);prime=set(scope['Pprime_enabled']);common=sorted(p&prime)
 lost=len(p)-len(common);need_t7=20*lost>len(p)
 specifications=[('T1',set(),'PM7',None,None),('T2',final,'PM7',None,None),('T3',runner,'PM7',None,None),
  ('T4',final,'UFF',None,common),('T5',final,'PM7',250000,None),('T6',final,'PM7',500000,None)]
 if need_t7:specifications.append(('T7',final,'PM7',None,common))
 root=Path(study_directory) if study_directory else REPO/'configs/p_recipe'
 if not root.is_absolute():root=REPO/root
 destination=root/'confirmation';destination.mkdir(parents=True,exist_ok=True);configs=[];fits={}
 for arm,components,source,count,fields in specifications:
  c=configuration(base,components,run=base.get('run_prefix','')+'confirmation_'+arm,round_number=0,arm=arm,samples=confirmation_samples,stage=3)
  c.update(source=source,condition='Pprime' if source=='UFF' else 'P',subset_molecules=count,subset_seed=20261112)
  if switch_snapshot is not None:c['confirmation_switch_snapshot']=switch_snapshot
  if source=='UFF' and (OUT/'corpus/Pprime_corpus.json').is_file():c['corpus']=str(OUT/'corpus/Pprime_corpus.json')
  if fields is not None:c['fields']=fields
  if 'B4' in components:c['p_recipe']['gamma']=read_json(R/'runs/p_recipe_20261113/D4_gamma.json')['gamma']
  labels=sorted(components&LABEL_COMPONENTS)
  if labels:
   path=OUT/'label_parameters'/(source+'_'+'_'.join(labels)+'.json');c['label_parameters']=str(path)
   if not path.is_file():fits[str(path)]=str(destination/(arm+'.json'))
  path=destination/(arm+'.json')
  if path.is_file():
   existing=read_json(path)
   c.update({key:existing[key] for key in ('handoff_request','handoff_ack') if key in existing})
   if existing.get('attempt',1)>1:
    c.update({key:existing[key] for key in ('run','output','attempt','batch_size','microbatch_size','resume','resume_samples','handoff_request','handoff_ack') if key in existing})
  path.write_text(json.dumps(c,indent=2)+'\n');configs.append(str(path))
 m2=state['merge_base_components'] if state['round']==3 else state['merged_components'] if state['round']==2 else None
 plan=dict(configurations=configs,final_components=sorted(final),runner_up_components=sorted(runner),
  study_revision=base.get('study_revision','original_20261113'),results_directory=base.get('results_directory','results/p_recipe'),base_configuration=str(base_path),
  control_directory=base.get('control_directory',str(R/'runs/p_recipe_20261113')),
  M2_components=m2,M2_after_rollback=bool(state['round']==3 and state['merge_rollback']),
  P_fields=len(p),Pprime_fields=len(prime),common_fields=common,lost_P_fields=lost,lost_P_fraction=lost/len(p),
  Pprime_comparator='T7' if need_t7 else 'T2',T7_required=need_t7,T7_queue_after_initial_six=need_t7,
  label_parameters_to_fit=fits,batch_size=base.get('batch_size',128),
  batch_size_by_run={read_json(path)['run']:read_json(path)['batch_size'] for path in configs},samples_per_run=confirmation_samples,screening_samples=screening_samples,confirmation_multiplier=3)
 if switch_snapshot is not None:plan['confirmation_switch_snapshot']=switch_snapshot
 (destination/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps(plan,indent=2),flush=True);return plan

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--state',required=True);p.add_argument('--base-configuration');p.add_argument('--study-directory');a=p.parse_args();prepare(read_json(a.state),base_configuration=a.base_configuration,study_directory=a.study_directory)
