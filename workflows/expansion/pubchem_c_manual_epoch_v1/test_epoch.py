"""Three synthetic boundary methods only; no DATA, scheduler, Budget or claim IO."""
import math,unittest
from . import policy as P
from pubchem_c_finite500_continuation_v3 import state as S

class Boundaries(unittest.TestCase):
    def test_mixed_origin_adoption_and_physical_cost_union(self):
        initial={0:{'shard_index':0,'status':'CLOSED','job_id':'10'}}
        fees={'10':{'job_id':'10','actual_allocated_core_seconds':16},'11':{'job_id':'11','actual_allocated_core_seconds':336}}
        old={'shard_index':52,'status':'CLOSED','job_id':'12','actual_allocated_core_seconds':32,'root_range_review_reference':{'synthetic':'old'}}
        running={'shard_index':53,'status':'RUNNING','job_id':'13','root_range_review_reference':{'synthetic':'new'}}
        pop,actual=P.merge_rows(initial,[old,running],fees)
        self.assertEqual(set(pop),{0,52,53});self.assertEqual(set(actual),{'10','11','12'})
        self.assertIs(pop[52],old);self.assertIs(pop[53],running);self.assertEqual(actual['11']['actual_allocated_core_seconds'],336)
        with self.assertRaisesRegex(ValueError,'ONE_REGISTERED'):P.merge_rows(initial,[old,dict(old)],fees)
        with self.assertRaisesRegex(ValueError,'DOUBLE_COUNT'):P.merge_rows(initial,[dict(old,job_id='10')],fees)
        x={'endpoint':'synthetic-alpha','uid':1264,'job_id':'12','allocated_core_seconds':32}
        self.assertEqual(len(P.exact_union([x,dict(x)])),1)
        self.assertEqual(len(P.exact_union([x,dict(x,endpoint='synthetic-main')])),2)
        with self.assertRaisesRegex(ValueError,'CONFLICTING'):P.exact_union([x,dict(x,allocated_core_seconds=33)])

    def test_consumed_unknown_never_reappears_as_unstarted_and_original_capacity(self):
        seen=[]
        def decision(*args):seen.append(args);return ('ELIGIBLE',54,'synthetic-node')
        self.assertTrue(P.safe_next({52:{'status':'CLOSED'}},{52,53},set(),decision,{},1,2)[0].startswith('HOLD'))
        self.assertTrue(P.safe_next({52:{'status':'CLOSED'}},set(),{53},decision,{},1,2)[0].startswith('HOLD'));self.assertEqual(seen,[])
        self.assertEqual(P.safe_next({52:{}},{52},{52},decision,{},1,2),('ELIGIBLE',54,'synthetic-node'))
        closed={i:{'status':'CLOSED','expected_rows':250000,'actual_state':'COMPLETED','actual_exit':'0:0'} for i in range(54)}
        # The actual frozen state functions decide the original6-C/spare16 limits.
        pop={**closed,**{i:{'status':'RUNNING'} for i in range(54,60)}}
        action,_,_=S.decision(pop,set(),{n:96 for n in S.NODES},1,2);self.assertEqual(action,'WAIT_AT_ROOT_NONTERMINAL_C_CAP')
        self.assertIsNone(S.choose_node({n:16 if k==0 else 0 for k,n in enumerate(S.NODES)}))
        self.assertIsNotNone(S.choose_node({n:32 if k==0 else 0 for k,n in enumerate(S.NODES)}))
        blocked={**closed,54:{'status':'UNKNOWN'}}
        self.assertEqual(S.decision(blocked,set(),{n:96 for n in S.NODES},1,2)[0],'HOLD_FAILED_UNKNOWN_OR_PARTIAL_NO_RETRY')

    def test_finite_cutover_wait_zero_intent_and_source_identity(self):
        old=100.0;self.assertEqual(P.finite_epoch(old,90.0,180.0)['old_deadline_unchanged'],old)
        for bad in (True,float('inf'),float('nan')):
            with self.assertRaises(ValueError):P.finite_epoch(old,bad,180)
        with self.assertRaises(ValueError):P.finite_epoch(old,100,72101)
        self.assertTrue(P.transition_gate(True,True,100,110,200,True).startswith('WAIT'))
        self.assertTrue(P.transition_gate(False,False,100,110,200,True).startswith('WAIT'))
        with self.assertRaises(ValueError):P.transition_gate(False,True,100,99,200,True)
        with self.assertRaises(ValueError):P.transition_gate(False,True,100,110,200,False)
        self.assertTrue(P.transition_gate(False,True,100,201,200,True).startswith('FINITE'))
        self.assertEqual(P.transition_gate(False,True,100,110,200,True),'ROOT_REVIEWED_NEW_EPOCH_CAN_OBSERVE')
        calls=[]
        self.assertTrue(P.safe_next({},set(),set(),lambda *a:calls.append(a),{},200,200)[0].startswith('FINITE'));self.assertEqual(calls,[])
        from . import epoch as E,controller as N,fixture_cpu as F
        from pubchem_c_metadata_recovery_v4 import controller as R
        self.assertEqual(len(E.FILES)+len(E.QUEUE_FILES),10);self.assertEqual(F.PARAMETERS['methods'],3)
        for name in ('close_new','account_row','materialize_one','actual_imports','data_locator','meta','pin','available_controller_lock'):
            self.assertIs(getattr(N,name),getattr(R,name))
        self.assertIs(N.S,R.S);self.assertIs(N.V,R.V);self.assertIs(N.A,R.A)

if __name__=='__main__':unittest.main()