"""Conditional report with the already-published D4/A1 composition references."""
import collections
import numpy as np
from stage0_cohort import R,O,load,save
from stage3_information import statistics
B=R/'MFM_p_data_information'
def offline(role,panel,fields,graph,pairs,specs):
 counts={r['molecule_id']:collections.Counter(r['elements']) for r in panel};out={}
 for level in ['composition','isomer']:
  fs={};mode='median' if level=='isomer' else 'first'
  for f in fields:
   name=f['field_key'];spec=specs.get(name)
   if spec is None or f['level']!='molecule' or np.asarray(spec['scale']).size!=1:continue
   scale=float(np.asarray(spec['scale']).flat[0]);reference=spec.get('element_reference');offset={mid:float(reference.get('intercept',0))+sum(c.get(int(z),0)*coef for z,coef in zip(reference['basis'],reference['coefficients'])) if reference else 0. for mid,c in counts.items()};vals=[];refs=[];residuals=[];units=[]
   for i,pair in enumerate(pairs[level]):
    try:a,b=graph[pair['a']][name][mode],graph[pair['b']][name][mode]
    except KeyError:a,b=None,None
    delta=None if a is None or b is None else (a-b)-(offset[pair['a']]-offset[pair['b']])
    vals.append(abs(delta)/scale if delta is not None else np.nan);refs.append(abs(offset[pair['a']]-offset[pair['b']]));residuals.append(abs(delta) if delta is not None else np.nan);units.append(pair['formula_charge'] if level=='isomer' else str(i))
   if not np.isfinite(vals).any():continue
   s=statistics(vals,units);s['reference_component_median']=float(np.median(refs)) if refs else None;s['residual_raw_unit_median']=statistics(residuals,units)['median'];s['has_element_reference']=bool(reference);s['interpretation']='Existing mathematical affine transform; final actual FP32 rounding assessed separately in stage5';fs[name]=s
  out[level]=fs
 return out

def main():
 data=load(B/'results/p_data_information/conditional_information.json');fields=load(B/'configs/p_data_information/fields.json')['fields'];panels=load(O/'panel.json');pairs=load(O/'pairs.json');A1=load(B/'configs/p_recipe/label_parameters/PM7_A1.json')['normalizations'];D4all={};A1all={};lines=[];amp=[];mismatches=[]
 for role,panel in panels.items():
  graph=load(O/('graph_summaries_'+role+'.json'));D4=load(O/('normalizations_'+role+'.json'));effectiveA1=dict(D4,**A1);D4all[role]=offline(role,panel,fields,graph,pairs[role],D4);A1all[role]=offline(role,panel,fields,graph,pairs[role],effectiveA1)
  for r in panel:
   if sorted(collections.Counter(r['elements']).items())!=[tuple(x) for x in __import__('json').loads(r['formula_charge'])[0]]:mismatches.append(dict(role=role,molecule_id=r['molecule_id']))
  for level,fs in data['roles'][role].items():
   for name,s in fs.items():
    s['raw_median_over_D4_scale']=s['median']/s['scale'] if s['median'] is not None and s['scale'] is not None else None
    if level in ('composition_composition','isomer_isomer'):
     key=level.split('_')[0];correct=D4all[role][key].get(name)
     if correct is not None:s['median_D4_amplitude']=correct['median']
    s['resolution_classification']=dict(reliably_distinguished=dict(count=None,reason='No applicable calculation precision evidence'),only_above_print_or_storage_resolution=dict(count=None,reason='Source printing precision unresolved; FP32 inequality alone is insufficient'),not_resolved_as_a_physical_difference=dict(count=None,reason='Unknown calibration is not zero effect'),incomparable_pairs=s['candidate_pairs']-s['comparable_pairs'],equal_FP32_pairs=s['comparable_pairs']-s['nonzero_stored_differences'],different_FP32_pairs=s['nonzero_stored_differences'])
 for f in fields:
  name=f['field_key']
  if f['family']!='energy' or f['level']!='molecule':continue
  t=data['roles']['TRAIN'];a=t['composition_composition'][name];b=t['isomer_isomer'][name];c=t['conformer_core'][name]
  if all(x['median'] is None for x in [a,b,c]):continue
  fmt=lambda v:'UNKNOWN' if v is None else f'{v:.6g}'
  lines.append(f"|{name}|{f['unit']}|{fmt(a['median'])}|{fmt(b['median'])}|{fmt(c['median'])}|{fmt(a['median_D4_amplitude'])}|{fmt(c['median_D4_amplitude'])}|")
 data.update(D4_offline_graph_scalars=D4all,A1_offline_graph_scalars=A1all,A1_changed_fields=sorted(A1),formula_metadata_vs_M_mismatches=mismatches);save(B/'results/p_data_information/conditional_information.json',data)
 (B/'docs/p_data_information/03_CONDITIONAL_INFORMATION.md').write_text('''# 阶段3：控制组成后的条件差异\n\n状态：COMPLETE_AT_STORED_LABEL_LAYER；原计算可靠性仍未解决。\n\n按阶段1冻结配对比较原单位差异。构象对先按分子等权平均、异构对先按分子式组等权平均，再对独立单位等权。中位数/P10/P90与1000次分组bootstrap95%区间见conditional_information.json，seed20261025；核心/富集与TRAIN/VAL分报，区间只描述固定面板。\n\n|TRAIN能量字段|单位|跨组成中位差|同式异构中位差|核心构象中位差|当前D4跨组成幅度|当前D4构象幅度|\n|---|---|---:|---:|---:|---:|---:|\n'''+ '\n'.join(lines)+'''\n\n**原单位跨度不等于当前模型目标跨度。** 当前D4已对部分能量提供元素参考；跨组成必须先扣除两分子的不同参考，不能只把原差值除以尺度。这里逐项离线应用已有D4/A1，分别给组成参考分量、原单位残差和归一化幅度。A1未覆盖的字段沿用D4，不假设A1改了所有能量标签。相同组成/同分子的元素参考差为0，因此改变尺度只改变相对幅度，不产生新的标签信息。没有重拟合参数或改生产流程；实际FP32舍入另在阶段5检查。\n\n同式主差异为各分子有效构象样本中位数之差；外部graph_summaries保存首构象、有效数、min/max。单点范围0不证明无构象变化，样本中位数不当作热力学平均。异构差异不能全归因于连接关系。局部标量/pair按共同有效源位点计算RMS，pair按有向端点交集；局部最大差与元素细分见local_differences.json，不构造新pair。\n\n矢量的独立x/y/z存储先重组，再按实际几何proper Kabsch求L2差；原子矢量求对齐后局部RMS。带电原点敏感图矢量缺适用原点规则时保持未知；组件尺度不冒充共同矢量尺度。扰动标签使用pos_perturbed。不能对齐的字段保持未知，不把分量变化当物性变化。\n\n差异的最早可追溯层是pilot FP32。打印/计算误差未知，四级物理分辨类别按null和reason保留，不能把浮点数不同升级为可靠化学区分，也不能把未知归为零效应。没有统一化学显著阈值，不要求能量随RMSD单调。\n\n首次差值运行在第一个分子的分开存储矢量组件处退出；修正组装后复用缓存，没有重读该分子源标签或运行QM。所有失败日志保留。\n''')
 progress=load(B/'results/p_data_information/progress.json');progress['stage3']='COMPLETE_AT_STORED_LABEL_LAYER_WITH_UNRESOLVED_PRECISION';save(B/'results/p_data_information/progress.json',progress)
 print('\n'.join(lines),flush=True);print('FORMULA_MISMATCHES',len(mismatches),flush=True)
if __name__=='__main__':main()
