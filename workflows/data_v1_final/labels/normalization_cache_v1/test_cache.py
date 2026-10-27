"""Six incremental cache-reader boundaries; no old statistics suite repeated."""
import copy,hashlib,struct,tempfile,unittest
from pathlib import Path
from .reader import CompatibilityGap,base_metadata,cell_view,entries,equal_bits,finite_train,logical_source,projected_decode
from .profile import PointerIndex
from workflows.data_v1_final.labels.streaming_v1.support import legacy
from workflows.data_v1_final.labels.streaming_v1.calibration import train_values
from workflows.data_v1_final.labels.streaming_v1 import compact
from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import encode
SCIENCE=None


class CacheAdapterBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SCIENCE is None:raise RuntimeError('RUN_THROUGH_FRESH_PROFILE_PRIMARY_TO_BIND_SCIENCE_SOURCE_PINS')
        cls.common,cls.masks=legacy(SCIENCE)

    def test_selected_F64_rebase_preserves_bits_and_ignores_other_branch(self):
        nan=struct.unpack('<d',bytes.fromhex('010000000000f87f'))[0]
        value={'selected':{'x':[-0.0,nan,0.0]},'ignored':[1.0,2.0,3.0]};tree,pool=encode(value)
        out=projected_decode(tree,pool,{'selected'})
        self.assertTrue(equal_bits(out,{'selected':value['selected']}));self.assertEqual(struct.pack('<d',out['selected']['x'][1]),struct.pack('<d',nan))

    def test_logical_CELL_kinds_and_JSON_order_are_strict(self):
        samples=[(1,[], -0.0),(2,[],2**54+3),(3,[],False),(4,[],'native text'),
          (5,[2,2],[[0.0,-0.0],[1.5,2.5]]),(6,[2],[0,4]),(7,[2],[True,False]),
          (8,[],[{'atom_i':1,'basis_i':'px','atom_j':0,'basis_j':'s','value':-0.0}]),(10,[],{'z':[None,0,1.25],'a':False})]
        for kind,shape,value in samples:
            item={'registry_id':60,'kind':kind,'declared_shape':shape,'state':'DECODED','decoded_scientific_value':value}
            result=cell_view(item,self.common);self.assertTrue(equal_bits(self.common.decode_cell(result),value))
        absent=cell_view({'registry_id':60,'kind':9,'declared_shape':[],'state':'ABSENT'},self.common)
        self.assertIs(self.common.decode_cell(absent),self.common.MISSING)

    def test_duplicate_or_unknown_source_never_becomes_an_accepted_empty_input(self):
        p={'source_status_and_precision':{'status':'SUCCESS'},'provenance':{'source_reference':{'family':'pm7_neutral'}},
          'structural_reviews':[{'reason':'DUPLICATE_REGISTRY_CELL_REVIEW','registry_id':999}], 'cells':[]}
        with self.assertRaisesRegex(CompatibilityGap,'LEGACY_WOULD_STOP'):logical_source(p,self.common)
        with self.assertRaisesRegex(CompatibilityGap,'UNIDENTIFIED'):cell_view({'unidentified_cell':None},self.common)

    def test_regenerated_partial_mask_and_NULL_convergence_parity(self):
        field={'field_id':0,'field_key':'fixture.atom','registry_id':1,'task':'xtb_vfukui','source_path':'values.atom_fixture',
          'level':'atom','component':'value','physical_range':{'lower':0.0,'upper':None,'lower_exclusive':False}}
        cell={'registry_id':1,'kind':5,'declared_shape':[2],'state':'DECODED','decoded_scientific_value':[-1.0,2.0]}
        row={'status':'SUCCESS','converged':None,'calc_type':'xtb_vfukui','total_atoms':2}
        _,sm,vm,sr,nr,rr=self.masks.source_value_mask(field,row,[-1.0,2.0],None)
        item={'field_id':0,'values_float64':[-1.0,2.0],'source_value_mask':sm,'value_mask':vm,'source_reasons':sr,'new_reasons':nr,'review_reasons':rr}
        p={'provenance':{'source_reference':{'family':'xtb_vfukui'},'owner':{'total_atoms':2,'record_ordinal':7}},
          'task':'xtb_vfukui','source_status_and_precision':row,'cells':[cell],'structural_reviews':[],
          'component_map':[{'field_key':'fixture.atom','cell_position':0,'ordered_leaf_paths':[['decoded_scientific_value',0],['decoded_scientific_value',1]],'atom_indices':[0,1]}],
          'original_compact_candidate':compact.encode(7,1,[item])}
        out=entries(p,[field],self.common,self.masks,1)[0]
        self.assertEqual(out['value_mask'],[False,True]);self.assertIn('SUCCESS_WITH_CONVERGENCE_EVIDENCE_UNKNOWN',out['review_reasons'])
        bad=copy.deepcopy(p);bad['original_compact_candidate']['valid_fields']=compact.bits([])
        with self.assertRaisesRegex(CompatibilityGap,'REGENERATED_MASK_DIFFER'):entries(bad,[field],self.common,self.masks,1)

    def test_only_source_TRAIN_valid_leaves_reach_the_frozen_calibration(self):
        item={'values_float64':[-0.0,99.0],'value_mask':[True,False]}
        self.assertTrue(equal_bits(finite_train(item,'TRAIN',train_values),[-0.0]))
        for role in ('VAL','FULL','EMBARGO'):self.assertEqual(finite_train(item,role,train_values),[])
        with self.assertRaises(ValueError):finite_train(item,'UNKNOWN',train_values)

    def test_base_Z_projection_avoids_coordinate_pool_and_pointer_duplicate_holds(self):
        z=[1,6];sha=hashlib.sha256(b''.join(struct.pack('<q',v) for v in z)).hexdigest()
        value={'provenance':{'owner':{'record_ordinal':7}},'original_geometry':{'atomic_numbers':z,'positions_A':[[1.0,2.0,3.0],[4.0,5.0,6.0]],
          'native_atom_order_sha256':sha,'source_payload_sha256':'x','geometry_status':'ORIGINAL_PM7_GEOMETRY'}}
        tree,pool=encode(value);self.assertTrue(pool);out=base_metadata(tree)
        self.assertEqual(out['original_geometry']['atomic_numbers'],z);self.assertNotIn('positions_A',out['original_geometry'])
        with tempfile.TemporaryDirectory() as tmp:
            index=PointerIndex(Path(tmp)/'pointer.sqlite')
            try:
                index.add(7,1,3,5)
                with self.assertRaisesRegex(CompatibilityGap,'DUPLICATE_CANONICAL_KEY_ANY_VALUE'):index.add(7,1,4,0)
            finally:index.close()
