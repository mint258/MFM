"""Three meaningful synthetic boundaries. No DATA or initialize/invoke."""
import copy,importlib.util,pathlib,sys,unittest
from workflows.data_v1_final.pprime.strict_numerics_qa_proposal_v1.test_v1 import baseline
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from . import contract as C,inputs as I,execution_contract as E
from .proposal import proposal

class Boundaries(unittest.TestCase):
    def test_unique_MID_rank0_target_independent_sample_and_atom_boundary(self):
        pairs=[{'record_id':f'synthetic-{i}-{rank}','molecule_id':f'mid-{i:04d}','random_order_rank':rank,
            'source':{'total_atoms':81 if i<10 else 0 if i<20 else 1},'unused_target_values':[i,rank]} for i in range(1000) for rank in (0,1)]
        chosen,stats=C.choose20(pairs);again,_=C.choose20(list(reversed(pairs)))
        self.assertEqual([p['record_id'] for p in chosen],[p['record_id'] for p in again]);self.assertEqual(len({p['molecule_id'] for p in chosen}),20)
        self.assertTrue(all(p['random_order_rank']==0 and p['source']['total_atoms']==1 for p in chosen));self.assertEqual(stats['QA_unavailable_over80_atoms'],10)
        self.assertEqual(stats['invalid_source_below1_atom'],10);self.assertEqual(stats['eligible_MIDs_1to80_atoms'],980)
        changed=copy.deepcopy(pairs)
        for pair in changed:pair['unused_target_values']=['DO_NOT_SCORE']
        self.assertEqual([p['record_id'] for p in C.choose20(changed)[0]],[p['record_id'] for p in chosen])
        bad=copy.deepcopy(pairs);bad[-1]['record_id']=bad[0]['record_id']
        with self.assertRaises(ValueError):C.choose20(bad)
        for pair in bad:pair['source']['total_atoms']=81
        with self.assertRaises(ValueError):C.choose20(bad)

    def test_all12_five_arms_renderer_exact_P90_and_only_three_protocol_fields(self):
        import numpy as np
        path=C.S.P.ORIGINAL_PROTOCOL.parent.parent/'scripts/wp5_engine_v3.py';self.assertEqual(C.Q.pin(path)['sha256'],C.O.ENGINE_SHA)
        saved=list(sys.path);sys.path.insert(0,str(path.parent))
        try:
            spec=importlib.util.spec_from_file_location('new20_synthetic_renderer_only',path);engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
        finally:sys.path[:]=saved
        self.assertIsNone(engine.NATIVE);old=baseline();new,diff=C.S.P.derive(old);self.assertEqual(C.S.P.restore(new),old);self.assertEqual(len(diff),3)
        z=np.asarray([6,1,1,1,1,1],dtype='<i8');xyz=np.asarray([[0.,0.,0.],[.5,1.,0.],[-.5,0.,1.],[1.,2.,3.],[-2.,-1.,.5],[3.,0.,-1.]],dtype='<f8')
        native={'symbols':['C','H','H','H','H','H'],'z':z,'coords':xyz,'pairs':[(1,0)],'native_atom_order_sha256':C.O.sha(z.tobytes())}
        pair={'molecule_id':'SYNTHETIC','record_id':'SYNTHETIC-PAIR','source':{'record_id':'SYNTHETIC-NATIVE'},'uff_coordinate_sha256':C.O.sha(xyz.tobytes())}
        values=I.render_one(pair,native,old,new,engine);self.assertEqual(len(values),60);by={(v['condition'],v['arm']):v for v in values}
        for name in C.TASKS:
            b=by[name,'B1'];self.assertEqual(b['candidate_inputs'],by[name,'B2']['candidate_inputs'])
            self.assertEqual(by[name,'P1']['candidate_inputs'],by[name,'P2']['candidate_inputs'])
            p=by[name,'P1'];expected={n:T.p90(body,n) if n in ('input.xyz','input.mop') else body for n,body in b['original_inputs'].items()}
            self.assertEqual(p['original_inputs'],expected);self.assertEqual(p['case']['symbols'],native['symbols'])
            self.assertEqual(b['case']['row']['record_id'],pair['record_id']);self.assertEqual(p['case']['rotation_matrix'],C.O.P90)
            self.assertEqual(T.arrays(b['original_inputs'],native['symbols']).tobytes(),T.arrays(b['candidate_inputs'],native['symbols']).tobytes())
        self.assertIsNone(engine.NATIVE)

    def test_no_new20_authority_no_execution_and_finite_role_bounds(self):
        for plan in ({},{'user_decision_reference':None}):
            with self.assertRaises(ValueError):E.require_user(plan)
        with self.assertRaises(ValueError):E.user_fields({'schema':'USER_AUTHORIZED_PPRIME_STRICT_NUMERICS15_QA_V1'}, {})
        ref={'path':'/synthetic/protocol','bytes':19385976,'sha256':'0'*64};prep={'path':'/synthetic/prepared','bytes':1,'sha256':'1'*64}
        self.assertEqual(C.O.triple(ref),ref)  # DATA locator is not the2MiB small metadata normalizer.
        first=E.once_key(ref,prep,'qa20-00-00');self.assertNotEqual(first,E.once_key(ref,prep,'qa20-19-59'))
        self.assertNotEqual(first,E.once_key({**ref,'sha256':'2'*64},prep,'qa20-00-00'))
        for key in ('qa-00','qa20-20-00','qa20-00-60'):
            with self.assertRaises(ValueError):E.once_key(ref,prep,key)
        p=proposal();self.assertEqual(p['maximum_new_QM_calls'],1200);r=p['execution_resources_proposed']
        self.assertLess(r['managed_upper_bound_bytes'],32<<30);self.assertEqual(r['managed_upper_bound_bytes'],32672<<20)
        self.assertFalse(p['source_state']['execution_entrypoint_present']);self.assertTrue(r['RLIMIT_FSIZE_is_not_total_scratch_limit'])

if __name__=='__main__':unittest.main()
