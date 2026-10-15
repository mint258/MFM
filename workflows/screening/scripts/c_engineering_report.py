"""Small C3/C4/C5 JSON summary and decision-table appendix; no data/QM work."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
    pending=Path(str(path)+'.pending');pending.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n');pending.replace(path)

def memory_bytes(value):
    if not value or value in {'Unknown','N/A','None'}:return None
    match=re.fullmatch(r'(\d+(?:\.\d+)?)([KMGT]?)',str(value))
    return float(match.group(1))*{'':1,'K':1024,'M':1024**2,'G':1024**3,'T':1024**4}[match.group(2)] if match else None

def collect_sacct(jobs):
    fields=('JobIDRaw','State','ElapsedRaw','AllocCPUS','MaxRSS','MaxRSSNode','MaxRSSTask','TotalCPU','MaxDiskRead','MaxDiskWrite','NodeList')
    command=['sacct','-j',','.join(jobs),'--units=K','--parsable2','--noheader','--format='+','.join(fields)]
    result=subprocess.run(command,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=45)
    values=[]
    if result.returncode==0:
        for line in result.stdout.splitlines():
            tokens=line.split('|')
            if len(tokens)>=len(fields):values.append(dict(zip(fields,tokens)))
    return {'argv':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'fields':fields,'rows':values}

def node_rows(paths,capacity,accounting):
    nodes=capacity.get('nodes',{});reports={};duplicates=[]
    for path in paths:
        data=read(path);node=data['hostname']
        if node in reports:duplicates.append({'node':node,'paths':[reports[node]['path'],str(path)]})
        reports[node]={'path':str(path),'sha256':sha(path),'data':data}
    output=[]
    for index in range(14,20):
        name=f'compute-0-{index}';node=nodes.get(name,{}).get('stdout','')
        fields=dict(re.findall(r'(\w+)=([^\s]+)',node));entry=reports.get(name)
        slots=int(fields.get('CPUTot','0'))//24 if fields.get('CPUTot','').isdigit() else (8 if index==17 else 5 if index==19 else 4)
        memory=int(fields['RealMemory'])*1024**2 if fields.get('RealMemory','').isdigit() else None
        row={'node':name,'k':24,'slots':slots,'node_RealMemory_bytes':memory,'node_85percent_limit_bytes':memory*.85 if memory else None,
            'closed_probe':entry is not None,'report_reference':entry,'sacct_MaxRSS_max_observed_bytes':None}
        if entry:
            data=entry['data'];observed=data['memory'];job=data['job_id']
            job_account=[value for value in accounting.get('rows',[]) if value.get('JobIDRaw','').split('.')[0]==job]
            maxrss=[memory_bytes(value.get('MaxRSS')) for value in job_account]
            maxrss=[value for value in maxrss if value is not None]
            declarations=data.get('declared_memory_MiB')
            declaration=declarations*1024**2 if declarations is not None else None
            rss=observed.get('observed_peak_concurrent_RSS_bytes');pss=observed.get('observed_peak_concurrent_PSS_bytes')
            row.update(job_id=job,actual_seconds=data['actual_seconds'],
                actual_scientific_worker_PID_union=len(data['actual_scientific_worker_pids']),
                peak_concurrent_RSS_bytes=rss,peak_concurrent_PSS_bytes=pss,
                exact_job_cgroup_peak=observed.get('exact_job_cgroup_peak_observations'),
                sacct_rows=job_account,sacct_MaxRSS_max_observed_bytes=max(maxrss) if maxrss else None,
                per_job_declared_bytes=declaration,all_slots_declared_bytes=declaration*slots if declaration is not None else None,
                all_slots_RSS_linear_planning_bytes=rss*slots if rss is not None else None,
                all_slots_PSS_linear_planning_bytes=pss*slots if pss is not None else None,
                declarations_fit_85percent=(declaration*slots<=memory*.85) if declaration is not None and memory is not None else None,
                RSS_planning_fits_85percent=(rss*slots<=memory*.85) if rss is not None and memory is not None else None,
                PSS_planning_fits_85percent=(pss*slots<=memory*.85) if pss is not None and memory is not None else None,
                scratch_before=data['scratch_before'],scratch_after=data['scratch_after'],process_IO=observed.get('sampled_cumulative_own_process_io'),
                issues=data['issues'])
            completed=[]
            for round_ in data['rounds']:
                summary=round_.get('summary')
                if summary:completed.extend(value for value in summary['receipts'] if value['status']=='COMPLETE_WITH_RECORDED_OUTCOMES')
            row['observed_completed_record_executions']=sum(value['records'] for value in completed)
            row['observed_unique_completed_molecules']=len({value['molecule_id'] for value in completed})
            row['observed_closed_archive_bytes']=sum((value.get('archive') or {}).get('bytes',0) for value in completed)
            row['observed_closed_Parquet_bytes']=sum(value['parquet']['bytes'] for value in completed)
            row['completed_records_per_job_second']=row['observed_completed_record_executions']/data['actual_seconds']
        output.append(row)
    return output,duplicates

def markdown(report):
    def gib(value):return '未测/不可用' if value is None else f'{value/1024**3:.3f}'
    def gb(value):return '未测/不可用' if value is None else f'{value/1e9:.3f}'
    xyz=report.get('C5');storage=report.get('C4')
    lines=['| 项目 | 决策关键数字 | 可选方案与配置决策 |','|---|---|---|',
        f"| C3 六节点 k24 | 已闭合 {report['C3_closed_nodes']}/6；29 槽声明合计 {gib(report.get('all_29_slots_declared_bytes'))} GiB；RSS/PSS 见下表 | k、每任务内存、29槽是否可部署；满29槽并发峰值尚未直接测量 |",
        f"| C4 样本序列化 | {'尚未闭合' if storage is None else str(storage['sample_records'])+'条候选Data+P序列化；问题'+str(storage['records_with_issues'])+'条'} | value字段/无损压缩候选、五文件字节边界、写回峰值；最终格式未采纳 |",
        f"| C5 xyz 往返 | {'尚未闭合' if xyz is None else str(xyz['records'])+'条；坐标最大误差 '+str(xyz['xyz_max_error_A'])+' A；顺序通过 '+str(xyz['atom_order_equal_records'])} | 导出格式/原子顺序；analysis_geometry供B5旋转对齐 |",'','C3 细节（RSS/PSS 单位 GiB；所有空值保持不可用，不填零）：','',
        '| 节点 | 槽位 | 实际秒 | RSS峰 | PSS峰 | sacct MaxRSS | 全槽声明 | 85%内存内 |','|---|---:|---:|---:|---:|---:|---:|---|']
    for row in report['C3_nodes']:
        lines.append(f"| {row['node']} | {row['slots']} | {row.get('actual_seconds','等待')} | {gib(row.get('peak_concurrent_RSS_bytes'))} | {gib(row.get('peak_concurrent_PSS_bytes'))} | {gib(row.get('sacct_MaxRSS_max_observed_bytes'))} | {gib(row.get('all_slots_declared_bytes'))} | {row.get('declarations_fit_85percent')} |")
    lines+=['','同一时刻的全部自有worker/QM/parser/序列化进程RSS/PSS由身份双读的sampler统计；job cgroup不能隔离时明确使用同UID自有进程树。PSS校正共享页。sacct原值独立保存；空白MaxRSS或不可用memory.peak不冒充峰值。各节点全槽乘积是规划外推，不能声称观测了29槽同时运行。正式提交仍需核对当时全部用户承诺。','',
        'C3用无POLAR的完整其它B标签及原native序列化/压缩/scratch链路重测；六节点分子桶不重叠，重复round只用于同节点工程测试。跨节点样本不同，未经分层标准化的吞吐不能当作纯硬件性能差。']
    if storage:
        lines+=['','C4 候选 value 存储（十进制 GB）：','',
            '| 保留集 | 基础Data pickle4 | 全P pickle5 | 全P zstd3 | 4KiB页取整模型 |', '|---|---:|---:|---:|---:|']
        for name,value in storage['populations'].items():
            totals=value['total_estimated_bytes']
            lines.append(f"| {name} | {gb(totals['base_Data_pickle4_bytes'])} | {gb(totals['all_registry_candidate_pickle5_bytes'])} | {gb(totals['all_registry_candidate_zstd3_bytes'])} | {gb(totals['per_record_4KiB_rounding_estimate_bytes'])} |")
        lines+=['','原Data非描述符字段保留；D23去Kappa为D20，HBA按当前RDKit修正，指定3D在原PM7坐标计算。P按B6注册表去重复、共享方法单位元信息，逐例QC不删除。pickle和zstd均为候选，未确定lmdb_1格式；数据库页模型不是实测LMDB大小。','',
            '五文件边界及写回峰值完整明细链接：['+Path(report['C4_reference']['path']).name+']('+report['C4_reference']['path']+')。原20/25/30/40及按字节累计的新整数边界均保持同分子构象在同文件。']
    if xyz:
        lines+=['','C5几何使用真实只读源PayloadSHA；独立从实际scratch xyz读取元素与坐标，原键图另存并带摘要，未用SMILES猜原子排列。原native仅坐标回读证据已明确限定，本次补齐显式顺序证据。']
    lines+=['','所有原LMDB只读，本轮不建立lmdb_1；数据问题留在逐条报告并继续扫描。临时xyz和样本blob已删除；C3必要故障输出/闭合证据暂保留，Root可按完成状态和用途统一清理。','',
        '本报告为C3/C4/C5分组附录；全13项总报告第一页由Root合并A/B/C决策表。']
    return '\n'.join(lines)+'\n'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    parser.add_argument('--accounting');parser.add_argument('--collect-sacct',action='store_true')
    parser.add_argument('--capacity',default=str(ROOT/'reports/resource_snapshot.json'))
    parser.add_argument('--output',default=str(ROOT/'reports/c_engineering_summary.json'));args=parser.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text());print(json.dumps({'status':'AST_PASS','data_read':False}));return 0
    paths=sorted((ROOT/'c_engineering/nodes').rglob('node_probe_report.json'))
    jobs=[read(path)['job_id'] for path in paths]
    accounting=read(args.accounting) if args.accounting else collect_sacct(jobs) if args.collect_sacct and jobs else {'rows':[],'MaxRSS':'NOT_COLLECTED'}
    capacity=read(args.capacity) if Path(args.capacity).is_file() else {}
    nodes,duplicates=node_rows(paths,capacity,accounting)
    xyz_path=ROOT/'c_engineering/xyz/xyz_report.json';storage_path=ROOT/'c_engineering/storage/storage_report.json'
    xyz=read(xyz_path) if xyz_path.is_file() else None;storage=read(storage_path) if storage_path.is_file() else None
    closed=sum(row['closed_probe'] for row in nodes);declarations=[row.get('all_slots_declared_bytes') for row in nodes]
    report={'status':'C_ENGINEERING_COMPLETE' if closed==6 and xyz and storage and not duplicates else 'C_ENGINEERING_PARTIAL_OBSERVATION',
        'C3_closed_nodes':closed,'C3_nodes':nodes,'C3_duplicate_node_reports':duplicates,'sacct':accounting,
        'all_29_slots_declared_bytes':sum(declarations) if all(value is not None for value in declarations) else None,
        'full29_concurrent_peak_measured':False,'C4':storage,'C5':xyz,
        'C4_reference':{'path':str(storage_path),'sha256':sha(storage_path)} if storage else None,
        'C5_reference':{'path':str(xyz_path),'sha256':sha(xyz_path)} if xyz else None,
        'script_sha256':sha(__file__),'created_epoch':time.time(),'LMDB_written':False,'QM_started':False}
    output=Path(args.output).absolute()
    if not output.is_relative_to(ROOT/'reports'):raise ValueError('Only own analysis report output permitted')
    save(output,report);output.with_suffix('.md').write_text(markdown(report),encoding='utf-8')
    print(json.dumps({'status':report['status'],'C3_closed_nodes':closed,'C4_ready':storage is not None,'C5_ready':xyz is not None}));return 0

if __name__=='__main__':raise SystemExit(main())
