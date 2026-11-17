"""H6: PMA chemical enrichment, requested attention entropy and query contributions."""
import argparse,collections,fcntl,hashlib,json,math,os,sys
import numpy as np
import torch
from h_resources import REPO,R,CONTROL,guard,load,save,watchdog
sys.path.insert(0,str(REPO/'tools/p_recipe'))
from diagnose import validation_indices
from checkpoint_paths import evaluation_checkpoint
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset
from phychem_mfm.phase1.v31_loader import collate_samples
from phychem_mfm.phase1.v2_s_training import s_model
from phychem_mfm.model.v3_latent import MolecularLatent,LatentSpec
from torch_geometric.utils import to_dense_batch


def chemical_categories(sample,factory):
 from rdkit import Chem
 from rdkit.Chem import rdDetermineBonds
 z=np.asarray(sample['Z']);pos=sample['pos'];raw=None
 for key in ('P.pm7_B.r68.value','P.pm7_B.r64.value'):
  t=sample['targets'].get(key)
  if t is not None and np.asarray(t.valid).all():raw=float(np.asarray(t.raw,np.float64).sum());break
 if raw is None:raise ValueError('D6 total charge unavailable')
 charge=int(round(raw));mol=Chem.RWMol()
 for element in z:mol.AddAtom(Chem.Atom(int(element)))
 mol=mol.GetMol();conformer=Chem.Conformer(len(z))
 for i,p in enumerate(pos):conformer.SetAtomPosition(i,[float(v) for v in p])
 mol.AddConformer(conformer);rdDetermineBonds.DetermineBonds(mol,charge=charge)
 if [a.GetAtomicNum() for a in mol.GetAtoms()]!=z.tolist():raise ValueError('D6 atom order differs after reconstruction')
 categories={}
 def add(key,indices):
  mask=categories.setdefault(key,np.zeros(len(z),bool));mask[list(indices)]=True
 for a in mol.GetAtoms():
  i=a.GetIdx();add(a.GetSymbol()+'_'+str(a.GetHybridization()),[i])
  if a.GetIsAromatic():add('Aromatic_atom',[i])
  if a.IsInRing():add('Ring',[i])
 for feat in factory.GetFeaturesForMol(mol):
  if feat.GetFamily() in ('Donor','Acceptor','PosIonizable','NegIonizable','Aromatic','Hydrophobe'):add(feat.GetFamily(),feat.GetAtomIds())
 return categories,charge


def attention_weights(module,query,key,value,key_mask=None):
 b,n,_=query.shape;head=module.width//module.heads
 q=module.q(query).reshape(b,n,module.heads,head).transpose(1,2)
 k=module.k(key).reshape(b,-1,module.heads,head).transpose(1,2)
 logits=(q@k.transpose(-1,-2))/math.sqrt(head)
 if key_mask is not None:logits=logits.masked_fill(~key_mask[:,None,None,:],float('-inf'))
 return torch.softmax(logits,dim=-1)


def enrichment_statistics(rows,repeats=1000):
 categories=sorted({c for row in rows for c in row['enrichments']});m=len(rows);values=np.zeros((m,8,len(categories)));present=np.zeros((m,len(categories)));heads=np.zeros((8,8,len(categories)));head_counts=np.zeros(len(categories));entropy=[]
 for i,row in enumerate(rows):
  entropy.append(row['entropy'])
  for j,c in enumerate(categories):
   if c in row['enrichments']:
    present[i,j]=1;values[i,:,j]=row['enrichments'][c];heads[:,:,j]+=row['head_enrichments'][c];head_counts[j]+=1
 rng=np.random.default_rng(20261025);weights=np.vstack([np.ones(m),np.array([np.bincount(rng.integers(0,m,m),minlength=m) for _ in range(repeats)])]);den=weights@present
 numerator=(weights@values.reshape(m,-1)).reshape(repeats+1,8,len(categories));ratio=np.divide(numerator,den[:,None,:],out=np.full_like(numerator,np.nan),where=den[:,None,:]>0)
 out=[]
 for q in range(8):
  for j,c in enumerate(categories):
   draws=ratio[1:,q,j];draws=draws[np.isfinite(draws)];out.append(dict(query=q,category=c,molecules=int(present[:,j].sum()),enrichment=float(ratio[0,q,j]),ci95=np.quantile(draws,[.025,.975]).tolist() if len(draws) else None))
 ent=np.asarray(entropy);medians=np.median(ent,axis=0);qualifying=sorted({r['query'] for r in out if r['enrichment']>=2 and r['ci95'] and r['ci95'][0]>1});global_median=float(np.median(ent))
 verdict='SUPPORT' if len(qualifying)>=4 and bool((medians<.9).all()) else 'NOT_SUPPORT' if global_median>=.95 else 'PARTIAL_SUPPORT'
 return dict(categories=categories,enrichments=out,head_mean_enrichments=np.divide(heads,head_counts[None,None,:],out=np.zeros_like(heads),where=head_counts[None,None,:]>0).tolist(),entropy_query_medians=medians.tolist(),entropy_global_median=global_median,qualifying_queries=qualifying,verdict=verdict,bootstrap=dict(repetitions=repeats,seed=20261025,unit='molecule',ci='percentile95'))


def prepare_chemistry(c):
 """Producer-only one-pass reconstruction/alignment, cached for the GPU step."""
 path=CONTROL/'H6_chemistry.json'
 payload=load(path) if path.exists() else dict(complete=False,molecules={})
 if payload.get('complete'):
  print('H6_CHEMISTRY_ALREADY_COMPLETE',len(payload['molecules']),flush=True);return
 from rdkit import RDConfig
 from rdkit.Chem import ChemicalFeatures
 import pathlib
 watchdog();factory=ChemicalFeatures.BuildFeatureFactory(str(pathlib.Path(RDConfig.RDDataDir)/'BaseFeatures.fdef'))
 indices=validation_indices();data=PRecipeDataset(c['root'],split='FULL',training_view=c['training_view'],normalizations=load(c['normalizations']),label_parameters=c['label_parameters'],source='PM7',k=10,molecule_indices=indices)
 for i,mi in enumerate(indices):
  key=str(int(mi))
  if key in payload['molecules']:continue
  sample=data.read(int(mi),int(data.choices(int(mi))[0]))
  try:
   categories,charge=chemical_categories(sample,factory)
   payload['molecules'][key]=dict(charge=charge,categories={name:np.flatnonzero(mask).tolist() for name,mask in categories.items()})
  except Exception as e:payload['molecules'][key]=dict(error=type(e).__name__+': '+str(e).split('\n')[0])
  if i%100==0:
   guard();pending=path.with_suffix('.next.json');save(pending,payload);pending.replace(path);print('H6_CHEMISTRY',i,len(indices),flush=True)
 data.close();payload['complete']=True;payload['requested_molecules']=len(indices);payload['retained_molecules']=sum('error' not in v for v in payload['molecules'].values());payload['excluded_molecules']=len(indices)-payload['retained_molecules'];payload['charge_source']='rounded sum of complete original neutral PM7 net atomic charges'
 guard();pending=path.with_suffix('.next.json');save(pending,payload);pending.replace(path)
 print('H6_CHEMISTRY_COMPLETE',payload['retained_molecules'],payload['excluded_molecules'],flush=True)

def main():
 from rdkit import RDConfig
 from rdkit.Chem import ChemicalFeatures
 import pathlib,subprocess
 p=argparse.ArgumentParser();p.add_argument('--prepare-chemistry',action='store_true');args=p.parse_args()
 if args.prepare_chemistry:
  torch.set_num_threads(1);prepare_chemistry(load(REPO/'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/B3.json'));return
 watchdog();torch.set_num_threads(4);torch.set_float32_matmul_precision('highest');torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 gpu=os.environ['CUDA_VISIBLE_DEVICES'].split(',')[0];used,total=map(float,subprocess.check_output(['nvidia-smi','--id='+gpu,'--query-gpu=memory.used,memory.total','--format=csv,noheader,nounits'],text=True).strip().split(','))
 if used/total>.3:raise RuntimeError('GPU admission changed')
 lock=(R/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 c=load(REPO/'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/B3.json');checkpoint=evaluation_checkpoint(c,3000000);payload=torch.load(checkpoint,map_location='cpu',weights_only=True);state=payload['model'];model,_=s_model(c['distance_bias'],c['views']);model.load_state_dict({k.removeprefix('structural.'):v for k,v in state.items() if k.startswith('structural.')});encoder=model.encoder.cuda().eval()
 pma=MolecularLatent(LatentSpec(kind='pma',n_ref=53.64145,write_back=False,reconstruction=False));pma.load_state_dict({k.removeprefix('pd.p_recipe_pma.'):v for k,v in state.items() if k.startswith('pd.p_recipe_pma.')});pma=pma.cuda().eval()
 observed=[]
 def capture(module,args):observed.append(attention_weights(module,*args).detach().cpu().double().numpy())
 hook=pma.layers[0].read.register_forward_pre_hook(capture)
 data=PRecipeDataset(c['root'],split='FULL',training_view=c['training_view'],normalizations=load(c['normalizations']),label_parameters=c['label_parameters'],source='PM7',k=10,molecule_indices=validation_indices());factory=ChemicalFeatures.BuildFeatureFactory(str(pathlib.Path(RDConfig.RDDataDir)/'BaseFeatures.fdef'))
 chemistry_path=CONTROL/'H6_chemistry.json';chemistry=load(chemistry_path) if chemistry_path.exists() else None
 if chemistry is not None and not chemistry.get('complete'):raise RuntimeError('H6 chemistry producer has not completed')
 rows=[];failures=collections.Counter();latent=[];latent_all=[]
 with torch.no_grad():
  for start in range(0,len(data.indices),32):
   samples=[data.read(int(mi),int(data.choices(int(mi))[0])) for mi in data.indices[start:start+32]];b=collate_samples(samples,device='cuda');h=encoder.encode_atoms(b);dense,mask=to_dense_batch(h,b.batch);z=pma.finish(dense,mask).cpu().double().numpy();weights=observed.pop();latent_all.extend(z.tolist())
   for j,sample in enumerate(samples):
    if chemistry is not None:
     cached=chemistry['molecules'][str(int(sample['molecule_index']))]
     if 'error' in cached:failures[cached['error']]+=1;continue
     charge=cached['charge'];categories={}
     for name,indices in cached['categories'].items():
      v=np.zeros(len(sample['Z']),bool);v[indices]=True;categories[name]=v
    else:
     try:categories,charge=chemical_categories(sample,factory)
     except Exception as e:failures[type(e).__name__+': '+str(e).split('\n')[0]]+=1;continue
    n=len(sample['Z']);a=weights[j,:,:,:n];mean=a.mean(0);entropy=-(mean*np.log(np.maximum(mean,1e-300))).sum(-1)/math.log(n) if n>1 else np.zeros(8)
    rows.append(dict(molecule_index=int(sample['molecule_index']),charge=charge,entropy=entropy.tolist(),enrichments={c:(mean[:,v].mean(-1)*n).tolist() for c,v in categories.items()},head_enrichments={c:(a[:,:,v].mean(-1)*n) for c,v in categories.items()}));latent.append(z[j,:512].reshape(8,64))
   guard();print('H6_FORWARD',start,len(data.indices),'retained',len(rows),flush=True)
 data.close();hook.remove();stats=enrichment_statistics(rows)
 # Requested first512 molecular-z query blocks, with the existing linear P heads.
 std=np.std(np.asarray(latent_all)[:,:512].reshape(-1,8,64),axis=0);contributions=[]
 metadata={v['field_key']:v for cols in data.schema['columns'].values() for v in cols}
 for field in data.view.fields:
  description=json.dumps(metadata.get(field.get('source_field',field['name']),{})).lower()
  if field['group']!='P' or field['level'] not in ('molecule','graph') or not any(t in description for t in ('frontier','homo','lumo','ionization','electron_affinity')):continue
  key='f_'+hashlib.sha256(field['name'].encode()).hexdigest()[:24];weight=state.get('pd.heads.field_heads.'+key+'.weight')
  if weight is None or weight.shape[-1]!=577:continue
  w=weight.detach().cpu().double().numpy()[:,:512].reshape(-1,8,64);importance=np.linalg.norm(w,axis=(0,2))*np.linalg.norm(std,axis=1);q=int(np.argmax(importance));enrich={r['category']:r for r in stats['enrichments'] if r['query']==q and r['category'] in ('Donor','Acceptor','Aromatic')};contributions.append(dict(field=field['name'],query_importance=importance.tolist(),largest_query=q,enrichments=enrich))
 stats.update(chemistry_cache=str(chemistry_path) if chemistry is not None else None,status='COMPLETE',requested_molecules=5000,retained_molecules=len(rows),excluded_molecules=sum(failures.values()),exclusion_reasons=dict(failures),checkpoint=str(checkpoint),query_contributions=contributions,charge_source='rounded sum of complete D6 original neutral PM7 net atomic charges; no labels changed',optional_28_SMARTS='not loaded; no dependency on pending data-line delivery')
 save(REPO/'results/p_heads/H/H6_attention.json',stats)
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 heat=np.array([[next(r['enrichment'] for r in stats['enrichments'] if r['query']==q and r['category']==c) for c in stats['categories']] for q in range(8)])
 fig,ax=plt.subplots(figsize=(max(10,len(stats['categories'])*.24),4));im=ax.imshow(heat,aspect='auto',vmin=0,vmax=max(2,float(np.max(heat))));ax.set_yticks(range(8),[str(q) for q in range(8)]);ax.set_xticks(range(len(stats['categories'])),stats['categories'],rotation=90);ax.set_ylabel('PMA query');fig.colorbar(im,ax=ax,label='Enrichment vs uniform atom weight');fig.tight_layout();guard();fig.savefig(REPO/'results/p_heads/H/H6_attention.png',dpi=180);plt.close(fig)
 lines=['# H6：PMA 注意力的化学落点','','沿用 H1 的5000个VAL分子，每分子取首允许构象。读取B3 PMA第一次query-to-atom交叉注意力；主分析平均8个头，逐头均值附在JSON。RDKit DetermineBonds以D6原子元素、坐标、原始PM7完整电荷和的最近整数重建，逐原子核对元素顺序；重建和唯一元素序列核对可先由1CPU生产步骤缓存，GPU步骤只读已完成缓存，不重复重建/核对；失败分子排除并计数。BaseFeatures.fdef类别与元素×杂化、芳香和环类别同时报告。','','类别富集为类别原子平均注意力除以1/N；先逐分子计算，再对出现该类别的分子取均值，1000次分子bootstrap给95%百分位区间。熵用H/logN归一化。支持要求至少4个query各有富集≥2且CI下界>1的类别，并且8个query各自熵中位数都<0.9；总熵中位数≥0.95为不支持，其余部分支持。','',f'保留{len(rows)}/5000分子，排除{sum(failures.values())}；判定：{stats["verdict"]}。',f'各query熵中位数：{stats["entropy_query_medians"]}；合格query：{stats["qualifying_queries"]}。','','![Query类别富集](../../results/p_heads/H/H6_attention.png)','','frontier/IP-EA线性头按64维query块权重范数乘该块标准差范数，输出最大贡献query及Donor/Acceptor/Aromatic富集，详见JSON。该项仅描述。','','局限：重建失败会改变保留分子分布；注意力富集不证明因果贡献，类别同时检验未做额外多重比较校正，严格按预注册规则判定。28类SMARTS未接入，不等待交付。']
 guard();(REPO/'docs/p_heads/H6_ATTENTION.md').write_text('\n'.join(lines)+'\n');print('H6_COMPLETE',stats['verdict'],flush=True)

if __name__=='__main__':main()
