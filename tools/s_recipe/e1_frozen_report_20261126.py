"""Deliver each real E1 frozen endpoint once, reusing original molecular draws."""
import json
from pathlib import Path
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,ROOT,write
from e1_reporting_20261126 import original_p_algebra,apply_s_verdict

read=lambda path:json.loads(Path(path).read_text())


def run():
    records=[]
    algebra=None
    reference=None
    for k in (1,2,5):
        name=f'S_E1_k{k}_s0_3M'
        output=C/'training'/name
        marker=C/(name+'_frozen_report_20261126_COMPLETE.json')
        destination=R/'results/s_recipe'/(name+'.json')
        if marker.exists():
            records.append(read(destination))
            continue
        if destination.exists():
            raise ValueError('Inspect the delivered endpoint before consuming original sources again')
        if not (output/'summary.json').exists():continue
        summary=read(output/'summary.json')
        if summary.get('status')!='COMPLETE':continue
        c=read(output/'configuration.json')
        phase=read(output/'readout/terminal_statistics_status.json')
        parent=read(Path(phase['configuration']).parent/'record.json')
        command=read(Path(phase['configuration']).parent/'command_exit.json')
        if (c.get('run')!=name or c.get('samples')!=3000000 or c.get('seed')!=0
                or c.get('conformer_cap')!=k
                or summary.get('samples')!=3000000 or summary.get('updates')!=93750
                or not summary.get('statistics_complete')
                or phase.get('status')!='COMPLETE' or phase.get('exit_code')!=0
                or parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
                or command.get('exit_code')!=0
                or not all(p.get('owned_descendants_exited') and p.get('observer_joined')
                           for p in (phase,parent))):
            raise ValueError('Exact original3M endpoint and actual CPU parent closure required')
        gpu=read(output/'readout/terminal_gpu_status.json')
        close=read(C/(gpu['resource_handle']+'_resource_close.json'))
        source=read(parent['configuration'])
        statistics_source=read(source['source_configuration'])
        training_lifecycle=read(statistics_source['training_closure_record'])
        if training_lifecycle.get('job_id') is None:
            training=read(C/(name+'_producer_exit_evidence.json'))
        else:
            state=read(C/'current_state.json')
            pulse=read(state['latest_pipeline_pulse'])
            job=training_lifecycle['job_id']
            actual=[row for row in pulse['jobs'] if row['job_id']==job]
            if (len(actual)!=1 or actual[0]['state']!='COMPLETED' or actual[0]['exit_code']!='0:0'
                    or actual[0]['node']!=training_lifecycle['node']
                    or training_lifecycle.get('run')!=name
                    or training_lifecycle.get('status')!='TRAINING_COMPLETE_READOUT_PENDING'
                    or training_lifecycle.get('result',{}).get('samples')!=3000000
                    or not training_lifecycle.get('owned_descendants_exited')
                    or not training_lifecycle.get('observer_joined')
                    or pulse['observed_time']<training_lifecycle.get('ended_at',float('inf'))):
                raise ValueError('Actual successful full-budget Slurm producer and own exit required')
            training=dict(run=name,full_budget_samples=3000000,mode='Slurm',
                source_lifecycle=statistics_source['training_closure_record'],
                producer=training_lifecycle['producer'],owned_descendants_exited=True,
                actual_job=actual[0],source_accounting=state['latest_pipeline_pulse'])
            origin=read(C/'execution.json')['runs'][name].get('native_lifecycle_record')
            if origin:
                training.update(native_origin_source=origin,native_origin_exit=read(origin))
        if (gpu.get('run')!=name or gpu.get('samples')!=3000000 or gpu.get('exit_code')!=0
                or gpu.get('status')!='GPU_TERMINAL_COMPLETE_WAITING_CPU'
                or close.get('status')!='OWN_RESOURCES_CLOSED' or close.get('exit_code')!=0
                or close.get('run')!=name or close.get('role')!='terminal'
                or training.get('run')!=name or training.get('full_budget_samples')!=3000000
                or training.get('actual_proc_identity') is not None):
            raise ValueError('Native GPU and full-budget training resources have not really closed')
        if algebra is None:
            algebra=original_p_algebra(ROOT/'MFM_p_recipe')
            baseline=C/'training/S_R1_s0_3M'
            if (read(baseline/'configuration.json')['samples']!=3000000
                    or read(baseline/'summary.json')['status']!='COMPLETE'):
                raise ValueError('E1 k10 reference is the original independent3M S-R1')
            reference=read(baseline/'readout/scores.json')
        scores=read(output/'readout/scores.json')
        fields=('complete','mean_normalized_improvement','bootstrap_ci','bootstrap_samples',
            'bootstrap_defined','bootstrap_unit','bootstrap_seed','included_tasks')
        comparisons={key:apply_s_verdict(algebra.compare_frozen(scores,reference,key)) for key in ('R1','R3')}
        record=dict(schema='S_E1_FROZEN_ENDPOINT_20261126_V1',
            status='FROZEN_COMPLETE_FULL_FT_PENDING',run=name,k=k,seed=0,samples=3000000,
            source_training_budget=3000000,independent_budget=True,layer=6,
            formal_H='encode_atoms output',readout_seed=0,reference_run='S_R1_s0_3M',
            source_scores=str(output/'readout/scores.json'),
            source_summary=str(output/'summary.json'),source_configuration=str(output/'configuration.json'),
            readouts={key:{field:scores[key][field] for field in fields if field in scores[key]}
                for key in ('R1','R3')},paired_frozen_vs_k10=comparisons,
            final_VAL=read(output/'VAL_3000000.json'),
            clip=read(R/'results/s_recipe'/(name+'_clip_calibration.json')),
            training_exit=training,gpu_exit=gpu,gpu_resource_close=close,
            failed_standby_exit=(read(close['failed_standby_evidence'])
                if close.get('failed_standby_evidence') else None),
            statistics_exit=phase,statistics_parent_exit=parent,statistics_command_exit=command,
            reporting_execution=execution_fields(),new_bootstrap_draws=0,new_fits=0,
            full_finetuning_complete=False,k_star=None,seed1_triggered=False,
            interpretation='Frozen component only. Wait for all registered cells and full FT before E1 selection; original recipe unchanged.')
        write(destination,record)
        write(marker,dict(status='COMPLETE',run=name,output=str(destination),
            scope='Frozen component only; original draws reused, no new resampling or fits'))
        records.append(record)
    lines=['# E1：已完成的冻结读出','',
        '全部为独立3M、seed0，第6层H0、读出种子0；k=10直接复用原S-R1的3M。这里只报告冻结部分，k*尚未判定。','',
        '| k | R1 | R3 | R3相对k10的Δ / 95%CI / τ / 判定 |',
        '| --- | ---: | ---: | --- |']
    for row in records:
        value=row['paired_frozen_vs_k10']['R3']
        decision=value['decision']
        lines.append(f"| {row['k']} | {row['readouts']['R1']['mean_normalized_improvement']:.6f} | "
            f"{row['readouts']['R3']['mean_normalized_improvement']:.6f} | "
            f"{decision['delta']:.6f} / [{decision['ci_lower']:.6f}, {decision['ci_upper']:.6f}] / "
            f"{value['threshold']:.6f} / {decision['verdict'].upper()} |")
    lines += ['', 'Δ与CI调用P既有E1函数，对原生产者的1000次分子配对抽样做差；判定沿用S任务书4.4，CI上界<0即LOSS。没有重抽、重拟合或选层。每格R1/R3置信区间、R1配对结果和原始来源见results/s_recipe/S_E1_k*_s0_3M.json。', '',
        '必须等k=1、2、5及参照的全量微调四任务×三种子闭合后，才按两种判定选择k*；当前不据冻结分量触发seed1、不改原3M配方。P/S共同k*后续仍待用户确认。','']
    (R/'docs/s_recipe/E1_FROZEN_PROGRESS.md').write_text('\n'.join(lines))
    print(json.dumps(dict(status='FROZEN_COMPONENTS_REPORTED',runs=[row['run'] for row in records],
        scores={row['run']:row['readouts'] for row in records},k_star=None,new_bootstraps=0)),flush=True)
    return 0
