"""Original source replay and single-cast checks over the actual finite supplement."""
import collections
import hashlib
import json
import multiprocessing as mp
import concurrent.futures as cf
from . import contract as C
from workflows.data_v1_final.export.pilot_family_D3_fast55k_v1 import verify as V, writer as W, wire, io as I
from workflows.data_v1_final.export.family_export_day_v1 import verify as Readers

S = V.S


def run(db, stores, root, pool, budget):
    db.create_function('sample_rank', 2, lambda store, gid: V.O.rank_hash(20261025, store, gid), deterministic=True)
    count = db.execute("SELECT count(*) FROM exported WHERE kind='labels'").fetchone()[0]
    sample_count = min(10000, count)
    samples = db.execute("SELECT store,gid,parts FROM exported WHERE kind='labels' ORDER BY sample_rank(store,gid),store,gid LIMIT ?",
                         (sample_count,)).fetchall()
    C.need(len(samples) == sample_count, 'EXACT_FINITE_SOURCE_QA_SAMPLE_NO_FAKE_10K')
    bystore = collections.defaultdict(list)
    for row in samples:
        bystore[row['store']].append(row)
    replay, digest, closed = {}, hashlib.sha256(), []
    for ref in stores:
        manifest = I.load_data(ref, 8 << 20)
        side = manifest['f64_authority']['reference']
        I.add(side)
        I.require(side)
        f64 = I.connect(side['path'], True)
        with W.Reader(manifest['path']) as reader:
            C.need(reader.count == manifest['records'] and reader.molecule_count == manifest['molecules'] and
                   f64.execute('SELECT count(*) FROM authority').fetchone()[0] == reader.count,
                   'ALL_DIAGNOSTIC_RECORDS_HAVE_PERMANENT_ORIGINAL_F64')
            for row in bystore.get(manifest['name'], []):
                budget.check()
                metadata, arrays = reader.get(row['gid'])
                C.need(metadata['effective_role'] == 'TRAIN' and metadata['sample_role'] == C.ROLE and
                       metadata['training_excluded'] is True and metadata['source_scientific_mask_unchanged'] is True,
                       'REAL_SEEN_TRAIN_MOLECULE_DIAGNOSTIC_SAMPLE_NOT_TRAINING')
                saved = f64.execute('SELECT payload,sha FROM authority WHERE rid=?', (row['gid'],)).fetchone()
                C.need(saved is not None and hashlib.sha256(saved['payload']).hexdigest() == saved['sha'] ==
                       metadata['permanent_F64_sidecar_record']['payload_sha256'], 'PERMANENT_F64_AUTHORITY_HASH')
                source = {}
                for tid in json.loads(row['parts']):
                    item = db.execute('SELECT n,payload,source_locator FROM pieces WHERE gid=? AND part=?', (row['gid'], tid)).fetchone()
                    values = S.unpack(item['payload'])
                    C.need(not set(source) & set(values), 'NO_OVERLAPPING_TARGET_ARRAYS')
                    source.update(values)
                    locator = json.loads(item['source_locator'])
                    task = replay.setdefault(locator['typed_part_reference']['path'], (locator['typed_part_reference'], []))
                    task[1].append({'locator': locator, 'n': item['n'], 'tid': tid, 'packed': item['payload']})
                V.bit_equal(source, S.unpack(saved['payload']))
                digest.update(wire.original_cast_compare(source, arrays).encode())
                C.need(all(not state['eligible'] for state in metadata['loss_eligibility'].values()),
                       'R674_ALWAYS_LOSS_OFF_WITH_ORIGINAL_NUMERIC_MASKS')
        f64.close()
        closed.append({'reference': side, 'records': manifest['records']})
    results = []
    pending = {}
    tasks = iter(replay.values())
    exhausted = False
    while pending or not exhausted:
        while not exhausted and len(pending) < 32:
            try:
                task = next(tasks)
            except StopIteration:
                exhausted = True
                break
            budget.check()
            pending[pool.submit(V.replay, task)] = True
        if pending:
            done, _ = cf.wait(pending, timeout=1, return_when=cf.FIRST_COMPLETED)
            for future in done:
                pending.pop(future)
                results.append(future.result())
    C.need(sum(row['pieces'] for row in results) == sum(len(json.loads(row['parts'])) for row in samples),
           'EVERY_SAMPLED_ORIGINAL_SOURCE_PIECE_REPLAYED_BITS_MASK_REASONS')
    mids = [row[0] for row in db.execute("SELECT mid FROM molecules ORDER BY sample_rank('whole_MID',mid),mid LIMIT 16")]
    readers = []
    if mids:
        work = []
        for index, mid in enumerate(mids):
            paths = [(row[0], row[1]) for row in db.execute('SELECT s.path,e.gid FROM exported e JOIN stores s ON s.name=e.store JOIN geometries g ON g.gid=e.gid WHERE g.mid=? ORDER BY e.store,e.gid', (mid,))]
            work.append((index, [(mid, paths)]))
        context = mp.get_context('spawn')
        barrier = context.Barrier(len(work))
        with cf.ProcessPoolExecutor(max_workers=len(work), mp_context=context, initializer=Readers.read_initializer, initargs=(barrier,)) as reader_pool:
            readers = list(reader_pool.map(Readers.molecule_reader, work, chunksize=1))
        C.need(len({row['pid'] for row in readers}) == len(work) and all(row['all_handles_closed'] for row in readers),
               'ACTUAL_DISTINCT_FINITE_WHOLE_MID_READERS_NOT_REQUESTED_CPU_COUNT')
    result = {'schema': 'ACTUAL_D3_DIAGNOSTIC_SOURCE_QA_V1', 'available_label_records': count,
              'source_roundtrip_records': sample_count, 'sample_rule': 'ALL_IF_LESS_THAN10000_ELSE_ORIGINAL_SEED10000',
              'permanent_F64_sidecars': closed, 'original_once_F32_cast_digest': digest.hexdigest(),
              'source_piece_results': results, 'actual_spawn_reader_count': len(readers), 'spawn_readers': readers,
              'scientific_masks_unchanged': True, 'r73_original_ordered_records_retained': True,
              'r674_loss_OFF_not_numeric_mask_OFF': True, 'Model_ACK': False}
    return I.save(root / 'actual_diagnostic_Source_QA.json', result)
