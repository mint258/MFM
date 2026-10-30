"""Exactly3 synthetic methods; actual CPU Parent runs these before DATA."""
import concurrent.futures as cf,hashlib,inspect,json,pathlib,struct,unittest
from . import contract as C
from .run import I
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import prepare as P,publication as U,worker
WORKSPACE=None

class Boundaries(unittest.TestCase):
    def test_original_worker_and_assigned_domain(self):
        self.assertTrue(worker.inverse()['entire_original_worker_code'])
        rows=[{'molecule_id':'native:alpha','effective_role':'TRAIN','source_role':'TRAIN','S_conformers':2,'Sprime_conformers':3,'global_rank':40},
              {'molecule_id':'native:beta','effective_role':'VAL','source_role':'ROUTINE','S_conformers':2,'Sprime_conformers':2,'global_rank':912}]
        P.validate_assignment(rows,{'molecules':2},set());self.assertEqual([r['global_rank'] for r in rows],[40,912])
        for changed,excluded in (([rows[0],rows[0]],set()),(rows,{'native:alpha'}),([dict(rows[0],global_rank=True),rows[1]],set()),([dict(rows[0],S_conformers=1),rows[1]],set())):
            with self.assertRaises(ValueError):P.validate_assignment(changed,{'molecules':2},excluded)
        from workflows.data_v1_final.pprime.formal_packed_day_v1 import prepare as Before
        origin=C.meta(C.Q.pin(C.Before.HERE/'source_origin.json'));current=inspect.getsource(P.build).strip()+'\n'
        for edit in origin['prepare_build_inverse_replacements']:
            self.assertIn(edit['after'],current);current=current.replace(edit['after'],edit['before'])
        self.assertEqual(current,inspect.getsource(Before.build).strip()+'\n')
        normal=lambda s:'\n'.join(line.strip() for line in s.strip().splitlines())
        fragment=normal(origin['original_hash_numerical_fragment'])
        self.assertIn(fragment,normal(inspect.getsource(Before.build)))
        self.assertIn(fragment,normal(inspect.getsource(P.hash_one)))
        self.assertIs(P.geometry.adapt_native,Before.geometry.adapt_native)
        self.assertIs(I.Preparation.input_hashes,Before.I.Preparation.input_hashes)
        self.assertEqual(C.RAW_CAP,768<<20);self.assertEqual(C.RESULT_CAP,128<<20)
        self.assertEqual(I.Budget.SOFTWARE_WORKING_BUDGET_BYTES,64<<30)
        self.assertEqual(I.Budget.RSS_LIMIT_BYTES,56<<30)
        chain=I.Budget.__mro__;self.assertEqual(chain[chain.index(I.Resource.Budget)+1],I.Resource.Original.Budget)
        self.assertLess(chain.index(I.Preparation.Budget),chain.index(I.Resource.Budget))

    def test_global_known_bytes_concurrent_reserve_no_unknown_release(self):
        root=pathlib.Path(WORKSPACE)/'synthetic_cas';root.mkdir();pool=U.Pool.__new__(U.Pool)
        pool.root=root;pool.lock=root/'pool.lock';pool.state=root/'pool_state.json';pool.cap=32<<20;pool.kind='EXEC'
        pool.reference=C.Q.write_new(root/'authority.json',{'synthetic':True})
        def reserve(n):return pool.update(1<<20,'synthetic_%d'%n)
        with cf.ThreadPoolExecutor(max_workers=8) as ex:tokens=list(ex.map(reserve,range(32)))
        state=json.loads(pool.state.read_bytes());used=sum(t['reserved_bytes'] for t in state['tokens'].values())
        self.assertGreater(sum(t is not None for t in tokens),0);self.assertLessEqual(used,pool.cap-(16<<20))
        self.assertFalse(U.allocation(pool.cap-(16<<20),used,1<<20))
        key=next(iter(state['tokens']))
        identity=state['tokens'][key]['identity'];pool.update(0,identity,commit=key)
        after=json.loads(pool.state.read_bytes());self.assertEqual(used,sum(t['reserved_bytes'] for t in after['tokens'].values()))
        self.assertTrue(any(t['status']=='RESERVED_UNKNOWN_UNTIL_COMMITTED' for k,t in after['tokens'].items() if k!=key))

    def test_closed_stable_copy_F64_and_onsite_bytes_not_rewritten(self):
        root=pathlib.Path(WORKSPACE)/'synthetic_copy';root.mkdir();src=root/'original.bin'
        payload=struct.pack('<QQQQ',0,1<<63,0x7ff8000000000073,0x3ff0000000000000)+b'opaque_raw_and_F64\n'*(200000)
        src.write_bytes(payload);ref=I.pin(src,[root]);dst=root/'publication'/'original.bin';target=U.copy_ref(ref,dst)
        self.assertEqual((ref['bytes'],ref['sha256']),(target['bytes'],target['sha256']));self.assertEqual(dst.read_bytes(),payload)
        with self.assertRaises(ValueError):U.copy_ref(dict(ref,sha256='0'*64),root/'bad.bin')
        link=root/'alias';link.symlink_to(src.name)
        with self.assertRaises(ValueError):I.pin(link,[root])
        mapping=[{'origin_reference':ref,'target_reference':target}];self.assertEqual(U.relocated(ref,mapping),target)
        with self.assertRaises(ValueError):U.relocated(ref,mapping+mapping)
        self.assertEqual(struct.unpack('<QQQQ',dst.read_bytes()[:32]),(0,1<<63,0x7ff8000000000073,0x3ff0000000000000))
        from .resource_forecast import validate
        pointer={'schema':'ROOT_CURRENT_ALL_FUTURE_METADATA_POINTER_V1','total_future_reserved_bytes':123456789}
        review={'reviewer':'root','status':'APPROVED_EXACT_FORECAST_RETIREMENT_ONLY','total_future_reserved_bytes':123456789}
        self.assertEqual(validate(pointer,review),123456789)
        for changed in (dict(review,total_future_reserved_bytes=123456788),dict(review,reviewer='not-root')):
            with self.assertRaises(ValueError):validate(pointer,changed)
        with self.assertRaises(ValueError):validate(dict(pointer,total_future_reserved_bytes=True),review)
        # Same actual Parent: narrowly check new admission without any Native call.
        from . import authority as A,run as R
        f=R.private_function(R.Original.execution,C=C)
        self.assertIs(f.__code__,R.Original.execution.__code__);self.assertIs(f.__closure__,R.Original.execution.__closure__)
        self.assertTrue(all(f.__globals__[k]is R.Original.execution.__globals__[k]for k in f.__globals__ if k!='C'))
        self.assertIs(C.record_once_key,C.Original.record_once_key)
        init=R.private_function(R.OldIO.Budget.__init__,C=C)
        self.assertIs(init.__code__,R.OldIO.Budget.__init__.__code__)
        self.assertEqual(C.MODES,{'EXECUTE':'pprime_current_closed_component_parentstate_v3'})
        self.assertNotEqual(A.SCHEMA,'ROOT_ACCEPTED_PPRIME_SHARED_PAIRS_PREPARATION_V2')
        for state,code in (('RUNNING','0:0'),('COMPLETED','0:0'),('FAILED','1:0')):
            self.assertEqual(A.observed_parent_state(state,code),state)
        for state,code in (('UNKNOWN','0:0'),('COMPLETED','1:0'),('FAILED','unknown')):
            with self.assertRaises(ValueError):A.observed_parent_state(state,code)
        pair={'record_id':'pprime:synthetic:73'};task_names=list(C.O.TASKS)
        values=[{'task':t,'original_input_file_sha256':[{'name':'input.xyz','sha256':'a'*64}],
          'candidate_input_file_sha256':[{'name':'input.xyz','sha256':'a'*64}]}for t in task_names]
        hashes={'record_id':pair['record_id'],'original_pair_sha256':hashlib.sha256(C.O.canonical(pair)).hexdigest(),
          'geometry_sha256':'b'*64,'hashes':values};A.validate_hashes(pair,hashes,task_names)
        for bad in (dict(hashes,original_pair_sha256='0'*64),dict(hashes,hashes=values[:-1]),dict(hashes,geometry_sha256='bad')):
            with self.assertRaises(ValueError):A.validate_hashes(pair,bad,task_names)
