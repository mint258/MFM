#!/usr/bin/env python3
"""Read only the original records absent from the existing TRAIN/FULL index.

The compact-index complement determines the exact source points. Legacy QA
classifications annotate their history and never remove a record under the new
rules. No existing split is invented, no geometry is generated, and LMDBs are
opened read-only. This standalone script never imports old scan/common guards.
"""
from __future__ import annotations

import argparse
from collections import Counter
import concurrent.futures as futures
import datetime as dt
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import pickle
import re
import sys
import time

PROJECT = Path('/share/home/zixiao/descriptor_analysis')
AUDIT = PROJECT / 'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2'
QA = PROJECT / 'docs/phase1/evidence/stage48_full_corpus_qa/run_v2_4511985'
OUTPUT = PROJECT / 'runs/phase1_dataset_rebuild_20261010'
sys.path[:0] = [str(AUDIT / 'deps'), str(AUDIT / 'scripts/deps')]
WHITELIST = {1, 5, 6, 7, 8, 9, 14, 15, 16, 17, 34, 35, 53}
SAMPLE_KEY = re.compile(r'^(.*)_([0-9]{8})_([0-9]{2})$')
STATUSES = {1: 'train', 2: 'validation', 3: 'known_fullkey_embargo',
            4: 'unknown_non_h_composition_embargo', 5: 'native_structure_quarantine',
            6: 'identity_or_order_quarantine', 7: 'record_read_or_decode_quarantine'}
SOURCES = None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def ref(path: Path) -> dict:
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha256(path)}


def dump(path: Path, value: object) -> None:
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
                       + '\n', encoding='utf-8')
    pending.replace(path)


def original_fields(raw) -> dict:
    if hasattr(raw, 'to_dict'):
        return dict(raw.to_dict())
    if isinstance(raw, dict):
        return dict(raw)
    return dict(vars(raw))


def typed_value(value):
    """Keep source types, tensor dtypes/shapes, values and nonfinite literals."""
    import numpy as np
    import torch
    if isinstance(value, torch.Tensor):
        return {'python_type': 'torch.Tensor', 'dtype': str(value.dtype),
                'shape': list(value.shape),
                'values': typed_value(value.detach().cpu().tolist())}
    if isinstance(value, np.ndarray):
        return {'python_type': 'numpy.ndarray', 'dtype': str(value.dtype),
                'shape': list(value.shape), 'values': typed_value(value.tolist())}
    if isinstance(value, np.generic):
        return {'python_type': type(value).__module__ + '.' + type(value).__name__,
                'value': typed_value(value.item())}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else {'nonfinite_float_literal': repr(value)}
    if isinstance(value, dict):
        return {str(key): typed_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return {'python_type': 'tuple', 'values': [typed_value(item) for item in value]}
    if isinstance(value, list):
        return [typed_value(item) for item in value]
    if isinstance(value, bytes):
        return {'python_type': 'bytes', 'hex': value.hex()}
    return {'python_type': type(value).__module__ + '.' + type(value).__name__,
            'representation': repr(value)}


def initialize(sources: list[dict]) -> None:
    global SOURCES
    SOURCES = sources
    import torch
    from rdkit import RDLogger
    torch.set_num_threads(1)
    RDLogger.DisableLog('rdApp.*')


def tensor_array(value):
    import torch
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().numpy()
    return None


def scalar_float(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def analyze(raw, pointer: dict, source: dict, payload: bytes) -> dict:
    import numpy as np
    from rdkit import Chem
    fields = original_fields(raw)
    sample = fields.get('sample_key')
    sample = sample if isinstance(sample, str) else None
    match = SAMPLE_KEY.fullmatch(sample or '')
    rid = source['name'] + ':' + str(pointer['real_index'])
    row = {'record_id': rid, 'shard_id': pointer['shard_id'],
           'real_index': pointer['real_index'], 'shard_name': source['name'],
           'source_path': source['path'], 'record_payload_sha256': hashlib.sha256(payload).hexdigest(),
           'split': 'unassigned', 'membership': [],
           'member_train': False, 'member_full': False, 'member_routine': False,
           'train_logical_index': None, 'full_logical_index': None,
           'routine_logical_index': None, 'logical_index': None,
           'sample_key': sample, 'sample_key_parse_valid': bool(match),
           'sample_prefix': match.group(1) if match else None,
           'molecule_id': match.group(1) + '_' + match.group(2) if match else 'UNPARSED:' + rid,
           'conformer_id': int(match.group(3)) if match else None,
           'source_family': 'principal' if source['name'].startswith('principal_') else 'unimol',
           'smiles': fields.get('smiles') if isinstance(fields.get('smiles'), str) else None,
           'canonical_smiles': fields.get('canonical_smiles') if isinstance(fields.get('canonical_smiles'), str) else None,
           'isomeric_smiles': fields.get('isomeric_smiles') if isinstance(fields.get('isomeric_smiles'), str) else None,
           'stored_inchikey': None, 'total_atoms': pointer['legacy_atoms'], 'heavy_atoms': None,
           'elements': [], 'element_counts': None, 'electron_count': None,
           'energy_raw': scalar_float(fields.get('energy')),
           'energy_unit': fields.get('energy_unit') if isinstance(fields.get('energy_unit'), str) else None,
           'stored_graph_fragments': None, 'formal_charge': None, 'charged_atoms': None,
           'radical_electrons': None, 'parse_failed': None, 'sanitize_failed': None,
           'native_x_encoding_or_shape_invalid': True, 'atom_sequence_mismatch': None,
           'H_count_mismatch': None, 'atomic_array_shape_mismatch': None,
           'geometry_nonfinite': None, 'geometry_all_zero': None,
           'minimum_distance_A': None, 'minimum_nonbond_distance_A': None,
           'bond_count': None, 'bond_length_outlier_count': None,
           'bond_length_outlier_fraction': None, 'order_suspected_from_bond_lengths': None,
           'geometry_missing_bonds': None, 'geometry_extra_bonds': None,
           'X01': None, 'X01_geometry_checked': False, 'X02': None, 'X03': None,
           'X04': None, 'X05': None, 'G01': None, 'G02': None, 'G03': None, 'B01': None,
           'H01_abs_energy_per_atom': None, 'energy_per_atom_signed': None,
           'X_keep': False, 'pre_geometry_keep': False,
           'legacy_QA_status_code': pointer['legacy_status_code'],
           'legacy_QA_status': STATUSES[pointer['legacy_status_code']],
           'legacy_QA_atoms': pointer['legacy_atoms'],
           'legacy_QA_error_metadata_json': json.dumps(pointer.get('legacy_error_metadata'), sort_keys=True),
           'legacy_QA_classification_path': pointer['classification_path'],
           'legacy_QA_classification_offset': pointer['classification_offset'],
           'existing_membership_reason': 'Absent from the existing compact TRAIN/FULL index; no new split assigned.',
           'decode_status': 'OK', 'decode_error': None,
           'original_fields_json': json.dumps({key: typed_value(value) for key, value in fields.items()},
                                             sort_keys=True, ensure_ascii=False, allow_nan=False)}
    x = tensor_array(fields.get('x'))
    z = None
    if x is not None:
        row['total_atoms'] = int(x.shape[0]) if x.ndim else None
        valid = (x.ndim == 2 and x.shape[1] == 1 and np.issubdtype(x.dtype, np.integer)
                 and bool(((x >= 0) & (x < 118)).all()))
        row['native_x_encoding_or_shape_invalid'] = not valid
        if valid:
            z = x.reshape(-1).astype(np.int64) + 1
            counts = Counter(map(int, z))
            row.update(heavy_atoms=int((z > 1).sum()), elements=sorted(counts),
                       element_counts=sorted(counts.items()), electron_count=int(z.sum()),
                       X02=any(value not in WHITELIST for value in counts), X05=bool(int(z.sum()) % 2))
    xyz = tensor_array(fields.get('pos'))
    if xyz is not None and row['total_atoms'] is not None:
        valid = xyz.shape == (row['total_atoms'], 3) and bool(np.isfinite(xyz).all())
        row['geometry_nonfinite'] = not valid
        row['geometry_all_zero'] = bool((xyz == 0).all()) if valid else None
    smiles = row['smiles']
    mol = Chem.MolFromSmiles(smiles) if smiles else None
    row['parse_failed'] = mol is None
    if smiles and '.' in smiles:
        row['X01'] = True
    if mol is not None:
        row.update(stored_graph_fragments=len(Chem.GetMolFrags(mol)),
                   formal_charge=int(Chem.GetFormalCharge(mol)),
                   charged_atoms=sum(atom.GetFormalCharge() != 0 for atom in mol.GetAtoms()),
                   radical_electrons=sum(atom.GetNumRadicalElectrons() for atom in mol.GetAtoms()),
                   sanitize_failed=False)
        row['X01'] = bool(row['X01'] or row['stored_graph_fragments'] > 1)
        row['X03'] = row['formal_charge'] != 0
        row['X04'] = row['radical_electrons'] > 0
        try:
            row['stored_inchikey'] = Chem.MolToInchiKey(mol) or None
        except Exception as exc:
            row['stored_inchikey'] = None
            row['sanitize_failed'] = True
            row['decode_status'] = 'GRAPH_IDENTITY_UNAVAILABLE'
            row['decode_error'] = type(exc).__name__ + ': ' + str(exc)[:1000]
        if z is not None:
            try:
                expected = np.asarray([atom.GetAtomicNum() for atom in Chem.AddHs(mol).GetAtoms()])
                row['atom_sequence_mismatch'] = not np.array_equal(expected, z)
                row['H_count_mismatch'] = int((expected == 1).sum()) != int((z == 1).sum())
            except Exception:
                row['atom_sequence_mismatch'] = None
    elif smiles:
        try:
            unsanitized = Chem.MolFromSmiles(smiles, sanitize=False)
            row['sanitize_failed'] = bool(Chem.SanitizeMol(unsanitized, catchErrors=True)) if unsanitized else None
        except Exception:
            row['sanitize_failed'] = True
    if row['total_atoms'] and row['energy_raw'] is not None:
        row['H01_abs_energy_per_atom'] = abs(row['energy_raw']) / row['total_atoms']
        row['energy_per_atom_signed'] = row['energy_raw'] / row['total_atoms']
    row['X_keep'] = all(row[code] is False for code in ('X01', 'X02', 'X03', 'X04', 'X05'))
    # G is unassessed in this point inventory, so no premature pilot eligibility.
    return row


def consume(task: list[dict]) -> dict:
    import lmdb
    started = time.monotonic()
    handles = {}
    rows = []
    try:
        for pointer in task:
            sid = pointer['shard_id']
            source = SOURCES[sid]
            if sid not in handles:
                actual = Path(source['path']).stat()
                if actual.st_size != source['source_size'] or actual.st_mtime_ns != source['source_mtime_ns']:
                    raise RuntimeError(f'Original source metadata differs: {source["path"]}')
                env = lmdb.open(source['path'], subdir=False, readonly=True, create=False,
                                lock=False, readahead=False, meminit=False, max_readers=512)
                if env.stat()['entries'] != source['entries'] or env.info()['last_txnid'] != source['last_txnid']:
                    env.close()
                    raise RuntimeError(f'Original source entry/transaction differs: {source["path"]}')
                handles[sid] = env
            with handles[sid].begin(buffers=False) as transaction:
                payload = transaction.get(f'{pointer["real_index"]:09d}'.encode())
            if payload is None:
                raise RuntimeError('Missing dense original source record: ' + str(pointer))
            raw = pickle.loads(payload)
            rows.append(analyze(raw, pointer, source, payload))
        return {'rows': rows, 'PID': os.getpid(), 'seconds': time.monotonic() - started,
                'CPU_seconds': time.process_time()}
    finally:
        for env in handles.values():
            env.close()


def find_unassigned(plan: dict, qa: Path) -> tuple[list[dict], dict]:
    import numpy as np
    base_ref = plan['manifests']['train']['base_index']
    dtype = np.dtype([('sid', '<u2'), ('flags', '<u2'), ('real', '<u8'), ('atoms', '<u4')])
    if base_ref['format'] != '<HHQI' or Path(base_ref['path']).stat().st_size != base_ref['rows'] * dtype.itemsize:
        raise RuntimeError('Unexpected compact index format/length.')
    base = np.memmap(base_ref['path'], mode='r', dtype=dtype)
    gaps = {}
    for sid, source in enumerate(plan['sources']):
        retained = base['real'][base['sid'] == sid]
        missing = np.ones(source['length'], dtype=bool)
        missing[retained] = False
        gaps[sid] = np.flatnonzero(missing)
    expected_gap = sum(item['length'] for item in plan['sources']) - base_ref['rows']
    if sum(map(len, gaps.values())) != expected_gap:
        raise RuntimeError('Compact-index complement does not conserve the original source domain.')
    history = json.loads((qa / 'quality_and_identity.json').read_text(encoding='utf-8'))
    pointers = []
    consumed_receipts = []
    legacy_counts = Counter()
    classification_dtype = np.dtype([('status', 'u1'), ('atoms', '<u4')])
    for receipt_ref in history['ordered_closed_chunk_receipts']:
        receipt_path = Path(receipt_ref['path'])
        chunk = json.loads(receipt_path.read_text(encoding='utf-8'))
        sid = chunk['shard_id']
        lo = int(np.searchsorted(gaps[sid], chunk['start']))
        hi = int(np.searchsorted(gaps[sid], chunk['stop']))
        selected = gaps[sid][lo:hi]
        if not len(selected):
            continue
        if sha256(receipt_path) != receipt_ref['sha256'] or not chunk['complete']:
            raise RuntimeError('Legacy QA receipt is no longer the closed reference: ' + str(receipt_path))
        classification_ref = chunk['artifacts']['classifications.bin']
        classification = Path(classification_ref['path'])
        if classification.stat().st_size != (chunk['stop'] - chunk['start']) * classification_dtype.itemsize:
            raise RuntimeError('Legacy dense classification length differs: ' + str(classification))
        values = np.memmap(classification, mode='r', dtype=classification_dtype)
        errors = {}
        error_ref = chunk['artifacts'].get('errors.jsonl')
        if error_ref:
            with Path(error_ref['path']).open(encoding='utf-8') as stream:
                for line in stream:
                    entry = json.loads(line)
                    errors[entry['real_index']] = entry
        for original in selected:
            real = int(original)
            offset = real - chunk['start']
            item = values[offset]
            status = int(item['status'])
            if status not in STATUSES or status in (1, 2):
                raise RuntimeError('Complement point has a retained/unknown legacy classification.')
            pointers.append({'shard_id': sid, 'real_index': real,
                             'legacy_status_code': status, 'legacy_atoms': int(item['atoms']),
                             'classification_path': str(classification),
                             'classification_offset': offset,
                             'legacy_error_metadata': errors.get(real)})
            legacy_counts[STATUSES[status]] += 1
        consumed_receipts.append({'receipt': receipt_ref, 'classification': classification_ref,
                                  'errors': error_ref, 'selected_source_points': len(selected)})
    if len(pointers) != expected_gap or len({(row['shard_id'], row['real_index']) for row in pointers}) != expected_gap:
        raise RuntimeError('Incomplete or duplicated complement/classification join.')
    expected_history = {name: count for name, count in history['statuses'].items()
                        if name not in ('train', 'validation') and count}
    if dict(legacy_counts) != expected_history:
        raise RuntimeError('Legacy complement reason counts differ from closed QA totals.')
    pointers.sort(key=lambda row: (row['shard_id'], row['real_index']))
    return pointers, {'base_index': base_ref, 'original_source_records': sum(item['length'] for item in plan['sources']),
                      'existing_membership_records': base_ref['rows'], 'unassigned_records': expected_gap,
                      'legacy_reason_counts': dict(legacy_counts),
                      'legacy_receipts_used': consumed_receipts}


def schema(pa):
    strings = ('record_id', 'shard_name', 'source_path', 'record_payload_sha256', 'split',
               'sample_key', 'sample_prefix', 'molecule_id', 'source_family', 'smiles',
               'canonical_smiles', 'isomeric_smiles', 'stored_inchikey', 'energy_unit',
               'legacy_QA_status', 'legacy_QA_error_metadata_json', 'legacy_QA_classification_path',
               'existing_membership_reason', 'decode_status', 'decode_error', 'original_fields_json')
    integers = ('shard_id', 'real_index', 'train_logical_index', 'full_logical_index',
                'routine_logical_index', 'logical_index', 'conformer_id', 'total_atoms',
                'heavy_atoms', 'electron_count', 'stored_graph_fragments', 'formal_charge',
                'charged_atoms', 'radical_electrons', 'bond_count', 'bond_length_outlier_count',
                'geometry_missing_bonds', 'geometry_extra_bonds', 'legacy_QA_status_code',
                'legacy_QA_atoms', 'legacy_QA_classification_offset')
    booleans = ('member_train', 'member_full', 'member_routine', 'sample_key_parse_valid',
                'parse_failed', 'sanitize_failed', 'native_x_encoding_or_shape_invalid',
                'atom_sequence_mismatch', 'H_count_mismatch', 'atomic_array_shape_mismatch',
                'geometry_nonfinite', 'geometry_all_zero', 'order_suspected_from_bond_lengths',
                'X01', 'X01_geometry_checked', 'X02', 'X03', 'X04', 'X05', 'G01', 'G02', 'G03',
                'B01', 'X_keep', 'pre_geometry_keep')
    numbers = ('energy_raw', 'minimum_distance_A', 'minimum_nonbond_distance_A',
               'bond_length_outlier_fraction', 'H01_abs_energy_per_atom', 'energy_per_atom_signed')
    return pa.schema([(key, pa.string()) for key in strings] +
                     [(key, pa.int64()) for key in integers] +
                     [(key, pa.bool_()) for key in booleans] +
                     [(key, pa.float64()) for key in numbers] +
                     [('membership', pa.list_(pa.string())), ('elements', pa.list_(pa.int64())),
                      ('element_counts', pa.map_(pa.int64(), pa.int64()))])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUTPUT)
    parser.add_argument('--plan', type=Path, default=AUDIT / 'plan.json')
    parser.add_argument('--qa-root', type=Path, default=QA)
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--batch-size', type=int, default=64)
    parser.add_argument('--seed', type=int, default=20261010)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not 16 <= args.workers <= int(os.environ.get('SLURM_CPUS_PER_TASK', 0)):
        raise RuntimeError('A Slurm allocation with >=16 effectively parallel CPU workers is required.')
    if args.batch_size < 1:
        raise ValueError('Positive batch size required.')
    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / 'unassigned_record_index.parquet'
    pending = destination.with_name(destination.name + '.pending')
    if destination.exists() or pending.exists():
        raise RuntimeError('Unassigned index already exists; use a fresh output directory.')
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    started = time.monotonic()
    pointers, closure = find_unassigned(plan, args.qa_root)
    dump(args.out / 'unassigned_inventory_inputs.json',
         {'plan': ref(args.plan), 'script': ref(Path(__file__)), **closure})
    import pyarrow as pa
    import pyarrow.parquet as pq
    arrow_schema = schema(pa)
    tasks = [pointers[start:start + args.batch_size] for start in range(0, len(pointers), args.batch_size)]
    context = mp.get_context('spawn')
    workers = set()
    counts = {code: Counter() for code in ('X01', 'X02', 'X03', 'X04', 'X05')}
    molecules = set()
    done_records = 0
    writer = pq.ParquetWriter(pending, arrow_schema, compression='zstd')
    try:
        with futures.ProcessPoolExecutor(max_workers=args.workers, mp_context=context,
                                        initializer=initialize, initargs=(plan['sources'],)) as pool:
            # map preserves source point order, and the bounded corpus has only
            # ~130 small batches; no additional Native point is ever submitted.
            for result in pool.map(consume, tasks, chunksize=1):
                rows = result['rows']
                writer.write_table(pa.Table.from_pylist(rows, schema=arrow_schema))
                workers.add(result['PID'])
                for row in rows:
                    molecules.add(row['molecule_id'])
                    for code in counts:
                        counts[code]['true' if row[code] is True else 'false' if row[code] is False else 'unknown'] += 1
                done_records += len(rows)
                dump(args.out / 'unassigned_inventory_progress.json',
                     {'records': done_records, 'planned': len(pointers),
                      'worker_PIDs': sorted(workers), 'elapsed_seconds': time.monotonic() - started})
        writer.close()
        writer = None
        if done_records != closure['unassigned_records']:
            raise RuntimeError('Decoded complement coverage differs.')
        pending.replace(destination)
        from rdkit import rdBase
        summary = {'schema': 'phase1_WP0_unassigned_original_source_inventory_v1',
                   'status': 'ALL_ORIGINAL_COMPACT_INDEX_GAP_POINTS_ACCOUNTED_NEW_GEOMETRY_PENDING',
                   'created_UTC': dt.datetime.now(dt.timezone.utc).isoformat(),
                   'job_id': os.environ['SLURM_JOB_ID'], 'seed': args.seed,
                   'records': done_records, 'molecules': len(molecules),
                   'legacy_reason_counts': closure['legacy_reason_counts'],
                   'new_X_counts': {key: dict(value) for key, value in counts.items()},
                   'actual_worker_PIDs': sorted(workers), 'requested_workers': args.workers,
                   'elapsed_seconds': time.monotonic() - started,
                   'script': ref(Path(__file__)), 'output': ref(destination),
                   'software': {'python': sys.version, 'RDKit': rdBase.rdkitVersion, 'pyarrow': pa.__version__},
                   'original_LMDB_mode': 'readonly=True,create=False,lock=False',
                   'split_policy': 'All rows remain unassigned with empty membership; legacy embargo/quarantine is historical annotation only.',
                   'new_screen_scope': 'X01 stored graph/dot, X02 actual elements, X03 net charge, X04 radicals, X05 atomic-number parity; G/B await the new geometry pass.',
                   'original_field_transport': 'Typed JSON records original scalar values and tensor dtype/shape/values; source pointer and full payload SHA also retained.',
                   'legacy_QA_error_scope': 'errors.jsonl stored only the first 1000 errors per old chunk; absence of a detailed error is not an absence of legacy exclusion.',
                   'new_LMDB_created_or_written': False, 'existing_train_full_membership_changed': False}
        dump(args.out / 'unassigned_inventory.json', summary)
        print(json.dumps({'output': str(destination), 'records': done_records,
                          'elapsed_seconds': summary['elapsed_seconds']}), flush=True)
    finally:
        if writer is not None:
            writer.close()


if __name__ == '__main__':
    main()
