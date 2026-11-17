"""Render H2-H4 tables from completed producer JSONs, without reevaluation."""
import csv,re
from pathlib import Path
from h_resources import REPO,CONTROL,guard,load


def cyp_report(expected):
 """Format producer-emitted report-only errors; do not reload predictions."""
 completed={'H_'+c+'_'+m:(c,m) for c,m in expected if (REPO/f'results/p_heads/H/H_{c}_{m}.json').exists()}
 rows={};path=CONTROL/'H_sources_scores.csv'
 if path.exists():
  with path.open(newline='') as stream:
   for row in csv.DictReader(stream):
    if row['run'] in completed and row['task'].startswith('cyp.'):
     rows[(row['run'],row['task'],row['readout'])]=row['error']
 for condition,mode in ((c,m) for c in ('B3','M2') for m in ('z','concat')):
  run='H_'+condition+'_'+mode
  if run not in completed:continue
  for path in sorted(CONTROL.glob('H_'+condition+'_'+mode+'_*.log'),key=lambda p:p.stat().st_mtime,reverse=True):
   text=path.read_text()
   if 'H_SOURCE_COMPLETE '+run not in text:continue
   for line in text.splitlines():
    match=re.match(r'^H4_CELL\s+(cyp\.\S+)/(R1|R2)\s+([-+0-9.eE]+)\s*$',line)
    if match:rows[(run,match[1],match[2])]=match[3]
   break
 metrics={t['task_id']:t['error_metric'] for t in load(REPO/'configs/dev_panel_v3.json')['tasks']}
 lines=['','## CYP报告附表（不进入主分）','','直接引用已完成producer的原误差：H2/H3来自本线H_sources_scores.csv，H4来自已完成日志的H4_CELL行；不重读预测或重算误差。CYP不进入7任务均值或变体判定，以下error沿用原任务指标、越低越好。','','|checkpoint|变体|读出|任务|原指标|error|','|---|---|---|---|---|---:|']
 for c,m in expected:
  label='第'+m+'层' if m in ('3','4','5') else {'mean':'第3–6层等权平均','whiten':'按元素白化','z':'PMA z','concat':'[mean(H6), z]'}[m]
  run='H_'+c+'_'+m
  for task in sorted(t for t in metrics if t.startswith('cyp.')):
   for readout in ('R1','R2') if m in ('z','concat') else ('R1','R3'):
    value=rows.get((run,task,readout))
    if value is None:continue
    formatted=f'{float(value):.6g}' if value not in ('','None') else 'NA'
    lines.append(f'|{c}|{label}|{readout}|{task}|{metrics[task]}|{formatted}|')
 lines+=['','第6层CYP参照直接沿用[主线已交付分数表](../../results/p_recipe/scores.csv)中当前B3/M1运行的3M记录，不增加评价。']
 return lines

def main():
 expected=[(c,m) for c in ('B3','M1') for m in ('3','4','5','mean','whiten')]+[(c,m) for c in ('B3','M2') for m in ('z','concat')]
 lines=['# H2–H4：下游表示来源','','方法：使用主线冻结开发面板与完全相同的TrainOnlyPackedStore、GroupedTrainingView、task_rows/atomization_rows、ridge_probe和run_probe；不训练编码器，不读取TEST。第6层基线和分数直接引用已有3M checkpoint。层3/4/5取实际中间输出，层平均为第3–5中间输出和第6层out_norm输出等权平均。','','元素白化统计仅来自预训练固定5000 VAL分子的首允许构象，第6层逐元素逐维均值和标准差；元素原子数不足50保持原特征，标准差下限为该维全局标准差的1e-6。完全常数全局维度无可定义方差，去均值后以单位尺度保留零值，未产生新信号；下游不重新拟合白化统计。','','PMA的577维z从已预训练PMA模块读取，由512维query块、64维sigmoid门控求和项和1维logN组成。H6和T3只检验query→atom softmax通路，不能把其判定扩展成全部PMA加权机制。[mean(H6),z]的两个块在下游TRAIN上分别按维标准化，使用已有graph_features接口直接进入R1或现成R2（池化后MLP），不新写读出协议。CYP原子任务仅将同一分子向量广播至各原子作描述；其站点预测不含原子区分信息，不纳入主分或结论。','','统计：沿用主线7任务平均规范化改善分数，按同一分子组、种子和顺序的1000次配对bootstrap逐抽样相减，95%百分位区间。变体减同checkpoint第6层基线；H4的R1/R2均与该checkpoint现有R1比较，两个读出共用已交付R1参照误差进行归一化，保持与R1基线相同量尺。更优要求CI下界>0且Δ≥max(0.02,基线×5%)；CI上界<0为更差，其余持平。','','|checkpoint|变体|读出|分数|Δ|95%CI|判定|','|---|---|---|---:|---:|---|---|']
 # The taskbook explicitly requests direct reuse of existing layer6 scores.
 for name in ('B3','M1','M2'):
  config=load(REPO/('configs/p_recipe/fixed_20261115/round3/M2.json' if name=='M2' else 'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/'+name+'.json'))
  baseline=load(Path(config['output'])/'readout/scores.json')
  for readout in ('R1','R3'):
   value=baseline[readout]['mean_normalized_improvement']
   lines.append(f'|{name}|第6层（已有分数引用）|{readout}|{value:.6g}|—|—|REFERENCE|')
 completed=0;missing=[];notes=[]
 labels={'3':'第3层','4':'第4层','5':'第5层','mean':'第3–6层等权平均','whiten':'按元素白化','z':'PMA z','concat':'[mean(H6), z]'}
 for c,m in expected:
  p=REPO/f'results/p_heads/H/H_{c}_{m}.json'
  if not p.exists():missing.append(c+'_'+m);continue
  result=load(p);completed+=1
  for r,d in result['deltas'].items():
   score=result['scores'][r]['mean_normalized_improvement'];ci=d["ci95"];lines.append(f'|{c}|{labels[m]}|{r}|{score:.6g}|{d["delta"]:.6g}|[{ci[0]:.6g}, {ci[1]:.6g}]|{d["verdict"]}|')
  if m=='whiten':notes.append(c+'未白化的下游原子数：'+', '.join(str(k)+'='+str(v) for k,v in result.get('unwhitened_atoms',{}).items())+'。')
 lines+=['']+notes+['',f'已完成{completed}/{len(expected)}组。尚未产出：'+(', '.join(missing) if missing else '无')+'。']
 if not missing:
  lines+=['','结果解释：H2的R1在B3第3/4层和M1第4层相对各自第6层R1更差，其余所测换层或等权平均持平；H3的R1在B3和M1均持平。H2/H3的R3在全部所测变体中均相对同checkpoint第6层R3更差，因此这些结果不支持用本次换层、等权平均或元素白化替换该R3来源。','','H4中，z及[mean(H6), z]的R1各自相对B3第6层R1更优；按同一预注册R1参照，z的R2更差，拼接向量的R2更优。M2上按其原第6层R1参照，z的R1更优、R2更差，拼接向量的R1/R2均更优，复现B3已有注册判定的同一模式。两种分子向量的线性读出可作为后续表示建议；未比较z与拼接向量的直接配对差异，也未作跨读出协议的胜负或B3与M2间差异判定。','','原始12组H2–H4完成时，H1、H2–H4和H6已执行GPU作业累计墙钟4.8670小时；新增M2 H4、H7及后续几何的实核卡时另记日报，保持原≤15 GPU小时预算。']
 lines+=['','局限：同一checkpoint的读出比较不含训练种子变异；所有结果仅构成建议，不自动接入主线。H4的R2相对线性R1基线还包含非线性读出容量变化，不能单独将增益归因于z信息更优。不同元素中的稀有元素估计、PMA广播站点读出和白化常数维的数值处理均已明确；未搜索新超参数或读出结构。']
 lines+=cyp_report(expected)
 guard();(REPO/'docs/p_heads/H2_H4_SOURCES.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':main()
