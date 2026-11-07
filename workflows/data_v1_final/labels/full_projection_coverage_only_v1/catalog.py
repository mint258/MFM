"""Receipt-based coverage directory; first base-Z read, no label-value replay."""
import collections
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import struct

from workflows.data_v1_final.labels.normalization_compact_day_v1 import io as I, lineage as L
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import contract as C, codec as K, bindings as B
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import (
    TASK_FAMILIES, identity, lookup_batch, sqlite_ro)

SCHEMA = 'COMPACT_NUMERIC_PRODUCER_EVIDENCE_COVERAGE_V1'
STATUS = 'CLOSED_PRODUCER_EVIDENCE_COVERAGE_AND_BASE_INDEX_NOT_FINAL_MASKS'
N = 11231854


def source_path(reference):
    """Existing positive DATA pin plus current FD/type/owner/frame, not a new body hash."""
    return I.require(reference, content=False)


def execute(cfg, proof, root, gate, budget):
    import pyarrow.parquet as pq
    C.need(cfg['mode'] == 'full', 'ONLY_FULL_RECEIPT_COVERAGE')
    book = I.load(I.require(cfg['source_inventory_reference']))
    files = book['files']; sources = {s['file_id']: s for s in files}
    C.source_contract(files)
    canonical_path = source_path(cfg['canonical_index']); canonical_frame = identity(canonical_path)
    canonical = sqlite_ro(canonical_path)
    db = sqlite3.connect(root / 'numeric_catalog.sqlite')
    db.execute('PRAGMA journal_mode=DELETE'); db.execute('PRAGMA synchronous=FULL')
    db.execute('PRAGMA cache_size=-8192')
    db.execute('PRAGMA max_page_count=' + str((cfg['whole_output_cap_bytes'] - (512 << 20)) // 4096))
    db.executescript('CREATE TABLE parts(file INTEGER,lo INTEGER,hi INTEGER,task INTEGER,kind TEXT,ref TEXT,window TEXT,parent TEXT,PRIMARY KEY(file,lo,task));'
                     'CREATE TABLE base(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,numbers BLOB,meta TEXT,owner_sha BLOB,usable INTEGER);'
                     'CREATE TABLE formal(rid TEXT PRIMARY KEY,mol TEXT,payload TEXT,natoms INTEGER);'
                     'CREATE TABLE molecules(mol TEXT PRIMARY KEY) WITHOUT ROWID;')
    intervals = []; stats = collections.defaultdict(collections.Counter)
    physical = collections.defaultdict(collections.Counter)
    per_job_task = collections.Counter(); base_parts = []
    parts = base_rows = formal_rows = base_pending = 0
    try:
        # Metadata-only canonical-owner census; no label values or typed bits.
        jobs = {str(job): count for job, count in canonical.execute('SELECT job_id,count(*) FROM records GROUP BY job_id')}
        count, molecules, low, high = canonical.execute(
            'SELECT count(*),count(DISTINCT molecule_id),min(record_ordinal),max(record_ordinal) FROM records').fetchone()
        C.need(count == N and molecules == 1220466 and low == 0 and high == N - 1,
               'ORIGINAL_CANONICAL_RECORD_MOLECULE_ORDINAL_DOMAIN')
        for parent in cfg['batch_history']:
            budget.check()
            manifest, _ = L.actual(parent); parent_root = L.parts_root(manifest, parent)
            oldcfg = I.load(I.require(manifest['config']))
            for key in ('canonical_index', 'footer_manifest_reference', 'logical_group_plan_reference',
                        'field_map_reference', 'codec_schema', 'row_size_rule', 'mode'):
                C.need(oldcfg[key] == cfg[key], 'ONE_UNCHANGED_PRODUCER_SOURCE_CODEC:' + key)
            C.need(manifest['status'] in ('CLOSED_WINDOWS_ACTUAL_PARENT_ACCOUNTING_REQUIRED',
                    'DAY_INTERNAL_COMMITTED_WINDOWS_NOT_CHILD_C0', 'ROOT_ADOPTED_FAILED_DAY_CLOSED_WINDOWS_CURRENT_PARENT_VERIFIED')
                   and not (manifest['errors'] or manifest['quality_hold_fields'] or manifest['unpublished_tickets']),
                   'CLEAN_ACTUAL_CLOSED_PRODUCER_ONLY')
            for wr in manifest['verified_window_receipts']:
                budget.check()
                C.need(Path(wr['path']).parent == parent_root / 'parts', 'BOUND_CLOSED_WINDOW_PATH')
                window = I.load(I.require(wr)); fid = window['file_id']; source = sources[fid]
                C.need(window['schema'] == 'COMPACT_NUMERIC_PHYSICAL_WINDOW_V1'
                       and window['source_reference'] == source and window['all_part_reopen_bits_verified'] is True,
                       'ORIGINAL_PRODUCER_WINDOW_BITS_ALREADY_VERIFIED')
                lo, hi = window['physical_row_lo'], window['physical_row_hi']
                classes = window['physical_classifications']
                C.need(all(type(v) is int and v >= 0 for v in classes.values())
                       and sum(classes.values()) == hi - lo, 'PHYSICAL_WINDOW_CLASSIFICATION_MASS')
                intervals.append(dict(file_id=fid, lo=lo, hi=hi, all_part_reopen_bits_verified=True))
                physical[source['source_kind']].update(classes)
                for key, value in window['field_stats'].items(): stats[key].update(value)
                kinds = set(); window_rows = 0
                allowed = {255} if source['family'] == 'base_geometry' else {
                    B.TASKS[t] for t, family in TASK_FAMILIES.items() if family == source['family']}
                for part in window['parts']:
                    pr = part['reference']; kind = part['row_kind']; task = part['task_code']; rows = part['rows']
                    C.reference(pr)
                    C.need(Path(pr['path']).parent == parent_root / 'parts' and Path(pr['path']).suffix == '.parquet'
                           and (kind, task) not in kinds and task in allowed
                           and kind == ('base' if task == 255 else 'task') and type(rows) is int and rows > 0
                           and re.fullmatch('[0-9a-f]{64}', part['typed_stream_sha256']),
                           'UNIQUE_ORIGINAL_CLOSED_PART_TASK_ROWCOUNT_AND_PRODUCER_DIGEST')
                    source_path(pr)  # current FD/frame/type/size only; no label DATA body read
                    kinds.add((kind, task)); window_rows += rows
                    per_job_task[(str(source['source_job_id']), task)] += rows
                    db.execute('INSERT INTO parts VALUES(?,?,?,?,?,?,?,?)',
                               (fid, lo, hi, task, kind, K.canonical(pr).decode(), K.canonical(wr).decode(),
                                K.canonical(parent['manifest']).decode()))
                    parts += 1
                    if kind == 'base': base_parts.append((pr, fid, lo, hi, rows))
                C.need(window_rows == classes.get('CANONICAL', 0), 'CLOSED_CANONICAL_ROWS_EQUAL_PART_MASS')
                db.commit()
        cursors = C.advance_cursors(files, {}, intervals)
        C.need(all(cursors[str(s['file_id'])] == s['rows'] for s in files), 'ALL_SOURCE_INTERVALS_NO_GAP_OR_OVERLAP')
        C.need(set(job for job, _ in per_job_task) == set(jobs), 'EXACT_CANONICAL_PRODUCER_JOB_DOMAIN')
        for job, expected in jobs.items():
            C.need(all(per_job_task[(job, task)] == expected for task in [255, *B.TASKS.values()]),
                   'ORIGINAL_CANONICAL_OWNER_AND_CLOSED_PRODUCER_ALL14_BASE_MASS:' + job)
        C.need(physical['label']['CANONICAL'] == N * 14 and sum(physical['label'].values()) == 157254650
               and physical['base']['CANONICAL'] == N and sum(physical['base'].values()) == 11232475,
               'FULL_PHYSICAL_CANONICAL_SHADOW_MASS')
        C.need(len(stats) == 146 and all(s['records'] == N for s in stats.values()), 'ALL146_ORIGINAL_FIELD_DENOMINATORS')
        holds = B.quality_stop_fields(stats, N, .01)
        if holds:
            I.save(root / 'quality_hold.json', dict(quality_hold_fields=holds, field_stats={k: dict(v) for k, v in stats.items()}))
        C.need(not holds, 'UNCHANGED_ONE_PERCENT_SOURCE_QUALITY_HOLD')

        # Formal pointer metadata is read once. Delete each matched pointer after
        # its original base checks; SQLite can reuse pages instead of retaining
        # a second full-population formal table alongside the completed base.
        formal = source_path(cfg['formal_record_index_reference']); before = identity(formal)
        handle = pq.ParquetFile(formal)
        try:
            needed = ['record_id', 'molecule_id', 'record_payload_sha256', 'total_atoms']
            C.need(set(needed) <= set(handle.schema_arrow.names), 'ORIGINAL_FORMAL_POINTER_FIELDS')
            for batch in handle.iter_batches(batch_size=1024, columns=needed, use_threads=False):
                budget.check()
                for r in batch.to_pylist():
                    C.need(type(r['record_payload_sha256']) is str and re.fullmatch('[0-9a-f]{64}', r['record_payload_sha256']),
                           'REAL_FORMAL_PAYLOAD_SHA')
                    db.execute('INSERT INTO formal VALUES(?,?,?,?)',
                               (r['record_id'], r['molecule_id'], r['record_payload_sha256'], r['total_atoms']))
                    formal_rows += 1
                db.commit()
        finally: handle.close()
        C.need(identity(formal) == before, 'FORMAL_POINTER_CURRENT_FRAME')
        for pr, fid, lo, hi, expected_rows in base_parts:
            budget.check(); path = source_path(pr); frame = identity(path)
            source = sources[fid]; handle = pq.ParquetFile(path); rows = 0; last = -1
            try:
                columns = ['record_id', 'row_kind', 'task_code', 'file_id', 'physical_row',
                           'record_ordinal', 'owner_sha256', 'role_code', 'base_f64', 'base_json']
                for batch in handle.iter_batches(batch_size=16, columns=columns, use_threads=False):
                    budget.check(); batch_rows = batch.to_pylist()
                    owners = lookup_batch(canonical, [r['record_id'] for r in batch_rows])
                    for r in batch_rows:
                        owner = owners.get(r['record_id'])
                        C.need(r['row_kind'] == 'base' and r['task_code'] == 255 and r['file_id'] == fid
                               and lo <= r['physical_row'] < hi and r['physical_row'] > last,
                               'ORIGINAL_BASE_PART_TASK_AND_PHYSICAL_ORDER')
                        last = r['physical_row']
                        C.need(owner is not None and owner['record_ordinal'] == r['record_ordinal']
                               and owner['job_id'] == source['source_job_id'] and K.owner_signature(owner) == r['owner_sha256']
                               and B.ROLES[owner['new_role']] == r['role_code'] and 0 <= r['record_ordinal'] < N,
                               'ORIGINAL_BASE_CANONICAL_OWNER_AND_ROLE')
                        pool = [struct.unpack_from('<d', r['base_f64'], i)[0] for i in range(0, len(r['base_f64']), 8)]
                        g = B.decode(r['base_json'], pool); z = g['atomic_numbers']
                        pointer = db.execute('SELECT mol,payload,natoms FROM formal WHERE rid=?', (r['record_id'],)).fetchone()
                        C.need(pointer is not None and pointer[0] == owner['molecule_id']
                               and pointer[1] == g['source_payload_sha256'] and pointer[2] == owner['total_atoms'],
                               'ORIGINAL_FORMAL_BASE_PAYLOAD_OWNER')
                        usable = (type(z) is list and len(z) == owner['total_atoms']
                                  and all(type(v) is int and 1 <= v <= 118 for v in z)
                                  and hashlib.sha256(b''.join(struct.pack('<q', v) for v in z)).hexdigest() == g['native_atom_order_sha256']
                                  and g['geometry_status'] == 'ORIGINAL_PM7_GEOMETRY')
                        base_pending += not usable
                        packed = b''.join(struct.pack('<q', v) for v in z) if usable else None
                        db.execute('INSERT INTO base VALUES(?,?,?,?,?,?)',
                                   (r['record_ordinal'], r['record_id'], packed, r['base_json'], r['owner_sha256'], int(usable)))
                        db.execute('DELETE FROM formal WHERE rid=?', (r['record_id'],))
                        db.execute('INSERT OR IGNORE INTO molecules VALUES(?)', (owner['molecule_id'],))
                        rows += 1; base_rows += 1
                    db.commit()
            finally: handle.close()
            C.need(identity(path) == frame and rows == expected_rows, 'FIRST_BASE_READ_STABLE_FRAME_AND_PRODUCER_ROWCOUNT')
        C.need(base_rows == N and db.execute('SELECT count(*) FROM molecules').fetchone()[0] == 1220466,
               'UNIQUE_BASE_ORDINAL_RID_AND_CANONICAL_DOMAIN_COMPLETE')
        db.execute('DROP TABLE formal'); db.commit(); db.close(); db = None
        C.need(identity(canonical_path) == canonical_frame, 'CLOSED_CANONICAL_METADATA_FRAME_UNCHANGED')
        return dict(schema=SCHEMA, status=STATUS, config=I.small_ref(cfg['config_path']), job_id=str(proof['job_id']),
                    mode='full', records=N, molecules=1220466, task_rows=N * 14, base_rows=base_rows, parts=parts,
                    field_map_reference=cfg['field_map_reference'], element_basis=cfg['element_basis'],
                    canonical_index=cfg['canonical_index'], logical_group_plan_reference=cfg['logical_group_plan_reference'],
                    source_inventory_reference=cfg['source_inventory_reference'], field_stats={k: dict(v) for k, v in stats.items()},
                    physical_classifications={k: dict(v) for k, v in physical.items()}, quality_hold_fields=[], errors=[],
                    base_geometry_pending_records=base_pending, formal_pointer_rows_observed=formal_rows, fixture_gate=gate,
                    coverage_basis='ORIGINAL_CANONICAL_UNIQUE_MAPPING_AND_CLOSED_PRODUCER_PHYSICAL_INTERVAL_TASK_MASS',
                    producer_closed_window_evidence_reused=True, producer_part_reopen_bits_verified=True,
                    producer_typed_stream_digests_reused=True, independent_numeric_replay_performed=False,
                    independent_label_ordinal_bitmap_performed=False, label_typed_values_reopened=False,
                    input_whole_file_hashes_recomputed=False, base_Z_first_read_performed=True,
                    all14task_and_base_mass_from_closed_producer_evidence=True, base_ordinal_exact_once_first_read=True,
                    old1904_state='TIMEOUT', old_UNKNOWN_or_RESERVED_promoted=False,
                    final_mask_release=False, final_Common_D4=False, normalization_completed=False,
                    native_text_precision_or_frame_verified=False, joint_model_policy_release_reference=None)
    finally:
        canonical.close()
        if db is not None: db.close()
