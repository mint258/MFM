"""Render bounded D7 evidence; never infer a full population from a pilot."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    path=Path(path)
    if path.stat().st_size>2*1024**2:
        raise ValueError('Metadata renderer refuses inputs above2MiB')
    return json.loads(path.read_text(encoding='utf-8'))


def ref(path):
    path=Path(path);raw=path.read_bytes()
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def render(run_root):
    root=Path(run_root);folder=root/'artifacts/conformers/statistics_v1'
    rp=folder/'profile_v1/receipt.json';receipt=load(rp);sp=folder/'profile_v1/profile_statistics.json';s=load(sp)
    prepare=load(folder/'prepared_v1/prepared.json');history=load(folder/'prepared_v1/history_search.json')
    c=load(root/'control/d7_profile_actual_closure_v1.json')
    if receipt['status']!='D7_PROFILE_COMPLETED_NOT_FULL_POPULATION' or s['completed_molecules']!=256 or receipt['error_molecules']!=0:
        raise ValueError('Only actual closed256-molecule no-error profile can render this report')
    for pin in receipt['outputs']:
        if Path(pin['path']).name in {'profile_statistics.json','errors.json','molecule_manifest.json'} and ref(pin['path'])!=pin:
            raise ValueError('Output metadata SHA differs')
    if c['receipt']!=ref(rp) or c['actual_parent']['State']!='COMPLETED' or c['actual_parent']['ExitCode']!='0:0':
        raise ValueError('Actual parent closure differs')
    lines=['# 构象统计：实际有界试点','',
           '状态：**D7 全共同人群报告尚未完成**。以下仅为2026-10-25实际256个完整分子的只读试点，非总体估计；不会因本报告冻结common或训练构象顺序。','',
           f"准备job4520383实际COMPLETED0/180s/16CPU；统计job4520390实际COMPLETED0/{c['actual_parent']['ElapsedRaw']}s/16CPU。原PM7记录{prepare['records']:,}条。没有嵌入、优化或量化调用，没有修改原数据。",'',
           '试点限定至多16个canonical owner jobs，先覆盖原来源角色、大小和N分层，再固定hash抽样；存在I/O与来源选择偏差。角色仍为原TRAIN/FULL，尚非最终TRAIN＋ROUTINE VAL共同人群。','',
           '## 原子映射与去重定义','',
           'PM7和S′均按固定源重原子索引、proper Kabsch、0.5 Å RMSD判重，不进行反射、对称原子置换或原子重排。两侧均按seed20261025的固定随机顺序做贪心判重。来源图、原子序、立体化学检查错误为0；逐分子坐标摘要、三种顺序、代表ID和全交叉RMSD保存在外部压缩JSON。','',
           '配置与代码使用16进程池；当前receipt未保存每个实际worker PID/任务数，故不把配置16声明为16 distinct PID实测证据。正式统计需补上这一观测。','',
           '## 不重复构象数','',
           '|不重复数|PM7分子数|S′分子数|','|---:|---:|---:|']
    for n in sorted(set(s['unique_counts']['pm7']['histogram'])|set(s['unique_counts']['uff_sprime']['histogram']),key=int):
        lines.append(f"|{n}|{s['unique_counts']['pm7']['histogram'].get(n,0)}|{s['unique_counts']['uff_sprime']['histogram'].get(n,0)}|")
    lines += ['', '|达到的构象数|PM7比例|S′比例|','|---|---:|---:|']
    for n in ('2','5','10'):
        lines.append(f"|≥{n}|{100*s['unique_counts']['pm7']['fractions_ge_2_5_10'][n]:.6f}%|{100*s['unique_counts']['uff_sprime']['fractions_ge_2_5_10'][n]:.6f}%|")
    lines += ['',f"PM7含重复构象的分子占{100*s['pm7_molecules_with_duplicates_fraction']:.6f}%；重复构象占原构象{100*s['unique_counts']['pm7']['duplicate_conformer_fraction']:.6f}%。S′对应重复构象比例{100*s['unique_counts']['uff_sprime']['duplicate_conformer_fraction']:.6f}%。这是本试点、指定贪心顺序下的比例，不能外推为全量优化收敛比例。",'',
              '## 构象数相关性','', '|相关性|Spearman ρ|有效分子数|','|---|---:|---:|']
    for name,r in s['correlations'].items():lines.append(f"|{name}|{r['spearman_rho']:.9f}|{r['n']}|")
    lines += ['', '## PM7生成热范围和PM7—S′交叉RMSD','',
              f"{s['canonical_hof_complete_molecules']}个分子的全部PM7几何均取得canonical pm7_B registry60/kind1/f64生成热，单位kcal/mol。按record/molecule/attempt/job/task五键、lane及原子数核对，未使用native energy替代；缺失原因计数为空，NULL收敛review记录{s['hof_convergence_null_review_records']}。",'',
              '|分位百分数|分子内生成热范围（kcal/mol）|全部PM7—S′构象对RMSD（Å）|','|---:|---:|---:|']
    for q in ('0','25','50','75','90','95','99','100'):
        lines.append(f"|{q}|{s['complete_canonical_hof_range_quantiles_kcal_mol'][q]:.9g}|{s['cross_rmsd_A_quantiles'][q]:.9g}|")
    lines += ['', '交叉RMSD按本试点全部构象对汇集，构象较多的分子贡献更多pair；不是按分子等权的分位数。生成热范围分位数则每分子贡献一个范围。三种顺序以原几何ID保存，能量／最低能起点多样性本试点HOF完整；最终训练排序仍等待全common覆盖。','',
              '## 原始N规则的历史来源','',
              '**未找到**原始PM7首次决定每个分子构象数的明确生成策略。检索仅覆盖配置指定的legacy、dataset_rebuild及历史服务器源码；导入器读取既有构象、WP0统计既有ID、S′复制既有PM7 N，都不能证明原始N公式。不从可旋转键相关性推测。各文件路径/SHA、命中行和截断记录见外部history_search.json。','',
              '## 证据和复现','',
              '以下路径相对外部run根；统计由prepare_profile.py和run_profile.py实际计算，本文件由render_report.py读取已闭合小型JSON生成，不重新处理科学正文。','',
              '- `artifacts/conformers/statistics_v1/prepared_v1/prepared.json`、`history_search.json`',
              '- `artifacts/conformers/statistics_v1/profile_v1/receipt.json`、`profile_statistics.json`、`molecule_manifest.json`、`errors.json`',
              '- `control/d7_profile_preparation_actual_closure_v1.json`、`control/d7_profile_actual_closure_v1.json`','',
              f"统计JSON：{ref(sp)['bytes']}B，SHA256 `{ref(sp)['sha256']}`。",'',
              '复现渲染：`python -B workflows/data_v1_final/conformers/statistics_v1/render_report.py --run-root <外部run根> --output <新的报告路径>`。渲染拒绝覆盖；原科学数据只读。','']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    text=render(a.run_root)
    with Path(a.output).open('x',encoding='utf-8',newline='\n') as f:f.write(text)


if __name__=='__main__':main()
