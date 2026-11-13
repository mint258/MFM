"""P-only full-TRAIN execution; every arm owns its complete sample schedule."""
from concurrent.futures import ProcessPoolExecutor
import csv,json,multiprocessing,os,time
from pathlib import Path
import numpy as np
import torch
from .p_recipe_data import PRecipeDataset,dataset_configuration,read_json,original_predictions
from .p_recipe import normalized_field_weights,UncertaintyWeights,collapse_penalty
from .v31_loader import encode_samples
from .v31_training import V31PDModel
from .v31_prefetch import ordered_sample_batches
from .v2_s_training import s_model,sample_lr_ratio
from .v3_training import SampleClock
from .v2_disk import save_checkpoint
from .v3_latent_training import TrainingHistory

REPO=Path(__file__).resolve().parents[3]

def init_reader(configuration,mean_labels):
 global DATA,MEAN
 torch.set_num_threads(1);DATA=PRecipeDataset(**configuration);MEAN=mean_labels

def read_choice(choice):
 molecule,conformer=choice;sample=DATA.read(molecule,conformer)
 if MEAN:sample['targets']=DATA.molecule_mean(molecule)
 return sample

def family_losses(loss,families):
 names=[n for n in loss.fields if loss.counts[n]>0]
 return {family:torch.stack([loss.fields[n] for n in names if families[n]==family]).mean()
         for family in sorted({families[n] for n in names})}

def train(configuration):
 c=dict(configuration);recipe=c.get('p_recipe',{});torch.set_num_threads(1);torch.manual_seed(c['seed'])
 c.setdefault('activation_checkpointing',True)
 reader=dataset_configuration(c);data=PRecipeDataset(**reader);validation=PRecipeDataset(**dataset_configuration(c,validation=True))
 fixed=[(int(m),int(validation.choices(int(m))[0])) for m in validation.indices]
 print(json.dumps(dict(run=c['run'],TRAIN_molecules=len(data),batch_size=c['batch_size'],microbatch_size=c['microbatch_size'],source=c['source'])),flush=True)
 structural,architecture=s_model('C1-0','three')
 # Keep the actual B128 batch and recompute existing layers during backward.
 # This preserves parameter/state keys, losses and the original sampled graphs.
 structural.encoder.backbone.activation_checkpointing=c['activation_checkpointing']
 architecture['backbone']['activation_checkpointing']=c['activation_checkpointing']
 pd=V31PDModel(structural.encoder,data.view,forms=c['head_form'],pooling='registry',p_recipe=recipe)
 modules=dict(structural=structural,pd=pd)
 fields=tuple(f.name for f in pd.registry.enabled(('P',)) if c.get('fields') is None or f.name in c['fields'])
 heads={pd.selections[n][0] for n in fields};families={f.name:f.family for f in pd.head_registry.fields if f.name in heads}
 if recipe.get('uncertainty_weighting',False):
  names=sorted(set(families.values())) if recipe.get('family_equal',False) else list(families)
  modules['uncertainty']=UncertaintyWeights(names)
 model=torch.nn.ModuleDict(modules).cuda().train();params=list(model.parameters())
 optimizer=torch.optim.AdamW(params,lr=c['lr'],betas=tuple(c['betas']),weight_decay=c['weight_decay'])
 clock=SampleClock(c['samples'],milestones=tuple(range(500000,c['samples']+1,500000)));rng=np.random.default_rng(c['seed']);clip=read_json(c['clip_reference'])['clip']
 gamma=recipe.get('gamma',0.1597693323500406);output=Path(c['output']);resuming=c.get('resume')
 output.mkdir(parents=True,exist_ok=bool(resuming));prior=0.;window={};window_updates=0;clipped=0;total_window=[]
 if resuming:
  cp=torch.load(resuming,map_location='cpu',weights_only=True);model.load_state_dict(cp['model']);optimizer.load_state_dict(cp['optimizer']);clock.load_state_dict(cp['clock']);rng.bit_generator.state=cp['rng'];torch.set_rng_state(cp['torch_rng']);torch.cuda.set_rng_state(cp['cuda_rng']);prior=cp['elapsed_seconds'];window=cp['family_window'];window_updates=cp['family_window_updates'];clipped=cp['clipped_updates'];total_window=cp.get('total_window',[])
 (output/'configuration.json').write_text(json.dumps(c,indent=2)+'\n')
 history=TrainingHistory(output,c,initial_samples=clock.samples_consumed);history.window=total_window
 csv_path=REPO/'results/p_recipe/training'/c['run']/'family_losses.csv';csv_path.parent.mkdir(parents=True,exist_ok=True)
 columns=['run','kind','samples','updates','family','loss','clipped_fraction','seconds']
 def deliver(rows):
  exists=csv_path.exists()
  with csv_path.open('a',newline='') as stream:
   writer=csv.DictWriter(stream,fieldnames=columns)
   if not exists:writer.writeheader()
   writer.writerows(rows)
 def calculate(samples):
  clean,h=encode_samples(samples,pd.encoder,device='cuda')
  prediction=pd.predict(samples,groups=('P',),fields=fields,clean_features=h,clean_batch=clean)
  loss=pd.loss(prediction,samples,groups=('P',),fields=fields);family=family_losses(loss,families)
  if recipe.get('uncertainty_weighting',False):
   values=family if recipe.get('family_equal',False) else {n:v for n,v in loss.fields.items() if loss.counts[n]>0}
   total=model['uncertainty'](values)
  else:
   active={n:families[n] for n in loss.fields if loss.counts[n]>0}
   weights=normalized_field_weights(active,family_equal=recipe.get('family_equal',False),device='cuda')
   total=sum((loss.fields[n]*w for n,w in weights.items()),loss.total.new_zeros(()))
  if recipe.get('anti_collapse',False):total=total+.1*collapse_penalty(h,gamma)
  return total,family,prediction
 started=time.monotonic();initial_samples=clock.samples_consumed;clip_reported=False;success=False
 def validate():
  model.eval();sums={};counts={};native={}
  with torch.no_grad():
   for start in range(0,len(fixed),c['batch_size']):
    samples=[validation.read(m,conf) for m,conf in fixed[start:start+c['batch_size']]]
    clean,h=encode_samples(samples,pd.encoder,device='cuda');pred=pd.predict(samples,groups=('P',),fields=fields,clean_features=h,clean_batch=clean)
    loss=pd.loss(pred,samples,groups=('P',),fields=fields)
    for name,value in loss.fields.items():
     sums[name]=sums.get(name,0.)+float(value)*loss.counts[name];counts[name]=counts.get(name,0)+loss.counts[name]
    restored=original_predictions(pd,pred,samples,data.label_parameters)
    for name,value in restored.items():
     truth=np.concatenate([s['original_targets'][name].raw for s in samples]);valid=np.concatenate([s['original_targets'][name].valid for s in samples]);values=value.cpu().double().numpy()
     if valid.any():
      a,n=native.get(name,(0.,0));native[name]=(a+float(np.abs(values[valid]-truth[valid]).sum()),n+int(valid.sum()))
  result={f:float(np.mean([sums[n]/counts[n] for n in sums if families[n]==f and counts[n]>0])) for f in sorted(set(families.values())) if any(families[n]==f and counts[n]>0 for n in sums)}
  native_rows=[dict(field=n,MAE_original_units=a/nobs,observations=nobs,unit=pd.definitions[n].get('unit','source_registry_unit')) for n,(a,nobs) in native.items()]
  with (csv_path.parent/('VAL_original_units_'+str(clock.samples_consumed)+'.csv')).open('w',newline='') as stream:
   writer=csv.DictWriter(stream,fieldnames=['field','MAE_original_units','observations','unit']);writer.writeheader();writer.writerows(native_rows)
  model.train();return result
 try:
  with ProcessPoolExecutor(c['workers'],mp_context=multiprocessing.get_context('spawn'),initializer=init_reader,initargs=(reader,c['mean_labels'])) as pool,(output/'losses.csv').open('a' if resuming else 'w',buffering=1) as stream:
   writer=csv.DictWriter(stream,fieldnames=['samples','updates','total','preclip_norm','lr','seconds'])
   if stream.tell()==0:writer.writeheader()
   for samples,consumed_rng in ordered_sample_batches(pool,read_choice,data,clock,rng,c['batch_size'],c['samples']):
    lr=c['lr']*sample_lr_ratio(clock.samples_consumed,c['samples'],'cosine')
    for group in optimizer.param_groups:group['lr']=lr
    optimizer.zero_grad(set_to_none=True);total,family,_=calculate(samples);total.backward();norm=torch.nn.utils.clip_grad_norm_(params,clip,error_if_nonfinite=True);optimizer.step()
    clock.advance(len(samples));rng.bit_generator.state=consumed_rng;clipped+=int(float(norm)>clip);window_updates+=1
    for name,value in family.items():
     value_sum,n=window.get(name,(0.,0));window[name]=(value_sum+float(value.detach()),n+1)
    seconds=prior+time.monotonic()-started;row=dict(samples=clock.samples_consumed,updates=clock.optimizer_updates,total=float(total.detach()),preclip_norm=float(norm),lr=lr,seconds=seconds);writer.writerow(row);history.log(row)
    if clock.optimizer_updates%1000==0:
     deliver([dict(run=c['run'],kind='TRAIN_1000_updates',samples=clock.samples_consumed,updates=clock.optimizer_updates,family=n,loss=s/num,clipped_fraction=clipped/clock.optimizer_updates,seconds=seconds) for n,(s,num) in window.items()]);window={};window_updates=0
     if clipped/clock.optimizer_updates>.2 and not clip_reported:
      print(json.dumps(dict(run=c['run'],clipped_fraction=clipped/clock.optimizer_updates,clip_unchanged=clip)),flush=True);clip_reported=True
    if clock.samples_consumed%500000==0:
     values=validate();deliver([dict(run=c['run'],kind='VAL_fixed2000',samples=clock.samples_consumed,updates=clock.optimizer_updates,family=n,loss=v,clipped_fraction=clipped/clock.optimizer_updates,seconds=prior+time.monotonic()-started) for n,v in values.items()])
    final=clock.samples_consumed==c['samples'];milestone=clock.samples_consumed%500000==0 or final
    if milestone:
     payload=dict(model=model.state_dict(),optimizer=optimizer.state_dict(),configuration=c,architecture=architecture,clock=clock.state_dict(),rng=rng.bit_generator.state,torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state(),elapsed_seconds=prior+time.monotonic()-started,family_window=window,family_window_updates=window_updates,clipped_updates=clipped,total_window=history.window)
     destination=output/('samples_'+str(clock.samples_consumed)+'.pt');save_checkpoint(payload,destination)
    if clock.optimizer_updates%100==0:print(json.dumps(row),flush=True)
  if window:deliver([dict(run=c['run'],kind='TRAIN_final_partial_window',samples=clock.samples_consumed,updates=clock.optimizer_updates,family=n,loss=s/num,clipped_fraction=clipped/clock.optimizer_updates,seconds=prior+time.monotonic()-started) for n,(s,num) in window.items()])
  summary=dict(status='TRAINING_COMPLETE_EVALUATION_PENDING',run=c['run'],samples=clock.samples_consumed,updates=clock.optimizer_updates,actual_samples=clock.samples_consumed-initial_samples,seconds=prior+time.monotonic()-started,clipped_fraction=clipped/clock.optimizer_updates,clip=clip,batch_size=c['batch_size'],microbatch_size=c['microbatch_size'],GPU_peak_bytes=torch.cuda.max_memory_allocated())
  (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');success=True;return summary
 finally:history.close(success);data.close();validation.close()
