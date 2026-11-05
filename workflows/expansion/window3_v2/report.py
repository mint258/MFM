"""Compose the single batch manifest/report from producer summaries only."""
import argparse
import collections
import json
from pathlib import Path
import subprocess
from .producer import read, save


def combine(config):
    totals, streams, states, reasons = (collections.Counter() for _ in range(4))
    masks, files = collections.defaultdict(collections.Counter), []
    summary_roots = [Path(config['pilot']), *map(Path, config['full_shards'])]
    for root in summary_roots:
        summary = read(root/'summary.json')
        totals.update(summary['counts']); streams.update(summary['streams']); states.update(summary['states'])
        reasons.update(summary.get('failure_reasons', {}))
        for key, value in summary['masks'].items(): masks[key].update(value)
        files.extend(read(root/'manifest.json'))
    if totals['molecules'] != 2500000 or streams != {'R':1250000,'N':1250000}:
        raise ValueError('FULL_BATCH_PRODUCER_COUNTS_NOT_COMPLETE')
    family_rows = collections.Counter()
    for ref in files: family_rows[Path(ref['path']).stem] += ref['rows']
    if (family_rows['D20'] != 2500000 or family_rows['source_status'] != 2500000
            or family_rows['D3'] != totals['conformers'] or family_rows['geometry'] != totals['conformers']):
        raise ValueError('PRODUCER_FAMILY_COUNTS_NOT_ALIGNED')
    # No parquet or molecular spool is opened here. These are the producing
    # steps' own counts, including their one-time numerical/alignment checks.
    rates = [{'field_stream':key, **dict(value),
              'fraction':value['newly_masked_records']/value['records'] if value['records'] else None}
             for key, value in masks.items()]
    return totals, streams, states, reasons, rates, family_rows, files


def accounting(job_ids):
    raw = subprocess.check_output(['sacct','-X','-P','-n','-j',','.join(job_ids),
        '-o','JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS'], text=True)
    rows = [line.split('|') for line in raw.splitlines() if line.strip()]
    parents = {row[0]:row for row in rows}
    if set(parents) != set(job_ids): raise ValueError('NATIVE_ACCOUNTING_PARENT_MISSING')
    active = {'RUNNING','PENDING','COMPLETING','SUSPENDED','CONFIGURING'}
    if any(row[1] in active for row in rows): raise ValueError('PRODUCTION_JOB_STILL_ACTIVE')
    return sum(int(row[3])*int(row[4]) for row in rows)/3600, rows


def run(config):
    totals, streams, states, reasons, rates, families, files = combine(config)
    output = Path(config['output']); output.mkdir(parents=True, exist_ok=True)
    save(output/'manifest.json', files)
    stats = read(Path(config['statistics'])/'summary.json')
    baseline = read(config['baseline_summary'])
    cost, parents = accounting(config['job_ids'])
    stored = int(subprocess.check_output(['du','-sB1',config['data_root']],text=True).split()[0])
    finite_rates = [r for r in rates if r['fraction'] is not None]
    highest = max(finite_rates,key=lambda r:r['fraction'])
    pilot = read(Path(config['pilot'])/'summary.json')
    n = totals['molecules']
    good = states['SUCCESS']; insufficient = states['INSUFFICIENT_UNIQUE_CONFORMERS']
    distribution = {(r['population_or_comparison'],r['field']):r for r in baseline['numeric']}
    values = {(r['population'],r['field']):r for r in stats['numeric']}
    rows=[]
    for group,label in [('v1_common','v1'),('pubchem_1m','PubChem随机100万'),('R','R'),('N','N')]:
        fields=values if group in ('R','N') else distribution
        rows.append('| '+label+' | '+' | '.join(f"{fields[group,field]['mean']:.3f}" for field in ('heavy_atoms','logp','tpsa_A2','rotatable_bonds'))+' |')
    coverage={row[0]:row for row in stats['coverage_to_v1']}
    text=f'''# PubChem v2 candidate：首批250万

**完成：R/N各125万来源均已处理；D20每分子一次，D3/逐原子SASA逐实际构象；家族Parquet已写出。** 固定种子、原S′ UFF参数、0.5Å去重，最多3个实际构象；不足保留实际数，不补足、不重试。

**筛选与去污染。** 原始124,857,440条；筛选通过110,050,006，化学排除14,764,875，技术未确定42,559；内部去重后109,875,599，完整InChIKey及原wp5精确去污染排除4,204,766，留下105,670,833。R/N各500万嵌套队列，首批各125万。无组成/通配符否决；PDBbind移出来源；结构未确定行保留处置记录并从下游评估排除。

**结构分布（均值；全体来源，含UFF失败）。** 完整分箱表见仓库外统计目录。

| 群体 | 重原子 | logP | TPSA/Å² | 可旋转键 |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

**覆盖（已有结果；E4.3口径待用户确认）。** R/N到v1的平均既有NN Tanimoto分别为{coverage['R'][2]:.5f}/{coverage['N'][2]:.5f}；低于0.4的比例为{coverage['R'][4]:.2%}/{coverage['N'][4]:.2%}；新骨架比例为{coverage['R'][7]:.2%}/{coverage['N'][7]:.2%}，新环系为{coverage['R'][8]:.2%}/{coverage['N'][8]:.2%}。原随机100万对v1均值0.519917。增广后的NN分布没有计算；来源自身的直接覆盖不作为查询集覆盖增益。本节不能证明E4.3完成。新增计算仍遵守任务书禁止条款，等待用户确定报告口径。全部现有分数均复用既有结果。

**UFF与标签。** 恰3构象{good:,}分子（{good/n:.2%}），不足3构象{insufficient:,}；交付{totals['conformers']:,}个实际构象。状态：{json.dumps(dict(states),ensure_ascii=False)}。失败原因保留于source_status，逐分子耗时在timings家族。物理范围新增掩码最高{highest['fraction']:.3%}（{highest['field_stream']}，{highest['newly_masked_records']}/{highest['records']}）；源缺失另计，比例不触发停止。

**运行与存储。** 1万试跑墙钟{pilot['wall_seconds']/60:.2f}分钟，分子内科学/处理CPU合计{pilot['counts']['molecule_CPU_seconds']/3600:.2f}核时；其结果直接采用。全批并发见生产配置。本次v2作业分配核时{cost:,.2f}（含失败/续接；不重复计步骤），当前目录实际占用{stored/1e9:.3f}GB，交付Parquet合计{sum(f['size'] for f in files)/1e9:.3f}GB。历史筛选/NN成本按周汇总。数据根：`{config['data_root']}`；唯一交付清单：`{output/'manifest.json'}`（仅路径、大小、行数）。

不做QM/P′或训练格式导出；v1原数据未修改。草稿PR1保持未合并，后续单点/训练格式由对应窗口决定。
'''
    Path(config['report_path']).write_text(text,encoding='utf-8')
    save(output/'batch_summary.json', {'molecules':n,'streams':dict(streams),'states':dict(states),
        'counts':dict(totals),'family_rows':dict(families),'mask_rates':rates,'failure_reasons':dict(reasons),
        'allocated_core_hours':cost,'actual_parent_rows':parents,'allocated_storage_bytes':stored})
    print(text,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True)
    run(read(parser.parse_args().config))
