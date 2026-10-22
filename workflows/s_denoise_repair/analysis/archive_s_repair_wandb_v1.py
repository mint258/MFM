"""Bounded S-repair W&B metadata archive, sharing the established archive lock."""
import argparse
from datetime import datetime,timezone,timedelta
import fcntl
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import time

PROJECT=Path('/share/home/zixiao/descriptor_analysis')
ROOT=PROJECT/'runs/s_denoise_repair_20261016'
ARCH=PROJECT/'runs/phase1_full_corpus/wandb_archive'
TZ=timezone(timedelta(hours=8))
TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}
INDEX='s_denoise_repair_20261016_index'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def query(argv):return subprocess.check_output(argv,stdin=subprocess.DEVNULL,text=True,timeout=60)


def inventory(run,helper):
    helper.owned(run,True)
    entries=[];pointers=[]
    for path in sorted(run.rglob('*')):
        info=path.lstat();assert info.st_uid==1278
        if stat.S_ISDIR(info.st_mode):continue
        relative=path.relative_to(run).as_posix()
        if stat.S_ISLNK(info.st_mode):
            # External global SDK cache is outside this task's ownership scope.
            # Preserve pointer text, never copy arbitrary external log bytes.
            assert relative=='logs/debug-core.log','Unrecognized SDK link layout'
            pointers.append(dict(relative_path=relative,source_link_text=os.readlink(path),
                copied=False,reason='External SDK cache target is outside owned task phase; pointer preserved without dereferencing'))
            continue
        helper.checked_file(path,ROOT)
        entries.append(dict(relative_path=relative,read_path=str(path),bytes=info.st_size,sha256=sha(path)))
    assert len(entries)<=4096 and sum(e['bytes'] for e in entries)<=192<<20
    return entries,pointers


def add_metric_curves(destination,helper):
    import csv,math
    rows=list(csv.DictReader((destination/'metrics.csv').open()))
    keys=list(rows[0]) if rows else []
    metrics=[k for k in keys if not k.startswith('_') and any(t in k.lower() for t in ['loss','rmse','mse','accuracy','nll','gradient_norm','records_per_second'])]
    figures=[]
    for key in metrics[:18]:
        points=[]
        for i,row in enumerate(rows):
            try:x=float(row.get('_step',i));y=float(row[key])
            except (ValueError,TypeError):continue
            if math.isfinite(x) and math.isfinite(y):points.append((x,y))
        if len(points)<2:continue
        xmin,xmax=min(x for x,y in points),max(x for x,y in points)
        ymin,ymax=min(y for x,y in points),max(y for x,y in points)
        coords=' '.join(f'{50+650*(x-xmin)/max(1.,xmax-xmin):.2f},{210-170*(y-ymin)/(ymax-ymin or 1):.2f}' for x,y in points[::max(1,len(points)//800)])
        figures.append('<section><h3>'+html.escape(key)+'</h3><svg viewBox="0 0 730 245" role="img"><path d="M50 30V210H710" fill="none" stroke="#aaa"/>'
            +f'<polyline points="{coords}" fill="none" stroke="#2563eb" stroke-width="1.5"/><text x="2" y="35">{ymax:.5g}</text><text x="2" y="210">{ymin:.5g}</text>'
            +f'<text x="50" y="235">{xmin:g}</text><text x="620" y="235">{xmax:g} SDK step</text></svg></section>')
    page='<!doctype html><meta charset="utf-8"><title>S去噪修复指标</title><style>body{font:16px system-ui;margin:32px;max-width:1100px}svg{max-width:730px}section{border:1px solid #ddd;padding:12px;margin:16px 0}</style>'
    page+='<p><a href="../../'+INDEX+'.html">返回S去噪修复记录</a></p><h1>'+html.escape(destination.name.strip('.'))+'</h1>'
    page+='<p>记录仍为offline，未同步到W&B网页。归档不表示科学门槛通过；取消/失败段的日志尾部不能视为已提交的恢复进度。外部debug-core日志仅保留链接文本。</p>'
    page+='<p><a href="metrics.csv">全部指标CSV</a> · <a href="last_metrics.json">最近记录</a> · <a href="manifest.json">清单与实际作业状态</a></p>'+''.join(figures)
    helper.atomic_bytes(destination/'index.html',page.encode())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--receipt',type=Path,required=True);args=parser.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert args.receipt.is_absolute() and args.receipt.is_relative_to(ROOT/'reports') and not args.receipt.exists()
    helper_path=PROJECT/'scripts/archive_phase1_wandb_v2.py'
    assert sha(helper_path)=='3fbd821e85fe093e037c4b45e6bf666d08533eb07edaabf0435d5b8b1e88f975a'
    spec=importlib.util.spec_from_file_location('established_archive_v2',helper_path)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    ARCH.mkdir(exist_ok=True);helper.owned(ARCH,True)
    lock=os.open(ARCH/'.archive.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        candidates=list((ROOT/'diagnostics').glob('*/job_*/wandb/offline-run-*'))
        candidates+=list((ROOT/'s_training').glob('*/segment_*/wandb/offline-run-*'))
        candidates+=list((ROOT/'probe_results_v3').glob('*/wandb/offline-run-*'))
        assert len(candidates)<=2048
        queue_raw=query(['squeue','-h','-u','zixiao','-o','%i|%j|%T'])
        active={line.split('|')[0] for line in queue_raw.splitlines()}
        entries=[]
        for run in sorted(candidates):
            job=next((p.name.split('_')[1] for p in run.parents if re.fullmatch(r'(?:job|segment)_\d+',p.name)),None)
            if job is None:
                endpoint=run.parents[1];receipt=endpoint/'receipt.json'
                if not receipt.exists():continue
                job=json.loads(receipt.read_text())['job_id']
            assert job.isdecimal()
            entries.append((run,job))
        ids=sorted({job for run,job in entries})
        raw=query(['sacct','-X','-j',','.join(ids),'-n','-P','-o','JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS']) if ids else ''
        parents={r[0]:r[1:] for r in (line.split('|') for line in raw.splitlines()) if r[0] in ids}
        results=[];errors=[]
        for run,job in entries:
            basic=dict(source_run=str(run),job_id=job,run_id=run.name.rsplit('-',1)[1])
            parent=parents.get(job)
            if job in active or parent is None or parent[1].split()[0] not in TERMINAL:
                results.append({**basic,'archival_status':'WAITING_FOR_JOB_END','actual_parent':parent});continue
            assert parent[0]=='zixiao'
            parent_state=parent[1].split()[0]
            condition=run.parents[2].name
            if re.fullmatch('segment_\d+',condition):condition=run.parents[3].name
            if condition in ['diagnostics','probe_results_v3']:condition=run.parents[1].name
            if '_seed' not in condition:condition+='_seedNA'
            model='S_denoise_repair_v3_'+re.sub('[^A-Za-z0-9_.-]','_',condition)
            date,clock,run_id=re.fullmatch(r'offline-run-(\d{8})_(\d{6})-([a-z0-9]+)',run.name).groups()
            label=parent_state if parent_state!='COMPLETED' or parent[2]!='0:0' else 'CLOSED_SCIENTIFIC_STATUS_SEPARATE'
            destination=ARCH/model/(date+'_'+clock+'_job'+job+'_'+label+'_'+run_id)
            try:
                if destination.exists():
                    manifest=json.loads((destination/'manifest.json').read_text())
                    assert manifest['source_run']==str(run) and manifest['run_id']==run_id
                    for item in manifest['source_files']:assert sha(destination/'wandb'/run.name/item['relative_path'])==item['sha256']
                    results.append({**basic,'archival_status':'ARCHIVED','archive_relative_path':destination.relative_to(ARCH).as_posix(),'actual_parent':parent});continue
                source,pointers=inventory(run,helper)
                journals=[]
                for path in run.parents[1].glob('*.jsonl'):
                    helper.checked_file(path,ROOT);journals.append(dict(path=str(path),name=path.name,sha256=sha(path),bytes=path.stat().st_size))
                budget=helper.reserve(sum(e['bytes'] for e in source)+sum(j['bytes'] for j in journals),len(active))
                pending=destination.with_name('.'+destination.name+'.pending')
                assert not pending.exists(),'Existing partial archive needs explicit owned-byte review'
                pending.mkdir(parents=True,mode=0o700)
                for item in source:
                    target=pending/'wandb'/run.name/item['relative_path'];target.parent.mkdir(parents=True,exist_ok=True)
                    with target.open('xb') as stream:stream.write(Path(item['read_path']).read_bytes())
                    assert sha(target)==item['sha256']
                for item in journals:
                    target=pending/'journals'/item['name'];target.parent.mkdir(exist_ok=True)
                    with target.open('xb') as stream:stream.write(Path(item['path']).read_bytes())
                    assert sha(target)==item['sha256']
                sdk_files=list((pending/'wandb'/run.name).glob('run-*.wandb'));assert len(sdk_files)==1
                exported=helper.export_history(sdk_files[0],pending,parent_state!='COMPLETED' or parent[2]!='0:0')
                add_metric_curves(pending,helper)
                after,after_pointers=inventory(run,helper);assert after==source and after_pointers==pointers
                for item in journals:assert sha(item['path'])==item['sha256']
                manifest=dict(schema='S_DENOISE_REPAIR_ARCHIVE_V1',**basic,actual_parent=parent,source_files=source,
                    excluded_external_log_pointers=pointers,source_journals=journals,budget=budget,export=exported,
                    offline_unsynced=True,scientific_status='See immutable diagnostic/training result; archive is not scientific acceptance',
                    source_archive_program_sha256=sha(__file__),established_export_helper_sha256=sha(helper_path),
                    updated_at_Asia_Shanghai=datetime.now(TZ).isoformat(timespec='seconds'))
                helper.atomic_json(pending/'manifest.json',manifest)
                for path in pending.rglob('*'):
                    if path.is_file():helper.owned(path)
                pending.rename(destination)
                results.append({**basic,'archival_status':'ARCHIVED','archive_relative_path':destination.relative_to(ARCH).as_posix(),'actual_parent':parent})
            except Exception as exc:errors.append({**basic,'error':repr(exc)})
        document=dict(status='S_REPAIR_ARCHIVE_SCAN_COMPLETE' if not errors else 'S_REPAIR_ARCHIVE_ERRORS',records=results,errors=errors,
            actual_parent_raw=raw,actual_queue_raw=queue_raw,updated_at_Asia_Shanghai=datetime.now(TZ).isoformat(timespec='seconds'))
        helper.atomic_json(ARCH/(INDEX+'.json'),document)
        rows=[]
        for item in results:
            link=item.get('archive_relative_path')
            link='<a href="'+html.escape(link+'/index.html',quote=True)+'">指标与曲线</a>' if link else '运行中，等待闭合'
            rows.append('<tr><td>'+html.escape(item['job_id'])+'</td><td>'+html.escape(item['run_id'])+'</td><td>'+html.escape(str(item.get('actual_parent')))
                +'</td><td>'+html.escape(item['archival_status'])+'</td><td>'+link+'</td></tr>')
        page='<!doctype html><meta charset="utf-8"><title>S去噪修复 W&B记录</title><style>body{font:16px system-ui;margin:32px}td,th{padding:8px;border-bottom:1px solid #ddd}</style>'
        page+='<h1>S去噪修复 W&B记录</h1><p>刷新：'+document['updated_at_Asia_Shanghai']+'。offline未同步；归档不等于科学门槛通过。外部debug-core指针不解引用。</p>'
        page+='<table><tr><th>Slurm</th><th>SDK run</th><th>实际父状态</th><th>归档</th><th>阅读</th></tr>'+''.join(rows)+'</table>'
        page+='<p><a href="index.html">原Phase1记录</a> · <a href="'+INDEX+'.json">本任务完整索引</a></p>'
        helper.atomic_bytes(ARCH/(INDEX+'.html'),page.encode())
        launcher=PROJECT/'W&B_训练记录.html';previous=launcher.read_bytes()
        marker=b'data-s-denoise-repair-20261016'
        if marker not in previous:
            addition='<p data-s-denoise-repair-20261016><a href="runs/phase1_full_corpus/wandb_archive/'+INDEX+'.html">S去噪修复：离线训练记录、指标表和曲线</a></p>'
            assert launcher.read_bytes()==previous
            helper.atomic_bytes(launcher,previous+addition.encode())
        assert sha(helper_path)=='3fbd821e85fe093e037c4b45e6bf666d08533eb07edaabf0435d5b8b1e88f975a'
        helper.atomic_json(args.receipt,document)
        print(json.dumps(dict(status=document['status'],archived=sum(r['archival_status']=='ARCHIVED' for r in results),waiting=sum(r['archival_status']=='WAITING_FOR_JOB_END' for r in results),errors=errors)))
        if errors:raise SystemExit(1)
    finally:fcntl.flock(lock,fcntl.LOCK_UN);os.close(lock)


if __name__=='__main__':main()
