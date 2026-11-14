"""Render the final taskbook REPORT from completed study outputs, once ready.

No training, probe fitting, bootstrap resampling or intermediate hashes run here.
Only the final T2/T3/T4 checkpoints receive new SHA256 values.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    with Path(path).open(newline='') as stream:
        return list(csv.DictReader(stream))


def number(value):
    return '—' if value in (None, '', 'None') else f'{float(value):.8g}'


def table(headers, values):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(map(cell, headers)) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in values])


def link(path, label=None):
    path = Path(path)
    relative = os.path.relpath(path, REPO / 'docs/p_recipe').replace(os.sep, '/')
    return f'[{label or path.name}]({relative})'


def key(row):
    return tuple(str(row.get(name, 'MEAN' if name == 'task' else ''))
                 for name in ('purpose', 'round', 'readout', 'task', 'A', 'B'))


def comparison_table(comparisons, purpose, delta_source, line_numbers):
    selected = [row for row in comparisons if row['purpose'] == purpose]
    return table(['读出', '任务', 'A − B', 'Δ', '95% CI', '判定', '证据'],
                 [[row['readout'], row.get('task', 'MEAN'), row['A'] + ' − ' + row['B'],
                   number(row['delta']), f"[{number(row['ci_lower'])}, {number(row['ci_upper'])}]",
                   row['verdict'], link(delta_source, 'deltas.csv')[:-1] + f'#L{line_numbers[key(row)]})']
                  for row in selected])


def parameter_appendix(paths):
    sections = []
    for path in sorted(paths):
        fitted = read(path)
        sections.extend([f'### {path.stem}', '',
                         f"完整精度参数：{link(path)}。拟合角色 {fitted['fit_role']}，"
                         f"分子数 {fitted['fit_molecules']}，随机种子 {fitted['fit_seed']}。", ''])
        normalizations = fitted['normalizations']
        element_rows = []
        for name, counts in sorted(fitted['fit'].items()):
            if 'A1_molecules' not in counts:
                continue
            spec = normalizations[name]
            reference = spec['element_reference']
            # A5 moves a composed residual's reference to its reversible offset.
            if reference is None:
                reference = fitted['heavy_tail'][name]['offset_reference']
            coefficients = ', '.join(f'Z{z}:{coefficient:.12g}' for z, coefficient in
                                     zip(reference['basis'], reference['coefficients']))
            element_rows.append([name, counts['A1_molecules'], coefficients,
                                 f"{reference['intercept']:.12g}", number(spec['center']), number(spec['scale'])])
        if element_rows:
            sections.extend([table(['A1字段', '有效分子', '元素系数（按原子序数）', '截距', '中心', '尺度'], element_rows), ''])
        differences = fitted['state_difference']
        if differences:
            sections.extend([table(['A2状态字段', '对应中性字段', '中心', '尺度'],
                                   [[name, neutral, number(normalizations[name]['center']), number(normalizations[name]['scale'])]
                                    for name, neutral in sorted(differences.items())]), ''])
        tails = fitted['heavy_tail']
        if tails:
            sections.extend([table(['A5字段', 'm', '先扣元素参考', '中心', '尺度'],
                                   [[name, f"{spec['m']:.12g}", '是' if spec['offset_reference'] else '否',
                                     number(normalizations[name]['center']), number(normalizations[name]['scale'])]
                                    for name, spec in sorted(tails.items())]), ''])
    return '\n'.join(sections)


def scaling_plot(configs, summaries, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    counts = [250000, 500000, read(configs['T2']['corpus'])['train_molecules']]
    fig, ax = plt.subplots(figsize=(6.4, 4.0), layout='constrained')
    for readout, color in (('R3', '#c75b12'), ('R1', '#2367a5')):
        results = [summaries[arm][readout] for arm in ('T5', 'T6', 'T2')]
        ax.plot(counts, [result['mean_normalized_improvement'] for result in results],
                marker='o', color=color, label=readout)
        for count, result in zip(counts, results):
            if result['bootstrap_ci'] is not None:
                ax.vlines(count, *result['bootstrap_ci'], color=color, linewidth=1.3)
    ax.set(xlabel='Training molecules (nested subsets)', ylabel='Mean normalized improvement',
           title='Fixed 4.5M training samples; molecular bootstrap 95% CI', xticks=counts,
           xticklabels=[f'{count:,}' for count in counts])
    ax.grid(alpha=.2)
    ax.legend()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, format='svg', metadata={'Date': None})
    plt.close(fig)


def render(plan, verdict, states, selection, code_commit):
    configs = {read(path)['arm']: read(path) for path in plan['configurations']}
    summaries = {arm: read(Path(c['output']) / 'readout/scores.json') for arm, c in configs.items()}
    results = REPO / plan.get('results_directory', 'results/p_recipe')
    delta_source = results / 'deltas.csv'
    line_numbers = {key(row): index for index, row in enumerate(rows(delta_source), 2)}
    all_scores = rows(REPO / 'results/p_recipe/scores.csv')
    score_index = {(row['run'], row['readout'], row['task'], int(row['samples'])): row for row in all_scores}
    configurations = []
    for state in states:
        for evidence in state['component_evidence'].values():
            path = evidence['configuration']
            if path not in configurations:
                configurations.append(path)
    parameter_paths = {REPO / 'configs/p_recipe/label_parameters' / ('PM7_' + arm + '.json')
                       for arm in ('A1', 'A2', 'A5')}
    for configuration in list(configs.values()) + [read(path) for path in configurations]:
        if configuration.get('label_parameters'):
            parameter_paths.add(REPO / 'configs/p_recipe/label_parameters' / Path(configuration['label_parameters']).name)
    chosen = configs[verdict['final_arm']]
    clips = {arm: read(Path(c['output']) / 'clip_calibration.json')['threshold']
             for arm, c in configs.items()}
    family_losses = {arm: {row['family']: row['loss'] for row in
                          rows(REPO / 'results/p_recipe/training' / configs[arm]['run'] / 'family_losses.csv')
                          if row['kind'] == 'VAL_fixed2000' and int(row['samples']) == 4500000}
                     for arm in ('T1', 'T2', 'T3')}
    panel = read(REPO / 'configs/dev_panel_v3.json')['tasks']
    full_count = verdict['full_TRAIN_molecules']
    final_config = Path(verdict['runnable_configuration'])
    content = ['# P 预训练配方研究：最终交付', '',
               f"最终配方为 **{verdict['final_arm']}**，组件：{', '.join(verdict['final_components']) or 'B0，无新增组件'}。"
               f"可运行配置：{link(final_config)}。研究修订：`{verdict['study_revision']}`。", '',
               table(['最终实际batch', '最终学习率', '逐层重算', '头', '配方开关'],
                     [[chosen['batch_size'], f"{chosen['lr']:g}", chosen.get('activation_checkpointing', False),
                       chosen['head_form'], json.dumps(chosen['p_recipe'], ensure_ascii=False, sort_keys=True)]]), '',
               '旧1.5M首轮结论已按用户要求作废，旧第二轮停止；旧输出只作历史记录，未用于本次配方选择。', '',
               '## 校准及固定设置', '',
               f"四组各3M的校准按最高3M R3选中 `{selection['winner_group']}`："
               f"batch={selection['batch_size']}，lr={selection['lr']:g}，"
               f"逐层重算={selection['activation_checkpointing']}；新筛选预算为 {selection['screening_samples']:,} 样本。"
               f"预算观测来源：`{selection['observation_source']}`。", '',
               link(REPO / 'results/p_recipe/calibration_20261114/calibration.csv', '完整校准表') + '；' +
               link(REPO / 'results/p_recipe/calibration_20261114/throughput.csv', '逐卡1000步实测吞吐') + '。', '',
               f"全量TRAIN为 {full_count:,} 分子，排除323个重叠分子；VAL为7567。"
               '整个研究固定使用 window2_TRAIN_normalization_parameters_20261107_v1，不重拟合基础归一化。'
               '主干C1-0：512维、6层、8头、FFN宽2d、FP32、TF32关闭，PM7几何下单独P/clean视图。'
               '先均匀抽分子，再均匀抽构象，每分子最多10个构象。', '',
               'AdamW betas=(0.9,0.95)、wd=0.01；各运行在自己的样本预算内执行完整cosine退火，warmup 2%，种子0。'
               '裁剪阈值在每条运行前5%样本内以281.7作初始值，记录裁剪前梯度范数，随后冻结该运行自己的p99。'
               '标准化标量采用Huber δ=1，向量采用radial_huber_v1。每1000更新记录家族损失，每500k样本在固定2000个VAL分子上记录家族损失，均不用于配方选择。', '',
               table(['确认运行', '实际batch', '学习率', '自身前5%范数p99', '标签/几何', 'TRAIN分子数'],
                     [[arm, c['batch_size'], f"{c['lr']:g}", number(clips[arm]), c['source'],
                       c.get('subset_molecules') or full_count] for arm, c in configs.items()]), '',
               '## 放大确认：T1/T2/T3', '',
               table(['运行', '组件', '实际batch/lr', 'R3主分', 'R1副分', 'VAL家族损失'],
                     [[arm, ', '.join(configs[arm]['components']) or 'B0',
                       f"{configs[arm]['batch_size']}/{configs[arm]['lr']:g}",
                       number(summaries[arm]['R3']['mean_normalized_improvement']),
                       number(summaries[arm]['R1']['mean_normalized_improvement']),
                       link(REPO / 'results/p_recipe/training' / configs[arm]['run'] / 'family_losses.csv')]
                      for arm in ('T1', 'T2', 'T3')]), '',
               '逐任务单元格为 R3 / R1；SoM只报告，不进入平均分。', '',
               table(['任务'] + ['T1 R3/R1', 'T2 R3/R1', 'T3 R3/R1'],
                     [[task['task_id']] + [' / '.join(number(score_index[(configs[arm]['run'], readout, task['task_id'], 4500000)]['score'])
                                                               for readout in ('R3', 'R1')) for arm in ('T1', 'T2', 'T3')]
                      for task in panel]), '',
               '固定2000个VAL分子、最终4.5M点的标准化家族P损失：', '',
               table(['家族', 'T1', 'T2', 'T3'],
                     [[family] + [number(family_losses[arm].get(family)) for arm in ('T1', 'T2', 'T3')]
                      for family in sorted(set().union(*(set(value) for value in family_losses.values())))]), '',
               comparison_table(verdict['comparisons'], 'confirmation', delta_source, line_numbers), '',
               comparison_table(verdict['comparisons'], 'final_recipe', delta_source, line_numbers), '',
               ('T2、T3均未按预注册规则胜过T1，结果如实保留。' if verdict['neither_candidate_beats_T1'] else
                '至少一个候选按预注册规则胜过T1；最终配方由T2/T3之间的比较决定。'), '',
               'B0与M2的预算同号检查：`' + json.dumps(verdict['B0_M2_budget_sign'], ensure_ascii=False) + '`。', '',
               '## P与P′对比', '',
               f"P比较臂为 {plan['Pprime_comparator']}，P′为T4；共同启用字段 {len(plan['common_fields'])} 个，"
               f"丢失P字段 {plan['lost_P_fields']} 个（{plan['lost_P_fraction']:.3%}），T7要求为 {plan['T7_required']}。", '',
               comparison_table(verdict['comparisons'], 'P_vs_Pprime', delta_source, line_numbers), '',
               '## 分子数扩展：固定4.5M样本', '',
               table(['分子数', '运行', 'R3主分', 'R1副分', '平均重复次数'],
                     [[f'{count:,}', arm, number(summaries[arm]['R3']['mean_normalized_improvement']),
                       number(summaries[arm]['R1']['mean_normalized_improvement']), number(4500000 / count)]
                      for count, arm in ((250000, 'T5'), (500000, 'T6'), (full_count, 'T2'))]), '',
               comparison_table(verdict['comparisons'], 'molecule_scaling', delta_source, line_numbers), '',
               '子集种子20261112，250k ⊂ 500k ⊂ 全量。分子数减少会提高重复次数；这里只报告，不作扩量决策。', '',
               f"![固定预算分子数曲线]({os.path.relpath(results / 'molecule_scaling.svg', REPO / 'docs/p_recipe').replace(os.sep, '/')})", '',
               '## 全部筛选臂及组件取舍', '']
    experiment_rows = []
    for state in states:
        for arm, decision in state['decisions'].items():
            source = link(delta_source, 'deltas.csv')[:-1] + f"#L{line_numbers[key(decision)]})"
            experiment_rows.append([state['round'], arm, number(decision['delta']),
                                    f"[{number(decision['ci_lower'])}, {number(decision['ci_upper'])}]",
                                    decision['verdict'], '是' if arm in state['adopted_winners'] else '否', source])
    content.extend([table(['轮', '臂', 'ΔR3', '95% CI', '判定', '当轮并入', '证据'], experiment_rows), '',
                    '合并、冲突与停止记录：', '',
                    table(['轮', '合并组件', '合并回退', '累计筛选GPUh', '停止原因'],
                          [[state['round'], ', '.join(state['merged_components']) or 'B0', state['merge_rollback'],
                            number(state['screening_gpu_hours']), '; '.join(state['stop_reasons']) or '继续下一轮']
                           for state in states]), '',
                    '## 评价及统计方法', '',
                    '计分任务为ExpansionRx的LogD、LogS、HLM CLint，以及QM9原子化能、alpha、homo、lumo。'
                    '原子化能为U0减去QM9官方U0原子参考之和。CYP3A4/2D6 SoM只报告。'
                    'R1为mean(H)上的ridge；R3为原子MLP后拼接mean与sum/N_ref再经MLP，下游均读取最终第6层、共享投影器之前的H。', '',
                    '特征标准化前剔除TRAIN标准差低于max(1e-12,1e-4×各维标准差中位数)的维度。'
                    'R3探针TRAIN按分子90/10切分，种子20261112；仅90%上训练30epoch，以内部10%最低误差选epoch，'
                    '不在100%重训。探针AdamW lr1e-3、wd0.01、batch32、种子0。'
                    'E_ref为同协议、同读出的随机C1-0误差，单任务分数(E_ref−E)/E_ref。'
                    'E_ref低于0.05倍标签标准差的任务剔出平均，具体去除标记保留于scores.csv。', '',
                    '主分为有效计分任务R3均值，副分为R1均值。按分子配对bootstrap1000次，种子20261025，取95%百分位区间。'
                    'A胜B需ΔR3区间下界>0且Δ≥max(0.01,0.05×max(score_A,score_B))；否则按对称规则判负或平局，平局取更简单配置。'
                    'R1仅报告；R3胜且R1负仍采纳。每轮仅与当轮基线比较，B2/B3及C1/C2冲突时保留Δ较大项；'
                    '合并基线若输给前轮最佳单项则回退。最多3轮、连续两轮无胜项提前结束；新筛选达200GPUh时完成当前轮后停止。'
                    '旧作废筛选、测速及校准成本不混入新筛选预算。', '',
                    '## A1/A2/A5定义及TRAIN拟合参数', '',
                    'A1对尚未扣元素参考的广延分子标量拟合y≈Σc_Z n_Z+b，训练目标取残差；'
                    '已扣参考的字段不重复扣。A2对注册表中相同物理量、同分子/原子/分量取状态值减中性值，且两者掩码均有效；'
                    '反变换加回中性值。A5取t=sign(r)·log1p(|r|/m)，反变换为r=sign(t)·m·expm1(|t|)，'
                    'm为TRAIN绝对目标中位数，r先按既有元素参考/已采纳变换处理。'
                    '组合顺序为状态差、元素参考、重尾、标准化，逆序反变换后报告原单位。', '',
                    '拟合使用清洁TRAIN，种子20261112，默认128000分子，A1每字段至少100000有效分子。'
                    '最小二乘、参考扣除和组合变换采用FP64，模型目标为FP32。向量零中心、同头各分量共用模长的总体标准差；'
                    '重尾向量各分量共用m。下表系数便于阅读，链接JSON保存完整精度及所有对应关系。', '',
                    parameter_appendix(parameter_paths),
                    '## 最终交付标识', '',
                    f'最终代码提交：`{code_commit}`。', '',
                    f"P′及分子数运行采用T2/M3配方。{verdict['repeat_on_T3']}。", '',
                    f"闭合P0证据：{link(REPO / 'docs/p_recipe/P0_SUMMARY.md')}；"
                    f"完整任务评分：{link(REPO / 'results/p_recipe/scores.csv')}；"
                    f"本修订配对比较：{link(delta_source)}。", ''])
    return '\n'.join(content), configs, summaries, results


def checkpoint_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(16 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--verdict', required=True)
    parser.add_argument('--states', nargs='+', required=True)
    parser.add_argument('--selection', required=True)
    parser.add_argument('--code-commit', required=True)
    parser.add_argument('--output', default=str(REPO / 'docs/p_recipe/REPORT.md'))
    args = parser.parse_args()
    content, configs, summaries, results = render(read(args.plan), read(args.verdict),
                                                [read(path) for path in args.states],
                                                read(args.selection), args.code_commit)
    scaling_plot(configs, summaries, results / 'molecule_scaling.svg')
    hashes = [[arm, checkpoint_sha(Path(configs[arm]['output']) / 'samples_4500000.pt')]
              for arm in ('T2', 'T3', 'T4')]
    content += '\n' + table(['最终检查点', 'SHA256'], hashes) + '\n'
    Path(args.output).write_text(content)
    print(json.dumps(dict(report=args.output, scaling_figure=str(results / 'molecule_scaling.svg'),
                          checkpoint_hashes=dict(hashes)), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
