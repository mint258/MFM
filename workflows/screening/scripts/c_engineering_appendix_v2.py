"""C4/C5 actual decision appendix plus C3 closure and shared-registry metadata.

JSON-only analysis; no numeric-profile rerun, original data write or adoption.
Optional ESP/CD scope bytes are explicitly ratio models, not reserialized
joint-compression measurements. Every currently parsed scientific value stays.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
CD={'pm7_ESP','pm7_water','pm7_octanol','pm7_cation','pm7_anion'}

def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    pending=Path(str(path)+'.pending');pending.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n');pending.replace(path)

def inclusion(entry):
    return (entry['registry_id'],entry['task'],entry['source_path'],entry['classification'],
        bool(entry.get('derived_from')),bool(entry.get('dedup_of')),bool(entry.get('excluded')))

def registry_delta(storage,new_path):
    old_path=Path(storage['registry']['candidate_snapshot']);old=read(old_path);new=read(new_path)
    left=[inclusion(entry) for entry in old['entries']];right=[inclusion(entry) for entry in new['entries']]
    same=left==right
    return {'original_actual_snapshot':{'path':str(old_path),'sha256':sha(old_path),'bytes':old_path.stat().st_size},
        'corrected_shared_registry':{'path':str(new_path),'sha256':sha(new_path),'bytes':new_path.stat().st_size},
        'same_ID_order_source_paths_classification_and_inclusion':same,
        'same_per_record_numeric_wire':same,
        'shared_metadata_delta_bytes':new_path.stat().st_size-old_path.stat().st_size if same else None,
        'count_delta_once_globally_not_per_record_or_file':True,
        'numerical_profile_rerun':False,
        'corrections':'Native vs perturbed geometry context; atom-level Fukui names/semantics. Original measured candidate snapshot retained.'}

def ratio_scenarios(storage,population):
    rows=[]
    for name,summary in storage['populations'].items():
        sums=summary['total_estimated_bytes'];base=sums['base_Data_zstd3_bytes']
        observed_joint=sums['all_registry_nohessian_zstd3_bytes']
        groups=[row for row in storage['P_task_group_projections'] if row['population']==name and row['task']!='xtb_hessian']
        strata={row['size_stratum']:row for row in population[name]['strata']}
        denominator=sum(row['standalone_zstd3_estimated_bytes'] or 0 for row in groups)
        missing=any(row['standalone_zstd3_estimated_bytes'] is None for row in groups)
        for drop_ESP,minimum_CD in ((False,False),(True,False),(False,True),(True,True)):
            modeled=0.0
            for group in groups:
                amount=group['standalone_zstd3_estimated_bytes']
                if amount is None:continue
                if drop_ESP and group['task']=='pm7_ESP':continue
                if minimum_CD and group['task'] in CD:
                    weight=strata[group['size_stratum']]
                    amount*=weight['molecules']/weight['records']
                modeled+=amount
            fraction=modeled/denominator if denominator else None
            estimate=base+(observed_joint-base)*fraction if base is not None and observed_joint is not None and fraction is not None and not missing else None
            rows.append({'population':name,'ESP_scope':'DROP' if drop_ESP else 'ALL',
                'PM7_C_D_scope':'MOLECULAR_MINIMUM' if minimum_CD else 'ALL_CONFORMERS',
                'xTB_nonhessian_scope':'ALL_CONFORMERS','Hessian_scope':'EXCLUDED_FROM_THIS_RATIO_TABLE',
                'standalone_group_byte_fraction':fraction,'estimated_joint_zstd3_nohessian_value_bytes':estimate,
                'actual_joint_reserialization_measured':not drop_ESP and not minimum_CD,
                'whole_scope_is_adopted':False,
                'model':'Hold measured compressed base fixed; scale measured joint non-hessian P marginal by sum of standalone task-group compression sizes retained. All/min task amount ratio approximated by A molecule/record counts.',
                'limits':'Task groups are separately compressed; joint zstd is not additive. Atom/molecular-minimum data size distribution can differ from all conformers. B-derived-from-CD fields and all old per-case QC stay in fixed B marginal, conservatively overcounting a future CD-min recipe. Does not delete current labels, assign unknown records to TRAIN, or determine final field format.'})
    return rows

def markdown(report):
    storage=report['C4'];delta=report['registry_update'];xyz=report['C5']
    def gb(value):return '未测' if value is None else f'{value/1e9:.3f}'
    def tb(value):return '未测' if value is None else f'{value/1e12:.3f}'
    lines=['| 工程项 | 实际关键数字 | 配置决策与状态 |','|---|---|---|',
        f"| C4样本 | {storage['sample_records']:,}条、{len(storage['actual_worker_pids'])}实际worker、{storage['records_with_issues']}问题、{storage['seconds']:.1f}s | 原Data修D20/HBA+指定3D+注册表P；最终wire未采纳 |",
        '| C4严格 | Data基础184.272 GB；全P zstd3 546.396 GB；逐记录页模型565.975 GB | 全C/D与全部xTB的完整科学标签候选，含100%最低构象Hessian |',
        '| C4放宽 | Data基础219.007 GB；全P zstd3 649.887 GB；逐记录页模型672.894 GB | plain pickle5约2.288 TB，压缩格式及LMDB实际页开销需作为配置选择 |',
        '| 五文件放宽 | 旧20/25/30/40字节max/min 2.211；建议22/26/30/36为1.067 | molecule maxNheavy边界建议，同分子不跨文件，未改变任何数据 |',
        f"| C4写回峰值 | 放宽、无Hessian、成功普通原输出仅留最低且失败全留：页模型+解析+400GB，per-call保守约1.885 TB，快照约1.911 TB，余26.483 GB | 余量需扣实际quota变化/C3暂存；不是已预留容量或600GB LMDB上限内 |",
        f"| Registry v2 | {len(storage['registry']['entries'])}个稳定ID；共享元信息仅增加{delta['shared_metadata_delta_bytes']} B、全局一次 | 数值record wire不变，C4原测量保留、不重跑 |",
        f"| C5 | {xyz['records']:,}/{xyz['records']:,}通过；最大偏差{xyz['xyz_max_error_A']:.3e} A；全部原子顺序/原键图可用 | 显式xyz往返已完成，几何供B5 |",
        f"| C3 | 设计六桶已闭合{report['C3_closed_design_cohorts']}/6；原14–19直接测量{report['C3_original_physical_nodes_measured']}/6；实际执行节点{report['C3_actual_execution_nodes_measured']}个 | 用户已授权15→12、16→13；原物理15/16未直接测量；满29槽并发峰值未实测 |",'',
        'C4完整候选大小与五文件边界（GB十进制）：','',
        '| 保留集 | 原payload | D20+3D Data pickle4 | Data+P plain pickle5 | Data+P zstd3 | 逐记录4KiB模型 |','|---|---:|---:|---:|---:|---:|']
    for key,value in storage['populations'].items():
        total=value['total_estimated_bytes']
        lines.append(f"| {key} | {gb(total['source_payload_bytes'])} | {gb(total['base_Data_pickle4_bytes'])} | {gb(total['all_registry_candidate_pickle5_bytes'])} | {gb(total['all_registry_candidate_zstd3_bytes'])} | {gb(total['per_record_4KiB_rounding_estimate_bytes'])} |")
    lines+=['','页模型为每record向4KiB取整的规划估计，Btree/空闲页/碎片没有实际LMDB测量。600GB既定LMDB预留被放宽完整候选超过；本报告不自动改预算或字段。','',
        '| 保留集 | 原边界max/min | 字节平衡边界 | 新max/min |','|---|---:|---|---:|']
    for key,value in storage['five_files'].items():
        original=value['baseline_20_25_30_40'];new=value['suggested_byte_balanced']
        lines.append(f"| {key} | {original['max_to_min_byte_ratio']:.3f} | {new['boundaries_max_molecule_heavy']} | {new['max_to_min_byte_ratio']:.3f} |")
    lines+=['','写回峰值：下表仍保留全部当前科学标签；“原输出只留最低”只改变raw归档策略。源归档是WITH_POLAR旧完整pilot，C3闭合后的NOPOLAR实际系数另行补充。','',
        '| 保留集 | raw策略 | 压缩模型 | Hessian比例 | 预估峰值TB | quota余GB |','|---|---|---|---:|---:|']
    for row in storage['writeback_peak_scenarios']:
        if row['value_format']!='per_record_4KiB_rounding_estimate_bytes' or row['hessian_fraction'] not in (0,.1,1):continue
        policy='B成功仅最低' if row['raw_policy']=='SUCCESS_B_MINIMUM_OTHER_OUTPUTS_UNCHANGED' else '普通成功仅最低/失败全留'
        model='pack期望' if row['raw_model']=='EXPECTED_SAME_SIZE_PACK_FACTOR' else 'per-call相加'
        correction=delta['shared_metadata_delta_bytes'] or 0
        peak=row['writeback_peak_forward_bytes']+correction if row['writeback_peak_forward_bytes'] is not None else None
        head=row['headroom_bytes']-correction if row['headroom_bytes'] is not None else None
        lines.append(f"| {row['population']} | {policy} | {model} | {row['hessian_fraction']} | {tb(peak)} | {gb(head)} |")
    lines+=['','以下是未来计算范围的可选字节模型，含“C/D最低”的覆盖变化；不是当前raw保留策略，也没有删除任何已解析科学值。计算核时由Root C1同范围矩阵对应。分组zstd不能精确相加，故非基准项均标为比率估计。','',
        '| 保留集 | ESP | C/D | 联合无Hessian候选GB | 口径 |','|---|---|---|---:|---|']
    for row in report['optional_scope_byte_ratio_models']:
        lines.append(f"| {row['population']} | {row['ESP_scope']} | {row['PM7_C_D_scope']} | {gb(row['estimated_joint_zstd3_nohessian_value_bytes'])} | {'原实测' if row['actual_joint_reserialization_measured'] else '分组比率估计'} |")
    lines+=['','旧10020样本是严格保留集的分层全分子样本；新放宽立体差异记录的label大小在同层内代表性是外推假设。4,900 unassigned包含4,100 external-test embargo和800未解析QM7 composition，工程不赋TRAIN。split/角色完整性与正式准入按A3决策。','',
        f"B5实证{report['B5_atom_graph_aligned_molecules']}分子原子序列/原键图匹配；Fukui分量原数值保持，v2仅修层级、名称和geometry/electronic context。所有int原值/float64/空值/QC在已关闭C4测量中保留；不用metadata修订重跑QM或numeric profile。",'',
        'C3 sampler测同UID精确job cgroup或验证自有进程树的同时RSS/PSS；sacct MaxRSS空白/cgroup memory.peak不可用保持null。用户已明确批准设计15/16桶分别在实际12/13执行，分子桶仍按原%6规则，不改变分片。四个原节点14/17/18/19与两个替代节点构成本轮六份测量；原物理15/16未直接测量。原计划14–19的29槽保留为部署上下文，替代节点容量单列。单节点测量乘原槽数仅规划/转移外推；满29槽同时峰值未实测。','',
        '源引用、完整数字、候选参数与限制见工程appendix JSON；原C4 snapshot、结果与全部当前科学文件保留。']
    lines+=['','C3设计/执行映射：','',
        '| 原设计节点 | 实际执行节点 | 已闭合 | 原物理节点直接测量 | 原计划k24槽位 |','|---|---|---|---|---:|']
    for row in report.get('C3_nodes',[]):
        lines.append(f"| {row['design_node']} | {row.get('actual_node') or '未闭合'} | {row['closed_probe']} | {row['original_physical_node_measured']} | {row['slots']} |")
    calibration=report.get('C3_archive_recheck')
    if calibration:
        lines+=['','C3 NOPOLAR闭合归档元数据校准（不重打包、不删raw）：','',
            '| 范围 | size层 | 分子执行数 | 唯一分子 | per-call压缩GB | 实际闭合归档GB | pack系数 |','|---|---|---:|---:|---:|---:|---:|']
        for row in calibration['calibrations']:
            if row['scope']!='UNIQUE_MOLECULE_FIRST_CLOSED_ROUND':continue
            factor='未测' if row['archive_pack_factor'] is None else f"{row['archive_pack_factor']:.6f}"
            lines.append(f"| {row['scope']} | {row['size_stratum']} | {row['molecule_executions']} | {row['unique_molecules']} | {gb(row['percall_compressed_bytes'])} | {gb(row['closed_archive_bytes'])} | {factor} |")
        lines+=['','重复benchmark轮不扩大独立人口。NOPOLAR闭合系数单列用于工程比较；上文C4写回估算仍是已测旧WITH_POLAR归档模型，未把新的选择性归档、跨轮样本或压缩比当作实际重打包结果。']
    else:
        lines+=['','C3 NOPOLAR闭合归档校准尚未生成；C4的旧WITH_POLAR归档预算保持原测量口径。']
    return '\n'.join(lines)+'\n'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    parser.add_argument('--c-summary',default=str(ROOT/'reports/c_engineering_summary_v3.json'))
    parser.add_argument('--registry',default=str(ROOT/'reports/label_registry_v2.json'))
    parser.add_argument('--output',default=str(ROOT/'reports/c_engineering_appendix_v2.json'));args=parser.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());print(json.dumps({'status':'AST_PASS','numeric_profile_rerun':False}));return 0
    storage_path=ROOT/'c_engineering/storage/storage_report.json';xyz_path=ROOT/'c_engineering/xyz/xyz_report.json'
    storage=read(storage_path);xyz=read(xyz_path);population=read(ROOT/'a_retained/population_by_stratum.json')
    summary=read(args.c_summary) if Path(args.c_summary).is_file() else None
    delta=registry_delta(storage,Path(args.registry))
    if not delta['same_per_record_numeric_wire']:raise ValueError('Registry inclusion/order changed; cannot assert numeric-wire equivalence')
    b5_path=ROOT/'b_quantum/analysis/B5_coverage_ICC.json';b5=read(b5_path)
    archive_path=ROOT/'c_engineering/c3_archive_recheck.json'
    archive=read(archive_path) if archive_path.is_file() else None
    archive_summary={key:archive.get(key) for key in ('status','nodes_closed','unique_molecules','molecule_executions','actual_worker_pids','calibrations','WITH_POLAR_full10020_reference','issues','scope_note')} if archive else None
    report={'status':'C4_C5_ENGINEERING_APPENDIX_CLOSED_C3_STATUS_SEPARATE','C4':storage,'C5':xyz,
        'C3_closed_nodes':summary['C3_closed_nodes'] if summary else len(list((ROOT/'c_engineering/nodes').rglob('node_probe_report.json'))),
        'C3_closed_design_cohorts':summary.get('C3_closed_design_cohorts') if summary else None,
        'C3_original_physical_nodes_measured':summary.get('C3_original_physical_nodes_measured') if summary else None,
        'C3_actual_execution_nodes_measured':summary.get('C3_actual_execution_nodes_measured') if summary else None,
        'C3_nodes':summary.get('C3_nodes',[]) if summary else [],
        'C3_user_authorized_substitutions':summary.get('C3_user_authorized_substitutions',[]) if summary else [],
        'C3_original_physical_15_16_measured':summary.get('C3_original_physical_15_16_measured') if summary else None,
        'C3_original_planned_slots':29,'full29_concurrent_peak_measured':False,
        'C3_archive_recheck':archive_summary,
        'C3_archive_recheck_reference':{'path':str(archive_path),'sha256':sha(archive_path)} if archive else None,
        'C3_summary_reference':{'path':args.c_summary,'sha256':sha(args.c_summary)} if summary else None,
        'registry_update':delta,'optional_scope_byte_ratio_models':ratio_scenarios(storage,population),
        'B5_atom_graph_aligned_molecules':b5['atom_graph_aligned_molecules'],
        'B5_source':{'path':str(b5_path),'sha256':sha(b5_path)},
        'source_C4':{'path':str(storage_path),'sha256':sha(storage_path)},
        'source_C5':{'path':str(xyz_path),'sha256':sha(xyz_path)},
        'script_sha256':sha(__file__),'created_epoch':time.time(),'LMDB_written':False,'QM_started':False,
        'numeric_profile_repeated':False,'budget_or_schema_adopted':False,'current_scientific_labels_deleted':False}
    output=Path(args.output).absolute()
    if not output.is_relative_to(ROOT/'reports'):raise ValueError('Own report output only')
    save(output,report);output.with_suffix('.md').write_text(markdown(report),encoding='utf-8')
    print(json.dumps({'status':report['status'],'shared_registry_delta_bytes':delta['shared_metadata_delta_bytes'],
        'C3_closed_nodes':report['C3_closed_nodes'],'C4_records':storage['sample_records']}));return 0

if __name__=='__main__':raise SystemExit(main())
