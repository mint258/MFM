"""Three small synthetic IO/math/order boundaries before any DATA."""
import copy,hashlib,struct,unittest
from . import codec as K,contract as C,bindings as B

class Boundaries(unittest.TestCase):
    def test_float64_none_masks_indices_reasons_and_owned_offsets(self):
        field={'field_id':0,'field_key':'synthetic','source_path':'value'}
        e={'field_id':0,'values_float64':[-0.0,None,1.25,float('inf')],'atom_indices':[0,None,2,3],
          'source_value_mask':[True,False,True,False],'value_mask':[True,False,False,False],
          'source_reasons':['SOURCE_SYNTHETIC'],'new_reasons':['NEW_SYNTHETIC'],'review_reasons':['REVIEW_SYNTHETIC']}
        row=K.pack_entries([e]);out=K.unpack_entries(row,{0:field})[0]
        self.assertEqual(struct.pack('<d',out['values_float64'][0]),struct.pack('<d',-0.0));self.assertIsNone(out['values_float64'][1])
        for key in ('atom_indices','source_value_mask','value_mask','source_reasons','new_reasons','review_reasons'):self.assertEqual(out[key],e[key])
        bad=copy.deepcopy(row);bad['data_f64']+=b'\0'
        with self.assertRaises(ValueError):K.unpack_entries(bad,{0:field})
        bad=copy.deepcopy(row);bad['lengths']=[5]
        with self.assertRaises(ValueError):K.unpack_entries(bad,{0:field})
        self.assertNotEqual(K.owner_signature({'new_role':'TRAIN','record_id':'same'}),K.owner_signature({'new_role':'VAL','record_id':'same'}))

    def test_exact_physical_cursor_and_quality_no_timeout_promotion(self):
        files=[{'file_id':7,'rows':10}];win={'file_id':7,'lo':0,'hi':4,'all_part_reopen_bits_verified':True}
        self.assertEqual(C.advance_cursors(files,{},[win]),{'7':4})
        self.assertEqual(C.advance_cursors(files,{'7':4},[dict(win,lo=4,hi=10)]),{'7':10})
        for windows in ([dict(win,lo=1)], [win,win], [dict(win,all_part_reopen_bits_verified=False)]):
            with self.assertRaises(ValueError):C.advance_cursors(files,{},windows)
        self.assertEqual(B.quality_stop_fields({'0':{'newly_masked_records':1}},100,.01),[])
        self.assertEqual(B.quality_stop_fields({'0':{'newly_masked_records':2}},100,.01),['0'])
        account={'schema':'DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1','status':'ACTUAL_PARENT_ACCOUNTING_CLOSED','query_returncode':0,'uid':1278,
          'parents':[{'job_id':'SYNTHETIC','state':'TIMEOUT','exit_code':'0:0','alloc_cpus':16}]}
        with self.assertRaises(ValueError):C.actual_c0(account,'SYNTHETIC')
        account['parents'][0]['state']='COMPLETED';self.assertEqual(C.actual_c0(account,'SYNTHETIC')['state'],'COMPLETED')
        with self.assertRaises(ValueError):C.actual_c0(account,'DIFFERENT_PARENT')

    def test_original256_buffer_continues_across_parts_and_leftfold(self):
        from workflows.data_v1_final.labels.streaming_v1 import calibration as O
        self.assertIs(B.TSQR,O.TSQR);self.assertIs(B.merge_qr,O.merge_qr);self.assertIs(B.RadixCounts,O.RadixCounts)
        # Same logical row sequence, two physical repackings, one accumulator per group.
        sequence=[([1,6],float(i%7)) for i in range(513)]
        left=B.TSQR([1,6]);right=B.TSQR([1,6])
        for z,v in sequence:left.add(z,v)
        for part in (sequence[:1],sequence[1:255],sequence[255:256],sequence[256:512],sequence[512:]):
            for z,v in part:right.add(z,v)
        self.assertEqual(left.state(),right.state())
        self.assertEqual(B.verify_function_objects()['TSQR_chunk'],256)
        # Original statistical-copy winsorization and Chan/ddof0 output; source values remain unchanged.
        source=[0.,1.,2.,3.,4.];before=list(source);moment=B.WinsorMoments(1.,3.);moment.add(source)
        value=B.combine([B.moment_state(moment)])
        self.assertEqual(source,before);self.assertEqual(value['n'],5);self.assertEqual(value['mean'],2.)
        self.assertAlmostEqual(value['std_ddof0'],.8**.5)
        from .statistics import exact_tails
        with self.assertRaises(ValueError):exact_tails([{'field_id':0}],{'lower':[],'upper':[]})

if __name__=='__main__':unittest.main()