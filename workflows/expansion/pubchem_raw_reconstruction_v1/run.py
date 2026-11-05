"""Durable full500 raw reconstruction using unchanged scientific functions."""
from __future__ import annotations
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
import fcntl
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import socket
import time
import traceback
import uuid
from . import facts, kernel
from .plan import validate
from .support import BASELINE, CATEGORIES, N, CooperativeStop, RuntimeGuard, canonical, frame, load, need, reference, verify, write_new


def initialize_worker(stop):
    from .science import features_legacy_compatible_v2 as compatible
    from rdkit import rdBase
    began, cpu = time.monotonic(), time.process_time()
    compatible.rdkit_modules()
    kernel.STOP = stop
    kernel.INITIALIZATION = {'pid': os.getpid(), 'uid': os.getuid(), 'hostname': socket.gethostname(), 'job_id': os.environ.get('SLURM_JOB_ID'), 'affinity': sorted(os.sched_getaffinity(0)), 'rdkit': rdBase.rdkitVersion, 'rdkit_build': rdBase.rdkitBuild, 'elapsed_seconds': time.monotonic() - began, 'CPU_seconds': time.process_time() - cpu, 'chemical': True}


def chemical_batch(records):
    values = []
    for original in records:
        try:
            values.append(kernel.chemical_task(original))
        except CooperativeStop:
            return {'values': values, 'resource_stop': True}
    return {'values': values, 'resource_stop': False}


def iter_original_records(part, observation, check):
    path = Path(part['reference']['path'])
    before = frame(path)
    need(before[2] == part['bytes'], 'Original raw source part size differs')
    digest = hashlib.sha256()
    ordinal, offset, previous = part['first_ordinal'], 0, None
    first = last = None
    with path.open('rb', buffering=1 << 20) as stream:
        opened = os.fstat(stream.fileno())
        need((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_uid) == before, 'Original raw source same FD required')
        while True:
            check()
            raw = stream.readline(facts.C.MAX_LINE + 1)
            if not raw:
                break
            fact = facts.row_fact(raw, ordinal, part['index'], offset)
            original = facts.record(raw, fact, part['reference'])
            cid = int(original['cid_source_ascii'])
            need(previous is None or cid > previous, 'Original raw source CID order/uniqueness differs')
            previous = cid
            summary = facts.cid_summary(original['cid_source_ascii'].encode('ascii'))
            first = summary if first is None else first
            last = summary
            digest.update(raw)
            offset += len(raw)
            ordinal += 1
            yield original
        opened = os.fstat(stream.fileno())
        need((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_uid) == before == frame(path), 'Original raw part changed while computing')
    need(ordinal == part['last_ordinal'] + 1 and offset == part['bytes'] and digest.hexdigest() == part['reference']['sha256'] and first == part['first_cid'] and last == part['last_cid'], 'Every original source byte/CID/ordinal/row must conserve')
    observation.update(source_SHA_verified=digest.hexdigest(), source_frame=list(before), input_rows=part['records'], source_bytes=offset, first_cid=first, last_cid=last)


class Writer:
    def __init__(self, attempt, fragment_id, flush_rows=8192):
        import pyarrow as pa
        import pyarrow.parquet as pq
        self.pa, self.pq, self.fragment_id, self.flush_rows = pa, pq, fragment_id, flush_rows
        self.schema = kernel.output_schema()
        self.accepted_schema = self.schema.append(pa.field('cid', pa.int64())).append(pa.field('source_fragment_id', pa.string()))
        self.fact_schema = pa.schema([('ordinal', pa.int64()), ('part_index', pa.int32()), ('offset_bytes', pa.int64()), ('source_row_bytes', pa.int32()), ('smiles_bytes', pa.int32()), ('source_row_sha256', pa.string()), ('source_smiles_sha256', pa.string()), ('source_terminator_hex', pa.string()), ('cid_source_ascii', pa.string())])
        self.paths = {'all_results': attempt / 'all_results.parquet', 'source_facts': attempt / 'source_facts.parquet', 'accepted': attempt / 'accepted.parquet'}
        self.writers = {'all_results': pq.ParquetWriter(self.paths['all_results'], self.schema, compression='zstd'), 'source_facts': pq.ParquetWriter(self.paths['source_facts'], self.fact_schema, compression='zstd'), 'accepted': pq.ParquetWriter(self.paths['accepted'], self.accepted_schema, compression='zstd')}
        self.rows, self.facts = [], []
        self.counts = Counter({key: 0 for key in CATEGORIES})
        self.first_rules, self.overlap_rules, self.technical_codes, self.worker_records = Counter(), Counter(), Counter(), Counter()
        self.worker_initializations = {}
        self.next_ordinal = None

    def append(self, value):
        original, category = value['input'], value['category']
        need(category in CATEGORIES and (self.next_ordinal is None or original['ordinal'] == self.next_ordinal), 'Ordered original chemical result required')
        self.next_ordinal = original['ordinal'] + 1
        self.rows.append(kernel.parquet_row(value, 'full_shard'))
        self.facts.append({name: original[name] for name in self.fact_schema.names})
        self.counts[category] += 1
        if category == 'chemReject':
            reasons = value['legacy_dispatcher_result']['reasons']
            need(reasons, 'Original chemical reject reason evidence required')
            self.first_rules[reasons[0]] += 1
            self.overlap_rules.update(reasons)
        elif category == 'technicalUnresolved':
            self.technical_codes.update(value['technical_codes'])
        pid = str(value['worker_pid'])
        self.worker_records[pid] += 1
        self.worker_initializations[pid] = value['worker_initialization']
        if len(self.rows) >= self.flush_rows:
            self.flush()

    def flush(self):
        if not self.rows:
            return
        import pyarrow.compute as pc
        table = self.pa.Table.from_pylist(self.rows, schema=self.schema)
        fact_table = self.pa.Table.from_pylist(self.facts, schema=self.fact_schema)
        self.writers['all_results'].write_table(table, row_group_size=self.flush_rows)
        self.writers['source_facts'].write_table(fact_table, row_group_size=self.flush_rows)
        accepted = table.filter(pc.equal(table['category'], 'accepted'))
        if len(accepted):
            cid = pc.cast(accepted['cid_source_ascii'], self.pa.int64(), safe=True)
            need(cid.null_count == 0 and pc.all(pc.greater(cid, 0)).as_py(), 'Original positive CID must survive in accepted rows')
            accepted = accepted.append_column('cid', cid).append_column('source_fragment_id', self.pa.array([self.fragment_id] * len(accepted)))
            self.writers['accepted'].write_table(accepted, row_group_size=self.flush_rows)
        self.rows, self.facts = [], []

    def close(self):
        try:
            self.flush()
        finally:
            for writer in self.writers.values():
                writer.close()
        for path in self.paths.values():
            with path.open('rb') as stream:
                os.fsync(stream.fileno())


def complete_shard(part, plan):
    receipt_path = Path(plan['output_directory']) / 'fragments' / ('%03d_0' % part['index']) / 'complete.json'
    if not receipt_path.exists():
        return None
    receipt = load(receipt_path)
    need(receipt['schema'] == 'PUBCHEM_RAW_RECONSTRUCTION_SHARD_V1' and receipt['source_descriptor'] == part and receipt['scientific_scope_sha256'] == plan['scientific_scope_sha256'], 'Closed shard belongs to a different immutable scope')
    need(receipt['source_rows'] == sum(receipt['counts'].values()) == part['records'], 'Closed shard source mass differs')
    if list(frame(part['reference']['path'])) != receipt['source_observation']['source_frame']:
        verify(part['reference'])
    for kind, ref in receipt['outputs'].items():
        # A closed file was hashed by its producer. Reuse that proof while its
        # exact physical frame is unchanged; rehash only a changed/restored file.
        if list(frame(ref['path'])) != receipt['output_frames'][kind]:
            verify(ref)
    return receipt


def process_shard(part, plan, pool, check=lambda: None):
    existing = complete_shard(part, plan)
    if existing is not None:
        return existing
    unit = Path(plan['output_directory']) / 'fragments' / ('%03d_0' % part['index'])
    unit.mkdir(parents=True, exist_ok=True)
    with (unit / 'claim.lock').open('a+b') as claim:
        try:
            fcntl.flock(claim, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None  # Actual live lock, not existence of an old intent file.
        existing = complete_shard(part, plan)
        if existing is not None:
            return existing
        attempt = unit / ('attempt_' + uuid.uuid4().hex)
        attempt.mkdir(exist_ok=False)
        writer = Writer(attempt, unit.name)
        observation, waiting, batch = {}, deque(), []
        began = time.monotonic()

        def collect():
            future, expected_ordinals = waiting.popleft()
            result = future.result()  # No arbitrary chemistry task timeout.
            values = result['values']
            need([value['input']['ordinal'] for value in values] == expected_ordinals[:len(values)], 'Worker batch source order differs')
            for value in values:
                writer.append(value)
            need(not result['resource_stop'] and len(values) == len(expected_ordinals), 'Cooperative resource drain retained an incomplete shard, never a chemical exclusion')
            check()

        try:
            for original in iter_original_records(part, observation, check):
                batch.append(original)
                if len(batch) == plan['batch_rows']:
                    waiting.append((pool.submit(chemical_batch, batch), [r['ordinal'] for r in batch]))
                    batch = []
                    if len(waiting) >= 2 * plan['workers']:
                        collect()
            if batch:
                waiting.append((pool.submit(chemical_batch, batch), [r['ordinal'] for r in batch]))
            while waiting:
                collect()
            need(sum(writer.counts.values()) == observation['input_rows'] == part['records'] and writer.next_ordinal == part['last_ordinal'] + 1, 'All original part rows must complete before checkpoint')
            writer.close()
            outputs = {kind: reference(path) for kind, path in writer.paths.items()}
            need(writer.pq.ParquetFile(outputs['all_results']['path']).metadata.num_rows == writer.pq.ParquetFile(outputs['source_facts']['path']).metadata.num_rows == part['records'] and writer.pq.ParquetFile(outputs['accepted']['path']).metadata.num_rows == writer.counts['accepted'], 'Actual typed/facts/accepted Parquet cardinalities must conserve')
            receipt = {'schema': 'PUBCHEM_RAW_RECONSTRUCTION_SHARD_V1', 'status': 'FULL_ORIGINAL_RAW_SHARD_RECOMPUTED_NO_POOL_RELEASE', 'scientific_scope_sha256': plan['scientific_scope_sha256'], 'source_descriptor': part, 'source_rows': part['records'], 'source_observation': observation, 'counts': dict(writer.counts), 'outputs': outputs, 'first_rule_counts': dict(writer.first_rules), 'overlap_rule_counts': dict(writer.overlap_rules), 'technical_reason_counts': dict(writer.technical_codes), 'actual_worker_records': dict(writer.worker_records), 'actual_worker_initializations': writer.worker_initializations, 'actual_parent': {'pid': os.getpid(), 'uid': os.getuid(), 'hostname': socket.gethostname(), 'SlurmJobID': os.environ.get('SLURM_JOB_ID')}, 'wall_seconds': time.monotonic() - began, 'technical_UNKNOWN_not_chemical_exclusion': True, 'original_Alpha_scientific_bodies_reused': False, 'new_chemical_calls': part['records'], 'full_JSON_journal_duplicated': False, 'original_full_result_JSON_and_errors_preserved_in_typed_Parquet': True}
            receipt['output_frames'] = {kind: list(frame(ref['path'])) for kind, ref in outputs.items()}
            write_new(unit / 'complete.json', receipt)
            return receipt
        except BaseException as exc:
            # Consume already dispatched work naturally; do not signal/terminate
            # any process or classify infrastructure failures as chemistry.
            for future, unused in waiting:
                try:
                    future.result()
                except BaseException:
                    pass
            try:
                writer.close()
            except BaseException:
                pass
            write_new(attempt / 'failure.json', {'schema': 'PUBCHEM_RECONSTRUCTION_PARTIAL_V1', 'source_descriptor': part, 'scientific_scope_sha256': plan['scientific_scope_sha256'], 'error': repr(exc), 'traceback': traceback.format_exc(), 'partial_counts_not_a_complete_shard': dict(writer.counts), 'partial_files_retained': True, 'chemical_exclusion_invented': False})
            raise


def baseline_comparison(counts):
    difference = {key: counts[key] - BASELINE[key] for key in CATEGORIES}
    return {'old_Alpha_baseline_counts': BASELINE, 'new_observed_counts': counts, 'new_minus_old': difference, 'matches_original_baseline': not any(difference.values()), 'counts_forced_equal': False, 'rowwise_old_Alpha_comparison': 'UNAVAILABLE_UNLESS_ORIGINAL_BODIES_ARE_RECOVERED', 'known_causes': [], 'unattributed_difference': any(difference.values()), 'interpretation': 'Different technical outcomes may resolve under changed operational timeout policy. An aggregate count difference alone does not prove its cause; preserve all actual reasons and do not fabricate equality.'}


def assemble(plan_path):
    plan = validate(load(plan_path))
    receipts = []
    for part in plan['scientific_scope']['parts']:
        value = complete_shard(part, plan)
        need(value is not None, 'Full original500 reconstruction is not complete: part' + str(part['index']))
        receipts.append(value)
    counts = {key: sum(r['counts'][key] for r in receipts) for key in CATEGORIES}
    need(len(receipts) == 500 and sum(counts.values()) == N, 'Every original124857440 source row must conserve; no smaller fallback')
    out = Path(plan['output_directory'])
    manifest = {'schema': 'PUBCHEM_ALL_CLOSED_PROJECTIONS_V2', 'status': 'COMPLETE_ACCEPTED_PROJECTIONS_NO_POOL_RELEASE', 'producer_schema': 'PUBCHEM_FULL_RAW_RECONSTRUCTION_COVERAGE_V1', 'source_rows': N, 'counts': counts, 'fragment_count': 500, 'accepted_parquets': [r['outputs']['accepted'] for r in receipts], 'fragments': [reference(out / 'fragments' / ('%03d_0' % p['index']) / 'complete.json') for p in plan['scientific_scope']['parts']], 'scientific_scope_sha256': plan['scientific_scope_sha256'], 'source_scope': plan['scientific_scope'], 'baseline_comparison': baseline_comparison(counts), 'old_502_Alpha_body_closure_claimed': False, 'chemistry_recomputed': True, 'new_chemical_calls': N, 'full_raw_scope_reconstructed': True}
    manifest['new_chemical_calls_scope'] = 'Canonical completed500 attempts only, not all failed/partial attempts'
    manifest['total_actual_invocations_including_unclosed_partials'] = 'UNKNOWN_WHERE_INTERRUPTED; actual allocated parent core-hours must include every attempt'
    manifest['actual_cost_from_real_parent_accounting_required'] = True
    path = out / 'projection_manifest.json'
    if path.exists():
        need(load(path) == manifest, 'Existing full reconstruction manifest differs')
    else:
        write_new(path, manifest)
    return manifest


def run(plan_path, indices=None):
    plan = validate(load(plan_path))
    need(os.getuid() == 1278 and socket.gethostname().startswith('compute-'), 'Full data work must run on actual Main compute nodes')
    actual_cpus = min(len(os.sched_getaffinity(0)), int(os.environ.get('SLURM_CPUS_PER_TASK', len(os.sched_getaffinity(0)))))
    need(plan['workers'] <= actual_cpus and plan['workers'] >= 16 and os.environ.get('SLURM_JOB_ID'), 'A real allocation with at least16 effective CPUs is required')
    node, partition = socket.gethostname().split('.')[0], os.environ.get('SLURM_JOB_PARTITION')
    if node == 'compute-0-21':
        need('cpu21_authorization_reference' in plan, 'Explicit actual user CPU21 authorization reference required')
        approval = load(verify(plan['cpu21_authorization_reference']))
        validate_cpu21_policy(node, partition, approval)
    out = Path(plan['output_directory'])
    out.mkdir(parents=True, exist_ok=True)
    scope_path = out / 'scientific_scope.json'
    if scope_path.exists():
        need(load(scope_path) == plan['scientific_scope'], 'Cannot resume a different source/scientific scope')
    else:
        write_new(scope_path, plan['scientific_scope'])
    verify(plan['scientific_scope']['raw_reference'])
    verify(plan['scientific_scope']['source_index_reference'])
    selected = set(range(500) if indices is None else indices)
    need(selected and selected <= set(range(500)), 'Explicit original descriptor allocation required')
    context = mp.get_context('spawn')
    stop = context.Event()
    guard = RuntimeGuard(plan, stop)
    closed, held = [], []
    try:
        with ProcessPoolExecutor(max_workers=plan['workers'], mp_context=context, initializer=initialize_worker, initargs=(stop,)) as pool:
            for part in plan['scientific_scope']['parts']:
                if part['index'] not in selected:
                    continue
                guard.check()
                receipt = process_shard(part, plan, pool, guard.check)
                (held if receipt is None else closed).append(part['index'])
                print(canonical({'event': 'ORIGINAL_SHARD_' + ('CLOSED' if receipt is not None else 'LIVE_LOCK_HELD'), 'index': part['index'], 'counts': receipt['counts'] if receipt else None}).decode(), flush=True)
    finally:
        guard.close()
    parent = {'schema': 'PUBCHEM_RECONSTRUCTION_PARENT_SCOPE_V1', 'status': 'OWN_DECLARED_SHARD_SCOPE_RETURNED_NOT_GLOBAL_POOL_RELEASE', 'actual_job_id': os.environ['SLURM_JOB_ID'], 'pid': os.getpid(), 'uid': os.getuid(), 'hostname': socket.gethostname(), 'plan_reference': reference(plan_path), 'selected_original_indices': sorted(selected), 'closed_or_reused_indices': closed, 'actual_live_lock_indices_not_claimed_complete': held, 'runtime_observation': guard.receipt(), 'global_original500_completion_not_inferred': True}
    parent['actual_partition'] = partition
    parent['cpu21_authorization_reference'] = plan.get('cpu21_authorization_reference') if node == 'compute-0-21' else None
    parent['GPU_requested_or_used_by_this_producer'] = False
    target = out / ('parent_' + os.environ['SLURM_JOB_ID'] + '_' + str(os.getpid()) + '.json')
    write_new(target, parent)
    return parent


def validate_cpu21_policy(node, partition, approval):
    need(approval['schema'] == 'PUBCHEM_EXPANSION_USER_CPU21_AUTHORIZATION_V1' and approval['status'] == 'USER_APPROVED' and approval['node'] == node == 'compute-0-21' and approval['partition'] == partition == 'all' and approval['GPU_used'] is False and approval['paid_server_used'] is False, 'Actual CPU-only node21/all user approval required; do not claim cpu-partition execution')
