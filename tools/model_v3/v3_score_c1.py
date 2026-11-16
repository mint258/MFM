"""Aggregate the seven actual v2-panel evaluation productions; no pretraining."""
import argparse
import itertools
import json
from pathlib import Path

from phychem_mfm.phase1.v3_dev_evaluation_v2 import score_evaluation
from phychem_mfm.phase1.v3_selection import select_candidate,paired_difference
from phychem_mfm.phase1.v2_disk import save_metadata_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True)
    parser.add_argument('--results',required=True)
    parser.add_argument('--page',required=True)
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text())
    panels,rows = {},[]
    for run in plan['runs']:
        summary,primary = score_evaluation(run['output'],
            Path(plan['reference_output'])/run['candidate'],run['legacy_summary'])
        panels.setdefault(run['candidate'],{})[run['condition']] = primary
        rows.append(dict(candidate=run['candidate'],condition=run['condition'],
            R1=summary['R1_mean_normalized_improvement'],R2=summary['R2_mean_normalized_improvement'],
            R3=summary['mean_normalized_improvement'],historical18=summary['historical_18_cell_mean'],
            summary=str(Path(run['output'])/'summary.json'),checkpoint=run['checkpoint']))
    if set(panels)!=set(('C1-0','C1-a','C1-b')):
        raise ValueError('All three original C1 candidates are required')
    decision = select_candidate(panels,('C1-0','C1-a','C1-b'))
    comparisons = [dict(A=a,B=b,**paired_difference(panels[a],panels[b]))
                   for a,b in itertools.combinations(('C1-0','C1-a','C1-b'),2)]
    old_rank = ['C1-a','C1-0','C1-b']
    result = dict(status='C1_SELECTED_PANEL_V2_SEED0',panel='configs/dev_panel_v2.json',
        primary='equal_nine_task_R3_then_equal_S_P',conditions=['S','P'],pretraining_seed=0,
        rows=rows,decision=decision,pairwise=comparisons,old_18_cell_rank=old_rank,
        R3_rank_differs_from_old18=decision['ranked']!=old_rank,
        source_roles=['train','train_inner_validation'],downstream_TEST_read=False,
        latent_selection='not_yet_performed',model_and_recipe_frozen=False)
    target = Path(args.results)
    if target.exists():
        if json.loads(target.read_text())!=result:
            raise ValueError('Retain a different existing C1 result')
    else:
        save_metadata_json(result,target)
    lines = ['# M3 C1：v2面板单种子结果','',
        '选定距离偏置：**'+decision['selected']+'**。仅为C1选择；潜变量、后续阶段5/6和模型/配方冻结尚未完成。','',
        '| C1 | 条件 | R1 | R2 | R3（主） | 历史18格 |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for row in rows:
        lines.append('| {candidate} | {condition} | {R1:.8f} | {R2:.8f} | {R3:.8f} | {historical18:.8f} |'.format(**row))
    lines.extend(['','| A − B（S/P等权） | Δ | 95%区间 | 效果阈值 | 判定 |',
                  '| --- | ---: | --- | ---: | --- |'])
    for row in comparisons:
        winner = row['A'] if row['A_wins'] else row['B'] if row['B_wins'] else '平局'
        lines.append('| {} − {} | {:.8f} | [{:.8f}, {:.8f}] | {:.8f} | {} |'.format(
            row['A'],row['B'],row['delta'],*row['ci95'],row['effect_threshold'],winner))
    lines.extend(['','全部来自原6个6M检查点；编码器冻结，不重新预训练。任务/成员/TRAIN内层及匹配随机对照沿用v1，历史18格直接引用。',
        '按分子组配对bootstrap1000次、seed20261025，A/B/全部格子/条件共享同次抽样；先条件内任务等权，再S/P等权。',
        '先比较主分第一/第二；只有Δ区间下界>0且达到max(.01,.05×较高分数)才选第一，否则按C1-0/a/b在前二中取简单者。',
        'R2/R3为固定30轮最后一轮，无早停；优化子集标准化。方法见V3_METHODS.md，完整数值见results/model_v3_c1_final.json。',
        '原补种子作业均按v3取消，原失败/日志/检查点仍保留；无下游TEST。',''])
    Path(args.page).write_text('\n'.join(lines))
    print(json.dumps(dict(selected=decision['selected'],ranked=decision['ranked'],results=str(target))))


if __name__=='__main__':
    main()
