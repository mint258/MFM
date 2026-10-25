"""Compact a closed EA diagnostic on its CPU host; metadata only, no source reads."""
import argparse,collections,csv,hashlib,io,json,os,pathlib,socket,stat,subprocess
BASE=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
INPUT=BASE/'artifacts/labels/ea_diagnostic_v1/dv1_ea_known_seven_io_v4/diagnostic.json'

def reference(path,raw):return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def read_metadata(path,limit):
    assert not path.is_symlink()
    with path.open('rb') as f:
        before=os.fstat(f.fileno());assert stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size<=limit
        raw=f.read(limit+1);after=os.fstat(f.fileno())
    assert len(raw)==before.st_size and (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
    return raw

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=pathlib.Path,required=True)
    p.add_argument('--report',type=pathlib.Path,required=True)
    p.add_argument('--accounting',type=pathlib.Path,required=True)
    a=p.parse_args();assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-17'
    assert a.output.parent==BASE/'control' and not a.output.exists()
    raw=read_metadata(INPUT,8*1024**2);d=json.loads(raw)
    assert d['status']=='ACTUAL_BOUNDED_DIAGNOSIS_CAUSAL_REVIEW_PENDING'
    assert len(d['cases'])==7 and len(d['formal_context_rows'])==14 and len(set(d['actual_worker_pids']))==16
    assert d['new_masks']==0 and d['new_QM_calls']==0 and d['source_values_or_status_changed'] is False
    workers=d['worker_receipts'];assert len(workers)==16
    io=[w['parquet_io_lifecycle'] for w in workers]
    assert all(r['opens']==r['closes'] and r['current_open_handles']==0 and r['max_simultaneously_open_handles']==1 for r in io)
    intentpath=pathlib.Path(d['root_preflight']['path'])
    assert reference(intentpath,read_metadata(intentpath,2*1024**2))==d['root_preflight']
    monitorpath=BASE/'artifacts/cpu_analysis_guards/dv1_ea_known_seven_io_v4/closure.json'
    monitorraw=read_metadata(monitorpath,2*1024**2);monitor=json.loads(monitorraw)
    assert monitor['job_id']=='4520570' and monitor['status']=='COMPLETED_NO_MEMORY_DENIAL'
    assert monitor['intent_reference']==d['root_preflight'] and monitor['first_denial'] is None and monitor['durable_evidence_exported']
    assert a.accounting.parent==BASE/'control'
    accountingraw=read_metadata(a.accounting,2*1024**2);accounting=json.loads(accountingraw)
    assert accounting['query_returncode']==0 and accounting['command_argv'][0]=='sacct'
    argv=accounting['command_argv'];rawref=accounting['raw_sacct_reference']
    querybytes=read_metadata(pathlib.Path(rawref['path']),2*1024**2)
    assert reference(pathlib.Path(rawref['path']),querybytes)==rawref
    query_raw=querybytes.decode();parents=[r for r in accounting['actual_parents'] if r['JobIDRaw']=='4520570']
    assert len(parents)==1 and parents[0]['State']=='COMPLETED' and parents[0]['ExitCode']=='0:0'
    flags=[{k:r.get(k) for k in ('record_id','calc_type','status','source_status','converged','scf_iterations','failure_code')} for r in d['formal_context_rows']]
    summary={'schema':'EA_CLOSED_CPU_DIAGNOSTIC_COMPACT_METADATA_V1','status':d['status'],
        'job_id':'4520570','diagnostic_reference':reference(INPUT,raw),'monitor_reference':reference(monitorpath,monitorraw),
        'cases':len(d['cases']),'contexts':len(d['formal_context_rows']),'actual_workers':len(workers),
        'max_worker_rss_bytes':max(w['maxrss_bytes'] for w in workers),'elapsed_worker_phase_seconds':d['elapsed_seconds'],
        'parquet_handles_opened':sum(r['opens'] for r in io),'parquet_handles_closed':sum(r['closes'] for r in io),
        'parquet_reuses':sum(r['reuses'] for r in io),'max_simultaneous_handles_per_worker':1,'all_handles_closed':True,
        'raw_evidence_counts':dict(collections.Counter(r['evidence_status'] for r in d['raw_context'])),
        'raw_outputs_found':sum(bool(r['canonical_output_found']) for r in d['raw_context']),
        'comparisons':d['comparisons'],'convergence_observations':flags,'sacct_argv':argv,'sacct_stdout':query_raw,'actual_parent':parents[0],'accounting_reference':reference(a.accounting,accountingraw),'cause':d['cause'],'new_QM_calls':0,'new_masks':0,
        'guide_approximately_390_population_reestablished':d['guide_approximately_390_SUCCESS_NULL_population_count_reestablished'],
        'source_reference':reference(pathlib.Path(__file__),pathlib.Path(__file__).read_bytes()),
        'metadata_only':True,'original_parquet_or_archives_read':False}
    payload=json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False).encode()+b'\n';assert len(payload)<32768
    with a.output.open('xb') as f:f.write(payload)
    assert a.report.parent==BASE/'repository/docs/data_v1' and not a.report.exists()
    core_seconds=int(parents[0]['ElapsedRaw'])*int(parents[0]['AllocCPUS'])
    lines=['# 七例电子亲和能的原生上下文诊断','',
        '目的：复核既有极端EA的同记录SP/VIPEA上下文，不重算QM，不改标签或mask。', '',
        '输入及完整哈希：', '', '```json',json.dumps({'diagnostic':summary['diagnostic_reference'],
        'config':d['config'],'monitor':summary['monitor_reference'],'summary':reference(a.output,payload)},ensure_ascii=False,indent=2),'```','',
        '规则：严格原canonical owner/record/task/lane；7例、14上下文、6原源文件、16实际worker。读取列、筛选逻辑和xTB参数保持；SP GFN2与VIPEA GFN1不是同一方法，不能将跨方法能量或gap符号直接当成失败证据。','',
        '实际父任务4520570：'+parents[0]['State']+'/'+parents[0]['ExitCode']+'，'+parents[0]['ElapsedRaw']+'秒×'+parents[0]['AllocCPUS']+'CPU='+str(core_seconds/3600)+'分配核时。中央monitor无内存denial且证据完整导出。','',
        '句柄打开/关闭='+str(summary['parquet_handles_opened'])+'/'+str(summary['parquet_handles_closed'])+'；复用='+str(summary['parquet_reuses'])+'；每worker同时最多1个handle，最终全部关闭。worker最高RUsage RSS='+str(summary['max_worker_rss_bytes'])+'B，低于本次1280MiB内部上限。原失败与真实超限证据保留，未进一步提高预算。','',
        '| record_id | EA/eV | IP/eV | SP gap/eV | SP原子电荷和/e |','|---|---:|---:|---:|---:|']
    for row in d['comparisons']:
        lines.append('| '+' | '.join(str(row[k]) for k in ('record_id','EA_eV','IP_eV','SP_gap_eV','SP_atomic_charge_sum_e'))+' |')
    lines += ['', '原生状态/收敛元数据逐条保留：','','```json',json.dumps(flags,ensure_ascii=False,indent=2),'```','',
        '原始输出证据分类：'+json.dumps(summary['raw_evidence_counts'],ensure_ascii=False)+'。实际找到'+str(summary['raw_outputs_found'])+'份canonical原始输出；未保留或不存在不能推出SCF失败。','',
        '异常与限制：最大EA8791.0184eV的异常值保持原样，根因仍UNKNOWN。当前注册的VIPEA wire没有足够的中性/阳离子/阴离子能量和电荷阶段证据；不从绝对能量大小或跨方法差值推断零能量、错误电荷态或不收敛。约390条SUCCESS+NULL的全人口计数未重建，本结果不是全人群扫描或最终mask规则。没有新QM调用或新增mask。','',
        '复算脚本：workflows/data_v1_final/labels/ea_cpu_v2/summarize_closed_v2.py；只读取已闭合结果元数据及会计信息，不读取原parquet/SQLite，不启动科学任务。']
    with a.report.open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
    print(json.dumps({'status':'CLOSED_METADATA_COMPACTED','reference':reference(a.output,payload),
        'cases':7,'contexts':14,'workers':16,'max_worker_rss_bytes':summary['max_worker_rss_bytes'],
        'raw_outputs_found':summary['raw_outputs_found'],'diagnostic_reference':summary['diagnostic_reference']}))
if __name__=='__main__':main()