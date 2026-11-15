"""Append the stereo supplement from closed metadata only; no label readback."""
import argparse
import collections
import json
from pathlib import Path

from .capacity import protect
from .producer import read,save

MARKER='## 未指定立体化学补跑'


def ratio(counts,a,b):
    n=counts.get(a,0)+counts.get(b,0)
    return '未计得' if not n else f"{counts.get(a,0)/n:.2%}/{counts.get(b,0)/n:.2%}"


def section(batch,all_graph,only_3d,resources,manifest_path):
    """Render producer counts, explicitly distinguishing positive shortages/zero."""
    counts=batch['effective_conformer_counts']
    cip,ez=batch['assigned_CIP_counts'],batch['assigned_EZ_counts']
    extra_cip={k:v for k,v in cip.items() if k not in ('R','S') and v}
    extra_ez={k:v for k,v in ez.items() if k not in ('E','Z') and v}
    rows=[]
    for name,value in [('全部来源图（原结果复用）',all_graph),('仅含实际3D的来源',only_3d)]:
        after=value['after'];n=value['queries'];c=value['counts']
        rows.append(f"| {name} | {value['reference_molecules']:,} | {after['mean']:.6f} | {after['population_std']:.6f} | "+
                    ' / '.join(f"{c['after_below_'+t]/n:.2%}" for t in ('0.4','0.6','0.8'))+' |')
    new_positive=batch['molecules_with_3D']-batch['original_molecules_with_3D']
    failed=batch['stereo_unique_molecules']-new_positive
    cpu=sum(s['counts'].get('molecule_CPU_seconds',0) for s in batch['producer_summaries'])/3600
    return f'''\n\n{MARKER}（{resources['finished_on']}）

本次仅处理原1,285,342条立体参照缺失记录；原D20及已有几何直接复用。最终全批恰3构象{counts.get('3',0):,}分子、实际1–2构象{counts.get('1',0)+counts.get('2',0):,}、0构象{counts.get('0',0):,}、构象数未知{counts.get('unknown',0):,}；含3D共{batch['molecules_with_3D']:,}分子、{batch['final_conformers']:,}个实际构象。补跑新增含3D分子{new_positive:,}，其余零3D/未知{failed:,}；全批零几何状态为{json.dumps(batch['zero_geometry_states'],ensure_ascii=False)}。

最终采用/末次参照的CIP计数{json.dumps(cip,ensure_ascii=False)}，R/S={ratio(cip,'R','S')}（分母R+S，其他{json.dumps(extra_cip,ensure_ascii=False)}另列）；双键计数{json.dumps(ez,ensure_ascii=False)}，E/Z={ratio(ez,'E','Z')}（其他{json.dumps(extra_ez,ensure_ascii=False)}）。均仅描述；重抽{batch['redrawn_molecules']:,}个最终有效分子，其中最终0构象{format(batch['redrawn_final_zero_conformers'],',') if 'redrawn_final_zero_conformers' in batch else '未计得'}、构象数未知{format(batch['redrawn_unknown_conformer_count'],',') if 'redrawn_unknown_conformer_count' in batch else '未计得'}；历史处理事件中的重抽计数{batch.get('redrawn_processing_events',batch['redrawn_molecules']):,}另列，不与最终分子数混用。另修复{batch['preparation_repairs']:,}条零嵌入/UFF调用的准备失败，未重做任何已有几何或原生失败，计数已替换而非重复加入。原S′/UFF参数、30候选、0.5Å及最多3实际构象保持，不补足。

覆盖沿用原固定100万查询、完整1,196,122个v1参考顺序前缀、原指纹和自匹配口径；加入前NN均值{all_graph['before']['mean']:.6f}、总体标准差{all_graph['before']['population_std']:.6f}。

| 加入后的参考范围 | 参考分子数 | NN均值 | 总体标准差 | 低于0.4 / 0.6 / 0.8 |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

本补充Slurm分配{resources['allocated_core_hours']:,.2f}核时（含准备、单测、失败及修复；原批次成本不重复计）；已记录分子内CPU{cpu:,.2f}核时（缺失的历史调用CPU不计为零）。新增Alpha目录实际{resources['alpha_storage_bytes']/1e9:.3f}GB、Main本次NN目录{resources['main_storage_bytes']/1e9:.3f}GB；交付Parquet引用合计{resources['manifest_bytes']/1e9:.3f}GB。唯一最终清单：`{manifest_path}`（path/size/rows）。原状态/SMILES/CID保留，当前状态/实际数/顺序使用effective_*；无新去污染查询、指纹计算、QM/P′或训练导出。
'''


def run(config):
    if not config.get('disk_checks'):
        raise ValueError('ACTUAL_REPORT_TARGET_DISK_PROTECTION_REQUIRED')
    delivery=Path(config['delivery'])
    batch=read(delivery/'batch_summary.json')
    old=read(config['original_batch_summary'])['augmented_nn']
    nn_root=Path(config['nn_3D'])
    nn=read(nn_root/'summary.json');nn_files=read(nn_root/'manifest.json')
    native=read(nn_root/'accounting.json');resources=read(config['resources'])
    if (native['state']!='COMPLETED' or native['exit_code']!='0:0'
        or nn['reference_scope']!='pubchem_with_3D' or nn['queries']!=1000000
        or nn['original_reference_prefix']!=1196122
        or nn['added_reference_molecules']!=batch['molecules_with_3D']
        or nn['reference_molecules']!=1196122+batch['molecules_with_3D']
        or nn['new_fingerprints_computed']!=0 or sum(r['rows'] for r in nn_files)!=1000000
        or sum(batch['effective_states'].values())!=2500000
        or batch['stereo_unique_molecules']!=1285342 or batch['D20_recomputed']!=0):
        raise ValueError('CLOSED_STEREO_SUPPLEMENT_AND_ONLY_3D_COVERAGE_REQUIRED')
    files=read(delivery/'manifest.json');known={r['path'] for r in files}
    files.extend(r for r in nn_files if r['path'] not in known)
    families=collections.Counter()
    for ref in files:families[Path(ref['path']).stem]+=ref['rows']
    if any(families[k]!=n for k,n in [('D20',2500000),('source_status',2500000),
        ('D3',batch['final_conformers']),('geometry',batch['final_conformers'])]):
        raise ValueError('FINAL_MANIFEST_PRODUCER_COUNTS_DIFFER')
    resources=dict(resources,manifest_bytes=sum(r['size'] for r in files))
    text=section(batch,old,nn,resources,delivery/'manifest.json')
    path=Path(config['report']);original=path.read_text(encoding='utf-8')
    if MARKER in original:raise ValueError('SUPPLEMENT_ALREADY_APPENDED_RETAIN_EXISTING_REPORT')
    protect(config)
    save(delivery/'manifest.json',files)
    with path.open('a',encoding='utf-8') as stream:stream.write(text)
    print(text,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True)
    run(read(parser.parse_args().config))
