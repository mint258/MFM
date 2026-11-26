"""Current counters and registered performance metadata; no scientific refits."""
import csv
import datetime
import json
from pathlib import Path
import time
from storage_20261122 import CONTROL as C, REPO as R, write

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
    if not output.exists() or not hardware_path.exists():
        continue
    hardware=read(hardware_path)
    configuration=read(output/'configuration.json')
    with (output/'losses.csv').open('rb') as stream:
        stream.seek(max(0,stream.seek(0,2)-8192))
        tail=list(csv.reader(stream.read().decode().splitlines()))
    cursor=next(row for row in reversed(tail) if len(row)==9 and row[0].isdigit())
    count=int(cursor[0])
    budget=configuration['samples']
    finish=(datetime.datetime.fromtimestamp(now+(budget-count)/hardware['first1000']['samples_per_second'],zone)
            if count<budget else None)
    summary=read(output/'summary.json') if (output/'summary.json').exists() else {}
    rows.append(dict(run=run,samples=count,budget=budget,hardware=hardware,
        summary_status=summary.get('status'),rough_finish_CST=finish.isoformat() if finish else None))
    clip_path=output/'clip_calibration.json'
    delivery=R/'results/s_recipe'/(run+'_clip_calibration.json')
    if clip_path.exists() and not delivery.exists():
        write(delivery,dict(run=run,source=str(clip_path),calibration=read(clip_path),
                            role='Original producer own p99; reported only, never tuned'))
        new_clip.append(str(delivery.relative_to(R)))
point=read(R/'results/s_recipe/S_final_s0_9M.json')['paired_vs_B0']['R3']
def progress(row):
    label=row['run']+' '+row['hardware']['node']+' '+str(row['samples'])+'/'+str(row['budget'])
    if row['samples']>=row['budget']:
        return label+('，训练及正式冻结统计已完成' if row['summary_status']=='COMPLETE'
                      else '，训练完成，读出/统计状态'+str(row['summary_status']))
    return label+'，按原首1000步粗估'+datetime.datetime.fromisoformat(row['rough_finish_CST']).strftime('%m-%d %H:%M')+'训练结束'
# Deliver current closed metadata before rendering this single concise page.
if (C/'e1_s_rule_check_20261127.json').exists():
    import runpy
    runpy.run_path(str(C/'deliver_execution_progress_20261127.py'),run_name='__main__')
execution=read(R/'results/s_recipe/execution_progress_20261127.json')
completed_points=len(list((R/'results/s_recipe/full_finetune').glob('*.json')))
active=[row for row in rows if row['summary_status']!='COMPLETE']
subset_wait=('T5在节点20本次RAM准入未通过（两项预留128GiB＋余量16GiB，现场可用约107GiB），未启动、不降在跑预留；待合适资源。'
    if 'S_subset_T5_s0_9M' not in read(C/'execution.json')['runs'] else '')
lines=['# S 配方研究 · '+stamp.date().isoformat()+' · '+stamp.strftime('%H:%M'), '',
    '已完成：原六条3M和指定诊断；S-final=S-R1。原9M的R3：B0=0.470412、final=0.449116，Δ='+format(point['delta'],'.6f')+
    '、95%CI['+format(point['ci_lower'],'.6f')+', '+format(point['ci_upper'],'.6f')+']，LOSS；原3M冻结不重开。', '',
    '当前闭合：全量微调'+str(completed_points)+'/16点评测、'+str(execution['completed_full_fit_count'])+
    '/192个fit，选中模型'+str(len(execution['selected_models']))+'份；原9M新增前缀读出/CPU统计'+
    str(len(execution['completed_original9M_prefix_statistics']))+'/16点。详情见[微调](../FULL_FINETUNING_PROGRESS.md)及[执行进展](../../../results/s_recipe/execution_progress_20261127.json)。', '',
    '在跑与预计：'+'；'.join(progress(row) for row in active)+
    '。微调及前缀按登记顺序补位；训练结束估计取原首1000步速度，读出/统计另计。', '',
    '人群：E1 TRAIN=1192951；原P T5/T6与S交集249744/499456，不重抽。两条子集9M及其评测仍在登记范围内，E1争卡优先。', '',
    '真实首1000步（样本/秒；整卡点均W，非整段能耗）：']
for row in rows:
    hardware=row['hardware']
    lines.append('- '+row['run']+' / '+hardware['gpu_name']+'：'+
        format(hardware['first1000']['samples_per_second'],'.4f')+'；'+
        format(hardware['whole_card_power_sample_mean_watts'],'.2f')+'W/'+str(hardware['power_records'])+'点。')
lines += ['', '工程记账（原失败保留，完成的科学结果不重算）：',
    '- 接管路径类型和交付目录问题均已修复；原P scratch复用，最佳模型按既有规则封存。',
    '- XFS/NFS锁互斥域问题已实测修复；8M台账依据实际C0及退出证明恢复。',
    '- 两个Guard前时间误拒入口复用原4540371/4540372恢复；旧原生wait状态未知，未伪造。', '',
    '下一步：完成剩余微调、曲线与k5读出，合规空卡推进子集。'+subset_wait+'半小时监控和存储/退出保护继续。全部原任务及A/B/C完成后写最终报告，再一次完整回归/仓库检查、开PR不合并。', '',
    '待确认事项：P/S共同k*，待双方结果齐备后提交具体值；当前不选k*或触发额外种子。工程与来源见[执行说明](../EXECUTION_20261126.md)。', '']

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
