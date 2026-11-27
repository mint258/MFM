"""Current counters and registered performance metadata; no scientific refits."""
import csv
import datetime
import json
from pathlib import Path
import time
from storage_20261122 import CONTROL as C, REPO as R, write
from control_metadata_io_20261127 import write

read=lambda path:json.loads(Path(path).read_text())
zone=datetime.timezone(datetime.timedelta(hours=8))
now=time.time()
stamp=datetime.datetime.fromtimestamp(now,zone)
rows=[]
new_clip=[]
for run in ('S_E1_k1_s0_3M','S_E1_k2_s0_3M','S_E1_k5_s0_3M',
            'S_subset_T5_s0_9M','S_subset_T6_s0_9M'):
    output=C/'training'/run
    hardware_path=R/'results/s_recipe'/(run+'_initial_hardware.json')
    if not output.exists() or not (output/'losses.csv').exists():
        continue
    hardware=read(hardware_path) if hardware_path.exists() else None
    configuration=read(output/'configuration.json')
    with (output/'losses.csv').open('rb') as stream:
        stream.seek(max(0,stream.seek(0,2)-8192))
        tail=list(csv.reader(stream.read().decode().splitlines()))
    cursor=next((row for row in reversed(tail) if len(row)==9 and row[0].isdigit()),None)
    count=int(cursor[0]) if cursor else 0
    budget=configuration['samples']
    finish=(datetime.datetime.fromtimestamp(now+(budget-count)/hardware['first1000']['samples_per_second'],zone)
            if count<budget and hardware else None)
    summary=read(output/'summary.json') if (output/'summary.json').exists() else {}
    rows.append(dict(run=run,samples=count,budget=budget,hardware=hardware,node=configuration['node'],
        summary_status=summary.get('status'),rough_finish_CST=finish.isoformat() if finish else None))
    clip_path=output/'clip_calibration.json'
    delivery=R/'results/s_recipe'/(run+'_clip_calibration.json')
    if clip_path.exists() and not delivery.exists():
        write(delivery,dict(run=run,source=str(clip_path),calibration=read(clip_path),
                            role='Original producer own p99; reported only, never tuned'))
        new_clip.append(str(delivery.relative_to(R)))
point=read(R/'results/s_recipe/S_final_s0_9M.json')['paired_vs_B0']['R3']
def progress(row):
    label=row['run']+' '+row['node']+' '+str(row['samples'])+'/'+str(row['budget'])
    if row['samples']>=row['budget']:
        return label+('，训练及正式冻结统计已完成' if row['summary_status']=='COMPLETE'
                      else '，训练完成，读出/统计状态'+str(row['summary_status']))
    return label+('，首1000步吞吐待原记录交付' if not row['rough_finish_CST'] else
        '，按原首1000步粗估'+datetime.datetime.fromisoformat(row['rough_finish_CST']).strftime('%m-%d %H:%M')+'训练结束')
# Deliver current closed metadata before rendering this single concise page.
if (C/'e1_s_rule_check_20261127.json').exists():
    import runpy
    runpy.run_path(str(C/'deliver_execution_progress_20261127.py'),run_name='__main__')
execution=read(R/'results/s_recipe/execution_progress_20261127.json')
completed_points=len(list((R/'results/s_recipe/full_finetune').glob('*.json')))
ledger=read(C/'execution.json')
active_fits=[row for row in ledger['statistics'].values()
    if row.get('mode') in ('finetune','finetune_native') and not row.get('resource_closed')]
fit_text='；'.join(row['point']+'/'+row['task']+'/seed'+str(row['seed'])+'@'+row['node']
    for row in active_fits) or '无未结清拟合'
from conformer_mean_reporting_20261127 import means
actual_means=means()
e1_path=R/'configs/s_recipe/E1_k_star.json'
e1_decision=read(e1_path) if e1_path.exists() else {}
e1_pending=('S本线k*='+str(e1_decision['k_star'])+'已闭合，未触发额外seed1；P/S共同值仍待用户确认。'
    if e1_decision.get('status')=='COMPLETE' and not e1_decision.get('conditional_seed1_required') else
    'P/S共同k*，待双方结果齐备后提交具体值；当前不选k*或触发额外种子。')
active=[row for row in rows if row['summary_status']!='COMPLETE']
subset_wait=('T5在节点20本次RAM准入未通过（两项预留128GiB＋余量16GiB，现场可用约107GiB），未启动、不降在跑预留；待合适资源。'
    if 'S_subset_T5_s0_9M' not in ledger['runs'] else '')
lines=['# S 配方研究 · '+stamp.date().isoformat()+' · '+stamp.strftime('%H:%M'), '',
    '已完成：原六条3M和指定诊断；S-final=S-R1。原9M的R3：B0=0.470412、final=0.449116，Δ='+format(point['delta'],'.6f')+
    '、95%CI['+format(point['ci_lower'],'.6f')+', '+format(point['ci_upper'],'.6f')+']，LOSS；原3M冻结不重开。', '',
    '当前闭合：全量微调'+str(completed_points)+'/16点评测、'+str(execution['completed_full_fit_count'])+
    '/192个fit，选中模型'+str(len(execution['selected_models']))+'份；原9M新增前缀读出/CPU统计'+
    str(len(execution['completed_original9M_prefix_statistics']))+'/16点。详情见[微调](../FULL_FINETUNING_PROGRESS.md)及[执行进展](../../../results/s_recipe/execution_progress_20261127.json)。', '',
    '在跑与预计：'+'；'.join(progress(row) for row in active)+
    '。当前微调：'+fit_text+'。微调在登记范围内按E1优先补位；训练结束估计取原首1000步速度，读出/统计另计。', '',
    '人群：E1 TRAIN=1192951；实际平均PM7构象数（上限1/2/5/10）='+
    '/'.join(format(actual_means[str(k)],'.9f') for k in (1,2,5,10))+
    '；原P T5/T6与S交集249744/499456，不重抽。两条子集9M及其评测仍在登记范围内，E1争卡优先。', '',
    '真实首1000步（样本/秒；整卡点均W，非整段能耗）：']
for row in rows:
    hardware=row['hardware']
    if not hardware:continue
    lines.append('- '+row['run']+' / '+hardware['gpu_name']+'：'+
        format(hardware['first1000']['samples_per_second'],'.4f')+'；'+
        format(hardware['whole_card_power_sample_mean_watts'],'.2f')+'W/'+str(hardware['power_records'])+'点。')
lines += ['', '工程记账（原失败保留，完成的科学结果不重算）：',
    '- 接管路径类型和交付目录问题均已修复；原P scratch复用，最佳模型按既有规则封存。',
    '- XFS/NFS锁互斥域问题已实测修复；8M台账依据实际C0及退出证明恢复。',
    '- 两个Guard前时间误拒入口复用原4540371/4540372恢复；旧原生wait状态未知，未伪造。', '',
    '后续微调：相同解释器的实际vfork/exec及元数据开销支持8GiB物理预留；预训练仍64GiB。累计保留'+
    str(len(execution.get('retained_safe_pause_segments',[])))+
    '段实际75完整状态暂停，另计失败与成本，不计成功fit；结清后按实际资源准入续接，见[资源修订](../RESOURCE_CONCURRENCY_20261127.md)。', '',
    '下一步：完成剩余微调、曲线与k5读出，合规空卡推进子集。'+subset_wait+'半小时监控和存储/退出保护继续。全部原任务及A/B/C完成后写最终报告，再一次完整回归/仓库检查、开PR不合并。', '',
    '待确认事项：'+e1_pending+'工程与来源见[执行说明](../EXECUTION_20261126.md)。', '']

daily=R/'docs/s_recipe/daily'/(stamp.date().isoformat()+'.md')
daily.write_text('\n'.join(lines))
state=read(C/'current_state.json')
state['extension_latest_progress']=rows
admission=read(C/'gpu_writer_admission_check_20261126.json')
admission_record=read(admission['native_record'])
admission_exit=read(Path(admission['native_record']).with_name('command_exit.json'))
if (admission['new_tests']!=2 or admission_record['status']!='COMPLETE'
        or admission_record['exit_code']!=0 or admission_exit['exit_code']!=0
        or not admission_record['owned_descendants_exited'] or not admission_record['observer_joined']):
    raise ValueError('New writer-admission check must close before reporting')
admission_delivery=R/'results/s_recipe/gpu_writer_admission_check_20261126.json'
if not admission_delivery.exists():
    write(admission_delivery,dict(admission,execution=admission_record))
state['unpublished_changes']=sorted(set(state.get('unpublished_changes',[])+new_clip+
    [str(daily.relative_to(R)),str(admission_delivery.relative_to(R))]))
write(C/'current_state.json',state)
print(json.dumps(dict(observed_CST=stamp.isoformat(),runs=[dict(run=row['run'],samples=row['samples'],
    rough_finish_CST=row['rough_finish_CST']) for row in rows],new_clip_records=new_clip)),flush=True)
