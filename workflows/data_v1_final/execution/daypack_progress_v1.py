"""Write current operational progress from small metadata, without opening science bodies."""
import json
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q


def main():
    Q.on_login()
    root = Q.ROOT
    base = root / 'control/cpu_packed_day_v1/dv1_pack_sprime_remaining_20261028_v1'
    sub = Q.load(base / 'submission.json')
    out = root / 'artifacts/conformers/formal_cpu_auto_v3/packed_day_v1/day01'
    census = Q.load(out / 'actual_ordinary_census.json')
    live = Q.query(['squeue', '-h', '-j', sub['job_id'], '-o', '%i|%T|%C|%M|%l|%N']).strip()
    names = ('dispatch', 'starts', 'packets', 'errors', 'internal_checkpoints')
    counts = {name: sum(p.is_file() for p in (out / name).iterdir()) for name in names}
    observed = Q.now()
    record = {'schema': 'ROOT_DAYPACK_OPERATIONAL_PROGRESS_V1', 'observed_at': observed,
        'job_id': sub['job_id'], 'squeue': live, 'own_output_directory_metadata_counts': counts,
        'original_census_state_counts': census['state_counts'],
        'candidate_state_counts': census['candidate_state_counts'],
        'scientific_quality_or_population_complete': False,
        'scientific_packet_bodies_opened_or_hashed_by_report': False}
    stamp = observed.replace(':', '').replace('-', '').replace('.', '').replace('+', '_')
    ref = Q.write_new(root / 'control' / ('daypack_progress_' + stamp + '.json'), record)
    text = f'''# 2026-10-28 单日打包实际进度

目的：按用户要求把生产工作合并为约一天的作业，复用已完成结果。

观测时间：{observed}。本报告由 workflows/data_v1_final/execution/daypack_progress_v1.py 从真实 Slurm 和小元数据生成。

- S′ 单一作业 {sub['job_id']}，现场状态 {live}。64CPU、24小时上限、无SBATCH内存申请。9项作业内预检已通过。
- 候选剩余32749分子；已派发{counts['dispatch']}、已启动{counts['starts']}、已存结果包{counts['packets']}、执行器错误文件{counts['errors']}。这些是文件元数据计数，不代表最终科学成功率。
- 原结果清点：{json.dumps(census['state_counts'], ensure_ascii=False)}。500分子仅作内部检查点，不产生子Slurm作业。
- Drugs全75099名称/558002构象的保守身份并集已通过严格消费读回，实际4524566 C0/82秒/16CPU/1312分配核秒，原126构象差异与31名称差异全部保留。Kraken此前已READY；全11来源仍须汇总验收。
- 标签全量数值缓存旧batch2实际4524528 C0/1430秒/16CPU/22880分配核秒；16源各自游标139392，累计2230272源物理行。后续按单日父作业继续，不再逐短批提交。
- P′已有1200次限定诊断及独立读回；500项原向量比较通过断言。单位、符号、张量与坐标原点仍须完成完整证据审阅，2000构象试点及全量尚未放行。

输入证据及哈希：本次观测 {ref['path']}，{ref['bytes']}B，SHA256 {ref['sha256']}。其余实际来源见 control/active_checkpoint_v41.json、Drugs READY candidate 和标签batch2真实会计与独立Root接受对象。

已知限制：整轮D1–D7、共同人群最终阈值、P′正式生成及扩充第一批尚未全部完成。原始结果、失败与UNKNOWN、配方及全部质量阈值保持。技能1.0.123已同步本机和X盘。
'''
    dest = Q.REPO / 'docs/data_v1/actual_progress_20261028_daypack_v1.md'
    dest.write_text(text, encoding='utf-8')
    status = Q.REPO / 'docs/interfaces/STATUS.md'
    prior = status.read_text(encoding='utf-8')
    marker = '## 2026-10-28 单日打包与全量继续'
    if marker not in prior:
        note = marker + '\n\n最新实际状态见[单日打包进度](../data_v1/actual_progress_20261028_daypack_v1.md)。S′已改为真实64CPU/24h单一作业4524556，内部500仅作检查点；Drugs严格去污染身份投影4524566实际C0并独立接受，Kraken既有READY复用；标签数值余量正在改为单日父作业。1200次P′限定诊断已经完成，500项原向量比较实际通过，旧“待授权”段落保留原时间点历史；物理参考系/张量证据及正式2000/full仍待完整验收。全指南goal继续执行，D1仍未jointfreeze，D1–D7与扩充最终交付尚未完成。\n\n'
        status.write_text(note + prior, encoding='utf-8')
    print(json.dumps({'operational_receipt': ref, 'report': str(dest), 'scientific_DATA_body_reads': 0}))


if __name__ == '__main__':
    main()
