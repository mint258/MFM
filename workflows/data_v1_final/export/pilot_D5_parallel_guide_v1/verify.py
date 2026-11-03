"""One count/sample pass: at most 1000 records, no independent reader replay."""
import collections
import hashlib
import json
from . import contract as C, parquet_qa
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import verify as V, writer as W, wire, io as I

S = V.S


def run(db, stores, root, pool, budget, context=None):
    db.create_function('sample_rank', 2, lambda store, gid: V.O.rank_hash(20261025, store, gid), deterministic=True)
    count = db.execute("SELECT count(*) FROM exported WHERE kind='labels'").fetchone()[0]
    sample_count = min(1000, count)
    samples = db.execute("SELECT store,gid,parts FROM exported WHERE kind='labels' ORDER BY sample_rank(store,gid),store,gid LIMIT ?",
                         (sample_count,)).fetchall()
    C.need(len(samples) == sample_count, 'EXACT_SINGLE_FINITE1000_SAMPLE')
    bystore = collections.defaultdict(list)
    for row in samples:
        bystore[row['store']].append(row)
    cast_digest, counts, replay_tasks = hashlib.sha256(), [], {}
    for ref in stores:
        budget.check()
        manifest = I.load_data(ref, 8 << 20)
        side = manifest['f64_authority']['reference']
        # The writer already closed and hashed this file. Count and sample it
        # directly; do not hash or scan its full payload independently again.
        f64 = I.connect(side['path'], True)
        try:
            with W.Reader(manifest['path']) as reader:
                planned = db.execute('SELECT count(*) FROM exported WHERE store=?', (manifest['name'],)).fetchone()[0]
                C.need(reader.count == manifest['records'] == planned and reader.molecule_count == manifest['molecules'] and
                       f64.execute('SELECT count(*) FROM authority').fetchone()[0] == planned,
                       'CLOSED_STORE_DOMAIN_AND_F64_COUNTS_AGREE')
                for row in bystore.get(manifest['name'], []):
                    budget.check()
                    metadata, arrays = reader.get(row['gid'])
                    C.need(metadata['effective_role'] == 'TRAIN' and metadata['sample_role'] == C.ROLE and
                           metadata['training_excluded'] is True and metadata['source_scientific_mask_unchanged'] is True,
                           'FROZEN_HELD_TRAIN_DIAGNOSTIC_ROLE_AND_MASKS')
                    saved = f64.execute('SELECT metadata,payload,sha FROM authority WHERE rid=?', (row['gid'],)).fetchone()
                    C.need(saved is not None and saved['sha'] == metadata['permanent_F64_sidecar_record']['payload_sha256'],
                           'SAMPLED_F64_AUTHORITY_REFERENCE')
                    authority_arrays = S.unpack(saved['payload'])
                    authority_metadata = json.loads(saved['metadata'])
                    annotations = authority_metadata['source_projection_annotations']
                    granularity = authority_metadata['reason_granularity']
                    for tid in json.loads(row['parts']):
                        item = db.execute('SELECT payload FROM pieces WHERE gid=? AND part=?', (row['gid'], tid)).fetchone()
                        names = S.unpack(item['payload']).keys()  # Layout only, never expected numerical values.
                        expected = {name: authority_arrays[name] for name in names}
                        note = dict(annotations[tid])
                        note[tid] = granularity[tid]
                        locator = metadata['permanent_source_locators'][tid]
                        part = locator['typed_part_reference']
                        task = replay_tasks.setdefault(part['path'], (part, []))
                        task[1].append(dict(locator=locator, n=metadata['n_atoms'], tid=tid,
                                           packed=S.pack(expected, note)))
                    reference = metadata['source_projection_annotations_authority']
                    C.need(metadata['reason_granularity'] == granularity and
                           reference['file_name'] == metadata['permanent_F64_sidecar_record']['file_name'] and
                           reference['record_id'] == row['gid'] and reference['annotations_sha256'] ==
                           hashlib.sha256(W.CODEC.canonical_json(annotations)).hexdigest(),
                           'SAMPLED_NATIVE_ANNOTATIONS_AND_AUTHORITY_REFERENCE_AGREE')
                    cast_digest.update(wire.original_cast_compare(authority_arrays, arrays).encode())
                    C.need(all(not state['eligible'] for state in metadata['loss_eligibility'].values()), 'R674_LOSS_OFF')
                counts.append(dict(name=manifest['name'], records=planned, molecules=reader.molecule_count))
        finally:
            f64.close()
    original_results = []
    for work in replay_tasks.values():
        budget.check()
        original_results.append(parquet_qa.replay(work, context=context))
    C.need(sum(r['pieces'] for r in original_results) == sum(len(json.loads(r['parts'])) for r in samples),
           'EVERY_SAMPLED_FIELD_ACTUALLY_COMPARED_WITH_ORIGINAL_PARQUET')
    return I.save(root / 'actual_diagnostic_Source_QA.json', dict(
        schema='D5_SINGLE_1000_FIELD_QA_V1', available_label_records=count, source_roundtrip_records=sample_count,
        sample_rule='ALL_IF_LESS_THAN1000_ELSE_SINGLE_SEED20261025_RANDOM1000', store_counts=counts,
        original_once_F32_cast_digest=cast_digest.hexdigest(), single_field_comparison_pass=True,
        original_parquet_field_comparison=True, original_parquet_results=original_results,
        expected_values_from_actual_output_F64_authority=True, domain_numerical_self_comparison=False,
        full_F64_second_scan=False, second_independent_replay=False, independent_spawn_reader_pass=False,
        scientific_masks_unchanged=True, r73_original_ordered_records_retained=True, r674_loss_OFF=True, Model_ACK=False))
