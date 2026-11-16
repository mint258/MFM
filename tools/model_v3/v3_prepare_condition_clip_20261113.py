"""Condition-local M4 TRAIN p99: consume each producer statistic without pooling."""
import argparse,json,math,os,socket
from pathlib import Path

SCHEMA='MODEL_V3_TRAIN_PRECLIP_P99_V1'
POLICY='per_condition_and_trial'
RECIPE_FIELDS=('selected_C1','selected_latent','selected_views','selected_head',
 'selected_pooling','learning_rate','batch_size','schedule','samples','seed')

def read(path):
 return json.loads(Path(path).read_text())

def recipe_from_configuration(cfg):
 recipe=dict(selected_C1=cfg['distance_bias'],selected_latent=cfg['latent'],
  selected_views=cfg['views'],selected_head=cfg.get('head_form'),
  selected_pooling=cfg.get('pooling'),learning_rate=cfg['lr'],
  batch_size=cfg['batch_size'],schedule=cfg['schedule'],samples=cfg['samples'],seed=cfg['seed'])
 if cfg['condition']=='S':
  recipe.update(selected_head=None,selected_pooling=None)
 return recipe

def condition_clip(evidence,condition,recipe):
 if (evidence.get('schema')!=SCHEMA or evidence.get('source_policy')!=POLICY
     or evidence.get('quantile')!=.99 or evidence.get('method')!='linear'
     or evidence.get('population')!='all_effective_TRAIN_updates'
     or evidence.get('source_conditions')!=[condition]):
  raise ValueError('Require this condition and trial only; pooled or foreign TRAIN p99 is forbidden')
 sources=evidence.get('source_runs',[])
 if (len(sources)!=1 or sources[0].get('condition')!=condition
     or sources[0].get('scientific_samples')!=6000000
     or not sources[0].get('configuration') or not sources[0].get('output')):
  raise ValueError('Require one explicit complete logical6M TRAIN trial of this condition')
 source_recipe=evidence.get('recipe',{})
 active=[key for key in RECIPE_FIELDS
  if condition!='S' or key not in ('selected_head','selected_pooling')]
 if any(key not in source_recipe or source_recipe[key]!=recipe[key] for key in active):
  raise ValueError('Require the same actual selected recipe; inactive pure-S head/pooling do not enter')
 value=float(evidence['p99'])
 if not math.isfinite(value) or value<=0:
  raise ValueError('Require the original finite positive producer TRAIN p99')
 return value

def prepare_evidence(configuration):
 cp=Path(configuration);cfg=read(cp);output=Path(cfg['output'])
 summary=read(output/'summary.json')
 if (cfg['samples']!=6000000 or cfg['expected_molecules']!=240000 or cfg['seed']!=0
     or summary.get('status')!='TRAINING_COMPLETE_DEV_EVALUATION_PENDING'
     or summary.get('samples')!=6000000):
  raise ValueError('Require the actual closed240k/6M/seed0 source trial')
 evidence=dict(schema=SCHEMA,source_policy=POLICY,quantile=.99,method='linear',
  population='all_effective_TRAIN_updates',source_conditions=[cfg['condition']],
  source_runs=[dict(condition=cfg['condition'],scientific_samples=6000000,
   configuration=str(cp),output=str(output),summary=str(output/'summary.json'),
   stage=cfg.get('stage'),arm=cfg.get('arm'))],
  recipe=recipe_from_configuration(cfg),p99=summary['preclip_gradient_p99'],
  statistic_source='original_training_producer_summary',
  canonical_restored_history=True,unsaved_replay_tail_added=False,
  percentile_recomputed=False,downstream_TEST_read=False)
 condition_clip(evidence,cfg['condition'],evidence['recipe'])
 return evidence

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--configuration',type=Path,required=True)
 parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args()
 if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20':
  raise ValueError('Use the existing development node')
 if args.output.exists():
  raise FileExistsError('Preserve existing evidence; use a fresh output path')
 evidence=prepare_evidence(args.configuration)
 args.output.write_text(json.dumps(evidence,indent=2)+'\n')
 print(json.dumps(dict(status='CONDITION_LOCAL_TRAIN_P99_EVIDENCE_PREPARED',
  condition=evidence['source_conditions'][0],p99=evidence['p99'],
  percentile_recomputed=False)))
if __name__=='__main__':main()
