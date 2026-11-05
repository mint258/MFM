"""Three synthetic boundaries only: no initialization, native calls or DATA."""
import copy,importlib.util,pathlib,sys,tempfile,unittest
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from workflows.data_v1_final.pprime.strict_numerics_qa_proposal_v1.test_v1 import baseline
from . import contract as C,io as W,prepare as A


class Boundaries(unittest.TestCase):
    def test_protocol_inverse_and_protocol_bound_claim_is_exclusive(self):
        old=baseline();new,diff=C.P.derive(old);self.assertEqual(C.P.restore(new),old);self.assertEqual(len(diff),3)
        protocol={'path':'/synthetic/protocol','bytes':1,'sha256':'0'*64};prepared={'path':'/synthetic/prepared','bytes':1,'sha256':'2'*64}
        key=C.P.once_key(protocol,prepared,'qa-00')
        self.assertNotEqual(key,C.P.once_key({**protocol,'sha256':'1'*64},prepared,'qa-00'))
        self.assertNotEqual(key,C.P.once_key(protocol,prepared,'qa-01'))
        with tempfile.TemporaryDirectory(prefix='strictqa15_synthetic_claim_') as d:
            root=pathlib.Path(d);store=W.Store(root,3<<20);p=root/(key+'.json');value={'synthetic_only':True,'protocol':protocol,'prepared':prepared,'qa_id':'qa-00'}
            first=W.claim_create(p,value,store)
            with self.assertRaises(FileExistsError):W.claim_create(p,value,store)
            self.assertEqual(C.Q.pin(p),first)

    def test_no_or_wrong_user_decision_fails_before_body_callback(self):
        called=[]
        def dependent(plan):C.require_user(plan);called.append('BODY_OR_NATIVE_MUST_NEVER_HAPPEN')
        for value in ({},{'user_decision_reference':None}):
            with self.assertRaises(ValueError):dependent(value)
        plan={'candidate_protocol_reference':{'synthetic':1},'original_protocol_reference':{'synthetic':2}}
        decision={'schema':'USER_AUTHORIZED_PPRIME_STRICT_NUMERICS15_QA_V1','status':'USER_AUTHORIZED','authorization_basis':'EXPLICIT_USER_MESSAGE_IN_THIS_SESSION',
            'actual_user_statement':'SYNTHETIC UNIT VALUE ONLY - NO REAL APPROVAL','candidate_protocol_reference':plan['candidate_protocol_reference'],
            'original_protocol_reference':plan['original_protocol_reference'],'maximum_new_QM_calls':15,'cpus':16,'maximum_wall_seconds':7200,
            'per_call_timeout_seconds':900,'whole_output_cap_bytes':C.CAP,'original_quality_thresholds_unchanged':True,'production_recipe_unchanged':True,
            'automatic_retry':False,'full_or2000_release':'HOLD'}
        C.user_fields(decision,plan)
        for key,value in (('status','PENDING'),('maximum_new_QM_calls',16),('per_call_timeout_seconds',901),('automatic_retry',True),('full_or2000_release','RELEASE')):
            bad=copy.deepcopy(decision);bad[key]=value
            with self.assertRaises(ValueError):C.user_fields(bad,plan)
        self.assertEqual(called,[])

    def test_original_renderer_same_coordinates_only_declared_parameters(self):
        import numpy as np
        path=C.P.ORIGINAL_PROTOCOL.parent.parent/'scripts/wp5_engine_v3.py';self.assertEqual(C.Q.pin(path)['sha256'],C.O.ENGINE_SHA)
        saved=list(sys.path);sys.path.insert(0,str(path.parent))
        try:
            spec=importlib.util.spec_from_file_location('strictqa15_synthetic_renderer_only',path);engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
        finally:sys.path[:]=saved
        self.assertIsNone(engine.NATIVE);old=baseline();new,_=C.P.derive(old)
        z=np.asarray([6,1,1],dtype='<i8');coords=np.asarray([[0.,0.,0.],[.5,1.,0.],[-.5,0.,1.]],dtype='<f8')
        case={'symbols':['C','H','H'],'atomic_numbers':z.tolist(),'pairs':[[0,1],[0,2]],'native_atom_order_sha256':C.O.sha(z.tobytes()),'row':{'record_id':'SYNTHETIC-ONLY'}}
        native={'symbols':case['symbols'],'z':z,'coords':coords,'pairs':case['pairs'],'native_atom_order_sha256':case['native_atom_order_sha256']}
        for name in ('pm7_B','xtb_singlepoint'):
            before=next(v for v in old['tasks'] if v['name']==name);inputs=engine.render_inputs(before,native,case['row'],old)
            actual,seed=T.bridge(case,inputs,before,old,engine);task={'case':case,'original_task':before,'seed':seed,'native_coordinates_A':actual['coords'].tolist()}
            derived,_,after,rendered=A.targets(task,inputs,old,new,engine)
            self.assertEqual(T.arrays(inputs,case['symbols']).tobytes(),T.arrays(rendered,case['symbols']).tobytes())
            self.assertEqual(derived['coords'].tobytes(),coords.tobytes())
            if name=='pm7_B':self.assertEqual(after['keywords'],before['keywords']+' '+C.P.SCFCRT)
            else:self.assertEqual(rendered,inputs);self.assertEqual(after['args'],before['args']+C.P.ACC)
        self.assertIsNone(engine.NATIVE)


if __name__=='__main__':unittest.main()
