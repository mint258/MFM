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
    for row in active_fits) or '无活动拟合'
latest_fits={}
for row in sorted(ledger['statistics'].values(),key=lambda value:value.get('released_at',0)):
    if row.get('mode') in ('finetune','finetune_native'):latest_fits[row['run']]=row
waiting_fits=[row for row in latest_fits.values()
    if row.get('resource_closed') and row.get('status') in
        ('PAUSED_SAFE_CONTINUATION','FAILED_STARTUP_SAFE_CONTINUATION')]
if waiting_fits:
    fit_text+='；待资源续接 '+ '；'.join(row['point']+'/'+row['task']+'/seed'+str(row['seed'])
        for row in waiting_fits)
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
curve_path=R/'results/s_recipe/budget_curve_status.json'
curve_complete=curve_path.exists() and read(curve_path).get('status')=='READOUTS_COMPLETE_FULLFT_COMPLETE'
next_work=('C1预算曲线已齐备；T6的9M训练、3M/6M/9M冻结统计及12个终点微调和配对比较已完成。下一步：完成T5的9M及登记评测，再交付完整C2分子数曲线。'
    if curve_complete else '下一步：完成剩余微调与C1/C2曲线，继续两条子集9M及其登记评测。')
science_complete=(execution['completed_full_fit_count']==192 and completed_points==16
    and read(R/'results/s_recipe/full_finetune_contrasts_status.json').get('completed_pairs')==13
    and read(R/'results/s_recipe/molecule_scaling.json').get('status')=='COMPLETE')
validation_complete=False
validation_path=R/'results/s_recipe/final_validation_20261128.json'
if validation_path.exists():
    validation=read(validation_path)
    record_path=Path(validation['native_record'])
    command_path=record_path.with_name('command_exit.json')
    if record_path.exists() and command_path.exists():
        actual=read(record_path); command=read(command_path)
        validation_complete=(validation.get('status')=='COMPLETE' and len(validation.get('steps',[]))==4
            and all(row.get('exit_code')==0 for row in validation['steps'])
            and actual.get('status')=='COMPLETE' and actual.get('exit_code')==0
            and command.get('exit_code')==0 and actual.get('owned_descendants_exited')
            and actual.get('observer_joined'))
if science_complete:
    next_work=('全部登记科学工作、C1/C2曲线及一次完整默认CPU回归/仓库检查已完成；下一步：最终交付并开PR、不合并。'
        if validation_complete else
        '全部登记科学工作已闭合（192个fit、16个完整评测点、13项配对、C2九点/54行VAL）；固定截止成本已交付。下一步：一次完整默认CPU回归与仓库检查，登记实际结果后开PR、不合并。')

lines=['# S 配方研究 · '+stamp.date().isoformat()+' · '+stamp.strftime('%H:%M'), '',
    '已完成：原六条3M和指定诊断；S-final=S-R1。原9M的R3：B0=0.470412、final=0.449116，Δ='+format(point['delta'],'.6f')+
    '、95%CI['+format(point['ci_lower'],'.6f')+', '+format(point['ci_upper'],'.6f')+']，LOSS；原3M冻结不重开。', '',
    '当前闭合：全量微调'+str(completed_points)+'/16点评测、'+str(execution['completed_full_fit_count'])+
    '/192个fit，选中模型'+str(len(execution['selected_models']))+'份；原9M新增前缀读出/CPU统计'+
    str(len(execution['completed_original9M_prefix_statistics']))+'/16点。详情见[微调](../FULL_FINETUNING_PROGRESS.md)及[执行进展](../../../results/s_recipe/execution_progress_20261127.json)。', '',
    '在跑与预计：'+('；'.join(progress(row) for row in active) or '无活动预训练')+
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
lines += ['', '工程恢复、原失败与成本保留，完成的科学结果不重算；来源见[执行说明](../EXECUTION_20261126.md)和[资源记录](../RESOURCE_CONCURRENCY_20261127.md)。', '',
    '后续微调：同一已跟踪解释器QM9为8GiB，LogD/LogS经闭合任务峰值估算为6GiB；其它解释器16/64GiB，预训练仍64GiB；新微调运行期仅抵扣本进程已有不可回收匿名RAM。累计保留'+
    str(len(execution.get('retained_safe_pause_segments',[])))+
    '段实际75完整状态暂停；另有'+str(len(execution.get('retained_startup_admission_failures',[])))+
    '段启动准入失败（原退出码未观测、原状态保留）。各段另计失败与成本，不计成功fit；结清后按实际资源准入续接，见[资源修订](../RESOURCE_CONCURRENCY_20261127.md)。', '',
    next_work+subset_wait+'半小时监控和存储/退出保护继续。全部原任务及A/B/C完成后写最终报告，再一次完整回归/仓库检查、开PR不合并。', '',
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
