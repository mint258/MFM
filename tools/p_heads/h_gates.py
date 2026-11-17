"""H7: describe the actual scalar sigmoid gate shared by 64 sum channels."""
import argparse,fcntl,os,subprocess
import numpy as np
import torch
from h_resources import REPO,R,CONTROL,guard,load,save,watchdog


def gate_row(values,categories):
 g=np.asarray(values,np.float64).reshape(-1);n=len(g);mean=float(g.mean())
 return dict(atoms=n,sum=float(g.sum()),square=float(g@g),within=float(np.square(g-mean).sum()),undefined_gate_mass=mean<=0,enrichments={c:float(g[np.asarray(indices,int)].mean()/mean) for c,indices in categories.items() if len(indices) and mean>0})


def gate_statistics(rows,repeats=1000):
 categories=sorted({c for row in rows for c in row['enrichments']});m=len(rows)
 values=np.zeros((m,len(categories)));present=np.zeros_like(values)
 for i,row in enumerate(rows):
  for j,c in enumerate(categories):
   if c in row['enrichments']:values[i,j]=row['enrichments'][c];present[i,j]=1
 rng=np.random.default_rng(20261025)
 weights=np.vstack([np.ones(m),np.array([np.bincount(rng.integers(0,m,m),minlength=m) for _ in range(repeats)])])
 den=weights@present;num=weights@values
 ratios=np.divide(num,den,out=np.full_like(num,np.nan),where=den>0)
 enrichments=[]
 for j,c in enumerate(categories):
  draws=ratios[1:,j];draws=draws[np.isfinite(draws)]
  enrichments.append(dict(category=c,molecules=int(present[:,j].sum()),enrichment=float(ratios[0,j]),ci95=np.quantile(draws,[.025,.975]).tolist() if len(draws) else None))
 n=sum(r['atoms'] for r in rows);s=sum(r['sum'] for r in rows);q=sum(r['square'] for r in rows);within=sum(r['within'] for r in rows);total=max(0.,q-s*s/n)
 return dict(categories=categories,scalar_gate_enrichments=enrichments,shared_sum_dimensions=list(range(64)),dimension_gate_mapping='All 64 sum_project channels share scalar_gate_enrichments; computed once, no independent sigmoid per channel.',undefined_gate_mass_molecules=sum(r.get('undefined_gate_mass',False) for r in rows),distribution=dict(atoms=n,mean=s/n,std=float(np.sqrt(total/n)),within_molecule_atom_variance_fraction=within/total if total>0 else None,between_molecule_variance_fraction=(total-within)/total if total>0 else None,variance_reason=None if total>0 else 'constant gate: total variance is zero'),bootstrap=dict(repetitions=repeats,seed=20261025,unit='molecule',ci='percentile95'))


def scalar_gate(pma,dense):
 return torch.sigmoid(pma.sum_gate(pma.sum_norm(dense)))


def main():
 from h_sources import condition_configuration
 from checkpoint_paths import evaluation_checkpoint
 from diagnose import validation_indices
 from phychem_mfm.phase1.v31_loader import MFM4Dataset,collate_samples
 from phychem_mfm.phase1.v2_s_training import s_model
 from phychem_mfm.model.v3_latent import MolecularLatent,LatentSpec
 from torch_geometric.utils import to_dense_batch
 p=argparse.ArgumentParser();p.add_argument('--condition',choices=['B3','M2'],required=True);a=p.parse_args()
 watchdog();torch.set_num_threads(4);torch.set_float32_matmul_precision('highest');torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 gpu=os.environ['CUDA_VISIBLE_DEVICES'].split(',')[0]
 used,total=map(float,subprocess.check_output(['nvidia-smi','--id='+gpu,'--query-gpu=memory.used,memory.total','--format=csv,noheader,nounits'],text=True).strip().split(','))
 if used/total>.3:raise RuntimeError('GPU admission changed')
 lock=(R/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 chemistry_path=CONTROL/'H6_chemistry.json';chemistry=load(chemistry_path)
 if not chemistry.get('complete'):raise RuntimeError('Requires completed H6 chemistry cache; never reconstruct here')
 c=condition_configuration(a.condition);checkpoint=evaluation_checkpoint(c,3000000);payload=torch.load(checkpoint,map_location='cpu',weights_only=True);state=payload['model'];model,_=s_model(c['distance_bias'],c['views'])
 model.load_state_dict({k.removeprefix('structural.'):v for k,v in state.items() if k.startswith('structural.')});encoder=model.encoder.cuda().eval()
 pma=MolecularLatent(LatentSpec(kind='pma',n_ref=53.64145,write_back=False,reconstruction=False));pma.load_state_dict({k.removeprefix('pd.p_recipe_pma.'):v for k,v in state.items() if k.startswith('pd.p_recipe_pma.')});pma=pma.cuda().eval()
 data=MFM4Dataset(c['root'],split='FULL',geometry_only=True,k=10,molecule_indices=validation_indices());rows=[];excluded={}
 with torch.no_grad():
  for start in range(0,len(data.indices),32):
   samples=[data.read(int(mi),int(data.choices(int(mi))[0])) for mi in data.indices[start:start+32]];b=collate_samples(samples,device='cuda');dense,mask=to_dense_batch(encoder.encode_atoms(b),b.batch);g=scalar_gate(pma,dense).cpu().double().numpy()
   for j,sample in enumerate(samples):
    mi=str(int(sample['molecule_index']));cached=chemistry['molecules'][mi]
    if 'error' in cached:excluded[mi]=cached['error'];continue
    row=gate_row(g[j,:len(sample['Z']),0],cached['categories']);row['molecule_index']=int(mi);rows.append(row)
   guard();print('H7_FORWARD',a.condition,start,len(data.indices),'retained',len(rows),flush=True)
 data.close();stats=gate_statistics(rows)
 stats.update(status='COMPLETE',condition=a.condition,checkpoint=str(checkpoint),chemistry_cache=str(chemistry_path),requested_molecules=5000,retained_molecules=len(rows),excluded_molecules=len(excluded),exclusion_reasons=excluded,gate_shape='one scalar per atom, broadcast to 64 projected sum channels',variance_definition='within=sum_m sum_i(g_mi-mean_m)^2; total=sum_m sum_i(g_mi-global_atom_mean)^2; fraction=within/total',descriptive_only=True)
 save(REPO/f'results/p_heads/H/H7_gates_{a.condition}.json',stats)
 # Per-dimension rows are a format mapping of the one shared gate statistic.
 lines=['# H7：'+a.condition+'门控求和落点','','真实实现每原子只有一个sigmoid门，64维sum_project输出共享该门。仅统计此门，不改变模型，不分析门乘投影特征。复用H6完整化学缓存及同5000 VAL首允许构象，不重建或重新核对元素序列。','','逐分子令a_i=g_i/Σg，类别富集=N×类别内a_i均值；对出现类别的分子取平均。1000次MID bootstrap（seed20261025），95%百分位区间。全部结果仅描述，无判定。','','原始门均值/标准差以全体保留原子加权。跨原子方差占比为分子内平方和/全体原子总平方和；分子间占比是其余部分，常数门总方差为0时记NA。',f'保留{len(rows)}/5000分子；排除{len(excluded)}。','原始门分布见下表。','','64个输出维（0–63）共享下表的同一标量门富集，JSON提供64维索引映射，不重复进行64次统计。','','|类别|分子数|共享门富集|95%CI|','|---|---:|---:|---|']
 distribution_lines=['','|原始门分布指标|值|','|---|---:|']
 for key,value in stats['distribution'].items():
  formatted=f'{value:.6g}' if isinstance(value,(int,float)) else ('NA' if value is None else value)
  distribution_lines.append(f'|{key}|{formatted}|')
 location=lines.index('64个输出维（0–63）共享下表的同一标量门富集，JSON提供64维索引映射，不重复进行64次统计。');lines[location:location]=distribution_lines+['']
 for row in stats['scalar_gate_enrichments']:
  ci=row['ci95'];formatted=f'[{ci[0]:.6g}, {ci[1]:.6g}]' if ci else 'NA';lines.append(f'|{row["category"]}|{row["molecules"]}|{row["enrichment"]:.6g}|{formatted}|')
 lines+=['','局限：类别数目及稀有类别的分子数完整保留，未设额外过滤或多重比较判定；富集仅描述门值分配，不证明因果贡献。原子加权分布与按分子平均类别富集的权重不同，分别定义。']
 guard();(REPO/f'docs/p_heads/H7_GATES_{a.condition}.md').write_text('\n'.join(lines)+'\n');print('H7_COMPLETE',a.condition,flush=True)


if __name__=='__main__':main()
