"""Registered A6 QM9 count comparison using the unchanged frozen-R3 scorer."""
import argparse,json,os,csv,fcntl,time
from pathlib import Path
import numpy as np
from finetune_statistics_entry import require_cpu_admission,atomic_json,fingerprint
from finetune_entry import CooperativeStop,set_actual_deadline
def run(c):
 with CooperativeStop() as stop:
  set_actual_deadline(c,stop);require_cpu_admission(c)
  import torch
  from phychem_mfm.phase1.v3_dev_evaluation import compare_panel
  from phychem_mfm.phase1.v3_dev_evaluation_v2 import _unpack
  torch.set_num_threads(1)
  out=Path(c['output']);out.mkdir(parents=True,exist_ok=True)
  with (out/'owner.lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   if (out/'primary_complete.json').exists():raise ValueError('Closed A6 statistics must not be repeated')
   gpu=json.loads(Path(c['GPU_receipt']).read_text())
   assert gpu['status']=='GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS' and gpu['train_groups']==30000 and gpu['evaluation_groups']==2048
   assert set(gpu['sources'])=={'T2_9M','T5_9M','T6_9M','random'}
   tasks=('qm9.U0_atom','qm9.homo','qm9.lumo','qm9.alpha')
   bindings={k:fingerprint(v) for k,v in gpu['sources'].items()}
   def load(label):
    m=json.loads(Path(gpu['sources'][label]).read_text())
    assert set(m['files'])=={t+'/R3' for t in tasks} and m['readout_seed']==0
    result={}
    for t in tasks:
     p=Path(m['files'][t+'/R3'])
     r=torch.load(p,map_location='cpu',weights_only=True);result[t]=_unpack(r['prediction'])
    return m,result
   reference,random=load('random');summaries={};rows=[]
   for label in ['T5_9M','T6_9M','T2_9M']:
    p=out/(label+'_scores.json')
    if p.exists():s=json.loads(p.read_text())
    else:
     if stop.requested or time.time()+c['work_unit_seconds']>=float(os.environ['P_MANAGED_STOP_NEW_UNITS_AT']):return 75
     manifest,actual=load(label)
     s=compare_panel(actual,random,architecture_sha256='C1-0-reference',reference_architecture_sha256='C1-0-reference',retain_paired_samples=True,retain_task_samples=True)
     assert s['complete'] and s['bootstrap_defined']==1000
     assert all(x['observed_molecules']==2048 for x in s['tasks'].values())
     s.update(source=label,train_groups=30000,evaluation_groups=2048,readout_seed=0,reference='matched30000_random_encoder_seed20261025',files_identity=bindings)
     atomic_json(p,s)
    summaries[label]=s
    for t in tasks:rows.append(dict(source=label,task=t,train_groups=30000,readout_seed=0,**s['tasks'][t]))
   if bindings!={k:fingerprint(v) for k,v in gpu['sources'].items()}:raise ValueError('Closed prediction manifests changed')
   old={k:json.loads(Path(v).read_text())['R3'] for k,v in c['old_scores'].items()}
   if old['T5_9M']['paired_bootstrap']['groups']!=old['T6_9M']['paired_bootstrap']['groups']:raise ValueError('Old molecular bootstrap order differs')
   if summaries['T5_9M']['paired_bootstrap']['groups']!=summaries['T6_9M']['paired_bootstrap']['groups']:raise ValueError('New molecular bootstrap order differs')
   contrast=[]
   for t in tasks:
    row=dict(task=t,comparison='T6_500000_minus_T5_250000',normalization='original_random_encoder_R3_E_ref_matched_to_readout_TRAIN_count')
    for n,values in [(8192,old),(30000,summaries)]:
     a,b=values['T6_9M'],values['T5_9M']
     point=a['tasks'][t]['normalized_improvement']-b['tasks'][t]['normalized_improvement']
     x=np.asarray(a['paired_bootstrap']['task_values'][t],float)-np.asarray(b['paired_bootstrap']['task_values'][t],float)
     assert x.shape==(1000,) and np.isfinite(x).all()
     row[str(n)]=dict(delta=point,ci95=np.quantile(x,[.025,.975]).tolist(),bootstrap_samples=1000,paired_within_readout_count=True)
    row['change_of_delta_point']=row['30000']['delta']-row['8192']['delta']
    row['cross_count_joint_CI']=None
    row['cross_count_CI_reason']='Original seven-task and new QM9-only producers consume different molecular draws; no unaligned-draw difference CI is formed.'
    contrast.append(row)
   result=dict(status='COMPLETE',rows=rows,molecule_count_effect=contrast,readout_TRAIN_group_counts=[8192,30000],original8192_nested_in30000=True,evaluation_groups=2048,old_readout_scores_reused=True,new_frozen_R3_cells=16,readout_seed=0,encoder_updated=False,geometry_unchanged=True,descriptive_only=True,new_recipes_adopted=False,source_identity=bindings)
   atomic_json(out/'primary.json',result)
   atomic_json(out/'primary_complete.json',dict(status='COMPLETE',job=os.environ['SLURM_JOB_ID'],rows=12,paired_task_contrasts=8,source_identity=bindings,old_primaries_recomputed=False))
   print(json.dumps(dict(status='COMPLETE',rows=12,paired_task_contrasts=8)),flush=True);return 0
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--configuration',type=Path,required=True);args=p.parse_args();c=json.loads(args.configuration.read_text())
 if c.get('ready') is not True or os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('CPU-only activated A6 statistics required')
 raise SystemExit(run(c))
