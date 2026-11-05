"""Render the formal Pprime status from the original closed audit, with no DATA read."""
import json
from pathlib import Path
ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
CONTROL = ROOT / 'control/Pprime_complete_remaining_20261104_v1'
ANALYSIS = ROOT / 'artifacts/pprime_complete_remaining_20261104_v1/final_delivery/final_analysis.json'
REPORT = ROOT / 'repository/docs/data_v1/pprime_labels.md'
MARKER = '<!-- ORIGINAL_PPRIME_PILOT_HISTORY -->'

def main():
    v = json.loads(ANALYSIS.read_text(encoding='utf-8'))
    closure = json.loads((CONTROL / 'root_final_completion_20261105_v1.json').read_text(encoding='utf-8-sig'))
    if v['status'] != 'ALL_FROZEN_READY_CALCULATIONS_AND_PHYSICAL_RECORD_COVERAGE_VERIFIED' or closure['status'] != 'COMPLETE_DO_NOT_RESUME_OR_RECOMPUTE':
        raise ValueError('Actual closed audit and final completion required')
    original = REPORT.read_text(encoding='utf-8-sig')
    if MARKER in original:
        original = original.split(MARKER, 1)[1].lstrip()
    rows = [
        ('原 ready 分子', v['original_ready_molecules']),
        ('完成构象', v['completed_conformers']),
        ('全12项成功构象', v['all12_success']),
        ('非全12项成功构象', v['not_all12_success']),
        ('全12项成功率', format(100*v['all12_success_fraction'], '.6f')+'%'),
        ('全任务结果行', v['all12_task_rows']),
        ('缺失构象', v['missing_conformers']),
        ('意外构象', v['unexpected_conformers']),
        ('审计覆盖 family 文件', v['verified_files']),
        ('审计覆盖 family 字节', v['verified_family_bytes']),
        ('原ready范围之外N1或不可用分子', v['N1_or_unavailable_molecules_outside_original_ready_scope']),
        ('生成实际父作业数', v['generation_actual_parent_count']),
        ('生成分配核时', v['generation_allocated_core_hours']),
        ('每请求构象生成分配核秒', v['generation_core_seconds_per_requested_conformer']),
    ]
    lines = ['# P′ 标签：冻结输入范围计算与覆盖已完成', '',
        '2026-11-05。此为原冻结 ready 范围的计算和覆盖闭合，不代表最终 Common 或 D-6 放行。下文旧试点准备记录仅作历史。', '',
        '| 项目 | 原闭合审计结果 |', '| --- | --- |']
    lines += ['| '+name+' | '+str(number)+' |' for name, number in rows]
    lines += ['', '原固定随机顺序前两个构象、版本、关键词、精度、种子、输入及900秒单调用超时保持。失败和UNKNOWN历史保留，不重复Native重试。生成核时只包含生成父作业，不包括元数据、验证、清理和只读恢复，不代表全流程总成本。成功率超过用户已批准的99.45%线。',
        '', '实际最终审计：'+closure['final_actual_audit']+'。本摘要只消费原闭合JSON，不增加审计、哈希、读回或QM。',
        '', '正式结果：'+str(ANALYSIS)+'；原计算/覆盖审计脚本：'+str(CONTROL/'audit_final_full_v2.py')+'。其task_failures、role_outcomes、roles、family_rows保留失败、角色及家族计数；同目录completion_manifest.json追溯正式交付。',
        '', '待完成：最终Common绑定、原1.5异常值扫描、TRAIN归一化、P/P′同字段分布与相关性对照。当前没有这些全量结果，不以试点代替。r674继续LOSS_DISABLED，不追加QM。',
        '', '重建：python -B workflows/data_v1_final/pprime/render_closed_delivery_summary_v1.py。',
        '', MARKER, '', original]
    REPORT.write_text('\n'.join(lines), encoding='utf-8')
    print('PPRIME_CLOSED_AUDIT_SUMMARY_RENDERED_NO_NEW_DATA_READ')

if __name__ == '__main__':
    main()
