"""External exact full-InChIKey/minimum-CID dedup; all CID aliases remain."""
from __future__ import annotations
import os
from pathlib import Path
import time
import threading
import uuid
from .common import canonical, load, need, reference, resource_check, verify, write_new


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def materialize(projection_manifest_path, output, workers, memory_bytes, resource_plan=None, inputs_verified=False):
    import duckdb
    import pyarrow.parquet as pq
    projection = load(projection_manifest_path)
    need(projection['schema'] == 'PUBCHEM_ALL_CLOSED_PROJECTIONS_V2' and projection['status'] == 'COMPLETE_ACCEPTED_PROJECTIONS_NO_POOL_RELEASE', 'Complete source projections required before dedup')
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    scope = {'schema': 'PUBCHEM_EXACT_MINCID_SCOPE_V2', 'source_projection': reference(projection_manifest_path), 'input_parquets': projection['accepted_parquets'], 'sql_semantics': 'minimum_positive_CID_per_full_InChIKey; retain_every_accepted_CID_alias'}
    scope_path = out / 'scope.json'
    if scope_path.exists():
        need(load(scope_path) == scope, 'Materialization scope changed on resume')
    else:
        write_new(scope_path, scope)
    final = out / 'receipt.json'
    if final.exists():
        closed = load(final)
        need(closed['scope'] == scope, 'Closed materialization belongs to another source scope')
        verify(closed['candidates'])
        verify(closed['aliases'])
        return closed
    # A failed previous merge is preserved under its own attempt name; source
    # projection checkpoints are reused. No ambiguous partial SQL is promoted.
    attempt = out / ('attempt_' + uuid.uuid4().hex)
    attempt.mkdir(exist_ok=False)
    candidates_path, aliases_path = attempt / 'candidates.parquet', attempt / 'aliases.parquet'
    if resource_plan:
        resource_check(resource_plan, Path(resource_plan['output_directory']))
    incoming = []
    for source in projection['accepted_parquets']:
        # The combined run has already verified every just-closed or resumed
        # fragment once. Standalone merge verifies its own input bodies once.
        incoming.append(str(Path(source['path']) if inputs_verified else verify(source)))
    before_frames = {p: (os.stat(p).st_size, os.stat(p).st_mtime_ns) for p in incoming}
    db = duckdb.connect(str(attempt / 'external_merge.duckdb'))
    started = time.monotonic()
    monitor_done = threading.Event()
    resource_errors = []
    def observe():
        while not monitor_done.wait(15):
            try:
                resource_check(resource_plan, Path(resource_plan['output_directory']))
            except BaseException as exc:
                resource_errors.append(repr(exc))
                # Interrupt only this connection's own SQL. No process signal,
                # source change, or promotion of partial output is involved.
                db.interrupt()
                return
    monitor = threading.Thread(target=observe, daemon=True) if resource_plan else None
    if monitor:
        monitor.start()
    try:
        db.execute('SET threads=' + str(int(workers)))
        db.execute('SET memory_limit=' + literal(str(int(memory_bytes)) + 'B'))
        db.execute('SET temp_directory=' + literal(attempt / 'spill'))
        db.execute('SET preserve_insertion_order=false')
        db.read_parquet(incoming, union_by_name=False).create_view('accepted')
        count, unique_cids, missing_keys = db.execute('SELECT count(*), count(DISTINCT cid), count(*) FILTER (WHERE full_key IS NULL OR cid IS NULL OR cid <= 0) FROM accepted').fetchone()
        need(count == projection['counts']['accepted'] and unique_cids == count and missing_keys == 0, 'Every accepted positive source CID must occur once')
        db.execute('CREATE TABLE winners AS SELECT full_key, min(cid) AS cid FROM accepted GROUP BY full_key')
        unique = db.execute('SELECT count(*) FROM winners').fetchone()[0]
        need(0 < unique <= count, 'Exact nonempty dedup cardinality required')
        db.execute('COPY (SELECT cid, full_key, ordinal AS source_ordinal, source_fragment_id FROM accepted) TO ' + literal(aliases_path) + ' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 65536)')
        # The complete original row is selected by the same key/minimum-CID
        # criterion as the original SQLite INSERT OR REPLACE implementation.
        # No floating arithmetic, molecular standardization, or JSON rewrite.
        db.execute('COPY (SELECT a.* FROM accepted AS a JOIN winners AS w ON a.full_key=w.full_key AND a.cid=w.cid) TO ' + literal(candidates_path) + ' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 65536)')
        observed_aliases = pq.ParquetFile(aliases_path).metadata.num_rows
        observed_candidates = pq.ParquetFile(candidates_path).metadata.num_rows
        need(observed_aliases == count and observed_candidates == unique, 'Actual Parquet counts differ from SQL cardinalities')
        # Independent relation checks of the actual exported aliases/candidates.
        db.read_parquet(str(candidates_path)).create_view('written_candidates')
        db.read_parquet(str(aliases_path)).create_view('written_aliases')
        stats = db.execute('SELECT count(*), count(DISTINCT full_key), count(DISTINCT cid) FROM written_candidates').fetchone()
        need(stats == (unique, unique, unique), 'Exported candidate keys/CIDs must be unique')
        mismatch = db.execute('SELECT count(*) FROM written_candidates c JOIN (SELECT full_key,min(cid) cid FROM written_aliases GROUP BY full_key) a USING(full_key) WHERE c.cid<>a.cid').fetchone()[0]
        need(mismatch == 0, 'Exported candidates must have the minimum CID among ALL aliases')
        db.execute('CHECKPOINT')
    finally:
        monitor_done.set()
        if monitor:
            monitor.join()
        db.close()
    need(not resource_errors, 'Actual resource observation stopped bulk SQL: ' + str(resource_errors))
    need(all((os.stat(p).st_size, os.stat(p).st_mtime_ns) == before_frames[p] for p in incoming), 'Immutable accepted projection changed during merge')
    if resource_plan:
        resource_check(resource_plan, Path(resource_plan['output_directory']))
    result = {'schema': 'PUBCHEM_EXACT_MINCID_CANDIDATE_POOL_V2', 'status': 'MATERIALIZED_UNFILTERED_NO_RELEASE', 'scope': scope, 'source_rows': projection['source_rows'], 'source_counts': projection['counts'], 'aliases_rows': count, 'unique_full_keys': unique, 'pubchem_duplicate_full_key': count - unique, 'candidates': reference(candidates_path), 'aliases': reference(aliases_path), 'original_SQL_minimum_CID_semantics': True, 'all_original_Arrow_fields_and_F64_preserved': True, 'original_payload_JSON_text_preserved': True, 'technical_UNKNOWN_is_not_chemical_exclusion': True, 'decontamination_filter_rank_or_training_release': False, 'scientific_functions_invoked': False, 'duckdb_version': duckdb.__version__, 'worker_pid': os.getpid(), 'wall_seconds': time.monotonic() - started}
    write_new(final, result)
    print(canonical({'event': 'UNFILTERED_MINCID_POOL_CLOSED', 'unique_full_keys': unique, 'aliases': count, 'receipt': str(final)}).decode(), flush=True)
    return result
