"""Report current actual registered queue and live observer from small metadata."""
import argparse,datetime,json,os,pathlib,re,time
from .shared import ROOT,REPO,load,need,on_login,pin,query,read_small,write_new,now

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--registry',type=pathlib.Path,required=True)
    p.add_argument('--observer-output',type=pathlib.Path,required=True);p.add_argument('--accounting',type=pathlib.Path,required=True)
    p.add_argument('--tag',required=True);a=p.parse_args();on_login();need(re.fullmatch(r'[a-z0-9_]+',a.tag),'SAFE_TAG')
    report=REPO/'docs/data_v1'/('queued_actual_'+a.tag+'.md');proofpath=ROOT/'control'/('queued_actual_'+a.tag+'.json')
    need(not report.exists() and not proofpath.exists(),'EXCLUSIVE_REPORT_OUTPUTS')
    registry=load(a.registry);identity=load(a.observer_output/'identity.json');account=load(a.accounting)
    proc=pathlib.Path('/proc')/str(identity['pid']);st=(proc/'stat').read_text();ticks=int(st[st.rfind(')')+2:].split()[19])
    need(proc.stat().st_uid==identity['uid']==1278 and ticks==identity['start_ticks']
        and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==identity['boot_id'],'ACTUAL_LIVE_OBSERVER_IDENTITY')
    need(pin(identity['source_reference']['path'])==identity['source_reference'],'OBSERVER_SOURCE_CHANGED')
    pointer=load(a.observer_output/'latest.json');need(pin(pointer['snapshot']['path'])==pointer['snapshot'],'HEARTBEAT_REFERENCE')
    snapshot=load(pointer['snapshot']['path']);age=time.time()-datetime.datetime.fromisoformat(snapshot['observed_at']).timestamp()
    need(0<=age<=120,'FRESH_LIVE_OBSERVER_HEARTBEAT_REQUIRED')
    rows=[];parents={r['JobIDRaw']:r for r in account['actual_parents']}
    rp=ROOT/'control/requests/dv1_q_sprime_recovery_20261026_v1.plan.json';recovery=load(rp)
    combined=(recovery['original_pilot_actual_core_seconds']+recovery['additional_allocated_core_seconds_cap'])/3600
    original_limit=recovery['original1p5_estimate_gate_core_seconds']/3600
    need(combined<original_limit,'ORIGINAL_COST_GATE_RETAINED')
    inputs=[pin(a.registry),pin(a.observer_output/'identity.json'),pointer['snapshot'],pin(a.accounting),pin(pathlib.Path(__file__).absolute()),pin(rp)]
    for row in registry['jobs']:
        for key in ('request_reference','receipt_reference'):
            need(pin(row[key]['path'])==row[key],'REGISTERED_REFERENCE_CHANGED');inputs.append(row[key])
        req=load(row['request_reference']['path']);sub=load(row['receipt_reference']['path']);jid=row['job_id']
        need(sub['job_id']==jid and sub['request']==req and sub['sbatch_returncode']==0,'ACTUAL_SUBMISSION_BINDING')
        raw=query(['scontrol','show','job',jid,'--oneliner']);need(jid in parents,'ACTUAL_PARENT_ACCOUNTING')
        from .queue_contract import parse_scontrol_jobs
        job=parse_scontrol_jobs(raw)[0]
        need(job['UserId']=='zixiao(1278)' and job['JobName']==req['job_name'] and job['OverSubscribe']=='USER'
            and job['Requeue']=='0' and int(job['NumCPUs'])==16 and job['MinMemoryNode']=='64G','ACTUAL_QUEUED_RESOURCE_BINDING')
        rows.append({'job_id':jid,'name':req['job_name'],'kind':req['kind'],'state':job['JobState'],'reason':job['Reason'],
            'node':req['node'],'cpus':16,'memory_gib':64,'dependencies':req['dependencies'],'actual_job_metadata':raw,
            'request_reference':row['request_reference'],'receipt_reference':row['receipt_reference'],'actual_parent':parents[jid]})
    lines=['# 实际排队与持续观察','',
        '目的：按用户持续提交指令，将已具备输入与审查的步骤交给Slurm等待资源。以下为当前真实作业，不代表计算或整轮验收完成。','',
        '|任务ID|步骤|当前状态|原因|CPU|GiB|','|---|---|---|---|---:|---:|']
    labels={'dv1_q_checks_20261026_v1':'22项新边界检查','dv1_q_sprime_recovery_20261026_v1':'2缺包恢复+14复现控制',
        'dv1_q_pprime_frame_20261026_v1':'72次真实帧控制计算与验收','dv1_q_pprime_retention_20261026_v1':'2000UFF输入的retention准备，无QM'}
    lines += [f"|{r['job_id']}|{labels.get(r['name'],r['name'])}|{r['state']}|{r['reason']}|16|64|" for r in rows]
    lines += ['', '所有任务经实际readback核实exclusive=user、16CPU/64GiB、禁自动重排。观察进程启动后已release到资源队列；后继任务依赖检查任务实际C0。计算启动前还必须取得120秒内、目标节点时钟的Root执行证明，重算全用户声明85%、真实内存、quota200GB和前置任务结果。零/缺失内存声明不作豁免。','',
        '用户级隔离等待规则见[Slurm官方文档](https://slurm.schedmd.com/sbatch.html#OPT_exclusive)。它阻止与其他用户同节点；初始held后readback确认再release，未修改其他作业。','',
        f"S′保留334旧包和原TIMEOUT，新物理重放只含2缺包与14控制。{recovery['wall_seconds']}秒×16CPU的追加分配上限加原成本为{combined:.6f}核时，低于原{original_limit:g}核时门槛；这是上限，不是完成耗时预测。",'',
        '72帧控制只验证规定的软件/字段与变换范围，不冒充2000构象12任务试点。2000QM仍须等待实际frame PASS和retention manifest真实闭合后冻结提交。','',
        f"已验证观察进程PID {identity['pid']} 的UID、boot/start_ticks和源文件；当前心跳年龄{age:.3f}秒。它每20秒观察已注册作业，有效期24小时，期满须对同一真实作业重新核对并续接观察，不能重提作业。",'',
        f"本run实际父任务{len(account['actual_parents'])}个，已观测分配核时{account['allocated_core_hours_observed']}，含所有失败/超时；完整sacct在{a.accounting}。",'',
        'D1–D7最终交付、正式全量S′/P′及扩充第一批仍未完成。目标保持active；不能用本排队记录或源码测试替代真实结果。','',
        '输入与完整path/bytes/SHA、实际scontrol和父会计见 '+str(proofpath)+'。报告时间：'+now()+'。','']
    with report.open('x',encoding='utf-8') as f:f.write('\n'.join(lines))
    obj={'schema':'ACTUAL_REGISTERED_CPU_QUEUE_REPORT_V1','observed_at':now(),'task_complete':False,'rows':rows,
        'observer_identity':identity,'observer_live_verified':True,'heartbeat_reference':pointer['snapshot'],
        'observer_heartbeat_age_seconds':age,'input_references':inputs,'report':pin(report),
        'owned_parent_count':len(account['actual_parents']),'allocated_core_hours_observed':account['allocated_core_hours_observed']}
    write_new(proofpath,obj);print(json.dumps({'report':pin(report),'proof':pin(proofpath),'job_ids':[r['job_id'] for r in rows],'observer_live':True,'task_complete':False}))
if __name__=='__main__':main()
