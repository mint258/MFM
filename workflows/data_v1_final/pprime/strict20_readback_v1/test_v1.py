"""Three synthetic boundaries; never open NEW20 task/result/raw/receipt DATA."""
from __future__ import annotations
import copy,importlib,pathlib,struct,sys,unittest
from workflows.data_v1_final.pprime.strict_numerics20_qa_v1 import analysis as A
from . import contract as C,checks as K

class Boundaries(unittest.TestCase):
    def test_large_DATA_reference_and_closed_root_boundary(self):
        r={'path':str(C.ACTUAL/'qa20-00-00/all_output_raw.sqlite'),'bytes':4<<30,'sha256':'a'*64}
        self.assertEqual(C.triple(r),r);self.assertEqual(C.within(r,[C.ACTUAL]),r)
        for bad in (True,False,0,-1,1.0):
            with self.assertRaises(ValueError):C.triple(dict(r,bytes=bad))
        for bad in ('a'*63,'a'*65,'A'*64):
            with self.assertRaises(ValueError):C.triple(dict(r,sha256=bad))
        with self.assertRaises(ValueError):C.within(dict(r,path=str(C.ACTUAL.parent/'other/result')), [C.ACTUAL])
        with self.assertRaises(ValueError):C.triple(dict(r,path=str(C.ACTUAL/'../other')))
        empty=dict(r,bytes=0,sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
        self.assertEqual(C.triple(empty,source=True),empty)
        with self.assertRaises(ValueError):C.triple(empty)

    def test_cell_protocol_and_claim_identity_cannot_alias(self):
        qa='qa20-00-00';mid='SYNTHETIC_ONLY';ref={'path':'/synthetic/task','bytes':1,'sha256':'a'*64}
        plan={k:dict(ref,path='/synthetic/'+k) for k in ('candidate_protocol_reference','prepared20_reference','user_decision_reference')}
        row={'qa_id':qa,'molecule_id':mid,'task_reference':ref}
        task={'qa_id':qa,'condition':C.E.P.TASKS[0],'arm':'B1','molecule_id':mid}
        result={**task,**plan,'task_reference':ref};claim={**plan,'qa_id':qa,'task_reference':ref,'job_id':C.JOB,'uid':1278,'automatic_retry':False,'state':'INTENT_NOT_NATIVE_RETURN'}
        K.identity(row,task,result,claim,plan)
        for key,value in (('qa_id','qa20-00-01'),('arm','P1'),('molecule_id','OTHER_SOURCE'),('condition',C.E.P.TASKS[1])):
            with self.assertRaises(ValueError):K.identity(row,task,dict(result,**{key:value}),claim,plan)
        with self.assertRaises(ValueError):K.identity(row,task,result,dict(claim,candidate_protocol_reference=ref),plan)
        with self.assertRaises(ValueError):K.identity(row,task,result,dict(claim,state='NATIVE_RETURN_INVENTED'),plan)
        for bad in ('qa20-20-00','qa20-00-60','qa20-0-00','other-00-00'):
            with self.assertRaises(ValueError):K.qa_cell(bad)

    def test_original_bit_codec_and_original_five_pair_objects(self):
        wp5=C.ROOT.parent/'phase1_wp5_20261011/scripts'
        vector=C.REPO/'workflows/data_v1_final/pprime/vector_audit'
        for path in (wp5,vector):
            if str(path) not in sys.path:sys.path.insert(0,str(path))
        original_math=importlib.import_module('math_v1')
        self.assertEqual(pathlib.Path(original_math.__file__),vector/'math_v1.py')
        wire=importlib.import_module('wp5_parquet_v2');self.assertEqual(pathlib.Path(wire.__file__),wp5/'wp5_parquet_v2.py')
        # Dict member order is not scientific ordering; list/channel ordinals are.
        a={'v':[None,-0.0,{'atom_i':0,'atom_j':0,'channel_i':'P-PI','channel_j':'S-SIGMA'}],'mask':False}
        self.assertTrue(K.exact(a,dict(reversed(list(a.items()))),wire))
        for b in ({'v':[None,0.0,a['v'][2]],'mask':False},{'v':[None,-0.0,a['v'][2]],'mask':0},
                  {'v':list(reversed(a['v'])),'mask':False},{'v':[0.0,-0.0,a['v'][2]],'mask':False}):
            with self.assertRaises(ValueError):K.exact(a,b,wire)
        records=[]
        for arm in C.E.P.ARMS:
            records.append({'qa_id':'SYNTHETIC_'+arm,'molecule_id':'SYNTHETIC_ONLY','condition':'pm7_water','arm':arm,
                'native_invoke_function_return_observed':True,'parsed_wp5_result':{'scope_status':'SUCCESS','atomic_array_validation':[]},
                'actual_postcall_input_references':[{'matches_prepared_bytes':True}],
                'closed_raw_container_reference':{'synthetic':True},'raw_readback_source':'CLOSED_SQLITE_GZIP_EOF_CRC_WHOLE_AND_MEMBER_SHA_ORIGINAL_UNBUNDLE'})
        pairs=A.completed_group(records,{})
        self.assertEqual([tuple(r['arms']) for r in pairs],list(A.PAIRS));self.assertTrue(all(r['defined_QC_pass'] and not r['defined_vector_checks'] for r in pairs))
        with self.assertRaises(ValueError):A.completed_group(records+[records[0]],{})
        changed=copy.deepcopy(pairs);changed[0]['unsupported_axes_basis_tensors_certified']=True
        with self.assertRaises(ValueError):K.exact(pairs,changed,wire)

if __name__=='__main__':unittest.main()
