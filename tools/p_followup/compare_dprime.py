"""Read existing M2/Dprime R1/R3 draws; enforce the user-directed seed rule."""
import argparse
from pathlib import Path
from resources import REPO, load, save, guard
from compare_dedup import paired_ci
from dprime_decision import decision


def scores(configuration, seed):
    if configuration['seed'] != seed or configuration['samples'] != 3000000:
        raise ValueError('Dprime comparison requires the exact paired seed and3M budget')
    return load(Path(configuration['output']) / 'readout/scores.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate-seed1')
    parser.add_argument('--baseline-seed1')
    args = parser.parse_args()
    if bool(args.candidate_seed1) != bool(args.baseline_seed1):
        parser.error('Both seed1 configurations are required together')
    guard(force=True)
    candidate_path = REPO / 'configs/p_followup/Dprime_M2_seed0_continued.json'
    if not candidate_path.exists():
        candidate_path = REPO / 'configs/p_followup/Dprime_M2_seed0.json'
    configuration_pairs = [(0, candidate_path, REPO / 'configs/p_followup/M2_reference.json')]
    if args.candidate_seed1:
        configuration_pairs.append((1, Path(args.candidate_seed1), Path(args.baseline_seed1)))
    comparisons = {}
    baseline_r3 = []
    for seed, candidate_path, baseline_path in configuration_pairs:
        candidate, baseline = load(candidate_path), load(baseline_path)
        actual, reference = scores(candidate, seed), scores(baseline, seed)
        comparison = {readout: paired_ci(actual[readout], reference[readout]) for readout in ('R1', 'R3')}
        comparisons[str(seed)] = dict(candidate_configuration=str(candidate_path),
            baseline_configuration=str(baseline_path), candidate_run=candidate['run'], baseline_run=baseline['run'],
            candidate_scores=str(Path(candidate['output']) / 'readout/scores.json'),
            baseline_scores=str(Path(baseline['output']) / 'readout/scores.json'),
            baseline_R3=reference['R3']['mean_normalized_improvement'], comparisons=comparison)
        baseline_r3.append(reference['R3']['mean_normalized_improvement'])
    outcome = decision([v['comparisons']['R3'] for v in comparisons.values()], baseline_r3)
    result = dict(**outcome, primary='Dprime minus M2/R3', samples=3000000, comparisons=comparisons,
                  mainline_modified=False, integration_requires_user_confirmation=True)
    save(REPO / 'results/p_followup/Dprime_M2_comparison.json', result)
    lines = ['# D′ 对当前最优M2的配对比较', '',
        '复用各运行精确3M的既有R1/R3及1000次MID配对bootstrap。任务集和bootstrap分组/seed/次数/置信度一致后相减；不追加探针。判定严格采用用户2026-11-17补充计划：seed0仅在|Δ|≥0.06且95%CI不跨0时直接判定，否则补本线D′ seed1并复用配方线M2 seed1。两个seed均为正向CI且平均Δ≥max(0.03，M2两seed平均R3×8%)判胜；两CI均全负判负；其余持平。', '',
        '|seed|读出|D′−M2|配对95%CI|', '|---|---|---:|---|']
    for seed, value in comparisons.items():
        for readout, comparison in value['comparisons'].items():
            lines.append(f"|{seed}|{readout}|{comparison['delta']}|{comparison['ci95']}|")
    lines += ['', '状态：' + outcome['status'] + '；判定：' + str(outcome['verdict']) + '。',
        '只有win形成候选建议，实际接入仍由用户确认；不因CURRENT_BEST后续更新重跑本M2基底上的运行。',
        '', '原单位同分子构象差MAE与第6层表示几何仅描述，另见对应Dprime报告；C3只复用配方线分数及单次几何前向，不训练。']
    (REPO / 'docs/p_followup/DPRIME_M2_COMPARISON.md').write_text('\n'.join(lines) + '\n')
    print('DPRIME_DECISION', outcome, flush=True)


if __name__ == '__main__':
    main()
