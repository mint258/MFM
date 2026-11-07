"""Native tiny source fixtures for the new scheduler/runtime callback boundary."""
from pathlib import Path
import tempfile
import unittest
from ..alpha_runtime_v1.common import reference, write
from ..pubchem_closed500_bulk_v2.test_bulk import source_fixture
from .run import project_fragments, merge_original, projection_manifest


class CheckOnly:
    def __init__(self):self.calls = 0
    def check(self):self.calls += 1


class AlphaTypedHandoffTests(unittest.TestCase):
    def test_durable_typed_projection_and_minCID_reuse_original_functions(self):
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a = source_fixture(root / '000_0.parquet', [(10, 'AAAAAAAAAAAAAA-AAAAAAAAAA-N', 'accepted'), (11, 'reject', 'chemReject'), (12, 'unknown', 'technicalUnresolved')])
            b = source_fixture(root / '001_0.parquet', [(5, 'AAAAAAAAAAAAAA-AAAAAAAAAA-N', 'accepted'), (7, 'BBBBBBBBBBBBBB-BBBBBBBBBB-N', 'accepted')], first=4)
            plan = {'output_directory': str(root / 'new'), 'fragments': [a, b], 'workers': 2, 'batch_rows': 2, 'duckdb_memory_bytes': 256 << 20}
            guard = CheckOnly()
            values = project_fragments(plan, {'000_0', '001_0'}, guard)
            reused = project_fragments(plan, {'000_0', '001_0'}, guard)
            self.assertEqual(sorted(r['source_sha256'] for r in values), sorted(r['source_sha256'] for r in reused))
            self.assertEqual(len(list((root / 'new/fragments').glob('*/attempt_*'))), 2)
            path = root / 'new/fixture_projection.json'
            write(path, {'schema': 'PUBCHEM_ALL_CLOSED_PROJECTIONS_V2', 'status': 'COMPLETE_ACCEPTED_PROJECTIONS_NO_POOL_RELEASE', 'source_rows': 5, 'counts': {'accepted': 3, 'chemReject': 1, 'technicalUnresolved': 1}, 'accepted_parquets': [r['accepted_parquet'] for r in values]})
            result = merge_original(path, root / 'new/mincid', plan, guard)
            self.assertEqual((result['unique_full_keys'], result['aliases_rows']), (2, 3))
            self.assertEqual(sorted(pq.read_table(result['candidates']['path'])['cid'].to_pylist()), [5, 7])
            self.assertEqual(sorted(pq.read_table(result['aliases']['path'])['cid'].to_pylist()), [5, 7, 10])
            self.assertGreater(guard.calls, 0)

    def test_partial_actual_scope_cannot_claim_full502_manifest(self):
        with self.assertRaisesRegex(ValueError, 'All actual502'):
            projection_manifest({'fragments': []}, [])

    def test_original_merge_bindings_are_restored_after_failure(self):
        from ..pubchem_closed500_bulk_v2 import merge as original
        before = original.resource_check, original.verify
        with tempfile.TemporaryDirectory() as temp:
            class Stop:
                def check(self):raise RuntimeError('synthetic_actual_resource_stop')
            root = Path(temp); source = root / 'manifest.json'
            write(source, {'schema': 'PUBCHEM_ALL_CLOSED_PROJECTIONS_V2', 'status': 'COMPLETE_ACCEPTED_PROJECTIONS_NO_POOL_RELEASE', 'source_rows': 0, 'counts': {'accepted': 0}, 'accepted_parquets': []})
            with self.assertRaisesRegex(RuntimeError, 'synthetic_actual_resource_stop'):
                merge_original(source, root / 'out', {'output_directory': str(root), 'workers': 1, 'duckdb_memory_bytes': 64 << 20}, Stop())
        self.assertIs(original.resource_check, before[0]); self.assertIs(original.verify, before[1])


if __name__ == '__main__':unittest.main()
