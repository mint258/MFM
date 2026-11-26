"""Registered subset-vs-full reporting from closed producers and retained draws."""
import csv
import io
import json
from pathlib import Path

from cpu_execution_20261126 import execution_fields,native_record
from extension_training_20261124 import validate
from s_statistics import paired
from storage_20261122 import CONTROL as C,REPO as R,write

RUNS=('S_subset_T5_s0_9M','S_subset_T6_s0_9M')
FULL='S_final_s0_9M'
SAMPLES=(3000000,6000000,9000000)
read=lambda path:json.loads(Path(path).read_text())


def closed_subset(run):
    output=C/'training'/run
    c=read(output/'configuration.json')
    summary=read(output/'summary.json')
    population=read(c['population'])
    validate(c,read(R/'configs/s_recipe/confirmation/S-final.json'),population)
    phase=read(output/'readout/terminal_statistics_status.json')
    parent=read(Path(phase['configuration']).parent/'record.json')
    command=read(Path(phase['configuration']).parent/'command_exit.json')
    gpu=read(output/'readout/terminal_gpu_status.json')
    close=read(C/(gpu['resource_handle']+'_resource_close.json'))
    source=read(parent['configuration'])
    statistics_source=read(source['source_configuration'])
    training=read(statistics_source['training_closure_record'])
    if (c['run']!=run or c['samples']!=9000000 or c['seed']!=0
            or c['evaluation_samples']!=list(SAMPLES)
            or summary.get('status')!='COMPLETE' or summary.get('samples')!=9000000
            or summary.get('updates')!=281250 or not summary.get('statistics_complete')
            or any(v.get('status')!='COMPLETE' or v.get('exit_code')!=0
                or not v.get('owned_descendants_exited') or not v.get('observer_joined')
                for v in (phase,parent))
            or command.get('exit_code')!=0 or gpu.get('run')!=run or gpu.get('samples')!=9000000
            or gpu.get('exit_code')!=0 or not gpu.get('owned_descendants_exited')
            or close.get('status')!='OWN_RESOURCES_CLOSED' or close.get('exit_code')!=0
            or close.get('run')!=run or close.get('role')!='terminal'
            or training.get('run')!=run or not training.get('owned_descendants_exited')
            or not training.get('observer_joined')):
        raise ValueError('Exact full9M subset and its complete terminal GPU/CPU must close first')
    return dict(configuration=c,population=population,summary=summary,training_exit=training,
        statistics_exit=phase,statistics_parent_exit=parent,statistics_command_exit=command,
        gpu_exit=gpu,gpu_resource_close=close)


def contrasts(scores,full):
    if set(scores)!=set(SAMPLES) or set(full)!=set(SAMPLES):
        raise ValueError('Only matched3/6/9M boundaries of these9M trajectories')
    result={}
    for samples in SAMPLES:
        result[samples]={}
        for key in ('R1','R3'):
            value=paired(scores[samples][key],full[samples][key])
            value.pop('verdict')
            result[samples][key]=value
    return result


def csv_file(path,rows):
    fields=list(dict.fromkeys(key for row in rows for key in row))
    stream=io.StringIO(newline='')
    writer=csv.DictWriter(stream,fieldnames=fields)
    writer.writeheader();writer.writerows(rows)
    pending=path.with_suffix(path.suffix+'.next')
    pending.write_text(stream.getvalue());pending.replace(path)


def collect():
    marker=C/'molecule_scaling_delivery_20261127_COMPLETE.json'
    if marker.exists():return read(marker)
    # Validate both complete subset executions before consuming any original
    # scores/VAL. Intermediate representations were computed by terminal once.
    sources={run:closed_subset(run) for run in RUNS}
    cache=read(C/'budget_readout_primaries_20261127.json')
    full={p['samples']:p['scores'] for p in cache['points']
        if p['run']==FULL and p['samples'] in SAMPLES}
    endpoint=read(R/'results/s_recipe'/(FULL+'.json'))
    if (endpoint.get('status')!='COMPLETE' or endpoint.get('run')!=FULL
            or endpoint.get('samples')!=9000000 or endpoint.get('layer')!=6
            or set(full)!={3000000,6000000}):
        raise ValueError('Original full-population trajectory and delivered terminal source required')
    # This retained endpoint is a necessary input to the newly registered C2
    # contrasts. No endpoint statistic/prediction/bootstrap is recomputed.
    full[9000000]=read(endpoint['source_scores'])
    subset_scores={run:{n:read(C/'training'/run/('readout' if n==9000000 else 'readout_'+str(n))/'scores.json')
        for n in SAMPLES} for run in RUNS}
    comparisons={run:contrasts(values,full) for run,values in subset_scores.items()}
    scores={**subset_scores,FULL:full}
    fields=('complete','mean_normalized_improvement','bootstrap_ci','bootstrap_samples',
        'bootstrap_defined','bootstrap_unit','bootstrap_seed','included_tasks')
    populations={run:sources[run]['population']['TRAIN_molecules'] for run in RUNS}
    populations[FULL]=read(R/'configs/s_recipe/population.json')['TRAIN_molecules']
    points=[]
    for run in (*RUNS,FULL):
        for n in SAMPLES:
            point=dict(run=run,samples=n,source_training_budget=9000000,independent_budget=False,
                TRAIN_molecules=populations[run],layer=6,seed=0,descriptive_only=True,
                readouts={key:{f:scores[run][n][key][f] for f in fields if f in scores[run][n][key]}
                    for key in ('R1','R3')})
            if run!=FULL:point['paired_vs_full_same_boundary']=comparisons[run][n]
            points.append(point)
    with (R/'results/s_recipe/budget_curve.csv').open(newline='') as stream:
        existing=[r for r in csv.DictReader(stream) if r['source_run']==FULL]
    if len(existing)!=18:raise ValueError('Reuse all18 previously transcribed full-population VAL records')
    vals=[]
    families=('s_bond','s_element','s_noise')
    for row in existing:
        vals.append(dict(run=FULL,samples=int(row['samples']),TRAIN_molecules=populations[FULL],
            source=row['VAL_source'],**{family:row['VAL_loss_'+family] for family in families}))
    for run in RUNS:
        for n in range(500000,9000001,500000):
            path=C/'training'/run/('VAL_'+str(n)+'.json')
            val=read(path)
            if val.get('samples')!=n or set(val.get('losses',{}))!=set(families):
                raise ValueError('Exact original fixed-VAL sample boundary/families required')
            vals.append(dict(run=run,samples=n,TRAIN_molecules=populations[run],source=str(path),
                **{key:val['losses'][key] for key in families}))
    value=dict(status='COMPLETE_FROZEN_SUBSET_COMPONENTS',points=points,VAL=vals,sources=sources,
        reporting_execution=execution_fields(),new_fits=0,new_bootstrap_draws=0,
        new_model_evaluations=0,original_subset_VAL_records_transcribed=36,
        original_full_VAL_records_reopened=0,seed1_triggered=False,recipe_changed=False,
        scope='Original P selected MIDs intersect S; matched9M trajectories only; descriptive contrasts')
    retained=C/'molecule_scaling_retained_primaries_20261127.json'
    write(retained,dict(scores={run:{str(n):s for n,s in values.items()} for run,values in scores.items()},
        source='Original closed producer arrays used for the required C2 contrasts; no new draws'))
    value['retained_primary_delivery']=str(retained)
    write(marker,value)
    return value


def run():
    native_record()
    value=collect()
    rows=[]
    completed=[]
    all_contrasts=[]
    val={(r['run'],r['samples']):r for r in value['VAL']}
    for point in value['points']:
        run,n=point['run'],point['samples']
        row={key:point[key] for key in ('run','samples','TRAIN_molecules','source_training_budget','independent_budget','layer','seed')}
        for key in ('R1','R3'):
            score=point['readouts'][key]
            row.update({key+'_mean':score['mean_normalized_improvement'],
                key+'_ci_lower':score['bootstrap_ci'][0],key+'_ci_upper':score['bootstrap_ci'][1]})
            pair=point.get('paired_vs_full_same_boundary',{}).get(key,{})
            for field in ('delta','ci_lower','ci_upper'):row[key+'_subset_minus_full_'+field]=pair.get(field,'')
        for family in ('s_bond','s_element','s_noise'):row['VAL_loss_'+family]=val[(run,n)][family]
        row.update(fullFT_status='NOT_REGISTERED_INTERMEDIATE',fullFT_seed_mean='',
            fullFT_ensemble_mean='',fullFT_ensemble_ci_lower='',fullFT_ensemble_ci_upper='')
        if n==9000000:
            ft_point='S_final_9M' if run==FULL else run.removesuffix('_s0_9M')+'_9M'
            path=R/'results/s_recipe/full_finetune'/(ft_point+'.json')
            row['fullFT_status']='WAITING_COMPLETE_POINT'
            if path.exists():
                ft=read(path)
                binding=ft.get('source_binding',{})
                if (ft.get('status')!='COMPLETE_FULLFT_POINT' or ft.get('point')!=ft_point
                        or binding.get('run')!=run or binding.get('samples')!=9000000
                        or binding.get('source_training_budget')!=9000000):
                    raise ValueError('Exact completed own9M fullFT point required')
                a=ft['aggregate'];completed.append(ft_point)
                row.update(fullFT_status='COMPLETE_DESCRIPTIVE',fullFT_seed_mean=a['scratch_improvement_seed_mean'],
                    fullFT_ensemble_mean=a['ensemble_scratch_improvement'],
                    fullFT_ensemble_ci_lower=a['ensemble_ci'][0],fullFT_ensemble_ci_upper=a['ensemble_ci'][1])
            if run!=FULL:
                path=R/'results/s_recipe/full_finetune_contrasts'/(ft_point+'_minus_S_final_9M.json')
                if path.exists():
                    pair=read(path)
                    if (pair.get('status')!='COMPLETE' or pair.get('left')!=ft_point
                            or pair.get('right')!='S_final_9M'):
                        raise ValueError('Completed exact subset-minus-full fullFT contrast required')
                    all_contrasts.append(pair)
                    a=pair['aggregate']
                    for field in ('delta_seed_mean','delta_ensemble','ensemble_ci_lower','ensemble_ci_upper'):
                        row['fullFT_subset_minus_full_'+field]=a[field]
        rows.append(row)
    status='COMPLETE' if len(completed)==3 and len(all_contrasts)==2 else 'FROZEN_COMPLETE_FULLFT_PENDING'
    destination=R/'results/s_recipe'
    csv_file(destination/'molecule_scaling.csv',rows)
    csv_file(destination/'molecule_scaling_VAL.csv',value['VAL'])
    write(destination/'molecule_scaling.json',dict(value,status=status,
        complete_fullFT_points=completed,fullFT_paired_contrasts=all_contrasts,table=rows,
        last_reporting_execution=execution_fields()))
    lines=['# S：分子数 scaling','',
        '原P T5/T6实际选中清单与S TRAIN取交集；不重新抽样。固定VAL、9M cosine、各自p99及既有归一化不变。', '',
        '| TRAIN分子数 | 样本数 | R1 | R3 | R3子集−全量 Δ [95%CI] |',
        '| ---: | ---: | ---: | ---: | --- |']
    for row in rows:
        delta=row['R3_subset_minus_full_delta']
        text='参照' if delta=='' else f"{delta:.6f} [{row['R3_subset_minus_full_ci_lower']:.6f}, {row['R3_subset_minus_full_ci_upper']:.6f}]"
        lines.append(f"| {row['TRAIN_molecules']} | {row['samples']} | {row['R1_mean']:.6f} | {row['R3_mean']:.6f} | {text} |")
    lines+=['', '状态：'+status+'。9M全量微调逐种子分数改善、平均预测改善/CI及其配对差分列在[molecule_scaling.csv](../../results/s_recipe/molecule_scaling.csv)；每任务差与CI引用原完整微调配对交付。', '',
        '三种子分数均值和平均预测的分子CI属于不同估计量。冻结差只用原1000次分子配对抽样做代数，不重抽；没有多重比较校正。只比较相同9M轨迹样本边界，3/6M不是独立预算训练；不触发seed1、配方或k*修改。', '',
        '原每500k的三家族VAL见[molecule_scaling_VAL.csv](../../results/s_recipe/molecule_scaling_VAL.csv)。s_element恢复目标在全部三条运行中关闭，其监测损失不能解释为被优化目标。原P实际MIDs及S交集产品继续保留供D后续使用。', '']
    (R/'docs/s_recipe/MOLECULE_SCALING.md').write_text('\n'.join(lines))
    print(json.dumps(dict(status=status,points=len(rows),fullFT_points=completed,new_fits=0,new_bootstrap_draws=0)),flush=True)
    return 0
