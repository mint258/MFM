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
lines=['# S 配方研究 · '+stamp.date().isoformat(),'',
    '已完成：原六条3M及三组指定诊断此前闭合，CURRENT_BEST=S-R1。两条原9M正式统计已闭合：R3的B0=0.470412、final=0.449116；final−B0='+format(point['delta'],'.6f')+
    '，95%CI['+format(point['ci_lower'],'.6f')+', '+format(point['ci_upper'],'.6f')+']，原规则LOSS。原3M冻结不重开，见[9M报告](../9M_CONFIRMATION.md)。两9M的36个固定VAL记录已对齐[预算表](../BUDGET_CURVE.md)；仅复用9M读出，16个中间读出和5个微调点仍待。', '',
    '准备完成：既有14项检查保留，新增8项合成检查通过；矩阵16组/192项微调、复用12项P scratch。E1共同TRAIN1192951，原P的T5/T6与S交集249744/499456；实际均k见[扩展注册](../EXTENSIONS_20261124.md)。退役闭合诊断H暂存23165911040字节，保留指标/NPZ/预测及失败partial。已推送并导入93a74b93。', '',
    '进度与预计结束（'+stamp.strftime('%H:%M')+'）：'+'；'.join(progress(row) for row in rows)+
        '。活跃运行的读出/统计另计，估计非保证；同任务真实接管待机分别记录，排队不计虚构分配，保留完整状态交接。', '',
    '本轮真实首1000步：'+'；'.join(row['run']+' / '+row['hardware']['gpu_name']+' '+format(row['hardware']['first1000']['samples_per_second'],'.4f')+
        '样本/秒、整卡点均'+format(row['hardware']['whole_card_power_sample_mean_watts'],'.4f')+'W/'+str(row['hardware']['power_records'])+'点' for row in rows)+
        '。无另测，不外推跨卡因果提速或整段能耗；原值见[启动记录](../EXTENSION_STARTUP.md)。', '',
    '资源与工程：短CPU按[11-26新规](../../interfaces/SCHEDULING_RULE_20261126.md)实测空闲核后SSH执行，记录真实退出和CPU时间；原五项队列核实UID/PENDING/零运行后撤销。k1完整训练和GPU读出已退出，训练待机4540277、读出待机4540341均核实本账号零运行取消后才退役预留；k5接续节点22，待机4540342。节点20第二卡此前因实际并发RAM不足拒绝，不缩减峰值占卡。新增6项结清边界检查通过；旧科学统计/旧套件未重跑，详见[执行适配](../EXECUTION_20261126.md)。在跑训练继续，未触发seed1。', '',
    '下一步：活跃E1继续各自3M，正式读出后接CPU原统计；合规空卡优先B0/G1全量微调，E1先于T5/T6。半小时监控、磁盘/配额/自有退出守卫及工程续接保持；全部原任务及A/B/C完成后才最终报告、一次完整回归/仓库检查、开PR不合并。当前无待用户决定事项；S/P共同k*后续另待确认。', '']
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
