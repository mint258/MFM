"""Join delivered D5 identities to existing native S locations (CPU job).

Only identity metadata is read. The producer performs the single alignment
check while creating the index; no labels, hashes or acceptance receipts.
"""
from pathlib import Path
import argparse
import json

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--d5', required=True)
    parser.add_argument('--native-manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    d5 = json.loads(Path(args.d5).read_text())['components']
    native = json.loads(Path(args.native_manifest).read_text())
    selected = pq.read_table(d5['subsets']['train_240000']['path'], columns=['molecule_id'])
    if len(selected) != 240_000 or len(set(selected['molecule_id'].to_pylist())) != 240_000:
        raise ValueError('D5 must contain the declared 240000 unique TRAIN molecules')
    con = duckdb.connect()
    con.execute('SET threads=16')
    con.register('selected', selected)
    con.execute('CREATE TABLE bases AS SELECT b.molecule_id, b.native_record_id AS record_id, '
                'b.training_rank FROM read_parquet(?) b JOIN selected s USING(molecule_id) '
                "WHERE b.geometry_source='pm7' AND b.effective_role='TRAIN'",
                [d5['training_fixed_random_base_index_reference']['path']])
    reference = next(r for r in native['references']
                     if r['kind'] == 'record_metadata' and r['role'] == 'train')
    with pa.memory_map(reference['path'], 'r') as source:
        table = pa.ipc.open_file(source).read_all().select(
            ['molecule_id', 'record_id', 'source_path', 'real_index', 'total_atoms'])
        con.register('native_records', table)
        rows = con.execute('SELECT b.molecule_id, b.record_id, b.training_rank, '
            'n.source_path, n.real_index, n.total_atoms FROM bases b JOIN native_records n '
            'ON b.record_id=n.record_id AND b.molecule_id=n.molecule_id '
            'ORDER BY b.molecule_id,b.training_rank').fetch_arrow_table()
    expected = con.execute('SELECT count(*), count(DISTINCT molecule_id) FROM bases').fetchone()
    observed = (len(rows), len(set(rows['molecule_id'].to_pylist())))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if observed != expected or observed[1] != 240_000:
        summary = {'status': 'IDENTITY_JOIN_INCOMPLETE', 'expected_records_molecules': expected,
                   'observed_records_molecules': observed}
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        raise ValueError(str(summary))
    path = output / 'records.parquet'
    pq.write_table(rows, path, compression='zstd')
    summary = {'status': 'READY', 'molecules': observed[1], 'records': observed[0],
               'geometry': 'PM7', 'sampling': 'uniform_molecule_then_uniform_allowed_conformer',
               'D5_holdouts': 'excluded_by_delivered_training_fixed_random_base_index',
               'labels_read': False, 'path': str(path), 'bytes': path.stat().st_size}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
