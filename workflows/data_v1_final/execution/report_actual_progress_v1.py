"""Generate a source-only progress report from bounded receipts and actual sacct.

Only <=2MiB metadata files are read; no scientific data bodies are opened.
This is a point-in-time observation, never a scientific acceptance authority.
"""
from __future__ import annotations
import argparse, datetime, hashlib, json, os, pathlib, socket, subprocess

ROOT = pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO = ROOT / 'repository'
LIMIT = 2*1024**2

def raw(path):
    path=pathlib.Path(path)
    with path.open('rb') as f:
        before=os.fstat(f.fileno()); assert before.st_size<=LIMIT
        body=f.read(LIMIT+1); after=os.fstat(f.fileno())
    assert len(body)==before.st_size<=LIMIT
    assert (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
    return body

def pin(path):
    body=raw(path)
    return {'path':str(path),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def load(path): return json.loads(raw(path))

def write_new(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        f.write(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def query(argv):
    result=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
    assert result.returncode==0, (argv,result.returncode,result.stderr)
    return result.stdout

def main():
    a=argparse.ArgumentParser();a.add_argument('--tag',required=True);a.add_argument('--report-name',required=True);x=a.parse_args()
    assert x.tag.isidentifier() and pathlib.Path(x.report_name).name==x.report_name and x.report_name.endswith('.md')
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    now=datetime.datetime.now().astimezone().isoformat()
    control=ROOT/'control'; report=REPO/'docs/data_v1'/x.report_name
    destinations=[control/f'owned_accounting_{x.tag}.json',control/f'owned_sacct_{x.tag}.txt',control/f'active_checkpoint_{x.tag}.json',report]
    assert not any(p.exists() for p in destinations)
    owned={}; refs=[]
    for p in sorted((control/'submissions').glob('*.json')):
        if '.intent.' in p.name or '.verification.' in p.name: continue
        r=load(p)
        if str(r.get('job_id','')).isdigit():
            assert str(r['job_id']) not in owned
            owned[str(r['job_id'])]=p.name;refs.append(pin(p))
    argv=['sacct','-j',','.join(sorted(owned)),'--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList','-P']
    text=query(argv); parts=[r.split('|') for r in text.strip().splitlines()]
    rows=[dict(zip(parts[0],r)) for r in parts[1:] if r[0] in owned]
    assert {r['JobIDRaw'] for r in rows}==set(owned)
    active_states={'RUNNING','PENDING','COMPLETING','CONFIGURING','SUSPENDED'}
    for r in rows:
        r['submission_receipt']=owned[r['JobIDRaw']]
        r['allocated_core_seconds_observed']=int(r['ElapsedRaw'])*int(r['AllocCPUS'])
    write_new(destinations[1],text)
    account={'schema':'DATA_V1_OWNED_ACCOUNTING_POINT_IN_TIME_V1','observed_at':now,'actual_parents':rows,'submission_receipts':refs,'command_argv':argv,'query_returncode':0,'raw_sacct_reference':pin(destinations[1]),'terminal_core_seconds':sum(r['allocated_core_seconds_observed'] for r in rows if r['State'] not in active_states),'active_parent_ids':[r['JobIDRaw'] for r in rows if r['State'] in active_states],'active_core_seconds_lower_bound':sum(r['allocated_core_seconds_observed'] for r in rows if r['State'] in active_states),'failed_parents_included':True,'foreign_model_and_old_deletion_jobs_excluded':True,'final':False}
    write_new(destinations[0],account)
    xp=control/'x_full_v3_actual_closure_v1.json'; xp_data=load(xp)
    bp=ROOT/'artifacts/expansion/screening/bounded_prefix_v2/receipt.json'; bp_data=load(bp)
    red=ROOT/'artifacts/labels/streaming_v1/reduce_med_r6_p32_v1/reduction.json';rd=load(red)
    assert rd['records']==4251 and rd['molecules']==512 and rd['stop_fields']==[]
    progress=sorted((ROOT/'artifacts/conformers/pilot_32g_v1').glob('progress*.json'))[-1]
    sp=load(progress)
    queue=query(['squeue','-w','compute-0-20','-o','%i|%j|%T|%C|%m|%M|%l|%N'])
    missing_submissions=[]
    for name in ['dv1_prefix_feature_diag_v1','dv1_label_mad_r0_p32_v1','dv1_vector_prepare_32g_v1']:
        req=control/'requests'/(name+'.json')
        if req.exists() and not (control/'submissions'/(name+'.intent.json')).exists():missing_submissions.append(pin(req))
    cp={'schema':'DATA_V1_ACTIVE_CHECKPOINT_V7','state':'ACTIVE_NOT_COMPLETE','observed_at':now,'head':query(['git','-C',str(REPO),'rev-parse','HEAD']).strip(),'accounting':pin(destinations[0]),'sprime_progress':sp,'sprime_progress_reference':pin(progress),'full_X_actual':pin(xp),'bounded_prefix_actual':pin(bp),'exact_median_pilot_reduction':pin(red),'ready_requests_without_submission_intent':missing_submissions,'compute20_queue':queue,'pending_node_scope_question':'Await user decision on using compute21 for analysis; latest user AGENTS explicitly compute20','formal_hardware':'16CPU64GiB ordinary all-user declared memory<=85%; UFF/QM14-19; no extension of one-off336live-memory exception','remaining':['336 pilot closure and full common population','MAD/mask pilot and full abnormality scan','size-rho/unit/vector frame closure and final registry','Pprime actual quantum pilot/full','final common TRAIN normalization and diagnostic geometry freeze','D3/D5/D6 real exports and model-line cosign','all-source all-split identity decontamination and expansion pipeline'],'GitHub_publication':'public d754cf5 is older source snapshot; exact-tree publication tracked separately','scientific_acceptance':False}
    write_new(destinations[2],cp)
    parent={r['JobIDRaw']:r for r in rows}
    prefix_parent=parent[bp_data['job_id']]
    masks=max(v['new_mask_fraction'] for v in rd['field_counts'].values())
    lines=[f'# 数据线实际进度快照（{now}）','',
      '目的：登记已实际完成和仍待完成的工作。此报告不是共同人群、最终注册表、归一化或训练导出的验收凭证。', '',
      '输入与方法：脚本只读取不超过2MiB的闭合receipt/控制元数据，并查询本轮不可变提交记录对应的全部Slurm父作业；不读取大型科学数据正文。核秒为父作业ElapsedRaw×AllocCPUS，包含失败。', '',
      '| 项目 | 实际结果 |','| --- | --- |',
      f"| X全原始输入回放 | {xp_data['evaluated_records']:,}唯一记录；规则及条件入选一致率{xp_data['chemical_admission_agreement']:.3%}；未解释差异{xp_data['all_native_rule_layers_and_unexplained_drift']}；{xp_data['mismatch_rows']}条历史flag差异全部留存 |",
      f"| PubChem有界前缀 | {bp_data['input_prefix_records']:,}输入行，{len(bp_data['worker_pids_observed'])}真实worker；X及身份/特征后{bp_data['counts']['after_X_and_identity']:,}行，{bp_data['unique_full_keys']:,}唯一完整key；作业{bp_data['job_id']} {prefix_parent['State']}/{prefix_parent['ExitCode']}/{prefix_parent['ElapsedRaw']}s |",
      f"| 特征失败 | {bp_data['counts']['first:IDENTITY_OR_FEATURE_FAILED']}行，比例{bp_data['counts']['first:IDENTITY_OR_FEATURE_FAILED']/bp_data['input_prefix_records']:.2%}；原错误和所有拒绝保留，三CID逐阶段诊断待执行，不新增化学排除 |",
      f"| 精确中位数小试点 | {rd['molecules']}完整分子/{rd['records']}记录/{len(rd['field_counts'])}字段；已完成median全部radix轮，MAD与最终mask待执行；本阶段新增mask最大比例{masks:.3%} |",
      f"| S′补齐小试点4520364 | {sp['completed']}/{sp['expected']}完成；submitted={sp['submitted']}；dispatch_allowed={sp['dispatch_allowed']}；resource_denial={sp['resource_denial']}；尚待最终receipt/实际成本/失败分层审查 |",
      f"| 本轮作业记账 | {len(rows)}个实际父作业，已终态{account['terminal_core_seconds']:,}分配核秒；仍活动{account['active_parent_ids']}，活动成本另为下限，不能报总成本完成 |", '',
      '异常与处理：compute-0-20当前被其他作业全部占用，已备诊断/MAD/只读vector准备请求尚无提交intent；不修改或终止该作业。正式生成维持原16CPU/64GiB及普通全部用户申报内存85%要求，UFF/QM仅14–19。本轮336分子小试点的单次实测内存例外不扩展。', '',
      '实现验证：size语义增量13项/16进程实际通过（4520430）；S′稳定物理ID新增9项实际通过；P′稳定raw policy4项、保留策略3项、正式流程8项及修复后的SQL fixture1项实际通过。旧SQL fixture失败证据保留。实现与合成测试不替代真实科学验收。', '',
      '已知限制：前10000输入行不是PubChem代表性样本，尚未完成去污染。X回放仍待共同人群范围绑定。当前校准使用原TRAIN的小试点，不能用作D-4；D-4须冻结common及诊断几何后重算。D-1 draft.3尚未双方定为v3.0，D-2及D-3至D-7最终真实交付均未完成。', '',
      '输入小文件引用：','', '```json',json.dumps({'X_closure':pin(xp),'prefix_receipt':pin(bp),'median_reduction':pin(red),'progress':pin(progress),'actual_accounting':pin(destinations[0]),'checkpoint':pin(destinations[2])},ensure_ascii=False,indent=2),'```','']
    write_new(report,'\n'.join(lines))
    status=f'''# 数据线与模型线接口状态

更新：{now}。分支data-v1。最新实际证据见[进度快照](../data_v1/{x.report_name})；源码发布与数据验收分开登记。

- 用户决定保持：Se单元素排除率例外，仍排除UFF_UNSUPPORTED；VAL为既有全部ROUTINE7610分子/72525 PM7记录，TRAIN1206608分子/11104772记录。小试点可降低资源使用，正式生成维持原硬件要求。
- D-1：[契约draft.3](training_format_v3.md)，尚待双方共同定为v3.0。D-2：146启用统计分量，物理target聚合/单位/size-rho及实际参考系仍待闭合，未冻结最终family或模型head数。
- 标签512完整分子/4251记录/16来源组已完成精确median全部轮次，新增mask为0；MAD与mask尚待执行。normalization实现实际24fixture通过，最终D-4须common/roles/geometry/order/diagnostic冻结后重建，当前试点不代替它。
- S′336分子试点job4520364当前{sp['completed']}/{sp['expected']}，未最终验收。正式生成保持16CPU64GiB、14–19及全部用户声明内存85%；本次live-memory例外仅这336。N=1分子保留common候选，第二P′候选仍待独立真实方案。
- P′已完成1000分子/2000UFF输入准备，尚无量子计算；稳定物理ID/扰动身份复用及raw保留方案已实现验证。实际vector/tensor frame和量子试点待闭合。
- PubChem官方raw已实际下载并验证SHA/CRC。X全原始输入{xp_data['evaluated_records']:,}记录回放通过，未解释差异0；共同人群范围仍待绑定。前缀10000行实际得到{bp_data['unique_full_keys']}唯一key，但{bp_data['counts']['first:IDENTITY_OR_FEATURE_FAILED']}条特征失败待诊断；全部下游全部划分去污染未完成，未发布候选池，未生成扩充UFF/D。
- D-3/D-4/D-5/D-6/D-7最终真实交付未完成。D7仅256分子只读试点报告；D5/导出实现有实际合成验证，尚缺冻结科学权威和真实导出。
- compute-0-20当前全部CPU被其他作业占用；本轮未修改或终止该作业。已备小任务暂未提交，节点范围确认待用户回复。

不可变用户决定见configs/data_v1/run_decisions_v2.json与v3.json。每项实际父作业成本含失败；活动作业成本只是下限。完整v1和扩充批次未完成，尚未按最终提交规则开PR。
'''
    (REPO/'docs/interfaces/STATUS.md').write_text(status,encoding='utf-8',newline='\n')
    print(json.dumps({'report':pin(report),'checkpoint':pin(destinations[2]),'actual_parent_count':len(rows),'active_ids':account['active_parent_ids'],'status_updated':True},ensure_ascii=False))

if __name__=='__main__':main()
