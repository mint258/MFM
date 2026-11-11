"""Score the prescribed latent experiments and their registered T1 contrasts."""
import argparse
import json
from pathlib import Path

import numpy as np

from phychem_mfm.phase1.v3_latent_evaluation import score
from phychem_mfm.phase1.v3_selection import paired_difference
from phychem_mfm.phase1.v3_dev_evaluation_v2 import _json


def som_panel(panel):
    keys = ('cyp.3A4', 'cyp.2D6')
    boot = panel['paired_bootstrap']
    values = []
    for i in range(1000):
        row = [boot['task_values'][k][i] for k in keys]
        values.append(None if any(x is None for x in row) else float(np.mean(row)))
    return dict(complete=panel['complete'], tasks={k: panel['tasks'][k] for k in keys},
        mean_normalized_improvement=float(np.mean([panel['tasks'][k]['normalized_improvement'] for k in keys])),
        paired_bootstrap=dict(boot, values=values))


def t1_result(panels):
    if set(panels) != {'A0', 'A1', 'A2', 'A3', 'A4'} or any(set(p) != {'S', 'P'} for p in panels.values()):
        raise ValueError('Require all ten prescribed paired continuations')
    def pick(arm, readout):
        return {c: panels[arm][c][readout] for c in ('S', 'P')}
    comparisons = {}
    for name, aa, ar, ba, br in (
        ('primary_A3_vs_A0', 'A3', 'R2z', 'A0', 'R3'),
        ('parameter_control_A3_vs_A4', 'A3', 'R2z', 'A4', 'R3'),
        ('readout_A1_vs_A0', 'A1', 'R2z', 'A0', 'R3'),
        ('exchange_A2_vs_A1', 'A2', 'R2z', 'A1', 'R2z'),
        ('reconstruction_A3_vs_A2', 'A3', 'R2z', 'A2', 'R2z'),
        ('information_A3_X_vs_z', 'A3', 'R3', 'A3', 'R2z'),
        ('linear_A3_vs_A0', 'A3', 'R1z', 'A0', 'R3'),
        ('fallback_parameter_control_A1_vs_A4', 'A1', 'R2z', 'A4', 'R3')):
        comparisons[name] = dict(A=aa, A_readout=ar, B=ba, B_readout=br,
            **paired_difference(pick(aa, ar), pick(ba, br)))
    som = {arm: {c: som_panel(panels[arm][c]['R2']) for c in ('S', 'P')}
           for arm in ('A0', 'A1', 'A3')}
    baseline = float(np.mean([p['mean_normalized_improvement'] for p in som['A0'].values()]))
    tolerance = max(.02, .1*abs(baseline))
    safeguards = {}
    for arm in ('A3', 'A1'):
        mean = float(np.mean([p['mean_normalized_improvement'] for p in som[arm].values()]))
        safeguards[arm] = dict(mean_normalized_improvement=mean, baseline=baseline,
            tolerated_decrease=tolerance, passes=mean >= baseline-tolerance,
            paired_comparison=paired_difference(som[arm], som['A0'], expected_task_count=2))
    a3 = (comparisons['primary_A3_vs_A0']['A_wins'] and
          comparisons['parameter_control_A3_vs_A4']['A_wins'] and safeguards['A3']['passes'])
    a1 = (comparisons['readout_A1_vs_A0']['A_wins'] and
          comparisons['fallback_parameter_control_A1_vs_A4']['A_wins'] and safeguards['A1']['passes'])
    selected = 'lite_rec' if a3 else 'pma' if a1 else 'none'
    som_rows = [dict(arm=arm, condition=c, task=k, **panels[arm][c]['R2']['tasks'][k])
                for arm in ('A0', 'A1', 'A3') for c in ('S', 'P') for k in ('cyp.3A4', 'cyp.2D6')]
    return dict(status='T1_PROVISIONAL_DECISION', provisional_latent=selected,
        module_finally_confirmed=False, lambda_k_required=a3, fresh6M_confirmation_required=selected != 'none',
        comparisons=comparisons, SoM_safeguards=safeguards, SoM_rows=som_rows,
        SoM_statistic='mean normalized improvement; tolerance max(.02,.1*abs(A0 mean))',
        source_roles=['train', 'train_inner_validation'], downstream_TEST_read=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--results', required=True)
    parser.add_argument('--page', required=True)
    parser.add_argument('--stage', choices=('T0','T1','all'), default='all')
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text())
    panels, rows = {}, []
    for run in plan['runs']:
        if args.stage != 'all' and run['stage'] != args.stage:
            continue
        if not run.get('evaluation_output'):
            raise ValueError('Bind the actual frozen evaluation outputs first')
        summaries = score(run['evaluation_output'])
        row = dict(stage=run['stage'], arm=run['arm'], condition=run['condition'],
                   scores={k: p['mean_normalized_improvement'] for k, p in summaries.items()},
                   output=run['evaluation_output'])
        rows.append(row)
        if run['stage'] == 'T1':
            panels.setdefault(run['arm'], {})[run['condition']] = summaries
    if args.stage == 'T0':
        if len(rows) != 4 or {(r['arm'],r['condition']) for r in rows} != {(a,c) for a in ('T0-3','T0-4') for c in ('S','P')}:
            raise ValueError('Require the four user-confirmed T0 trained readouts')
        result = dict(status='T0_TRAINED_READOUTS_COMPLETE', provisional_latent=None, comparisons={},
            selection_use=False, module_finally_confirmed=False,
            T0_1_reused_source='docs/model_v3/M3_C1_RESULTS.md',
            T0_2_separate_report='/lfshome/zixiao/model_v31_20261105/LATENT_V3_20261111/T0_2_four_statistics/summary.json',
            source_roles=['train','train_inner_validation'], downstream_TEST_read=False)
    else:
        result = t1_result(panels)
    result['rows'] = rows
    _json(result, args.results)
    lines = ['# 潜变量第0/1层结果', '',
        ('T0的4组训练读出已闭合，只报告，不作采用门槛。T0-1引用C1结果，T0-2四统计量单独交付。'
         if args.stage == 'T0' else
         'T1暂定结论：**' + result['provisional_latent'] + '**。采用新模块时仍须规定的从头6M确认；不在这里宣布冻结。'), '',
        '| 层 | 组 | 条件 | R1(X) | R2(X) | R3(X) | R1z | R2z |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        values = [format(r['scores'][k], '.8f') if k in r['scores'] else '—'
                  for k in ('R1', 'R2', 'R3', 'R1z', 'R2z')]
        lines.append('| ' + ' | '.join([r['stage'], r['arm'], r['condition'], *values]) + ' |')
    lines += ['', '| 预注册比较 | Δ | 95%区间 | 结论 |', '| --- | ---: | --- | --- |']
    for name, r in result['comparisons'].items():
        conclusion = r['A'] if r['A_wins'] else r['B'] if r['B_wins'] else '平局'
        lines.append('| {} | {:.8f} | [{:.8f}, {:.8f}] | {} |'.format(name, r['delta'], *r['ci95'], conclusion))
    if args.stage == 'T0':
        lines += ['', 'T0的R1z新置信区间仅覆盖7个分子任务；加入原SoM两格后的九任务汇总仅报告点分数。方法见V3_METHODS.md。', '']
    else:
        lines += ['', 'SoM使用两格R2(X)的归一化改善，条件内两任务等权再S/P等权；不得用原始误差退化替代此判据。',
                  '完整逐格SoM、保护阈值及配对区间见结果JSON。方法见V3_METHODS.md。机制分析仅报告，不参与本结论。', '']
    Path(args.page).write_text('\n'.join(lines))
    print(json.dumps(dict(provisional_latent=result['provisional_latent'], results=args.results)))


if __name__ == '__main__':
    main()
