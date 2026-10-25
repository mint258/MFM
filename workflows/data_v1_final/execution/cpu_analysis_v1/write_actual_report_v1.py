"""Generate a reproducible point-in-time CPU report from owned small metadata."""
import argparse,collections,csv,datetime,io,json,pathlib,re,subprocess
from workflows.data_v1_final.execution.cpu_analysis_v1 import policy

def write(path,obj):
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True)
    a=p.parse_args();policy.require(re.fullmatch(r'[a-z0-9_]+',a.tag),'SAFE_NEW_TAG_REQUIRED')
    root=policy.ROOT;repo=policy.REPO;control=root/'control'
    report=repo/'docs/data_v1'/('cpu_actual_'+a.tag+'.md')
    account=control/('owned_accounting_'+a.tag+'.json')
    rawpath=control/('owned_sacct_'+a.tag+'.txt')
    for path in (report,account,rawpath):policy.require(not path.exists(),'EXCLUSIVE_NEW_REPORT_REQUIRED')
    receipts={}
    for path in sorted((control/'submissions').glob('*.json')):
        obj=policy.load(path)
        if not (obj.get('job_id') and obj.get('request') and obj.get('sbatch_returncode')==0):continue
        jid=str(obj['job_id']);policy.require(jid.isdecimal() and jid not in receipts,'UNIQUE_OWNED_SUBMISSION_REQUIRED')
        receipts[jid]={'receipt_reference':policy.ref(path),'job_name':path.stem}
    policy.require(receipts,'ACTUAL_OWNED_SUBMISSIONS_REQUIRED')
    prior=policy.load(control/'owned_accounting_v7.json')
    policy.require({r['JobIDRaw'] for r in prior['actual_parents']}<=set(receipts),'PREVIOUS_OWNED_PARENTS_MUST_ALL_BE_RETAINED')
    argv=['sacct','-j',','.join(sorted(receipts,key=int)),
        '--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,Partition','-P']
    query=subprocess.run(argv,capture_output=True,text=True,check=True)
    with rawpath.open('x',encoding='utf-8') as f:f.write(query.stdout)
    rows=[];steps=[]
    for row in csv.DictReader(io.StringIO(query.stdout),delimiter='|'):
        jid=row['JobIDRaw']
        if not jid.isdecimal():steps.append(row);continue
        policy.require(jid in receipts,'UNEXPECTED_ACCOUNTING_PARENT')
        row.update(receipts[jid]);row['allocated_core_seconds_observed']=int(row['ElapsedRaw'])*int(row['AllocCPUS'])
        rows.append(row)
    policy.require({r['JobIDRaw'] for r in rows}==set(receipts) and len(rows)==len(receipts),'COMPLETE_UNIQUE_ACTUAL_PARENT_SET_REQUIRED')
    observed=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    total=sum(r['allocated_core_seconds_observed'] for r in rows)
    terminal={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL'}
    active=[r['JobIDRaw'] for r in rows if r['State'].split()[0] not in terminal]
    evidence={'schema':'DATA_V1_OWNED_ACCOUNTING_POINT_IN_TIME_V2','observed_at':observed,
        'command_argv':argv,'query_returncode':query.returncode,'raw_sacct_reference':policy.ref(rawpath),
        'actual_parents':rows,'steps_preserved_not_added_to_parent_cost':steps,'active_parent_job_ids':active,
        'allocated_core_seconds_observed':total,'allocated_core_hours_observed':total/3600,
        'cost_basis':'ElapsedRaw integer seconds times allocated CPUs, all FAILED/TIMEOUT included; not CPU utilization.',
        'zero_elapsed_interpretation':'Scheduler integer-second floor; not proof of zero wall time or zero actual resource consumption.'}
    write(account,evidence)
    partialpath=root/'artifacts/conformers/partial_pilot_audit_v1/audit_v1/audit_report.json'
    partial=policy.load(partialpath)
    cohortpath=partialpath.parent/'cohort_report.json';cohorts=policy.load(cohortpath)
    statuses=collections.Counter()
    for row in cohorts:statuses.update(row['status_counts'])
    sizepath=root/'artifacts/labels/size_rho_v1/dv1_size_rho_cpu_v2/manifest.json'
    sizem=policy.load(sizepath)
    inputs=[policy.ref(partialpath),policy.ref(cohortpath),policy.ref(sizepath),policy.ref(pathlib.Path(__file__).absolute()),
        policy.ref(repo/'configs/data_v1/run_decisions_v4.json'),policy.ref(repo/'configs/data_v1/cpu_analysis_small_scopes_v1.json')]
    identitypath=root/'artifacts/expansion/identity/identity_source_pins_cpu_v2/receipt.json'
    identity=policy.load(identitypath) if identitypath.exists() else None
    if identity is not None:inputs.append(policy.ref(identitypath))
    lines=['# CPU 数据线实际进度与成本', '', '观测时间：'+observed+'。本报告仅从小型来源/回执元数据生成；科学数据正文没有在登录节点读取。', '',
        '目的：核对有限 CPU 分析试点、保存失败和超时成本，避免将进程成功当成 v1 最终验收。', '',
        '输入及其完整 path/bytes/SHA：`'+str(account)+'`；以下元数据引用由同一脚本核验。', '', '```json',json.dumps(inputs,ensure_ascii=False,indent=2),'```','',
        '规则：实际 cpu 分区、16 CPU；有限分析使用已登记的实测内存政策和本地 monotonic 监控。正式 S′/UFF/QM 仍要求14–19、64GiB、全部用户声明内存85%，Se唯一科学例外及 ROUTINE VAL 保持。', '',
        '原 S′ 336 试点4520364为 TIMEOUT，不能用 Exit0:0 代替完成。只读审计为独立任务，不是恢复生成：', '',
        '- 完整可复用包：'+str(partial['complete_reusable_molecules'])+'；这些包的科学状态分别为 '+json.dumps(dict(statuses),ensure_ascii=False)+'。包完整不代表补齐成功。',
        '- 完整包字节：'+str(partial['complete_package_bytes'])+'；闭合包已保存 worker 秒：'+str(partial['complete_package_science_worker_seconds'])+'，不包括缺包分子的未保存工作。',
        '- 缺包名单见同目录 missing_tasks.json；原包不修改，恢复需独立方案、资源批准和真实联合验收。', '',
        '尺寸相关性结果：'+str(sizem['status'])+'。129物理目标/146统计分量，16个实际worker每遍；当前原始source TRAIN小试点，不能作为最终共同人群注册表或D4。', '',
        '去污染来源：'+(str(identity['status']) if identity is not None else '仍待实际回执')+'。来源当前pin成功不代表已导出全部identity、去污染已通过或候选池已放行。', '',
        '异常：原MAD0共享文件系统心跳失败；原小审计缺partition、第二轮reducer跨主机时间差、EA单进程RSS、vector历史相对路径、候选评估旧quota均保留实际失败与日志。新提交时间取目标节点内存probe时钟，登录时间独立保存，不放宽运行时新鲜度或内存门槛。', '',
        '限制：共同人群、构象顺序、最终掩码/归一化、P′真实QM、D3/D5/D6及扩充第一批均未最终验收。契约仍draft.3，不能据源代码或小试点伪造最终交付。', '',
        '本run实际父任务 '+str(len(rows))+' 个；当前活动 '+json.dumps(active)+'；已观测分配核时 '+str(total/3600)+'。包括所有失败/超时，步骤不重复计费；ElapsedRaw=0是整秒下取值，不能宣称真实零成本。', '',
        '| 父任务 | 名称 | 状态 | Exit | 秒 | CPU | 已观测分配核秒 |',
        '|---|---|---|---|---:|---:|---:|']
    for row in sorted(rows,key=lambda r:int(r['JobIDRaw'])):
        lines.append('| '+' | '.join(str(row[k]) for k in ('JobIDRaw','job_name','State','ExitCode','ElapsedRaw','AllocCPUS','allocated_core_seconds_observed'))+' |')
    with report.open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
    print(json.dumps({'status':'POINT_IN_TIME_REPORT_WRITTEN_NOT_FINAL','report':policy.ref(report),
        'accounting':policy.ref(account),'owned_parents':len(rows),'active':active,'allocated_core_hours_observed':total/3600}))
if __name__=='__main__':main()