"""Assemble the 15-item screening report from closed JSON/Markdown evidence.

Metadata only: no original LMDB, numerical records, scientific execution, or
final configuration adoption. The first printable page is a decision table.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import heapq
import json
from pathlib import Path
import time

ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')


def read(relative):
    return json.loads((ROOT / relative).read_text())


def fmt(value, digits=3):
    return '未测/不适用' if value is None else f'{value:,.{digits}f}'


def measured_range(values, digits=2):
    observed = [value for value in values if value is not None]
    return '未测' if not observed else f'{min(observed):.{digits}f}–{max(observed):.{digits}f}'


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(map(cell, headers)) + ' |',
                     '|' + '|'.join(['---'] * len(headers)) + '|'] +
                    ['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows])


def linked(path, title=None):
    absolute = ROOT / path
    return f'[{title or Path(path).name}]({absolute})'


def io_appendix(engineering):
    rows = []
    for row in engineering['C3_nodes']:
        before = row.get('scratch_before') or {}
        after = row.get('scratch_after') or {}
        io = row.get('process_IO') or {}
        rows.append([row['design_node'] + '→' + str(row.get('actual_node')),
            row.get('actual_scientific_worker_PID_union'), row.get('observed_unique_completed_molecules'),
            row.get('observed_completed_record_executions'),
            fmt(io.get('read_bytes') / 1e9 if io.get('read_bytes') is not None else None),
            fmt(io.get('write_bytes') / 1e9 if io.get('write_bytes') is not None else None),
            fmt(before.get('write_MiB_s')) + '→' + fmt(after.get('write_MiB_s')),
            fmt(before.get('read_MiB_s')) + '→' + fmt(after.get('read_MiB_s'))])
    return '\n'.join(['### C3：scratch I/O 与实际完成覆盖', '',
        table(['设计→实际节点', '实际worker PID并集', '闭合唯一分子', '闭合记录执行数',
               '采样read GB', '采样write GB', 'fsync写MiB/s 前→后', '缓冲读MiB/s 前→后'], rows), '',
        '128MiB scratch 探针包含 fsync；立即回读经过页缓存，不代表冷盘带宽。采样 /proc I/O 随子进程生命周期有观测窗口，字节数不是完整作业的精确 I/O 等待。现有数据不显示 fsync 吞吐退化，不能据此保证满 29 槽并发时没有 I/O 瓶颈。', '',
        '预算到期的 partial-resumable round 是正常截断，并非原人口 manifest 不一致。上表仅列已闭合分子/记录执行数，不宣称整个 10,020-record panel 全量闭合；重复 round 也不增加独立分子人口。'])


def esp_appendix(report):
    analysis = report['analysis']
    rows = []
    for size, item in analysis['cost']['by_size_stratum'].items():
        components = item['component_average_seconds_per_record']
        rows.append([size, fmt(item['represented_population'], 0),
            fmt(components['b1_ESP_alone'], 6), fmt(components['b1_ESP_WILLIAMS'], 6),
            fmt(item['completion_time_censored_population_fraction'], 6)])
    return '\n'.join([
        '从原 7,316 个失败记录中按报错类型×大小抽取 200 例，单独运行 PM7 1SCF ESP，恢复 0/200。对非 d 轨道不支持的 109 例补跑 WILLIAMS，恢复 0/109；91 例明确不支持的路径没有重复运行。原坐标与源 LMDB 保持不变。', '',
        table(['直接观测失败原因', '原/本轮单跑数量', '元素与证据'], [
            ['d 轨道不支持', '91/91', 'MOPAC 原始文本明确拒绝；七大小层均有'],
            ['表面生成/半径缺失', '57/57', '均含 Se'],
            ['TOO MANY NEIGHBORS', '28/28', '26 含 B、2 含 Se；有些退出码为 0'],
            ['仅观测到 signal 终止', '24/24', '均含 B；底层原因未定，不归为已确认 SCF 不收敛']]), '',
        '单跑退出码：173×0、16×SIGABRT(−6)、11×SIGSEGV(−11)。退出码为 0 也可能没有可用 ESP 电荷。WILLIAMS 的 59 例表面失败均含 Se，50 例 SIGSEGV 均含 B；没有观察到超时、可修复关键词冲突或已确认 SCF 未收敛。', '',
        '未加权实际服务时间：单跑 2,924.309 s、条件补跑 72.499 s。恢复到原失败人口后，每条原失败记录为单跑 1.377515 s，加条件补跑 0.020466 s，总 1.397981 s。不能把失败样本均值当作全人口首跑均值；无条件成本还包括原 2,704 个成功记录的实测时间，已纳入 C1。', '',
        table(['大小层', '代表的原失败数', '单跑均值s/失败记录', '条件补跑均值s', '超时删失权重比例'], rows), '',
        '没有证据支持常规单跑/WILLIAMS 修复策略。配置选项是删除 ESP，或保留支持子集的成功值、charge QC 与缺失 mask；已知不支持/表面/邻居限制/信号失败路径不常规重复。当前成功科学数值继续保留，最终计算范围由用户确定。', '',
        linked('b_quantum/analysis/B1_ESP_conclusion.md', '原诊断结论与任务绑定') + '；' +
        linked('b_quantum/esp_analysis/job_4513567/report.json', '全部 200 例、分层权重与失败转移') + '；' +
        linked('b_quantum/esp_analysis/failure_refine_job_4513581.json', '原/本轮共 600 槽实际文本诊断'), ''])


def b_appendix(b2, b4, b5, site, b6, relationships):
    lines = ['## B2、B4、B5、B6：计算与标签证据', '',
        'B1 与 B3 的完整小样本对照已在前文列出。以下统计来自已闭合的原生 pilot；本轮没有因标签失败排除整条基础几何数据。', '',
        '### B2：POLAR 的原始输出确认', '',
        f"20/20 个不同分子的原始输出三行静态张量与独立解析完全一致。{b2['molecular_polar_tensors']:,} 个张量中，{b2['asymmetric_gt0_01']:,} 个不对称绝对幅度超过 0.01 bohr³。", '',
        table(['幅度/关系', '结果'], [
            [key, fmt(b2['antisymmetry_abs_bohr3'][key], 6) + ' bohr³']
            for key in ('min', 'p50', 'p90', 'p99', 'max')]) , '',
        f"PM7 trace/3 与 xTB D4 原子 α 之和 Pearson={fmt(b2['correlation_PM7_trace_over3_vs_sum_D4_atomic_alpha']['pearson'], 6)}；D4 原子求和是代理量，其相关性不能证明 PM7 张量可靠。按任务文件结论删除 POLAR，不继续追查。", '',
        linked('b_quantum/analysis/B2_raw_manual_20.md', '20 例原始输出核对') + '；' + linked('b_quantum/analysis/B2_POLAR.json', '完整幅度与分层相关性'), '',
        '### B4：数值 QC 与标签缺失', '',
        table(['统计（单位）', 'n', 'p50', 'p90', 'p99', 'max'], [
            [name, data['n']] + [fmt(data[k], 6) for k in ('p50', 'p90', 'p99', 'max')]
            for name, data in [
                ('Q01 梯度范数（kcal/mol/Å）', b4['Q01']),
                ('|Q02| Hf 复现误差（kcal/mol）', b4['Q02_absolute']),
                ('PERT 全分子力 Frobenius 范数（eV/Å）', b4['perturb_force_norm_eV_A']),
                ('PERT 单记录最大原子力范数（eV/Å）', b4['maximum_atom_force_eV_A'])]]), '',
        '原 pilot 的逐原子 PERT 力范数中位数 4.184、p90 15.126 eV/Å；它与上表的全分子 Frobenius 范数是不同统计。PERT 包含随机坐标微扰，不能当作原 PM7 几何上的受力。', '',
        '阳离子 UHF 成功 9,979/10,020（41 个超时）；阴离子成功 10,017/10,020（3 个超时）。S²−0.75 的中位数分别 0.058329、0.064566，p99 分别 0.455461、0.455647；负 EA 保留为物理值。', '',
        table(['原生 task', '状态', '数量'], [[r['task'], r['status'], r['count']] for r in b4['task_statuses']]), '',
        'Q01/Q02/自旋污染仅统计，不制定剔除阈值。xTB 单点、ALPB 两溶剂、FOD、PERT 全部成功；vipea 14 例失败、vfukui 3 例失败；原 Hessian 17 例超时。基础 PM7 B 数据可用 10,020/10,020，POLAR 属性失败与 B 基础可用性分别记录。', '',
        linked('b_quantum/analysis/B4_QC.json', '完整分位数与自旋分布') + '；' +
        linked('b_quantum/analysis/B4_missing_by_label_group.parquet', '逐标签 × 元素 × 大小缺失率') + '；' +
        linked('b_quantum/analysis/B4_supplement.json', '原逐原子力、离子 SCF 与 xTB 失败详情'), '',
        '缺失率表分别记录 absent/null/nonfinite/empty；失败状态与某个字段是否可用分开统计，没有填零。', '',
        '### B5：构象覆盖依据', '',
        '1,441/1,441 个分子的原子序列和原存储键图在构象间一致。采用不平衡单因素随机效应 ANOVA：within=MSW，between=(MSB−MSW)/n₀，ICC=between/(within+between)，并给出 within/between；负 between 估计保留，仅计算 ICC 时截到零。至少需要同分子两条有效构象；仅最低构象的 Hessian 无法估计构象 ICC。', '',
        '全局 ICC 会受分子大小跨度影响。跨分子的“同索引原子”也不等于同一化学位点；因此同时报告同分子原位点 SD、按大小分层的 ICC，以及原子排列不变的分子级 mean/RMS/min/max。电荷总和的 mean 可能被电荷守恒固定，不能据此声称原子电荷不变。', '',
        '下面展示占放宽保留集约一半的 21–30 重原子层，使用物理单位评估变化。全部标签、全部七层与不能估计的条目保留在链接的 JSON/Parquet。', '']
    picks = [
        ('pm7_B', 'vertical_IP_eV', 'scalar'),
        ('pm7_B', 'vertical_EA_eV', 'scalar'),
        ('pm7_B', 'pm7_water_HOF_difference_kcal_mol', 'scalar'),
        ('pm7_B', 'pm7_octanol_HOF_difference_kcal_mol', 'scalar'),
        ('pm7_water', 'cosmo_area_A2', 'scalar'),
        ('pm7_water', 'heat_of_formation_kcal_mol', 'scalar'),
        ('pm7_cation', 'heat_of_formation_kcal_mol', 'scalar'),
        ('pm7_anion', 'heat_of_formation_kcal_mol', 'scalar'),
        ('xtb_singlepoint', 'dipole_Debye', 'norm'),
        ('xtb_singlepoint', 'molecular_quadrupole_traceless_au', 'frobenius'),
        ('xtb_singlepoint', 'homo_eV', 'scalar'),
        ('xtb_vipea', 'IP_eV', 'scalar'),
        ('xtb_vipea', 'EA_eV', 'scalar'),
        ('xtb_ALPB_water', 'Gsolv_Eh', 'scalar'),
        ('xtb_fod', 'NFOD_e', 'scalar')]
    rows = []
    for task, suffix, feature in picks:
        matches = [r for r in b5['labels'] if r['size_stratum'] == '21_30' and r['task'] == task and
                   r['source_path'].endswith('.' + suffix) and r['feature'] == feature]
        for r in matches:
            rows.append([task + ':' + suffix, r['unit'], r['molecules'], fmt(r['within_sd'], 6),
                         fmt(r['ICC'], 6), fmt(r['p90_molecule_within_sd'], 6)])
    lines += [table(['标签/分子级量', '单位', '分子数', '构象内 SD', 'ICC', '分子内 SD 的 p90'], rows), '',
        '按原子索引跨分子汇聚的 within SD（21–30 层）：每个索引先计算 ANOVA sqrt(MSW)，再对有效索引取 p50/p90。另列每个索引的单分子 SD 中位数再对索引取 p50；两种统计不同，跨分子原子排序影响索引解释。', '']
    candidates = [r for r in site['labels'] if r['size_stratum'] == '21_30' and any(
        key in r['source_path'] for key in ('fukui', 'charges', 'bond_orders', 'force', 'FOD_atom', 'alpha'))]
    lines += [table(['task', '原字段', '单位', '有效分量数', 'sqrt(MSW)索引 p50', 'sqrt(MSW)索引 p90', '分子SD中位数的索引p50'], [
        [r['task'], r['source_path'], r.get('unit'), r['components'], fmt(r['within_sd']['p50'], 6),
         fmt(r['within_sd']['p90'], 6), fmt(r['molecule_within_sd_median']['p50'], 6)] for r in candidates]), '',
        '全构象 C/D 保留每条几何对应的离子、溶剂和反应性变化；只算最低构象可显著节约成本，同时会缺少这些逐构象目标。PM7 IP/EA 的 SD 约 0.16–0.19 eV、p90 分子内 SD 约 0.25–0.26 eV；溶剂 Hf 差的 SD 约 1 kcal/mol，不能视作构象常量。采用 C/D 最低构象是预算与目标覆盖的取舍，不是 pilot 证明标签不变。xTB 非 Hessian 保持全构象能保留原子/键与三维响应。', '',
        '偶极采用模长，没有评估方向敏感性；xTB 六个四极矩分量按官方顺序 xx,xy,yy,xz,yz,zz 还原对称矩阵，再计算 Frobenius 范数和特征值。[xTB 官方多极矩文档](https://xtb-docs.readthedocs.io/en/latest/properties.html)。分子级矩也可能遮蔽局部重排，需结合上表原位点 SD。', '',
        linked('b_quantum/analysis/B5_size_conditioned/report_v2.json', '全部分层与原位点 ICC/SD') + '；' +
        linked('b_quantum/analysis/B5_molecule_invariants/report.json', '排列不变的分子级完整指标') + '；' +
        linked('b_quantum/analysis/B5_molecule_invariants/molecule_summary_ICC.parquet', '分子级指标 Parquet'), '',
        '### B6：登记表、推导关系与重复字段', '',
        '756 个稳定 registry ID，未登记字段为 0。v2 修正 atom-level Coulson Fukui、原/微扰几何上下文、FOD 电子温度和 D4/四极矩单位；科学数值与 source_path/ID/inclusion 不变，共享元信息仅增加 96,486 B（全局一次）。分类为 physical_label、QC 和 provenance；数组作为复合标签，索引不另立物理目标。', '',
        table(['推导关系', '数值分量数', 'R²', '最大绝对误差', '观测精确相同'], [
            [r['formula'], r['n'], fmt(r['R2'], 12), fmt(r['max_abs_error'], 12), r['exact_observed']]
            for r in b6['formula_checks']]), '',
        table(['补充关系', '数值分量数', 'R²', '最大绝对误差'], [
            [r['relationship'], r['numeric_components'], fmt(r['R2'], 12), fmt(r['absolute_error']['max'], 12)]
            for r in relationships['relationships']]), '',
        '9 个主关系与 4 个补充关系达到 R²>0.9999；高 R² 与逐位无损等价不同，舍入误差如表。Mulliken 与 Coulson/shell population 的关系仅 R²≈0.7395，不能相互替代。', '',
        table(['同方法字段（B vs ESP）', '配对记录', '最大差', '观测精确重复'], [
            [r['field'], r['paired_records'], fmt(r['max_abs_difference'], 12), r['exact_duplicate_in_observed_pairs']]
            for r in b6['within_method_duplicates']]), '',
        'COSMO 面积/体积 2,982 对观测精确重复；Hf、偶极、电荷、轨道能存在差异，当前全部科学数值保留，未来字段去冗余另行确认。POLAR static 与频率 0 块的重复只归入诊断。xTB specialty 输出按实际请求的中性/离子方法上下文登记。', '',
        linked('reports/label_registry_v2.json', '修正后的完整标签登记表') + '；' +
        linked('b_quantum/analysis/B6_registry_audit.json', '逐字段匹配与推导审计') + '；' +
        linked('b_quantum/analysis/B6_additional_relationships.json', '补充推导关系'), '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text()); print('ASSEMBLER_AST_PASS'); return
    paths = [
        'a_retained/A1_A4_validation_summary.json', 'reports/A_final_decision_appendix.md',
        'b_quantum/analysis/B1_ESP_conclusion.md', 'b_quantum/analysis/B2_POLAR.json',
        'b_quantum/esp_analysis/job_4513567/report.json',
        'b_quantum/analysis/B4_QC.json', 'b_quantum/analysis/B4_supplement.json',
        'b_quantum/analysis/B5_size_conditioned/report_v2.json',
        'b_quantum/analysis/B5_molecule_invariants/report.json',
        'b_quantum/analysis/B6_registry_audit.json', 'b_quantum/analysis/B6_additional_relationships.json',
        'b_quantum/hessian_analysis/job_4513568/report.json', 'b_quantum/analysis/B3_Hessian_conclusion.md',
        'b_quantum/hessian_analysis/requested_scope_repair/report.json',
        'c_engineering/cost_packing_v3/C1_scenario_matrix.json',
        'c_engineering/cost_packing_v3/C2_job_distribution.json',
        'c_engineering/cost_packing_v3/C2_actual_task_validation.json',
        'reports/c_engineering_summary_v3.json', 'reports/c_engineering_summary_v3.md',
        'reports/c_engineering_appendix_v2.json', 'reports/c_engineering_appendix_v2.md',
        'reports/cleanup_actual.json', 'reports/final_quota.json', 'reports/final_job_snapshot.json',
        'reports/label_registry_v2.json', 'reports/authority.json',
        'reports/C3_substitution_authority.json', 'reports/c3_sacct_login_final.json']
    missing = [p for p in paths if not (ROOT / p).exists()]
    if missing:
        print(json.dumps({'status': 'WAITING_CLOSED_EVIDENCE', 'missing': missing})); return
    b2 = read('b_quantum/analysis/B2_POLAR.json'); b4 = read('b_quantum/analysis/B4_QC.json')
    esp = read('b_quantum/esp_analysis/job_4513567/report.json')
    b5 = read('b_quantum/analysis/B5_molecule_invariants/report.json')
    site = read('b_quantum/analysis/B5_size_conditioned/report_v2.json')
    b6 = read('b_quantum/analysis/B6_registry_audit.json')
    rel = read('b_quantum/analysis/B6_additional_relationships.json')
    hess = read('b_quantum/hessian_analysis/requested_scope_repair/report.json')
    costs = read('c_engineering/cost_packing_v3/C1_scenario_matrix.json')
    packing = read('c_engineering/cost_packing_v3/C2_job_distribution.json')
    validation = read('c_engineering/cost_packing_v3/C2_actual_task_validation.json')
    engineering = read('reports/c_engineering_summary_v3.json')
    appendix = read('reports/c_engineering_appendix_v2.json')
    cleanup = read('reports/cleanup_actual.json'); quota = read('reports/final_quota.json')
    scenarios = costs['scenarios']
    if engineering['C3_closed_design_cohorts'] != 6:
        raise ValueError('Final report requires all six authorized C3 design cohorts closed')
    if hess['analysis']['records'] != 100 or len(scenarios) != 48:
        raise ValueError('Final report B3/C1 metadata evidence is incomplete')
    imag_counts = {task: sum(group[task]['imaginary_molecules'] for group in hess['analysis']['by_original_group'].values())
                   for task in ('b3_xtb_hess','b3_xtb_ohess','b3_pm7_force')}
    measured_rss = [r.get('peak_concurrent_RSS_bytes') / 1024**3 if r.get('peak_concurrent_RSS_bytes') is not None else None for r in engineering['C3_nodes']]
    measured_pss = [r.get('peak_concurrent_PSS_bytes') / 1024**3 if r.get('peak_concurrent_PSS_bytes') is not None else None for r in engineering['C3_nodes']]
    measured_times = [r['actual_seconds'] / 60 for r in engineering['C3_nodes']]
    planned_core_hours = sum(row['planned_core_hours'] for row in packing['jobs'])
    slots = [0.0] * 29
    for job in sorted(packing['jobs'], key=lambda row: row['planned_wall_hours_longest_lane'], reverse=True):
        heapq.heappush(slots, heapq.heappop(slots) + job['planned_wall_hours_longest_lane'])
    planned_slot_makespan = max(slots)
    free_quota_bytes = quota['measurements'][0]['free_bytes']
    conservative_peaks = {row['hessian_fraction']: row for row in quota['relaxed_full_candidate_peak_vs_current_quota']
                          if row['raw_model'] == 'CONSERVATIVE_DIRECT_PER_CALL_COMPRESSED_SUM'}
    candidate = next(r for r in scenarios if r['retained'] == 'relaxed' and
        r['POLAR'] == 'drop' and r['ESP'] == 'drop' and r['Hessian'] == '10pct_ohess' and r['CD_scope'] == 'minimum')
    arows = [
        ['A1', '严格 9,555,930/1,023,158 → 放宽 11,236,754/1,220,956（记录/分子）；+1,680,824/+197,798', '严格 / 放宽并标 T01', 'I01 比较规则'],
        ['A2', '15,879,477 物理记录；两套漏斗与 UpSet 全数闭合，放宽未知层 0', '按既有排除规则保留 / 改规则后复核', '保留范围与化学覆盖'],
        ['A3', '无归属 4,699→4,900；放宽重识别完整键 Train–FULL 共享 233、骨架 1,081', '保留角色但明确重叠 / 修复分组划分；embargo 保持', 'split 与外部 TEST 隔离'],
        ['A4', '放宽 T01=1,687,836、B01=3,184；H01 p99=9.928 kcal/mol/atom、S02 p99=16.284 kcal/mol', '只标注 / 后续另定阈值', 'QC 标注与阈值'],
        ['B1', '失败样本 ESP 单跑 0/200 恢复；加权默认 1.378 s/失败记录', '删除 / 仅支持子集保留并 mask', 'ESP 方案'],
        ['B2', '20/20 原输出核对一致；9,211/9,211 张量不对称>0.01；α 相关 r=0.908', '删除 POLAR（按任务文件）', 'POLAR 删除'],
        ['B3', f"原虚频670/1,424；三组目标各100/100可用；分层小样本虚频 hess {imag_counts['b3_xtb_hess']}/100、ohess {imag_counts['b3_xtb_ohess']}/100、FORCE {imag_counts['b3_pm7_force']}/100", '不算 / 10% --ohess / 100% --hess', 'Hessian 方法及覆盖'],
        ['B4', '|Q02| p99=12.000、max=180.034 kcal/mol；离子成功 9,979/10,017（各/10,020）', '保留数值 QC 与字段缺失 mask', 'QC 规则与标签可用性'],
        ['B5', '1,441 原子图对齐；21–30 层 PM7 IP/EA SD≈0.163/0.185 eV，xTB偶极模长SD≈1.30 Debye', 'C/D 全构象 / 最低；xTB 非 Hessian 全构象', '标签覆盖与预算取舍'],
        ['B6', '756 ID、未登记 0；13 推导关系 R²>0.9999；元信息修正 +96,486 B', '保留原值 / 字段确认时去冗余', '字段登记与方法上下文'],
        ['C1', f"48 成本组合；候选放宽/去 POLAR+ESP/C-D 最低/xTB 全/10%ohess：{fmt(candidate['allocated_core_hours_old_pilot_calibrated'], 1)} 核时，696 CPU 均值容量 {fmt(candidate['wall_hours_at696_old_pilot_calibrated'], 1)} h", '矩阵选择成本与覆盖', '正式计算配置'],
        ['C2', f"16 实际任务误差 p90/p99={fmt(validation['absolute_prediction_error_seconds']['p90']/3600)}/{fmt(validation['absolute_prediction_error_seconds']['p99']/3600)} h；候选 {packing['tasks']:,} 任务、超限{len(packing['oversized_molecules_requiring_chunk_resume_or_intramolecule_parallelism'])}；max lane {packing['planned_job_wall_hours']['max']:.2f}h；余量容量{planned_core_hours/696:.1f}h/29槽排程{planned_slot_makespan:.1f}h", 'k24/目标20h；checkpoint续跑', '任务打包与24h限制'],
        ['C3', f"6/6 分片；15→12/16→13替代；k24目标90min、实测{measured_range(measured_times, 1)}min；RSS {measured_range(measured_rss)}/PSS {measured_range(measured_pss)}GiB", '按 RSS/PSS 容量规划；原15/16与29槽并发未直接测', '每任务核数与节点槽位'],
        ['C4', f"放宽全标签zstd3 649.887/页模型672.894GB；边界22/26/30/36，字节比1.067；完整100%Hess峰值{conservative_peaks[1]['projected_new_writeback_peak_bytes']/1e12:.3f}TB>quota余{free_quota_bytes/1e12:.3f}TB", '无损压缩/成功raw仅最低、失败全留；10%/C-D最低降低峰值', '存储预算与五文件边界'],
        ['C5', '10,020/10,020 往返和原子顺序通过；max偏差5.009×10⁻¹³ Å', '继续按原原子顺序导出', 'xyz/几何一致性']]
    lines = [table(['筛查项', '关键数字', '可选方案/建议', '对应配置决策'], arows),
        '\n<div style="page-break-after: always;"></div>\n',
        '# Phase1 本轮筛查报告', '',
        '任务文件虽写“13 项”，实际列出 A1–A4、B1–B6、C1–C5 共 15 项，本报告覆盖全部条目。原 LMDB 全程只读，没有建立 lmdb_1；本轮只有授权的小样本 QM/节点测试及现有证据分析。', '',
        '## 待确定的正式配置', '',
        '基于结果的候选配置：放宽 I01 并加 T01，先处理 A3 的跨集合重叠与外部 TEST embargo；删除 POLAR；删除 ESP 或保留现有支持子集且标记缺失；C/D 可选最低构象以控制预算，xTB 非 Hessian 保持全构象；Hessian 的三组选项按 B3 结果选择。', '',
        f"成本候选 C/D 最低 + xTB 全构象 + 10% --ohess：约 {fmt(candidate['allocated_core_hours_old_pilot_calibrated'], 1)} 分配核时，696 调度 CPU 理想并行下经旧 pilot 开销校准约 {fmt(candidate['wall_hours_at696_old_pilot_calibrated'], 1)} h。696 含 SMT，物理核为 600，排队时间不计入。", '',
        '工程候选：五文件按全分子最大重原子数 22/26/30/36 划分；k=24，按 20h 打包、24h 作业上限；成功普通 raw 仅最低构象、失败/超时/property-failed raw 全留，已解析科学标签全部保留，采用实测的无损压缩候选。超大分子与尾部按 C2 单列策略处理。上述是待确认配置，没有自动改变数据或计划。', '',
        '若正式选择 OHess，先把本轮已验证的 D4 解析/请求范围修复移入新的正式实现，并用已归档 100 例验证；原冻结 parser 和原状态保留。优化后的频率/热化学需要独立 geometry context 与优化坐标，字段格式随后讨论，不能直接覆盖原坐标标签。', '',
        '### A1–A4：保留集与划分', '', (ROOT / 'reports/A_final_decision_appendix.md').read_text(), '',
        '## B1：ESP 失败重测', '', esp_appendix(esp), '',
        '## B3：同批 Hessian、OHess 与 PM7 FORCE 对照', '',
        (ROOT / 'b_quantum/analysis/B3_Hessian_conclusion.md').read_text(), '',
        b_appendix(b2, b4, b5, site, b6, rel), '',
        '## C1：48 个成本组合', '',
        '费用外推以旧严格 pilot 的各大小层均值重加权到严格/放宽人口，加入失败 ESP 单跑的分层加权成本与本轮 hess/ohess 耗时。C/D 包括溶剂、离子，以及选留的 ESP/POLAR。100% Hessian 指现 --hess；10% 指独立 scratch --ohess，OHess 优化几何不会覆盖原 PM7 坐标。超时计入已花费预算，不能视为已获得成功标签的完整成本。', '',
        'Hessian 人口分层混合：原 1,424 成功分子部分使用 fresh100 的分层加权均值；原 17 超时分子的 --hess 使用各自旧实测已花服务时间，OHess 使用每例 7,200s 的明确规划预算。后者没有 fresh OHess 观测，也不是成功完成时间或验证上界。层内混合完成后再外推人口、再乘一次分配开销因子；C2 使用同一 OHess 基础成本。', '',
        'C1/C2 使用实际已消耗服务时间，未以 PROPERTY_FAILED 筛掉 OHess 计时；B3 的非请求 D4 误解析后来已独立核验纠正，因此成本数值与打包保持原关闭结果，不重跑 QM 或成本分析。旧成本 JSON 的原始 call status 保留为 engine 诊断，Hessian 目标可用性以本报告 B3 requested-scope 核验为准。', '',
        table(['保留集', 'POLAR', 'ESP', 'Hessian', 'C/D', '服务核时', '校准分配核时', '696 CPU 墙钟h'], [
            [r['retained'], r['POLAR'], r['ESP'], r['Hessian'], r['CD_scope'],
             fmt(r['service_core_hours'], 1), fmt(r['allocated_core_hours_old_pilot_calibrated'], 1),
             fmt(r['wall_hours_at696_old_pilot_calibrated'], 2)] for r in scenarios]), '',
        linked('c_engineering/cost_packing_v3/C1_scenario_matrix.json', '分层成本、分项与外推限制'), '',
        '## C2：实际任务误差与放宽集重新打包', '',
        '真实任务验证留出一个 Slurm 父任务，使用其余 15 个任务的 task×size 均值和 allocated/service 校准预测其 elapsed；包含原 Hessian 与失败/超时已花费预算。另以分子为单位五折留出验证全分子非 Hessian 服务时间，避免同分子构象泄漏。', '',
        table(['实际 job', '实际 elapsed h', '预测 h', '绝对误差 h', '实际/预测'], [
            [r['job_id'], fmt(r.get('actual_elapsed_seconds', 0)/3600),
             fmt(r.get('predicted_elapsed_seconds', 0)/3600), fmt(r.get('absolute_error_seconds', 0)/3600),
             fmt(r.get('actual_over_prediction'))] for r in validation['jobs'] if r['prediction_available']]), '',
        table(['规划统计', 'p50', 'p90', 'p99', 'max'], [
            [name] + [fmt(data[k], 3) for k in ('p50', 'p90', 'p99', 'max')] for name, data in [
                ('实际 pilot 父任务 elapsed（秒）', validation['actual_job_elapsed_seconds']),
                ('实际任务绝对误差（秒）', validation['absolute_prediction_error_seconds']),
                ('实际任务 实际/预测', validation['actual_over_prediction']),
                ('实测单分子非Hessian服务（秒）', packing['prediction_validation']['actual_molecule_service_seconds']),
                ('实测>40重原子单分子非Hessian服务（秒）', packing['prediction_validation']['heavy_gt40_actual_molecule_service_seconds']),
                ('分子验证 实际/预测', packing['prediction_validation']['actual_over_prediction']),
                ('打包任务最长lane（h）', packing['planned_job_wall_hours']),
                ('打包任务核时', packing['planned_job_core_hours'])]]), '',
        f"重新打包 {packing['packed_molecules']:,} 个分子，{packing['tasks']:,} 个任务；另单列超 24h 的全分子 {len(packing['oversized_molecules_requiring_chunk_resume_or_intramolecule_parallelism']):,} 个，完整人口计数闭合。单分子不跨文件，工程纳入 unassigned 仅用于预算，不代表准入 TRAIN。", '',
        f"C1 的均值服务成本经旧开销校准为 {fmt(candidate['wall_hours_at696_old_pilot_calibrated'], 3)} h；C2 另加入 p90 分子预测残差膨胀 {fmt(packing['p90_residual_inflation'], 6)} 及大尺寸外推，合计规划 {fmt(planned_core_hours, 3)} 核时，除以 696 为 {fmt(planned_core_hours/696, 3)} h。将已生成的 {packing['tasks']} 个任务按其最长 lane 时长分配至 29 个 k24 槽位，纯排程模型 makespan 约 {fmt(planned_slot_makespan, 3)} h（不含排队、失败重试，未实际运行正式轮）。这些口径分列，不能把 C1 的均值容量时间当作含保守余量与尾部的任务排程时间。", '',
        '24h 的候选 elapsed 上界没有得到直接实验保证。新放宽人口有旧 pilot 未覆盖的几何/尺寸；超出实测原子数使用三次方外推只是规划假设。最耗时实测分子与最大候选分子、超限清单如下：', '',
        '```json\n' + json.dumps({'maximum_observed_molecule': packing['prediction_validation']['maximum_observed_molecule'],
            'maximum_candidate_molecule': packing['maximum_candidate_molecule'],
            'oversized': packing['oversized_molecules_requiring_chunk_resume_or_intramolecule_parallelism']}, ensure_ascii=False, indent=2) + '\n```', '',
        linked('c_engineering/cost_packing_v3/C2_actual_task_validation.json', '16 个实际任务验证') + '；' +
        linked('c_engineering/cost_packing_v3/C2_job_distribution.json', '完整打包分布与模型假设') + '；' +
        linked('c_engineering/cost_packing_v3/C2_relaxed_candidate_task_manifest.parquet', '候选全分子任务清单'), '',
        '## C3：六个设计分片的节点测试', '',
        (ROOT / 'reports/c_engineering_summary_v3.md').read_text().replace('全13项总报告', '全部15项总报告'), '',
        io_appendix(engineering), '',
        '## C4、C5：存储、归档与几何一致性', '',
        (ROOT / 'reports/c_engineering_appendix_v2.md').read_text()
            .replace('| strict | ALL | MOLECULAR_MINIMUM |', '| strict | 保留ESP/仅最低(随C-D) | MOLECULAR_MINIMUM |')
            .replace('| relaxed | ALL | MOLECULAR_MINIMUM |', '| relaxed | 保留ESP/仅最低(随C-D) | MOLECULAR_MINIMUM |'), '',
        'C4 比率模型里的 ESP_scope=ALL 表示保留该任务；当 C/D=MOLECULAR_MINIMUM 时，ESP 同样仅最低构象，不能把该行当作 ESP 全构象。旧 JSON 元信息保留原测量口径，本报告作此语义澄清。', '',
        f"最新账户可用 {free_quota_bytes/1e12:.6f} TB。保留完整已测 C/D 与全部非 Hessian xTB 标签、成功普通 raw 只留最低且失败全留的保守峰值：无 Hessian {conservative_peaks[0]['projected_new_writeback_peak_bytes']/1e12:.6f} TB（余 {conservative_peaks[0]['headroom_vs_final_quota_bytes']/1e9:.3f} GB）；10%旧 Hessian存储比例 {conservative_peaks[.1]['projected_new_writeback_peak_bytes']/1e12:.6f} TB（余 {conservative_peaks[.1]['headroom_vs_final_quota_bytes']/1e9:.3f} GB）；100% {conservative_peaks[1]['projected_new_writeback_peak_bytes']/1e12:.6f} TB（余 {conservative_peaks[1]['headroom_vs_final_quota_bytes']/1e9:.3f} GB）。100%完整候选超当前额度；C/D最低与去ESP的可选字节估计已分列，属于比率模型。", '',
        '这里按旧 --hess 字段/主输出归档估计 Hessian 存储比例。正式采用 --ohess 时，优化坐标、RMSD/能量差与 geometry context 应按新的字段格式纳入；100例诊断 normal_modes 向量已经保存，本模型没有默认把全量模式向量作为新训练标签。', '',
        '## 清理与最终可用空间', '',
        '临时 xyz 已在 C5 逐次删除；C4 没有建立临时 LMDB，序列化样本使用内存中的 blob。结束后检查六组 C3 均只有首轮/预算截断轮，额外重复归档清理候选为 0，因此没有为凑清理量删除必要证据。首轮、失败/超时/property-failed 输出、所有科学结果和诊断保留；归档字节与 SHA 测量已先完成。', '',
        '```json\n' + json.dumps({'cleanup': cleanup, 'final_quota': quota}, ensure_ascii=False, indent=2) + '\n```', '',
        '## 证据与提交状态', '',
        '科学不收敛、元素不支持、缺失字段和空白 sacct MaxRSS 均作为结果记录。一个离线 ESP reporter 因 pyarrow 环境缺失启动失败后仅修正环境；未重复其 QM。原节点 15/16 排队任务依用户授权取消并由 12/13 补测。没有修改其他用户的任务。', '',
        linked('reports/final_job_snapshot.json', '最终 Slurm 状态') + '；' + linked('reports/C3_substitution_authority.json', '节点替代授权') + '；' +
        linked('reports/authority.json', '原始物理人口与任务文档绑定') + '；' + linked('reports/screening_report_evidence.json', '本报告输入绑定'), '',
        '请先确定正式配置，再更新工作计划；lmdb_1 字段格式随后单独讨论。']
    text = ('\n'.join(lines) + '\n').replace('](/share/home/zixiao/descriptor_analysis/', '](X:/')
    evidence = {'status': 'ALL_15_SCREENING_ITEMS_REPORTED', 'generated_UTC': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'items': [row[0] for row in arows], 'original_LMDB_read_only': True, 'lmdb_1_created': False,
        'configuration_adopted': False, 'sources': [{'path': str(ROOT / p),
            'sha256': hashlib.sha256((ROOT / p).read_bytes()).hexdigest(), 'bytes': (ROOT / p).stat().st_size} for p in paths]}
    output = ROOT / 'reports/screening_report.md'
    output.write_text(text)
    evidence['report_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    (ROOT / 'reports/screening_report_evidence.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'status': evidence['status'], 'path': str(output), 'bytes': output.stat().st_size, 'sha256': evidence['report_sha256']}))


if __name__ == '__main__':
    main()
