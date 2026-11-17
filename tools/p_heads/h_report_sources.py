"""Render H2-H4 tables from completed producer JSONs, without reevaluation."""
from h_resources import REPO,guard,load


def main():
 expected=[(c,m) for c in ('B3','M1') for m in ('3','4','5','mean','whiten')]+[('B3','z'),('B3','concat')]
 lines=['# H2–H4：下游表示来源','','方法：使用主线冻结开发面板与完全相同的TrainOnlyPackedStore、GroupedTrainingView、task_rows/atomization_rows、ridge_probe和run_probe；不训练编码器，不读取TEST。第6层基线和分数直接引用已有3M checkpoint。层3/4/5取实际中间输出，层平均为第3–5中间输出和第6层out_norm输出等权平均。','','元素白化统计仅来自预训练固定5000 VAL分子的首允许构象，第6层逐元素逐维均值和标准差；元素原子数不足50保持原特征，标准差下限为该维全局标准差的1e-6。完全常数全局维度无可定义方差，去均值后以单位尺度保留零值，未产生新信号；下游不重新拟合白化统计。','','PMA的577维z从已预训练PMA模块读取。[mean(H6),z]的两个块在下游TRAIN上分别按维标准化，使用已有graph_features接口直接进入R1或现成R2（池化后MLP），不新写读出协议。CYP原子任务仅将同一分子向量广播至各原子作描述；其站点预测不含原子区分信息，不纳入主分或结论。','','统计：沿用主线7任务平均规范化改善分数，按同一分子组、种子和顺序的1000次配对bootstrap逐抽样相减，95%百分位区间。变体减同checkpoint第6层基线；H4的R1/R2均与该checkpoint现有R1比较。更优要求CI下界>0且Δ≥max(0.02,基线×5%)；CI上界<0为更差，其余持平。','','|checkpoint|变体|读出|分数|Δ|95%CI|判定|','|---|---|---|---:|---:|---|---|']
 completed=0;missing=[]
 labels={'3':'第3层','4':'第4层','5':'第5层','mean':'第3–6层等权平均','whiten':'按元素白化','z':'PMA z','concat':'[mean(H6), z]'}
 for c,m in expected:
  p=REPO/f'results/p_heads/H/H_{c}_{m}.json'
  if not p.exists():missing.append(c+'_'+m);continue
  result=load(p);completed+=1
  for r,d in result['deltas'].items():
   score=result['scores'][r]['mean_normalized_improvement'];ci=d["ci95"];lines.append(f'|{c}|{labels[m]}|{r}|{score:.6g}|{d["delta"]:.6g}|[{ci[0]:.6g}, {ci[1]:.6g}]|{d["verdict"]}|')
  if m=='whiten':lines+=['',f'{c}未白化的下游原子数（按数据集）：{result.get("unwhitened_atoms",{})}。','']
 lines+=['',f'已完成{completed}/{len(expected)}组。尚未产出：'+(', '.join(missing) if missing else '无')+'。','','局限：同一checkpoint的读出比较不含训练种子变异；所有结果仅构成建议，不自动接入主线。不同元素中的稀有元素估计、PMA广播站点读出和白化常数维的数值处理均已明确；未搜索新超参数或读出结构。']
 guard();(REPO/'docs/p_heads/H2_H4_SOURCES.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':main()
