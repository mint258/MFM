"""The taskbook's fixed arms and composition rules; no extra candidates."""
from copy import deepcopy
import json
from pathlib import Path

ROUNDS={1:('A1','A2','A3','A4','A5'),2:('B1','B2','B3','B4'),3:('C1','C2','C3','C4')}
LABEL_COMPONENTS=frozenset(('A1','A2','A5'))
CONFLICTS=(frozenset(('B2','B3')),frozenset(('C1','C2')),
           frozenset(('X1','X2')),frozenset(('F1','F2')))
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
 apply_round4_components(c,components,base)
 return c


def apply_round4_components(configuration,components,base):
 """Carry only the registered round4 field/head changes into merged recipes."""
 active=set(components)&{'X1','X2','F1','F2'}
 if not active:
  if base.get('round4_field_selection'):
   configuration.pop('fields',None);configuration.pop('round4_field_selection',None)
  return
 if {'X1','X2'}<=active or {'F1','F2'}<=active:
  raise ValueError('Mutually exclusive round4 components must be resolved before configuration')
 path=Path(__file__).resolve().parents[3]/'configs/p_recipe/fixed_20261115/round4/fidelity_pairs.json'
 table=json.loads(path.read_text());pairs=table['pairs']
 names={entry['field'] for entry in table['unpaired']}
 names.update(name for pair in pairs for side in ('PM7_fields','xTB_fields') for name in pair[side])
 if 'X1' in active:names={n for n in names if int(n.split('.')[2][1:]) not in (623,624,625)}
 if 'F2' in active:names.difference_update(name for pair in pairs for name in pair['xTB_fields'])
 configuration['fields']=sorted(names);configuration['round4_field_selection']=True
 recipe=configuration['p_recipe']
 if 'B4' in components and 'gamma' in base.get('p_recipe',{}):recipe['gamma']=base['p_recipe']['gamma']
 if 'X2' in active:recipe['field_loss_multipliers']={n:5 for n in sorted(names) if int(n.split('.')[2][1:]) in (624,625)}
 if 'F1' in active:recipe.update(fidelity_pairs=str(path),method_embedding_dim=8)


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
