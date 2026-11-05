"""Report real closed-parent metadata without opening numeric/native DATA bodies."""
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q

def main():
    Q.on_login()
    root=Q.ROOT
    path=root/'artifacts/labels/source_status_v1/physical_closure_day_v1/day02_r2/manifest.json'
    ref=Q.pin(path);m=Q.load(path)
    ap=root/'control/accounting/pprime_physical_day02_r2_4524581_actual_terminal_v1.json'
    a=Q.load(ap)
    assert a['query_returncode']==0 and a['parents']==[{'job_id':'4524581','state':'COMPLETED','exit_code':'0:0','alloc_cpus':16,'elapsed_raw_seconds':121,'node':'compute-0-18'}]
    assert Q.pin(a['raw_sacct_reference']['path'])==a['raw_sacct_reference']
    assert '4524581|COMPLETED|0:0|121|16|compute-0-18|1278' in Q.read_small(a['raw_sacct_reference']['path']).decode()
    assert m['status']=='COMPLETE_RETAINED_PHYSICAL_EVIDENCE_REQUIRES_ROOT_D1_REVIEW' and not m['errors']
    assert m['job_id']=='4524581' and m['new_QM_UFF_calls']==m['native_initialize_or_invoke_calls']==m['once_writes']==0
    for pr in m['pure_boundary_references']:
        assert Q.pin(pr['path'])==pr
        p=Q.load(pr['path'])
        assert p['tests_run']==3 and p['failures']==p['errors']==p['skips']==p['expected_failures']==p['unexpected_successes']==0
    proof=Q.load(m['startup_proof_reference']['path'])
    assert Q.pin(m['startup_proof_reference']['path'])==m['startup_proof_reference']
    assert proof['job_id']=='4524581' and proof['request']['cpus']==16 and proof['request']['node']=='compute-0-18'
    d=m['sections']['defined'];t=m['sections']['retained_tensors_and_gradient'];n=m['sections']['native384'];old=m['sections']['old72']
    assert d['own_rows']==d['pair_rows']==1200 and d['vector_checks']==500 and d['empty_vector_pair_rows']==900
    assert t['SP_calls_reread']==t['gradient_calls_reread']==t['tensor_comparisons']==100
    assert t['counts']=={'PASS':100} and t['gradient_force_relation_counts']=={'PASS':100} and t['input_orbit_failures']==0
    assert n['completed_keys']==384 and len(n['per_condition'])==12 and all(v['records']==32 for v in n['per_condition'])
    assert old['origin_counts']=={'PASS':8} and old['tensor_counts']=={'PASS':24} and old['companion_original_gate_counts']=={'PASS':16}
    for p in ('io.py','reduce.py','tensor.py','native.py','run.py','metadata.py','README.md','__init__.py'):
        now=Q.REPO/'workflows/data_v1_final/pprime/physical_closure_day_v1'/p
        before=root/'control/source_snapshots/physical_closure_day_failed4524577_r1_v1'/p
        assert Q.pin(now)['sha256']==Q.pin(before)['sha256']
    record={'schema':'ROOT_ACTUAL_PPRIME_PHYSICAL_DAY_R2_TECHNICAL_REVIEW_V1',
        'status':'APPROVED_TECHNICAL_RETAINED_OUTPUT_CLOSURE_ONLY','reviewer':'root','observed_at':Q.now(),
        'manifest_reference':ref,'accounting_reference':Q.pin(ap),'raw_accounting_reference':a['raw_sacct_reference'],
        'startup_proof_reference':m['startup_proof_reference'],'pure_boundary_references':m['pure_boundary_references'],
        'old_failed_technical_parent_accounting_reference':Q.pin(root/'control/accounting/pprime_physical_day01_4524577_actual_FAILED_v1.json'),
        'actual_C0_allocated_core_seconds':1936,'old_failed_allocated_core_seconds':544,
        'defined_vectors':500,'retained_tensor_checks_PASS':100,'retained_gradient_force_relations_PASS':100,
        'original_SCF_states':d['SCF_original_converged_counts'],'old72_original_contradictions_preserved':old['old_contradictions'],
        'old72_original_control_counts':{k:old[k] for k in ('origin_counts','tensor_counts','companion_original_gate_counts')},
        'native384_per_condition':n['per_condition'],'official_exact_Source_files':m['sections']['official_source']['exact_primary_source_files'],
        'numeric_or_raw_DATA_bodies_opened_by_this_metadata_review':False,
        'official_program_unit_sign_origin_and_frame_final_Root_review':'PENDING_DETAILED_SOURCE_AND_NATIVE_CONTEXT_REVIEW',
        'missing_native_coordinate_blocks_not_backfilled':True,
        'technical_C0_is_not_all_population_quality_acceptance':True,
        'new_QM_UFF_init_once':0,'formal_2000_or_full_release':False,'new_precision_execution_permission':False,'D1_jointly_frozen':False}
    rr=Q.write_new(root/'control/root_actual_pprime_physical_day_r2_technical_review_v1.json',record)
    lines=['# P′ 留存输出物理核验：2026-10-28 实际结果','',
        '目的：在不新增量子化学调用的前提下，复核已留存的限定诊断和原生输出。', '',
        f'输入：实际 manifest `{ref["path"]}`，{ref["bytes"]}B，SHA256 `{ref["sha256"]}`；独立技术审阅 `{rr["path"]}`，SHA256 `{rr["sha256"]}`。原输入及所有原生输出沿该闭合清单溯源。','',
        '规则：复用原读回函数、旋转/张量函数和容差；修复的只是严格输入清单漏登记任务文件及原 once 记录的问题。原读取闸门、数学、标签和质量阈值没有更改。','',
        '| 项目 | 实际结果 |','| --- | --- |',
        '| Slurm | 4524581，COMPLETED/0:0，16CPU，121秒，1936分配核秒 |',
        '| 作业内预检 | producer3＋resource3，全部通过 |',
        '| 已定义向量比较 | 500项通过；其余900行属于原字段未定义，不计科学通过 |',
        '| 留存SP张量旋转 | 100/100通过原容差 |',
        '| 留存扰动梯度与力关系 | 100/100通过；未做能量有限差分验证 |',
        '| 原72控制 | 原点8、张量24、同几何伴随16通过；原15项矛盾及FAILED父任务仍保留 |',
        '| 原生证据 | 384项，12条件各32；MOPAC及梯度坐标可核，其他xTB缺独立坐标块仍UNKNOWN |',
        '| 新QM / UFF / native初始化 / once写入 | 0 |','',
        '异常：首次只读核验4524577因输入定位清单遗漏而FAILED，34秒/544分配核秒，源码、输出和成本全部保留。修复后以新输入清单和独立输出重新核验，不重算化学标签。原SCF状态保持TRUE=1000、NULL_UNKNOWN=200，未知不改为失败或成功。','',
        '限制：这些结果支持有限留存窗口的技术闭合；官方程序的单位、符号、原点、实际输出轴和原生身份仍要综合审阅。没有据此签署D1、授权新的精度设置，或放行2000构象试点/全量。当前后台S′与标签扫描继续。','']
    report=Q.REPO/'docs/data_v1/pprime_physical_closure_actual_20261028_v1.md'
    report.write_text('\n'.join(lines),encoding='utf-8')
    print({'technical_review':rr,'report':str(report),'numeric_DATA_body_reads':0})

if __name__=='__main__':main()
