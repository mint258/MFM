"""SOURCE-ONLY candidate: parallelize original store writes, never a runner.

Install beside the frozen single_job_v1 modules in a new isolated producer.
Not executed or syntax-tested. Admission, source closure, worker initialization,
quota accounting, final counts/1000-Parquet QA, delivery and Model ACK belong to
its existing parent. No test, queue, resource-policy or release framework here.

Input context keys: pieces_database, geometry_index_database,
D4_geometry_database, root, compiled, policy, plan, proof, metadata_factory, control.
The first three files must already be admitted closed sources. The pieces
cache may be changed ONLY between fully joined shard worker generations, if
release_payloads=True; its scientific inputs/configuration never change.
The caller supplies the original spawn initializer/arguments, which configure
original IO admissions in each spawned worker; this initializer then creates a
fresh worker-local StableOutputCensus and forwards actual budget.control to
runtime_budget.worker_check(control). Keep the existing single-thread BLAS env.

Automatic store continuation accepts only this writer's committed small meta
DBs. Import of an older serial writer's stores/counters is the parent's job;
file existence by itself never makes a store complete or supplies missing
eligibility counts. There is no global coverage check in a single-store task.
"""
import collections
import concurrent.futures as cf
import hashlib
import json
import multiprocessing as mp
import os
import pathlib
import sqlite3

from . import writer as W, payload_io as P, closed_domain_resume as Closed
from . import io as I, runtime_budget as Runtime
from workflows.data_v1_final.export.pilot_D5_parallel_guide_v1.resource import clone, ObjectProxy
from workflows.data_v1_final.export.lossless_sqlite_io_v1 import codec as GeometryCodec

MAX_WORKERS = 8
_WORKER_CONTEXT = None

def _initialize_writer(context, original_initializer, original_args):
    original_initializer(*original_args)
    # Constructed after spawn, once in this worker. No parent census object,
    # open FD, or lock is serialized into context or retained from the parent.
    census = Runtime.StableOutputCensus(pathlib.Path(context['root']))
    I.ACTIVE_CENSUS = census
    if P.I is not I:
        P.I.ACTIVE_CENSUS = census
    global _WORKER_CONTEXT
    _WORKER_CONTEXT = context


def _worker_one(task):
    W.C.need(_WORKER_CONTEXT is not None, 'ACTUAL_CONFIGURED_WRITER_CONTEXT')
    return write_one_store(task, _WORKER_CONTEXT)


def _source_paths(context):
    return tuple(pathlib.Path(context[key]).absolute() for key in
                 ('pieces_database', 'geometry_index_database', 'D4_geometry_database'))


def _frames(paths):
    return {str(path): I.identity(path) for path in paths}


def _open_input(context, *, worker):
    db = I.connect(context['pieces_database'], True)
    try:
        Closed.configure_views(db, context['geometry_index_database'], context['D4_geometry_database'])
        if worker:
            # 112+64+64 MiB, plus a separate 16 MiB partitions connection.
            for name, kib in (('main', 114688), ('geo_index', 65536), ('raw_geo', 65536)):
                db.execute('PRAGMA ' + name + '.cache_size=-' + str(kib))
        return db
    except BaseException:
        db.close()
        raise


def _task_identity(task):
    return [task[key] for key in ('name', 'kind', 'src', 'view', 'family', 'targets')]


def _metadata_path(context, task):
    return pathlib.Path(context['root']) / 'writer_metadata' / (task['name'] + '.sqlite')


def write_one_store(task, context):
    """Original one-store inner loop; independent writable metadata/output only."""
    W.C.need(context is not None, 'ACTUAL_CONFIGURED_WRITER_CONTEXT')
    source_paths = _source_paths(context)
    partition_path = pathlib.Path(task['partitions_database']).absolute()
    source_frames = _frames((*source_paths, partition_path))
    root = pathlib.Path(context['root'])
    compiled, policy, plan, proof = (context[key] for key in ('compiled', 'policy', 'plan', 'proof'))
    config = policy['export_configuration']
    name, kind, src, view, family, tid_text = _task_identity(task)
    tids = json.loads(tid_text)
    metadata_path = _metadata_path(context, task)
    W.C.need(not metadata_path.exists(), 'FRESH_SINGLE_STORE_METADATA_OR_EXPLICIT_CLOSED_META_IMPORT')
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    source = partitions = output = side = writer = None
    eligibility = collections.Counter()
    # These are the exact private bindings used by current payload_io.write.
    annotations = P.AnnotationIO(compiled, context.get('metadata_factory') or W.metadata)
    source_arrays = P.stage_source(reason_annotations=annotations.reason_annotations)
    geometry_arrays = clone(W.geometry_arrays, T=ObjectProxy(W.T, native_bonds=P.native_io.native_bonds))
    try:
        source = _open_input(context, worker=True)
        partitions = I.connect(partition_path, True)
        partitions.execute('PRAGMA cache_size=-16384')
        output = I.connect(metadata_path)
        output.executescript('CREATE TABLE exported(store TEXT,gid TEXT,kind TEXT,parts TEXT,PRIMARY KEY(store,gid));'
                            'CREATE TABLE stores(name TEXT PRIMARY KEY,path TEXT,ref TEXT);'
                            'CREATE TABLE task_identity(value TEXT);'
                            'CREATE TABLE eligibility(key TEXT PRIMARY KEY,n INTEGER);')
        output.execute('INSERT INTO task_identity VALUES(?)', (json.dumps(_task_identity(task)),))
        schema = {'kind': 'geometry'} if kind == 'geometry' else W.T.family_schema(compiled, family, src, tids)
        schema.update(contract_version='v3.0', bounded_pilot_acceptance_reference=plan['pilot_acceptance_reference'], bounded_source_projection_reference=plan['bounded_export_review_reference'],
                      D1_design_policy_reference=plan['D1_design_policy_reference'], D1_five_layer_reference=plan['D1_five_layer_reference'], actual_parent_job_id=str(proof['job_id']),
                      exact_codec_source_references=plan['codec_source_references'], full_Common_D6_release=False, Model_ACK=False, **W.C.capabilities(plan))
        path = root / name
        side = P.Sidecar(root / (name + '.authority_f64.sqlite'))
        writer = P.TrainingWriter(path, schema, map_bytes=config['map_bytes_per_store'])
        buffer = []
        buffer_bytes = 0
        # Only the frozen partitions DB is consulted here, never parent metadata.
        for (gid,) in partitions.execute('SELECT gid FROM partitions WHERE name=? ORDER BY gid', (name,)):
            Runtime.worker_check(context['control'])
            g = GeometryCodec.decode(source.execute('SELECT row FROM geometries WHERE gid=?', (gid,)).fetchone()[0])
            m = annotations.metadata(source, g)
            arrays = {}
            notes = {}
            locators = {}
            if W.C.native_mode(plan):
                ranks = {r[0]: r[1] for r in source.execute('SELECT kind,rank FROM orders WHERE gid=?', (gid,))}
                W.C.need(set(ranks) <= {'fixed_random'}, 'NO_UNAVAILABLE_NATIVE_ORDER_METADATA')
                m.update(**W.C.capabilities(plan), available_base_order_ranks=ranks,
                         ordered_base_only=g['parent_geometry_id'] is None and source.execute('SELECT aux FROM geometries WHERE gid=?', (gid,)).fetchone()[0] == 0,
                         unavailable_order_request='REFUSE_ENERGY_DIVERSITY_OR_LOWEST_ENERGY_RANK0_NOT_RELEASED')
            if kind == 'geometry':
                arrays = geometry_arrays(source, g)
            else:
                for tid in tids:
                    p = source.execute('SELECT payload,source_locator FROM pieces WHERE gid=? AND part=?', (gid, tid)).fetchone()
                    W.C.need(p is not None, 'ALL_ACTUAL_PARTITION_TARGETS_PRESENT')
                    a = source_arrays.unpack(p[0])
                    W.C.need(not set(arrays) & set(a), 'NO_OVERLAPPING_FAMILY_ARRAYS')
                    arrays.update(a)
                    notes.update(source_arrays.reason_annotations(p[0]))
                    locators[tid] = P.locator_json_loads(p[1])
                m.update(group_exposure_mask=config['group_exposure_mask'], family_exposure_mask=config['family_exposure_mask'], reason_granularity=notes,
                         reason_codebook_sha256=policy['reason_codebook_reference']['sha256'], permanent_source_locators=locators,
                         source_missing_positions={t: v['typed_missing_positions'] for t, v in locators.items()}, source_precision=policy['source_precision_policy'])
                target_policy = {}
                for tid in tids:
                    target_policy[tid] = dict(policy['target_policy'].get(tid, {}), actual_task_charge=locators[tid]['actual_task_charge'])
                m = annotations.annotate(m, arrays, schema, target_policy, {t: locators[t]['member_geometry_ids'] for t in tids})
                if W.C.native_mode(plan):
                    disabled = {tid: {'status': 'DISABLED_UNIT_UNSPECIFIED', 'eligible': False, 'numeric_mask_changed': False,
                                      'unit_status': 'UNKNOWN_ORIGINAL_SOURCE_SCHEMA', 'original_values_exported': True}
                                for tid in tids if any(x['field_key'] == 'D20.MolMR' for x in compiled['physical_targets'].get(tid, {}).get('members', []))}
                    if disabled:
                        W.C.need(all(target_policy[tid]['physical_policy_status'] == 'DISABLED_UNIT_UNSPECIFIED' for tid in disabled),
                                 'MOLMR_UNKNOWN_UNIT_ALWAYS_PHYSICAL_LOSS_OFF_NOT_VALUE_MASK_OR_FIELD_DELETE')
                        m['target_loss_exposure'] = disabled
                for tid, state in m['loss_eligibility'].items():
                    eligibility[tid + '/' + m['effective_role'] + '/' + state['status']] += 1
            m['actual_geometry_manifest_reference'] = plan['actual_geometry_manifest_reference']
            m['actual_field_geometry_claims_reference'] = policy['actual_cell_binding_reference']
            original_m = dict(m)
            m['permanent_F64_sidecar_record'] = side.put(original_m, arrays)
            buffer.append((m, arrays))
            buffer_bytes += sum(a.nbytes for a in arrays.values())
            if len(buffer) >= 64 or buffer_bytes >= 128 << 20:
                side.commit()
                writer.write_batch(buffer)
                buffer = []
                buffer_bytes = 0
            output.execute('INSERT INTO exported VALUES(?,?,?,?)', (name, gid, kind, json.dumps(tids)))
        if buffer:
            side.commit()
            writer.write_batch(buffer)
        f64 = side.finish()
        receipt = writer.finish()
        # These original finish/pin/save calls are the existing output hashes;
        # no input-domain SHA, extra readback or second store hash is added.
        side.close()
        side = None
        writer.close()
        writer = None
        manifest = {'name': name, 'path': str(path), 'kind': kind, 'geometry_source': src, 'view_id': view, 'family': family,
                    'manifest_reference': I.pin(path / 'manifest.json'), 'f64_authority': f64, **receipt, **W.C.capabilities(plan)}
        reference = I.save(root / (name + '.closed_store.json'), manifest)
        output.execute('INSERT INTO stores VALUES(?,?,?)', (name, str(path), json.dumps(reference)))
        output.executemany('INSERT INTO eligibility VALUES(?,?)', eligibility.items())
        output.commit()
    finally:
        if side is not None:
            side.close()
        if writer is not None:
            writer.close()
        for connection in (output, partitions, source):
            if connection is not None:
                connection.close()
    W.C.need(_frames((*source_paths, partition_path)) == source_frames, 'IMMUTABLE_INPUTS_UNCHANGED_DURING_SINGLE_STORE_WRITE')
    return {'name': name, 'metadata_path': str(metadata_path), 'store_reference': reference,
            'global_coverage_checked': False}


def _build_partitions(context, index, mids, path, budget):
    """Original thin partition loop, once per real <=5000 MID shard."""
    W.C.need(not path.exists(), 'FRESH_CURRENT_ATTEMPT_PARTITIONS_FILE')
    source = output = None
    try:
        source = _open_input(context, worker=False)
        output = I.connect(path)
        output.execute('CREATE TABLE partitions(name TEXT,gid TEXT,kind TEXT,src TEXT,view TEXT,family TEXT,targets TEXT,PRIMARY KEY(name,gid))')
        for mid in mids:
            budget.check()
            for gid, src, view in source.execute('SELECT gid,src,view FROM geometries WHERE mid=? AND selected=1 ORDER BY gid', (mid,)):
                domains = [('geometry', None, ())]
                byfamily = {}
                for (tid,) in source.execute('SELECT part FROM pieces WHERE gid=? ORDER BY part', (gid,)):
                    t = context['compiled']['ordered_record_targets'].get(tid) or context['compiled']['physical_targets'][tid]
                    byfamily.setdefault(t['family'], []).append(tid)
                domains.extend(('labels', family, tuple(tids)) for family, tids in sorted(byfamily.items()))
                for kind, family, tids in domains:
                    key = (index, kind, src, view, family, tids)
                    name = 'pilot_' + str(index).zfill(6) + '_' + hashlib.sha256(W.CODEC.canonical_json(key)).hexdigest()[:24]
                    output.execute('INSERT INTO partitions VALUES(?,?,?,?,?,?,?)', (name, gid, kind, src, view, family, json.dumps(tids)))
        output.commit()
        rows = output.execute('SELECT DISTINCT name,kind,src,view,family,targets FROM partitions ORDER BY name').fetchall()
        return [dict(zip(('name', 'kind', 'src', 'view', 'family', 'targets'), row), partitions_database=str(path)) for row in rows]
    finally:
        if output is not None:
            output.close()
        if source is not None:
            source.close()


def _merge_store(parent, result, task, context):
    """Merge only small output metadata; source DBs are never attached writable."""
    metadata_path = pathlib.Path(result['metadata_path'])
    W.C.need(metadata_path == _metadata_path(context, task), 'EXACT_STORE_METADATA_PATH')
    parent.execute('ATTACH DATABASE ? AS finished_store', (metadata_path.absolute().as_uri() + '?mode=ro&immutable=1',))
    merged=False
    try:
        identity = parent.execute('SELECT value FROM finished_store.task_identity').fetchall()
        rows = parent.execute('SELECT name,path,ref FROM finished_store.stores').fetchall()
        W.C.need(len(identity) == 1 and json.loads(identity[0][0]) == _task_identity(task)
                 and len(rows) == 1 and rows[0][0] == task['name'], 'ONE_ACTUALLY_FINISHED_MATCHING_STORE')
        reference = json.loads(rows[0][2])
        if 'store_reference' in result:
            W.C.need(reference == result['store_reference'], 'EXACT_WORKER_FINISHED_STORE_REFERENCE')
        eligibility = dict(parent.execute('SELECT key,n FROM finished_store.eligibility'))
        parent.execute('INSERT INTO exported SELECT * FROM finished_store.exported')
        parent.execute('INSERT INTO stores SELECT * FROM finished_store.stores')
        parent.execute('INSERT INTO parallel_store_completion VALUES(?,?,?)',
                       (task['name'], str(metadata_path), json.dumps(eligibility)))
        parent.commit()
        merged=True
        return reference
    except BaseException:
        parent.rollback()
        raise
    finally:
        parent.execute('DETACH DATABASE finished_store')
        if merged:os.unlink(metadata_path)


def _release_shard(context, first_mid, last_mid, budget):
    # Called only after executor.shutdown(wait=True) AND actual child exit=0.
    budget.check()
    source = I.connect(context['pieces_database'])
    try:
        Closed.configure_views(source, context['geometry_index_database'], context['D4_geometry_database'])
        source.execute('UPDATE pieces SET payload=? WHERE gid IN(SELECT gid FROM geometries WHERE mid>=? AND mid<=?)',
                       (b'', first_mid, last_mid))
        source.commit()
        incremental = source.execute('PRAGMA auto_vacuum').fetchone()[0] == 2
        if incremental:
            source.execute('PRAGMA incremental_vacuum')
            source.commit()
        return incremental
    finally:
        source.close()


def write_parallel(parent, root, compiled, policy, plan, proof, budget, *,
                   pieces_database, geometry_index_database, D4_geometry_database,
                   worker_initializer, worker_initargs, metadata_factory=None,
                   max_workers=MAX_WORKERS, release_payloads=True):
    """Parent writer helper; returns the original (store refs, eligibility).

    parent is a DISTINCT mutable metadata DB, already equipped with the same
    geometry/molecules TEMP VIEWs for the caller's unique finish_export pass.
    It must not retain an immutable ATTACH of pieces_database while release is
    enabled. Its exported/stores rows may contain only already-admitted output.
    The original Source executor must have been shut down before this helper.
    No fresh test, QA, hash replay, benchmark, rsync or submission occurs here.
    """
    W.C.need(type(max_workers) is int and 1 <= max_workers <= MAX_WORKERS, 'AT_MOST8_WRITERS_INSIDE_REAL16CPU_PARENT')
    W.C.need(callable(worker_initializer), 'ORIGINAL_CONFIGURING_SPAWN_INITIALIZER_REQUIRED')
    root = pathlib.Path(root)
    context = dict(pieces_database=str(pieces_database), geometry_index_database=str(geometry_index_database),
                   D4_geometry_database=str(D4_geometry_database), root=str(root), compiled=compiled,
                   policy=policy, plan=plan, proof=proof, metadata_factory=metadata_factory, control=budget.control)
    source_paths = _source_paths(context)
    databases = [(row[1], pathlib.Path(row[2]).absolute()) for row in parent.execute('PRAGMA database_list') if row[2]]
    W.C.need(all(not os.path.samefile(path, source_paths[0]) for _, path in databases), 'PARENT_METADATA_NEVER_WRITES_OR_RETAINS_SOURCE_DOMAIN')
    main = next(path for name, path in databases if name == 'main')
    W.C.need(all(not os.path.samefile(main, path) for path in source_paths), 'DISTINCT_MUTABLE_PARENT_METADATA_DATABASE')
    size = policy['export_configuration']['molecules_per_shard']
    W.C.need(type(size) is int and 1 <= size <= 5000, 'WHOLE_MID_INTERNAL_SHARDS_ONLY')
    parent.executescript('CREATE TABLE IF NOT EXISTS exported(store TEXT,gid TEXT,kind TEXT,parts TEXT,PRIMARY KEY(store,gid));'
                         'CREATE TABLE IF NOT EXISTS stores(name TEXT PRIMARY KEY,path TEXT,ref TEXT);'
                         'CREATE TABLE IF NOT EXISTS parallel_store_completion(name TEXT PRIMARY KEY,metadata_path TEXT,eligibility TEXT);')
    parent.commit()
    partition_root = root / 'writer_partitions'
    partition_root.mkdir(parents=True, exist_ok=True)
    (root / 'writer_metadata').mkdir(parents=True, exist_ok=True)
    index = 0
    last = ''
    while True:
        mids = [row[0] for row in parent.execute('SELECT mid FROM molecules WHERE mid>? ORDER BY mid LIMIT ?', (last, size))]
        if not mids:
            break
        budget.check()
        partition_path = partition_root / (str(proof['job_id']) + '_' + str(index).zfill(6) + '.sqlite')
        tasks = _build_partitions(context, index, mids, partition_path, budget)
        pending_tasks = []
        for task in tasks:
            old = parent.execute('SELECT ref FROM stores WHERE name=?', (task['name'],)).fetchone()
            if old is not None:
                W.C.need(parent.execute('SELECT 1 FROM parallel_store_completion WHERE name=?', (task['name'],)).fetchone() is not None,
                         'SERIAL_STORE_ELIGIBILITY_NOT_INVENTED_BY_PARALLEL_CONTINUATION')
                continue
            metadata_path = _metadata_path(context, task)
            if metadata_path.exists():
                # A previous candidate worker may have closed before its parent
                # merged it. An incomplete DB has no committed stores row and
                # fails _merge_store; it is never silently retried or accepted.
                _merge_store(parent, {'name': task['name'], 'metadata_path': str(metadata_path)}, task, context)
            else:
                pending_tasks.append(task)
        if pending_tasks:
            pool = cf.ProcessPoolExecutor(max_workers=max_workers, mp_context=mp.get_context('spawn'),
                                          initializer=_initialize_writer, initargs=(context, worker_initializer, tuple(worker_initargs)))
            processes = []
            try:
                pending = {}
                task_iter = iter(pending_tasks)
                def fill():
                    while len(pending) < max_workers:
                        try:
                            task = next(task_iter)
                        except StopIteration:
                            break
                        budget.check()
                        pending[pool.submit(_worker_one, task)] = task
                fill()
                while pending:
                    ready, _ = cf.wait(pending, timeout=1, return_when=cf.FIRST_COMPLETED)
                    budget.check(dispatch=False)
                    for future in ready:
                        task = pending.pop(future)
                        _merge_store(parent, future.result(), task, context)
                    fill()
            finally:
                processes = list(pool._processes.values())
                pool.shutdown(wait=True, cancel_futures=True)
            W.C.need(all(not process.is_alive() and process.exitcode == 0 for process in processes), 'ALL_SHARD_WRITER_PROCESSES_REALLY_EXITED')
        # No source-domain or partitions connection/worker survives this point.
        incremental = _release_shard(context, mids[0], mids[-1], budget) if release_payloads else False
        I.append(root / 'shard_checkpoints.jsonl', {'index': index, 'first_mid': mids[0], 'last_mid': mids[-1], 'molecules': len(mids),
                 'all_stores_and_f64_closed': True, 'parent_job_id': str(proof['job_id']), 'parallel_store_workers': max_workers,
                 'all_parallel_store_worker_processes_exited': True, 'internal_payloads_released_after_authority_closure': bool(release_payloads),
                 'source_locators_and_shapes_retained': True, 'incremental_vacuum_applied': incremental,
                 'global_coverage_checked': False})
        os.unlink(partition_path)
        last = mids[-1]
        index += 1
    eligibility = collections.Counter()
    for (text,) in parent.execute('SELECT eligibility FROM parallel_store_completion'):
        eligibility.update(json.loads(text))
    references = [json.loads(row[0]) for row in parent.execute('SELECT ref FROM stores ORDER BY name')]
    # The caller's ONE finish_export count/source-sample pass owns global
    # coverage. In particular no single-store subset pretends coverage=0.
    return references, dict(eligibility)