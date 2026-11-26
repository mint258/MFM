"""Required descriptive FT contrasts using delivered original P draw caches."""
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import numpy as np
from cpu_execution_20261126 import execution_fields,native_record
from storage_20261122 import CONTROL as C,REPO as R,ROOT,write

TASKS=('qm9.U0_atom','qm9.homo','exp.LogD','exp.LogS')
PAIRS=[(point,'S_B0_3M') for point in (
    'S_G1_3M','S_N1_3M','S_N2_3M','S_R1_3M','S_R2_3M',
    'S_E1_k1_3M','S_E1_k2_3M','S_E1_k5_3M')]
PAIRS += [('S_final_9M','S_B0_9M')]
PAIRS += [(f'S_subset_T{n}_9M',reference) for n in (5,6) for reference in ('S_B0_9M','S_final_9M')]
read=lambda path:json.loads(Path(path).read_text())


def provider():
    path=ROOT/'MFM_p_recipe/tools/p_recipe/finetune_statistics.py'
    matrix=read(R/'configs/s_recipe/full_finetune_matrix_20261124.json')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=matrix['providers_sha256'][str(path)]:
        raise ValueError('The registered P statistics provider changed')
    spec=importlib.util.spec_from_file_location('_s_original_p_ft_contrasts_20261127',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contrast(candidate,baseline,left,right,original):
    for primary,point in ((candidate,left),(baseline,right)):
        if (primary.get('status')!='COMPLETE' or len(primary['rows'])!=4
                or {(row['condition'],row['task'],row['seed_count']) for row in primary['rows']}
                    != {(point,task,3) for task in TASKS}
                or primary['retained']['completed_draws']!=1000):
            raise ValueError('Exact complete four-task/three-seed primaries required')
    # The original function verifies molecular groups, draw identity and the
    # unchanged scratch/reference bindings before any aggregate subtraction.
    rows=[original.paired_contrast(candidate,left,right,task,right_primary=baseline) for task in TASKS]
    values=[]
    for task in TASKS:
        a=candidate['retained']['draws'][left+'/'+task]['scratch_improvement']
        b=baseline['retained']['draws'][right+'/'+task]['scratch_improvement']
        values.append(np.asarray(a,dtype=np.float64)-np.asarray(b,dtype=np.float64))
    values=np.asarray(values)
    if values.shape!=(4,1000) or not np.isfinite(values).all():
        raise ValueError('Original aligned ensemble draws are incomplete or undefined')
    bounds,defined=original.interval(values.mean(axis=0).tolist())
    if defined!=1000:raise ValueError('All original1000 contrast draws must be defined')
    return dict(task_rows=rows,aggregate=dict(
        delta_seed_mean=float(np.mean([row['delta_seed_mean'] for row in rows])),
        delta_ensemble=float(np.mean([row['delta_ensemble'] for row in rows])),
        ensemble_ci_lower=bounds[0],ensemble_ci_upper=bounds[1],bootstrap_defined=defined,
        ci_estimand='difference_of_four_task_mean_scores_of_three_seed_mean_predictions',
        point_estimand='difference_of_four_task_means_of_three_seed_scores',
        ordinary_fullft_is_descriptive=True,E1_decision_uses_separate_seed_mean_draws=True))


def closed_delivery(point):
    path=R/'results/s_recipe/full_finetune'/(point+'.json')
    if not path.exists():return None
    delivery=read(path)
    if delivery.get('status')!='COMPLETE_FULLFT_POINT' or delivery.get('point')!=point:
        raise ValueError('Only a complete exact point delivery can be contrasted')
    context=delivery['reporting_execution']
    parent_path=Path(context['native_record'])
    parent=read(parent_path)
    if (parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
            or read(parent_path.with_name('command_exit.json')).get('exit_code')!=0
            or not parent.get('owned_descendants_exited') or not parent.get('observer_joined')):
        raise ValueError('Point delivery CPU producer has not closed')
    cache=Path(delivery['retained_primary_delivery'])
    if cache!=C/'fullft_delivery_20261127'/(point+'_primary.json'):
        raise ValueError('Use the already delivered original retained primary, not predictions')
    return delivery,cache


def run():
    native_record()
    original=None
    loaded={}
    completed=[]
    missing=[]
    for left,right in PAIRS:
        destination=R/'results/s_recipe/full_finetune_contrasts'/(left+'_minus_'+right+'.json')
        if destination.exists():
            result=read(destination)
            if result.get('status')!='COMPLETE' or (result.get('left'),result.get('right'))!=(left,right):
                raise ValueError('Inspect an existing contrast before consuming any sources again')
            completed.append(result)
            continue
        sources=[closed_delivery(point) for point in (left,right)]
        if any(source is None for source in sources):
            missing.append(dict(left=left,right=right))
            continue
        for point,source in zip((left,right),sources):
            if point not in loaded:loaded[point]=read(source[1])
        if original is None:original=provider()
        value=contrast(loaded[left],loaded[right],left,right,original)
        value.update(status='COMPLETE',left=left,right=right,**execution_fields(),
            authority='docs/s_recipe/USER_DIRECTIVE_20261123B.md; subset full-reference pairs also20261123C',
            source_deliveries=[str(R/'results/s_recipe/full_finetune'/(point+'.json')) for point in (left,right)],
            original_retained_primary_deliveries=[str(source[1]) for source in sources],
            new_fits=0,new_bootstrap_draws=0,original_prediction_files_read=0,
            interpretation='Descriptive FT comparison; original frozen S recipe decisions unchanged')
        destination.parent.mkdir(parents=True,exist_ok=True)
        write(destination,value)
        completed.append(value)
    if completed:
        rows=[dict(row,left=result['left'],right=result['right'])
            for result in completed for row in result['task_rows']]
        stream=io.StringIO(newline='')
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        (R/'results/s_recipe/full_finetune_contrasts.csv').write_text(stream.getvalue())
        lines=['# 全量微调：规定的配对对比','',
            '3M臂对独立3M的S-B0；9M终点对9M的S-B0。子集另对全分子的S-final 9M。轨迹前缀只作同条运行内部趋势，不加入筛选臂比较。','',
            '| 候选 | 参照 | Δ三种子分数均值 | Δ平均预测分数 | 平均预测差95%CI |',
            '| --- | --- | ---: | ---: | --- |']
        for item in completed:
            a=item['aggregate']
            lines.append(f"| {item['left']} | {item['right']} | {a['delta_seed_mean']:.6f} | "
                f"{a['delta_ensemble']:.6f} | [{a['ensemble_ci_lower']:.6f}, {a['ensemble_ci_upper']:.6f}] |")
        lines += ['','点估计与平均预测CI是不同估计量；逐任务差与CI见[原P配对函数输出](../../results/s_recipe/full_finetune_contrasts.csv)。S-G1相对S-B0的四任务差也在该表中。这里只对原保留的1000个分子抽样做配对代数，不重抽、不读取原预测或拟合模型。E1选择另用真实seed-mean抽样CI，普通配方不据微调更改。','']
        (R/'docs/s_recipe/FULL_FINETUNING_CONTRASTS.md').write_text('\n'.join(lines))
    status=dict(status='COMPLETE' if not missing else 'PARTIAL_REQUIRED_PAIRS_PENDING',
        completed_pairs=len(completed),required_pairs=len(PAIRS),pending_pairs=missing,
        new_fits=0,new_bootstrap_draws=0,original_prediction_files_read=0,**execution_fields())
    write(R/'results/s_recipe/full_finetune_contrasts_status.json',status)
    done={(item['left'],item['right']) for item in completed}
    for point in {left for left,_ in PAIRS}:
        path=R/'results/s_recipe/full_finetune'/(point+'.json')
        if not path.exists():continue
        delivery=read(path)
        references=[right for left,right in PAIRS if left==point]
        links=[str(R/'results/s_recipe/full_finetune_contrasts'/(point+'_minus_'+right+'.json'))
            for right in references if (point,right) in done]
        paired_status='COMPLETE' if all((point,right) in done for right in references) else 'PENDING_REGISTERED_REFERENCE_POINTS'
        if (delivery.get('required_paired_contrasts_status')!=paired_status
                or delivery.get('completed_descriptive_contrasts')!=links):
            delivery.update(required_paired_contrasts_status=paired_status,completed_descriptive_contrasts=links)
            write(path,delivery)
    print(json.dumps(status),flush=True)
    return 0
