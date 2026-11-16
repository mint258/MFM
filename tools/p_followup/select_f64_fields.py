"""B0: apply the frozen selection rule to original, already cached TRAIN pairs."""
import collections,csv,pickle,time
import numpy as np
from resources import REPO,CONTROL,OLD,guard,load,save

def main():
 started=time.monotonic();capacity=guard(force=True);rule=load(REPO/'configs/p_followup/B_field_selection_rule.json')
 panel=load(OLD/'panel.json')['TRAIN'];core={r['molecule_id'] for r in panel if r['core']}
 pairs=load(OLD/'pairs.json')['TRAIN']['conformer'];ids=load(OLD/'pilot_physical_ids.json')['TRAIN']
 fields=load(REPO.parent/'MFM_p_data_information/configs/p_data_information/fields.json')['fields'];names=[f['field_key'] for f in fields]
 candidates=[f for f in fields if f['level']=='molecule'];assert len(candidates)==43
 norms=load(OLD/'normalizations_TRAIN.json');pilot=np.load(OLD/'distances_TRAIN.npz')['conformer']
 with (OLD/'source_graph_scalars.pkl').open('rb') as stream:values=pickle.load(stream)['TRAIN']
 rows=[]
 for field in sorted(candidates,key=lambda f:f['field_key']):
  guard();name=field['field_key'];a=[];b=[];raw=[]
  for r in panel:
   if r['molecule_id'] in core:
    raw.extend(abs(v[name]) for v in values[r['molecule_id']].values() if v.get(name) is not None and np.isfinite(v[name]))
  for i,p in enumerate(pairs):
   if p['molecule_id'] not in core or not np.isfinite(pilot[i,names.index(name)]):continue
   mid=p['molecule_id'];x=values[mid][ids[mid][str(p['a'])]].get(name);y=values[mid][ids[mid][str(p['b'])]].get(name)
   if x is not None and y is not None and np.isfinite(x) and np.isfinite(y) and x!=y:a.append(x);b.append(y)
  a=np.asarray(a,np.float64);b=np.asarray(b,np.float64);delta=a-b
  # Quantize the stored endpoints once, then measure their difference in F64.
  rounded=a.astype(np.float32).astype(np.float64)-b.astype(np.float32).astype(np.float64)
  e=np.abs(rounded-delta);relative=e/np.abs(delta);scale=float(np.asarray(norms[name]['scale']).reshape(-1)[0]);n=len(delta)
  me=float(np.median(e)) if n else None;mr=float(np.median(relative)) if n else None;erased=int(np.count_nonzero(rounded==0));rate=erased/n if n else None
  selected=bool(n and ((mr>1e-4 and me/scale>1e-6) or rate>=.001))
  rows.append(dict(field=name,unit=field['unit'],median_abs_raw=float(np.median(raw)) if raw else None,nonzero_core_pairs=n,median_abs_delta=float(np.median(np.abs(delta))) if n else None,median_abs_error=me,median_relative_error=mr,D4_scale=scale,median_abs_error_over_scale=me/scale if me is not None else None,erased_pairs=erased,erasure_rate=rate,selected=selected))
 result=dict(status='COMPLETE',rule=rule,panel='existing TRAIN core',new_source_reads=0,source_nonzero_pair_units='Frozen physical conformer pairs; descriptive selection table uses pooled pairs as specified',subtraction='F32 stored endpoints promoted to F64 to isolate endpoint quantization',fields=rows,selected_fields=[r['field'] for r in rows if r['selected']],elapsed_seconds=time.monotonic()-started)
 save(REPO/'results/p_followup/B_field_selection.json',result)
 path=REPO/'results/p_followup/B_field_selection.csv'
 with path.open('w',newline='') as stream:w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 lines=['# B0：原F64缓存上的字段选择','','状态：COMPLETE。规则在任何新数值结果前提交；只消费既有冻结TRAIN核心对与原F64图标量缓存，新源读取0。','','每条源非零冻结构象对计算端点F32量化后的差值误差。按任务书用配对的中位误差/相对误差或归零比例选择；这里是数值存储误差，不是全域物理噪声界。D0只把这张表作为指定的数值误差下限。','','|字段|非零对|中位相对误差|中位误差/D4尺度|归零比例|入选|','|---|---:|---:|---:|---:|---|']
 for row in rows:lines.append('|'+ '|'.join(str(row[k]) for k in ['field','nonzero_core_pairs','median_relative_error','median_abs_error_over_scale','erasure_rate','selected'])+'|')
 lines+=['','入选：'+', '.join(result['selected_fields'])+'。','后续B1覆盖任务书指定的D6全split记录；B2开关默认关闭，C/D及主线均不启用sidecar。']
 guard();(REPO/'docs/p_followup/B0_FIELD_SELECTION.md').write_text('\n'.join(lines)+'\n')
 print('B0_COMPLETE',result['selected_fields'],flush=True)
if __name__=='__main__':main()