"""D3 primaryD-C and supplementalD-M1 from existing paired readout draws."""
from resources import REPO,load,save,guard
from compare_dedup import paired_ci
from pathlib import Path

if __name__=='__main__':
 guard(force=True);d=load(REPO/'configs/p_followup/D_decomposition.json');c=load(REPO/'configs/p_followup/C_dedup.json');m=load(REPO/'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/M1.json')
 actual=load(Path(d['output'])/'readout/scores.json');comparisons={}
 for name,reference in [('D-C',c),('D-M1',m)]:
  base=load(Path(reference['output'])/'readout/scores.json');comparisons[name]={r:paired_ci(actual[r],base[r]) for r in ['R1','R3']}
 decision=comparisons['D-C']['R3']['verdict']
 result=dict(status='COMPLETE',candidate=d['run'],C=c['run'],M1=m['run'],samples=3000000,seed=0,primary='D-C/R3',comparisons=comparisons,
  recommendation='Conformer decomposition is a candidate for adoption' if decision=='win' else 'Do not recommend conformer decomposition from this comparison',mainline_modified=False,integration_requires_user_confirmation=True)
 save(REPO/'results/p_followup/D_comparison.json',result)
 lines=['# D3：构象分解配方比较','','D与C均为seed0、3M，复用主线同一R1/R3及1000次MID配对bootstrap的保留抽样值。主比较D−C，D−M1仅补充。核对任务集及bootstrap分组/seed/次数/置信度后相减，取95%分位CI；R3区间全正win、全负loss、其余tie，不加效应门槛。','','|比较|读出|差值|95%CI|判定|','|---|---|---:|---|---|']
 for name,rows in comparisons.items():
  for r,v in rows.items():lines.append(f"|{name}|{r}|{v['delta']}|{v['ci95']}|{v['verdict']}|")
 lines+=['',result['recommendation']+'。只有D−C为win才形成候选建议；实际接入主线由用户确认。M1为A1基底，后续主线变化不扩展本证据范围。','','同分子构象差原单位MAE在冻结VAL面板的既有构象对上按字段作描述，见D_VAL_CONFORMER_MAE.md；表示指标及预注册A-H6见A_COLLAPSE_COMPOSITION.md。']
 (REPO/'docs/p_followup/D_COMPARISON.md').write_text('\n'.join(lines)+'\n');print('D_COMPARISON_COMPLETE',comparisons)