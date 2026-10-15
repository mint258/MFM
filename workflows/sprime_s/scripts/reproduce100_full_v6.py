"""Global full-population random 100 rerun; accept only exact coordinate reproduction."""
import concurrent.futures as cf, hashlib, json, multiprocessing as mp, os
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from prepare import ROOT, POP, save, sha
import sprime_v6 as science

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK']) >= 16
    import duckdb
    out = ROOT / 'dataset'
    manifest_path = out / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['status'] == 'FULL_POPULATION_CLOSED_AWAITING_REPRODUCTION100'
    prepared = json.loads((ROOT / 'full/prepared.json').read_text())
    assert prepared['source_sha256'] == sha(science.__file__)
    before_sha = sha(manifest_path)
    db = duckdb.connect()
    db.execute('SET threads=16')
    metas = db.execute(f"SELECT * FROM read_parquet('{POP / 'molecule_index.parquet'}') "
        "ORDER BY md5('sprime-full-reproduce100:' || molecule_id) LIMIT 100").fetch_arrow_table().to_pylist()
    db.close()
    ids = sorted(m['molecule_id'] for m in metas)
    assert len(set(ids)) == 100
    def read_baseline(group):
        filt = [('molecule_id', 'in', ids)]
        return (pq.read_table(out / f'molecules_group{group}.parquet', filters=filt).to_pylist(),
                pq.read_table(out / f'conformers_group{group}.parquet', filters=filt).to_pylist())
    old_m, old_c = {}, {mid: [] for mid in ids}
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        for ms, cs in pool.map(read_baseline, range(1, 6)):
            old_m.update({r['molecule_id']: r for r in ms})
            for c in cs:
                old_c[c['molecule_id']].append(c)
    assert set(old_m) == set(ids)
    columns = ['record_id', 'molecule_id', 'source_path', 'real_index', 'record_payload_sha256',
        'total_atoms', 'energy_raw', 'smiles', 'QC_molecule_chirality_conflict', 'QC_molecule_ez_conflict']
    records = pq.read_table(ROOT / 'full/record_pointers.parquet', columns=columns,
                           filters=[('molecule_id', 'in', ids)]).to_pylist()
    indexed = {mid: [] for mid in ids}
    for r in records:
        indexed[r['molecule_id']].append(r)
    assert all(len(indexed[m['molecule_id']]) == m['records'] for m in metas)
    results = []
    with cf.ProcessPoolExecutor(max_workers=16, mp_context=mp.get_context('spawn'),
                                initializer=science.worker_init) as pool:
        for actual, confs in pool.map(science.process, [(indexed[m['molecule_id']], m) for m in metas]):
            mid = actual['molecule_id']
            previous = old_m[mid]
            before = sorted(old_c[mid], key=lambda c: c['sprime_conf_idx'])
            after = sorted(confs, key=lambda c: c['sprime_conf_idx'])
            checks = []
            for new, old in zip(after, before):
                xyz = np.asarray(new['coordinates'], dtype='<f8')
                baseline = np.asarray(old['coordinates'], dtype='<f8')
                checks.append({'index': new['sprime_conf_idx'],
                    'index_equal': new['sprime_conf_idx'] == old['sprime_conf_idx'],
                    'shape_equal': xyz.shape == baseline.shape,
                    'coordinate_bytes_equal': xyz.tobytes() == baseline.tobytes(),
                    'seed_equal': new['seed'] == old['seed'],
                    'source_and_order_equal': new['source_record_id'] == old['source_record_id']
                        and new['atom_order_sha256'] == old['atom_order_sha256'],
                    'new_sha256': hashlib.sha256(xyz.tobytes()).hexdigest(),
                    'old_sha256': hashlib.sha256(baseline.tobytes()).hexdigest()})
            same_status = actual['status'] == previous['status']
            same_count = len(after) == len(before)
            passed = same_status and same_count and all(c['index_equal'] and c['shape_equal']
                and c['coordinate_bytes_equal'] and c['seed_equal'] and c['source_and_order_equal'] for c in checks)
            results.append({'molecule_id': mid, 'passed': passed, 'same_status': same_status,
                'same_count': same_count, 'actual_status': actual['status'], 'expected_status': previous['status'],
                'coordinates_tested': len(checks), 'checks': checks})
    result = {'status': 'PASS' if all(r['passed'] for r in results) else 'FAIL',
        'job_id': os.environ['SLURM_JOB_ID'], 'molecules': 100,
        'selection': 'Global formal population, md5(sprime-full-reproduce100: + molecule_id), first 100',
        'molecules_with_coordinates': sum(r['coordinates_tested'] > 0 for r in results),
        'conformers_tested': sum(r['coordinates_tested'] for r in results),
        'source_sha256': prepared['source_sha256'], 'dataset_manifest_before_sha256': before_sha,
        'criterion': 'Strict float64 coordinate bytes, seed, source/order, indices, count and status; no tolerance',
        'results': results}
    report = ROOT / 'reports/full_reproduction100.json'
    save(report, result)
    if result['status'] != 'PASS':
        raise RuntimeError('FULL_SAME_SEED_COORDINATE_REPRODUCTION_FAILED')
    assert sha(manifest_path) == before_sha
    manifest['status'] = 'FULL_DATASET_ACCEPTED'
    manifest['reproduction100'] = {'path': str(report), 'sha256': sha(report),
        **{k: v for k, v in result.items() if k != 'results'}}
    save(manifest_path, manifest)
    save(out / 'acceptance.json', {'status': 'FULL_DATASET_ACCEPTED',
        'dataset_manifest_sha256': sha(manifest_path), 'reproduction100_sha256': sha(report),
        'molecules': manifest['closure']['molecules'], 'source_records': manifest['closure']['source_records'],
        'sprime_conformers': manifest['closure']['sprime_conformers'], 'job_id': os.environ['SLURM_JOB_ID']})
    print(json.dumps({k: v for k, v in result.items() if k != 'results'}), flush=True)

if __name__ == '__main__':
    main()
