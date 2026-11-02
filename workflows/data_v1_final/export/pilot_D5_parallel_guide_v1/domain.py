"""Indexed projection of frozen held targets from the closed D4 SQLite source."""
import collections
import hashlib
import json
import pathlib
import struct
from . import contract as C
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import domain as D, io as I
from workflows.data_v1_final.export.lossless_sqlite_io_v1 import codec as W


def build(plan, accepted, d5, root, roots, budget):
    import pyarrow as pa
    from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as B
    from workflows.data_v1_final.pprime.geometry import geometry_hash
    components = accepted['component_references']
    population = D.read(components['population_reference'], roots)
    pre = D.read(population['preselection_reference'], roots)
    C.need(population['pilot_counts'] == pre['pilot_counts'] == C.O.COUNTS and pre['seed'] == 20261025 and
           pre['final_Common'] is False and pre['pilot_ready_scalar_only'] is True,
           'SAME_FROZEN55K_PRESELECTION_NOT_NEW_DIAGNOSTIC_SAMPLE')
    selected = {r['molecule_id']: r for r in D.row_stream(pre['tables']['pilot55k'], roots, budget.check)}
    C.need(len(selected) == 55000 and collections.Counter(r['effective_role'] for r in selected.values()) == C.O.COUNTS,
           'ACTUAL50000_TRAIN5000_ROUTINE_VAL_ROSTER')
    train = {mid for mid, row in selected.items() if row['effective_role'] == 'TRAIN'}
    global_bases = {}
    for row in D.row_stream(d5['components']['diagnostic_base_reference'], roots, budget.check):
        key = row['molecule_id'], row['geometry_source']
        C.need(key not in global_bases, 'UNIQUE_FORMAL_D5_BASE')
        global_bases[key] = row['geometry_id']
    global_mids = {mid for mid, src in global_bases}
    C.need(len(global_mids) == 20000 and len(global_bases) == 40000 and
           all((mid, src) in global_bases for mid in global_mids for src in ('pm7', 'uff_sprime')),
           'EXACT_ORIGINAL_GLOBAL20K_TWO_SOURCE_BASES')
    chosen = train & global_mids
    geometry = D.read(components['geometry_reference'], roots)
    C.need(geometry['all_in_scope_actual_direct_children_bound'] is True and geometry['unknown_input_bindings'] == 0 and
           geometry['available_orders'] == ['fixed_random'] and geometry['full_three_order'] is False,
           'ACTUAL_CLOSED_D4_CHILD_BINDINGS_FIXED_RANDOM_ONLY')
    bases = {}
    for row in D.row_stream(geometry['diagnostic_base_reference'], roots, budget.check):
        key = row['molecule_id'], row['geometry_source']
        C.need(key not in bases and key in global_bases and row['geometry_id'] == global_bases[key],
               'D4_HELD_BASE_IS_ORIGINAL_D5_BASE_NOT_RESELECTED')
        bases[key] = row['geometry_id']
    C.need({mid for mid, src in bases} == chosen and len(bases) == 2 * len(chosen),
           'EXACT_FROZEN_PILOT_TRAIN_GLOBAL_D5_INTERSECTION')
    targets = {}
    for row in D.row_stream(geometry['diagnostic_target_reference'], roots, budget.check):
        C.need(row['geometry_id'] not in targets and row['molecule_id'] in chosen,
               'UNIQUE_ACTUAL_D4_HELD_BASE_CHILD_INPUT_VIEW_TARGET')
        targets[row['geometry_id']] = row
    formal = {r['geometry_id']: r for r in D.row_stream(d5['components']['diagnostic_targets_reference'], roots, budget.check)
              if r['molecule_id'] in chosen}
    C.need(targets == formal, 'D4_HELD_TARGETS_EXACT_FORMAL_D5_INTERSECTION')
    binding = D.register(geometry['cell_binding_reference'], roots)
    path = pathlib.Path(I.require(binding))
    C.need(not any(pathlib.Path(str(path) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')),
           'CLOSED_D4_GEOMETRY_SQLITE_NO_ACTIVE_JOURNAL')
    before = I.identity(path)
    source = I.connect(path, True)
    db = I.connect(root / 'domain.sqlite')
    db.executescript('CREATE TABLE molecules(mid TEXT PRIMARY KEY,role TEXT,source_role TEXT,N INTEGER,row TEXT);'
      'CREATE TABLE geometries(gid TEXT PRIMARY KEY,mid TEXT,src TEXT,parent TEXT,view TEXT,selected INTEGER,aux INTEGER,row BLOB);'
      'CREATE INDEX supplement_mid ON geometries(mid,src);'
      'CREATE TABLE orders(mid TEXT,src TEXT,kind TEXT,rank INTEGER,gid TEXT,PRIMARY KEY(mid,src,kind,rank));'
      'CREATE TABLE excluded(gid TEXT PRIMARY KEY);CREATE TABLE native_bases(rid TEXT PRIMARY KEY,gid TEXT UNIQUE);'
      'CREATE TABLE pieces(gid TEXT,part TEXT,n INTEGER,payload BLOB,source_locator TEXT,PRIMARY KEY(gid,part));'
      'CREATE TABLE closed_groups(key TEXT PRIMARY KEY,ref TEXT);'
      'CREATE TABLE exported(store TEXT,gid TEXT,kind TEXT,parts TEXT,PRIMARY KEY(store,gid));'
      'CREATE TABLE stores(name TEXT PRIMARY KEY,path TEXT,ref TEXT);CREATE TABLE wanted_rids(rid TEXT PRIMARY KEY);')
    for row in D.row_stream(pre['tables']['complete_old_mother'], roots, budget.check):
        mid = row['molecule_id']
        if mid not in chosen:
            continue
        C.need(row['effective_role'] == selected[mid]['effective_role'] == 'TRAIN' and
               row['selection_rank'] == selected[mid]['selection_rank'] and row['scalar_complete_old_Sprime'] is True and
               type(row['S_conformers']) is int and row['S_conformers'] >= 2 and
               row['Sprime_conformers'] == row['S_conformers'] and type(row['source_role']) is str,
               'SAME_N_ROLE_AND_AT_LEAST_ONE_ORDINARY_TRAIN_BASE_AFTER_HELD_ANTI_JOIN')
        db.execute('INSERT INTO molecules VALUES(?,?,?,?,?)',
                   (mid, 'TRAIN', row['source_role'], row['S_conformers'], json.dumps(row, sort_keys=True)))
    C.need(db.execute('SELECT count(*) FROM molecules').fetchone()[0] == len(chosen),
           'ALL_ACTUAL_INTERSECTION_MOLECULES_WITH_ORIGINAL_N')
    anchors, indices = set(), []

    def fetch(gid):
        rows = []
        for table, aux in (('base', 0), ('children', 0), ('input_views', 1)):
            hit = source.execute('SELECT row FROM ' + table + ' WHERE gid=?', (gid,)).fetchone()
            if hit is not None:
                rows.append((W.decode(hit[0]), aux))
        C.need(len(rows) == 1, 'ONE_CLOSED_D4_GEOMETRY_FOR_GID_NOT_TASK_NAME')
        value, aux = rows[0]
        C.need(geometry_hash(value['atomic_numbers'], value['positions_A']) == value['geometry_sha256'] and
               hashlib.sha256(b''.join(struct.pack('<q', z) for z in value['atomic_numbers'])).hexdigest() == value['atom_order_sha256'],
               'ORIGINAL_F64_GEOMETRY_AND_ATOM_ORDER_HASH')
        return value, aux

    for gid, target in sorted(targets.items()):
        budget.check()
        value, aux = fetch(gid)
        mid, src, parent = value['molecule_id'], value['geometry_source'], value['parent_geometry_id']
        C.need(mid == target['molecule_id'] and src == target['geometry_source'], 'TARGET_MID_SOURCE_IDENTITY')
        base = parent is None and aux == 0
        held = bases[mid, src]
        C.need((base and gid == held) or (not base and parent == held), 'ONLY_ORIGINAL_HELD_BASE_AND_DIRECT_CHILD_INPUT_VIEW')
        db.execute('INSERT INTO geometries VALUES(?,?,?,?,?,?,?,?)',
                   (gid, mid, src, parent, value['view_id'], 1, aux, W.encode(value)))
        db.execute('INSERT INTO excluded VALUES(?)', (gid,))
        n = db.execute('SELECT N FROM molecules WHERE mid=?', (mid,)).fetchone()[0]
        if base:
            db.execute('INSERT INTO orders VALUES(?,?,?,?,?)', (mid, src, 'fixed_random', n - 1, gid))
        rid = value.get('native_record_id') if src == 'pm7' else value.get('native_anchor_record_id')
        C.need(type(rid) is str and rid, 'ACTUAL_NATIVE_GRAPH_ANCHOR')
        anchors.add(rid)
        if src == 'pm7':
            # Child IDs retain the same held native RID, never an unrelated source task.
            db.execute('INSERT OR IGNORE INTO wanted_rids VALUES(?)', (rid,))
        indices.append(dict(molecule_id=mid, geometry_id=gid, geometry_source=src, parent_geometry_id=parent,
            view_id=value['view_id'], is_base=base, original_fixed_random_rank=n - 1 if base else None,
            original_N=n, native_record_id=value['native_record_id'], sprime_conf_idx=value['sprime_conf_idx'],
            diagnostic_base_geometry_id=held, sample_role=C.ROLE, training_excluded=True))
    for rid in sorted(anchors):
        budget.check()
        hit = source.execute("SELECT gid,row FROM base WHERE rid=? AND src='pm7'", (rid,)).fetchone()
        C.need(hit is not None, 'REAL_NATIVE_ANCHOR_EXISTS_IN_CLOSED_D4')
        value = W.decode(hit['row'])
        C.need(value['molecule_id'] in chosen, 'ANCHOR_SAME_FROZEN_SEEN_MID')
        db.execute('INSERT INTO native_bases VALUES(?,?)', (rid, hit['gid']))
        if db.execute('SELECT 1 FROM geometries WHERE gid=?', (hit['gid'],)).fetchone() is None:
            db.execute('INSERT INTO geometries VALUES(?,?,?,?,?,?,?,?)',
                (hit['gid'], value['molecule_id'], 'pm7', value['parent_geometry_id'], value['view_id'], 0, 0, hit['row']))
    # Recheck the actual stored last fixed-random rank, rather than merely assigning N-1.
    found = {}
    for row in D.row_stream(geometry['table_references']['orders'], roots, budget.check):
        if row['geometry_id'] in targets and row['molecule_id'] in chosen:
            C.need(row['order_type'] == 'fixed_random', 'NO_UNAVAILABLE_ENERGY_DIVERSITY_ORDER')
            key = row['molecule_id'], row['geometry_source']
            C.need(key not in found and row['geometry_id'] == bases[key] and
                   row['rank'] == db.execute('SELECT N-1 FROM molecules WHERE mid=?', (row['molecule_id'],)).fetchone()[0],
                   'ACTUAL_ORIGINAL_LAST_FIXED_RANDOM_RANK_NOT_RENUMBERED')
            found[key] = row['geometry_id']
    C.need(found == bases, 'ALL_HELD_BASE_RANKS_MATCH_FROZEN_ORDER_TABLE')
    schema = pa.schema([('molecule_id', pa.string()), ('geometry_id', pa.string()), ('geometry_source', pa.string()),
        ('parent_geometry_id', pa.string()), ('view_id', pa.string()), ('is_base', pa.bool_()),
        ('original_fixed_random_rank', pa.int64()), ('original_N', pa.int64()), ('native_record_id', pa.string()),
        ('sprime_conf_idx', pa.int64()), ('diagnostic_base_geometry_id', pa.string()), ('sample_role', pa.string()), ('training_excluded', pa.bool_())])
    index = B.write_parquet(root / 'selected_diagnostic_geometry_ids.parquet', iter(indices), schema)
    mids = B.write_parquet(root / 'actual_seen_diagnostic_molecule_ids.parquet',
        (dict(molecule_id=mid, sample_role=C.ROLE) for mid in sorted(chosen)),
        pa.schema([('molecule_id', pa.string()), ('sample_role', pa.string())]))
    db.commit()
    source.close()
    C.need(I.identity(path) == before, 'CLOSED_D4_DATABASE_FRAME_UNCHANGED')
    actual_mids = db.execute('SELECT count(DISTINCT mid) FROM molecules').fetchone()[0]
    C.need(actual_mids == len(chosen), 'CPU_ACTUAL_DISTINCT_DIAGNOSTIC_MIDS')
    return db, geometry, binding, dict(closed_D4_geometry_origin_reference=binding,
        global_D5_diagnostic_MIDs=20000, frozen_D3_selected_TRAIN_MIDs=50000,
        actual_D3_seen_TRAIN_MIDs=None, actual_D3_seen_status='FROZEN_ROSTER_AWAITING_INDEPENDENT_D3_PAYLOAD_CLOSURE',
        actual_seen_D5_intersection_MIDs=actual_mids, global_D5_MIDs_outside_actual_seen_TRAIN=len(global_mids - train),
        selected_diagnostic_geometry_ids_reference=index, actual_seen_diagnostic_molecule_ids_reference=mids,
        selected_geometries=len(indices), selected_bases=sum(r['is_base'] for r in indices),
        selected_child_input_views=sum(not r['is_base'] for r in indices))
