"""Build a native integration panel from completely covered smoke molecules.

This is a bounded integration-test population, not the 10,000-record WP4 panel.
Input index and annotation files remain read-only; this script never opens LMDB.
Run under an allocated Slurm job with at least 16 CPUs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import sys
import time

ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
AUDIT_DEPS = Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps')
X_CODES = ['X01', 'X02', 'X03', 'X04', 'X05']
EXCLUDE = X_CODES + ['G01', 'G02', 'G03', 'C02', 'C03', 'I01']


def q(value):
    return "'" + str(value).replace("'", "''") + "'"


def rows(db, sql):
    cur = db.execute(sql)
    names = [x[0] for x in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(path):
    stat = Path(path).stat()
    return {'path': str(Path(path).absolute()), 'bytes': stat.st_size,
            'mtime_ns': stat.st_mtime_ns, 'inode': stat.st_ino}


def write_json(path, value):
    pending = Path(str(path) + '.pending')
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    os.replace(pending, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', default=str(ROOT / 'record_index.parquet'))
    parser.add_argument('--geometry', default=str(ROOT / 'wp1_geometry_smoke/job_4512807/geometry_annotations.parquet'))
    parser.add_argument('--output', default=str(ROOT / 'bounded_native_panel'))
    parser.add_argument('--records', type=int, default=160)
    parser.add_argument('--min-molecules', type=int, default=16)
    parser.add_argument('--seed', type=int, default=20261010)
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        import ast
        ast.parse(Path(__file__).read_text())
        print(json.dumps({'status': 'SOURCE_SYNTAX_PASS', 'data_read': False, 'LMDB_opened': False}))
        return 0
    allocated = int(os.environ.get('SLURM_CPUS_PER_TASK', '0'))
    if not os.environ.get('SLURM_JOB_ID') or allocated < 16 or not 16 <= args.workers <= allocated:
        raise RuntimeError('Requires a Slurm allocation with >=16 CPUs and >=16 DuckDB/PyArrow worker threads')
    if args.records < 1 or args.min_molecules < 16:
        raise ValueError('Positive record budget and at least 16 molecules are required')
    try:
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ModuleNotFoundError:
        sys.path.insert(0, str(AUDIT_DEPS))
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
    pa.set_cpu_count(args.workers)
    pa.set_io_thread_count(min(args.workers, 8))
    out = Path(args.output).absolute()
    if not out.is_relative_to(ROOT) or out == ROOT:
        raise ValueError('Output must be a new directory inside this phase root')
    out.mkdir(parents=True, exist_ok=True)
    panel = out / 'pilot_sample_manifest.parquet'
    manifest_path = out / 'pilot_manifest.json'
    completeness_path = out / 'molecule_completeness.parquet'
    if any(path.exists() for path in (panel, manifest_path, completeness_path)):
        raise RuntimeError('Existing final output; preserve it and use a fresh output directory')
    inputs_before = {'index': identity(args.index), 'geometry': identity(args.geometry)}
    geometry_sha = sha(args.geometry)
    started = time.monotonic()
    db = duckdb.connect()
    db.execute(f'SET threads={args.workers}')
    db.execute("SET memory_limit='24GB'")
    db.execute(f'SET temp_directory={q(out / "duckdb_tmp")}')
    db.execute(f'CREATE VIEW idx AS SELECT * FROM read_parquet({q(args.index)})')
    db.execute(f'CREATE TABLE geo AS SELECT * FROM read_parquet({q(args.geometry)})')
    idx_columns = {r[0] for r in db.execute('DESCRIBE idx').fetchall()}
    geo_columns = {r[0] for r in db.execute('DESCRIBE geo').fetchall()}
    needed = {'record_id', 'molecule_id', 'conformer_id', 'shard_id', 'real_index',
              'record_payload_sha256', 'energy_raw', 'total_atoms', 'heavy_atoms', 'B01', *EXCLUDE[:8]}
    gneeded = {'record_id', 'molecule_id', 'geometry_X01', 'G01', 'G02', 'G03',
               'B01', 'C02', 'C03', 'I01', 'T01', 'reidentified_smiles',
               'reidentified_inchikey', 'reidentified_connectivity_key',
               'connectivity_mismatch', 'stereo_only_key_mismatch', 'error', 'geometry_seconds'}
    if needed - idx_columns or gneeded - geo_columns:
        raise ValueError('Missing source columns: ' + str({'index': sorted(needed - idx_columns),
                                                        'geometry': sorted(gneeded - geo_columns)}))
    geometry_duplicate = db.execute('SELECT count(*)-count(DISTINCT record_id) FROM geo').fetchone()[0]
    if geometry_duplicate:
        raise ValueError(f'Duplicate smoke record IDs: {geometry_duplicate}')
    if db.execute('SELECT count(*) FROM geo WHERE record_id IS NULL OR molecule_id IS NULL').fetchone()[0]:
        raise ValueError('Smoke records with missing native identity')
    db.execute('CREATE TABLE candidates AS SELECT DISTINCT molecule_id FROM geo')
    # Scan the FULL current index. Filtering to candidate molecules keeps all
    # their index members, including any conformers beyond the smoke prefix.
    scan_started = time.monotonic()
    db.execute('CREATE TABLE candidate_index AS SELECT i.* FROM idx i JOIN candidates c USING(molecule_id)')
    scan_seconds = time.monotonic() - scan_started
    if db.execute('SELECT count(*)-count(DISTINCT record_id) FROM candidate_index').fetchone()[0]:
        raise ValueError('Duplicate candidate record IDs in the full current index')
    mismatch = db.execute('''SELECT count(*) FROM geo g LEFT JOIN candidate_index i USING(record_id)
       WHERE i.record_id IS NULL OR g.molecule_id <> i.molecule_id''').fetchone()[0]
    if mismatch:
        raise ValueError(f'Smoke identities absent from or inconsistent with the current index: {mismatch}')
    xcond = ' AND '.join('NOT coalesce(i.' + code + ',false)' for code in X_CODES)
    db.execute(f'CREATE TABLE after_x AS SELECT i.* FROM candidate_index i WHERE {xcond}')
    db.execute('''CREATE TABLE coverage_counts AS SELECT i.molecule_id,
      count(*) AS after_x_conformer_count,
      count(g.record_id) AS evaluated_after_x_conformer_count,
      count(*) FILTER(WHERE g.record_id IS NULL) AS missing_after_x_conformer_count
      FROM after_x i LEFT JOIN geo g USING(record_id) GROUP BY i.molecule_id''')
    db.execute('''CREATE TABLE coverage AS SELECT c.molecule_id,
      coalesce(v.after_x_conformer_count,0) AS after_x_conformer_count,
      coalesce(v.evaluated_after_x_conformer_count,0) AS evaluated_after_x_conformer_count,
      coalesce(v.missing_after_x_conformer_count,0) AS missing_after_x_conformer_count,
      coalesce(v.after_x_conformer_count>0 AND v.missing_after_x_conformer_count=0,false)
        AS complete_after_x_geometry_coverage
      FROM candidates c LEFT JOIN coverage_counts v USING(molecule_id)''')
    # Match wp1_report.py exactly: geometry X01 augments index X01, G/B use
    # annotation-first coalesce, and only explicitly evaluated records can pass.
    db.execute('''CREATE TABLE combined AS SELECT i.* EXCLUDE(X01,G01,G02,G03,B01),
      coalesce(i.X01,false) OR coalesce(g.geometry_X01,false) AS X01,
      coalesce(g.G01,i.G01,false) AS G01,coalesce(g.G02,i.G02,false) AS G02,
      coalesce(g.G03,i.G03,false) AS G03,coalesce(g.B01,i.B01,false) AS B01,
      g.C02,g.C03,g.I01,g.T01,g.geometry_X01,
      g.record_id IS NOT NULL AS geometry_evaluated,
      g.reidentified_smiles,g.reidentified_inchikey,g.reidentified_connectivity_key,
      g.connectivity_mismatch,g.stereo_only_key_mismatch,g.error AS geometry_error,
      g.geometry_seconds,v.after_x_conformer_count,v.evaluated_after_x_conformer_count,
      v.complete_after_x_geometry_coverage
      FROM after_x i JOIN coverage v USING(molecule_id) LEFT JOIN geo g USING(record_id)
      WHERE v.complete_after_x_geometry_coverage''')
    keep = ' AND '.join('NOT coalesce(' + code + ',false)' for code in EXCLUDE)
    db.execute('ALTER TABLE combined ADD COLUMN retained BOOLEAN')
    db.execute(f'UPDATE combined SET retained=geometry_evaluated AND ({keep})')
    db.execute('''CREATE TABLE votes AS SELECT molecule_id,reidentified_inchikey,count(*) AS votes
      FROM combined WHERE reidentified_inchikey IS NOT NULL GROUP BY molecule_id,reidentified_inchikey''')
    db.execute('CREATE TABLE vote_max AS SELECT molecule_id,max(votes) AS max_votes FROM votes GROUP BY molecule_id')
    # S02 has the same after-X molecular minimum semantics as wp1_report.py.
    db.execute('CREATE TABLE minima AS SELECT molecule_id,min(energy_raw) AS energy_min FROM combined GROUP BY molecule_id')
    observed = EXCLUDE + ['B01', 'T01']
    codes = ','.join('CASE WHEN coalesce(c.' + code + ',false) THEN ' + q(code) + ' END' for code in observed)
    db.execute(f'''CREATE TABLE quality AS SELECT c.*,v.votes AS identity_votes,vm.max_votes,
      coalesce(v.votes<vm.max_votes,false) AS S01,
      c.energy_raw-m.energy_min AS S02_delta_energy_kcal_mol,
      list_filter([{codes},CASE WHEN v.votes<vm.max_votes THEN 'S01' END],x -> x IS NOT NULL) AS quality_codes
      FROM combined c LEFT JOIN votes v USING(molecule_id,reidentified_inchikey)
      LEFT JOIN vote_max vm USING(molecule_id) LEFT JOIN minima m USING(molecule_id)''')
    db.execute('''CREATE TABLE molecules AS SELECT molecule_id,count(*) AS conformers,
      max(total_atoms) AS total_atoms,max(heavy_atoms) AS heavy_atoms,
      min(energy_raw) FILTER(WHERE isfinite(energy_raw)) AS lowest_stored_energy,
      CASE WHEN max(heavy_atoms)<=10 THEN '0_10' WHEN max(heavy_atoms)<=20 THEN '11_20'
        WHEN max(heavy_atoms)<=30 THEN '21_30' WHEN max(heavy_atoms)<=50 THEN '31_50'
        WHEN max(heavy_atoms)<=75 THEN '51_75' WHEN max(heavy_atoms)<=100 THEN '76_100'
        ELSE 'above_100' END AS size_stratum
      FROM quality WHERE retained GROUP BY molecule_id''')
    available = rows(db, 'SELECT * FROM molecules')
    population = rows(db, '''SELECT count(*) AS smoke_molecules,
      count(*) FILTER(WHERE complete_after_x_geometry_coverage) AS completely_evaluated_molecules,
      sum(after_x_conformer_count) AS candidate_after_x_records,
      sum(evaluated_after_x_conformer_count) AS smoke_evaluated_after_x_records,
      sum(missing_after_x_conformer_count) AS unassessed_candidate_after_x_records FROM coverage''')[0]
    population['complete_retained_molecules'] = len(available)
    population['complete_retained_records'] = sum(int(r['conformers']) for r in available)
    db.execute(f'''COPY (SELECT v.*,coalesce(m.conformers,0) AS retained_conformer_count,
      m.size_stratum FROM coverage v LEFT JOIN molecules m USING(molecule_id) ORDER BY molecule_id)
      TO {q(completeness_path)} (FORMAT PARQUET,COMPRESSION ZSTD)''')
    report = {'status': 'PREPARING_BOUNDED_NATIVE_INTEGRATION_PANEL',
      'scope': 'BOUNDED_NATIVE_INTEGRATION_TEST_POPULATION',
      'is_formal_wp4_10000_record_panel': False,
      'population_limitation': 'Only molecules in the 1000-record geometry smoke whose complete current-index after-X population was evaluated; no full-corpus sampling inference.',
      'seed': args.seed, 'target_records': args.records, 'minimum_molecules': args.min_molecules,
      'population': population, 'input': {'record_index': inputs_before['index'],
        'geometry': inputs_before['geometry'], 'geometry_sha256': geometry_sha},
      'output': str(panel), 'threads': args.workers, 'job_id': os.environ['SLURM_JOB_ID'],
      'hostname': socket.gethostname(), 'python_logical_entry': sys.executable,
      'software': {'duckdb': duckdb.__version__, 'pyarrow': pa.__version__},
      'script_sha256': sha(Path(__file__).absolute()),
      'full_candidate_index_scan_seconds': scan_seconds,
      'retention_codes': EXCLUDE, 'retention_rule_matches': str(ROOT / 'scripts/wp1_report.py'),
      'all_retained_conformers_of_each_selected_molecule': True,
      'complete_current_index_after_x_conformers_evaluated_before_selection': True,
      'native_identity_or_status_synthesized': False,
      'panel_columns_added': ['size_stratum', 'retained_conformer_count', 'molecule_lowest_energy_conformer'],
      'no_lmdb_created_or_written': True,
      'source_index_modified': False, 'completeness_audit': str(completeness_path)}
    if len(available) < args.min_molecules:
        report.update(status='INSUFFICIENT_COMPLETE_RETAINED_MOLECULES', actual_records=0,
                      molecules=0, panel_written=False,
                      reason=f'Only {len(available)} complete retained molecules; at least {args.min_molecules} required')
        report['seconds'] = time.monotonic() - started
        write_json(manifest_path, report)
        db.close()
        print(json.dumps({'status': report['status'], 'population': population}))
        return 2
    # Same record-budget strategy as select_native_panel.py, limited to this
    # eligible smoke population. Never cut a molecule to hit the target exactly.
    grouped = {}
    for row in available:
        grouped.setdefault(row['size_stratum'], []).append(row)
    for group in grouped.values():
        group.sort(key=lambda r: (hashlib.sha256((r['molecule_id'] + '|' + str(args.seed)).encode()).hexdigest(), r['molecule_id']))
    budgets = {key: min(sum(int(r['conformers']) for r in group), args.records // len(grouped))
               for key, group in grouped.items()}
    remaining = args.records - sum(budgets.values())
    while remaining > 0:
        eligible = [key for key in sorted(grouped) if budgets[key] < sum(int(r['conformers']) for r in grouped[key])]
        if not eligible:
            break
        step = max(1, remaining // len(eligible))
        for key in eligible:
            add = min(step, remaining, sum(int(r['conformers']) for r in grouped[key]) - budgets[key])
            budgets[key] += add
            remaining -= add
    selected, offsets, selected_counts = [], {}, {}
    for key in sorted(grouped):
        total, offset = 0, 0
        while offset < len(grouped[key]) and (total < budgets[key] or offset == 0):
            row = grouped[key][offset]
            selected.append(row)
            total += int(row['conformers'])
            offset += 1
        offsets[key], selected_counts[key] = offset, total
    while len(selected) < args.min_molecules:
        keys = [key for key in grouped if offsets[key] < len(grouped[key])]
        key = min(keys, key=lambda k: (selected_counts[k], k))
        row = grouped[key][offsets[key]]
        selected.append(row)
        offsets[key] += 1
        selected_counts[key] += int(row['conformers'])
    db.register('selected_arrow', pa.Table.from_pylist(selected))
    db.execute('CREATE TABLE selected AS SELECT * FROM selected_arrow')
    db.execute('''CREATE TABLE lowest AS SELECT molecule_id,record_id FROM
      (SELECT molecule_id,record_id,row_number() OVER(PARTITION BY molecule_id
        ORDER BY energy_raw,coalesce(conformer_id,0),record_id) AS rank
       FROM quality WHERE retained AND energy_raw IS NOT NULL AND isfinite(energy_raw))
      WHERE rank=1''')
    pending = panel.with_suffix('.parquet.pending')
    db.execute(f'''COPY (SELECT q.*,s.size_stratum,s.conformers AS retained_conformer_count,
      coalesce(q.record_id=l.record_id,false) AS molecule_lowest_energy_conformer
      FROM quality q JOIN selected s USING(molecule_id) LEFT JOIN lowest l USING(molecule_id)
      WHERE q.retained ORDER BY s.size_stratum,q.molecule_id,coalesce(q.conformer_id,0),q.record_id)
      TO {q(pending)} (FORMAT PARQUET,COMPRESSION ZSTD)''')
    metadata = pq.read_metadata(pending)
    expected_records = sum(int(r['conformers']) for r in selected)
    if metadata.num_rows != expected_records:
        raise ValueError(f'Panel population differs: {metadata.num_rows} vs {expected_records}')
    inputs_after = {'index': identity(args.index), 'geometry': identity(args.geometry)}
    if inputs_before != inputs_after or sha(args.geometry) != geometry_sha:
        raise RuntimeError('Input changed during bounded panel construction; pending output preserved')
    os.replace(pending, panel)
    strata = []
    for key in sorted(grouped):
        population_records = sum(int(r['conformers']) for r in grouped[key])
        n_molecules = sum(1 for r in selected if r['size_stratum'] == key)
        strata.append({'size_stratum': key, 'molecules': n_molecules,
          'records': selected_counts[key], 'population_records': population_records,
          'population_molecules': len(grouped[key]),
          'record_population_weight': population_records / selected_counts[key],
          'molecule_population_weight': len(grouped[key]) / n_molecules,
          'population_weight_scope': 'Eligible smoke integration population only; not full corpus'})
    report.update(status='READY_FOR_NATIVE_WP4', actual_records=metadata.num_rows,
      molecules=len(selected), strata=strata, panel_written=True, panel_sha256=sha(panel),
      sampling='Deterministic whole-molecule hash sample, balanced retained-record budgets over every available heavy-atom stratum; minimum molecule count enforced',
      target_record_shortfall=max(0, args.records-metadata.num_rows),
      available_heavy_atom_strata=sorted(grouped),
      selected_molecule_ids=sorted(r['molecule_id'] for r in selected),
      seconds=time.monotonic()-started)
    write_json(manifest_path, report)
    db.close()
    print(json.dumps({key: report[key] for key in ('status', 'scope', 'actual_records', 'molecules', 'strata')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
