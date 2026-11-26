"""Deliver closed P-provider primaries; never reopen model predictions or refit."""
import csv
import io
import json
from pathlib import Path

import numpy as np

from cpu_execution_20261126 import execution_fields, native_record
from storage_20261122 import CONTROL as C, REPO as R, write

TASKS = ('qm9.U0_atom', 'qm9.homo', 'exp.LogD', 'exp.LogS')
read = lambda path: json.loads(Path(path).read_text())


def progress(delivered):
    lines = ['# 全量微调：已闭合评测点', '',
        '每点四任务、微调种子0–2，固定50轮和原scratch参照。普通S配方仍按冻结R3判定；微调只作描述。', '',
        '| 点 | 四任务三种子改善均值 | 平均预测改善 | 平均预测95%CI |',
        '| --- | ---: | ---: | --- |']
    for item in delivered:
        value=item['aggregate']
        lo,hi=value['ensemble_ci']
        lines.append(f"| {item['point']} | {value['scratch_improvement_seed_mean']:.6f} | "
            f"{value['ensemble_scratch_improvement']:.6f} | [{lo:.6f}, {hi:.6f}] |")
    lines += ['', '点估计是三种子分数的均值；平均预测及其CI属于另一统计量，分列报告。E1的选择只使用另行保存的真实seed-mean抽样CI，不用这里的平均预测CI替代。', '',
        f'表中完整点评测覆盖{len(delivered)}/16点、{len(delivered)*12}/192个fit；其他点内的部分fit见执行进展JSON。已闭合的配对对比见[FULL_FINETUNING_CONTRASTS.md](FULL_FINETUNING_CONTRASTS.md)，其余待对应点完成；不据部分点选择配方或k*。', '',
        '| 点 | 任务 | 原单位MAE均值 | MAE种子标准差 | scratch改善均值 | 平均预测改善95%CI |',
        '| --- | --- | ---: | ---: | ---: | --- |']
    for item in delivered:
        for row in item['rows']:
            lo,hi=(row['scratch_improvement_ensemble_ci_'+bound] for bound in ('lower','upper'))
            lines.append(f"| {item['point']} | {row['task']} | {row['mae_seed_mean']:.8f} | "
                f"{row['mae_seed_std']:.8f} | {row['scratch_improvement_seed_mean']:.6f} | [{lo:.6f}, {hi:.6f}] |")
    lines += ['', '逐种子MAE、原P统计来源、实际CPU退出、12个fit退出及选中模型工件见[逐任务表](../../results/s_recipe/full_finetune/rows.csv)和同目录每点评测JSON。原预测不重拟合，原1000次分子抽样保留供规定的配对代数使用。', '']
    (R/'docs/s_recipe/FULL_FINETUNING_PROGRESS.md').write_text('\n'.join(lines))


def aggregate(primary, point):
    rows = primary['rows']
    retained = primary['retained']
    if (primary['status'] != 'COMPLETE' or len(rows) != 4
            or {(r['condition'], r['task'], r['seed_count']) for r in rows}
            != {(point, task, 3) for task in TASKS}
            or retained['completed_draws'] != 1000):
        raise ValueError('Exactly the closed four-task, three-seed primary required')
    def means(metric):
        values = np.asarray([retained['draws'][point+'/'+task][metric] for task in TASKS], dtype=np.float64)
        if values.shape != (4, 1000) or not np.isfinite(values).all():
            raise ValueError('All original aligned primary draws must be finite and complete')
        return values.mean(axis=0)
    result = dict(scratch_improvement_seed_mean=float(np.mean([
        row['scratch_improvement_seed_mean'] for row in rows])),
        ensemble_scratch_improvement=float(np.mean([
            row['ensemble_scratch_improvement'] for row in rows])),
        ensemble_ci=np.quantile(means('scratch_improvement'), [.025, .975]).tolist(),
        ensemble_ci_estimand='four_task_mean_of_scores_of_three_seed_mean_predictions',
        point_estimand='four_task_mean_of_three_seed_scores_with_shared_scratch_mean_MAE',
        point_and_ensemble_ci_are_distinct=True)
    if retained['identity'].get('seed_mean_draws'):
        result['E1_seed_mean_ci'] = np.quantile(means('scratch_improvement_seed_mean'), [.025, .975]).tolist()
        result['E1_ci_estimand'] = 'four_task_mean_of_seed_scores_with_shared_mean_scratch_denominator'
    return result


def run():
    native_record()
    plan = read(R/'configs/s_recipe/full_finetune_matrix_20261124.json')
    delivered = []
    for binding in plan['points']:
        point = binding['point']
        destination = R/'results/s_recipe/full_finetune'/(point+'.json')
        marker = C/(point+'_fullft_delivery_20261127_COMPLETE.json')
        if marker.exists():
            delivered.append(read(destination))
            continue
        if destination.exists():
            raise ValueError('Inspect partial delivery before consuming a primary again')
        handle = 'S_FT_statistics_'+point+'_attempt0'
        controller = C/(handle+'_controller.json')
        if not controller.exists():
            continue
        source = read(controller)
        parent_path = Path(source['lifecycle_record'])
        if not parent_path.exists():
            continue
        parent = read(parent_path)
        command_path = parent_path.with_name('command_exit.json')
        if not command_path.exists() or parent.get('status') not in ('COMPLETE', 'FAILED'):
            continue
        if (parent.get('status') != 'COMPLETE' or parent.get('exit_code') != 0
                or read(command_path).get('exit_code') != 0
                or not parent.get('owned_descendants_exited') or not parent.get('observer_joined')):
            raise ValueError('An unfinished/failed primary cannot be delivered')
        cfg = read(source['configuration'])
        output = Path(cfg['output'])
        closure = read(C/(handle+'_guarded_'+source['native_handle']+'.json'))
        receipt = read(output/'primary_complete.json')
        if (closure.get('status') != 'COMPLETE' or closure.get('exit_code') != 0
                or not closure.get('owned_descendants_exited') or not closure.get('observer_joined')
                or receipt.get('status') != 'COMPLETE' or receipt.get('rows') != 4
                or receipt.get('bootstrap_draws') != 1000
                or receipt.get('native_execution', {}).get('record') != str(parent_path)):
            raise ValueError('Exact primary producer receipt and owned exit required')
        primary = read(output/'primary.json')
        summary = aggregate(primary, point)
        fits = []
        for item in cfg['completed_new_S_fits']:
            fit_exit = read(item['lifecycle_record'])
            receipt_path = Path(item['output'])/'selected_model_receipt.json'
            model = read(receipt_path)
            if (fit_exit.get('status') != 'COMPLETE' or fit_exit.get('exit_code') != 0
                    or not fit_exit.get('owned_descendants_exited') or not fit_exit.get('observer_joined')
                    or model.get('status') != 'SELECTED_MODEL_DURABLE_CONTINUATION_RETIRED'
                    or model.get('owned_exit_evidence') != item['lifecycle_record']):
                raise ValueError('All original fit exits and selected-model receipts must be closed')
            fits.append(dict(output=item['output'], lifecycle_record=item['lifecycle_record'],
                fit_exit=fit_exit, selected_model_receipt=model))
        if len(fits) != 12:
            raise ValueError('Retain the twelve exact scientific fit deliveries')
        cache = C/'fullft_delivery_20261127'/(point+'_primary.json')
        cache.parent.mkdir(parents=True, exist_ok=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        write(cache, primary)
        value = dict(status='COMPLETE_FULLFT_POINT', point=point,
            source_binding=binding, rows=primary['rows'], aggregate=summary,
            original_primary=str(output/'primary.json'), retained_primary_delivery=str(cache),
            primary_complete=receipt, primary_exit=closure, parent_exit=parent, fits=fits,
            reporting_execution=execution_fields(), new_fits=0, new_bootstrap_draws=0,
            required_paired_contrasts_status='Pending corresponding complete reference point deliveries',
            recipe_unchanged=True, ordinary_fullft_is_descriptive=True,
            E1_seed_mean_component_available=bool(primary['retained']['identity'].get('seed_mean_draws')))
        write(destination, value)
        write(marker, dict(status='COMPLETE', point=point, output=str(destination),
            retained_primary_delivery=str(cache)))
        delivered.append(value)
    if delivered:
        rows = [dict(point=record['point'], **row) for record in delivered for row in record['rows']]
        fields = list(dict.fromkeys(key for row in rows for key in row))
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        path = R/'results/s_recipe/full_finetune/rows.csv'
        temporary = path.with_suffix('.csv.next')
        temporary.write_text(stream.getvalue())
        temporary.replace(path)
        progress(delivered)
    print(json.dumps(dict(status='CLOSED_FULLFT_POINTS_DELIVERED',
        points=[row['point'] for row in delivered], required_points=len(plan['points']),
        paired_contrasts_complete=False, new_fits=0, new_bootstrap_draws=0)), flush=True)
    return 0
