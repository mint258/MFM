"""Real columnar merge tests: duplicates, all states, preserved payloads, and resume."""
from pathlib import Path
import tempfile
import unittest

from .common import load, reference, write_new
from .merge import materialize
from .project import project_fragment
from .schema import original_schema


def source_fixture(path, values, first=1):
    import pyarrow as pa
    import pyarrow.parquet as pq
    schema = original_schema()
    rows = []
    for i, (cid, key, category) in enumerate(values, first):
        row = {field.name: None for field in schema}
        row.update(sample_group='full_shard', ordinal=i, cid_source_ascii=str(cid), source_smiles='C', source_smiles_sha256='0' * 64, source_part_reference_json='{"raw":"exact"}', category=category, technical_codes=['FIXTURE_TECHNICAL'] if category == 'technicalUnresolved' else [], legacy_reasons=['X03', 'X05'] if category == 'chemReject' else [], full_key=key if category == 'accepted' else None, wp5_key=key[:14] + '-N' if category == 'accepted' else None, full_dispatcher_result_json='{"cid":%d,"logp":-0.0,"escaped":"\\u03b1"}' % cid if category == 'accepted' else None, molecular_weight_Da=16.04246, tpsa_A2=-0.0, logp=0.12345678901234567, elements=[6], generic_ring_systems=[], heavy_atoms=1, ecfp4_2048_hex='0' * 512)
        rows.append(row)
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path, compression='zstd', row_group_size=2)
    counts = {name: sum(row['category'] == name for row in rows) for name in ('accepted', 'chemReject', 'technicalUnresolved')}
    return {'fragment_id': path.stem, 'descriptor_index': 0, 'first_ordinal': first, 'last_ordinal': first + len(rows) - 1, 'rows': len(rows), 'counts': counts, 'Parquet_reference': reference(path), 'journal_reference': {'path': 'immutable-original-unused-journal', 'bytes': 1, 'sha256': '1' * 64}, 'accepted_metadata_reference': {'path': 'closed-original-source-receipt', 'bytes': 1, 'sha256': '2' * 64}, 'actual_parent_job_id': 'fixture'}


class BulkProjectionTests(unittest.TestCase):
    def test_exact_minimum_cid_aliases_and_preserved_double_payload(self):
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory(prefix='pubchem_bulk_fixture_') as directory:
            root = Path(directory)
            a = source_fixture(root / '000_0.parquet', [(10, 'AAAAAAAAAAAAAA-AAAAAAAAAA-N', 'accepted'), (11, 'ignored', 'chemReject'), (12, 'unknown', 'technicalUnresolved')])
            b = source_fixture(root / '001_0.parquet', [(5, 'AAAAAAAAAAAAAA-AAAAAAAAAA-N', 'accepted'), (7, 'BBBBBBBBBBBBBB-BBBBBBBBBB-N', 'accepted')], first=4)
            first = project_fragment(a, root / 'projected', batch_rows=2)
            second = project_fragment(b, root / 'projected', batch_rows=1)
            self.assertEqual(first['chemical_first_rule_counts'], {'X03': 1})
            self.assertEqual(first['chemical_overlap_rule_counts'], {'X03': 1, 'X05': 1})
            self.assertEqual(first['technical_reason_counts'], {'FIXTURE_TECHNICAL': 1})
            self.assertEqual(project_fragment(a, root / 'projected', batch_rows=1), first)
            self.assertEqual(len(list((root / 'projected' / '000_0').glob('attempt_*'))), 1)
            manifest = root / 'projection_manifest.json'
            write_new(manifest, {'schema': 'PUBCHEM_ALL_CLOSED_PROJECTIONS_V2', 'status': 'COMPLETE_ACCEPTED_PROJECTIONS_NO_POOL_RELEASE', 'source_rows': 5, 'counts': {'accepted': 3, 'chemReject': 1, 'technicalUnresolved': 1}, 'accepted_parquets': [first['accepted_parquet'], second['accepted_parquet']]})
            closed = materialize(manifest, root / 'merged', workers=2, memory_bytes=256 << 20)
            self.assertEqual(closed['aliases_rows'], 3)
            self.assertEqual(closed['unique_full_keys'], 2)
            self.assertEqual(closed['pubchem_duplicate_full_key'], 1)
            table = pq.read_table(closed['candidates']['path'])
            self.assertEqual(sorted(table['cid'].to_pylist()), [5, 7])
            self.assertEqual(sorted(pq.read_table(closed['aliases']['path'])['cid'].to_pylist()), [5, 7, 10])
            expected = pq.read_table(second['accepted_parquet']['path']).sort_by('cid')
            observed = table.sort_by('cid')
            self.assertEqual(expected.schema.names, observed.schema.names)
            self.assertEqual(expected.to_pylist(), observed.to_pylist())
            for name in ('logp', 'tpsa_A2', 'molecular_weight_Da'):
                # Covers signed zero and the complete binary64 mantissa, not just
                # Python numeric equality or loose allclose comparisons.
                self.assertEqual(expected[name].combine_chunks().buffers()[1].to_pybytes(), observed[name].combine_chunks().buffers()[1].to_pybytes())
            self.assertEqual(materialize(manifest, root / 'merged', workers=2, memory_bytes=256 << 20), closed)

    def test_digest_mismatch_cannot_publish_checkpoint(self):
        with tempfile.TemporaryDirectory(prefix='pubchem_bulk_badsha_') as directory:
            root = Path(directory)
            spec = source_fixture(root / 'bad.parquet', [(1, 'AAAAAAAAAAAAAA-AAAAAAAAAA-N', 'accepted')])
            spec['Parquet_reference']['sha256'] = 'f' * 64
            with self.assertRaisesRegex(RuntimeError, 'SHA mismatch'):
                project_fragment(spec, root / 'projected')
            self.assertFalse((root / 'projected' / 'bad' / 'complete.json').exists())
            self.assertTrue(list((root / 'projected' / 'bad').glob('attempt_*')))

    def test_ordinal_gap_cannot_be_silently_materialized(self):
        with tempfile.TemporaryDirectory(prefix='pubchem_bulk_badordinal_') as directory:
            root = Path(directory)
            spec = source_fixture(root / 'gap.parquet', [(1, 'AAAAAAAAAAAAAA-AAAAAAAAAA-N', 'accepted')])
            spec['first_ordinal'] = 2
            spec['last_ordinal'] = 2
            with self.assertRaisesRegex(RuntimeError, 'continuity'):
                project_fragment(spec, root / 'projected')
            self.assertFalse((root / 'projected' / 'gap' / 'complete.json').exists())

    def test_resume_checks_actual_checkpoint_body(self):
        with tempfile.TemporaryDirectory(prefix='pubchem_bulk_resume_') as directory:
            root = Path(directory)
            spec = source_fixture(root / 'once.parquet', [(1, 'AAAAAAAAAAAAAA-AAAAAAAAAA-N', 'accepted')])
            closed = project_fragment(spec, root / 'projected')
            path = Path(closed['accepted_parquet']['path'])
            with path.open('ab') as stream:
                stream.write(b'changed')
            with self.assertRaisesRegex(RuntimeError, 'reference mismatch'):
                project_fragment(spec, root / 'projected')


if __name__ == '__main__':
    unittest.main()
