"""Prepare 1,000 already-complete molecules and their fixed-order first two UFF conformers."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct

from common import (canonical, load_config, new_output, ordered_two, reference,
                    require_pin, require_preflight, runtime, stable_key, write_json)


def quote(text):
    return "'" + str(text).replace("'", "''") + "'"


def coordinate_sha(coordinates):
    flat = [float(v) for row in coordinates for v in row]
    return hashlib.sha256(struct.pack('<' + 'd' * len(flat), *flat)).hexdigest()


def stratified_audit(rows, fraction=0.01, seed=20261010):
    """Largest-remainder allocation gives exactly round(1% * records), without duplicates."""
    groups = defaultdict(list)
    for row in rows:
        groups[(int(row['file_group']), row['size_stratum'])].append(row)
    target = round(len(rows) * fraction)
    counts = {key: int(len(value) * fraction) for key, value in groups.items()}
    remainder = sorted(groups, key=lambda key: (-(len(groups[key]) * fraction - counts[key]), key))
    for key in remainder[:target - sum(counts.values())]:
        counts[key] += 1
    chosen = []
    for key in sorted(groups):
        ranked = sorted(groups[key], key=lambda row: (
            hashlib.sha256(f'{seed}|{row["record_id"]}'.encode()).hexdigest(), row['record_id']))
        chosen.extend(ranked[:counts[key]])
    return chosen


def source_paths(plan):
    if isinstance(plan, list):
        return plan
    if 'sources' in plan:
        return plan['sources']
    found = {int(s['shard_id']): s for m in plan['manifests'].values() for s in m['shards']}
    return [found[k] for k in sorted(found)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--root-preflight', required=True, type=Path)
    args = parser.parse_args()
    c = load_config(args.config)
    observed = runtime(prepare=True)
    approval = require_preflight(args.root_preflight, args.config, c)
    for pin in c['large_authority_pins']:
        require_pin(pin, full_hash=False)
    out = new_output(args.output, c)
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(16)
    pa.set_io_thread_count(4)
    roles = json.loads(require_pin(c['role_manifest']).read_text())
    if roles['status'] != 'ROUTINE_MOLECULE_VAL_ROLES_FROZEN' or roles['roles']['VAL'] != {'molecules': 7610, 'records': 72525}:
        raise ValueError('FROZEN_ROUTINE_MOLECULE_ROLE_AUTHORITY_REQUIRED')
    val_pin = next(p for p in roles['outputs'] if Path(p['path']).name == 'validation_molecules.parquet')
    validation = pq.read_table(require_pin(val_pin), columns=['molecule_id'])
    val_ids = sorted(set(validation['molecule_id'].to_pylist()))
    if len(val_ids) != 7610:
        raise ValueError('ROUTINE_MOLECULE_MEMBERSHIP_CHANGED')
    db = duckdb.connect()
    db.execute("SET threads=16; SET memory_limit='12GB'")
    db.register('routine_molecules', pa.table({'molecule_id': val_ids}))
    db.execute('CREATE VIEW p AS SELECT * FROM read_parquet(' + quote(c['per_molecule']) + ')')
    db.execute('CREATE VIEW m AS SELECT * FROM read_parquet(' + quote(c['molecule_index']) + ')')
    if db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM p').fetchone() != (1220466, 1220466):
        raise ValueError('S_SPRIME_ALIGNMENT_POPULATION_CHANGED')
    role_check = db.execute("SELECT count(*), count(*) FILTER(WHERE p.split_role='FULL') FROM p JOIN routine_molecules USING(molecule_id)").fetchone()
    if role_check != (7610, 7610):
        raise ValueError('ROUTINE_NOT_EXACT_FULL_SUBSET')
    # Complete, existing molecules need no future filling and retain this order.
    db.execute("""CREATE TEMP TABLE eligible AS SELECT p.*,m.file_group,m.max_heavy_atoms,
        m.max_total_atoms,CASE WHEN v.molecule_id IS NOT NULL THEN 'VAL' ELSE 'TRAIN' END AS effective_role,
        CASE WHEN m.max_heavy_atoms<=20 THEN '0_20' WHEN m.max_heavy_atoms<=40 THEN '21_40'
             WHEN m.max_heavy_atoms<=75 THEN '41_75' ELSE 'above_75' END AS size_stratum
        FROM p JOIN m USING(molecule_id) LEFT JOIN routine_molecules v USING(molecule_id)
        WHERE (p.split_role='TRAIN' OR v.molecule_id IS NOT NULL)
          AND p.S_conformers>=2 AND p.Sprime_conformers>=p.S_conformers""")
    seed = quote(str(c['selection_seed']))
    selected = db.execute("""SELECT * FROM (SELECT *,row_number() OVER(PARTITION BY
        file_group,effective_role,size_stratum ORDER BY sha256(molecule_id||SEED),molecule_id) AS rank
        FROM eligible) ORDER BY rank,sha256(molecule_id||SEED),molecule_id LIMIT 1000""".replace('SEED', seed)).fetch_arrow_table()
    if len(selected) != 1000:
        raise ValueError('FEWER_THAN_1000_COMPLETE_TWO_CONFORMER_MOLECULES')
    metadata = {r['molecule_id']: r for r in selected.to_pylist()}
    prior = defaultdict(list)
    manifest = json.loads(Path(c['sprime_manifest']).read_text())
    source_refs = []
    for pin in manifest['references']:
        if pin['kind'] != 'conformers':
            continue
        path = require_pin(pin, full_hash=False)
        before = path.stat()
        values = pq.read_table(path, filters=[('molecule_id', 'in', list(metadata)),
                                             ('status', '=', 'SUCCESS'), ('converged', '=', True)])
        for row in values.to_pylist():
            prior[row['molecule_id']].append(row)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError('SPRIME_SOURCE_CHANGED_DURING_SELECTED_READ')
        source_refs.append(dict(pin, verification='closed manifest hash inherited; current size and selected rows checked'))
    picked = []
    for mid, meta in sorted(metadata.items()):
        if len(prior[mid]) != int(meta['Sprime_conformers']):
            raise ValueError('SELECTED_SPRIME_USABLE_COUNT_CHANGED:' + mid)
        picked.extend((mid, rank, row) for rank, row in enumerate(ordered_two(prior[mid], mid, c['order_seed'])))
    source_ids = sorted({row['source_record_id'] for _, _, row in picked})
    db.register('selected_source_ids', pa.table({'record_id': source_ids}))
    pointers = db.execute('SELECT r.* FROM read_parquet(' + quote(c['record_index']) +
                          ') r JOIN selected_source_ids s USING(record_id)').fetch_arrow_table().to_pylist()
    by_record = {r['record_id']: r for r in pointers}
    if len(by_record) != len(source_ids) or len(pointers) != len(source_ids):
        raise ValueError('SPRIME_SOURCE_POINTERS_NOT_UNIQUE_AND_COMPLETE')
    source_plan = source_paths(json.loads(require_pin(c['source_plan']).read_text()))
    by_path = {s['path']: int(s['shard_id']) for s in source_plan}
    pairs = []
    for mid, rank, conformer in picked:
        source = dict(by_record[conformer['source_record_id']])
        meta = metadata[mid]
        if source['molecule_id'] != mid:
            raise ValueError('CONFORMER_MOLECULE_SOURCE_MISMATCH')
        source.update(shard_id=by_path[source['source_path']], file_group=int(meta['file_group']),
                      size_stratum=meta['size_stratum'], effective_role=meta['effective_role'],
                      source_role=meta['split_role'])
        rid = f'pprime:{mid}:{conformer["sprime_conf_idx"]}'
        pairs.append({'record_id': rid, 'molecule_id': mid, 'random_order_rank': rank,
                      'geometry_source': 'uff_sprime', 'source': source, 'conformer': conformer,
                      'uff_coordinate_sha256': coordinate_sha(conformer['coordinates']),
                      'conformer_row_sha256': hashlib.sha256(canonical(conformer)).hexdigest()})
    if len(pairs) != 2000 or len({p['record_id'] for p in pairs}) != 2000:
        raise ValueError('PILOT_PAIRS_NOT_EXACTLY_2000_UNIQUE_RECORDS')
    payload = b''.join(canonical(p) + b'\n' for p in pairs)
    with (out / 'pairs.jsonl').open('xb') as stream:
        stream.write(payload)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    audit_rows = [{'record_id': p['record_id'], 'file_group': p['source']['file_group'],
                   'size_stratum': p['source']['size_stratum']} for p in pairs]
    audited = stratified_audit(audit_rows)
    audit_path = out / 'audit_selected.parquet'
    pq.write_table(pa.Table.from_pylist(audited), audit_path, compression='zstd')
    audit_ref = dict(reference(audit_path), rows=len(audited))
    audit = {'schema': 'WP5_STRATIFIED_RECORD_AUDIT_V1', 'status': 'AUDIT_MEMBERSHIP_CLOSED',
             'selected_records': audit_ref, 'fraction': 0.01, 'seed': 20261010,
             'lineage': 'new P-prime membership; original WP5 audit unchanged'}
    write_json(out / 'audit_membership.json', audit)
    report = {'status': 'PPRIME_PAIRS_READY_NOT_QM_EXECUTED', 'runtime': observed,
              'config': reference(args.config), 'root_preflight': reference(args.root_preflight),
              'molecules': 1000, 'conformers': 2000, 'audit_records': len(audited),
              'role_counts': dict(Counter(m['effective_role'] for m in metadata.values())),
              'eligible_molecules': db.execute('SELECT count(*) FROM eligible').fetchone()[0],
              'eligible_N1_excluded_from_this_pilot': db.execute("SELECT count(*) FROM p LEFT JOIN routine_molecules v USING(molecule_id) WHERE (p.split_role='TRAIN' OR v.molecule_id IS NOT NULL) AND p.S_conformers=1").fetchone()[0],
              'population_status': 'already-complete subset; final common-population release not claimed',
              'source_sprime_references': source_refs,
              'large_source_hash_scope': 'inherited closed authority pins; no full source-file rehash',
              'outputs': [reference(out / 'pairs.jsonl'), audit_ref,
                          reference(out / 'audit_membership.json')],
              'original_lmdb_opened': False, 'QM_started': False}
    write_json(out / 'prepared.json', report)
    db.close()
    print(json.dumps({'status': report['status'], 'output': str(out)}))


if __name__ == '__main__':
    main()
