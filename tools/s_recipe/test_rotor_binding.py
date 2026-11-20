"""New native pointer selection only; no source audit or numerical IO."""
import json
from pathlib import Path
import sqlite3

import pytest
import pyarrow as pa
import pyarrow.parquet as pq

from prepare_rotors import NativeGraphs, prepare_source_smiles, relocated_source_path


def test_only_explicit_native_directory_prefix_is_relocated():
    old = Path('/share/home/zixiao/dataset/lmdb_new')
    new = Path('/lfshome/zixiao/dataset/lmdb_new')
    assert relocated_source_path(old/'shard.lmdb', old, new) == new/'shard.lmdb'
    outside = Path('/share/home/zixiao/other/shard.lmdb')
    assert relocated_source_path(outside, old, new) == outside
    assert relocated_source_path(old/'shard.lmdb') == old/'shard.lmdb'
    with pytest.raises(ValueError, match='required together'):
        relocated_source_path(old/'shard.lmdb', old, None)


def fixture():
    source = NativeGraphs.__new__(NativeGraphs)
    source.identities = sqlite3.connect(':memory:')
    source.identities.execute('CREATE TABLE mid_records(domain INTEGER,mid TEXT,ordinal INTEGER)')
    source.identities.executemany('INSERT INTO mid_records VALUES(?,?,?)',
                                 [(0, 'mA', 12), (0, 'mA', 4), (0, 'mB', 8), (1, 'mA', 1)])
    source.pointers = [sqlite3.connect(':memory:')]
    source.pointers[0].execute('CREATE TABLE pointers(domain INTEGER,ordinal INTEGER,locator TEXT)')
    for ordinal in (12, 4, 8):
        source.pointers[0].execute('INSERT INTO pointers VALUES(?,?,?)',
                                  (0, ordinal, json.dumps(dict(source_path='original.lmdb', real_index=ordinal))))
    return source


def test_native_pointer_is_bound_by_mid_and_original_ordinal():
    source = fixture()
    try:
        result = source.locate(['mA', 'mB'])
        assert result == dict(mA=dict(source_path='original.lmdb', real_index=4),
                              mB=dict(source_path='original.lmdb', real_index=8))
        with pytest.raises(ValueError, match='No original native graph witness'):
            source.locate(['missing'])
    finally:
        source.identities.close()
        for database in source.pointers:
            database.close()


def test_conflicting_original_native_pointer_is_rejected():
    source = fixture()
    source.pointers[0].execute('INSERT INTO pointers VALUES(?,?,?)',
                              (0, 4, json.dumps(dict(source_path='other.lmdb', real_index=4))))
    try:
        with pytest.raises(ValueError, match='Conflicting closed native witnesses'):
            source.locate(['mA'])
    finally:
        source.identities.close()
        for database in source.pointers:
            database.close()


def test_source_smiles_binds_exact_pointer_and_mid_in_one_pass(tmp_path):
    record_index = tmp_path/'original.parquet'
    pq.write_table(pa.Table.from_pylist([
        dict(source_path='original.lmdb', real_index=12, molecule_id='mA', smiles='CCC'),
        dict(source_path='original.lmdb', real_index=4, molecule_id='mA', smiles='CCCC'),
        dict(source_path='original.lmdb', real_index=8, molecule_id='mB', smiles='CCO')]), record_index)
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps(dict(status='WP5_FORMAL_POPULATION_CLOSED',
                                      outputs=dict(record_index=str(record_index)))))
    train, val = tmp_path/'train.parquet', tmp_path/'val.parquet'
    pq.write_table(pa.table(dict(molecule_id=['mA'])), train)
    pq.write_table(pa.table(dict(molecule_id=['mB'])), val)
    source = fixture()
    database = sqlite3.connect(':memory:')
    database.execute('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT)')
    try:
        population = dict(train=str(train), validation=str(val))
        expected = prepare_source_smiles(source, database, population, manifest, lambda: None)
        assert database.execute('SELECT smiles FROM native_smiles WHERE real_index=4').fetchone()[0] == 'CCCC'
        assert database.execute('SELECT count(*) FROM native_smiles WHERE real_index=12').fetchone()[0] == 0
        assert prepare_source_smiles(source, database, population, manifest, lambda: None) == expected
    finally:
        database.close()
        source.identities.close()
        for pointer_db in source.pointers:
            pointer_db.close()
