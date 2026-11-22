"""Original deferred R1/R3 scoring for the registered I1 own3M readout."""
import argparse,json,os,time
from pathlib import Path
from finetune_entry import CooperativeStop,set_actual_deadline
from budget_statistics_entry import require_cpu_admission
def run(c):
 if c.get('ready') is not True:raise ValueError('Actual I1 frozen readout must close before activation')
 with CooperativeStop() as stop:
  set_actual_deadline(c,stop);require_cpu_admission(c)
  import torch,cpu_statistics,shared_guard
  torch.set_num_threads(1)
  original=json.loads(Path(c['original_configuration']).read_text())
  if (original['arm']!='I1' or original['source_training_budget']!=3000000
      or original['samples']!=3000000 or original['run']!=c['original_run']
      or original['output']!=c['output'] or original['readout_seed']!=0):
   raise ValueError('Only the exact original I1 own3M frozen readout may be finalized')
  if stop.requested:return 75
  claim=json.loads((shared_guard.REGISTRY/'p-recipe.json').read_text())
  future=sum(x['bytes'] for x in claim['entries'] if x['kind']=='shared_fs' and x.get('path')=='/share')
  shared_guard.check_with_timeout('p-recipe','shared_fs',future,path='/share')
  def admit(candidate):
   if candidate!=original:raise ValueError('Statistics input changed')
   require_cpu_admission(c)
  from finetune_statistics_entry import fingerprint,atomic_json
  from i1_frozen_readout import complete_r1
  summary_path=Path(c['output'])/'summary.json';summary=json.loads(summary_path.read_text())
  identity=summary['H0_cache_identity']
  if {k:fingerprint(v['path']) for k,v in identity.items()}!=identity:raise ValueError('Original H0 cache identity changed')
  def should_stop():
   return stop.requested or time.time()+c['work_unit_seconds']>=float(os.environ['P_MANAGED_STOP_NEW_UNITS_AT'])
  if not complete_r1(dict(original,output=str(Path(c['output'])/'readout')),should_stop):return 75
  summary.update(R1_deferred_to_CPU=False,R1_CPU_complete=True);atomic_json(summary_path,summary)
  old=cpu_statistics.admit;cpu_statistics.admit=admit
  try:result=cpu_statistics.finalize(original)
  finally:cpu_statistics.admit=old
  print(json.dumps(result),flush=True);return 0
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--configuration',type=Path,required=True);a=p.parse_args();c=json.loads(a.configuration.read_text())
 if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('CPU-only entry required')
 raise SystemExit(run(c))
