"""Three new boundaries for the actual1915 base/provenance projection defect."""
import copy,hashlib,json,struct,unittest
from . import reader
from ..normalization_cache_v1 import reader as frozen
from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import encode
SCIENCE=None  # Assigned by the shared fixture harness; no source-body fixture.


def base_value():
    z=[1,6];sha=hashlib.sha256(b''.join(struct.pack('<q',v) for v in z)).hexdigest()
    return {'provenance':{'source_reference':{'seconds':1.4602348357439041},
      'owner':{'record_ordinal':7,'unneeded_float_metadata':0.25}},
      'original_geometry':{'atomic_numbers':z,'native_atom_order_sha256':sha,
        'source_payload_sha256':'fixture','geometry_status':'ORIGINAL_PM7_GEOMETRY',
        'positions_A':[[1.0,-0.0,3.0],[4.0,5.0,6.0]]}}


class CacheAdapterBoundaries(unittest.TestCase):
    def test_actual_float_reference_metadata_reproduces_old_failure_new_projection_uses_no_pool(self):
        value=base_value();tree,pool=encode(value);saved_tree=tree;saved_bits=[struct.pack('<d',v) for v in pool]
        with self.assertRaisesRegex(frozen.CompatibilityGap,'SELECTED_FLOAT_POOL_OWNERSHIP'):frozen.base_metadata(tree)
        out=reader.base_metadata(tree)
        self.assertEqual(out['provenance'],{'owner':{'record_ordinal':7}})
        self.assertEqual(out['original_geometry'],{k:value['original_geometry'][k] for k in
          ('atomic_numbers','native_atom_order_sha256','source_payload_sha256','geometry_status')})
        self.assertEqual(tree,saved_tree);self.assertEqual([struct.pack('<d',v) for v in pool],saved_bits)
        self.assertIs(reader.projected_decode,frozen.projected_decode);self.assertIs(reader.entries,frozen.entries)
        self.assertIs(reader.cell_view,frozen.cell_view);self.assertIs(reader.finite_train,frozen.finite_train)

    def test_required_metadata_float_or_missing_field_still_HOLD_no_zero_or_XYZ_fallback(self):
        for path in ('ordinal','Z'):
            value=base_value()
            if path=='ordinal':value['provenance']['owner']['record_ordinal']=7.0
            else:value['original_geometry']['atomic_numbers']=[1.0,6]
            tree,pool=encode(value)
            with self.assertRaisesRegex(frozen.CompatibilityGap,'SELECTED_FLOAT_POOL_OWNERSHIP'):reader.base_metadata(tree)
        value=base_value();del value['original_geometry']['source_payload_sha256'];tree,pool=encode(value)
        with self.assertRaisesRegex(frozen.CompatibilityGap,'REQUIRED_KEY'):reader.base_metadata(tree)

    def test_original_f64_index_uniqueness_bounds_and_order_bits_remain_unchanged(self):
        duplicate=json.dumps(['d',[['a',['f64',0]],['b',['f64',0]]]])
        with self.assertRaisesRegex(frozen.CompatibilityGap,'SELECTED_FLOAT_POOL_OWNERSHIP'):
            reader.projected_decode(duplicate,[1.0],{'a','b'})
        invalid=json.dumps(['d',[['a',['f64',1]]]])
        with self.assertRaisesRegex(frozen.CompatibilityGap,'SELECTED_FLOAT_POOL_OWNERSHIP'):
            reader.projected_decode(invalid,[1.0],{'a'})
        value={'keep':{'second':-0.0,'first':[False,None,2**54+3,1.25]},'ignore':9.0};tree,pool=encode(value)
        out=reader.projected_decode(tree,pool,{'keep'})
        self.assertTrue(frozen.equal_bits(out,{'keep':value['keep']}));self.assertEqual(list(out['keep']),['second','first'])
