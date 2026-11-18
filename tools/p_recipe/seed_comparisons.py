"""Plan only registered borderline seed1 runs and reuse completed references."""
import argparse,fcntl,json
from pathlib import Path
from execution_ledger import write
from phychem_mfm.phase1.p_recipe_seed_policy import second_seed_required,combined_seed_decision,fresh_seed1_configuration

REPO=Path(__file__).resolve().parents[2]
CONTROL=Path('/share/home/zixiao/descriptor_analysis/runs/p_recipe_20261113')
read=lambda path:json.loads(Path(path).read_text())


class SeedComparisons:
 def __init__(self,directory,*,registry=None,configuration_directory=None,output_root=None,ledger=None,reference=None,reference_configurations=None):
  self.directory=Path(directory)
  self.registry=Path(registry) if registry else CONTROL/'fixed_20261115/seed1_registry.json'
  self.configurations=Path(configuration_directory) if configuration_directory else REPO/'configs/p_recipe/fixed_20261115/conditional_seed1'
  self.output_root=output_root
  self.ledger=ledger if ledger is not None else read(CONTROL/'study_execution.json')
  self.reference=Path(reference) if reference else REPO/'configs/p_recipe/M2_SEED1_REFERENCE.json'
  self.reference_configurations=reference_configurations or {}
  state=self.directory/'seed_comparisons.json'
  self.previous=read(state).get('comparisons',{}) if state.is_file() else {}
  self.results={};self.requested={};self.scores={}

 def complete(self,c):
  if c['run'] in self.scores:return True
  record=self.ledger.get('runs',{}).get(c['run'],{})
  if record.get('state')!='COMPLETED' or record.get('exit_code') not in (0,'0:0'):return False
  try:
   summary=read(Path(c['output'])/'summary.json');scores=read(Path(c['output'])/'readout/scores.json')
   valid=(summary.get('status')=='COMPLETE' and summary['samples']==c['samples'] and
       all(scores[r].get('complete') and scores[r]['bootstrap_samples']==1000 and scores[r]['bootstrap_defined']==1000 for r in ('R1','R3')))
   if valid:self.scores[c['run']]=scores
   return valid
  except (FileNotFoundError,KeyError):return False

 def seed1(self,parent):
  """One canonical child per completed seed0; never submit a process here."""
  if parent['seed']!=0:raise ValueError('A seed1 parent cannot request another seed')
  self.registry.parent.mkdir(parents=True,exist_ok=True)
  with self.registry.with_suffix('.lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX)
   registry=read(self.registry) if self.registry.is_file() else dict(schema='P_RECIPE_CONDITIONAL_SEED1_V1',runs={})
   existing=registry['runs'].get(parent['run'])
   reused=False
   if existing:path=Path(existing['configuration'])
   else:
    reference=read(self.reference) if self.reference.is_file() else {}
    if parent['run'] in self.reference_configurations:
     path=Path(self.reference_configurations[parent['run']]);reused=True
    elif (reference.get('ready_for_reuse') and reference.get('observed_seed_noise',{}).get('seed0_run')==parent['run']
        and parent['samples']==reference.get('samples')):
     path=Path(reference['configuration']);path=path if path.is_absolute() else REPO/path;reused=True
    else:
     path=self.configurations/(parent['run']+'.json')
     if not path.exists():
      path.parent.mkdir(parents=True,exist_ok=True)
      write(path,fresh_seed1_configuration(parent,output_root=self.output_root))
    registry['runs'][parent['run']]=dict(configuration=str(path),reference_reused=reused,seed0_run=parent['run'])
    write(self.registry,registry)
   child=read(path)
   if child['seed']!=1 or child['samples']!=parent['samples']:
    raise ValueError('The stored child is not the matching registered seed1')
   if not reused and not existing and child.get('seed0_run')!=parent['run']:
    raise ValueError('The existing child configuration belongs to a different seed0')
   self.requested[parent['run']]=str(path)
   return child,str(path)

 @staticmethod
 def configuration(value):
  return (value,None) if isinstance(value,dict) else (read(value),str(value))

 @staticmethod
 def values(a,b,readout):
  aa=a[readout];bb=b[readout]
  return (aa['mean_normalized_improvement'],bb['mean_normalized_improvement'],
          aa['paired_bootstrap']['values'],bb['paired_bootstrap']['values'])

 def assess(self,A,B,purpose,round_number,*,descriptive=False):
  a,a_path=self.configuration(A);b,b_path=self.configuration(B)
  if a['seed']!=0 or b['seed']!=0:raise ValueError('Start each comparison from seed0')
  key='|'.join(map(str,(purpose,round_number,a['run'],b['run'])))
  result=dict(A=a['run'],B=b['run'],A_configuration=a_path,B_configuration=b_path,
              purpose=purpose,round=round_number,ready=False,seed_trigger_readout='R3')
  self.results[key]=result
  if not self.complete(a) or not self.complete(b):
   result['status']='WAITING_FOR_COMPLETE_SEED0';return result
  sa=self.scores[a['run']];sb=self.scores[b['run']]
  av,bv,*_=self.values(sa,sb,'R3')
  required=not descriptive and second_seed_required(av,bv)
  result.update(seed1_required=required,seed0_rows=self.previous.get(key,{}).get('seed0_rows'))
  def rows_and_evidence(scores):
   rows=[];evidence={}
   for readout in ('R3','R1'):
    pairs={seed:self.values(aa,bb,readout) for seed,(aa,bb) in scores.items()}
    combined=combined_seed_decision(pairs);decision=dict(combined['decision'])
    if descriptive:decision['verdict']='descriptive'
    rows.append(dict(purpose=purpose,round=round_number,readout=readout,task='MEAN',A=a['run'],B=b['run'],**decision))
    evidence[readout]=combined
   return rows,evidence
  result['seed0_evidence']=self.previous.get(key,{}).get('seed0_evidence')
  if result['seed0_rows'] is None or result['seed0_evidence'] is None:
   result['seed0_rows'],result['seed0_evidence']=rows_and_evidence({0:(sa,sb)})
  if required:
   aa,pa=self.seed1(a);bb,pb=self.seed1(b)
   result['seed1_configurations']={'A':pa,'B':pb}
   if not self.complete(aa) or not self.complete(bb):
    result['status']='WAITING_FOR_REGISTERED_SEED1';return result
   one_a=self.scores[aa['run']];one_b=self.scores[bb['run']]
   scores={0:(sa,sb),1:(one_a,one_b)}
  else:scores={0:(sa,sb)}
  if required:result['rows'],result['evidence']=rows_and_evidence(scores)
  else:result['rows'],result['evidence']=result['seed0_rows'],result['seed0_evidence']
  result.update(status='COMPLETE',ready=True,seed_count=len(scores),
                per_seed_scores={seed:{'A':{r:aa[r]['mean_normalized_improvement'] for r in ('R1','R3')},
                                      'B':{r:bb[r]['mean_normalized_improvement'] for r in ('R1','R3')}}
                                 for seed,(aa,bb) in scores.items()})
  return result

 def save(self):
  if not self.results:raise ValueError('No registered comparisons were supplied')
  self.directory.mkdir(parents=True,exist_ok=True)
  requested=list(dict.fromkeys(self.requested.values()))
  launch=[p for p in requested if read(p)['run'] not in self.ledger.get('runs',{})]
  state=dict(status='COMPLETE' if all(r['ready'] for r in self.results.values()) else 'WAITING_REGISTERED_INPUTS',
       authority='docs/p_recipe/USER_DIRECTIVE_20261118B.md',comparisons=self.results,
       seed1_configurations=requested,seed1_plan=str(self.directory/'seed1_plan.json'),jobs_submitted=0)
  write(self.directory/'seed_comparisons.json',state)
  write(self.directory/'seed1_plan.json',dict(configurations=launch,study_revision='fixed_20261115',
       purpose='registered_borderline_seed1_only',maximum_seeds=2,requires_actual_node_capacity_admission=True))
  return state


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pairs',required=True)
 parser.add_argument('--directory',required=True);parser.add_argument('--output-root')
 parser.add_argument('--reference-configurations');args=parser.parse_args()
 session=SeedComparisons(args.directory,output_root=args.output_root,
       reference_configurations=read(args.reference_configurations) if args.reference_configurations else None)
 for pair in read(args.pairs):session.assess(pair['A'],pair['B'],pair['purpose'],pair['round'],descriptive=pair.get('descriptive',False))
 state=session.save();print(json.dumps(dict(status=state['status'],seed1_plan=state['seed1_plan'],jobs_submitted=0)),flush=True)
