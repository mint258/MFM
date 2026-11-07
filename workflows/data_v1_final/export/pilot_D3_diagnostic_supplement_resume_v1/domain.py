"""Finite readonly C0 domain projection; exact seen intersection and D5 lineage."""
import json
import pathlib
from . import contract as C
from workflows.data_v1_final.export.pilot_family_D3_fast55k_resume_v1 import domain as D, io as I
from workflows.data_v1_final.export.d5_inputs_compound_day_v1 import core as W


def build(plan, receipt, prior, d5, root, roots, budget):
    import pyarrow as pa
    from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as B
    path = pathlib.Path(plan['closed_D3_domain_locator'])
    C.need(path == pathlib.Path(prior['output_directory']) / 'domain.sqlite' and
           not any(pathlib.Path(str(path) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')),
           'CLOSED_C0_DOMAIN_ONLY_NO_ACTIVE_SQLITE')
    before = I.identity(path)
    origin = I.pin(path)  # First DATA hash is on this actual admitted CPU, not login.
    source = I.connect(path, True)
    db = I.connect(root / 'domain.sqlite')
    tables = ('molecules', 'geometries', 'orders', 'excluded', 'native_bases', 'pieces', 'closed_groups', 'exported', 'stores')
    for name in tables:
        sql = source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
        C.need(sql is not None and sql[0].startswith('CREATE TABLE '), 'EXACT_CLOSED_D3_DOMAIN_TABLE:' + name)
        db.execute(sql[0])
    db.execute('CREATE INDEX supplement_mid ON geometries(mid,src)')
    db.execute('CREATE TABLE wanted_rids(rid TEXT PRIMARY KEY)')
    train = {r[0] for r in source.execute("SELECT mid FROM molecules WHERE role='TRAIN'")}
    seen = {r[0] for r in source.execute("SELECT DISTINCT g.mid FROM exported e JOIN geometries g ON g.gid=e.gid JOIN molecules m ON m.mid=g.mid WHERE m.role='TRAIN'")}
    C.need(len(train) == 50000 and seen == train, 'ACTUAL_D3_SEEN_TRAIN_MIDS_NOT_ROLE_NAME_ALONE')
    components = d5['components']
    bases, global_mids = {}, set()
    for row in D.row_stream(components['diagnostic_base_reference'], roots, budget.check):
        key = (row['molecule_id'], row['geometry_source'])
        C.need(key not in bases, 'UNIQUE_ORIGINAL_D5_HELD_BASE')
        bases[key] = row['geometry_id']
        global_mids.add(row['molecule_id'])
    C.need(len(global_mids) == 20000 and len(bases) == 40000 and
           all((mid, src) in bases for mid in global_mids for src in ('pm7', 'uff_sprime')),
           'WHOLE_REAL_D5_20K_AND_TWO_SOURCE_BASES_NOT_RESELECTED')
    chosen = seen & global_mids
    targets = {}
    for row in D.row_stream(components['diagnostic_targets_reference'], roots, budget.check):
        if row['molecule_id'] not in chosen:
            continue
        C.need(row['geometry_id'] not in targets, 'UNIQUE_FORMAL_D5_BASE_CHILD_INPUT_VIEW_TARGET')
        targets[row['geometry_id']] = row
    expected = {r[0] for r in source.execute('SELECT e.gid FROM excluded e JOIN geometries g ON g.gid=e.gid')
                if source.execute('SELECT mid FROM geometries WHERE gid=?', (r[0],)).fetchone()[0] in chosen}
    C.need(set(targets) == expected, 'FORMAL_D5_ALL_TARGETS_EQUAL_CLOSED_D4_D3_HELD_DOMAIN_IN_SEEN_INTERSECTION')
    for mid in sorted(chosen):
        row = source.execute('SELECT * FROM molecules WHERE mid=?', (mid,)).fetchone()
        db.execute('INSERT INTO molecules VALUES(?,?,?,?,?)', tuple(row))
    geometries, anchors, indices = {}, set(), []
    for gid, target in targets.items():
        budget.check()
        row = source.execute('SELECT * FROM geometries WHERE gid=?', (gid,)).fetchone()
        C.need(row is not None and row['selected'] == 0 and row['mid'] == target['molecule_id'] and row['src'] == target['geometry_source'],
               'REAL_HELD_TARGET_NOT_IN_ORIGINAL_TRAIN_EXPORT')
        C.need(source.execute('SELECT 1 FROM exported WHERE gid=?', (gid,)).fetchone() is None,
               'HELD_GEOMETRY_NEVER_PREVIOUSLY_EXPORTED_AS_TRAIN')
        geometry = W.decode(row['row'])
        C.need(row['parent'] == geometry['parent_geometry_id'] and row['view'] == geometry['view_id'],
               'CLOSED_SQL_AND_ORIGINAL_GEOMETRY_PARENT_VIEW_AGREE')
        base = geometry['parent_geometry_id'] is None and row['aux'] == 0
        parent = bases[(row['mid'], row['src'])]
        C.need((base and gid == parent) or (not base and geometry['parent_geometry_id'] == parent),
               'EXACT_D5_BASE_AND_DIRECT_CHILD_INPUT_VIEW_PARENT_NOT_TASK_NAME_ALIAS')
        rank = source.execute("SELECT rank FROM orders WHERE gid=? AND kind='fixed_random'", (gid,)).fetchall()
        n = source.execute('SELECT N FROM molecules WHERE mid=?', (row['mid'],)).fetchone()[0]
        C.need((len(rank) == 1 and rank[0][0] == n - 1) if base else not rank,
               'ORIGINAL_LAST_FIXED_RANDOM_RANK_NOT_RENUMBERED_DIAGNOSTIC_INDEX')
        values = list(row)
        values[5] = 1  # Private diagnostic export membership only; no scientific mask is changed.
        db.execute('INSERT INTO geometries VALUES(?,?,?,?,?,?,?,?)', values)
        db.execute('INSERT INTO excluded VALUES(?)', (gid,))
        for order in source.execute('SELECT * FROM orders WHERE gid=?', (gid,)):
            db.execute('INSERT INTO orders VALUES(?,?,?,?,?)', tuple(order))
        rid = geometry.get('native_record_id') if row['src'] == 'pm7' else geometry.get('native_anchor_record_id')
        C.need(type(rid) is str and rid, 'REAL_NATIVE_GRAPH_ANCHOR_FOR_HELD_GEOMETRY')
        anchors.add(rid)
        if row['src'] == 'pm7':
            db.execute('INSERT OR IGNORE INTO wanted_rids VALUES(?)', (rid,))
        geometries[gid] = geometry
        indices.append({'molecule_id': row['mid'], 'geometry_id': gid, 'geometry_source': row['src'],
                        'parent_geometry_id': geometry['parent_geometry_id'], 'view_id': geometry['view_id'],
                        'is_base': base, 'original_fixed_random_rank': rank[0][0] if base else None,
                        'original_N': n, 'native_record_id': geometry['native_record_id'],
                        'sprime_conf_idx': geometry['sprime_conf_idx'], 'diagnostic_base_geometry_id': parent,
                        'sample_role': C.ROLE, 'training_excluded': True})
    for rid in anchors:
        row = source.execute('SELECT rid,gid FROM native_bases WHERE rid=?', (rid,)).fetchone()
        C.need(row is not None, 'ORIGINAL_NATIVE_ANCHOR_EXISTS')
        db.execute('INSERT INTO native_bases VALUES(?,?)', tuple(row))
        if row['gid'] not in geometries:
            original = source.execute('SELECT * FROM geometries WHERE gid=?', (row['gid'],)).fetchone()
            values = list(original)
            values[5] = 0
            db.execute('INSERT INTO geometries VALUES(?,?,?,?,?,?,?,?)', values)
    schema = pa.schema([('molecule_id', pa.string()), ('geometry_id', pa.string()), ('geometry_source', pa.string()),
        ('parent_geometry_id', pa.string()), ('view_id', pa.string()), ('is_base', pa.bool_()),
        ('original_fixed_random_rank', pa.int64()), ('original_N', pa.int64()), ('native_record_id', pa.string()),
        ('sprime_conf_idx', pa.int64()), ('diagnostic_base_geometry_id', pa.string()), ('sample_role', pa.string()), ('training_excluded', pa.bool_())])
    index = B.write_parquet(root / 'selected_diagnostic_geometry_ids.parquet', iter(sorted(indices, key=lambda r: r['geometry_id'])), schema)
    mids_schema = pa.schema([('molecule_id', pa.string()), ('sample_role', pa.string())])
    mids = B.write_parquet(root / 'actual_seen_diagnostic_molecule_ids.parquet',
                           ({'molecule_id': mid, 'sample_role': C.ROLE} for mid in sorted(chosen)), mids_schema)
    db.commit()
    source.close()
    C.need(I.identity(path) == before, 'ORIGINAL_C0_D3_DATABASE_FRAME_UNCHANGED')
    return db, {'closed_D3_domain_origin_reference': origin, 'global_D5_diagnostic_MIDs': 20000,
                'actual_D3_seen_TRAIN_MIDs': 50000, 'actual_seen_D5_intersection_MIDs': len(chosen),
                'global_D5_MIDs_outside_actual_seen_TRAIN': len(global_mids - seen),
                'selected_diagnostic_geometry_ids_reference': index,
                'actual_seen_diagnostic_molecule_ids_reference': mids,
                'selected_geometries': len(indices), 'selected_bases': sum(r['is_base'] for r in indices),
                'selected_child_input_views': sum(not r['is_base'] for r in indices)}
