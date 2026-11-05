"""Native tiny closed RAW→minCID→typed-filter parity, not production work."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest


class TypedHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pyarrow as pa
        from ..pubchem_raw_reconstruction_v1 import kernel
        kernel.STOP = threading.Event()
        cls.rows, cls.counts = [], {'accepted': 0, 'chemReject': 0, 'technicalUnresolved': 0}
        for ordinal, (cid, smiles) in enumerate(((1, 'C'), (2, 'CC'), (3, 'CCC'), (4, 'CCCC'), (5, 'O'), (6, 'N'), (7, 'CCO'), (99, 'C'), (100, '[Na+]'), (101, 'not_a_smiles')), 1):
            original = {'cid_source_ascii': str(cid), 'ordinal': ordinal, 'source_smiles': smiles, 'source_smiles_sha256': hashlib.sha256(smiles.encode()).hexdigest(), 'source_part': {'fixture': True}}
            result = kernel.chemical_task(original)
            cls.counts[result['category']] += 1
            if result['category'] == 'accepted':
                row = kernel.parquet_row(result, 'synthetic_handoff_fixture')
                row.update(cid=cid, source_fragment_id='synthetic_fixture')
                cls.rows.append(row)
        cls.schema = kernel.output_schema().append(pa.field('cid', pa.int64())).append(pa.field('source_fragment_id', pa.string()))

    def source(self, root):
        import pyarrow as pa
        import pyarrow.parquet as pq
        from .runtime import reference, write_new
        path = root / 'accepted.parquet'
        pq.write_table(pa.Table.from_pylist(self.rows, schema=self.schema), path)
        manifest = root / 'projection_manifest.json'
        write_new(manifest, {'schema': 'PUBCHEM_ALL_CLOSED_PROJECTIONS_V2', 'status': 'COMPLETE_ACCEPTED_PROJECTIONS_NO_POOL_RELEASE', 'source_rows': 10, 'counts': self.counts, 'accepted_parquets': [reference(path)]})
        return manifest

    def exclusion(self, path):
        from ..coconut735_recovery_v1 import consumer as C
        from ..common import wp5_key
        db = sqlite3.connect(path); C.install_tables(db)
        by_cid = {r['cid']: r for r in self.rows}
        for kind, key, dataset in [('full', by_cid[1]['full_key'], 'qm9'), ('wp5', wp5_key(by_cid[6]['full_key']), 'som_cyp'), ('composition', by_cid[5]['non_h_composition'], 'qm7')]:
            db.execute('INSERT INTO excluded VALUES(?,?,?)', (kind, key, dataset))
        db.execute('INSERT INTO constraints VALUES(?,?,?)', ('fixture_C3_lower_bound', 'coconut', '{"synthetic":true}'))
        db.execute('INSERT INTO constraint_atoms VALUES(?,?,?)', ('fixture_C3_lower_bound', 6, 3))
        db.commit(); db.close()

    def test_closed_raw_merge_filter_preserves_typed_payload_and_original_v3_parity(self):
        import pyarrow.parquet as pq
        from .merge import merge_core
        from .filter import filter_core
        from ..coconut735_recovery_v1 import consumer as C
        from .. import decontamination as legacy
        self.assertIs(C.contamination_exact, legacy.contamination)
        self.assertEqual(self.counts, {'accepted': 8, 'chemReject': 1, 'technicalUnresolved': 1})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); manifest = self.source(root)
            result = merge_core(manifest, root / 'mincid', 1, 64 << 20, {'output_directory': str(root)}, lambda: None)
            self.assertEqual((result['unique_full_keys'], result['aliases_rows']), (7, 8))
            winners = pq.read_table(result['candidates']['path']).to_pylist()
            originals = {r['cid']: r for r in self.rows}
            self.assertEqual({r['cid'] for r in winners}, set(range(1, 8)))
            for winner in winners:
                self.assertEqual(winner, originals[winner['cid']])
            index = root / 'excluded.sqlite'; self.exclusion(index)
            read = sqlite3.connect(index)
            expected = {r['cid']: C.contamination(r, read) for r in winners}
            read.close()
            out = root / 'filtered'; out.mkdir()
            accepted, evidence, counts = filter_core(Path(result['candidates']['path']), index, out, 1, 64 << 20, lambda: None)
            selected = pq.read_table(accepted['path']).to_pylist()
            hits = pq.read_table(evidence['path']).to_pylist()
            observed = {r['cid']: [] for r in winners}
            for hit in hits:
                observed[hit['cid']].append((hit['kind'], hit['dataset']))
            self.assertEqual({cid: sorted(v) for cid, v in observed.items()}, expected)
            self.assertEqual({r['cid'] for r in selected}, {2, 7})
            self.assertEqual(counts['input_unique_molecules'], 7)
            self.assertEqual(counts['excluded_molecules'], 5)
            for row in selected:
                self.assertEqual(row, originals[row['cid']])

    def test_baseline_is_stable_unique_predecon_sample_and_query_contract(self):
        import pyarrow.parquet as pq
        from .merge import merge_core
        from .baseline import baseline_core, DOMAIN, SEED
        from .projection import QUERY_FIELDS
        from ..common import stable_hash
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); result = merge_core(self.source(root), root / 'pool', 1, 64 << 20, {'output_directory': str(root)}, lambda: None)
            out = root / 'baseline'; out.mkdir()
            membership, features, projection, total = baseline_core(Path(result['candidates']['path']), out, 1, 64 << 20, lambda: None, sample_size=3)
            pool = pq.read_table(result['candidates']['path']).to_pylist()
            expected = sorted(pool, key=lambda r: (stable_hash(DOMAIN, SEED, r['full_key']), r['full_key'], r['cid']))[:3]
            members = pq.read_table(membership['path']).to_pylist()
            self.assertEqual([r['cid'] for r in members], [r['cid'] for r in expected])
            self.assertEqual([r['sample_ordinal'] for r in members], [0, 1, 2])
            self.assertEqual(total, 7)
            records = [json.loads(line) for line in Path(projection['path']).read_text().splitlines()]
            self.assertEqual({r['full_key'] for r in records}, {r['full_key'] for r in members})
            self.assertEqual([r['full_key'] for r in records], [r['full_key'] for r in members])
            self.assertTrue(all(set(row) == set(QUERY_FIELDS) for row in records))
            self.assertEqual(pq.ParquetFile(features['path']).metadata.num_rows, 3)

    def test_vector_validation_rejects_inconsistent_or_coerced_candidate_domain(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        from .filter import filter_core
        for mutation in ({'elements': [6, 8]}, {'non_h_composition': '[[6,1.0]]'}):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); row = dict(self.rows[0], **mutation)
                path = root / 'bad.parquet'; pq.write_table(pa.Table.from_pylist([row], schema=self.schema), path)
                index = root / 'excluded.sqlite'; self.exclusion(index)
                out = root / 'out'; out.mkdir()
                with self.assertRaisesRegex(ValueError, 'canonical X02'):
                    filter_core(path, index, out, 1, 64 << 20, lambda: None)

    def test_pending_all11_header_cannot_release_pool(self):
        from ..coconut735_recovery_v1 import consumer as C
        from ..decontamination import REQUIRED
        with self.assertRaises(Exception):
            C.index_header({'schema': C.INDEX_SCHEMA, 'status': 'PENDING', 'sources': {s: {} for s in REQUIRED}, 'all_physical_source_rows_covered': False, 'original_graph_unknowns_retained': True, 'constraint_source_datasets': ['coconut', 'moleculenet']})


if __name__ == '__main__':
    unittest.main()
