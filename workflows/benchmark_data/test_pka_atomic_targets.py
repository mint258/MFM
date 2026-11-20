"""New projection boundaries; synthetic targets only, no chemistry or real-data replay."""
import json
import unittest
import pyarrow as pa
from .pka_atomic_targets import AUTHORITY, NAMESPACE, promote_table


def example():
    base = dict(endpoint='atomic_pKa_acid', target_value=-0.0, benchmark_role='TRAIN_POOL',
                geometry_dataset='pKahub', geometry_record_id='source:7',
                source_atom_index=2, model_atom_index=0, atom_site_id=None,
                eligibility_status='PROPOSED_SOURCE_CATALOG_DEFINITION_NOT_FROZEN',
                definition_approved=False,
                experimental_macro_reused_under_single_site_definition=True,
                experimental_microscopic_annotation=False, target_units='pKa',
                source_values=[-0.0, 1.2345678901234567])
    return pa.Table.from_pylist([dict(base, record_id='TRAIN_POOL:full-key:acid'),
        dict(base, record_id='EXTERNAL_BLIND:SAMPL7:SM01:acid', benchmark_role='EXTERNAL_BLIND',
             target_value=float('nan'))])


class AtomicProjectionTests(unittest.TestCase):
    def setUp(self):
        self.authority = json.loads(AUTHORITY.read_text())

    def test_explicit_matching_user_authority_is_required(self):
        for change in ({'approved':False}, {'authority_kind':'implicit'},
                       {'definition_id':'other'}, {'catalog_patterns':36}, {'question_item_id':''}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                promote_table(example(), dict(self.authority, **change))

    def test_atomic_namespace_preserves_macro_and_original_atom_mapping(self):
        source = example(); result, counts = promote_table(source, self.authority)
        self.assertEqual(result['macro_record_id'].to_pylist(), source['record_id'].to_pylist())
        self.assertEqual(result['record_id'].to_pylist(), [NAMESPACE+x for x in source['record_id'].to_pylist()])
        self.assertTrue(set(result['record_id'].to_pylist()).isdisjoint(source['record_id'].to_pylist()))
        self.assertEqual(result['source_atom_index'].to_pylist(), [2,2])
        self.assertEqual(result['model_atom_index'].to_pylist(), [0,0])
        self.assertEqual(result['atom_site_id'].to_pylist(), ['atomic_site:v1:pKahub:source:7:source_atom:2']*2)
        self.assertEqual(counts, {'TRAIN_POOL':1, 'EXTERNAL_BLIND':1})

    def test_f64_payload_bytes_and_source_precision_are_retained(self):
        source = example(); result, _ = promote_table(source, self.authority)
        for name in ('target_value', 'source_values'):
            self.assertEqual(result[name].type, source[name].type)
            before = source[name].chunk(0); after = result[name].chunk(0)
            self.assertEqual([b.to_pybytes() if b else None for b in before.buffers()],
                             [b.to_pybytes() if b else None for b in after.buffers()])
        self.assertEqual(result['definition_approved'].to_pylist(), [True,True])
        self.assertEqual(result['experimental_microscopic_annotation'].to_pylist(), [False,False])

    def test_ambiguous_or_unmapped_proposals_fail_without_silent_filtering(self):
        for change in ({'source_atom_index':-1}, {'model_atom_index':None},
                       {'eligibility_status':'UNRESOLVED'}, {'benchmark_role':'UNKNOWN'},
                       {'experimental_microscopic_annotation':True}):
            rows=example().to_pylist(); rows[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                promote_table(pa.Table.from_pylist(rows), self.authority)

    def test_duplicate_macro_identity_and_repromotion_are_rejected(self):
        rows=example().to_pylist(); rows[1]['record_id']=rows[0]['record_id']
        with self.assertRaises(ValueError):
            promote_table(pa.Table.from_pylist(rows), self.authority)
        result,_=promote_table(example(),self.authority)
        with self.assertRaises(ValueError):
            promote_table(result,self.authority)

    def test_non_f64_input_is_not_silently_promoted_or_cast(self):
        source=example(); source=source.set_column(source.schema.get_field_index('target_value'),
                                                  'target_value', pa.array([1.,2.],type=pa.float32()))
        with self.assertRaises(ValueError):
            promote_table(source,self.authority)


if __name__ == '__main__':
    unittest.main()
