"""Stage1 report producer, with stage2 evidence registration kept separate."""
import collections,json,pathlib
import numpy as np
from stage0_cohort import R,D,O,load,save
from stage1_geometry import key
B=R/'MFM_p_data_information'
def main():
 c=load(O/'coverage.json');pairs=load(O/'pairs.json');panels=load(O/'panel.json');aggregate={};cases={};lines=[]
 for role,r in c['roles'].items():
  metrics=[p['heavy_rmsd'] for p in pairs[role]['conformer'] if p['heavy_rmsd'] is not None]
  aggregate[role]={k:v for k,v in r.items() if k!='geometry'};aggregate[role].update(median_pair_heavy_rmsd=float(np.median(metrics)) if metrics else None,near_duplicate_pairs=sum(v<.5 for v in metrics),distinct_pairs=sum(v>=.5 for v in metrics))
  candidates=sorted(pairs[role]['conformer'],key=lambda p:(key(role,'case',[p['molecule_id'],p['a'],p['b']]),p['molecule_id']))[:6];cases[role]=candidates
  a=aggregate[role];lines.append(f"|{role}|{a['molecules']}|{a['core']}|{a['enriched_groups']}|{a['records']}|{a['representatives']}|{a['conformer_pairs']}|{a['isomer_pairs']}|{a['composition_pairs']}|")
 save(B/'results/p_data_information/coverage.json',dict(roles=aggregate,external_pair_manifest=str(O/'pairs.json'),external_panel=str(O/'panel.json'),elapsed_seconds=c['elapsed_seconds'],cases=cases))
 text='''# 阶段1：真实结构覆盖与比较组\n\n状态：COMPLETE_AT_PILOT_GEOMETRY_LAYER。本阶段不读标签值，面板与配对已冻结。\n\n|角色|并集分子|核心|同式组|允许记录|0.5Å代表|构象对|异构分子对|组成对|\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n'''+ '\n'.join(lines)+f'''\n\n按原selection_rank选择3000/300核心；按元素计数+形式净电荷分组，使用RDKit连接图身份（去立体信息的canonical图，而非输入SMILES字符串）区分连接结构，每图选固定hash成员，每组最多4图、TRAIN最多500组/VAL最多50组。每分子先排除既有M13 D5留出，再按fixed_random取最多10个；每分子hash选最多6个无序构象对。跨组成对不共用分子。种子20261025，UTF8紧凑JSON版本P-DATA-INFORMATION-v1。原母集之外未补入。\n\n几何使用实际pilot P坐标及M源重原子对应，proper Kabsch，禁止反射；0.5Å仅作几何分类。记录全原子RMSD、已有图非环重原子单键二面角变化、图距离≥3且最多hash选128个非键接触；已有扰动几何只在冻结主配对上另算RMSD。生产者的2个专用检查验证了刚体不变性/拒绝反射以及接触/二面角定义。\n\n全人口D7的已发表7,483,854/11,229,900口径只作背景，不能移用为当前成员、D5排除和first10下的代表数；这里保留本面板实际计算的几何距离。没有把近似重复当作独立计算对照。以上为pilot FP32坐标层，原WP5目标实际输入的最终跨层对应待阶段5；这些几何统计不能独自判定全部任务的物理变化。\n\n外部面板/完整配对：{O}/panel.json、pairs.json；汇总与总计最多12个的标签无关贯穿案例在coverage.json。几何计算耗时{c['elapsed_seconds']:.1f}秒。后续不依据标签结果重选这些成员和配对。\n'''
 (B/'docs/p_data_information/01_STRUCTURE_COVERAGE.md').write_text(text)
 bars=[]
 for i,(role,a) in enumerate(aggregate.items()):
  y=65+i*100;w=500*a['representatives']/max(a['records'],1);bars.append(f'<text x="20" y="{y}">{role}: {a["records"]} records / {a["representatives"]} representatives</text><rect x="20" y="{y+12}" width="500" height="24" fill="#dbe6f0"/><rect x="20" y="{y+12}" width="{w:.2f}" height="24" fill="#2679a5"/>')
 (B/'results/p_data_information/coverage.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="620" height="270"><rect width="620" height="270" fill="white"/><g font-family="sans-serif" font-size="15"><text x="20" y="25">Frozen panel: records and 0.5 A representatives</text>'+''.join(bars)+'</g></svg>')
 p=load(B/'results/p_data_information/progress.json');p['stage1']='COMPLETE_AT_PILOT_GEOMETRY_LAYER';save(B/'results/p_data_information/progress.json',p)
 print(json.dumps(aggregate),flush=True)
if __name__=='__main__':main()
