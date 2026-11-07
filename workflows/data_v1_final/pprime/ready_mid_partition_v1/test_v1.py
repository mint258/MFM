"""Exactly3 same-Parent synthetic boundaries; no native or original DATA."""
import json,pathlib,tempfile,unittest
from . import contract as C,planner as P
from workflows.data_v1_final.pprime.strict_numerics15_qa_v1.io import Store
WORKSPACE=None
class Boundaries(unittest.TestCase):
    def test_exact_original_availability_SQL_ROUTINE_big_pending_and_chosen(self):
        import duckdb,pyarrow as pa
        db=duckdb.connect(':memory:')
        try:
            ids=['a','big','v','pending','single','full']
            db.register('per',pa.table({'molecule_id':ids,'split_role':['TRAIN','TRAIN','FULL','TRAIN','TRAIN','FULL'],
              'S_conformers':[2,2,2,3,1,2],'Sprime_conformers':[2,2,2,2,2,2]}))
            db.register('mi',pa.table({'molecule_id':ids,'file_group':[0]*6,'max_heavy_atoms':[10,80,10,10,10,10],'max_total_atoms':[20,90,20,20,20,20]}))
            db.register('val',pa.table({'molecule_id':['v']}));db.execute(P.availability_sql())
            self.assertEqual(db.execute('SELECT molecule_id,effective_role FROM eligible ORDER BY molecule_id').fetchall(),[('a','TRAIN'),('big','TRAIN'),('v','VAL')])
            self.assertEqual(db.execute("SELECT size_stratum FROM eligible WHERE molecule_id='big'").fetchone()[0],'above_75')
            self.assertEqual(db.execute(P.pending_sql()).fetchone()[0],2)
            db.register('pilot_mids',pa.table({'molecule_id':['a']}));db.register('consumed_mid_ids',pa.table({'molecule_id':pa.array([],type=pa.string())}))
            db.execute(P.P.CHOSEN_SQL);self.assertEqual(db.execute('SELECT molecule_id FROM chosen ORDER BY molecule_id').fetchall(),[('big',),('v',)])
            self.assertIn(P.availability_sql(),P.P.build.__code__.co_consts)
        finally:db.close()
    def test_balanced_disjoint_complete_roles_and_real_closed_JSONL_IO(self):
        from . import run as Entry
        root=C.ROOT/'artifacts/pprime_ready_mid_partition_v1/synthetic_route'
        plan={'partition_id':'synthetic_partition','output_directory':str(root)};proof={'job_id':'9900003'}
        binding={'resource_evidence_output':str(root)+'_resource_observation','memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20}
        before=dict(binding);routed=Entry.observer_binding(plan,proof,root,binding)
        self.assertEqual(routed['resource_evidence_output'],str(C.ROOT/'artifacts/labels/source_status_v1/_pprime_partition_resource/synthetic_partition_j9900003'))
        self.assertEqual(binding,before)
        self.assertEqual({k:v for k,v in routed.items()if k!='resource_evidence_output'},
          {k:v for k,v in binding.items()if k!='resource_evidence_output'})
        with self.assertRaises(ValueError):Entry.observer_binding(dict(plan,partition_id='../outside'),proof,root,binding)
        with self.assertRaises(ValueError):Entry.observer_binding(plan,proof,root,dict(binding,resource_evidence_output='/other/root'))
        with self.assertRaises(ValueError):Entry.observer_binding(plan,{'job_id':'01'},root,binding)
        constructor=Entry.observer_constructor(plan,proof,root)
        self.assertIs(constructor.__code__,C.Resource.Budget.__init__.__code__)
        self.assertIsNot(constructor.__globals__,C.Resource.Budget.__init__.__globals__)
        base=C.Resource.B.Budget.__init__;old_R=base.__globals__['R']
        private=constructor.__globals__['private_io_function'](base,lambda path:0)
        self.assertIs(private.__code__,base.__code__);self.assertIs(base.__globals__['R'],old_R)
        self.assertIsInstance(private.__globals__['R'],Entry.ObserverMetadataRoute)
        def row(i):return {'molecule_id':'synthetic_%02d'%i,'effective_role':'VAL'if i==0 else'TRAIN','source_role':'ROUTINE'if i==0 else'TRAIN',
          'S_conformers':2,'Sprime_conformers':3,'global_rank':i}
        rows=[row(i)for i in range(14)];shards=P.balance(rows[2:],5)
        self.assertLessEqual(max(map(len,shards))-min(map(len,shards)),1)
        qa=P.membership_qa(rows,rows[:1],rows[1:2],shards)
        self.assertTrue(qa['pairwise_disjoint']);self.assertTrue(qa['union_covers_original_ready_MID_universe']);self.assertFalse(qa['physical_conformer_IDs_verified'])
        with self.assertRaises(ValueError):P.membership_qa(rows,rows[:1],rows[:2],shards)
        with self.assertRaises(ValueError):P.membership_qa(rows,rows[:1],rows[1:2],shards[:-1])
        with self.assertRaises(ValueError):P.balance([rows[0]]*50001,1)
        with self.assertRaises(ValueError):P.balance(rows,True)
        self.assertEqual(P.balance([],38),[])
        class Budget:
            def check(self,*args,**kwargs):pass
        with tempfile.TemporaryDirectory(prefix='planner_io_',dir=WORKSPACE)as folder:
            root=pathlib.Path(folder);store=Store(root,8<<20);ref=P.lines(store,root/'assigned.jsonl',rows,budget=Budget())
            body=P.Body(ref,Budget())
            try:
                actual=[json.loads(line)for line in body.stream];body.check()
                self.assertEqual(actual,rows);self.assertEqual(set(actual[0]),set(C.BODY_FIELDS))
            finally:body.close()
    def test_original_consumed_reader_byte_snapshot_protocol_and_physical_ids(self):
        class Budget:
            def check(self,*args,**kwargs):pass
        protocol={'path':'/synthetic/protocol.json','bytes':1,'sha256':'a'*64}
        with tempfile.TemporaryDirectory(prefix='planner_once_',dir=WORKSPACE)as folder:
            root=pathlib.Path(folder);ledger=root/'physical_records_v1';ledger.mkdir();store=Store(root,8<<20)
            specs=[('m1',0,'a'),('m1',1,'a'),('m2',0,'a'),('m3',0,'b'),('m3',1,'b')]
            for i,(mid,idx,sha)in enumerate(specs):
                key='%064x'%i;store.json(ledger/(key+'.json'),{'record_once_key':key,'record_id':'pprime:'+mid+':'+str(idx),
                  'original_protocol_reference':dict(protocol,sha256=sha*64)})
            frozen=P.snapshot_census_function(root)
            self.assertIs(frozen.__code__,P.P.consumed_mid_census.__code__)
            self.assertIsNot(frozen.__globals__,P.P.consumed_mid_census.__globals__)
            self.assertEqual(frozen({'original_protocol_reference':protocol},Budget()),{'m1'})
            self.assertEqual(P.P.claimed_identity('pprime:MID:with:colon:13'),('MID:with:colon',13))
            with self.assertRaises(ValueError):P.P.claimed_identity('pprime:x:01')
