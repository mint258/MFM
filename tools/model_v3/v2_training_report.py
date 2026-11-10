"""Build a small human report from producer diagnostic records only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path

REPORT_PATHS = ('results/model_v3_wandb/report/LATEST.md',
                'results/model_v3_wandb/report/training_curves.svg')
CST = timezone(timedelta(hours=8))


def closed_json_lines(path):
    """A still-open producer's incomplete final line is not a record."""
    if not path.exists():
        return []
    rows = []
    with path.open('rb') as stream:
        for line in stream:
            if not line.endswith(b'\n'):
                break
            rows.append(json.loads(line))
    return rows


def gather(manifest, progress):
    entries = {entry['job']: entry for entry in manifest['runs']}
    root = Path(manifest['tracking_root']) / 'diagnostics'
    result = []
    for current in progress['progress']:
        job = current['job']
        if job not in entries:
            raise ValueError('Report job is not in the actual training manifest')
        entry = entries[job]
        directory = root / str(job)
        observations = closed_json_lines(directory / 'system_metrics.jsonl')
        if any(row.get('job') != job or row.get('gpu') != entry['gpu'] or row.get('node') != entry['node']
               for row in observations):
            raise ValueError('System history identity differs from the real training job')
        windows = closed_json_lines(directory / 'loss_windows.jsonl')
        windows = [row for row in windows if row.get('updates') == 1000 and not row.get('partial')]
        result.append(dict(job=job, candidate=current['candidate'], progress=current, entry=entry,
            observations=observations, windows=windows,
            latest=observations[-1] if observations else None,
            latest_window=windows[-1] if windows else None))
    return result


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def system_series(observations, key):
    """Missing observations and long gaps break lines instead of filling zeros."""
    dates, values, previous = [], [], None
    for row in observations:
        timestamp = row['observed_at']
        date = datetime.fromtimestamp(timestamp, CST)
        if previous is not None and timestamp - previous > 90:
            dates.append(date)
            values.append(float('nan'))
        value = row.get('metrics', {}).get(key)
        dates.append(date)
        values.append(value if row.get('available') and finite(value) else float('nan'))
        previous = timestamp
    return dates, values


def display(value, digits=2):
    return f'{value:,.{digits}f}' if finite(value) else '缺测'


def markdown(rows, progress):
    observed = datetime.fromtimestamp(progress['observed_at'], CST).isoformat(timespec='seconds')
    lines = ['# 模型训练报告', '', '训练进度观测：' + observed + '（UTC+8）。', '',
        '当前为训练过程监测。架构与配方评价遵循任务书的完整训练预算。', '',
        '| 候选 / 实际作业 | 累计样本 | 状态 | 最近1000步总损失均值 | 均值窗口末样本 | 整卡功率 W | 整卡显存 GiB | GPU利用率 % |',
        '|---|---:|---|---:|---:|---:|---:|---:|']
    for row in rows:
        observation = row['latest'] or {}
        metrics = observation.get('metrics', {}) if observation.get('available') else {}
        window = row['latest_window'] or {}
        memory = metrics.get('gpu/memory_used_mib')
        label = str(row['candidate']).replace('|', '\\|').replace('\n', ' ')
        lines.append('| ' + ' | '.join([label + ' / ' + str(row['job']),
            f"{row['progress']['samples']:,}", row['progress']['state'],
            display(window.get('means', {}).get('total'), 6),
            f"{window['last_samples']:,}" if window else '缺测',
            display(metrics.get('gpu/power_watts')), display(memory/1024 if finite(memory) else None),
            display(metrics.get('gpu/utilization_percent'), 0)]) + ' |')
    components = sorted({key for row in rows for key in (row['latest_window'] or {}).get('means', {}) if key != 'total'})
    if components:
        lines += ['', '最近完整1000更新的分项均值（括号为有效条数）：', '',
            '| 候选 / 作业 | ' + ' | '.join(components) + ' |',
            '|---|' + '---:|' * len(components)]
        for row in rows:
            window = row['latest_window'] or {}
            values = [display(window.get('means', {}).get(key), 6) +
                ' (' + str(window.get('counts', {}).get(key, 0)) + ')' for key in components]
            lines.append('| ' + str(row['candidate']) + ' / ' + str(row['job']) + ' | ' + ' | '.join(values) + ' |')
    lines += ['', '![1000步平均损失与实际系统指标](training_curves.svg)', '',
        '损失为每个实际执行内连续1000优化器更新的算术均值，缺失分项使用各自有效条数；不混合不同续跑的重放记录。原逐步损失继续保存在完整离线SDK中。', '',
        '功率、显存和利用率属于实际物理卡；主进程指标与整卡读数分别保存。系统指标约30秒采样，缺测和超过90秒的间隔断线。图表采用实际观测时间（UTC+8），各组硬件可能不同，不按异构卡原始速度选择架构。', '',
        '系统观测与进度、损失窗口有各自时钟：', '']
    for row in rows:
        latest = row['latest'] or {}
        stamp = latest.get('observed_at')
        time_text = datetime.fromtimestamp(stamp, CST).isoformat(timespec='seconds') if stamp is not None else '尚无观测'
        sample = latest.get('metrics', {}).get('samples/cumulative')
        lines.append(f"- 作业{row['job']}：{row['entry']['node']}，`{row['entry']['gpu']}`；系统观测{time_text}，对应样本{sample if sample is not None else '缺测'}。")
    lines += ['', '交付方式：GitHub报告及每10万样本JSON持续更新；W&B保持离线，训练完成后另行提供完整W&B离线运行文件包。', '']
    return '\n'.join(lines)


def figure(rows, svg, preview=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'svg.hashsalt': 'model-v3-training-report', 'svg.fonttype': 'none'})
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.2), constrained_layout=True)
    definitions = [(axes[0, 1], 'gpu/utilization_percent', 'GPU utilization (%)', 1.),
        (axes[1, 0], 'gpu/memory_used_mib', 'GPU memory used (GiB)', 1/1024),
        (axes[1, 1], 'gpu/power_watts', 'Whole-GPU power (W)', 1.)]
    for index, row in enumerate(rows):
        color = f'C{index%10}'
        label = f"{row['candidate']} / job{row['job']}"
        windows = [window for window in row['windows'] if finite(window.get('means', {}).get('total'))]
        if windows:
            axes[0, 0].plot([window['last_samples']/1e6 for window in windows],
                [window['means']['total'] for window in windows], label=label, color=color, linewidth=1.6)
        for axis, key, title, scale in definitions:
            dates, values = system_series(row['observations'], key)
            axis.plot(dates, [value*scale for value in values], color=color, label=label, linewidth=1.2)
            axis.set_title(title)
            axis.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=CST))
            axis.set_xlabel('Actual observation time (UTC+8)')
    axes[0, 0].set_title('Mean training loss / 1000 optimizer updates')
    axes[0, 0].set_xlabel('Cumulative samples (million)')
    axes[0, 0].set_ylabel('Logged total loss')
    axes[0, 1].set_ylim(0, 105)
    for axis in axes.flat:
        axis.grid(alpha=.22)
        handles, labels = axis.get_legend_handles_labels()
        if handles:
            axis.legend(handles, labels, fontsize=8)
    fig.suptitle('Actual training execution diagnostics', fontsize=12)
    fig.savefig(svg, format='svg')
    if preview is not None:
        Path(preview).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(preview, format='png', dpi=120)
    plt.close(fig)


def write_report(manifest, progress, repo):
    rows = gather(manifest, progress)
    cache = Path(manifest['tracking_root']) / 'report-mpl'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(cache)
    paths = [Path(repo) / path for path in REPORT_PATHS]
    paths[0].parent.mkdir(parents=True, exist_ok=True)
    paths[0].write_text(markdown(rows, progress))
    figure(rows, paths[1], manifest.get('report_preview'))
    return [dict(path=relative, mode='100644', type='blob', content=path.read_text())
        for relative, path in zip(REPORT_PATHS, paths)]
