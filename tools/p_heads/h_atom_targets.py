"""H5: element-explained variance of the actual normalized atom targets."""
import collections,csv,json,sys,time
import numpy as np
from h_resources import REPO,CONTROL,R,guard,load,save,watchdog
sys.path.insert(0,str(REPO/'tools/p_recipe'))
from diagnose import validation_indices
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset


def explained(moments):
 counts=np.array([m[0] for m in moments.values()],np.float64)
 sums=np.array([m[1] for m in moments.values()],np.float64)
 squares=np.array([m[2] for m in moments.values()],np.float64)
 n=counts.sum();s=sums.sum();sq=squares.sum()
 total=sq-s*s/n if n else 0.
 between=(sums*sums/np.maximum(counts,1)).sum()-s*s/n if n else 0.
 return dict(atoms=int(n),elements=len(moments),total_variance=float(total/n) if n else None,element_explained_fraction=float(between/total) if total>0 else None,between_ss=float(between),total_ss=float(total))


def main():
 started=time.monotonic();watchdog()
 config=load(REPO/'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/B3.json')
 indices=validation_indices()
 data=PRecipeDataset(config['root'],split='FULL',training_view=config['training_view'],normalizations=load(config['normalizations']),label_parameters=config['label_parameters'],source='PM7',k=10,molecule_indices=indices)
 fields=[f for f in data.view.fields if f['group']=='P' and f['level']=='atom' and f.get('loss_enabled',True) and f.get('representation','scalar')!='vector' and data.schema.get('target_layout',{}).get(f.get('target_id'),{}).get('kind')!='vector']
 stats={f['name']:collections.defaultdict(lambda:np.zeros(3,np.float64)) for f in fields}
 for i,mi in enumerate(indices):
  sample=data.read(int(mi),int(data.choices(int(mi))[0]));z=sample['Z']
  for field in fields:
   target=sample['targets'][field['name']];value=np.asarray(target.values,np.float64).reshape(len(z),-1);valid=np.asarray(target.valid).reshape(value.shape)
   if value.shape[1]!=1:raise ValueError('H5 scalar selection contains multi-component target '+field['name'])
   for element in np.unique(z):
    y=value[(z==element),:];mask=valid[(z==element),:]&np.isfinite(y);y=y[mask]
    stats[field['name']][int(element)]+=np.array([len(y),y.sum(),np.square(y).sum()])
  if i%250==0:guard();print('H5',i,len(indices),flush=True)
 data.close();rows=[dict(field=f['name'],family=f['family'],**explained(stats[f['name']])) for f in fields]
 families=[]
 for family in sorted({r['family'] for r in rows}):
  chosen=[r for r in rows if r['family']==family];total=sum(r['total_ss'] for r in chosen)
  families.append(dict(family=family,fields=len(chosen),variance_weighted_explained_fraction=sum(r['between_ss'] for r in chosen)/total if total>0 else None))
 result=dict(status='COMPLETE',molecules=len(indices),conformer_policy='first allowed k10 conformer per frozen VAL molecule',normalizations=config['normalizations'],label_parameters=config['label_parameters'],fields=rows,families=families,seconds=time.monotonic()-started)
 save(REPO/'results/p_heads/H/H5_atom_targets.json',result)
 path=CONTROL/'H/H5_atom_targets.csv';guard();path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='') as stream:
  writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 lines=['# H5：原子目标的元素解释率','','方法：沿用工作 A 的固定 5000 个预训练 VAL 分子和首个允许构象；使用 B3 实际训练的 11-07 D4 routes 与 A1 参数，不拟合新标签变换。只统计有效且有限的原子标量值，逐字段累计逐元素计数、一阶矩和二阶矩。元素解释率为元素间平方和除以总平方和；家族汇总按总平方和加权。没有模型前向或编码器训练。','','该项为预注册描述性分析，不设置显著性判定、不执行额外扫描。零方差字段记为缺失。','','|字段|家族|有效原子|元素解释率|','|---|---|---:|---:|']
 for r in rows:lines.append(f"|{r['field']}|{r['family']}|{r['atoms']}|{r['element_explained_fraction']}|")
 lines+=['','|家族|字段数|方差加权解释率|','|---|---:|---:|']
 for r in families:lines.append(f"|{r['family']}|{r['fields']}|{r['variance_weighted_explained_fraction']}|")
 lines+=['','局限：元素解释率是标签统计相关，不能单独证明编码器塌缩的因果来源；该分析固定使用首允许构象，不代表额外构象加权。','',f'实际纳入 {len(fields)} 个标量字段，5000 个分子；运行耗时 {result["seconds"]:.1f} 秒。']
 guard();(REPO/'docs/p_heads/H5_ATOM_TARGETS.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(dict(status='COMPLETE',fields=len(fields),seconds=result['seconds'])),flush=True)

if __name__=='__main__':main()
