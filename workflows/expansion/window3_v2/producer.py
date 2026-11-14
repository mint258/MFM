"""Streaming taskbook-v2 UFF/D producer. Checks happen before the only write.

Restart uses completed chunks or the append-only interrupted chunk spool. A
started molecule without a result remains UNKNOWN; it is never regenerated.
No source-index rebuild, file digest, independent QA, or output reread.
"""
import argparse
import collections
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import json
import math
import multiprocessing
import os
from pathlib import Path
import random
import time
import uuid

from .kernel import Kernel, molecule_id
from .deadline import generate_limited
from . import stereo
from .capacity import protect

KERNEL = CONFIG = None


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.pending')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def physical_mask(values, bounds):
    source = [type(v) in (int, float) and math.isfinite(v) for v in values]
    result = source.copy()
    for i, value in enumerate(values):
        if not source[i]: continue
        low, high = bounds['lower'], bounds['upper']
        if ((low is not None and (value <= low if bounds['lower_exclusive'] else value < low))
                or (high is not None and value > high)):
            result[i] = False
    return source, result


def validate(packet):
    """Single producer check of identity, geometry, label and atom alignment."""
    if packet['molecule_id'] != molecule_id(packet['source']) or len(packet['conformers']) > 3:
        raise ValueError('ID_OR_MAX3_ALIGNMENT')
    d20 = packet['D20']
    if d20 and not (len(d20['names']) == len(d20['values']) == len(d20['valid_mask']) == 20):
        raise ValueError('D20_ALIGNMENT')
    n = len(packet['atomic_numbers'])
    for i, row in enumerate(packet['conformers']):
        if row['conformer_id'] != i or len(row['coordinates']) != n:
            raise ValueError('GEOMETRY_CONFORMER_ALIGNMENT')
        if any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in row['coordinates']):
            raise ValueError('NONFINITE_GEOMETRY')
        sasa = row['D3'].get('SASA_atom_A2')
        if sasa is not None and len(sasa) != n:
            raise ValueError('ATOM_SASA_ALIGNMENT')


def init(config):
    global CONFIG, KERNEL
    CONFIG = config
    import torch
    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1: torch.set_num_interop_threads(1)
    from rdkit import RDLogger
    RDLogger.DisableLog('rdApp.warning')
    KERNEL = Kernel(config['capsule'])


class Writer:
    def __init__(self):
        self.D20_SCHEMA, self.D3_SCHEMA = KERNEL.writer.D20_SCHEMA, KERNEL.writer.D3_SCHEMA

    @staticmethod
    def write_family_rows(rows, path, schema, metadata):
        import pyarrow as pa
        import pyarrow.parquet as pq
        # Preserve v1 family fields; obsolete digest slots are all null.
        table = pa.Table.from_pylist(rows, schema=schema)
        table = table.replace_schema_metadata({k.encode(): v.encode() for k, v in metadata.items()})
        pq.write_table(table, path, compression='zstd', row_group_size=4096)
        return {'path': str(path), 'size': path.stat().st_size, 'rows': len(rows)}


def write_packets(packets, folder):
    protect(CONFIG)
    from ..uff3_candidate_v1 import families
    # This new process uses only the already established family row layout.
    # Supply a writer which writes once and never calculates a content digest.
    families.load_writer = Writer
    budget = type('NoArtificialResourceGate', (), {'check': lambda *args: None})()
    items = []
    for packet in packets:
        validate(packet)
        packet['producer_job_id'] = os.environ['SLURM_JOB_ID']
        packet['once_key'] = packet['molecule_id']
        items.append(({'sha256': None}, packet))
    files = [{k: ref[k] for k in ('path', 'size', 'rows')}
             for ref in families.export_packets(items, folder, budget, os.environ['SLURM_JOB_ID'],
                 include_families={'D3','geometry','source_status'} if CONFIG.get('stereo_supplement') else None)]
    import pyarrow as pa
    import pyarrow.parquet as pq
    masks, mask_counts, candidates, timing = [], collections.defaultdict(collections.Counter), [], []
    for packet in packets:
        source, mid = packet['source'], packet['molecule_id']
        records = [('D20', mid + ':graph', packet['D20'])]
        if CONFIG.get('stereo_supplement'): records = []
        records += [('D3', mid + ':uff:' + str(c['conformer_id']), c['D3']) for c in packet['conformers']]
        for task, rid, value in records:
            for field in CONFIG['fields']:
                if field['task'] != task: continue
                name = field['source_path']
                if task == 'D20':
                    number = None if value is None else value['values'][value['names'].index(name)]
                else:
                    number = value.get(name)
                numbers = number if isinstance(number, list) else [number]
                src, mask = physical_mask(numbers, field['physical_range'])
                key = str(field['field_id']) + ':' + source['stream']
                mask_counts[key].update(records=1, newly_masked_records=int(any(a and not b for a, b in zip(src, mask))),
                                        source_missing_records=int(not any(src)))
                masks.append({'record_id': rid, 'molecule_id': mid, 'field_id': str(field['field_id']),
                              'field_key': field['field_key'], 'source_path': name,
                              'values_float64': numbers, 'source_value_mask': src, 'value_mask': mask,
                              'dataset_version': 'v2_candidate', 'stream': source['stream'],
                              'pubchem_cid': source['cid'], 'pubchem_version': source['pubchem_version']})
        candidates.append({'molecule_id': mid, 'pubchem_cid': source['cid'], 'seed': packet['seed'],
                           'dataset_version': 'v2_candidate', 'stream': source['stream'],
                           'pubchem_version': source['pubchem_version'],
                           'candidates_json': json.dumps(packet['candidates'], allow_nan=False),
                           'attempts_json': json.dumps(packet['attempts'], allow_nan=False)})
        candidates[-1].update({k: packet.get(k) for k in stereo.FIELDS})
        candidates[-1]['stereo_draws_json'] = json.dumps(packet.get('stereo_draws', []), allow_nan=False)
        timing.append({'molecule_id': mid, 'pubchem_cid': source['cid'], 'stream': source['stream'],
                       'dataset_version': 'v2_candidate', 'pubchem_version': source['pubchem_version'],
                       'seconds': packet['worker_wall_seconds'], 'CPU_seconds': packet['worker_CPU_seconds'],
                       'actual_conformers': len(packet['conformers']), 'state': packet['state']})
        timing[-1].update({k: packet.get(k) for k in stereo.FIELDS})
        timing[-1]['assigned_CIP_counts_json'] = json.dumps(packet.get('assigned_CIP_counts', {}))
        timing[-1]['assigned_EZ_counts_json'] = json.dumps(packet.get('assigned_EZ_counts', {}))
    mask_schema = pa.schema([('record_id', pa.string()), ('molecule_id', pa.string()), ('field_id', pa.string()),
        ('field_key', pa.string()), ('source_path', pa.string()), ('values_float64', pa.large_list(pa.float64())),
        ('source_value_mask', pa.large_list(pa.bool_())), ('value_mask', pa.large_list(pa.bool_())),
        ('dataset_version', pa.string()), ('stream', pa.string()), ('pubchem_cid', pa.int64()), ('pubchem_version', pa.string())])
    for name, rows, schema in [('validity_masks', masks, mask_schema), ('candidate_cache', candidates, None), ('timings', timing, None)]:
        path = folder / (name + '.parquet')
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), path, compression='zstd')
        files.append({'path': str(path), 'size': path.stat().st_size, 'rows': len(rows)})
    return files, {k: dict(v) for k, v in mask_counts.items()}


def process(task):
    protect(CONFIG)
    index, sources = task
    folder = Path(CONFIG['output']) / ('chunk_%06d' % index)
    folder.mkdir(parents=True, exist_ok=True)
    done = folder / 'done.json'
    if done.exists(): return read(done)
    results, started = {}, set()
    for spool in sorted(folder.glob('packets*.jsonl.gz')):
        try:
            with gzip.open(spool, 'rt') as stream:
                for line in stream:
                    row = json.loads(line)
                    started.add(row['index'])
                    if 'packet' in row: results[row['index']] = row['packet']
        except (EOFError, gzip.BadGzipFile, json.JSONDecodeError):
            pass
    spool = folder / ('packets_' + uuid.uuid4().hex + '.jsonl.gz')
    # Every gzip member is closed before the next scientific call. Resume reads
    # only a failed chunk, never completed parquet files for independent QA.
    def append(row):
        protect(CONFIG)
        with gzip.open(spool, 'at', encoding='utf-8') as stream:
            stream.write(json.dumps(row, allow_nan=False) + '\n')
    for i, source in enumerate(sources):
        if i in results: continue
        if i in started:
            packet = {'source': source, 'molecule_id': molecule_id(source), 'seed': 0, 'D20': None,
                'atomic_numbers': [], 'conformers': [], 'candidates': [], 'attempts': [], 'requested_conformers': 3,
                'orders': {}, 'state': 'INTERRUPTED_NO_RETRY', 'error': 'Original interrupted call retained',
                'insufficient_conformers': True, 'generation_count_unknown': True, 'cache_complete': False,
                'candidate_cache_sha256': None, 'atom_order_sha256': None,
                'worker_wall_seconds': None, 'worker_CPU_seconds': None}
            packet.update(stereo.defaults())
            override = CONFIG.get('interrupted_timeout_overrides', {}).get(packet['molecule_id'])
            if override:
                replacement = read(override)
                if (replacement.get('molecule_id') != packet['molecule_id'] or
                        replacement.get('state') != 'UFF_TIMEOUT' or
                        replacement.get('source') != source or
                        replacement.get('molecule_timeout_seconds') != 3600):
                    raise ValueError('APPROVED_INTERRUPTED_TIMEOUT_RECORD_DIFFERS')
                packet = replacement
        else:
            append({'index': i})
            packet = generate_limited(source, CONFIG)
        results[i] = packet
        append({'index': i, 'packet': packet})
    packets = [results[i] for i in range(len(sources))]
    export = folder / ('export_' + uuid.uuid4().hex)
    export.mkdir()
    files, masks = write_packets(packets, export)
    result = {'chunk': index, 'molecules': len(packets), 'files': files, 'masks': masks,
              'states': dict(collections.Counter(p['state'] for p in packets)),
              'streams': dict(collections.Counter(p['source']['stream'] for p in packets)),
              'conformers': sum(len(p['conformers']) for p in packets),
              'failure_reasons': dict(collections.Counter(p['error'] or p['state'] for p in packets if p['state'] != 'SUCCESS')),
              'native_attempt_states': dict(collections.Counter(a['state'] for p in packets for a in p['attempts'])),
              'molecule_seconds': sum(p['worker_wall_seconds'] for p in packets if p['worker_wall_seconds'] is not None),
              'molecule_CPU_seconds': sum(p['worker_CPU_seconds'] for p in packets if p['worker_CPU_seconds'] is not None)}
    result['stereo'] = {'redrawn_molecules': sum(p.get('stereo_draw_index', 0) > 0 for p in packets),
        'draws': sum(len(p.get('stereo_draws', [])) for p in packets),
        'molecules_with_3D': sum(bool(p['conformers']) for p in packets),
        'final_zero_3D': sum(not p['conformers'] for p in packets),
        'CIP': dict(sum((collections.Counter(p.get('assigned_CIP_counts', {})) for p in packets), collections.Counter())),
        'EZ': dict(sum((collections.Counter(p.get('assigned_EZ_counts', {})) for p in packets), collections.Counter()))}
    save(done, result)
    return result


def accept_shard(rank, config):
    return (rank - 1) % config.get('shard_count', 1) in config.get('shard_residues', [config.get('shard_index', 0)])


def selected_sources(config):
    manifest = read(config['source_manifest'])
    if config.get('stereo_supplement'):
        for ref in manifest['stereo_source_parts']:
            with Path(ref['path']).open() as stream:
                for line in stream:
                    row = json.loads(line)
                    if accept_shard(row['stream_rank'], config): yield row
        return
    rng = random.Random(20261025)
    ranks = {s: set(rng.sample(range(1, 1250001), 5000)) for s in ('R', 'N')}
    pilot_keys = {(s, rank) for s, selected in ranks.items() for rank in selected}
    for ref in manifest['source_parts']:
        with Path(ref['path']).open() as stream:
            for line in stream:
                row = json.loads(line)
                is_pilot = (row['stream'], row['stream_rank']) in pilot_keys
                if config['mode'] == 'pilot' and not is_pilot: continue
                if config['mode'] == 'full' and is_pilot: continue
                if config['mode'] == 'full' and not accept_shard(row['stream_rank'], config): continue
                yield row


def run(config):
    protect(config)
    workers = config['workers']
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ['SLURM_CPUS_PER_TASK']) < workers:
        raise RuntimeError('REAL_SLURM_ALLOCATION_REQUIRED')
    root = Path(config['output'])
    root.mkdir(parents=True, exist_ok=True)
    import fcntl
    lock = (root / 'producer.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    began = time.monotonic()
    totals, states, streams, masks = collections.Counter(), collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
    reasons, attempts, expected_streams = collections.Counter(), collections.Counter(), collections.Counter()
    files = []
    stereo_counts, cip_counts, ez_counts = collections.Counter(), collections.Counter(), collections.Counter()
    def consume(result):
        for k in ('molecules', 'conformers', 'molecule_seconds', 'molecule_CPU_seconds'): totals[k] += result[k]
        states.update(result['states']); streams.update(result['streams']); files.extend(result['files'])
        reasons.update(result.get('failure_reasons', {})); attempts.update(result.get('native_attempt_states', {}))
        for k, value in result['masks'].items(): masks[k].update(value)
        for k,v in result.get('stereo', {}).items():
            if k == 'CIP': cip_counts.update(v)
            elif k == 'EZ': ez_counts.update(v)
            else: stereo_counts[k] += v
        save(root / 'progress.json', {'counts': dict(totals), 'states': dict(states), 'streams': dict(streams),
                                    'wall_seconds': time.monotonic() - began, 'job_id': os.environ['SLURM_JOB_ID']})
    pending, batch, index = set(), [], 0
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'), initializer=init, initargs=(config,)) as pool:
        for row in selected_sources(config):
            expected_streams[row['stream']] += 1
            batch.append(row)
            if len(batch) < config['batch_size']: continue
            pending.add(pool.submit(process, (index, batch))); index += 1; batch = []
            if len(pending) >= workers * 2:
                future = next(as_completed(pending)); pending.remove(future); consume(future.result())
        if batch: pending.add(pool.submit(process, (index, batch)))
        for future in as_completed(pending): consume(future.result())
    expected = sum(expected_streams.values())
    if totals['molecules'] != expected or streams != expected_streams:
        raise ValueError('EXACT_FROZEN_BATCH_COVERAGE_DIFFERS')
    if not config.get('stereo_supplement') and config.get('shard_count', 1) == 1 and expected != (10000 if config['mode'] == 'pilot' else 2490000):
        raise ValueError('WHOLE_BATCH_SIZE_DIFFERS')
    summary = {'mode': config['mode'], 'counts': dict(totals), 'states': dict(states), 'streams': dict(streams),
               'masks': {k: dict(v) for k, v in masks.items()}, 'wall_seconds': time.monotonic() - began,
               'workers': workers, 'job_id': os.environ['SLURM_JOB_ID'], 'mask_rate_is_report_only': True,
               'shard_index': config.get('shard_index', 0), 'shard_count': config.get('shard_count', 1),
               'shard_residues': config.get('shard_residues', [config.get('shard_index', 0)]),
               'failure_reasons': dict(reasons), 'native_attempt_states': dict(attempts)}
    summary['stereo'] = {**dict(stereo_counts), 'CIP': dict(cip_counts), 'EZ': dict(ez_counts)}
    summary['molecule_timeout_seconds'] = config.get('molecule_timeout_seconds', 3600)
    summary['timeout_policy'] = 'USER_APPROVED_UFF_MOLECULE_WALL_1H_20261115'
    save(root / 'manifest.json', files)
    save(root / 'summary.json', summary)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    run(read(parser.parse_args().config))
