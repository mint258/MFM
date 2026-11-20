"""Once-only source-order strict rotor index, on CPU, without QM labels."""
import argparse
from collections import OrderedDict
from contextlib import ExitStack
from dataclasses import asdict
import importlib.util
import importlib
import json
from pathlib import Path
import pickle
import runpy
import sqlite3
import sys
import time

import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import rdBase

from phychem_mfm.phase1.v2_disk import save_metadata_json
from noise import align_source_graph, precompute_rotors, source_ordered_molecule
from s_data import GeometryDataset


PROJECT = Path('/share/home/zixiao/descriptor_analysis')


def relocated_source_path(source_path, relocation_from=None, relocation_to=None):
    """Apply only the explicitly supplied, verified native directory mapping."""
    if (relocation_from is None) != (relocation_to is None):
        raise ValueError('Both native relocation prefixes are required together')
    path = Path(source_path)
    if not path.is_absolute():
        path = PROJECT/path
    if relocation_from is not None:
        if not relocation_from.is_absolute() or not relocation_to.is_absolute():
            raise ValueError('Native relocation prefixes must be absolute')
        try:
            suffix = path.relative_to(relocation_from)
        except ValueError:
            pass
        else:
            path = relocation_to/suffix
    return path


class NativeGraphs:
    """Read closed MID/native pointers and original LMDB graphs, without hashes.

    The existing identity index is the authority for MID ownership. Only its
    pointer tables are consumed; physical labels and their bodies are unused.
    Connections stay open across batches so a million MIDs do not cause a
    million metadata database opens. Per-batch memory is bounded.
    """
    def __init__(self, manifest, source_repository, graph_script, *,
                 relocation_from=None, relocation_to=None, load_native_graph=True):
        # Validate paired arguments before opening any source metadata.
        relocated_source_path(PROJECT, relocation_from, relocation_to)
        self.relocation_from, self.relocation_to = relocation_from, relocation_to
        sys.path.insert(0, str(source_repository))
        try:
            module = importlib.import_module(
                'workflows.data_v1_final.export.full_physical_index_v3.read_index')
        finally:
            sys.path.pop(0)
        self.stack = ExitStack()
        self.handles = OrderedDict()
        try:
            index = json.loads(Path(manifest).read_text())
            if index['schema'] != 'D6_FULL_ORIGINAL_PHYSICAL_LOCATOR_INDEX_V1':
                raise ValueError('Expected the closed original physical locator index')
            self.identities = self.stack.enter_context(module.closed_db(index['identity_database']))
            storages = [index['QC_locations'], *[p['storage'] for p in index['partitions']]]
            # Skip partitions without native witnesses; inspect only one index
            # row, never scan or copy the physical tables.
            self.pointers = []
            for storage in storages:
                database = self.stack.enter_context(module.closed_db(storage))
                if database.execute('SELECT 1 FROM pointers WHERE domain=0 LIMIT 1').fetchone():
                    self.pointers.append(database)
            if not self.pointers:
                raise ValueError('Closed index contains no domain0 native pointers')
            if load_native_graph:
                sys.path.insert(0, str(graph_script.parent))
                previous = sys.modules.pop('prepare', None)
                try:
                    self.graph = runpy.run_path(str(graph_script))['graph']
                finally:
                    sys.path.pop(0)
                    sys.modules.pop('prepare', None)
                    if previous is not None:
                        sys.modules['prepare'] = previous
        except BaseException:
            self.close()
            raise

    def locate(self, mids):
        """Choose the first actual native conformer witness for each MID."""
        owners = {}
        # SQLite installations can have a 999 parameter limit.
        for start in range(0, len(mids), 256):
            part = mids[start:start+256]
            marks = ','.join('?' for _ in part)
            for mid, ordinal in self.identities.execute(
                    'SELECT mid,ordinal FROM mid_records WHERE domain=0 AND mid IN ('+marks+')', part):
                owners[int(ordinal)] = mid
        result = {}
        ordinals = sorted(owners)
        for start in range(0, len(ordinals), 256):
            part = ordinals[start:start+256]
            marks = ','.join('?' for _ in part)
            for database in self.pointers:
                for ordinal, locator in database.execute(
                        'SELECT ordinal,locator FROM pointers WHERE domain=0 AND ordinal IN ('+marks+')', part):
                    pointer = json.loads(locator)
                    mid = owners[int(ordinal)]
                    current = result.get(mid)
                    if current is None or int(ordinal) < current[0]:
                        if not isinstance(pointer.get('source_path'), str) or type(pointer.get('real_index')) is not int:
                            raise ValueError('Closed pointer lacks an original native path/key for '+mid)
                        result[mid] = (int(ordinal), pointer)
                    elif int(ordinal) == current[0] and pointer != current[1]:
                        raise ValueError('Conflicting closed native witnesses for '+mid)
        missing = set(mids) - result.keys()
        if missing:
            raise ValueError('No original native graph witness for '+min(missing))
        return {mid: value[1] for mid, value in result.items()}

    def read(self, pointer):
        import lmdb
        path = relocated_source_path(pointer['source_path'], self.relocation_from, self.relocation_to)
        key = str(path)
        if key not in self.handles:
            if len(self.handles) >= 4:
                self.handles.popitem(last=False)[1].close()
            self.handles[key] = lmdb.open(key, subdir=False, readonly=True, lock=False,
                                         create=False, readahead=False, max_readers=1024)
        environment = self.handles.pop(key)
        self.handles[key] = environment
        with environment.begin() as transaction:
            payload = transaction.get(f"{pointer['real_index']:09d}".encode())
        if payload is None:
            raise KeyError(('Missing native source graph', key, pointer['real_index']))
        return self.graph(pickle.loads(payload))[0]

    def close(self):
        while self.handles:
            self.handles.popitem(last=False)[1].close()
        self.stack.close()


def prepare_source_smiles(native, database, population_data, manifest_path, capacity):
    """Produce exact original-pointer/SMILES bindings in one metadata pass.

    The source is the original WP5 producer's published record-index output,
    not a new structure reconstruction or an independent old-data audit.
    No native LMDB, physical labels, content hashes or temporary spool is used.
    """
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('status') != 'WP5_FORMAL_POPULATION_CLOSED':
        raise ValueError('Original source population must be closed')
    record_index = Path(manifest['outputs']['record_index'])
    if not record_index.is_absolute():
        raise ValueError('Published source record index must be absolute')
    binding = dict(manifest=str(manifest_path), record_index=str(record_index),
                   key=['source_path', 'real_index'], graph_column='smiles')
    database.execute('CREATE TABLE IF NOT EXISTS native_smiles('
                     'source_path TEXT,real_index INTEGER,mid TEXT NOT NULL,smiles TEXT,'
                     'PRIMARY KEY(source_path,real_index)) WITHOUT ROWID')
    saved = database.execute('SELECT value FROM metadata WHERE key=?', ('native_smiles_complete',)).fetchone()
    if saved:
        if json.loads(saved[0]) != binding:
            raise ValueError('Source SMILES binding changed')
        return binding
    for key in ('train', 'validation'):
        rows = pq.read_table(population_data[key], columns=['molecule_id']).column(0).to_pylist()
        for start in range(0, len(rows), 1000):
            capacity()
            pointers = native.locate(rows[start:start+1000])
            database.executemany('INSERT INTO native_smiles VALUES(?,?,?,NULL) '
                'ON CONFLICT(source_path,real_index) DO UPDATE SET mid='
                'CASE WHEN mid=excluded.mid THEN mid ELSE NULL END',
                [(p['source_path'], p['real_index'], mid) for mid, p in pointers.items()])
            database.commit()
            if start % 100000 == 0:
                print(json.dumps(dict(native_pointer_binding=key, rows=min(start+1000, len(rows)))), flush=True)
    # This bounded metadata lookup is the only in-memory original-pointer map.
    # It contains one selected record per target molecule, not all conformers.
    wanted = {(p, int(i)): (mid, smiles) for p, i, mid, smiles in
              database.execute('SELECT source_path,real_index,mid,smiles FROM native_smiles')}
    source = pq.ParquetFile(record_index, pre_buffer=False)
    columns = ['source_path', 'real_index', 'molecule_id', 'smiles']
    if not set(columns) <= set(source.schema_arrow.names):
        source.close()
        raise ValueError('Published original record index lacks native SMILES columns')
    try:
        for batch_number, batch in enumerate(source.iter_batches(batch_size=8192, columns=columns, use_threads=False)):
            if batch_number % 16 == 0:
                capacity()
            updates = []
            for row in batch.to_pylist():
                key = row['source_path'], int(row['real_index'])
                selected = wanted.get(key)
                if selected is None:
                    continue
                mid, previous = selected
                smiles = row['smiles']
                if mid != row['molecule_id'] or not isinstance(smiles, str) or not smiles:
                    raise ValueError('Original pointer/MID/SMILES binding invalid for '+mid)
                if previous is not None and previous != smiles:
                    raise ValueError('Conflicting original pointer SMILES for '+mid)
                wanted[key] = mid, smiles
                updates.append((smiles, *key))
            if updates:
                database.executemany('UPDATE native_smiles SET smiles=? WHERE source_path=? AND real_index=?', updates)
                database.commit()
            if batch_number % 128 == 0:
                print(json.dumps(dict(source_smiles_batches=batch_number+1)), flush=True)
    finally:
        source.close()
    missing = database.execute('SELECT mid FROM native_smiles WHERE smiles IS NULL LIMIT 1').fetchone()
    if missing:
        raise ValueError('Original published source SMILES missing for '+missing[0])
    capacity()
    database.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',
                     ('native_smiles_complete', json.dumps(binding, sort_keys=True)))
    database.commit()
    return binding


def prepare(root, population, source_index, source_repository, output, summary,
            relocation_from=None, relocation_to=None, source_population_manifest=None):
    relocated_source_path(PROJECT, relocation_from, relocation_to)
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    population_data = json.loads(population.read_text())
    repo = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('disk', repo/'tools/model_v3/v2_diagnosis_disk.py')
    disk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(disk)
    total = population_data['TRAIN_molecules'] + population_data['VAL_molecules']
    # Source graphs are not copied. Estimate SQLite plans+index+rollback, then
    # update the remaining estimate from actual producer growth, not a cap.
    peak = max(2*1024**3, total*16384)
    done = 0
    growth_baseline_bytes = 0
    growth_baseline_done = 0

    def capacity(minimum_growth=0):
        nonlocal peak
        allocated = output.stat().st_blocks*512 if output.exists() else 0
        if done > growth_baseline_done:
            produced = done-growth_baseline_done
            variable = max(0, allocated-growth_baseline_bytes)
            peak = max(peak, allocated+int(variable*(total-done)/produced*1.25))
        remaining = max(32*1024**2, peak-allocated, minimum_growth)
        while True:
            try:
                from runtime import capacity as s_capacity
                s_capacity()
                disk.m.require_capacity(disk.m.filesystem_status('/'), 0, 0)
                disk.m.require_capacity(disk.m.filesystem_status(output.parent), remaining, 100)
                disk.m.quota_headroom(disk.CONTROL/'share_quota_available_v3.json', '/share',
                                      remaining, disk.remaining_nfs_other()+2*1024**3)
                return
            except OSError as error:
                print('ROTOR_DISK_WAIT '+str(error), flush=True)
                time.sleep(5)

    capacity()
    output.parent.mkdir(parents=True, exist_ok=True)
    existed = output.exists()
    database = sqlite3.connect(output)
    database.execute('PRAGMA temp_store=MEMORY')
    binding = dict(root=str(root), population=str(population), source_index=str(source_index),
                   source_repository=str(source_repository), native_graph_builder='workflows/sprime_s/scripts/sprime_v6.py:graph',
                   strict_rule='RDKit Strict3.1.0',
                   rdkit_version=rdBase.rdkitVersion)
    if relocation_from is not None:
        binding['native_source_relocation'] = dict(source_prefix=str(relocation_from),
                                                  actual_prefix=str(relocation_to))
    if source_population_manifest is not None:
        if relocation_from is not None:
            raise ValueError('SMILES metadata mode does not use native LMDB relocation')
        binding['native_graph_builder'] = 'original pointer-bound source SMILES + complete element/bond isomorphism'
        binding['source_population_manifest'] = str(source_population_manifest)
    if not existed:
        database.executescript('CREATE TABLE rotors(split TEXT,molecule_index INTEGER,mid TEXT,plan TEXT,'
                               'PRIMARY KEY(split,molecule_index));'
                               'CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);'
                               'CREATE TABLE progress(split TEXT PRIMARY KEY,cursor INTEGER,counts TEXT);')
        database.execute('INSERT INTO metadata VALUES(?,?)', ('binding', json.dumps(binding, sort_keys=True)))
        database.commit()
    else:
        previous = json.loads(database.execute('SELECT value FROM metadata WHERE key=?', ('binding',)).fetchone()[0])
        if previous != binding:
            transport_keys = {'native_source_relocation', 'native_graph_builder', 'source_population_manifest'}
            scientific = {k: v for k, v in binding.items() if k not in transport_keys}
            old_scientific = {k: v for k, v in previous.items() if k not in transport_keys}
            # A failed first source open has produced no scientific plans.
            # Record its verified path relocation without deleting its DB.
            if (scientific == old_scientific
                    and database.execute('SELECT 1 FROM rotors LIMIT 1').fetchone() is None
                    and database.execute('SELECT 1 FROM progress WHERE cursor>0 LIMIT 1').fetchone() is None):
                database.execute('UPDATE metadata SET value=? WHERE key=?',
                                 (json.dumps(binding, sort_keys=True), 'binding'))
                database.commit()
            else:
                database.close()
                raise ValueError('Existing rotor producer is bound to different inputs')
    done = sum(row[0] for row in database.execute('SELECT cursor FROM progress'))
    counts = {}
    native = None
    try:
        native = NativeGraphs(source_index, source_repository, repo/'workflows/sprime_s/scripts/sprime_v6.py',
                              relocation_from=relocation_from, relocation_to=relocation_to,
                              load_native_graph=source_population_manifest is None)
        source_smiles_binding = (prepare_source_smiles(native, database, population_data,
                                 source_population_manifest, capacity)
                                 if source_population_manifest is not None else None)
        # The one-time pointer/SMILES table is fixed overhead. Do not multiply
        # its size by the remaining molecule count when forecasting plans.
        growth_baseline_bytes = output.stat().st_blocks*512
        growth_baseline_done = done
        for validation in (False, True):
            data = GeometryDataset(root, population, source='PM7', validation=validation)
            split = 'FULL' if validation else 'TRAIN'
            saved = database.execute('SELECT cursor,counts FROM progress WHERE split=?', (split,)).fetchone()
            cursor = saved[0] if saved else 0
            strata = (json.loads(saved[1]) if saved else
                      dict(zero=0, one_to_three=0, four_to_seven=0, eight_or_more=0))
            def commit(cursor):
                database.execute('INSERT OR REPLACE INTO progress VALUES(?,?,?)',
                                 (split, cursor, json.dumps(strata, sort_keys=True)))
                database.commit()
            try:
                pointers = {}
                for row_cursor in range(cursor, len(data.rows)):
                    row = data.rows[row_cursor]
                    if (row_cursor-cursor) % 1000 == 0:
                        pointers = native.locate([r['molecule_id'] for r in data.rows[row_cursor:row_cursor+1000]])
                    if done % 1000 == 0:
                        capacity()
                    mid, index = row['molecule_id'], int(row['molecule_index'])
                    topology = data._record('M', index)
                    if source_population_manifest is not None:
                        pointer = pointers[mid]
                        bound = database.execute('SELECT mid,smiles FROM native_smiles '
                            'WHERE source_path=? AND real_index=?',
                            (pointer['source_path'], pointer['real_index'])).fetchone()
                        if bound is None or bound[0] != mid:
                            raise ValueError('Missing produced original source SMILES binding for '+mid)
                        molecule = source_ordered_molecule(topology[1], topology[2], topology[3], bound[1])
                    else:
                        molecule = align_source_graph(topology[1], topology[2], topology[3], native.read(pointers[mid]))
                    rotors = precompute_rotors(molecule)
                    n = len(rotors)
                    stratum = ('zero' if n == 0 else 'one_to_three' if n <= 3 else
                               'four_to_seven' if n <= 7 else 'eight_or_more')
                    strata[stratum] += 1
                    plan = json.dumps([asdict(r) for r in rotors], separators=(',', ':'))
                    if len(plan) > 4*1024**2:
                        capacity(2*len(plan))
                    database.execute('INSERT INTO rotors VALUES(?,?,?,?)', (split, index, mid, plan))
                    done += 1
                    if done % 1000 == 0:
                        commit(row_cursor+1)
                        print(json.dumps(dict(precomputed=done, total=total, forecast_bytes=peak)), flush=True)
                commit(len(data.rows))
            finally:
                data.close()
            counts[split] = strata
        capacity()
        database.commit()
    finally:
        database.close()
        if native is not None:
            native.close()
    save_metadata_json(dict(schema='S_RECIPE_SOURCE_ROTORS_V1', population=str(population),
                            source_index=str(source_index), native_graph_builder=binding['native_graph_builder'],
                            native_source_relocation=binding.get('native_source_relocation'),
                            source_smiles_binding=source_smiles_binding,
                            rdkit_version=rdBase.rdkitVersion, strict_rule='RDKit Strict3.1.0',
                            source_atom_order='complete element/bond isomorphism with source charges retained',
                            index=str(output), counts=counts,
                            zero_rotor_TRAIN_fraction=counts['TRAIN']['zero']/population_data['TRAIN_molecules'],
                            actual_allocated_bytes=output.stat().st_blocks*512,
                            physical_labels_used=False), summary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('root', 'population', 'source-index', 'output', 'summary'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--source-repository', type=Path,
                        default=PROJECT/'runs/data_v1_20261025/repository')
    parser.add_argument('--relocation-from', type=Path)
    parser.add_argument('--relocation-to', type=Path)
    parser.add_argument('--source-population-manifest', type=Path)
    args = parser.parse_args()
    prepare(args.root, args.population, args.source_index, args.source_repository, args.output, args.summary,
            args.relocation_from, args.relocation_to, args.source_population_manifest)
