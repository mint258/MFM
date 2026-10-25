"""Report all registered phases and verified live observers from small metadata."""
import argparse,datetime,time,pathlib,re
from ..queue_v1.shared import ROOT,REPO,PY,load,pin,read_small,write_new,need,on_login,now,query,fields,uid,memory_mib
from ..queue_v1.queue_contract import validate_request
from ..queue_v3.contract import validate_bound_request,validate_observer_identity,validate_disjoint
from ..queue_v3.registry import process_identity,load_request

PAIRS=[('control/queued_phase_20261026_v1.json','control/queue_observer_20261026_v1'),('control/queue_v3_registries/source_status_prepare_20261026_v1.json','control/queue_v3_observers/source_status_prepare_20261026_v1'),('control/queue_v3_registries/sb5_sources_20261026_v1.json','control/queue_v3_observers/sb5_sources_20261026_v1')]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--accounting',required=True,type=pathlib.Path);p.add_argument('--tag',required=True);a=p.parse_args();on_login()
    need(re.fullmatch(r'[a-z0-9_]+',a.tag),'SAFE_NEW_REPORT_TAG')
    report=REPO/'docs/data_v1'/('registered_phases_actual_'+a.tag+'.md');proof=ROOT/'control'/('registered_phases_actual_'+a.tag+'.json')
    need(not report.exists() and not proof.exists(),'NEW_REPORT_AND_PROOF_ONLY')
    account=load(a.accounting);need(account['schema']=='DATA_V1_OWNED_ACCOUNTING_POINT_IN_TIME_V2' and account['query_returncode']==0,'ACTUAL_ACCOUNTING_REQUIRED')
    need(pin(account['raw_sacct_reference']['path'])==account['raw_sacct_reference'],'EXACT_ACCOUNTING_RAW')
    age=time.time()-datetime.datetime.fromisoformat(account['observed_at']).timestamp();need(0<=age<=600,'RECENT_ACTUAL_ACCOUNTING_REQUIRED')
    parents={r['JobIDRaw']:r for r in account['actual_parents']};registries=[];observers=[];rows=[];inputs=[pin(a.accounting),account['raw_sacct_reference'],pin(pathlib.Path(__file__).absolute())]
    for rp,op in PAIRS:
        rp=ROOT/rp;op=ROOT/op;registry=load(rp);registries.append((str(rp),registry));saved=load(op/'identity.json');cur=process_identity(saved['pid'])
        need(all(saved[k]==cur[k] for k in ('pid','uid','boot_id','start_ticks')),'SAME_LIVE_OWN_OBSERVER')
        source=saved['source_reference'];need(pin(source['path'])==source,'OBSERVER_SOURCE_EXACT')
        module=pathlib.Path(source['path']).relative_to(REPO).with_suffix('').as_posix().replace('/','.')
        expected=[PY,'-B','-m',module,'--registry',str(rp),'--output',str(op),'--max-seconds','86400','--poll-seconds','20']
        need(cur['argv']==expected and cur['pgid']==cur['sid']==cur['pid'],'FULL_OWN_OBSERVER_ARGV_AND_SESSION')
        if 'argv' in saved:validate_observer_identity(saved,cur,expected_argv=expected,registry_reference=pin(rp),source_reference=source)
        pointer=load(op/'latest.json');need(pin(pointer['snapshot']['path'])==pointer['snapshot'],'EXACT_OBSERVER_HEARTBEAT')
        snapshot=load(pointer['snapshot']['path']);hb_age=time.time()-datetime.datetime.fromisoformat(snapshot['observed_at']).timestamp();need(0<=hb_age<=120,'FRESH_OBSERVER_HEARTBEAT')
        need(snapshot['identity_reference']==pin(op/'identity.json'),'HEARTBEAT_OBSERVER_BINDING')
        observers.append({'registry':pin(rp),'identity':pin(op/'identity.json'),'current_proc':cur,'heartbeat':pointer['snapshot'],'heartbeat_age_seconds':hb_age,'observed_states':snapshot['states']})
        inputs.extend([pin(rp),pin(op/'identity.json'),pointer['snapshot']])
        for row in registry['jobs']:
            req=load_request(row['request_reference']);need(pin(row['receipt_reference']['path'])==row['receipt_reference'],'EXACT_RECEIPT')
            sub=load(row['receipt_reference']['path']);jid=row['job_id'];need(sub['request']==req and sub['job_id']==jid and sub['sbatch_returncode']==0 and jid in parents,'ACTUAL_OWN_PARENT_BINDING')
            validate_request(req,read_small=read_small,script_text=read_small(req['script_reference']['path']).decode())
            if registry['schema']=='REGISTERED_QUEUED_CPU_JOBS_V3':validate_bound_request(req,read_small=read_small)
            raw=query(['scontrol','show','job',jid,'--oneliner']);job=fields(raw)
            need(uid(job)==1278 and job['JobName']==req['job_name'] and job['Partition']=='cpu' and job['ReqNodeList']==req['node'] and job['NumCPUs']=='16' and memory_mib(job['MinMemoryNode'])==65536 and job['OverSubscribe']=='USER' and job['Requeue']=='0' and job['Command']==req['script_reference']['path'],'EXACT_ACTUAL_REGISTERED_RESOURCES')
            rows.append({'job_id':jid,'name':req['job_name'],'kind':req['kind'],'node':req['node'],'state':job['JobState'],'reason':job['Reason'],'cpus':16,'memory_gib':64,'pilot':req['pilot'],'scope_key':req.get('scope_key'),'scope_parameters':req.get('scope_parameters'),'wall_seconds':req['wall_seconds'],'whole_output_cap_bytes':req['estimated_peak_output_bytes'],'dependencies':req['dependencies'],'request':row['request_reference'],'receipt':row['receipt_reference'],'actual_scontrol':raw,'accounting_parent':parents[jid]})
            inputs.extend([row['request_reference'],row['receipt_reference']])
    validate_disjoint(registries,load_request=load_request)
    labels={'dv1_q_checks_20261026_v1':'原22边界检查','dv1_q_sprime_recovery_20261026_v1':'2缺包恢复+14独立控制','dv1_q_pprime_frame_20261026_v1':'72真实QM帧控制','dv1_q_pprime_retention_20261026_v1':'2000UFF retention准备','dv1_q_v3_checks_20261026_v1':'14队列+8来源审计边界','dv1_q_source_status_prepare_20261026_v1':'全人口磁盘索引准备','dv1_q_sb5_identity_profile_20261026_v1':'原物理成员身份导出试点','dv1_q_sb5_raw_inventory_20261026_v1':'PubChem全原字节盘点'}
    lines=['# 已登记阶段与实际持续观察','', '目的：核实实际Slurm提交、资源、依赖、监控身份和全部已观测成本。以下是排队/运行状态，不代表科学交付完成。','', '|ID|步骤|节点|状态|原因|CPU/GiB|','|---|---|---|---|---|---|']
    lines += [f"|{r['job_id']}|{labels.get(r['name'],r['name'])}|{r['node']}|{r['state']}|{r['reason']}|16/64|" for r in rows]
    lines += ['',f"实际登记{len(rows)}项，{len(observers)}个独立监控均核对UID、boot/start_ticks、完整argv、PGID/SID、cgroup、源码及新鲜心跳。所有registry的job/request/proof/name不重合。旧监控及其他用户/模型作业未改动。",'', '新2项来源阶段依赖4521022实际C0，并各自在读真实正文前执行4项新增边界。身份试点只投影65536 formal记录、全部4900 embargo及本地全来源小集合；SOURCE_*是原逐记录成员标记，未应用新的整分子TRAIN/VAL/FULL或最终common。训练VAL仍为7610分子/72525记录。外部全来源去污染仍待实际证据。','', '原始文件盘点完整重验原gzip SHA/EOF/CRC并保留原字节TSV和有界JSONL索引，测真实N，不化学筛选或释放池。正文8880849781B已由原producer观测；元数据保守界及256MiB余量构成9247376245B逻辑预算，实际allocation/目录开销仍须监控，整体10GiB。','', '来源标签准备是诚实nonpilot：全11231854记录磁盘索引，stage24GiB、wholephase60GiB。实际prepare闭合后只可审首片，实测CPU/RSS/输出再决定余15片；560分配核时是全部预设分配上限，不是耗时预测或全片放行。','', '所有任务均实际readback16CPU/64GiB、exclusive=user、Requeue=0。启动仍需目标节点120秒内Root证明，重核所有用户声明85%、live memory和实际quota至少200GB剩余。内存0不解释为零占用；S/UFF/QM仍限14–19。','', 'S′6900s追加申请预算加原230800分配核秒为94.777778核时；实际总账仍含失败、重复、控制、cleanup与闭合成本，须守原96核时门槛。申请wall不是保证实际计费上限。Pprime2000QM仍待实际frame PASS和retention闭合；其99.5%/11.7分配核秒门槛未变。','',f"全run实际父任务{len(parents)}个，点时已观测分配核时{account['allocated_core_hours_observed']}；包含所有FAILED/TIMEOUT，step不重复加费，0整秒不代表真实零耗时。",'', 'D1–D7、最终common/掩码/归一化/导出、全Pprime及扩充第一批尚未完成；目标保持active。观测时间：'+now()+'。全部输入SHA、实际scontrol/父会计和监控进程证据：'+str(proof)+'。','']
    with report.open('x',encoding='utf-8') as f:f.write('\n'.join(lines))
    write_new(proof,{'schema':'ACTUAL_ALL_REGISTERED_PHASES_REPORT_V1','observed_at':now(),'task_complete':False,'rows':rows,'observers':observers,'inputs':inputs,'owned_parent_count':len(parents),'allocated_core_hours_observed':account['allocated_core_hours_observed'],'report':pin(report)})
    print({'report':pin(report),'proof':pin(proof),'jobs':len(rows),'live_observers':len(observers),'owned_parents':len(parents),'task_complete':False})
if __name__=='__main__':main()