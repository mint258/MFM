"""Three new pure boundaries inside the same20-method CPU parent preflight."""
import pathlib,unittest
from . import metadata as M,io as I,run,pilot_prepare as P

class Boundaries(unittest.TestCase):
    def test_persistent_cursor_does_not_turn_unknown_into_full_or_skip_a_gap(self):
        metas=[{'molecule_id':str(n)} for n in range(4)]
        self.assertEqual(run.conservative_cursor(metas,[{'molecule_id':'0'},{'molecule_id':'2','state':'UNKNOWN'}]),1)
        self.assertEqual(run.conservative_cursor(metas,[{'molecule_id':str(n)} for n in range(4)]),4)
        for bad in ([{'molecule_id':'0'},{'molecule_id':'0'}],[{'molecule_id':'foreign'}]):
            with self.assertRaises(ValueError):run.conservative_cursor(metas,bad)
        p={'node':'compute-0-14','source_mapping_review_reference':{'path':'/synthetic/mapping','bytes':1,'sha256':'c'*64},
            'output_directory':str(M.BASE/'synthetic'),'base_cache_plan_reference':{'path':'/synthetic/base','bytes':1,'sha256':'a'*64},
            'all_known_cache_parent_review_reference':{'path':'/synthetic/inventory','bytes':1,'sha256':'b'*64}}
        scope=M.parameters(p);self.assertFalse(scope['full_cache_or_Common_or_D7_release']);self.assertFalse(scope['Common_or_Sprime_predicate'])
        self.assertTrue(scope['old32_permissions_not_rewritten']);self.assertTrue(scope['internal_shards_are_not_Slurm_jobs'])
        # Priority is a two-pass scheduling partition, never a replacement roster
        # or permission to skip the remainder after the 55k pilot is cached.
        descriptors=[{'molecules':3},{'molecules':2}]
        segments=P.segments(descriptors,{0:1,1:2})
        self.assertEqual([(s['descriptor_ordinal'],s['phase'],s['molecules']) for s in segments],
            [(0,'PILOT_PRIORITY',1),(1,'PILOT_PRIORITY',2),(0,'ORIGINAL_REMAINDER',2)])
        original=[{'molecule_id':str(n),'original_pm7_count':n+1} for n in range(3)]
        records={m['molecule_id']:[{'record_id':'native-'+m['molecule_id']}] for m in original}
        a,ar=P.select_phase(original,records,{'1'},'PILOT_PRIORITY');b,br=P.select_phase(original,records,{'1'},'ORIGINAL_REMAINDER')
        self.assertEqual([m['molecule_id'] for m in a],['1']);self.assertEqual([m['molecule_id'] for m in b],['0','2'])
        self.assertIs(a[0],original[1]);self.assertIs(ar['1'],records['1']);self.assertEqual(set(ar)|set(br),set(records));self.assertFalse(set(ar)&set(br))
        for bad in ({0:4},{2:1},{0:True}):
            with self.assertRaises(ValueError):P.segments(descriptors,bad)

    def test_unknown_uid_parent_or_source_fingerprint_never_becomes_new_work(self):
        source={'path':str(M.HERE/'run.py'),'bytes':1,'sha256':'a'*64};key='a'*64;root=str(M.BASE/'synthetic')
        origin={'job_id':'1','kind':'day','root':root,'request':{'node':'compute-0-14','source_references':[source]}}
        claim={'job_id':'1','uid':1278,'node':'compute-0-14','cache_key':key,'molecule_id':'synthetic','output_root':root,
            'source_fingerprint':I.PC.digest([source]),'resource_scope':M.KEY,'schema':'PM7_PRECACHE_DAY_CLAIM_V1'}
        task={'cache_key':key,'meta':{'molecule_id':'synthetic'}}
        self.assertIs(I.check_claim(task,claim,source,{'1':origin}),origin)
        with self.assertRaises(ValueError):I.check_claim(task,claim,source,{})
        for fields in ({'uid':1264},{'node':'compute-0-13'},{'output_root':'/wrong'},{'source_fingerprint':'wrong'},
            {'resource_scope':'pm7_population_cache_v1_batch'}):
            with self.assertRaises(ValueError):I.check_claim(task,dict(claim,**fields),source,{'1':origin})
        no_uid=dict(claim);no_uid.pop('uid')
        with self.assertRaises((KeyError,ValueError)):I.check_claim(task,no_uid,source,{'1':origin})
        rows=[{'molecule_id':m,'effective_role':r} for m,r in (('a','TRAIN'),('c','VAL'),('b','TRAIN'))]
        ranked=P.rank_members(rows,20261025)
        self.assertEqual(ranked,P.rank_members(list(reversed(rows)),20261025))
        order=P.ranking_module().rank_hash
        self.assertEqual(ranked['TRAIN'],sorted(['a','b'],key=lambda m:(order(20261025,'TRAIN',m),m)))
        with self.assertRaises(ValueError):P.rank_members(rows+[rows[0]],20261025)
        with self.assertRaises(ValueError):P.rank_members([{'molecule_id':'x','effective_role':'FULL'}],20261025)

    def test_unchanged_worker_compute_packet_and_native_order_boundaries(self):
        from workflows.data_v1_final.conformers.postprocess_day_v1 import worker as original
        from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import core
        from workflows.data_v1_final.conformers.pm7_multinode_compat32_v1 import compute as local_context
        self.assertIs(I.WORKER.initialize,original.initialize);self.assertIs(I.WORKER.one,original.one)
        self.assertIs(I.WORKER.pm7_compute,local_context.compute)
        self.assertIs(local_context.geometry_orders,core.geometry_orders);self.assertIs(local_context.unique_representatives,core.unique_representatives)
        source={'path':'/synthetic/formal','bytes':1,'sha256':'a'*64};hof=dict(source,path='/synthetic/hof')
        records=[{'record_id':'nativeB','record_payload_sha256':'b'*64,'molecule_id':'m'},
            {'record_id':'nativeA','record_payload_sha256':'c'*64,'molecule_id':'m'}]
        self.assertEqual(I.PC.task_key(source,hof,records),I.PC.task_key(source,hof,list(reversed(records))))
        self.assertNotEqual(I.PC.task_key(source,hof,records),I.PC.task_key(source,dict(hof,sha256='d'*64),records))
        self.assertEqual(I.B.software_bound(I.B.MAX_RECORDS+1,1)['status'],'PENDING_SELECTED_SOURCE_EXCEEDS_SOFTWARE_BOUND')
        from workflows.data_v1_final.conformers.postprocess_day_v1.math_bridge import membership,exclusion_gates
        row={'molecule_id':'n1','effective_role':'TRAIN','S_usable_conformers':1,'S_conformers':1,'records':1,
            'Sprime_status':'SUCCESS','merged_uff_count':1,'elements_atomic_numbers':[6]}
        result=membership(row);self.assertTrue(result['common_population']);self.assertTrue(result['pprime_two_conformers_pending'])
        unsupported=membership(dict(row,Sprime_status='UFF_UNSUPPORTED'));self.assertFalse(unsupported['common_population'])
        gate=exclusion_gates([dict(row,**result),dict(row,molecule_id='excluded',**unsupported)])
        self.assertFalse(gate['passed']);self.assertTrue(gate['overall_gt2_percent'])
        # Exercise the actual Arrow/SQL source-column join, not a separately
        # invented dict projection. These are synthetic in-memory inputs only.
        import duckdb,pyarrow as pa
        db=duckdb.connect()
        try:
            db.register('pilot_original_p',pa.Table.from_pylist([{'molecule_id':'n1','S_conformers':1,'S_usable_conformers':1,
                'Sprime_conformers':1,'Sprime_status':'SUCCESS','elements_atomic_numbers':[6,1],'heavy_atoms':1}]))
            db.register('pilot_original_roles',pa.Table.from_pylist([{'molecule_id':'n1','effective_role':'VAL','source_role':'ROUTINE',
                'records':1,'file_group':'synthetic-original-file-group','legacy_routine_molecule':True}]))
            joined=db.execute(P.JOIN_SQL).fetch_arrow_table().to_pylist()
            self.assertEqual(len(joined),1);self.assertEqual(joined[0]['effective_role'],'VAL')
            self.assertEqual(joined[0]['records'],1);self.assertEqual(joined[0]['Sprime_conformers'],joined[0]['merged_uff_count'])
            self.assertTrue(membership(joined[0])['common_population']);self.assertTrue(membership(joined[0])['pprime_two_conformers_pending'])
        finally:db.close()
if __name__=='__main__':unittest.main()
