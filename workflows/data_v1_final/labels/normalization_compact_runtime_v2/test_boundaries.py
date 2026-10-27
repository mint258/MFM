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
        # Real central proof shape: canonical aware ISO and Slurm fields, no top-level unix field.
        from datetime import datetime
        from .runtime import wall_clock,remaining_wall,slurm_seconds
        proof={'job_id':'123','observed_at':'2026-10-27T14:18:41.504686+00:00','root_observed_at':'2026-10-27T22:18:41.494717+08:00',
          'job_metadata':'JobId=123 JobState=RUNNING RunTime=00:00:18 TimeLimit=02:00:00 StartTime=2026-10-27T22:18:22 EndTime=2026-10-28T00:18:22'}
        now=datetime.fromisoformat(proof['observed_at']).timestamp()+6;clock=wall_clock(proof,7200,now_wall=now,now_monotonic=100.)
        self.assertEqual(clock['conservative_elapsed_at_anchor_seconds'],26);self.assertEqual(clock['remaining_at_anchor_seconds'],7174)
        self.assertEqual(remaining_wall(clock,101.5),7172.5);self.assertLessEqual(wall_clock(proof,20,now_wall=now,now_monotonic=100.)['remaining_at_anchor_seconds'],0)
        self.assertEqual(slurm_seconds('2-03:04:05'),183845)
        for bad in ('UNLIMITED','00:60:00','garbage'):
            with self.assertRaises(ValueError):slurm_seconds(bad)
        for changed in (dict(proof,observed_at='2026-10-27T14:18:41'),dict(proof,root_observed_at='2026-10-27T22:18:41')):
            with self.assertRaises(ValueError):wall_clock(changed,7200,now_wall=now,now_monotonic=100.)
        with self.assertRaises(ValueError):wall_clock(proof,7200,now_wall=now-7,now_monotonic=100.)
        with self.assertRaises(ValueError):wall_clock(proof,7200,now_wall=float('inf'),now_monotonic=100.)
        with self.assertRaises(ValueError):remaining_wall(clock,99.)
        ref={'path':str(C.RUN/'control/synthetic_parent.json'),'bytes':1,'sha256':'0'*64};source3=dict(ref,path=str(C.RUN/'control/synthetic_source3.json'))
        review={'reviewer':'root','status':'ROOT_APPROVED_INDEPENDENT_NUMERIC_REPROJECTION','evidence':{'source_footer_actual_C0':ref},
          'verified_current_small_metadata_references':[ref],'actual_source_inverse3_review_reference':source3}
        self.assertEqual(len(C.parent_evidence(review)),2)
        with self.assertRaises(ValueError):C.parent_evidence(dict(review,verified_current_small_metadata_references=[]))
        with self.assertRaises(ValueError):C.parent_evidence(review,{ref['path']})
        with self.assertRaises(ValueError):C.parent_evidence(dict(review,actual_source_inverse3_review_reference=dict(ref,path=str(C.RUN/'artifacts/numeric.parquet'))))

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