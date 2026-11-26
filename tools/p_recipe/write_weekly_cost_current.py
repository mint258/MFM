"""Existing P weekly cost writer, extended for registered F/A/I phases.
Consumes exact native metadata; never calls Slurm, training or old science.
"""
import argparse,json,re,sys
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path

R=Path('/share/home/zixiao/descriptor_analysis')
C=R/'runs/p_recipe_20261113'
sys.path.insert(0,str(C))
from report_study import elapsed
REPO=R/'MFM_p_recipe'
LOCAL=timezone(timedelta(hours=8))
CLOSED_INITIAL_GPU_HOURS=3.81173

CPU_KINDS={'A1_STATS','F_STATS','F_CONTRASTS','A3_STATS'}
GPU_NODES={'compute-0-'+str(n) for n in list(range(8))+[20,21,22]}
HISTORICAL_STAGES={2,'calibration','calibration_speed'}
TERMINAL={'COMPLETED','COMPLETE','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED'}

def cost_records(ledger,native):
    """Use exact P handles, native metadata and the existing legacy clocks."""
    records=[];skipped=[];aliases=[];seen={}
    source=list(ledger['runs'].items());native_rows=native.get('rows',{})
    common={str(x['job_id']) for _,x in source if x.get('job_id')}
    for job in native.get('explicit_native_analysis_GPU_job_ids',[]):
        if job not in common and job in native_rows:
            row=native_rows[job]
            source.append((row['job_name'],dict(backend='Slurm',job_id=job,node=row['node'],purpose='REGISTERED_ANALYSIS_GPU',study_revision='analysis_20261122')))
    for name,original in source:
        record=dict(original);job=str(record.get('job_id',''));row=native_rows.get(job,{})
        node=row.get('node') if row.get('node') in GPU_NODES else record.get('node')
        if record.get('kind') in CPU_KINDS or node not in GPU_NODES:
            reason='CPU_target' if record.get('kind') in CPU_KINDS or node in {'compute-0-'+str(x) for x in range(8,20)} else 'Unproven_GPU_or_CPU_role'
            skipped.append(dict(name=name,job=job,reason=reason));continue
        if row and row['elapsed_seconds']==0 and row.get('start') in {'Unknown','N/A','None'}:
            skipped.append(dict(name=name,job=job,reason='No_native_allocation_start'));continue
        record['_cost_name']=name
        if job:record.setdefault('backend','Slurm')
        if record.get('backend') is None and job:record['backend']='Slurm'
        if record.get('backend')=='Slurm' and row:
            # Closed historical clocks include earlier native/Slurm handoff and
            # lower-bound handling. Preserve them instead of rewriting history.
            preserve=(record.get('accounting_closed') or record.get('elapsed_seconds_floor')
                      or 'lower bound' in record.get('cost_note','').lower()
                      or (record.get('stage') in HISTORICAL_STAGES and 'elapsed_seconds' in record))
            if not preserve:
                record['allocation_elapsed_seconds']=row['elapsed_seconds']
                record['elapsed_seconds']=max(0.,row['elapsed_seconds']-record.get('allocation_pretraining_seconds',0.))
            record['state']=row['state'].split()[0].rstrip('+');record['native_cost_observed_at']=native.get('observed_at')
        if record.get('backend')=='Slurm':
            handle=('Slurm',job) if job else ('unproven',name)
        elif record.get('native_pid') is not None and record.get('native_start_ticks') is not None:
            handle=('native',node,record.get('native_uid'),record['native_pid'],record['native_start_ticks'])
        else:handle=('native_state',record.get('native_state',name))
        if handle in seen:
            prior=seen[handle]
            if elapsed(record)!=elapsed(prior):raise ValueError('Physical alias clocks disagree: '+name)
            aliases.append(dict(name=name,canonical=prior['_cost_name'],job=job));continue
        if record.get('backend') not in {'Slurm','native_SSH'} and not record.get('accounting_closed'):
            raise ValueError('GPU clock has no supported native backend: '+name)
        seen[handle]=record;records.append((name,record))
    return records,skipped,aliases

def bucket(record):
    name=record.get('_cost_name','')
    if record.get('kind')=='F' and name.startswith('E1FT_'):return 'analysis_E1_full'
    if record.get('kind')=='E1_TRAINING' or 'E1_k' in name:return 'analysis_E1_training'
    revision=record.get('study_revision','')
    stage=record.get('stage')
    if revision=='original_20261113':return 'archived_screening'
    if stage=='calibration_speed':return 'batch_speed'
    if stage=='calibration':return 'calibration'
    if revision=='fixed_20261115_noise_seed1':return 'noise_seed1'
    if stage==2:return 'current_screening'
    if stage==3:return 'confirmation'
    name=record.get('_cost_name','')
    if record.get('kind')=='F':
        if name.startswith('F1_'):return 'analysis_F1'
        if name.startswith('F2FT_'):return 'analysis_F2'
        if name.startswith('I1FT_'):return 'analysis_I1_full'
    if record.get('kind')=='A1':return 'analysis_A1'
    if 'composition' in name.lower():return 'analysis_composition'
    if record.get('kind')=='A3_FORWARD' or 'A3_B4_forward' in name:return 'analysis_A3'
    if 'A6' in name:return 'analysis_A6'
    if 'I1' in name:return 'analysis_I1'
    if 'budget_' in name or record.get('stage')==0:return 'budget_readouts'
    return 'other'

def build():
    ledger=json.loads((C/'study_execution.json').read_text())
    snapshot=C/'weekly_cost_native_snapshot_20261123.json'
    native=json.loads(snapshot.read_text()) if snapshot.is_file() else {}
    records,skipped,aliases=cost_records(ledger,native)
    stamp=datetime.fromtimestamp(native.get('observed_at',ledger['last_observed_at']),timezone.utc)
    local=stamp.astimezone(LOCAL)
    revision=json.loads((REPO/'configs/p_recipe/fixed_20261115/base.json').read_text())['study_revision']
    groups=defaultdict(float);counts=defaultdict(int)
    screening=0.;reused=0.;unknown=[x['name']+' (unprovenCPU/GPUrole)' for x in skipped if x['reason']=='Unproven_GPU_or_CPU_role'];preflight_rejected=[];lower_bounds=[]
    for name,record in records:
        rejected=(record.get('state')=='FAILED' and record.get('training_started') is False
                  and record.get('actual_samples')==0
                  and record.get('end_reason')=='native_GPU_lock_rejected_before_training')
        if record.get('elapsed_seconds_floor') or 'lower bound' in record.get('cost_note','').lower():lower_bounds.append(name)
        if rejected:preflight_rejected.append(name)
        elif record.get('accounting_closed'):
            if 'elapsed_seconds' not in record:unknown.append(name)
        elif record['backend']=='Slurm':
            if 'elapsed_seconds' not in record:unknown.append(name)
        else:
            path=Path(record['native_state'])
            if not path.is_file():unknown.append(name)
            else:
                state=json.loads(path.read_text())
                if 'exit_code' not in state and record.get('observation_status')!='LIVE_BOUND_PROCESS':
                    unknown.append(name)
        hours=elapsed(record)/3600
        group=bucket(record);groups[group]+=hours;counts[group]+=int(not rejected)
        if record.get('study_revision')==revision and record.get('stage')==2:screening+=hours
        if record.get('screening_reuse_attribution',{}).get('study_revision')==revision:reused+=hours
    diagnostics=0.
    for name in ('P0_D1','P0_D2'):
        state=json.loads((C/(name+'_native.json')).read_text())
        if 'exit_code' not in state:raise ValueError('Closed P0 diagnostic lacks terminal accounting: '+name)
        diagnostics+=state['elapsed_seconds']/3600
    physical=sum(groups.values())
    acceptance_records={name:record for name,record in ledger.get('reservations',{}).items() if record.get('purpose')=='DEVELOPMENT_ACCEPTANCE'}
    acceptance=sum(elapsed(record) for record in acceptance_records.values())/3600
    for name,record in acceptance_records.items():
        if 'elapsed_seconds' not in record:unknown.append(name)
    current_report=C/revision/'round1_report_current.json'
    if not native and current_report.is_file():
        report=json.loads(current_report.read_text())
        if report['observed_at']==stamp.timestamp():
            if abs(physical-report['physical_training_gpu_hours'])>1e-8:
                raise ValueError('Weekly and daily accounting disagree')
    total=CLOSED_INITIAL_GPU_HOURS+diagnostics+physical+acceptance
    labels=[
        ('archived_screening','旧B128筛选及被取消的下一轮','结论作废，仅存档成本'),
        ('batch_speed','用户指定B32/B128测速','12个逻辑测量，含故障续接尝试'),
        ('calibration','G1–G4校准及续接','G2–G4已按用户停止；G1完成并复用B0'),
        ('current_screening','当前筛选（含归档/失败/迁出尝试）','原三轮及注册第4轮均3M，已闭合'),
        ('noise_seed1','M2 seed1噪声对照（含失败尝试）','独立注册，不重复计入主筛选预算'),
        ('confirmation','放大确认','每条9M，尚未启动' if groups['confirmation']==0 else '每条9M，按实际运行记录'),
        ('budget_readouts','22个预算补充读出及相关失败尝试','原断点评价，无新增预训练'),
        ('analysis_F1','F第一批full/top2/scratch','原120次；含分配及原入口收尾'),
        ('analysis_F2','F第二批full','原60次；含分配及原入口收尾'),
        ('analysis_A1','A1读出噪声','原16个R3读出；不含CPU统计'),
        ('analysis_composition','A2/H-comp组成前向','固定面板原前向；不含CPU统计'),
        ('analysis_A3','A3惩罚项前向','原注册前向及已发生尝试'),
        ('analysis_A6','A6三万标签读出','四来源16个R3单元'),
        ('analysis_I1','I1去B4自身3M','截至快照的原生占用；训练尚未闭合时非最终成本'),
        ('analysis_I1_full','I1注册full微调','仅实际发生的注册四任务三种子'),
        ('analysis_E1_training','E1构象数自身3M及读出','k1/2/5新3M；k10原参照复用不重复计时'),
        ('analysis_E1_full','E1原四任务三种子full','各格12项；不计CPU统计/测试'),
        ('other','其他已登记GPU运行','逐条真实句柄计时'),
    ]
    lines=[
        f'{local:%Y-%m-%d} 周更新，截至 {stamp:%Y-%m-%d %H:%M:%S UTC}（{local:%m-%d %H:%M:%S CST}）。',
        '',
        '每条实际GPU运行计一张卡的占用墙钟，包含初始化、评价和已发生的失败/取消成本。只从现有执行台账与原生起止状态汇总，不重跑训练、测速、P0或数据统计。',
        '',
        '| 阶段 | 已记录GPU小时 | 口径/状态 |',
        '|---|---:|---|',
        f'| 前期校验/P0及旧公共batch测量（已闭合） | {CLOSED_INITIAL_GPU_HOURS:.5f} | 沿用11-13周记的已闭合值 |',
        f'| 后续P0 D1/D2（已闭合） | {diagnostics:.5f} | 真实原生终态；CPU-only D3/标签拟合不记GPU小时 |',
    ]
    for key,label,note in labels:
        if key not in {'other','analysis_I1_full'} or counts[key]:lines.append(f'| {label} | {groups[key]:.5f} | {note}；{counts[key]}条物理运行 |')
    lines += [
        f'| F1真实加载器与逐头验收 | {acceptance:.5f} | 两次原生Slurm验收，含未通过尝试；不重复计入正式3M训练 |',
        f'| 物理合计 | {total:.5f} | '+('已记录部分/保守下界，见说明' if unknown or lower_bounds else '全部已登记运行；复用和接管不重复累计')+' |',
        '',
        f'当前研究（{revision}）筛选预算归属：新筛选 {screening:.5f}h + 复用G1/B0 {reused:.5f}h = {screening+reused:.5f}h。复用G1已经在校准物理成本内，以上只说明预算归属，不在物理合计再加一次。历史作废B128筛选单列；当前研究内迁出node21、此前A4迁移及其他已发生尝试仍计入当前筛选。',
        '',
        'Slurm沿用顶层作业实际Elapsed，并扣除台账已记录的接管前等待/原生重叠；原生SSH使用已核实PID/UID/start_ticks对应的真实起止时刻或本次live_verified_at。PENDING接管队列没有GPU运行时间；接管后两段真实运行各计一次，不把占位队列或逻辑别名再次当成训练。共享GPU时仍只记本任务自身一张卡的占用时间，不改其他用户作业。',
        '',
        '当前预算为筛选3M/条、确认9M/条。原任务书第8节的约135h筛选、145–170h确认来自旧样本预算，保留作历史估计，不作为新预算的工时承诺；实测吞吐和整卡功耗见当日日报及hardware_round*.csv。超原估计1.5倍只报告；200GPUh筛选上限已按11-17用户指示取消。最终配方已冻结，五条单种子9M为既定确认预算，不因成本估计停训。',
        '',
        '前期3.81173h来源沿用11-13周记及其原作业清单；后续P0沿用已闭合P0_D1/P0_D2原生状态。F1验收4536840/4536854分别1362/766秒，来自既有reservations台账，与正式训练互斥且单列。CPU-only拟合、D3和回归单列为CPU工作，不混入GPU小时。价格未提供，不换算费用。',
    ]
    lines+=['','11-22新增F/A/I按同一套原生句柄统计：CPU统计/测试不混入GPU小时，额外分析GPU句柄只取本线已登记原生来源；别名去重，未开始分配的占位作业不计。原CPU TotalCPU未测则保持未知，不能用已分配CPU秒冒充实耗。I1仍运行时本表是快照；全部注册后续完成后再闭合最终成本。']
    lines+=['','本次快照原生GPU句柄别名去重'+str(len(aliases))+'条；排除CPU或未分配记录'+str(len(skipped))+'条。来源为原study_execution.json与weekly_cost_native_snapshot_20261123.json，不回读旧模型结果或遥测。']
    lines+=['',f'11-22B F第一批原估90–130GPU小时，本次120个实际分配合计{groups["analysis_F1"]:.5f}h；第二批原60个合计{groups["analysis_F2"]:.5f}h。这里是本任务单目标卡的原生占用墙时，不是利用率积分或GPU内核执行时间。']
    if preflight_rejected:lines+=['','GPU锁预检拒绝、未创建训练进程的尝试：'+', '.join(preflight_rejected)+'。原台账明确training_started=false、actual_samples=0及锁拒绝原因，因此GPU时间为0；wrapper的CPU耗时不伪称已测，不把这两条算作物理GPU运行。']
    if lower_bounds:lines+=['','仅有已记录耗时下界的历史运行：'+', '.join(lower_bounds)+'。原Slurm重入/节点重启导致终止计时缺失，沿用原CSV/遥测下界，保留原始会计；以上合计因此也是下界，不伪称精确总量。']
    if unknown:lines+=['','未测/未能核实句柄：'+', '.join(unknown)+'。合计只含已记录时长，不把未知时长断言为零。']
    marker=f'<!-- weekly-cost:{local:%Y-%m-%d} -->'
    endmarker=f'<!-- /weekly-cost:{local:%Y-%m-%d} -->'
    target=REPO/'docs/p_recipe/COST.md';old=target.read_text()
    old=re.sub(re.escape(marker)+r'.*?'+re.escape(endmarker)+r'\n*','',old,flags=re.S)
    header,body=old.split('\n\n',1)
    content=header+'\n\n'+marker+'\n'+'\n'.join(lines)+'\n'+endmarker+'\n\n'+body
    return content,dict(observed_at=stamp.timestamp(),local_date=f'{local:%Y-%m-%d}',physical_ledger_gpu_hours=physical,F1_acceptance_gpu_hours=acceptance,F1_acceptance_jobs={k:v.get('job_id') for k,v in acceptance_records.items()},closed_initial_gpu_hours=CLOSED_INITIAL_GPU_HOURS,closed_D1_D2_gpu_hours=diagnostics,total_physical_gpu_hours=total,current_screening_gpu_hours=screening,reused_baseline_gpu_hours=reused,screening_budget_gpu_hours=screening+reused,groups=dict(groups),counts=dict(counts),unknown_handles=unknown,preflight_rejected_before_GPU=preflight_rejected,lower_bound_handles=lower_bounds,total_is_lower_bound=bool(unknown or lower_bounds),skipped_non_GPU_or_unallocated=skipped,physical_aliases=aliases,active_GPU_handles=[dict(name=n,job=r.get('job_id'),state=r.get('state'),seconds=elapsed(r)) for n,r in records if r.get('state') not in TERMINAL],native_snapshot=str(snapshot),snapshot_not_final=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true')
    args=parser.parse_args();content,summary=build()
    if args.write:(REPO/'docs/p_recipe/COST.md').write_text(content)
    print(json.dumps(dict(**summary,written=args.write,document_characters=len(content)),ensure_ascii=False))
