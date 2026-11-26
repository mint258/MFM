"""Render the final taskbook REPORT from completed study outputs, once ready.

No training, probe fitting, bootstrap resampling or intermediate hashes run here.
Only the actual final candidate checkpoints receive new SHA256 values.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from final_comparisons import completed_configurations,CLOSEOUT

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
                   '仅描述' if row['verdict']=='descriptive' else row['verdict'],
                   link(delta_source, 'deltas.csv')[:-1] + f'#L{line_numbers[key(row)]})']
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
           title=f"Fixed {configs['T2']['samples']/1e6:g}M training samples; molecular bootstrap 95% CI", xticks=counts,
           xticklabels=[f'{count:,}' for count in counts])
    ax.grid(alpha=.2)
    ax.legend()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, format='svg', metadata={'Date': None})
    plt.close(fig)


def screening_rows(states, delta_source, line_numbers):
    result = []
    for state in states:
        for arm, decision in state['decisions'].items():
            source = link(delta_source, 'deltas.csv')[:-1] + f"#L{line_numbers[key(decision)]})"
            result.append([state['round'], arm, number(decision['delta']),
                           f"[{number(decision['ci_lower'])}, {number(decision['ci_upper'])}]",
                           decision['verdict'], '是' if arm in state['adopted_winners'] else '否', source])
        for arm, entry in state.get('unresolved_arms', {}).items():
            reason = entry if isinstance(entry, str) else entry['reason']
            result.append([state['round'], arm, '—', '—', '未解决', '否', reason])
        for arm, reason in state.get('skipped_arms', {}).items():
            result.append([state['round'], arm, '—', '—', '条件未触发', '否', reason])
        if state['round'] == 4:
            decision = state['PP_comparison']['comparison']
            source = link(delta_source, 'deltas.csv')[:-1] + f"#L{line_numbers[key(decision)]})"
            result.append([4, 'PP', number(decision['delta']),
                           f"[{number(decision['ci_lower'])}, {number(decision['ci_upper'])}]",
                           decision['verdict'], '数据来源比较，不并入配方', source])
    return result


def round4_sections(state, delta_source, line_numbers):
    if state is None:
        return []
    if not state.get('merge_validation_complete'):
        raise ValueError('The final report waits for the registered round4 merge decision')
    pp = state['PP_comparison']
    content = ['## 第4轮：扰动信号、多保真度及3M P/Pprime', '',
               f"字段配对、未配对原因和P/Pprime交集：{link(REPO / 'docs/p_recipe/ROUND4_METHODS.md')}。"
               '本轮每条3M，以M2为基线；按11-19指示，仅seed0 WIN补seed1，真实训练问题例外另记，最多两个种子。PP单独比较数据来源，不作为配方组件。', '',
               'X1/F2平局时，仅在R3的CI包含0时采纳更简单的去掉项；CI整体为负时保留原项。X2/F1平局不采纳。X1/X2、F1/F2互斥，按Δ较大项取舍。'
               '下表保留原始胜负判定，最终并入项同时受M3合并比较约束。', '',
               table(['PP运行', '对照运行', 'R3 Δ', '95% CI', '最小效应', 'M2两种子R3差', '9M-T4决定'],
                     [[pp['run'], pp['control_run'], number(pp['comparison']['delta']),
                       f"[{number(pp['comparison']['ci_lower'])}, {number(pp['comparison']['ci_upper'])}]",
                       number(pp['minimum_effect']), number(pp['noise_R3_difference']),
                       pp.get('T4_user_decision',pp.get('recommendation','—'))]]), '',
               '按18B预授权，PP的CI不含0、|Δ|达到最小效应且超过M2两种子R3差时，自动省略9M-T4；否则保留。', '',
               table(['M3组件', '第4轮候选', '需3M合并比较', '最终组件', '合并验证完成'],
                     [[', '.join(state['merge_base_components']), ', '.join(state['screening_candidates']) or '无',
                       state['merge_required'], ', '.join(state['merged_components']), state['merge_validation_complete']]]), '']
    if state.get('merge_decision'):
        content.extend([comparison_table([state['merge_decision']], 'round4_merge', delta_source, line_numbers), ''])
    return content


def closeout_sections(plan):
    if plan.get('selection_authority')!=CLOSEOUT:
        return []
    lines=plan.get('external_line_decisions',{})
    if not plan.get('external_line_decisions_complete') or not {'heads','decoupling'}<=set(lines):
        raise ValueError('Final report requires both published side-line dispositions')
    summary=[];details=[]
    def source(value):
        return f'[正式判定]({value})' if str(value).startswith('https://') else str(value)
    for name,evidence in lines.items():
        summary.append([name,evidence['status'],', '.join(evidence.get('adopted_components',[])) or '无',source(evidence.get('source','—'))])
        for decision in evidence.get('component_decisions',[]):
            details.append([name,decision['arm'],decision.get('seed_count',0),number(decision.get('delta')),
                            json.dumps(decision.get('seed_CI',[]),ensure_ascii=False),decision['verdict'],
                            '是' if decision.get('adopted') else '否',source(decision.get('source',evidence.get('source','—')))])
    return ['## 最终配方冻结与侧线交接','',
            '第4轮为最后一轮筛选。两条侧线按各自原预注册规则产生的两种子胜出项直接合并；未完成者按记录的最终未解决处置不并入。'
            '本线不重判侧线、不另开验证轮；head类型线已规定的自身确认仍由该线完成。9M在全部判定与合并后冻结配方，T3/T7取消。','',
            table(['线路','最终状态','并入组件','证据'],summary),'',
            table(['线路','臂','种子数','原平均Δ','原各种子CI','原判定','并入','证据'],details),'']


def seed_sections(states,verdict):
    scores=[];decisions=[]
    for state in [*states,verdict]:
        for result in (state.get('seed_comparisons') or {}).get('comparisons',{}).values():
            if not result.get('ready'):raise ValueError('A required paired seed decision is incomplete')
            identity=f"{result['purpose']} / round{result['round']}"
            for seed,pair in result.get('per_seed_scores',{}).items():
                scores.append([identity,result['A'],result['B'],seed,
                    number(pair['A']['R3']),number(pair['B']['R3']),
                    number(pair['A']['R1']),number(pair['B']['R1'])])
            evidence=result['evidence']['R3'];decision=evidence['decision']
            decisions.append([identity,result['A'],result['B'],evidence['seed_count'],
                number(evidence['mean_score_A']),number(evidence['mean_score_B']),
                number(decision['delta']),f"[{number(decision['ci_lower'])}, {number(decision['ci_upper'])}]",
                result['rows'][0]['verdict']])
    return ['## 条件种子比较的实际证据','',
        '下表列出每条比较实际使用的seed及原始主副分；两种子比较的点估计为配对差值均值。'
        '分子数缩放只使用seed0，逐任务P/Pprime结果亦为seed0描述，不触发额外种子。','',
        table(['比较','A','B','seed','A R3','B R3','A R1','B R1'],scores),'',
        table(['比较','A','B','种子数','平均A R3','平均B R3','平均ΔR3','95% CI','判定'],decisions),'']


def render(plan, verdict, states, selection, code_commit, *, require_external_A4=True):
    supplemental_section = ''
    if (REPO / 'docs/p_recipe/USER_DIRECTIVE_20261122B.md').is_file():
        from final_report_22B import require_closed, render_sections
        supplemental_section = render_sections(REPO, require_closed(REPO,require_external_A4=require_external_A4),include_external_A4=require_external_A4)
    closeout=plan.get('selection_authority')==CLOSEOUT
    budget_section = ''
    if closeout and (REPO / 'docs/p_recipe/USER_DIRECTIVE_20261121.md').is_file():
        from budget_curve_report import report_section
        budget_section = report_section()
    if closeout and (not plan.get('conditional_seed_decisions_complete') or not verdict.get('conditional_seed_decisions_complete')):
        raise ValueError('The final report waits for all registered conditional second-seed decisions')
    configs = completed_configurations(plan)
    main_arms=tuple(arm for arm in ('T1','T2','T3') if arm in configs)
    round4 = next((state for state in states if state['round'] == 4), None)
    if plan.get('selection_round') == 4 and (round4 is None or not round4.get('merge_validation_complete')):
        raise ValueError('The registered round4 decision is required for the final report')
    confirmation_samples = plan.get('samples_per_run', configs['T2']['samples'])
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
                          if row['kind'] == 'VAL_fixed2000' and int(row['samples']) == confirmation_samples}
                     for arm in main_arms}
    panel = read(REPO / 'configs/dev_panel_v3.json')['tasks']
    full_count = verdict['full_TRAIN_molecules']
    final_config = Path(verdict['runnable_configuration'])
    fixed_description=(f"用户固定配置：batch={selection['batch_size']}，lr={selection['lr']:g}，逐层重算关闭；"
                       f"原三轮及注册第4轮筛选均{selection['screening_samples']:,}样本，确认{confirmation_samples:,}样本。"
                       "既有G1按用户要求原样完成并复用为B0，旧裁剪窗口作为明确例外记录。") if selection.get('selection_method')=='user_fixed' else (
                       f"校准选中{selection['winner_group']}；batch={selection['batch_size']}，lr={selection['lr']:g}；筛选{selection['screening_samples']:,}样本。")
    content = ['# P 预训练配方研究：最终交付', '',
               f"最终配方为 **{verdict['final_arm']}**，组件：{', '.join(verdict['final_components']) or 'B0，无新增组件'}。"
               f"可运行配置：{link(final_config)}。研究修订：`{verdict['study_revision']}`。", '',
               table(['最终实际batch', '最终学习率', '逐层重算', '头', '配方开关'],
                     [[chosen['batch_size'], f"{chosen['lr']:g}", chosen.get('activation_checkpointing', False),
                       chosen['head_form'], json.dumps(chosen['p_recipe'], ensure_ascii=False, sort_keys=True)]]), '',
               ('复现此配置时，GPU任务执行训练及原R1/R3读出；`statistics_backend=slurm_cpu`把最终bootstrap交给CPU节点8–19。'
                'GPU成功退出后，在CPU节点以同一配置执行`tools/p_recipe/cpu_statistics.py --finalize-configuration <配置路径>`，'
                '统计复用已有探针预测和已完成结果。现有队列由登录节点的`collect_execution.py`查询Slurm并派发该CPU后处理；'
                'CPU节点上的后处理写出完整R1/R3评分后，本运行才标为COMPLETE。'
                if chosen.get('statistics_backend')=='slurm_cpu' else ''), '',
               '旧1.5M首轮结论已按用户要求作废，旧第二轮停止；旧输出只作历史记录，未用于本次配方选择。', '',
               '## 校准及固定设置', '',
               fixed_description, '',
               link(REPO / 'results/p_recipe/calibration_20261114/calibration.csv', '完整校准表') + '；' +
               link(REPO / 'results/p_recipe/calibration_20261114/throughput.csv', '逐卡1000步实测吞吐') + '。', '',
               f"全量TRAIN为 {full_count:,} 分子，排除323个重叠分子；VAL为7567。"
               '整个研究固定使用 window2_TRAIN_normalization_parameters_20261107_v1，不重拟合基础归一化。'
               '主干C1-0：512维、6层、8头、FFN宽2d、FP32、TF32关闭，PM7几何下单独P/clean视图。'
               '先均匀抽分子，再均匀抽构象，每分子最多10个构象。'
               'P′采用数据方M18前二资格并排除M14留出，包含M17之外的P′专用几何；'
               '固定随机采样且资格数不超过k时，从全部合格成员中均匀抽一个，不用普通S′排列截断。', '',
               'AdamW betas=(0.9,0.95)、wd=0.01；各运行在自己的样本预算内执行完整cosine退火，warmup 2%，种子0。'
               '新运行前150000样本以281.7作初始裁剪，按步起点60000≤samples<150000收集裁剪前范数；保持完整32批，在150016样本边界冻结自身p99，此后只报告不调整。'
               '标准化标量采用Huber δ=1，向量采用radial_huber_v1。每1000更新记录家族损失，每500k样本在固定2000个VAL分子上记录家族损失，均不用于配方选择。', '',
               table(['确认运行', '实际batch', '学习率', '自身60k–150k范数p99', '标签/几何', 'TRAIN分子数'],
                     [[arm, c['batch_size'], f"{c['lr']:g}", number(clips[arm]), c['source'],
                       c.get('subset_molecules') or read(c['corpus'])['train_molecules']] for arm, c in configs.items()]), '',
               '## 放大确认：'+'/'.join(main_arms), '',
               table(['运行', '组件', '实际batch/lr', 'R3主分（seed0）', 'R1副分（seed0）', 'VAL家族损失'],
                     [[arm, ', '.join(configs[arm]['components']) or 'B0',
                       f"{configs[arm]['batch_size']}/{configs[arm]['lr']:g}",
                       number(summaries[arm]['R3']['mean_normalized_improvement']),
                       number(summaries[arm]['R1']['mean_normalized_improvement']),
                       link(REPO / 'results/p_recipe/training' / configs[arm]['run'] / 'family_losses.csv')]
                      for arm in main_arms]), '',
               '逐任务单元格为seed0的 R3 / R1；SoM只报告，不进入平均分。9M确认的所有配对判定均只用seed0，不补seed1。', '',
               table(['任务'] + [arm+' R3/R1' for arm in main_arms],
                     [[task['task_id']] + [' / '.join(number(score_index[(configs[arm]['run'], readout, task['task_id'], confirmation_samples)]['score'])
                                                               for readout in ('R3', 'R1')) for arm in main_arms]
                      for task in panel]), '',
               f'固定2000个VAL分子、最终{confirmation_samples/1e6:g}M点的标准化家族P损失：', '',
               table(['家族']+list(main_arms),
                     [[family] + [number(family_losses[arm].get(family)) for arm in main_arms]
                      for family in sorted(set().union(*(set(value) for value in family_losses.values())))]), '',
               comparison_table(verdict['comparisons'], 'confirmation', delta_source, line_numbers), '',
               *([] if closeout else [comparison_table(verdict['comparisons'], 'final_recipe', delta_source, line_numbers), '']),
               (('T2未按预注册规则胜过T1，结果如实保留；配方在9M前已冻结，不追加筛选。' if verdict['neither_candidate_beats_T1'] else
                 'T2按预注册规则胜过T1；配方在9M前已冻结，不追加筛选。') if closeout else
                'T2、T3均未按预注册规则胜过T1，结果如实保留。' if verdict['neither_candidate_beats_T1'] else
                '至少一个候选按预注册规则胜过T1；最终配方由T2/T3之间的比较决定。'), '',
               'B0与M2的预算同号检查：`' + json.dumps(verdict['B0_M2_budget_sign'], ensure_ascii=False) + '`。', '',
               '## P与P′对比', '',
               (f"P比较臂为 {plan['Pprime_comparator']}，P′为T4，实际共同启用字段 {len(configs['T4'].get('fields', plan['common_fields']))} 个。"
                if 'T4' in configs else '9M T4已按记录的预授权决定省略；P与Pprime保留第4轮3M PP结果，不构造9M对比。'
                f"用户确认：{plan['T4_user_confirmation']}。"), '',
               f"原始P/Pprime共同字段 {len(plan['common_fields'])} 个，丢失P字段 {plan['lost_P_fields']} 个"
               f"（{plan['lost_P_fraction']:.3%}），T7要求为 {plan['T7_required']}。", '',
               comparison_table(verdict['comparisons'], 'P_vs_Pprime', delta_source, line_numbers), '',
               f'## 分子数扩展：固定{confirmation_samples/1e6:g}M样本', '',
               table(['分子数', '运行', 'R3主分', 'R1副分', '平均重复次数'],
                     [[f'{count:,}', arm, number(summaries[arm]['R3']['mean_normalized_improvement']),
                       number(summaries[arm]['R1']['mean_normalized_improvement']), number(confirmation_samples / count)]
                      for count, arm in ((250000, 'T5'), (500000, 'T6'), (full_count, 'T2'))]), '',
               comparison_table(verdict['comparisons'], 'molecule_scaling', delta_source, line_numbers), '',
               '子集种子20261112，250k ⊂ 500k ⊂ 全量。T5/T6及全量缩放点使用seed0，分子数减少会提高重复次数；只作描述，不判胜负、不补种子或作扩量决策。', '',
               f"![固定预算分子数曲线]({os.path.relpath(results / 'confirmation/molecule_count_scaling.png', REPO / 'docs/p_recipe').replace(os.sep, '/')})", '',
               '## 全部筛选臂及组件取舍', '']
    if closeout:content.extend(seed_sections(states,verdict))
    experiment_rows = screening_rows(states, delta_source, line_numbers)
    content.extend([table(['轮', '臂', 'ΔR3', '95% CI', '判定', '当轮并入', '证据'], experiment_rows), '',
                    '合并、冲突与停止记录：', '',
                    table(['轮', '合并组件', '合并回退', '累计筛选GPUh', '停止原因'],
                          [[state['round'], ', '.join(state['merged_components']) or 'B0', state.get('merge_rollback', False),
                            number(state['screening_gpu_hours']), '; '.join(state.get('stop_reasons', [])) or
                            ('注册第4轮及所需合并比较完成' if state['round'] == 4 else '继续下一轮')]
                           for state in states]), '',
                    *round4_sections(round4, delta_source, line_numbers),
                    *closeout_sections(plan),
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
                    '合并基线若输给前轮最佳单项则回退。200GPUh筛选上限已按2026-11-17用户补充指示取消。'
                    '第4轮由11-18指示注册，X1/X2/F1/F2对照M2；M3不同于M2时，新增组件须经M3上的3M合并比较胜出后采纳。'
                    '旧作废筛选、测速及校准成本不混入新筛选预算。'
                    'M2 seed1作为噪声描述及已有配对参考供各线复用，不重训对照。'
                    '11-19起3M筛选仅seed0 WIN补seed1，真实训练问题例外另记；全部9M只用seed0，不补任何种子。'
                    '两种子点估计取配对Δ均值，各自原1000个分子bootstrap差值等权拼接为2000个差值，取95%分位CI；'
                    '阈值使用两种子平均分，原胜负规则不变。R1及逐任务结果只报告，不额外触发训练。', '',
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
                    '## 资源与成本', '',
                    link(REPO / 'docs/p_recipe/COST.md', '完整成本及历史会计口径') + '；' +
                    link(results / 'cost_current.json', '本次最终成本明细') + '。', '',
                    'GPU时间按实际原生运行及Slurm执行区间记账，保留失败与取消成本，'
                    '完整状态接管的重叠区间不重复计入；CPU拟合、统计、测试和导出另列。'
                    '历史缺失区间和耗时下界仍按原记录报告，不将未知成本当作零。', '',
                    table(['确认卡型', '实测样本/秒', '整卡平均功耗/W', '功耗采样数'],
                          [[row['gpu_type'], number(row['samples_per_second']),
                            number(row['mean_whole_board_power_watts']), row['power_observations']]
                           for row in rows(results / 'hardware_confirmation.csv')]), '',
                    link(results / 'hardware_confirmation.csv', '原自然训练遥测汇总') + '。'
                    '功耗为整卡采样均值、包含共用上下文；各配方和共用条件不同，'
                    '不据此作卡型的因果比较，未额外运行GPU测速。', '',
                    '## 最终交付标识', '',
                    f'最终代码提交：`{code_commit}`。', '',
                    f"已保留的P′及分子数运行采用T2的最终合并配方。{verdict['repeat_on_T3']}。", '',
                    f"闭合P0证据：{link(REPO / 'docs/p_recipe/P0_SUMMARY.md')}；"
                    f"完整任务评分：{link(REPO / 'results/p_recipe/scores.csv')}；"
                    f"本修订配对比较：{link(delta_source)}。", ''])
    return '\n'.join(content + [budget_section, supplemental_section]), configs, summaries, results


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
    if Path(args.output).exists():
        raise FileExistsError('Final REPORT already exists; do not generate it twice')
    sealed = REPO / 'results/p_recipe/independent_delivery_20261126.json'
    if sealed.is_file():
        from independent_delivery import assemble_final
        content = assemble_final(REPO, read(sealed), args.code_commit)
        with Path(args.output).open('x') as stream:
            stream.write(content)
        print(json.dumps(dict(report=args.output,source='original sealed P sections plus actual A4',
                              checkpoint_hashes_reused=True,new_scientific_computation=False)),flush=True)
        return
    content, configs, summaries, results = render(read(args.plan), read(args.verdict),
                                                [read(path) for path in args.states],
                                                read(args.selection), args.code_commit)
    scaling_plot(configs, summaries, results / 'molecule_scaling.svg')
    hashes = [[arm, checkpoint_sha(Path(configs[arm]['output']) / f"samples_{configs[arm]['samples']}.pt")]
              for arm in ('T2', 'T3', 'T4') if arm in configs]
    content += '\n' + table(['最终检查点', 'SHA256'], hashes) + '\n'
    Path(args.output).write_text(content)
    print(json.dumps(dict(report=args.output, scaling_figure=str(results / 'molecule_scaling.svg'),
                          checkpoint_hashes=dict(hashes)), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
