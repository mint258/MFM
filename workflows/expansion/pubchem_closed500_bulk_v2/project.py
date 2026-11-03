"""Columnar exact accepted projection; every closed fragment is independently resumable."""
from __future__ import annotations
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import multiprocessing as mp
import os
from pathlib import Path
import time
import uuid

from .common import CATEGORIES, DigestReader, canonical, load, need, reference, resource_check, verify, write_new
from .plan import validate_plan
from .schema import original_schema


def frequencies(array):
    import pyarrow.compute as pc
    return {item['values']: item['counts'] for item in pc.value_counts(array).to_pylist()}


def closed_fragment(directory, spec, verify_body=True):
    manifest = Path(directory) / spec['fragment_id'] / 'complete.json'
    if not manifest.exists():
        return None
    receipt = load(manifest)
    need(receipt['schema'] == 'PUBCHEM_CLOSED_FRAGMENT_PROJECTION_V2' and receipt['source_fragment'] == spec, 'Resume checkpoint belongs to a different source fragment')
    need(receipt['all_source_counts'] == spec['counts'] and receipt['input_rows'] == spec['rows'] and receipt['accepted_rows'] == spec['counts']['accepted'], 'Resume checkpoint row conservation differs')
    need(receipt['source_sha256'] == spec['Parquet_reference']['sha256'], 'Resume checkpoint did not verify the exact original bytes')
    if verify_body:
        verify(receipt['accepted_parquet'])
    return receipt


def project_fragment(spec, directory, batch_rows=8192):
    """No scientific re-evaluation, journal replay, JSON parse, or floating conversion."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    directory = Path(directory)
    completed = closed_fragment(directory, spec)
    if completed is not None:
        return completed
    unit = directory / spec['fragment_id']
    attempt = unit / ('attempt_' + uuid.uuid4().hex)
    attempt.mkdir(parents=True, exist_ok=False)
    source = spec['Parquet_reference']
    destination = attempt / 'accepted.parquet'
    expected = original_schema()
    output_schema = expected.append(pa.field('cid', pa.int64())).append(pa.field('source_fragment_id', pa.string()))
    counts, first_rules, overlap_rules, technical_codes = Counter({key: 0 for key in CATEGORIES}), Counter(), Counter(), Counter()
    next_ordinal, accepted_rows = spec['first_ordinal'], 0
    started = time.monotonic()
    with Path(source['path']).open('rb', buffering=1 << 20) as raw:
        digest = DigestReader(raw, source)
        parquet = pq.ParquetFile(digest)
        need(parquet.schema_arrow.equals(expected, check_metadata=True), 'Original stored Arrow schema changed')
        with pq.ParquetWriter(destination, output_schema, compression='zstd', use_dictionary=True, write_statistics=True) as writer:
            for batch in parquet.iter_batches(batch_size=batch_rows, use_threads=False):
                table = pa.Table.from_batches([batch])
                ordinals = table['ordinal'].combine_chunks()
                need(ordinals.null_count == 0 and len(ordinals) > 0 and ordinals[0].as_py() == next_ordinal, 'Source row/ordinal continuity changed')
                if len(ordinals) > 1:
                    need(pc.all(pc.equal(pc.subtract(ordinals.slice(1), ordinals.slice(0, len(ordinals) - 1)), 1)).as_py(), 'Noncontiguous source ordinals inside Arrow batch')
                next_ordinal += len(ordinals)
                categories = table['category'].combine_chunks()
                need(categories.null_count == 0, 'Null category cannot become a chemical exclusion')
                observed = frequencies(categories)
                need(set(observed) <= set(CATEGORIES), 'Unknown source category')
                counts.update(observed)
                rejected = table.filter(pc.equal(table['category'], 'chemReject'))
                if len(rejected):
                    reasons = rejected['legacy_reasons'].combine_chunks()
                    need(reasons.null_count == 0 and pc.all(pc.greater(pc.list_value_length(reasons), 0)).as_py(), 'Chemical reject requires original rule evidence')
                    first_rules.update(frequencies(pc.list_element(reasons, 0)))
                    overlap_rules.update(frequencies(pc.list_flatten(reasons)))
                unresolved = table.filter(pc.equal(table['category'], 'technicalUnresolved'))
                if len(unresolved):
                    technical_codes.update(frequencies(pc.list_flatten(unresolved['technical_codes'].combine_chunks())))
                accepted = table.filter(pc.equal(table['category'], 'accepted'))
                if not len(accepted):
                    continue
                need(accepted['full_key'].null_count == accepted['wp5_key'].null_count == accepted['full_dispatcher_result_json'].null_count == 0, 'Accepted original identity/payload cannot be null')
                cid = pc.cast(accepted['cid_source_ascii'], pa.int64(), safe=True)
                need(cid.null_count == 0 and pc.all(pc.greater(cid, 0)).as_py(), 'Accepted positive CID required')
                projected = accepted.append_column('cid', cid).append_column('source_fragment_id', pa.array([spec['fragment_id']] * len(accepted)))
                need(projected.schema.equals(output_schema, check_metadata=True), 'Projection must preserve every original typed field')
                writer.write_table(projected, row_group_size=batch_rows)
                accepted_rows += len(accepted)
        need(next_ordinal == spec['last_ordinal'] + 1 and dict(counts) == spec['counts'] and sum(counts.values()) == spec['rows'], 'Every original source row and all categories must conserve')
        source_sha = digest.finish()
        parquet.close()
        digest.close()
    parquet_ref = reference(destination)
    receipt = {'schema': 'PUBCHEM_CLOSED_FRAGMENT_PROJECTION_V2', 'status': 'COMPLETE_ACCEPTED_PROJECTION_NO_RELEASE', 'source_fragment': spec, 'source_sha256': source_sha, 'source_whole_SHA_verified_on_same_FD': True, 'input_rows': spec['rows'], 'all_source_counts': dict(counts), 'accepted_rows': accepted_rows, 'chemical_first_rule_counts': dict(first_rules), 'chemical_overlap_rule_counts': dict(overlap_rules), 'technical_reason_counts': dict(technical_codes), 'accepted_parquet': parquet_ref, 'all_original_Arrow_fields_and_F64_preserved': True, 'original_payload_JSON_text_preserved': True, 'scientific_functions_invoked': False, 'technical_UNKNOWN_is_not_chemical_exclusion': True, 'worker_pid': os.getpid(), 'wall_seconds': time.monotonic() - started}
    write_new(unit / 'complete.json', receipt)
    return receipt


def project(plan_path):
    plan = validate_plan(load(plan_path))
    out = Path(plan['output_directory'])
    out.mkdir(parents=True, exist_ok=True)
    directory = out / 'fragments'
    directory.mkdir(exist_ok=True)
    plan_ref = reference(plan_path)
    scope_path = out / 'projection_scope.json'
    scope = {'schema': 'PUBCHEM_BULK_PROJECTION_SCOPE_V2', 'coverage_reference': plan['coverage_reference'], 'fragments': plan['fragments'], 'output_directory': str(out)}
    if scope_path.exists():
        need(load(scope_path) == scope, 'Cannot reuse projection root for a different source scope')
    else:
        write_new(scope_path, scope)
    receipts, pending = [], []
    for spec in plan['fragments']:
        receipt = closed_fragment(directory, spec)
        if receipt is None:
            pending.append(spec)
        else:
            receipts.append(receipt)
    reused = len(receipts)
    resource_check(plan, out)
    context = mp.get_context('spawn')
    # Only one fragment per worker is scheduled. On failure, current workers finish
    # naturally and their committed checkpoints remain available to the next run.
    with ProcessPoolExecutor(max_workers=plan['workers'], mp_context=context) as pool:
        active, todo = {}, iter(pending)
        for unused in range(plan['workers']):
            spec = next(todo, None)
            if spec is not None:
                active[pool.submit(project_fragment, spec, str(directory), plan['batch_rows'])] = spec
        last_check = time.monotonic()
        while active:
            completed, unused = wait(active, timeout=30, return_when=FIRST_COMPLETED)
            if time.monotonic() - last_check >= 30:
                resource_check(plan, out)
                last_check = time.monotonic()
            for future in completed:
                spec = active.pop(future)
                receipt = future.result()
                receipts.append(receipt)
                print(canonical({'event': 'FRAGMENT_CLOSED', 'fragment_id': spec['fragment_id'], 'closed': len(receipts), 'total': len(plan['fragments']), 'accepted_rows': receipt['accepted_rows']}).decode(), flush=True)
                spec = next(todo, None)
                if spec is not None:
                    active[pool.submit(project_fragment, spec, str(directory), plan['batch_rows'])] = spec
    by_id = {item['source_fragment']['fragment_id']: item for item in receipts}
    need(len(by_id) == len(plan['fragments']), 'All projection checkpoints required')
    totals = {key: sum(item['all_source_counts'][key] for item in receipts) for key in CATEGORIES}
    need(totals == {key: sum(f['counts'][key] for f in plan['fragments']) for key in CATEGORIES}, 'Projection total category counts differ')
    result = {'schema': 'PUBCHEM_ALL_CLOSED_PROJECTIONS_V2', 'status': 'COMPLETE_ACCEPTED_PROJECTIONS_NO_POOL_RELEASE', 'plan_reference': plan_ref, 'coverage_reference': plan['coverage_reference'], 'fragment_count': len(receipts), 'reused_closed_fragments': reused, 'source_rows': sum(totals.values()), 'counts': totals, 'fragments': [reference(directory / f['fragment_id'] / 'complete.json') for f in plan['fragments']], 'accepted_parquets': [by_id[f['fragment_id']]['accepted_parquet'] for f in plan['fragments']], 'source_journals_replayed_again': False, 'chemistry_recomputed': False}
    # A resumed fully closed projection has the same immutable formal manifest.
    target = out / 'projection_manifest.json'
    if target.exists():
        previous = load(target)
        need(previous['accepted_parquets'] == result['accepted_parquets'] and previous['coverage_reference'] == result['coverage_reference'] and previous['counts'] == result['counts'], 'Closed projection manifest differs')
        return previous
    write_new(target, result)
    return result
