"""Stage actual 100k training reports from explicit executed development plans."""
import argparse,json,csv,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis');REPO=ROOT/'MFM_model_v3'
CONTROL=ROOT/'runs/model_v31_20261105'
import importlib.util
spec=importlib.util.spec_from_file_location('existing_actual_metadata_guard',REPO/'tools/model_v3/v2_diagnosis_disk.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
guard.m.require_capacity(guard.m.filesystem_status(REPO),4*1024**2,100)
guard.m.quota_headroom(guard.CONTROL/'share_quota_available_v3.json','/share',67108864,guard.remaining_nfs_other())
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--plan', action='append', help='Actual submitted run plan; repeat for multiple stages')
parser.add_argument('--page', default='docs/model_v3/V3_TRAINING_PROGRESS.md')
parser.add_argument('--pending', default=str(CONTROL/'MODEL_V3_latent_point_publication_pending.json'))
args=parser.parse_args()
plan_paths=args.plan or [str(CONTROL/'LATENT_V3_20261111/plan.json')]
runs={}
for path in plan_paths:
    for run in json.loads(Path(path).read_text())['runs']:
        runs.setdefault(run['job'], run)
cursor=json.loads((CONTROL/'M3_wandb_github_published.json').read_text())
published=set(cursor['published_keys']);entries=[];keys=[];table=[]
for run in runs.values():
    run=dict(run)
    root=Path(run['output']);history=root/'offline_wandb'/str(run['job'])
    configuration_path=root/'configuration.json'
    if not configuration_path.exists():
        configuration_path=Path(run['configuration'])
    configuration=json.loads(configuration_path.read_text())
    run['stage']=str(run.get('stage', configuration['stage']))
    run['arm']=str(run.get('arm', configuration.get('arm', configuration.get('candidate', root.name))))
    run['condition']=str(run.get('condition', configuration['condition']))
    windows=[]
    logfile=history/'training_history.jsonl'
    if logfile.exists():
        with logfile.open() as f:
            for line in f:
                if not line.endswith('\n'):continue
                row=json.loads(line)
                if 'loss_mean_1000_updates' in row:
                    windows.append((row['updates'],row['loss_mean_1000_updates']))
    for snapshot in sorted((history/'snapshots').glob('*.json')):
        point=json.loads(snapshot.read_text());key=str(run['job'])+':'+str(point['boundary_samples'])
        if key in published:continue
        recent=[(step,mean) for step,mean in windows if step<=point['metrics']['updates']]
        if recent:
            point['metrics']['loss_mean_1000_updates']=recent[-1][1]
            point['metrics']['loss_mean_window_end_update']=recent[-1][0]
        point.update(schema='MODEL_V3_TRAINING_WANDB_100K_V1',job=run['job'],stage=run['stage'],
            arm=run['arm'],condition=run['condition'],node=run['node'],gpu_uuid=run['gpu'],
            effective_batch_size=configuration['batch_size'],
            original_checkpoint_samples=int(point['metrics'].get('cumulative_samples', point['metrics']['samples']))-int(point['metrics']['samples']),
            scientific_sample_budget=configuration['samples'],
            actual_configuration_path=str(configuration_path),
            sample_clock='stage_relative_plus_explicit_base' if 'cumulative_samples' in point['metrics'] else 'absolute_samples_from_initialization',
            raw_sdk_directory=str(history),system_statistics_interval_seconds=30,
            SDK_source_revision_is_authoritative=True,weights_uploaded=False)
        relative='results/model_v3_wandb/points/'+str(run['job'])+'/'+str(point['boundary_samples'])+'.json'
        target=REPO/relative
        if target.exists():
            if json.loads(target.read_text())!=point:raise RuntimeError('Retain different previously staged point')
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(point,indent=2)+'\n')
        entries.append(dict(path=relative,mode='100644',type='blob',content=target.read_text()));keys.append(key)
    row=None
    csvfile=root/'losses.csv'
    if csvfile.exists():
        with csvfile.open() as f:
            for item in csv.DictReader(f):
                if item.get('gpu_peak_bytes') is not None:row=item
    table.append((run,row))
lines=['# \u6a21\u578b\u7ebfv3\u8bad\u7ec3\u8fdb\u5ea6','',
 '\u66f4\u65b0\u65f6\u95f4\uff1a'+time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime())+'\u3002\u6bcf100000\u9636\u6bb5\u6837\u672c\u4fdd\u5b58\u62a5\u544a\uff0c\u6839\u534f\u8c03\u5668\u6bcf1800\u79d2\u6279\u91cf\u63a8\u9001\u6240\u6709\u65b0\u8fb9\u754c\uff1b\u9636\u6bb5\u6837\u672c\u4e0e\u539f6M\u7d2f\u8ba1\u6837\u672c\u5206\u522b\u4fdd\u7559\u3002','',
 'C1-0已按v2选定。此页仅报告实际提交计划中的开发训练；潜变量采用、模型/配方冻结及B*均以对应完整结果为准。','',
 '| \u5c42/\u7ec4 | \u6761\u4ef6 | \u8bad\u7ec3\u4f5c\u4e1a | \u5df2\u8bad\u7ec3\u9636\u6bb5\u6837\u672c | \u6700\u65b0\u635f\u5931 | \u663e\u5b58\u5cf0\u503cGiB |','| --- | --- | ---: | ---: | ---: | ---: |']
for run,row in table:
    sample=row['samples'] if row else '\u5f85\u8fd0\u884c'
    loss=('{:.6f}'.format(float(row['total']))) if row else '\u2014'
    peak=row.get('gpu_peak_bytes') if row else None
    memory=('{:.3f}'.format(int(peak)/1024**3)) if peak not in (None, '', 'None') else '\u2014'
    lines.append('| '+run['stage']+'/'+run['arm']+' | '+run['condition']+' | '+str(run['job'])+' | '+sample+' | '+loss+' | '+memory+' |')
lines+=['','\u9010\u66f4\u65b0\u635f\u5931\u3001\u6bcf1000\u66f4\u65b0\u5747\u503c\u3001preclip\u68af\u5ea6\u3001\u5b66\u4e60\u7387\u3001\u9636\u6bb5/\u7d2f\u8ba1\u6837\u672c\u4e0e\u663e\u5b58\u5cf0\u503c\u4fdd\u7559\u5728\u771f\u5b9e\u79bb\u7ebfSDK\u548cJSONL\u4e2d\uff1bSDK\u539f\u751f\u7cfb\u7edf\u6307\u6807\u6bcf30\u79d2\u91c7\u6837\u3002\u6bcf\u4e2a10\u4e07\u8fb9\u754c\u7684\u539f\u59cb\u6307\u6807\u89c1results/model_v3_wandb/points/<\u4f5c\u4e1a>/<\u8fb9\u754c>.json\uff0c\u539f\u59cbSDK\u5173\u95ed\u540e\u5b8c\u6574\u5f52\u6863\u3002\u4e0d\u540cGPU\u539f\u59cb\u8017\u65f6\u4e0d\u7528\u4e8e\u9009\u62e9\u3002','',
 '报告来源计划：'+', '.join(plan_paths)+'。实际资源与队列状态见日报；此工具不查询、提交或恢复作业。','']
relative=args.page
(REPO/relative).write_text('\n'.join(lines))
entries.append(dict(path=relative,mode='100644',type='blob',content=(REPO/relative).read_text()))
pending=dict(expected_github_head=cursor['github_commit'],base_tree=cursor['github_tree'],
    entries=entries,keys=keys,paths=[e['path'] for e in entries],status='NEW_POINT_REPORTS_STAGED')
Path(args.pending).write_text(json.dumps(pending,indent=2)+'\n')
print('MODEL_V3_POINTS_JSON_BEGIN')
import base64
payload=base64.b64encode(json.dumps(pending,ensure_ascii=True,separators=(',',':')).encode()).decode()
for start in range(0,len(payload),64):print('V3PB:'+payload[start:start+64])
print('MODEL_V3_POINTS_JSON_END',flush=True)

