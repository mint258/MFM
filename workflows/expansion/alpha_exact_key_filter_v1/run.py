"""One allocated Alpha exact-key index and complete corrected-pool shard filter."""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import traceback
from ..alpha_runtime_v1 import common as Q, profile
from ..alpha_runtime_v1.guard import Guard
from ..alpha_all11_index_v3.reader import Reader, strict, S
from ..alpha_closed500_handoff_v1.sql import SQLStopper, literal, load_sqlite_table
from ..pubchem_generic_recovery_overlay_v1 import reader as population
from .core import POLICY, REQUIRED, disposition, candidate_census_sql, eligible_sql, locator, json_line
from .storage import Storage, write_shards


SCHEMA = 'ALPHA_EXACT_KEY_FULL_POOL_FILTER_PLAN_V1'
SCOPE = 'alpha_exact_key_full_pool_filter_v1'


def admit(plan, proof, plan_path, proof_path):
    actual = profile.admit(plan, minimum_workers=16)
    request = proof['request']
    Q.need(plan['schema'] == SCHEMA and plan['scope_key'] == request['scope_key'] == SCOPE
           and plan['policy'] == POLICY, 'Explicit new user-authorized exact-key-only policy')
    Q.need(request['producer_plan_reference'] == Q.reference(plan_path)
           and request['execution_argv'] == plan['execution_argv']
           and sys.argv[-4:] == ['--plan', str(plan_path), '--startup-proof', str(proof_path)]
           and request['execution_argv'][-4:] == sys.argv[-4:], 'Exact allocated driver command')
    Q.need(proof['uid'] == plan['uid'] == os.getuid() == 1264
           and proof['endpoint'] == plan['endpoint'] == Q.ENDPOINT
           and str(proof['job_id']) == actual['job_id'] == os.environ['SLURM_JOB_ID']
           and proof['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
           'Actual Alpha allocation/UID/boot required')
    for file in Path(__file__).parent.glob('*.py'):
        ref = Q.reference(file)
        Q.need(ref in request['source_references'] and ref in plan['code_references'],
               'Actual new driver sources pinned before DATA')
    for module in (profile, Q, population, sys.modules[Reader.__module__],
                   sys.modules[Guard.__module__], sys.modules[SQLStopper.__module__]):
        ref = Q.reference(module.__file__)
        Q.need(ref in request['source_references'] and ref in plan['code_references'],
               'Actual borrowed source reader/runtime/SQL module must be startup pinned')
    Q.need(plan['active_output_limit_bytes'] <= 8_000_000_000
           and 0 < plan['spill_limit_bytes'] <= 4_000_000_000
           and 0 < plan['duckdb_memory_bytes'] <= 64 << 30
           and plan['software_rss_budget_bytes'] <= 88 << 30
           and plan['minimum_node_available_bytes'] >= 24 << 30,
           'Explicit bounded active output, SQL memory and real node reserve')
    return actual


def located_rows(reader, ref):
    """Same original body read and whole SHA, plus exact physical line witnesses."""
    with reader.held(ref) as (stream, path, replica, before):
        digest = hashlib.sha256(); size = count = 0
        for raw in stream:
            Q.need(raw.endswith(b'\n'), 'Every original identity line must be closed')
            offset = size; size += len(raw); count += 1; digest.update(raw)
            yield strict(raw), count, offset, raw, replica
            if count % 4096 == 0:
                reader.check()
        if 'rows' in ref:
            Q.need(count == ref['rows'], 'Complete original identity-part row census')
        reader.done(ref, path, replica, before, digest, size, count)


def audited_exclusions(reader, plan, stream):
    """Optional original-audit projection; exact IDs only, never a pattern veto."""
    selected = set(); count = 0
    for ref in plan.get('audited_structure_exclusion_references', []):
        for row, ordinal, offset, raw, replica in located_rows(reader, ref):
            Q.need(row['dataset'] in REQUIRED and type(row['source_id']) is str and row['source_id']
                   and row.get('role') and type(row.get('subdataset', '')) is str
                   and {'source_reference', 'row_ordinal_1based', 'source_record_sha256'} <= set(row)
                   and type(row['row_ordinal_1based']) is int and row['row_ordinal_1based'] > 0
                   and len(row['source_record_sha256']) == 64,
                   'Audited unresolved record must retain actual original physical locator and body SHA')
            selected.add((row['dataset'], row['source_id']))
            value = dict(row, disposition='AUDITED_UNRESOLVED_STRUCTURE_NO_VETO_OR_EVALUATION',
                         audit_projection_reference=ref, audit_projection_ordinal_1based=ordinal,
                         audit_projection_byte_offset=offset,
                         audit_projection_record_sha256=hashlib.sha256(raw).hexdigest(),
                         actual_audit_replica_reference=replica)
            stream.write(json_line(value)); count += 1
    return selected, count


def build_index(reader, plan, out, store):
    manifest = reader.json(plan['source_manifest_reference'])
    sources = manifest['sources']
    Q.need(len(sources) == len(REQUIRED) and {s['dataset'] for s in sources} == REQUIRED,
           'All original eleven source families; PDBbind removal is a physical subdataset operation')
    path = out / 'excluded_exact_keys.sqlite'
    exclusions = out / 'eval_exclusions.jsonl'
    store.active.update((path, exclusions))
    db = sqlite3.connect(':memory:')
    db.execute('PRAGMA journal_mode=MEMORY'); db.execute('PRAGMA cache_size=-524288')
    db.execute('PRAGMA temp_store=MEMORY')
    db.execute('CREATE TABLE excluded(kind TEXT,key TEXT,dataset TEXT,PRIMARY KEY(kind,key,dataset)) WITHOUT ROWID')
    counts = {}; audit_rows = 0
    try:
        with exclusions.open('xb') as stream:
            unresolved, imported_audit_rows = audited_exclusions(reader, plan, stream)
            for source in sources:
                refs = source.get('identity_parts') or [source['identities']]
                Q.need(refs and all(ref and type(ref.get('rows')) is int and ref['rows'] > 0 for ref in refs),
                       'Every original strict5 part has its actual complete row count')
                total = 0; kinds = collections.Counter(); roles = collections.Counter(); subdatasets = collections.Counter(); batch = []
                for ref in refs:
                    for row, ordinal, offset, raw, replica in located_rows(reader, ref):
                        Q.need(row['role'] in source['required_roles']
                               and row.get('subdataset', '') in source.get('required_subdatasets', ['']),
                               'Original source role/subdataset must remain explicit')
                        status, keys = disposition(source['dataset'], row, unresolved)
                        batch.extend(keys); total += 1; kinds[status] += 1
                        roles[row['role']] += 1; subdatasets[row.get('subdataset', '')] += 1
                        if status != 'EXACT_KEYED':
                            value = locator(source, ref, replica, ordinal, offset, raw, row)
                            value.update(disposition=status, structure_veto_emitted=False,
                                         excluded_from_downstream_evaluation=True)
                            stream.write(json_line(value)); audit_rows += 1
                        if total % 4096 == 0:
                            db.executemany('INSERT OR IGNORE INTO excluded VALUES(?,?,?)', batch)
                            batch = []; db.commit(); store.check()
                            pages = db.execute('PRAGMA page_count').fetchone()[0]
                            page_size = db.execute('PRAGMA page_size').fetchone()[0]
                            Q.need(pages * page_size < 2_000_000_000, 'In-memory exact-key index must stay below 2GB')
                if batch:
                    db.executemany('INSERT OR IGNORE INTO excluded VALUES(?,?,?)', batch)
                db.commit()
                Q.need(total == sum(ref['rows'] for ref in refs) == sum(kinds.values()),
                       'Every original strict5 row has exactly one scientific disposition')
                counts[source['dataset']] = dict(original_identity_rows=total, dispositions=dict(kinds),
                                                 roles=dict(roles), subdatasets=dict(subdatasets))
                print(json_line(dict(event='EXACT_KEY_SOURCE_CLOSED', dataset=source['dataset'],
                                     counts=counts[source['dataset']])).decode().strip(), flush=True)
            stream.flush(); os.fsync(stream.fileno())
        Q.need(db.execute("SELECT count(*) FROM excluded WHERE kind NOT IN ('full','wp5')").fetchone()[0] == 0,
               'No composition/lower-bound/wildcard index entries')
        key_counts = db.execute('SELECT kind,dataset,count(*) FROM excluded GROUP BY kind,dataset').fetchall()
        Q.need(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'Closed native index integrity')
        db.commit()
        pages = db.execute('PRAGMA page_count').fetchone()[0]
        page_size = db.execute('PRAGMA page_size').fetchone()[0]
        Q.need(pages * page_size < 2_000_000_000, 'Complete in-memory index stays below2GB')
        target = sqlite3.connect(path)
        try:
            db.backup(target, pages=8192, progress=lambda *unused: store.check())
            Q.need(target.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'Actual one-time closed index backup integrity')
            target.commit()
        finally:
            target.close()
    finally:
        db.close()
    Q.need(all(not Path(str(path) + s).exists() for s in ('-wal', '-shm', '-journal')), 'Closed index has no writers/sidecars')
    Q.need(path.stat().st_size < 2_000_000_000, 'Actual backed-up index remains below2GB')
    store.check()
    index = store.close_file(path, role='EXACT_KEY_INDEX')
    audit = store.close_file(exclusions, rows=audit_rows + imported_audit_rows, role='DOWNSTREAM_EVALUATION_EXCLUSIONS')
    return index, audit, counts, key_counts


def filter_pool(plan, pool, index, out, store):
    import duckdb
    import pyarrow as pa
    db = duckdb.connect(':memory:')
    db.execute('SET threads=' + str(plan['workers']))
    db.execute('SET memory_limit=' + literal(str(plan['duckdb_memory_bytes']) + 'B'))
    db.execute('SET temp_directory=' + literal(store.spill))
    db.execute('SET max_temp_directory_size=' + literal(str(plan['spill_limit_bytes']) + 'B'))
    db.execute('SET preserve_insertion_order=false')
    monitor = SQLStopper(db, store.check)
    source = sqlite3.connect(Path(index['path']).as_uri() + '?mode=ro', uri=True)
    witnesses = []
    try:
        load_sqlite_table(db, source, 'excluded', ('kind', 'key', 'dataset'),
                          (pa.string(), pa.string(), pa.string()), store.check)
        db.execute("CREATE TABLE keys_full AS SELECT DISTINCT key FROM excluded WHERE kind='full'")
        db.execute("CREATE TABLE keys_wp5 AS SELECT DISTINCT key FROM excluded WHERE kind='wp5'")
        db.execute('DROP TABLE excluded')
        witnesses = population.bind(db, pool, store.check)
        census = db.execute(candidate_census_sql()).fetchone()
        Q.need(census == (109875599, 109875599, 109875599, 0)
               and pool['unique_full_keys'] == 109875599,
               'Actual complete corrected pool, valid original full/WP5 and unique CID/FullKey')
        original_schema = db.execute('SELECT * FROM candidates LIMIT 0').fetch_arrow_table().schema
        batches = db.execute(eligible_sql()).fetch_record_batch(131072)
        parts, eligible, schema = write_shards(batches, out / 'eligible_parts', store,
                                             target_bytes=plan.get('shard_target_bytes', 128 << 20),
                                             max_rows=plan.get('shard_max_rows', 1_000_000))
        Q.need(eligible == 0 or schema == original_schema, 'Every original typed candidate field/type preserved')
        Q.need(0 <= eligible <= census[0], 'Exact complete pool mass conservation')
        population.finish(witnesses); store.check()
        return dict(input_unique_molecules=census[0], unique_input_cids=census[1],
                    unique_input_full_keys=census[2], invalid_input_identity_rows=census[3],
                    eligible_molecules=eligible, excluded_molecules=census[0] - eligible,
                    output_unique_identity_proof='TWO_ANTI_JOINS_ARE_A_SUBSET_OF_VALIDATED_UNIQUE_INPUT',
                    candidates=parts, candidate_columns=[dict(name=f.name, arrow_type=str(f.type)) for f in original_schema],
                    fingerprint_partition=dict(column='ecfp4_2048_hex', arrow_type='string',
                                               rule='FIRST_LOWERCASE_HEX_NIBBLE', buckets=list('0123456789abcdef'),
                                               rows_by_bucket={key: sum(p['rows'] for p in parts if p['fp_bucket'] == key)
                                                               for key in '0123456789abcdef'},
                                               all_emitted_FP_strings_validated_lowerhex512=True,
                                               all_identity_rows_retained=True, FP_deduplication_performed=False),
                    source_physical_witnesses=witnesses,
                    original_candidate_fields_and_types_preserved=True,
                    input_body_whole_SHA_recomputed=False,
                    input_historical_SHA_and_closed_inode_proof_reused=True)
    finally:
        monitor.close(); source.close(); db.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', required=True, type=Path)
    p.add_argument('--startup-proof', required=True, type=Path)
    args = p.parse_args(); plan = Q.load(args.plan); proof = Q.load(args.startup_proof)
    actual = admit(plan, proof, args.plan, args.startup_proof)
    policy_ref = plan['policy_authority_reference']
    Q.need(policy_ref['bytes'] <= 2 << 20, 'Actual user instruction archive must be small')
    Q.verify(policy_ref)  # User authorization provenance, not another per-job approval.
    out = Path(plan['output_directory']); Q.need(not out.exists(), 'Fresh versioned output; preserve all previous jobs')
    guard = Guard(plan); store = None; started = time.time()
    try:
        out.mkdir(mode=0o700)
        store = Storage(out, guard.check, Q.reference, plan['active_output_limit_bytes'])
        import io
        import unittest
        from . import test_core, test_native
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m)
                                   for m in (test_core, test_native))
        log = io.StringIO()
        tests = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        Q.need(tests.testsRun == 4 and tests.wasSuccessful() and not tests.skipped,
               'Four actual source/SQL/shard fixtures must pass before full DATA')
        print(json_line(dict(event='SOURCE_FIXTURES', tests=tests.testsRun, errors=len(tests.errors),
                             failures=len(tests.failures), transcript=log.getvalue())).decode().strip(), flush=True)
        from ..portable_sources_v1.transport import bind_plan
        bind_plan(plan)
        reader = Reader(plan, store.check)
        index, audit, sources, key_counts = build_index(reader, plan, out, store)
        pool = population.validate_header(Q.load(Q.verify(plan['source_pool_receipt_reference'])))
        result = filter_pool(plan, pool, index, out, store)
        for token, before in reader.verified.items():
            source_path, _ = reader.resolve(json.loads(token))
            Q.need(S.frame(source_path.stat()) == before, 'Original identity/source metadata frame changed before final closure')
        active_peak = store.peak
        store.close(); store = None
        Q.write(out / 'manifest.json', dict(schema='PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1', status='COMPLETE',
                policy=POLICY, population_version=pool['population_version'],
                policy_authority_reference=policy_ref,
                filter_version='full-wp5-only-no-pdbbind-20261104-v1',
                source_pool_receipt=plan['source_pool_receipt_reference'],
                source_manifest_reference=plan['source_manifest_reference'],
                parent_transport_manifest=plan['parent_transport_manifest'],
                audited_structure_exclusion_references=plan.get('audited_structure_exclusion_references', []),
                original_identity_source_dispositions=sources, exact_index_key_counts=key_counts,
                exact_index=index, eval_exclusions=audit, source_consumption=reader.consumption,
                closed_files_journal=Q.reference(out / 'closed_files.jsonl'),
                aliases_relation=pool['aliases_relation'], aliases_preserved_by_reference=True,
                actual_parent=actual, plan_reference=Q.reference(args.plan),
                startup_proof_reference=Q.reference(args.startup_proof), runtime=guard.receipt(),
                elapsed_seconds=time.time() - started, downstream_targets_consumed=False,
                peak_actual_active_output_and_spill_bytes=active_peak,
                active_output_limit_bytes=plan['active_output_limit_bytes'],
                source_tests=dict(tests=tests.testsRun, failures=len(tests.failures), errors=len(tests.errors)),
                chemistry_recomputed=False, old_population_or_baselines_modified=False,
                no_new_per_job_Root_acceptance_required=True, **result))
        print(json_line(dict(event='EXACT_KEY_FULL_POOL_COMPLETE', manifest=str(out / 'manifest.json'),
                             eligible_molecules=result['eligible_molecules'], excluded_molecules=result['excluded_molecules'])).decode().strip(), flush=True)
    except BaseException as exc:
        if out.is_dir():
            Q.write(out / 'failure.json', dict(error=repr(exc), traceback=traceback.format_exc(),
                                              partials_preserved=True, previous_outputs_modified=False))
        raise
    finally:
        if store is not None:
            store.close()
        guard.close()


if __name__ == '__main__':
    main()
