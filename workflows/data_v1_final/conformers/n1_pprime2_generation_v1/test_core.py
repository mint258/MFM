"""Pure N1 boundary fixtures; no RDKit, torch, source LMDB or real optimization."""
import copy,json,pathlib,unittest
from types import SimpleNamespace
from workflows.data_v1_final.conformers.n1_pprime2_generation_v1 import contract as C,core

HERE=pathlib.Path(__file__).absolute().parent
CATALOG=json.loads((HERE/'frozen_sources.json').read_text())
SELECTION=C.module_from_pin('_n1_fixture_frozen_selection',CATALOG['references']['selection'])


class N1GenerationBoundaries(unittest.TestCase):
    mid='synthetic-n1'

    def baseline(self):
        return {'origin':'accepted_sprime','candidate_key':'existing:000000','candidate_id':None,
            'seed':1,'energy':0.,'x':0.,'geometry_sha256':'a'*64}

    def event(self,x=.1,cid=0,energy=1.,sha=None):
        return {'origin':'data_v1_n1_pprime2','candidate_key':f'n1p2:{C.proposed_seed(self.mid)}:{cid:06d}',
            'candidate_id':cid,'seed':C.proposed_seed(self.mid),'energy':energy,'x':x,
            'optimizer_called':True,'optimization_finished':True,'optimizer_code':0,
            'stereo_valid':True,'finite':True,'geometry_sha256':sha or format(cid+1,'064x')}

    def distance(self,left,right):return abs(left['x']-right['x'])

    def select(self,rows):return C.select_real_second(self.mid,self.baseline(),rows,self.distance,SELECTION)

    def ref(self,name):return {'path':'/synthetic/'+name,'bytes':1,'sha256':'0'*64}

    def task(self):
        baseline={'molecule_id':self.mid,'status':'SUCCESS','converged':True,'sprime_conf_idx':0,
            'seed':1,'coordinates':[[0.,0.,0.]],'uff_energy_kcal_mol':0.}
        return {'schema':'N1_PPRIME2_PREPARED_TASK_V1','task_key':C.task_key(self.mid),
            'meta':{'molecule_id':self.mid,'source_N':1,'PM7_source_count':1,'accepted_baseline_count':1,
                'UFF_desired_count':2,'final_common_member':True,'effective_role':'VAL','Sprime_status':'SUCCESS'},
            'records':[{'molecule_id':self.mid,'record_id':'pm7-only-source'}],
            'existing_conformers':[baseline],'baseline_row_sha256':C.sha_value(baseline),
            'baseline_geometry_id':'accepted-existing-uff-only',
            'authority_references':{name:self.ref(name) for name in ('frozen_common','source_pointer_manifest','accepted_baseline_evidence','roles_manifest')}}

    def test_original_seed_domain_known_value_and_separate_once_identity(self):
        # Independent PowerShell SHA256 metadata calculation supplied this value.
        self.assertEqual(C.proposed_seed(self.mid),1032214668)
        self.assertTrue(1<=C.proposed_seed(self.mid)<=0x7fffffff)
        self.assertEqual((C.SOURCE_N,C.UFF_DESIRED,C.CANDIDATES,C.MAX_CANDIDATES),(1,2,10,300))
        self.assertNotEqual(C.task_key(self.mid),C.task_key(self.mid+'2'))
        self.assertEqual(C.SCOPE['pilot_molecules'],32);self.assertFalse(C.SCOPE['automatic_retry'])

    def test_source_pointer_count_is_one_even_when_uff_target_is_two(self):
        task=self.task();common=task['authority_references']['frozen_common']
        self.assertEqual(C.validate_task(task,common)[3],C.proposed_seed(self.mid))
        for change in ('two_pointers','source_N2','UFF_target1','two_baselines'):
            with self.subTest(change=change):
                altered=copy.deepcopy(task)
                if change=='two_pointers':altered['records']*=2
                if change=='source_N2':altered['meta']['source_N']=2
                if change=='UFF_target1':altered['meta']['UFF_desired_count']=1
                if change=='two_baselines':altered['existing_conformers']*=2
                with self.assertRaises(ValueError):C.validate_task(altered,common)

    def test_actual_common_roles_and_original_row_hash_are_required(self):
        task=self.task();common=task['authority_references']['frozen_common']
        for change in ('FULL','not_common','unsupported','different_common','changed_old_coordinate'):
            with self.subTest(change=change):
                altered=copy.deepcopy(task);bound=common
                if change=='FULL':altered['meta']['effective_role']='FULL'
                if change=='not_common':altered['meta']['final_common_member']=False
                if change=='unsupported':altered['meta']['Sprime_status']='UFF_UNSUPPORTED'
                if change=='different_common':bound=self.ref('other_frozen_common')
                if change=='changed_old_coordinate':altered['existing_conformers'][0]['coordinates'][0][0]=1.
                with self.assertRaises(ValueError):C.validate_task(altered,bound)

    def test_distant_actual_candidate_precedes_lower_energy_below_threshold(self):
        old=self.baseline();events=[self.event(.1,0,0.),self.event(.5,1,10.)]
        snapshot=copy.deepcopy((old,events));result=C.select_real_second(self.mid,old,events,self.distance,SELECTION)
        self.assertEqual(result['second']['candidate_id'],1)
        self.assertFalse(result['second']['below_dedup_threshold'])
        self.assertEqual((result['selected_unique_at_0p5_A'],result['Pprime_actual_records']),(2,2))
        self.assertEqual((old,events),snapshot)

    def test_fallback_keeps_two_real_records_but_only_one_0p5_unique_geometry(self):
        result=self.select([self.event(.1,0,0.),self.event(.3,1,10.)])
        self.assertEqual(result['second']['candidate_id'],1)
        self.assertTrue(result['second']['below_dedup_threshold'])
        self.assertEqual(result['selected_unique_at_0p5_A'],1)
        self.assertEqual(result['candidate_pool_unique_at_0p5_A'],1)
        self.assertEqual(result['Pprime_actual_records'],2)

    def test_same_SHA_cannot_manufacture_second_row_and_rigid_unresolved_stays_pending(self):
        result=self.select([self.event(0.,0,0.,self.baseline()['geometry_sha256'])])
        self.assertIsNone(result['second']);self.assertEqual(result['Pprime_actual_records'],1)
        self.assertEqual(result['status'],'PPRIME2_PENDING_NO_SECOND_REAL_GEOMETRY')
        self.assertEqual(result['identity_or_quality_exclusions'][0]['reason'],'GEOMETRY_SHA_ALREADY_PRESENT')
        self.assertIsNone(self.select([])['second'])
        result=self.select([self.event(.6,0,2.),self.event(.6,1,1.,format(1,'064x'))])
        self.assertEqual(result['eligible_geometry_candidates'],1)
        self.assertEqual(result['second']['candidate_id'],1)

    def test_unconverged_or_stereo_nonfinite_events_never_supply_second(self):
        for field,value in (('optimizer_code',1),('stereo_valid',False),('finite',False)):
            with self.subTest(field=field):
                event=self.event(.8);event[field]=value
                self.assertIsNone(self.select([event])['second'])
        for field,value in (('optimizer_called',False),('optimization_finished',False),
                ('seed',1),('origin','accepted_sprime')):
            with self.subTest(field=field):
                event=self.event(.8);event[field]=value
                with self.assertRaises(ValueError):self.select([event])
        with self.assertRaisesRegex(ValueError,'DUPLICATE_NATIVE_CANDIDATE_ID'):
            self.select([self.event(.7),self.event(.8)])
        with self.assertRaisesRegex(ValueError,'CANNOT_EXCEED10'):
            self.select([self.event(.7,index) for index in range(11)])

    def test_expanded_orders_keep_baseline_and_use_original_stable_source_order(self):
        old=self.baseline();second=self.select([self.event(.7)])['second'];snapshot=copy.deepcopy((old,second))
        orders=C.expanded_orders(self.mid,old,second,self.distance,SELECTION)
        ids=[0,f"n1p2:{second['seed']}:{second['candidate_id']}"]
        self.assertEqual(orders['fixed_random'],sorted(ids,key=lambda value:(SELECTION.stable_key(20261025,self.mid,'uff_sprime',value),str(value))))
        self.assertEqual(orders['energy'],ids);self.assertEqual(orders['diversity'],ids)
        self.assertEqual((old,second),snapshot)
        with self.assertRaises(ValueError):C.expanded_orders(self.mid,old,dict(second,geometry_sha256=old['geometry_sha256']),self.distance,SELECTION)

    def test_pilot32_is_deterministic_and_short_roster_is_not_widened(self):
        rows=[{'meta':{'molecule_id':f'm{i:03d}'}} for i in range(35)]
        first=C.pilot32(rows,SELECTION);other=C.pilot32(list(reversed(rows)),SELECTION)
        self.assertEqual(first,other);self.assertEqual(len(first['tasks']),32)
        self.assertEqual(C.pilot32(rows[:31],SELECTION)['tasks'],[])
        with self.assertRaisesRegex(ValueError,'DUPLICATE_PILOT_MOLECULE'):C.pilot32(rows+[rows[0]],SELECTION)

    def test_only_zero_embedding_uses_same_seed_random_fallback_and_core_requires_admission(self):
        class FakeEmbedding:
            def __init__(self,responses):self.responses=list(responses);self.calls=[]
            def ETKDGv3(self):return SimpleNamespace()
            def EmbedMultipleConfs(self,mol,numConfs,params):
                self.calls.append({'requested':numConfs,**vars(params)})
                response=self.responses.pop(0)
                if isinstance(response,Exception):raise response
                return response
        engine=FakeEmbedding([[],list(range(10))]);attempts=[]
        self.assertEqual(core._embedding(object(),engine,10,C.proposed_seed(self.mid),attempts),list(range(10)))
        self.assertEqual([row['requested'] for row in engine.calls],[10,10])
        self.assertEqual([row['useRandomCoords'] for row in engine.calls],[False,True])
        self.assertTrue(all(row['randomSeed']==1032214668 and row['maxIterations']==200 and row['numThreads']==1
            and row['enforceChirality'] and row['pruneRmsThresh']==-1. for row in engine.calls))
        partial=FakeEmbedding([[0]])
        self.assertEqual(core._embedding(object(),partial,10,C.proposed_seed(self.mid),[]),[0])
        self.assertEqual(len(partial.calls),1)
        engine=FakeEmbedding([RuntimeError('synthetic first failure'),[]]);attempts=[]
        with self.assertRaisesRegex(ValueError,'EMBED_FAILED'):core._embedding(object(),engine,10,C.proposed_seed(self.mid),attempts)
        self.assertEqual(len(engine.calls),2);self.assertIn('synthetic first failure',attempts[0]['traceback'])
        original=core.CTX
        try:
            core.CTX={}
            with self.assertRaisesRegex(ValueError,'FRESH_ADMITTED_WORKER'):core.process_task({})
        finally:core.CTX=original


if __name__=='__main__':unittest.main()
