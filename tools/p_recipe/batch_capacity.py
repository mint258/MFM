"""User-authorized batch admission with real P forwards/backwards; no checkpoint."""
import argparse,gc,json,time
from pathlib import Path
import numpy as np
import torch
from phychem_mfm.phase1.v31_loader import MFM4Dataset,encode_samples
from phychem_mfm.phase1.v31_training import V31PDModel
from phychem_mfm.phase1.v2_s_training import s_model
from phychem_mfm.phase1.p_recipe import collapse_penalty
R=Path('/share/home/zixiao/descriptor_analysis');C=R/'runs/p_recipe_20261113'

def main():
 p=argparse.ArgumentParser();p.add_argument('--batch',type=int);p.add_argument('--stress-batches',type=int,default=1);p.add_argument('--maximum',type=int,default=256);a=p.parse_args()
 old=json.loads((R/'runs/model_v31_20261105/M3_P_C1_0_seed0_micro32.APPROVED.json').read_text())
 corpus=json.loads(Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/corpus/corpus.json').read_text())
 indices=np.load(corpus['train_indices'])
 data=MFM4Dataset(corpus['source_root'],training_view=old['training_view'],normalizations=json.loads(Path(old['normalizations']).read_text()),molecule_indices=indices,k=10)
 rng=np.random.default_rng(0);samples=[data.sample(rng) for _ in range(a.maximum*a.stress_batches)]
 torch.manual_seed(0);torch.set_num_threads(1)
 free_at_start,total_at_start=torch.cuda.mem_get_info()
 structural,_=s_model('C1-0','three')
 # Covers the largest permitted head combination as a memory check only.
 pd=V31PDModel(structural.encoder,data.view,forms='H3',p_recipe=dict(shared_projector=True,pma_pooling=True)).cuda().train()
 fields=tuple(f.name for f in pd.registry.enabled(('P',)))
 params=list(pd.parameters());optimizer=torch.optim.AdamW(params,lr=0.,betas=(.9,.95),weight_decay=.01)
 gamma=float(json.loads((C/'D4_gamma.json').read_text())['gamma'])
 limit=free_at_start
 margin=max(1536*1024**2,int(limit*.08));records=[]
 def attempt(batch):
  torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();started=time.monotonic()
  for step in range(2*a.stress_batches):
   start=(step//2)*a.maximum;selected=samples[start:start+batch]
   optimizer.zero_grad(set_to_none=True)
   clean,h=encode_samples(selected,pd.encoder,device='cuda')
   prediction=pd.predict(selected,groups=('P',),fields=fields,clean_features=h,clean_batch=clean)
   loss=pd.loss(prediction,selected,groups=('P',),fields=fields).total+.1*collapse_penalty(h,gamma)
   loss.backward();torch.nn.utils.clip_grad_norm_(params,1.);optimizer.step()
  torch.cuda.synchronize()
  return dict(batch_size=batch,status='PASS',peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),seconds=time.monotonic()-started,max_atoms=max(len(s['Z']) for offset in range(0,a.maximum*a.stress_batches,a.maximum) for s in samples[offset:offset+batch]),total_atoms=sum(len(s['Z']) for s in selected))
 candidates=[a.batch] if a.batch else list(range(32,a.maximum+1,32))
 selected=None
 for batch in candidates:
  try:
   row=attempt(batch);row['headroom_pass']=row['peak_reserved_bytes']<=limit-margin
   if row['headroom_pass']:selected=batch
  except torch.cuda.OutOfMemoryError:
   row=dict(batch_size=batch,status='CUDA_OOM',headroom_pass=False)
  records.append(row);print(json.dumps(row),flush=True)
  optimizer.zero_grad(set_to_none=True);gc.collect();torch.cuda.empty_cache()
  if not row['headroom_pass']:break
 result=dict(device=torch.cuda.get_device_name(0),device_total_bytes=total_at_start,device_free_at_start_bytes=free_at_start,reserve_bytes=margin,selected_batch_size=selected,records=records,source='approved clean TRAIN; original normalization used for memory only while repaired D4 is queued',numerical_recipe='FP32 noTF32; H3+projector+PMA+B4; P clean and required perturbed label route; AdamW state allocated; lr0; no checkpoint',actual_maximum_tested=a.maximum)
 path=C/('batch_capacity_'+str(__import__('os').environ.get('SLURM_JOB_ID',__import__('os').environ.get('P_RECIPE_RUN_ID','unknown')))+'.json');path.write_text(json.dumps(result,indent=2)+'\n')
 data.close();print(json.dumps(result),flush=True)
if __name__=='__main__':main()