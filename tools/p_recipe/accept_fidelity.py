"""One real-loader per-head overfit for the registered F1 implementation."""
import argparse,csv,json,time
from pathlib import Path
import numpy as np
import torch
from decide_round4 import completed
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset,dataset_configuration,original_predictions
from phychem_mfm.phase1.p_recipe_clip import GroupClipCalibration
from phychem_mfm.phase1.v2_s_training import s_model,sample_lr_ratio
from phychem_mfm.phase1.v31_training import V31PDModel
from phychem_mfm.phase1.v31_m2 import FieldMoments,save_metrics
from phychem_mfm.phase1.p_recipe_handoff import publish_checkpoint

CONTROL=Path('/share/home/zixiao/descriptor_analysis/runs/p_recipe_20261113')
read=lambda path:json.loads(Path(path).read_text())


def accept(configuration,c3_path,output,remaining_seconds):
 c=read(configuration)
 if c['arm']!='F1' or c['round']!=4:raise ValueError('Use the registered F1 configuration')
 c3=completed(c3_path,read(CONTROL/'study_execution.json'))
 if c3['arm']!='C3' or c3['round']!=3 or c3['study_revision']!=c['study_revision']:
  raise ValueError('Use the canonical C3 of this study revision')
 if not 0<remaining_seconds<=14400:raise ValueError('Respect the remaining registered4h development allowance')
 started=time.monotonic();output=Path(output);output.mkdir(parents=True,exist_ok=False)
 torch.set_num_threads(1);torch.manual_seed(c['seed']);rng=np.random.default_rng(c['seed'])
 torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 data=PRecipeDataset(**dataset_configuration(c))
 try:
  structural,architecture=s_model('C1-0','three')
  structural.encoder.backbone.activation_checkpointing=False
  model=V31PDModel(structural.encoder,data.view,forms=c['head_form'],pooling='registry',p_recipe=c['p_recipe'])
  model.configure_step_overhead(c.get('step_overhead',dict(grouped_fields=True,head_checkpointing=False,distance_tiling=True,prepared_input=True)))
  model=model.cuda().train();parameters=list(model.parameters())
  table=read(c['p_recipe']['fidelity_pairs'])
  fields=tuple(sorted({n for p in table['pairs'] for side in ('PM7_fields','xTB_fields') for n in p[side]}))
  if not set(fields)<=set(c['fields']):raise ValueError('F1 acceptance fields differ from the registered pairs')
  chosen=rng.choice(data.indices,1000,replace=False)
  fixed=[data.read(int(i),int(data.choices(int(i))[0])) for i in chosen]
  recipe=dict(configuration=str(configuration),run=c['run'],real_loader=True,
              acceptance='one_per_head_overfit_of_changed_fidelity_heads',fields=fields,
              molecules=1000,maximum_updates=10000,batch_size=32,
              criterion='Existing per-head original-unit R2 >=0.95',
              remaining_development_seconds=remaining_seconds)
  (output/'configuration.json').write_text(json.dumps(recipe,indent=2)+'\n')
  optimizer=torch.optim.AdamW(parameters,lr=c['lr'],betas=tuple(c['betas']),weight_decay=c['weight_decay'])
  clip=GroupClipCalibration(c['clip_calibration'],320000)

  @torch.no_grad()
  def evaluate():
   model.eval();moments=FieldMoments()
   for start in range(0,len(fixed),32):
    batch=fixed[start:start+32]
    prediction=model.predict(batch,groups=('P',),fields=fields)
    restored=original_predictions(model,prediction,batch,data.label_parameters)
    for name,value in restored.items():
     truth=np.concatenate([np.where(s['original_targets'][name].valid,s['original_targets'][name].raw,np.nan) for s in batch])
     moments.add(name,value.cpu().double().numpy(),truth)
   model.train();return moments.results()

  metrics=[];updates=0;timed_out=False
  with (output/'losses.csv').open('x',buffering=1) as stream:
   writer=csv.DictWriter(stream,fieldnames=['updates','samples','loss','preclip_norm','seconds']);writer.writeheader()
   for step in range(1,10001):
    if time.monotonic()-started>=remaining_seconds:timed_out=True;break
    batch=[fixed[int(i)] for i in rng.integers(1000,size=32)]
    for group in optimizer.param_groups:group['lr']=c['lr']*sample_lr_ratio(step*32,320000,'cosine')
    optimizer.zero_grad(set_to_none=True)
    prediction=model.predict(batch,groups=('P',),fields=fields)
    loss=model.loss(prediction,batch,groups=('P',),fields=fields)
    active=[v for n,v in loss.fields.items() if loss.counts[n]>0]
    total=torch.stack(active).mean();total.backward()
    norm=torch.nn.utils.clip_grad_norm_(parameters,clip.threshold,error_if_nonfinite=True);optimizer.step()
    updates=step
    clip.observe(float(norm),step*32,samples_before=(step-1)*32)
    row=dict(updates=step,samples=step*32,loss=float(total.detach()),preclip_norm=float(norm),seconds=time.monotonic()-started)
    writer.writerow(row)
    if step%500==0:
     metrics=evaluate();save_metrics(output/'per_head_metrics.csv',metrics)
     passed=len(metrics)==len(fields) and all(r['passed'] for r in metrics)
     print(json.dumps(dict(**row,passing_fields=sum(r['passed'] for r in metrics),fields=len(fields))),flush=True)
     if passed:break
  passed=len(metrics)==len(fields) and all(r['passed'] for r in metrics)
  publish_checkpoint(dict(model=model.state_dict(),optimizer=optimizer.state_dict(),configuration=recipe,
      architecture=architecture,updates=updates,rng=rng.bit_generator.state,torch_rng=torch.get_rng_state(),
      cuda_rng=torch.cuda.get_rng_state(),clip_calibration=clip.state_dict()),output/'final.pt')
  summary=dict(recipe,status='ACCEPTED' if passed else 'DEVELOPMENT_TIMEBOX' if timed_out else 'OVERFIT_NOT_PASSED',
               actual_updates=updates,seconds=time.monotonic()-started,all_fields_passed=passed,per_head_metrics=metrics)
  (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
  return summary
 finally:data.close()


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--configuration',required=True)
 parser.add_argument('--C3-configuration',dest='c3',required=True)
 parser.add_argument('--output',required=True)
 parser.add_argument('--remaining-seconds',type=float,required=True)
 args=parser.parse_args()
 print(json.dumps(accept(args.configuration,args.c3,args.output,args.remaining_seconds)),flush=True)
