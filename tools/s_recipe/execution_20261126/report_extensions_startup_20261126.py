"""Record each new real-training first1000 once, without a separate benchmark."""
import csv
import json
from pathlib import Path
from storage_20261122 import CONTROL as C, REPO as R, write
from cpu_execution_20261126 import execution_fields

read=lambda path:json.loads(Path(path).read_text())
new=[]
for run in ('S_E1_k1_s0_3M','S_E1_k2_s0_3M','S_E1_k5_s0_3M',
            'S_subset_T5_s0_9M','S_subset_T6_s0_9M'):
    source=C/'training'/run
    target=R/'results/s_recipe'/(run+'_initial_hardware.json')
    if target.exists() or not (source/'initial_throughput.json').exists():
        continue
    c=read(source/'configuration.json')
    throughput=read(source/'initial_throughput.json')
    controller=read(C/(run+'_extension_controller.json'))
    actual=read(C/'execution.json')['runs'][run]
    life=read(actual['lifecycle_record'])
    if (c['seed']!=0 or throughput['samples']!=32000
            or c['initialization']!=str(C/'initialization_seed0.pt') or life['run']!=run):
        raise ValueError('Bind the registered real first1000 producer')
    with (source/'gpu_telemetry.csv').open() as stream:
        rows=[row for row in csv.DictReader(stream)
              if int(row['samples'])<=32000 and row['gpu_uuid']==c['gpu_uuid']]
    if not rows:
        raise ValueError('Real first1000 power samples are unavailable')
    record=dict(run=run,node=c['node'],gpu_uuid=c['gpu_uuid'],gpu_name=rows[0]['gpu_name'],
        actual_training_job=life['job_id'],standby_job_id=life.get('standby_job_id'),
        actual_producer=life['producer'],ordered_readers=c['workers'],requested_cpus=controller['cpus'],
        allocated_cpus=controller['cpus'] if life['job_id'] is not None else 0,
        first1000=throughput,
        whole_card_power_sample_mean_watts=sum(float(row['whole_card_power_watts']) for row in rows)/len(rows),
        power_records=len(rows),source_throughput=str(source/'initial_throughput.json'),
        source_telemetry=str(source/'gpu_telemetry.csv'),source_configuration=str(source/'configuration.json'),
        finite_deadline_epoch=life['actual_deadline_epoch'],closing_reserve_seconds=life['closing_reserve_seconds'],
        speed_switches=c['speed_switches'],fresh_random_initialization=True,
        accounting_execution=execution_fields(),
        actual_lifecycle_source=actual['lifecycle_record'],
        original_native_lifecycle_source=actual.get('native_lifecycle_record'),
        first1000_may_span_complete_state_handoff=bool(actual.get('native_lifecycle_record')),
        scope='Original real-training first1000 updates; whole-card point mean only; no separate benchmark')
    write(target,record)
    new.append(record)
records=[]
for run in ('S_E1_k1_s0_3M','S_E1_k2_s0_3M','S_E1_k5_s0_3M',
            'S_subset_T5_s0_9M','S_subset_T6_s0_9M'):
    path=R/'results/s_recipe'/(run+'_initial_hardware.json')
    if path.exists():
        records.append(read(path))
lines=['# S补充运行：真实首1000步','',
    '只转录每条实际训练的首1000次更新，不另测速；均由共同seed0随机初始化新起、按各自完整预算训练。', '',
    '| 运行 | 节点/卡 | 样本/秒 | 整卡点均功耗W | 功耗点数 |',
    '| --- | --- | ---: | ---: | ---: |']
for value in records:
    lines.append('| '+value['run']+' | '+value['node']+' / '+value['gpu_name']+' | '+
        format(value['first1000']['samples_per_second'],'.6f')+' | '+
        format(value['whole_card_power_sample_mean_watts'],'.6f')+' | '+str(value['power_records'])+' |')
lines += ['', '保持B32/micro32、FP32、TF32关闭、不累积、不重算；每条训练自身60k–150k窗口的p99裁剪，不借用其他运行阈值。E1只改允许构象前缀，固定VAL5000和11-07归一化不改。', '',
    '原生训练的PID/start_ticks与同任务Slurm接管待机分别记录；待机排队不是已分配计算成本。原生入口保持真实48h截止、900秒收尾及完整状态接管。', '',
    '不同卡/配方的整卡功耗点均值不能作同卡提速或整段能耗因果比较。这里没有预训练3M/9M完成或下游胜负结论；原值及来源路径见results/s_recipe/*initial_hardware.json。', '']
(R/'docs/s_recipe/EXTENSION_STARTUP.md').write_text('\n'.join(lines))
state=read(C/'current_state.json')
state.setdefault('extension_first1000',{}).update({row['run']:row for row in new})
state['next']='Continue actual active E1 native producers and same-run standbys, never duplicate/migrate live training. Close full-budget producers before formal GPU readout and native CPU statistics. Fill a compliant GPU with B0/G1 fullFT first; E1 before T5/T6. Short CPU uses native SSH with actual idle/core leases, no standalone queued CPU job. Original9M results are published93a74b93; final R3 LOSS at9M does not reopen the frozen3M S-R1. Complete ALL original plus A/B/C work, then final report, one full regression/repository check and unmerged PR.'
state['unpublished_changes']=sorted(set(state.get('unpublished_changes',[])+[
    'tools/s_recipe/cpu_native_20261126.py','tools/s_recipe/finetune_statistics_extension_20261124.py',
    'docs/s_recipe/EXTENSION_STARTUP.md']+['results/s_recipe/'+row['run']+'_initial_hardware.json' for row in new]))
write(C/'current_state.json',state)
print(json.dumps(dict(new_first1000=[dict(run=row['run'],samples_per_second=row['first1000']['samples_per_second'],
    mean_card_power_watts=row['whole_card_power_sample_mean_watts'],power_records=row['power_records']) for row in new])),flush=True)
