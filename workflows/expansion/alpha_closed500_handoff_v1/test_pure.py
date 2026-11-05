"""Original function AST and tiny native selector/filter parity on synthetic data."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from .scientific_contract import verify


class AlphaPureStagesTests(unittest.TestCase):
    def test_every_pure_science_function_retains_original_ast(self):
        self.assertEqual(len(verify()['functions']), 9)

    def source(self, root):
        import pyarrow as pa
        import pyarrow.parquet as pq
        from ..pubchem_closed500_bulk_v2.test_bulk import source_fixture
        from ..pubchem_closed500_bulk_v2.project import project_fragment
        keys = [x * 14 + '-' + x * 10 + '-N' for x in 'ABCD']
        spec = source_fixture(root / '000_0.parquet', [(i+1, key, 'accepted') for i, key in enumerate(keys)])
        table = pq.read_table(spec['Parquet_reference']['path']); rows = table.to_pylist()
        for row, composition in zip(rows, ([[6, 1]], [[6, 2]], [[8, 1]], [])):
            row['non_h_composition'] = json.dumps(composition, separators=(',', ':'))
            row['elements'] = [p[0] for p in composition]; row['heavy_atoms'] = sum(p[1] for p in composition)
            row['element_combination'] = ','.join(str(p[0]) for p in composition)
            row['generic_murcko'] = ''; row['wp5_key'] = row['full_key'][:14] + ':' + row['full_key'][-1]
        pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), root / '000_0.parquet')
        from ..alpha_runtime_v1.common import reference
        spec['Parquet_reference'] = reference(root / '000_0.parquet')
        projected = project_fragment(spec, root / 'projected')
        return Path(projected['accepted_parquet']['path']), rows

    def test_original_v3_full_WP5_composition_and_bound_hits_equal_typed_SQL(self):
        import pyarrow.parquet as pq
        from .empty_domain import filter_core, contamination
        from . import science_v3 as C
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source, rows = self.source(root)
            index = root / 'index.sqlite'; db = sqlite3.connect(index)
            db.executescript('CREATE TABLE excluded(kind TEXT,key TEXT,dataset TEXT,PRIMARY KEY(kind,key,dataset));CREATE TABLE constraints(rule_id TEXT PRIMARY KEY,dataset TEXT,binding TEXT);CREATE TABLE constraint_atoms(rule_id TEXT,z INTEGER,n INTEGER,PRIMARY KEY(rule_id,z));')
            db.execute('INSERT INTO excluded VALUES(?,?,?)', ('full', rows[0]['full_key'], 'qm9'))
            db.execute('INSERT INTO excluded VALUES(?,?,?)', ('wp5', rows[0]['wp5_key'], 'som_cyp'))
            db.execute('INSERT INTO excluded VALUES(?,?,?)', ('composition', rows[0]['non_h_composition'], 'qm7'))
            db.execute('INSERT INTO constraints VALUES(?,?,?)', ('C2fixture', 'coconut', '{"fixture":true}'))
            db.execute('INSERT INTO constraint_atoms VALUES(?,?,?)', ('C2fixture', 6, 2)); db.commit()
            for r in rows[:3]:self.assertEqual(contamination(r, db), C.contamination(r, db))
            expected = {r['cid_source_ascii']: contamination(r, db) for r in rows}; db.close()
            out = root / 'filtered'; out.mkdir()
            selected, evidence, counts = filter_core(source, index, out, 1, 64 << 20, lambda: None)
            observed = {str(i): [] for i in (1, 2, 3, 4)}
            for r in pq.read_table(evidence['path']).to_pylist():observed[str(r['cid'])].append((r['kind'], r['dataset']))
            self.assertEqual({k: sorted(v) for k, v in observed.items()}, expected)
            self.assertEqual(sorted(pq.read_table(selected['path'])['cid'].to_pylist()), [3, 4])
            self.assertEqual((counts['input_unique_molecules'], counts['excluded_molecules'], counts['eligible_molecules']), (4, 2, 2))

    def test_fixed_predecon_selection_and_query_ordinal_order_match_original_hash(self):
        import pyarrow.parquet as pq
        from .baseline_core import baseline_core, DOMAIN, SEED
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source, rows = self.source(root); out = root / 'sample'; out.mkdir()
            membership, features, projection, total = baseline_core(source, out, 1, 64 << 20, lambda: None, sample_size=2)
            def key(r):return hashlib.sha256(json.dumps([DOMAIN, SEED, r['full_key']], separators=(',', ':'), ensure_ascii=True).encode()).hexdigest(), r['full_key'], int(r['cid_source_ascii'])
            expected = sorted(rows, key=key)[:2]; members = pq.read_table(membership['path']).to_pylist()
            queries = [json.loads(line) for line in Path(projection['path']).read_text().splitlines()]
            self.assertEqual(total, 4); self.assertEqual([r['sample_ordinal'] for r in members], [0, 1])
            self.assertEqual([r['full_key'] for r in members], [r['full_key'] for r in expected])
            self.assertEqual([r['full_key'] for r in queries], [r['full_key'] for r in members])
            self.assertEqual(pq.ParquetFile(features['path']).metadata.num_rows, 2)


if __name__ == '__main__':unittest.main()
