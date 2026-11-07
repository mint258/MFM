"""Materialize native locations for the two delivered D5 validation populations."""
import argparse
import json
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from phychem_mfm.phase1.v2_disk import save_metadata_json, save_metadata_parquet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--d5', required=True)
    parser.add_argument('--native-manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    d5 = json.loads(Path(args.d5).read_text())['components']
    native = json.loads(Path(args.native_manifest).read_text())
    con = duckdb.connect()
    con.execute('SET threads=16')
    for name, key in (('proxy', 'train_240000'), ('full_molecules', 'val_all'), ('routine_molecules', 'pilot_val')):
        con.register(name, pq.read_table(d5['subsets'][key]['path'], columns=['molecule_id']))
    con.register('diagnostic', pq.read_table(d5['diagnostic_base_reference']['path']))
    con.execute('CREATE TABLE wanted AS SELECT a.molecule_id,a.native_record_id AS record_id, '
        "'FULL' AS role, r.molecule_id IS NOT NULL AS routine "
        'FROM read_parquet(?) a JOIN full_molecules f USING(molecule_id) '
        "LEFT JOIN routine_molecules r USING(molecule_id) WHERE a.geometry_source='pm7' "
        'UNION ALL SELECT a.molecule_id,a.native_record_id AS record_id, '
        "'TRAIN_UNSEEN_CONFORMATION' AS role, false AS routine "
        'FROM read_parquet(?) a JOIN diagnostic d ON a.molecule_id=d.molecule_id '
        'AND a.geometry_id=d.geometry_id AND a.geometry_source=d.geometry_source '
        "JOIN proxy p ON a.molecule_id=p.molecule_id WHERE a.geometry_source='pm7'",
        [d5['all_fixed_random_base_index_reference']['path']] * 2)
    tables = []
    for role in ('train', 'full'):
        ref = next(r for r in native['references'] if r['kind'] == 'record_metadata' and r['role'] == role)
        with pa.memory_map(ref['path'], 'r') as source:
            tables.append(pa.ipc.open_file(source).read_all().select(
                ['molecule_id', 'record_id', 'source_path', 'real_index', 'total_atoms']))
    con.register('native_records', pa.concat_tables(tables))
    rows = con.execute('SELECT w.*,n.source_path,n.real_index,n.total_atoms FROM wanted w '
        'JOIN native_records n ON w.molecule_id=n.molecule_id AND w.record_id=n.record_id '
        'ORDER BY w.role,w.molecule_id,w.record_id').fetch_arrow_table()
    expected = con.execute('SELECT count(*) FROM wanted').fetchone()[0]
    if len(rows) != expected:
        raise ValueError(f'Validation identity join: {len(rows)} located, {expected} expected')
    output = Path(args.output)
    path = output / 'records.parquet'
    save_metadata_parquet(rows, path)
    con.register('result', rows)
    counts = con.execute('SELECT role,count(*),count(DISTINCT molecule_id) FROM result GROUP BY role').fetchall()
    summary = dict(path=str(path), bytes=path.stat().st_size, records=len(rows),
                   populations=counts, labels_read=False)
    save_metadata_json(summary, output / 'summary.json')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
