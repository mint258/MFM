"""Copy exact provisional D3 and reuse its Reader/16-process readback.

Call run(plan_path, host_context_path, check_host_resources=live_guard) from an
already admitted GPU validation parent, in process only. This module
does not allocate a GPU, train, issue a startup proof, or sign a Model ACK.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import csv
import hashlib
import io
import json
import multiprocessing as mp
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import time

REPO = Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository')
HERE = REPO/'workflows/data_v1_final/export/provisional_d3_local_readback_v1'
MODULE = 'workflows.data_v1_final.export.provisional_d3_local_readback_v1.run'
REPORT_RESERVE_BYTES = 128 << 20  # two bounded metadata reports, inside host cap


def need(value, reason):
    if not value:
        raise ValueError(reason)


def fingerprint(path):
    s = path.lstat()
    need(stat.S_ISREG(s.st_mode) and not path.is_symlink() and s.st_uid == 1278,
         'ACTUAL_MAIN_OWNED_REGULAR_FILE')
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_uid)


def ref(path, check=None):
    p = Path(path).absolute(); before = fingerprint(p); h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(4 << 20), b''):
            if check is not None: check()
            h.update(block)
    need(fingerprint(p) == before, 'FILE_CHANGED_DURING_READ')
    return {'path': str(p), 'bytes': before[2], 'sha256': h.hexdigest()}


def document(reference, limit=64 << 20):
    need(type(reference) is dict and set(reference) == {'path', 'bytes', 'sha256'}
         and 0 < reference['bytes'] <= limit, 'BOUNDED_EXACT_REFERENCE')
    need(ref(reference['path']) == reference, 'ACTUAL_METADATA_OR_SOURCE_SHA')
    return json.loads(Path(reference['path']).read_text())


def save(path, value):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    need(len(raw) <= 64 << 20, 'FINITE_IO_REPORT')
    with Path(path).open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return ref(path)


def query(argv):
    v = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    need(v.returncode == 0, 'ACTUAL_HOST_OBSERVATION_FAILED')
    return v.stdout


def host(plan, plan_ref, context_path):
    """Observe host resources; retain its original proof without relabelling it."""
    context_ref = ref(context_path); c = document(context_ref, 2 << 20)
    need(c['schema'] == 'ACTUAL_MODEL_GPU_PARENT_IO_CONTEXT_V1'
         and c['endpoint'] == '202.38.247.57:22'
         and c['host_purpose'] == 'AUTHORIZED_GPU_VALIDATION_OR_ACTUAL_D3_PAYLOAD'
         and c['io_plan_reference'] == plan_ref, 'ACTUAL_GPU_HOST_NOT_CPU_QUEUE_ALIAS')
    ticks = int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])
    need(os.getuid() == c['uid'] == 1278 and os.getpid() == c['pid']
         and c['process_start_ticks'] == ticks
         and Path('/proc/sys/kernel/random/boot_id').read_text().strip() == c['boot_id']
         and socket.gethostname().split('.')[0] == c['node']
         and os.environ.get('SLURM_JOB_ID') == str(c['job_id'])
         and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) >= 16
         and 0 <= time.monotonic() - c['observed_monotonic_seconds'] <= 120,
         'SAME_ACTUAL_GPU_PARENT_PID_BOOT_JOB_AND_CONTEXT')
    # Existing host proof/request remain the original documents. This I/O code
    # cannot upgrade an old CPU-only startup proof into GPU admission.
    proof = document(c['host_startup_proof_reference'], 2 << 20)
    document(c['host_request_reference'], 2 << 20)
    need(c['host_gpu_guard_already_admitted'] is True and proof.get('CPU_only') is not True
         and proof.get('schema') not in ('ACTUAL_D6_CPU_ONLY_DELIVERY_STARTUP_V1',
                                        'FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1')
         and proof.get('request', {}).get('kind') not in ('analysis', 'conformer', 'qm'),
         'ORIGINAL_GPU_HOST_GUARD_REQUIRED_NOT_NEW_CPU_PROOF')
    argv = Path('/proc/self/cmdline').read_bytes().split(b'\0')
    argv = [s.decode() for s in argv if s]
    argv_sha = hashlib.sha256(json.dumps(argv, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    need(c['host_full_argv_sha256'] == argv_sha, 'ACTUAL_HOST_FULL_ARGV_BOUND')
    visible = os.environ.get('CUDA_VISIBLE_DEVICES')
    need(visible == c['cuda_visible_devices'] and c['gpu_uuid'].startswith('GPU-'),
         'UNCHANGED_ACTUAL_HOST_GPU_VISIBILITY')
    if visible != c['gpu_uuid']:
        mapped = c['verified_visible_uuid_mapping']
        need(mapped['cuda_visible_devices'] == visible and mapped['gpu_uuid'] == c['gpu_uuid']
             and mapped['source_reference'] == c['gpu_binding_evidence_reference'],
             'EXISTING_GPU_GUARD_VERIFIED_NUMERIC_MAPPING_NOT_GUESSED_ZERO')
        document(c['gpu_binding_evidence_reference'], 2 << 20)
    inventory = query(['nvidia-smi', '--query-gpu=uuid,name', '--format=csv,noheader'])
    rows = list(csv.reader(io.StringIO(inventory)))
    need(any(len(r) == 2 and r[0].strip() == c['gpu_uuid']
             and r[1].strip() == c['gpu_name'] for r in rows), 'ACTUAL_PHYSICAL_HOST_GPU')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.slurm_format import fields
    raw = query(['scontrol', 'show', 'job', str(c['job_id']), '-o']); job = fields(raw)
    need(job['JobId'] == str(c['job_id']) and job['UserId'].endswith('(1278)')
         and job['JobState'] == 'RUNNING' and job['NodeList'] == c['node']
         and int(job['NumCPUs']) >= 16, 'ACTUAL_RUNNING_HOST_ALLOCATION')
    for source in plan['source_references']:
        need(ref(source['path']) == source, 'IO_AND_ORIGINAL_READER_SOURCE_CHANGED')
    need(c['context_source_reference'] in plan['source_references']
         and ref(c['context_source_reference']['path']) == c['context_source_reference'],
         'ACTUAL_EXISTING_GPU_HOST_CONTEXT_PRODUCER_SOURCE_BOUND')
    required = {str(HERE/'run.py'), str(HERE/'__init__.py'),
                str(REPO/'workflows/data_v1_final/export/family_export_day_v1/verify.py'),
                str(REPO/'workflows/data_v1_final/export/family_export_day_v1/store.py')}
    need(required <= {s['path'] for s in plan['source_references']}, 'ACTUAL_IO_READER_SOURCES_PINNED')
    return c, {'host_context_reference': context_ref, 'original_host_startup_proof_reference': c['host_startup_proof_reference'],
               'original_host_request_reference': c['host_request_reference'], 'actual_scontrol': raw,
               'actual_nvidia_smi': inventory, 'actual_host_job': job,
               'actual_host_full_argv': argv, 'actual_host_cgroup': Path('/proc/self/cgroup').read_text(),
               'GPU_USED_BY_THIS_IO_PHASE': False, 'host_is_existing_GPU_parent': True}


def run(plan_path, host_context_path, *, check_host_resources):
    """Mechanical I/O only. Existing parent resource guard continues unchanged."""
    need(callable(check_host_resources), 'IN_PROCESS_EXISTING_ADMITTED_GPU_GUARD_REQUIRED')
    check_host_resources()
    plan_ref = ref(plan_path); p = document(plan_ref); c, observation = host(p, plan_ref, host_context_path)
    need(p['schema'] == 'PROVISIONAL_D3_GPU_HOST_LOCAL_IO_PLAN_V1'
         and p['version'] == 'v1-pilot-provisional', 'EXACT_PROVISIONAL_D3_IO_PLAN')
    export = document(p['D3_export_reference']); root = Path(p['local_root'])
    need(export['schema'] == 'DATA_V1_PILOT_D3_FORMAL_EXPORT_DELIVERY_V1'
         and export['version'] == p['version']
         and export['status'] == 'DELIVERED_PROVISIONAL_SCOPE_NOT_FINAL_COMMON'
         and export['pilot_counts'] == {'TRAIN': 50000, 'VAL': 5000}
         and export['available_orders'] == ['fixed_random']
         and export['Model_payload_ACK'] is False, 'REAL_PROVISIONAL_EXPORT_NOT_FINAL_ALIAS')
    receipt = document(export['actual_D3_receipt_reference'])
    account = document(export['actual_parent_accounting_reference'])
    raw = document_text(account['raw_sacct_reference'])
    jid = str(export['actual_D3_parent_job_id']); parents = [r for r in account['parents'] if str(r['job_id']) == jid]
    need(account['schema'] == 'DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'
         and account['endpoint'] == '202.38.247.57:22' and account['uid'] == 1278
         and account['query_returncode'] == 0 and len(parents) == 1
         and parents[0]['state'] == 'COMPLETED' and parents[0]['exit_code'] == '0:0', 'TRUE_D3_C0_LINEAGE')
    actual = [r for r in csv.DictReader(io.StringIO(raw), delimiter='|') if r['JobIDRaw'] == jid]
    need(len(actual) == 1 and all(actual[0][k] == v for k, v in
         {'UID': '1278', 'State': 'COMPLETED', 'ExitCode': '0:0', 'AllocCPUS': '16'}.items()), 'RAW_D3_C0')
    need(receipt['schema'] == 'BOUNDED_PILOT_FAMILY_D3_RECEIPT_V1'
         and receipt['status'] == 'ACTUAL55K_FIXED_RANDOM_FAMILY_AND_10K_SOURCE_QA_COMPLETE_PENDING_ROOT_MODEL_REVIEW'
         and str(receipt['job_id']) == jid and receipt['errors'] == []
         and receipt['store_references'] == export['store_references']
         and receipt['verification_reference'] == export['verification_reference'], 'EXACT_CLOSED_D3_OBJECTS')
    need(root.is_absolute() and str(root).startswith('/tmp/') and '..' not in root.parts
         and not root.exists() and not any(x.is_symlink() for x in root.parents), 'FRESH_NODE_LOCAL_COPY_NO_OVERWRITE')
    need(all(type(p[k]) is int and p[k] > 0 for k in
         ('copy_cap_bytes', 'owned_rss_soft_cap_bytes', 'drain_reserve_seconds'))
         and type(p['local_disk_reserve_bytes']) is int and p['local_disk_reserve_bytes'] >= 0,
         'EXISTING_HOST_EXPLICIT_FINITE_SCRATCH_RSS_AND_WALL_BUDGET')
    root.mkdir(mode=0o700, parents=True)
    mounts = []
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left, right = line.split(' - ', 1)
        mount = Path(left.split()[4].replace('\\040', ' '))
        if root.is_relative_to(mount): mounts.append((len(mount.parts), right.split()[0], line))
    need(mounts and max(mounts)[1] in ('ext4', 'xfs', 'btrfs', 'zfs', 'f2fs'),
         'ACTUAL_NODE_LOCAL_DISK_NOT_NFS_GLUSTER_OR_TMPFS')
    observation['actual_local_mountinfo'] = max(mounts)[2]
    from workflows.data_v1_final.export.family_export_day_v1 import verify as V
    from workflows.data_v1_final.export.family_export_day_v1.store import Reader
    def sources():
        declared = {r['path']: r for r in p['source_references']}
        for module in list(sys.modules.values()):
            path = getattr(module, '__file__', None)
            if path is None: continue
            path = Path(path).absolute()
            if (REPO/'workflows/data_v1_final/export') in path.parents and path.suffix == '.py':
                need(declared.get(str(path)) == ref(path), 'EVERY_ACTUAL_IMPORTED_ORIGINAL_READER_SOURCE_BOUND')
    sources()
    stores = []; inventory = []; used = 0; last = 0.; started = time.monotonic()
    import psutil
    process = psutil.Process()

    def check(force=False):
        nonlocal last
        now = time.monotonic()
        if not force and now - last < 1:
            return
        last = now
        check_host_resources()
        members = [process, *process.children(recursive=True)]; rss = 0
        for item in members:
            try: rss += item.memory_info().rss
            except psutil.NoSuchProcess: pass
        need(rss <= p['owned_rss_soft_cap_bytes'], 'STOP_NEW_IO_OWNED_RSS_EXISTING_HOST_BUDGET')
        need(now - c['observed_monotonic_seconds'] < c['host_remaining_wall_seconds'] - p['drain_reserve_seconds'], 'STOP_NEW_IO_EXISTING_HOST_WALL')
        space = os.statvfs(root)
        need(space.f_bavail * space.f_frsize - max(0, p['copy_cap_bytes'] - used) >= p['local_disk_reserve_bytes'], 'ACTUAL_LOCAL_SCRATCH_CAPACITY')
        need(used <= p['copy_cap_bytes'], 'HOST_DECLARED_COPY_CAP')

    def copy(source, destination):
        nonlocal used
        check(True); before = fingerprint(Path(source['path']))
        need(before[2] == source['bytes'] and used + source['bytes'] + REPORT_RESERVE_BYTES <= p['copy_cap_bytes'], 'COPY_ACTUAL_SIZE_AND_HOST_CAP')
        temporary = destination.with_name(destination.name + '.partial'); h = hashlib.sha256(); n = 0
        with Path(source['path']).open('rb') as stream, temporary.open('xb') as target:
            while True:
                block = stream.read(4 << 20)
                if not block: break
                check(); target.write(block); h.update(block); n += len(block); used += len(block)
            target.flush(); os.fsync(target.fileno())
        need(fingerprint(Path(source['path'])) == before and n == source['bytes']
             and h.hexdigest() == source['sha256'], 'COPY_COMPLETE_EOF_SHA_AND_SOURCE_IDENTITY')
        os.rename(temporary, destination); target_ref = ref(destination, check)
        need(target_ref['bytes'] == n and target_ref['sha256'] == source['sha256'], 'LOCAL_REOPEN_WHOLE_SHA')
        inventory.append({'origin': source, 'local': target_ref})
        return target_ref

    # Same Reader class as the original Fast55k validation. Immutable manifest
    # and payload bytes are copied, never rewritten with target-path guesses.
    try:
        names = set(); mids = set()
        for r in export['store_references']:
            store = document(r); name = store['name']
            need(name not in names and '/' not in name and '\\' not in name and name not in ('.', '..'), 'UNIQUE_LITERAL_STORE_NAME')
            names.add(name); local = root/name; local.mkdir()
            copy(store['data'], local/'data.mdb'); copy(store['manifest_reference'], local/'manifest.json')
            side = copy(store['f64_authority']['reference'], root/(name+'.authority_f64.sqlite'))
            with Reader(local, expected_schema_sha256=store['schema_sha256']) as reader:
                need(reader.count == store['records'] and reader.molecule_count == store['molecules'], 'ALL_ORIGINAL_STORE_COUNTS_AND_SCHEMA')
                with reader.env.begin() as tx, tx.cursor(db=reader.molecules) as cursor:
                    for key, _ in cursor:
                        mids.add(key.decode())
            stores.append({'name': name, 'path': str(local), 'origin_reference': r, 'f64_authority': side})
        need(len(mids) == 55000, 'ACTUAL_ALL_55K_DISTINCT_LOCAL_MOLECULES')
        chosen = sorted(mids, key=lambda mid: (V.O.rank_hash(20261025, 'whole_MID', mid), mid))[:16]
        work = []
        for index, mid in enumerate(chosen):
            records = []
            for store in stores:
                with Reader(store['path']) as reader:
                    records.extend((store['path'], gid) for gid in reader.records_for_molecule(mid))
            need(records, 'WHOLE_MID_HAS_ACTUAL_LOCAL_RECORDS'); work.append((index, [(mid, records)]))
        check(True); ctx = mp.get_context('spawn'); barrier = ctx.Barrier(16); begin = time.monotonic()
        with cf.ProcessPoolExecutor(max_workers=16, mp_context=ctx, initializer=V.read_initializer, initargs=(barrier,)) as pool:
            active = {pool.submit(V.molecule_reader, item) for item in work}; results = []
            # All work is finite/already dispatched. Stop is natural pool drain;
            # no signals, cancellation, extra task, or retry is introduced.
            while active:
                check(); done, active = cf.wait(active, timeout=1, return_when=cf.FIRST_COMPLETED)
                results.extend(f.result() for f in done)
        seconds = time.monotonic() - begin
        need(len(results) == len({r['pid'] for r in results}) == 16
             and all(r['all_handles_closed'] for r in results), 'ACTUAL16_READER_PROCESSES_CLOSED')
        for row in results:
            try: alive = psutil.Process(row['pid']).create_time() == row['process_start']
            except psutil.NoSuchProcess: alive = False
            need(not alive, 'OWN_READER_PROCESSES_NATURALLY_JOINED')
        sources()
        copied = save(root/'copy_inventory.json', inventory)
        return save(root/'local_io_receipt.json', {'schema': 'ACTUAL_PROVISIONAL_D3_GPU_HOST_LOCAL_IO_RECEIPT_V1',
            'status': 'EXACT_D3_LOCAL_COPY_AND16_READER_IO_COMPLETE_NOT_MODEL_ACK',
            'version': p['version'], 'plan_reference': plan_ref, 'D3_export_reference': p['D3_export_reference'],
            **observation, 'local_root': str(root), 'local_copy_inventory_reference': copied,
            'local_stores': stores, 'actual_local_statvfs': list(os.statvfs(root)), 'copied_bytes': used,
            'distinct_molecules': len(mids), 'read_sample_MIDs': chosen, 'workers': results,
            'molecules_per_second_including_spawn': 16/seconds,
            'records_per_second_including_spawn': sum(r['records'] for r in results)/seconds,
            'benchmark_cache_state': 'AFTER_FULL_COPY_SHA_AND_INDEX_READ_NO_OS_CACHE_FLUSH',
            'wall_seconds_including_copy': time.monotonic()-started, 'Model_payload_ACK': False,
            'D6_or_final_Common_claimed': False, 'new_QM_UFF_calls': 0, 'new_GPU_computation_by_IO_phase': False})
    except BaseException as error:
        save(root/'partial_io_receipt.json', {'schema': 'PROVISIONAL_D3_LOCAL_IO_PARTIAL_V1',
            'status': 'PARTIAL_NOT_LOCAL_IO_ACCEPTANCE_NOT_MODEL_ACK', 'error_type': type(error).__name__,
            'copied_bytes': used, 'closed_stores': stores, 'plan_reference': plan_ref,
            'host_context_reference': observation['host_context_reference'], 'Model_payload_ACK': False,
            'partial_copies_retained_no_signals_or_retry': True})
        raise


def document_text(reference):
    need(ref(reference['path']) == reference and reference['bytes'] <= 2 << 20, 'EXACT_SMALL_RAW_ACCOUNTING')
    return Path(reference['path']).read_text(encoding='utf-8-sig')


def main():
    raise SystemExit('IN_PROCESS_ONLY: the admitted GPU Parent must call run(..., check_host_resources=its_live_guard); exec/standalone CLI would lose that guard and its locks.')


if __name__ == '__main__':
    main()
