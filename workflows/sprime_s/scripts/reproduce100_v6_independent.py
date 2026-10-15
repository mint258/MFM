"""Run the fixed random 100 independently of pilot completion, then compare."""
import argparse, concurrent.futures as cf, hashlib, json, multiprocessing as mp, os
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from prepare import ROOT, save, sha
import sprime_v6 as science

OUT = ROOT / 'reproduction100_v6'

def generate():
    OUT.mkdir(exist_ok=True)
    assert not (OUT / 'receipt.json').exists()
    metas = []
    for group in range(1, 6):
        rows = pq.read_table(ROOT / 'prepared/pilot_molecules.parquet',
                             filters=[('file_group', '=', group)]).to_pylist()
        metas.extend(sorted(rows, key=lambda r: hashlib.sha256(
            ('sprime-reproduce100:' + r['molecule_id']).encode()).digest())[:20])
    ids = {r['molecule_id'] for r in metas}
    assert len(metas) == len(ids) == 100
    columns = ['record_id', 'molecule_id', 'source_path', 'real_index',
               'record_payload_sha256', 'total_atoms', 'energy_raw', 'smiles',
               'QC_molecule_chirality_conflict', 'QC_molecule_ez_conflict']
    records = pq.read_table(ROOT / 'prepared/pilot_records.parquet',
                           columns=columns, filters=[('molecule_id', 'in', sorted(ids))]).to_pylist()
    indexed = {mid: [] for mid in ids}
    for r in records:
        indexed[r['molecule_id']].append(r)
    tasks = [(indexed[m['molecule_id']], m) for m in metas]
    molecules, conformers = [], []
    with cf.ProcessPoolExecutor(max_workers=16, mp_context=mp.get_context('spawn'),
                                initializer=science.worker_init) as pool:
        for m, c in pool.map(science.process, tasks):
            molecules.append(m)
            conformers.extend(c)
    for name, rows in [('molecules', molecules), ('conformers', conformers)]:
        p = OUT / (name + '.parquet')
        assert not p.exists()
        table = pa.Table.from_pylist(rows)
        if name == 'conformers':
            table = table.set_column(table.schema.get_field_index('coordinates'), 'coordinates',
                pa.array([r['coordinates'] for r in rows], type=pa.list_(pa.list_(pa.float64(), 3))))
        pq.write_table(table, str(p) + '.pending', compression='zstd')
        Path(str(p) + '.pending').replace(p)
    save(OUT / 'receipt.json', {'job_id': os.environ['SLURM_JOB_ID'], 'molecules': 100,
        'conformers': len(conformers), 'source_sha256': sha(science.__file__),
        'selection': '20 per file group; sha256(sprime-reproduce100: + molecule_id)',
        'references': [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                       for p in [OUT / 'molecules.parquet', OUT / 'conformers.parquet']]})
    print('INDEPENDENT_100_RERUN_SAVED', flush=True)

def compare():
    receipt = json.loads((OUT / 'receipt.json').read_text())
    assert receipt['source_sha256'] == sha(science.__file__)
    for ref in receipt['references']:
        p = Path(ref['path'])
        assert p.stat().st_size == ref['bytes'] and sha(p) == ref['sha256']
    actual_m = {r['molecule_id']: r for r in pq.read_table(OUT / 'molecules.parquet').to_pylist()}
    actual_c = {mid: [] for mid in actual_m}
    for c in pq.read_table(OUT / 'conformers.parquet').to_pylist():
        actual_c[c['molecule_id']].append(c)
    def read_baseline(group):
        r = json.loads((ROOT / f'pilot_v6/receipt_group{group}.json').read_text())
        assert r['source_sha256'] == receipt['source_sha256']
        for ref in r['references']:
            assert Path(ref['path']).stat().st_size == ref['bytes'] and sha(ref['path']) == ref['sha256']
        filt = [('molecule_id', 'in', sorted(actual_m))]
        return (pq.read_table(ROOT / f'pilot_v6/molecules_group{group}.parquet', filters=filt).to_pylist(),
                pq.read_table(ROOT / f'pilot_v6/conformers_group{group}.parquet', filters=filt).to_pylist())
    expected_m, expected_c = {}, {mid: [] for mid in actual_m}
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        for ms, cs in pool.map(read_baseline, range(1, 6)):
            expected_m.update({m['molecule_id']: m for m in ms})
            for c in cs:
                expected_c[c['molecule_id']].append(c)
    assert set(actual_m) == set(expected_m) and len(actual_m) == 100
    results = []
    for mid, actual in actual_m.items():
        old = expected_m[mid]
        new_cs = sorted(actual_c[mid], key=lambda c: c['sprime_conf_idx'])
        old_cs = sorted(expected_c[mid], key=lambda c: c['sprime_conf_idx'])
        checks = []
        for new, previous in zip(new_cs, old_cs):
            xyz = np.asarray(new['coordinates'], dtype='<f8')
            baseline = np.asarray(previous['coordinates'], dtype='<f8')
            checks.append({'index': new['sprime_conf_idx'],
                'index_equal': new['sprime_conf_idx'] == previous['sprime_conf_idx'],
                'shape_equal': xyz.shape == baseline.shape,
                'coordinate_bytes_equal': xyz.tobytes() == baseline.tobytes(),
                'seed_equal': new['seed'] == previous['seed'],
                'new_sha256': hashlib.sha256(xyz.tobytes()).hexdigest(),
                'old_sha256': hashlib.sha256(baseline.tobytes()).hexdigest()})
        same_status = actual['status'] == old['status']
        same_count = len(new_cs) == len(old_cs)
        passed = same_status and same_count and all(c['index_equal'] and c['shape_equal']
            and c['coordinate_bytes_equal'] and c['seed_equal'] for c in checks)
        results.append({'molecule_id': mid, 'passed': passed, 'same_status': same_status,
            'same_count': same_count, 'coordinates_tested': len(checks), 'checks': checks,
            'actual_status': actual['status'], 'expected_status': old['status']})
    result = {'status': 'PASS' if all(r['passed'] for r in results) else 'FAIL',
        'comparison_job_id': os.environ['SLURM_JOB_ID'], 'generation_job_id': receipt['job_id'],
        'molecules': 100, 'molecules_with_coordinates': sum(r['coordinates_tested'] > 0 for r in results),
        'conformers_tested': sum(r['coordinates_tested'] for r in results),
        'source_sha256': receipt['source_sha256'],
        'criterion': 'Strict float64 coordinate bytes, seed, indices, count and status; no tolerance',
        'results': results}
    save(ROOT / 'reports/pilot_reproduction100.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'results'}), flush=True)
    if result['status'] != 'PASS':
        raise RuntimeError('SAME_SEED_COORDINATE_REPRODUCTION_FAILED')

if __name__ == '__main__':
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK']) >= 16
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['generate', 'compare'])
    args = parser.parse_args()
    (generate if args.mode == 'generate' else compare)()
