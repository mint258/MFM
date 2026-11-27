"""Render cached execution accounting; no scientific files are read."""
import csv
import datetime
import io
import json


def _csv(fields, rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='raise')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def render(summary, inventory, slurm):
    """Keep physical GPU union totals separate from overlapping producer rows."""
    if (summary['inventory_snapshot_time'] != inventory['observed_time']
            or summary['Slurm_snapshot'] != slurm['latest_snapshot']):
        raise ValueError('Export the exact cached inputs of the closed summary')
    if summary['models_predictions_labels_scores_VAL_read'] is not False:
        raise ValueError('Only execution metadata accounting may be rendered')
    gpu = summary['GPU']
    cpu = summary['CPU']
    unverified = {tuple(row['identity']) for row in summary['producer_closure_not_fully_observed']}
    producer_rows = []
    for row in gpu['unique_producers']:
        node, uid, pid, ticks = row['identity']
        producer_rows.append(dict(node=node, uid=uid, pid=pid, start_ticks=ticks,
            gpu_uuid=row['gpu_uuid'], started_at=row['started_at'], ended_at=row['ended_at'],
            producer_wall_seconds=row['ended_at']-row['started_at'],
            exit_code=row['exit_code'], closure_verified=tuple(row['identity']) not in unverified,
            sources=json.dumps(row['sources'], ensure_ascii=False)))
    native_fields = ('node', 'uid', 'pid', 'start_ticks', 'handle', 'stage', 'started_at',
        'ended_at', 'wall_seconds', 'cpu_user_seconds', 'cpu_system_seconds',
        'exit_code', 'command_exit_code', 'source')
    native_rows = []
    seen = set()
    for row in inventory['closed_native_CPU_proofs'].values():
        producer = row['producer']
        key = (row['node'], producer['uid'], producer['pid'], producer['start_ticks'])
        if key in seen:
            continue
        seen.add(key)
        native_rows.append({field: producer[field] if field in ('uid', 'pid', 'start_ticks')
            else row.get(field) for field in native_fields})
    jobs = list(slurm['jobs'].values())
    job_fields = tuple(sorted({key for row in jobs for key in row}))
    text = [
        '# S：已闭合运行阶段的成本记录', '',
        '**这是部分成本记录，不能代表研究结项或全部实验成本。**', '',
        '仅使用已缓存的执行元数据；在跑训练和尚未入账的后续阶段不计入本表。'
        '空单元格表示未观测，不能当成零。', '',
        '| 指标 | 数值 |', '| --- | ---: |',
        f"| GPU绑定墙钟区间并集（秒） | {gpu['bound_GPU_wall_seconds']:.6f} |",
        f"| GPU绑定墙钟区间并集（小时） | {gpu['bound_GPU_wall_seconds']/3600:.6f} |",
        f"| 去重后的GPU生产者 | {len(producer_rows)} |",
        f"| GPU生产者退出码缺失 | {gpu['unknown_producer_exit_codes']} |",
        f"| GPU生产者完整退出证明缺失 | {len(unverified)} |",
        f"| Slurm已闭合句柄 | {len(jobs)} |",
        f"| Slurm分配CPU时间（核秒） | {cpu['Slurm_allocated_CPU_seconds']} |",
        f"| Slurm账面TotalCPU（秒，不能视为真实耗时） | {cpu['Slurm_measured_CPU_seconds']:.6f} |",
        f"| 原生短CPU实测时间（秒） | {cpu['native_measured_CPU_seconds']:.6f} |",
        f"| Slurm TotalCPU字段缺失句柄 | {len(cpu['Slurm_jobs_missing_measured_CPU_time'])} |",
        f"| 原生短CPU时间缺失生产者 | {cpu['native_producers_missing_CPU_time']} |", '',
        'GPU总量按同一UUID的闭合区间并集计算。生产者CSV中的区间可能重叠，'
        '不能直接相加得到这个总量。它不是CUDA忙碌时间、能耗或货币账单。'
        'Slurm分配CPU时间与实测CPU时间是不同量，不能相加。'
        '原生GPU阶段的CPU执行时间没有完整观测，不补估计值。', '',
        '本集群这份缓存的TotalCPU字段均报零；已运行的已完成作业及其batch/extern行'
        '也观察到零。零字段不代表真实CPU计算量为零，不能作为有效CPU计量。'
        '原始账面值保留在CSV中，真实Slurm CPU执行成本视为计量缺口。', '',
        '失败阶段仍入账；取消且零分配时长的待机句柄不冒充GPU生产者。'
        '旧记录的未知退出码与缺失退出证明保留原状。', '',
        '## 来源与覆盖边界', '',
        f"- 运行清单缓存时间（UTC）：{datetime.datetime.fromtimestamp(inventory['observed_time'], datetime.timezone.utc).isoformat()}",
        f"- Slurm缓存快照：`{slurm['latest_snapshot']}`",
        f"- 尚未闭合或当时尚未入账的执行来源：{len(summary['excluded_open_execution_sources'])}",
        f"- 缺失绑定来源：{len(summary['missing_bound_sources'])}",
        f"- 未识别绑定来源：{len(summary['unrecognized_bound_execution_sources'])}", '',
        '逐项数据见同目录的GPU区间、Slurm和原生CPU三个CSV。'
        '完整来源路径与生产者身份随表保留，用于追溯，不重读模型、预测或科学统计。', '',
    ]
    return {
        'cost_closed_phases_20261127.md': '\n'.join(text),
        'cost_GPU_producers_20261127.csv': _csv(tuple(producer_rows[0]) if producer_rows else
            ('node', 'uid', 'pid', 'start_ticks', 'gpu_uuid', 'started_at', 'ended_at',
             'producer_wall_seconds', 'exit_code', 'closure_verified', 'sources'), producer_rows),
        'cost_Slurm_jobs_20261127.csv': _csv(job_fields or ('job_id',), jobs),
        'cost_native_CPU_20261127.csv': _csv(native_fields, native_rows),
    }
