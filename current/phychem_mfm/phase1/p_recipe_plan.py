"""The taskbook's fixed arms and composition rules; no extra candidates."""
from copy import deepcopy
from pathlib import Path

ROUNDS={1:('A1','A2','A3','A4','A5'),2:('B1','B2','B3','B4'),3:('C1','C2','C3','C4')}
LABEL_COMPONENTS=frozenset(('A1','A2','A5'))
CONFLICTS=(frozenset(('B2','B3')),frozenset(('C1','C2')))
RECIPE_FLAGS={'A1':'element_residual','A2':'state_difference','A3':'pair_without_distance',
 'A4':'family_equal','A5':'heavy_tail','B1':'shared_projector','B3':'pma_pooling',
 'B4':'anti_collapse','C4':'uncertainty_weighting'}


def configuration(base,components,*,run,round_number,arm,samples=None,stage=2):
 if samples is None:samples=base.get('screening_samples',base.get('samples',3000000))
 batch=base.get('batch_size',32)
 c=deepcopy(base);c.update(run=run,round=round_number,arm=arm,samples=samples,stage=stage,
  batch_size=batch,microbatch_size=batch,persist_features=False,components=sorted(components))
 c['p_recipe']={};c['head_form']='H1';c['lr']=base['lr'];c['mean_labels']=False
 for key in ('resume','resume_samples','resume_from_output','attempt','handoff_request','handoff_ack',
             'label_parameters','speed_calibration','calibration_training','speed_board','required_gpu_uuid','evaluation_samples',
             'reuse_baseline_configuration','reuse_baseline_family_prefix','baseline_clip_exception'):
  c.pop(key,None)
 c['output']=str(Path(base['output']).parent/run)
 if c.get('checkpoint_policy')=='screen_final_confirmation_milestones':
  interval=base.get('screening_checkpoint_interval') if stage==2 else base.get('confirmation_checkpoint_interval',500000)
  points=set(range(interval,samples+1,interval)) if interval else set()
  if stage==2 and base.get('initial_checkpoint_samples'):
   points.add(min(samples,base['initial_checkpoint_samples']))
  c['checkpoint_samples']=sorted(points|{samples})
 for component in sorted(components):
  if component in RECIPE_FLAGS:c['p_recipe'][RECIPE_FLAGS[component]]=True
  elif component=='B2':c['head_form']='H3'
  elif component=='C1':c['lr']=base['lr']*2
  elif component=='C2':c['lr']=base['lr']*.5
  elif component=='C3':c['mean_labels']=True
 return c


def accepted_winners(decisions):
 selected={name for name,value in decisions.items() if value['verdict']=='win'}
 for conflict in CONFLICTS:
  active=selected&conflict
  if len(active)>1:
   winner=max(sorted(active),key=lambda name:decisions[name]['delta'])
   selected.difference_update(active-{winner})
 return selected


def runner_up_components(final_components,third_round_winners,pre_third_merge,component_evidence):
 if third_round_winners:return set(pre_third_merge)
 if not final_components:return set()
 least=min(sorted(final_components),key=lambda name:component_evidence[name]['delta'])
 return set(final_components)-{least}
