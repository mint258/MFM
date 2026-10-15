"""Archive closed Phase1 W&B records; metadata only, never run a model."""
import argparse
import csv
import fcntl
import hashlib
import html
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

BASE = Path('/share/home/zixiao/descriptor_analysis')
FORMAL = BASE / 'runs/phase1_full_corpus'
ARCH = FORMAL / 'wandb_archive'
EV = BASE / 'docs/phase1/evidence'
TZ = timezone(timedelta(hours=8))
UID = 1278
TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def stamp():
    return datetime.now(TZ).isoformat(timespec='seconds')


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode())


def atomic_bytes(path, raw):
    temp = path.with_name(path.name + '.pending')
    with temp.open('wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def owned(path, directory=False):
    info = path.lstat()
    need(info.st_uid == UID and not stat.S_ISLNK(info.st_mode), 'Owner or symlink differs: ' + str(path))
    need(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
         'Physical owned object required: ' + str(path))
    return info


def checked_file(path, root):
    need(path.is_relative_to(root), 'File leaves declared own output')
    owned(root, True)
    current = root
    for part in path.relative_to(root).parts[:-1]:
        current /= part
        owned(current, True)
    info = owned(path)
    need(info.st_size <= 128 << 20, 'Bounded individual W&B file required')
    return info


def source_manifest(run):
    phase = run.parent.parent
    entries = []
    for path in sorted(run.rglob('*')):
        info = path.lstat()
        need(info.st_uid == UID, 'Archive source UID differs')
        if stat.S_ISDIR(info.st_mode):
            continue
        relative = path.relative_to(run).as_posix()
        target, pointer = path, None
        if stat.S_ISLNK(info.st_mode):
            need(relative == 'logs/debug-core.log', 'Unrecognized SDK link layout')
            pointer = os.readlink(path)
            target = Path(os.path.abspath(os.path.join(str(path.parent), pointer)))
            need(target.parent == phase / 'cache/wandb/logs' and re.fullmatch(r'core-debug-\d{8}_\d{6}\.log', target.name),
                 'Unrecognized SDK core log target')
        checked_file(target, phase)
        raw = target.read_bytes()
        entries.append({'relative_path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                        'read_path': str(target), 'source_link_text': pointer})
    need(sum(e['bytes'] for e in entries) <= 192 << 20 and len(entries) <= 4096, 'Bounded run inventory required')
    return entries


def command(argv):
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45)
    need(result.returncode == 0, 'Metadata command failed: ' + argv[0] + ': ' + result.stderr[:200])
    return result.stdout


def phase_census():
    inventory = EV / 'stage60_root_disjoint_phase_storage_inventory_v1.py'
    spec = importlib.util.spec_from_file_location('wandb_archive_inventory', inventory)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    roots = [FORMAL] + sorted(p for p in EV.iterdir() if p.is_dir() and p.name.startswith(('stage59_', 'stage60_')))
    roots.append(EV / 'stage58_gpu_readout_cost_runs')
    for attempt in range(3):
        try:
            total = module.physical_forest_bytes(roots)['actual_bytes']
            return total + sum(p.lstat().st_size for p in EV.iterdir() if p.is_file() and not p.is_symlink())
        except FileNotFoundError:
            if attempt == 2:
                raise


def reserve(copy_bytes, active_project_jobs):
    # Reserve raw copy, CSV/HTML generation and atomic replacement peak conservatively.
    extra = 4 * copy_bytes + (16 << 20)
    existing = sum(p.lstat().st_size for p in ARCH.rglob('*') if p.is_file() and not p.is_symlink())
    need(existing + extra <= 2 << 30, 'W&B archive 2 GiB bound reached')
    need(phase_census() + extra + active_project_jobs * (2 << 30) <= 104 << 30, 'Whole-phase output reserve exhausted')
    quota = command(['quota', '-v', '-u', 'zixiao'])
    matches = []
    for line in quota.splitlines():
        fields = line.split()
        if fields and fields[0] == '/dev/sda1':
            values = [int(value.rstrip('*')) for value in fields[1:4]]
            limits = [value for value in values[1:] if value > 0]
            need(limits, 'No finite user quota observed')
            matches.append((min(limits) - values[0]) * 1024)
    need(len(matches) == 1 and matches[0] >= (32 << 30) + extra + active_project_jobs * (2 << 30), 'Actual user quota reserve exhausted')
    return {'actual_free_bytes': matches[0], 'actual_phase_bytes_before': phase_census(), 'additional_peak_reserved_bytes': extra}


def export_history(sdk_file, out, expected_failed):
    from wandb.proto import wandb_internal_pb2
    from wandb.sdk.internal.datastore import DataStore
    catalog_path = EV / 'stage57_node20_learning_continuation_v1/source_numeric_types.py'
    need(hashlib.sha256(catalog_path.read_bytes()).hexdigest() == '222b9b0edfdeb2a270e764f64c7aa64c181bcd6b3f953e440bf87f0d07a3ffd4d', 'Source numeric catalog changed')
    spec = importlib.util.spec_from_file_location('archive_source_numeric_types', catalog_path)
    catalog = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(catalog)
    data = DataStore()
    data.open_for_scan(str(sdk_file))
    rows, verified, decode_error = [], 0, None
    try:
        for ordinal in range(50000):
            raw = data.scan_data()
            if raw is None:
                break
            record = wandb_internal_pb2.Record()
            record.ParseFromString(raw)
            if not record.HasField('history') or not record.history.item:
                continue
            row = {}
            for item in record.history.item:
                key = item.key or '/'.join(item.nested_key)
                need(key not in row, 'Duplicate SDK history key')
                row[key] = json.loads(item.value_json)
            scientific = {k: v for k, v in row.items() if not k.startswith('_')}
            seal = scientific.pop('tracking/payload_sha256', None)
            if seal:
                typed, _ = catalog.restore_original_numeric_types(scientific)
                need(catalog.canonical_sha256(typed) == seal, 'Source-typed archived history seal mismatch')
                row.update(typed)
                verified += 1
            rows.append(row)
        else:
            raise ValueError('Bounded metadata scan exceeded 50000 SDK records')
    except (AssertionError, EOFError, OSError) as error:
        need(expected_failed, 'Unexpected SDK decode failure on a successful segment')
        decode_error = type(error).__name__ + ': ' + str(error)[:200]
    finally:
        data.close()
    keys = sorted({key for row in rows for key in row})
    with (out / 'metrics.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, allow_nan=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    latest = {}
    for row in rows:
        latest.update({k: v for k, v in row.items() if v is not None and not k.startswith('_')})
    atomic_json(out / 'last_metrics.json', latest)
    charts = []
    candidates = [k for k in keys if k.startswith(('train/', 'val/', 'validation/')) and any(word in k.lower() for word in ('loss', 'total', 'criterion', 'mae', 'weight'))]
    for key in candidates[:18]:
        points = [(row.get('_step', i), row[key]) for i, row in enumerate(rows)
                  if type(row.get(key)) in (float, int) and math.isfinite(row[key])]
        if len(points) < 2:
            continue
        xmin, xmax = min(x for x, y in points), max(x for x, y in points)
        ymin, ymax = min(y for x, y in points), max(y for x, y in points)
        stride = max(1, len(points) // 800)
        coords = ' '.join(f'{50+650*(x-xmin)/max(1,xmax-xmin):.2f},{210-170*(y-ymin)/(ymax-ymin or 1):.2f}' for x, y in points[::stride])
        charts.append('<section><h3>' + html.escape(key) + '</h3><svg viewBox="0 0 730 245" role="img">'
                      '<path d="M50 30V210H710" fill="none" stroke="#aaa"/>'
                      f'<polyline points="{coords}" fill="none" stroke="#2563eb" stroke-width="1.5"/>'
                      f'<text x="3" y="40">{ymax:.4g}</text><text x="3" y="210">{ymin:.4g}</text>'
                      f'<text x="50" y="233">{xmin}</text><text x="620" y="233">{xmax} W&amp;B step</text></svg></section>')
    table = ''.join('<tr><td>' + html.escape(k) + '</td><td>' + html.escape(str(v)) + '</td></tr>' for k, v in sorted(latest.items()))
    page = ('<!doctype html><meta charset="utf-8"><title>训练指标</title><style>body{font:16px system-ui;margin:32px;max-width:1100px}td,th{padding:8px;border-bottom:1px solid #ddd}svg{max-width:730px;width:100%}section{border:1px solid #ddd;margin:16px 0;padding:12px}</style>'
            '<a href="../../index.html">返回全部训练记录</a><h1>' + html.escape(out.parent.name + ' / ' + out.name) + '</h1>'
            '<p>离线记录，尚未同步到W&amp;B网页。失败段可能含未写入恢复检查点的尾部更新；最后一行不是可恢复进度。</p>'
            '<p><a href="metrics.csv">全部指标 CSV</a> · <a href="last_metrics.json">最近记录 JSON</a> · <a href="manifest.json">归档清单</a></p>'
            + ''.join(charts) + '<h2>各指标最后一次记录</h2><table><tr><th>指标</th><th>最后记录值</th></tr>' + table + '</table>')
    atomic_bytes(out / 'index.html', page.encode())
    return {'history_rows': len(rows), 'source_typed_payloads_verified': verified, 'sdk_decode_error': decode_error, 'raw_records_preserved': True}


def archive_run(run, info, active_count):
    date, clock, run_id = re.fullmatch(r'offline-run-(\d{8})_(\d{6})-([a-z0-9]+)', run.name).groups()
    condition = info['condition']
    label = info['training_status']
    name = f'{date}_{clock}_job{info["job_id"]}_{label}_{run_id}'
    parent = ARCH / condition
    parent.mkdir(mode=0o700, exist_ok=True)
    owned(parent, True)
    destination = parent / name
    if destination.exists():
        manifest = json.loads((destination / 'manifest.json').read_text())
        need(manifest['source_run'] == str(run) and manifest['run_id'] == run_id, 'Archive identity collision')
        return {'archive_relative_path': destination.relative_to(ARCH).as_posix(), 'run_id': run_id, 'already_archived': True, **info}
    before = source_manifest(run)
    budget = reserve(sum(e['bytes'] for e in before), active_count)
    pending = parent / ('.' + name + '.pending')
    need(not pending.exists(), 'Retained incomplete archive requires review: ' + str(pending))
    pending.mkdir(mode=0o700)
    sdk_root = pending / 'wandb' / run.name
    sdk_root.mkdir(parents=True)
    for entry in before:
        target = sdk_root / entry['relative_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = Path(entry['read_path']).read_bytes()
        need(len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256'], 'Source changed while copying')
        with target.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    phase = run.parent.parent
    journal = phase / 'tracking_journal.jsonl'
    if journal.exists():
        checked_file(journal, phase)
        raw = journal.read_bytes()
        need(len(raw) <= 16 << 20, 'Bounded journal copy required')
        (pending / 'tracking_journal.jsonl').write_bytes(raw)
    sdk_files = list(sdk_root.glob('run-*.wandb'))
    need(len(sdk_files) == 1 and sdk_files[0].name == 'run-' + run_id + '.wandb', 'One matching raw W&B SDK file required')
    exports = export_history(sdk_files[0], pending, info['slurm_state'] != 'COMPLETED')
    need(source_manifest(run) == before, 'Source files changed before archive publication')
    for entry in before:
        copied = sdk_root / entry['relative_path']
        need(hashlib.sha256(copied.read_bytes()).hexdigest() == entry['sha256'], 'Copied raw archive SHA differs')
    manifest = {'schema_version': 'phase1_wandb_readable_archive_v1', 'archived_at_Asia_Shanghai': stamp(),
                'source_run': str(run), 'run_id': run_id, 'source_files': before, 'budget': budget, 'exports': exports,
                'original_files_preserved': True, 'offline_unsynced': True, 'copied_log_links_are_physical_files': True, **info}
    atomic_json(pending / 'manifest.json', manifest)
    need(sum(p.lstat().st_size for p in pending.rglob('*') if p.is_file()) <= budget['additional_peak_reserved_bytes'], 'Archive peak reserve exceeded')
    os.rename(pending, destination)
    return {'archive_relative_path': destination.relative_to(ARCH).as_posix(), 'run_id': run_id, 'already_archived': False, **info}


def scan(expires_at):
    candidates = []
    for run in FORMAL.glob('*/*/*/segment_*/actual_child/*/wandb/offline-run-*'):
        parts = run.relative_to(FORMAL).parts
        if len(parts) == 8 and re.fullmatch('[0-9a-f]{64}', parts[0]) and re.fullmatch(r'segment_[0-9]+', parts[3]):
            owned(run, True)
            candidates.append((run, parts))
    need(len(candidates) <= 2048, 'Bounded Phase1 archive discovery required')
    ids = sorted({parts[3].split('_')[1] for run, parts in candidates})
    queue_raw = command(['squeue', '--noheader', '--user=zixiao', '--format=%i|%j|%T'])
    queue = {row[0]: row for line in queue_raw.splitlines() if (row := line.split('|')) and len(row) == 3}
    accounting_raw = command(['sacct', '--noheader', '--parsable2', '--jobs=' + ','.join(ids), '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw']) if ids else ''
    accounting = {row[0]: row for line in accounting_raw.splitlines() if (row := line.split('|')) and len(row) == 5 and row[0] in ids}
    active_count = sum(row[1].startswith(('p1full_', 'p1-')) for row in queue.values())
    records, errors = [], []
    for run, parts in sorted(candidates, key=lambda pair: pair[0].name, reverse=True):
        job = parts[3].split('_')[1]
        row = accounting.get(job)
        info = {'job_id': job, 'condition': parts[2], 'strategy': parts[1], 'protocol_sha256': parts[0],
                'source_relative_path': run.relative_to(FORMAL).as_posix(), 'source_run': str(run), 'offline_unsynced': True}
        if job in queue:
            records.append({'training_status': queue[job][2], 'archival_status': 'WAITING_FOR_JOB_END', 'run_id': run.name.rsplit('-', 1)[1], **info})
            continue
        if row is None or row[1] != 'zixiao' or row[2].split(' ')[0] not in TERMINAL:
            records.append({'training_status': 'UNVERIFIED', 'archival_status': 'WAITING_FOR_TERMINAL_ACCOUNTING', **info})
            continue
        info.update(slurm_state=row[2], exit_code=row[3], elapsed_seconds=int(row[4]))
        info['training_status'] = 'PARTIAL' if row[2] == 'COMPLETED' else row[2].split(' ')[0]
        guard = run.parents[3].with_name('segment_' + job + '.guard')
        receipt = guard / 'segment_receipt.json'
        if receipt.exists():
            actual = json.loads(receipt.read_text()).get('actual_result', {})
            if actual.get('status') == 'complete' and actual.get('counters', {}).get('consumed_base_exposures') == 47129667:
                info['training_status'] = 'FINAL'
        try:
            records.append({'archival_status': 'ARCHIVED', **archive_run(run, info, active_count)})
        except Exception as error:
            record = {'archival_status': 'ARCHIVE_PENDING', 'error': type(error).__name__ + ': ' + str(error)[:300], **info}
            records.append(record)
            errors.append(record)
    summary = {'schema_version': 'phase1_wandb_archive_index_v1', 'updated_at_Asia_Shanghai': stamp(), 'watcher_expires_unix_seconds': expires_at,
               'archive_root': str(ARCH), 'offline_unsynced': True, 'records': records, 'errors': errors,
               'closed_archives': sum(r['archival_status'] == 'ARCHIVED' for r in records),
               'active_runs': sum(r['archival_status'] == 'WAITING_FOR_JOB_END' for r in records),
               'actual_queue': queue_raw, 'actual_accounting': accounting_raw, 'original_scientific_results_unchanged': True}
    atomic_json(ARCH / 'index.json', summary)
    rows = []
    for r in records:
        relative = r.get('archive_relative_path')
        link = '<a href="' + html.escape(relative + '/index.html', quote=True) + '">查看指标与曲线</a>' if relative else '<a href="../' + html.escape(r['source_relative_path'], quote=True) + '">原始运行目录</a>'
        rows.append('<tr>' + ''.join('<td>' + html.escape(str(r.get(k, ''))) + '</td>' for k in ('condition', 'strategy', 'job_id', 'run_id', 'training_status', 'archival_status')) + '<td>' + link + '</td></tr>')
    end = datetime.fromtimestamp(expires_at, TZ).isoformat(timespec='seconds') if expires_at else '手动收尾调用'
    page = ('<!doctype html><meta charset="utf-8"><title>Phase1 W&B 训练记录</title><style>body{font:16px system-ui;margin:32px;max-width:1500px}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}a{color:#2563eb}</style>'
            '<h1>Phase1 W&amp;B 训练记录</h1><p>最近刷新：' + stamp() + '（Asia/Shanghai）；自动归档监视到期：' + end + '</p>'
            '<p>记录仍为 offline，尚未同步到W&amp;B网页。PARTIAL表示一个正常结束的分段；FAILED保留故障历史；FINAL才表示完整三轮结束。运行中的记录将在作业结束后归档。</p>'
            '<table><tr><th>模型 / seed</th><th>策略</th><th>作业</th><th>W&amp;B run</th><th>训练状态</th><th>归档状态</th><th>阅读入口</th></tr>' + ''.join(rows) + '</table><p><a href="index.json">完整索引 JSON</a></p>')
    atomic_bytes(ARCH / 'index.html', page.encode())
    launcher = '<!doctype html><meta charset="utf-8"><title>W&B 训练记录</title><h1>W&amp;B 训练记录</h1><p><a href="runs/phase1_full_corpus/wandb_archive/index.html">打开全部训练记录、指标表和曲线</a></p>'
    atomic_bytes(BASE / 'W&B_训练记录.html', launcher.encode())
    print(json.dumps({'closed_archives': summary['closed_archives'], 'active_runs': summary['active_runs'], 'archive_errors': len(errors), 'updated_at': stamp()}, ensure_ascii=False), flush=True)
    return len(errors)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch-seconds', type=int, default=0)
    args = parser.parse_args()
    need(os.getuid() == UID and socket.gethostname().split('.')[0] == 'sonmi', 'Own sonmi metadata operation only')
    need(0 <= args.watch_seconds <= 86400, 'Archive watcher bounded to at most 24 hours')
    ARCH.mkdir(mode=0o700, exist_ok=True)
    owned(ARCH, True)
    mutex = os.open(ARCH / '.archive.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    expires = time.time() + args.watch_seconds if args.watch_seconds else None
    errors = 0
    try:
        while True:
            try:
                fcntl.flock(mutex, fcntl.LOCK_EX | fcntl.LOCK_NB)
                errors = scan(expires)
            except BlockingIOError:
                if not args.watch_seconds:
                    raise
            except Exception as error:
                atomic_json(ARCH / 'last_archive_error.json', {'at': stamp(), 'error': type(error).__name__ + ': ' + str(error)[:500]})
                print('ARCHIVE_METADATA_ERROR ' + type(error).__name__ + ': ' + str(error)[:500], flush=True)
                errors = 1
            finally:
                fcntl.flock(mutex, fcntl.LOCK_UN)
            if not expires or time.time() >= expires:
                break
            time.sleep(min(60, max(0, expires - time.time())))
    finally:
        os.close(mutex)
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
