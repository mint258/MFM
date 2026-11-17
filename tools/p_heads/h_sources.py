"""H2-H4: feature-only wrappers around frozen mainline R1/R3 and existing R2."""
from dataclasses import replace
import argparse,fcntl,json,os,pathlib,sys
import numpy as np
import torch
from h_resources import REPO,CONTROL,R,guard,load,save,watchdog
sys.path.insert(0,str(REPO/'tools/p_recipe'))
import evaluate as E
from checkpoint_paths import evaluation_checkpoint
from phychem_mfm.phase1.v2_s_training import s_model
from phychem_mfm.phase1.v31_loader import MFM4Dataset,collate_samples
from phychem_mfm.model.v3_latent import MolecularLatent,LatentSpec
from torch_geometric.data import Batch,Data
from torch_geometric.utils import to_dense_batch
from diagnose import validation_indices


def whiten_table(moments):
 count=sum(v['count'] for v in moments.values());s=sum(np.asarray(v['sum']) for v in moments.values());q=sum(np.asarray(v['square']) for v in moments.values())
 global_std=np.sqrt(np.maximum(q/count-(s/count)**2,0.));out={}
 for z,v in moments.items():
  if v['count']<50:continue
  mean=np.asarray(v['sum'])/v['count'];std=np.sqrt(np.maximum(np.asarray(v['square'])/v['count']-mean**2,0.))
  std=np.maximum(std,1e-6*global_std)
  # Exactly constant global dimensions have no dispersion; leave their scale1.
  std=np.where(std>0,std,1.);out[int(z)]=(mean,std)
 return out


def fit_whitening(name,encoder,c):
 path=CONTROL/('H3_whitening_moments_'+name+'.json')
 if path.exists():return whiten_table(load(path))
 data=MFM4Dataset(c['root'],split='FULL',geometry_only=True,k=10,molecule_indices=validation_indices());moments={}
 with torch.no_grad():
  for start in range(0,len(data.indices),32):
   samples=[data.read(int(mi),int(data.choices(int(mi))[0])) for mi in data.indices[start:start+32]];b=collate_samples(samples,device='cuda');h=encoder.encode_atoms(b).cpu().double().numpy();z=np.concatenate([s['Z'] for s in samples])
   for element in np.unique(z):
    v=h[z==element];state=moments.setdefault(str(element),dict(count=0,sum=np.zeros(512),square=np.zeros(512)));state['count']+=len(v);state['sum']+=v.sum(0);state['square']+=np.square(v).sum(0)
   guard()
 data.close();moments={z:{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in state.items()} for z,state in moments.items()}
 save(path,moments);return whiten_table(moments)


def feature_producer(c,dataset,view):
 checkpoint=torch.load(c['checkpoint'],map_location='cpu',weights_only=True);cfg=checkpoint['configuration'];model,_=s_model(cfg['distance_bias'],cfg['views']);state=checkpoint['model']
 state={k.removeprefix('structural.'):v for k,v in state.items() if k.startswith('structural.')} if any(k.startswith('structural.') for k in state) else state
 model.load_state_dict(state);encoder=model.encoder.cuda().eval();mode=c['h_mode'];pma=None
 if mode in ('z','concat'):
  pma=MolecularLatent(LatentSpec(kind='pma',n_ref=53.64145,write_back=False,reconstruction=False))
  pma.load_state_dict({k.removeprefix('pd.p_recipe_pma.'):v for k,v in checkpoint['model'].items() if k.startswith('pd.p_recipe_pma.')});pma=pma.cuda().eval()
 white=fit_whitening(c['h_condition'],encoder,cfg) if mode=='whiten' else None
 members=[(i,view.get(i,role=role)) for role in ('train','train_inner_validation') for i in view.view(role)];members=[(i,s) for i,s in members if s.geometry_ready]
 fit=set(view.view('train'));records=[];sizes=[];vectors={};unwhitened=0
 with torch.no_grad():
  for start in range(0,len(members),32):
   selected=members[start:start+32];b=Batch.from_data_list([Data(x=s.x.reshape(-1,1),pos=s.pos) for _,s in selected]).cuda()
   h,layers=encoder.encode_atoms(b,return_intermediates=True)
   if mode in ('3','4','5'):h=layers[int(mode)-1]
   elif mode=='mean':h=torch.stack([layers[2],layers[3],layers[4],h]).mean(0)
   if pma is not None:
    dense,mask=to_dense_batch(h,b.batch);z=pma.finish(dense,mask).detach().cpu().float()
   h=h.detach().cpu().float();offset=0
   for j,(index,sample) in enumerate(selected):
    n=len(sample.x);v=h[offset:offset+n].clone()
    if white is not None:
     for element in torch.unique(sample.x+1).tolist():
      mask=(sample.x.reshape(-1)+1)==element
      if int(element) in white:
       mean,std=white[int(element)];v[mask]=(v[mask]-v.new_tensor(mean))/v.new_tensor(std)
      else:unwhitened+=int(mask.sum())
    if pma is not None:vectors[index]=z[j] if mode=='z' else torch.cat((v.mean(0),z[j]))
    records.append(dict(molecule_uid=sample.member_uid,member_index=index,h0=v,source_atom_ids=sample.source_atom_ids))
    if index in fit:sizes.append(n)
    offset+=n
   if start%1024==0:guard();print('H_SOURCE_FEATURES',c['h_condition'],mode,dataset,start,len(members),flush=True)
 # H4 concatenated blocks are each standardized using downstream TRAIN only.
 if mode=='concat':
  values=torch.stack([vectors[i] for i in vectors if i in fit]).double();mean=values.mean(0);std=values.std(0,unbiased=False);std=torch.where(std>0,std,torch.ones_like(std))
  vectors={i:((v.double()-mean)/std).float() for i,v in vectors.items()}
 c['_vectors_uid']={r['molecule_uid']:vectors[r['member_index']] for r in records} if vectors else {};c['_vectors']=vectors;c.setdefault('_unwhitened_atoms',{})[dataset]=unwhitened
 del model,encoder,checkpoint,pma,state;torch.cuda.empty_cache()
 return dict(records=records,n_ref=sum(sizes)/len(sizes))


def molecular_run(c):
 from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec,task_rows,ridge_probe,error
 from phychem_mfm.phase1.v3_dev_evaluation_v2 import _pack
 from phychem_mfm.phase1.v3_downstream_targets import atomization_rows,ATOMIZATION_TASK_ID
 output=pathlib.Path(c['output']);output.mkdir(parents=True,exist_ok=True)
 panel=load(REPO/'configs/dev_panel_v3.json');tasks=[replace(TaskSpec(**{k:t[k] for k in ('task_id','dataset_id','field','output_level','error_metric','pooling')}),pooling='mean') for t in panel['tasks']]
 store=E.TrainOnlyPackedStore(c['store'],verify_digests=False);history=E.History(output/'probe_history.jsonl');files={};details={};stds={}
 for dataset in ('expansionrx','cyp_isoform','qm9'):
  view=E.GroupedTrainingView(store,dataset,'official' if dataset=='expansionrx' else '0',store.group_map);payload=feature_producer(c,dataset,view);cached=E.cached_rows(payload);vectors=c.pop('_vectors');by_uid=c.pop('_vectors_uid')
  for task in [t for t in tasks if t.dataset_id==dataset]:
   rows=atomization_rows if task.task_id==ATOMIZATION_TASK_ID else task_rows
   train=rows(view,cached,task,role='train');val=rows(view,cached,task,role='train_inner_validation')
   if task.output_level=='graph':
    train=tuple(replace(r,graph_features=by_uid[r.source_member_uid]) for r in train)
    val=tuple(replace(r,graph_features=by_uid[r.source_member_uid]) for r in val)
   else:
    train=tuple(replace(r,h0=by_uid[r.source_member_uid].expand(len(r.h0),-1).clone()) for r in train)
    val=tuple(replace(r,h0=by_uid[r.source_member_uid].expand(len(r.h0),-1).clone()) for r in val)
   labels=torch.cat([r.targets[r.supervision_mask&r.candidate_mask].double() for r in train]);stds[task.task_id]=float(labels.std(unbiased=False))
   for readout in ('R1','R2'):
    key=task.task_id+'/'+readout;path=output/(task.task_id.replace('.','_')+'__'+readout+'.pt');history.cell=key
    if not path.exists():
     prediction,detail=(ridge_probe(train,val,task,relative_std_floor=True) if readout=='R1' else E.run_probe(train,val,task,readout='R2',n_ref=payload['n_ref'],seed=0,device='cuda',tracker=history,relative_std_floor=True,internal_epoch_selection=True))
     guard();torch.save(dict(prediction=_pack(prediction),detail=detail),path)
    p=torch.load(path,map_location='cpu',weights_only=True);details[key]={k:v for k,v in p['detail'].items() if k!='state_dict'};files[key]=str(path)
    print('H4_CELL',key,error(E._unpack(p['prediction'])),flush=True)
 manifest=dict(run=c['run'],files=files,details=details,label_stds=stds,stage=0,round=0,arm=c['run'],samples=3000000,protocol='existing_R1_R2_direct_graph_features',source_roles=['train','train_inner_validation'])
 save(output/'predictions.json',manifest);return manifest


def molecule_scores(c):
 from phychem_mfm.phase1.v3_dev_evaluation import compare_panel,error
 reference=load('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/reference_C1_0/predictions.json')
 candidate=load(pathlib.Path(c['output'])/'predictions.json');scores={}
 for readout in ('R1','R2'):
  actual={};random={};included=[]
  for key,path in candidate['files'].items():
   task,name=key.rsplit('/',1)
   if name!=readout:continue
   a=E._unpack(torch.load(path,map_location='cpu',weights_only=True)['prediction'])
   b=E._unpack(torch.load(reference['files'][task+'/R1'],map_location='cpu',weights_only=True)['prediction'])
   e=error(b)
   if task in E.PRIMARY_TASK_IDS and e>=.05*candidate['label_stds'][task]:actual[task]=a;random[task]=b;included.append(task)
  scores[readout]=compare_panel(actual,random,architecture_sha256='C1-0-reference',reference_architecture_sha256='C1-0-reference',retain_paired_samples=True,retain_task_samples=True);scores[readout]['included_tasks']=included
 save(pathlib.Path(c['output'])/'scores.json',scores);return scores

def main():
 p=argparse.ArgumentParser();p.add_argument('--condition',choices=['B3','M1'],required=True);p.add_argument('--mode',choices=['3','4','5','mean','whiten','z','concat'],required=True);a=p.parse_args()
 if a.mode in ('z','concat') and a.condition!='B3':raise ValueError('H4 is B3 only')
 watchdog();torch.set_num_threads(4);torch.set_float32_matmul_precision('highest');torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 gpu=os.environ['CUDA_VISIBLE_DEVICES'].split(',')[0]
 import subprocess
 used,total=map(float,subprocess.check_output(['nvidia-smi','--id='+gpu,'--query-gpu=memory.used,memory.total','--format=csv,noheader,nounits'],text=True).strip().split(','))
 if used/total>.3:raise RuntimeError('GPU admission changed')
 lock=(R/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 c=load(REPO/('configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/'+a.condition+'.json'));c.update(checkpoint=str(evaluation_checkpoint(c,3000000)),h_condition=a.condition,h_mode=a.mode,run='H_'+a.condition+'_'+a.mode,output=str(CONTROL/'sources'/a.condition/a.mode),features=str(CONTROL/'unused_features'),persist_features=False,store=str(R/'runs/model_v3_20261025/selected_train_store_4520421/native_store/training_store.json'))
 E.produce_missing_features=feature_producer
 if a.mode in ('z','concat'):m=molecular_run(c)
 else:m=E.run(c)
 if a.mode in ('z','concat'):
  scores=molecule_scores(c);readouts=('R1','R2')
 else:
  scores=E.score(pathlib.Path(c['output'])/'predictions.json','/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/reference_C1_0/predictions.json',CONTROL/'H_sources_scores.csv');readouts=('R1','R3')
 base=load(pathlib.Path(load(REPO/('configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/'+a.condition+'.json'))['output'])/'readout/scores.json');delta={}
 for r in readouts:
  baseline=base['R1' if r=='R2' else r]
  for key in ('groups','seed','samples','confidence'):
   if scores[r]['paired_bootstrap'].get(key)!=baseline['paired_bootstrap'].get(key):raise ValueError('Paired bootstrap membership differs')
  d=np.asarray(scores[r]['paired_bootstrap']['values'])-np.asarray(baseline['paired_bootstrap']['values']);ci=np.quantile(d,[.025,.975]).tolist();effect=scores[r]['mean_normalized_improvement']-baseline['mean_normalized_improvement'];threshold=max(.02,baseline['mean_normalized_improvement']*.05)
  delta[r]=dict(delta=effect,ci95=ci,verdict='BETTER' if ci[0]>0 and effect>=threshold else 'WORSE' if ci[1]<0 else 'TIE',baseline_readout='R1' if r=='R2' else r)
 save(REPO/('results/p_heads/H/'+c['run']+'.json'),dict(scores=scores,deltas=delta,unwhitened_atoms=c.get('_unwhitened_atoms',{})))
 print('H_SOURCE_COMPLETE',c['run'],flush=True)

if __name__=='__main__':main()
