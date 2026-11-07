"""Exactly three new pure/synthetic CPU boundaries; no scientific DATA."""
import math,struct,tempfile,unittest
from pathlib import Path
from . import contract as C,io as I,bindings as B,loss as L

class Boundaries(unittest.TestCase):
    def test_target_local_scale_and_raw_mean_of_norm_not_norm_of_mean(self):
        from . import contract as C
        old,old_io=C.prefix_adapter({'scope_key':'pm7_precache_day_v1','execution_argv':['py','-B','-m','workflows.data_v1_final.conformers.pm7_precache_day_v1.run']})
        new,new_io=C.prefix_adapter({'scope_key':'pm7_precache_hof_resume_day_v1','execution_argv':['py','-B','-m','workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1.run']})
        self.assertNotEqual(old.MODULE,new.MODULE)
        self.assertEqual(old_io.DAY_LEDGER,new_io.DAY_LEDGER)
        with self.assertRaises(ValueError):C.prefix_adapter({'scope_key':old.KEY,'execution_argv':['py','-B','-m',new.MODULE]})
        # This deliberately bad legacy alias is not the authoritative label
        # common module. Actual runtime and inverse use this same loader too.
        import sys,types
        from . import originals
        names=('common','calibration','support','build_registry','reduce');saved={name:sys.modules.get(name) for name in names}
        poison={name:types.ModuleType('synthetic_wrong_'+name) for name in names};path_before=list(sys.path)
        try:
            for name,value in poison.items():sys.modules[name]=value
            registry,reducer,series,compact,masks=originals.objects()
            from workflows.data_v1_final.labels import common as actual_common
            from workflows.data_v1_final.labels.streaming_v1 import calibration as actual_calibration,support as actual_support
            self.assertIs(registry.D20_NAMES,actual_common.D20_NAMES);self.assertEqual(len(registry.D20_NAMES),20)
            self.assertIs(registry.read_json,actual_common.read_json);self.assertIs(reducer.merge_qr,actual_calibration.merge_qr)
            self.assertIs(reducer.merge_qr,B.merge_qr);self.assertEqual(registry.family_for('D','values.HeavyAtomCount','molecule'),'size')
            self.assertIs(reducer.path_list,actual_support.path_list);self.assertIs(series.views,B.views)
            self.assertTrue(callable(reducer.rho_external));self.assertIs(originals.objects()[1],reducer)
            self.assertTrue(all(sys.modules[name]is value for name,value in poison.items()));self.assertEqual(sys.path,path_before)
        finally:
            for name,value in saved.items():
                if value is None:sys.modules.pop(name,None)
                else:sys.modules[name]=value
        pop={'path':'/synthetic/population.json','bytes':1,'sha256':'a'*64}
        args=dict(population_reference=pop,observed_population_reference=pop,statistic_reference=pop,series_key='physical/674/synthetic/frobenius_norm')
        for value in (None,0.,float('nan'),float('inf'),-1.):
            recipe=L.scale_recipe(value,**args)
            self.assertEqual(recipe['status'],'LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE')
            self.assertIsNone(recipe['candidate_scale']);self.assertFalse(recipe['actual_training_loss_enabled'])
            self.assertTrue(recipe['data_and_component_masks_preserved'])
        recipe=L.scale_recipe(2.,**args);joint=B.JointMoments(6);rawF=B.JointMoments(1)
        rows=[[3.,0.,0.,0.,0.,0.],[-3.,0.,0.,0.,0.,0.]]
        joint.add(rows)
        for row in rows:rawF.add([[math.sqrt(sum(w*x*x for w,x in zip(L.WEIGHTS,row)))]])
        q=B.combine_joint([joint.state()]);f=B.combine_joint([rawF.state()]);report=L.mean_F_report(f,recipe)
        self.assertEqual(q['mean_vector'],[0.]*6);self.assertEqual(report['raw_complete6_TRAIN_F_mean'],3.)
        self.assertEqual(report['mean_F_over_bound_s'],1.5)
        self.assertFalse(report['norm_of_component_mean_used_as_mean_F']);self.assertFalse(report['winsorized_mean_used_as_raw_mean'])

    def test_actual_child_unknown_or_duplicate_mass_remains_hold(self):
        C.closed_children(12,12,0,12)
        for values in ((12,11,0,11),(12,12,1,11),(12,13,0,13),(12,12,0,11),(True,1,0,1)):
            with self.assertRaises(ValueError):C.closed_children(*values)
        from workflows.data_v1_final.labels.common_train_normalization_day_v1.authority import eligible
        parent=('m','pm7','native');child=('m','pm7','realChild')
        self.assertFalse(eligible('TRAIN',True,child,parent,{parent})[0])
        self.assertFalse(eligible('VAL',True,parent,None,set())[0])
        self.assertTrue(eligible('TRAIN',True,('m','uff_sprime','0'),None,{parent})[0])
        from workflows.data_v1_final.export.d5_inputs_builder_v1.geometry import child_identity
        base={'geometry_source':'pm7','geometry_id':'native'}
        a=child_identity(base,'original-record','task','actual-occurrence:1','a'*64)
        b=child_identity(base,'original-record','task','actual-occurrence:2','a'*64)
        self.assertNotEqual(a,b)
        with self.assertRaises(ValueError):child_identity(base,'original-record','task','actual-occurrence:1',None)

    def test_arrow_F64_reopen_and_remaining_future_credited_only_once(self):
        import pyarrow as pa,pyarrow.parquet as pq
        saved=I.ALLOWED,I.ORIGINS,I.ROOT,I.CAP
        try:
            with tempfile.TemporaryDirectory(prefix='dv1_existing_sprime_source3_') as name:
                root=Path(name);I.configure({'source_references':[],'data_references':[],'cache_transitive_output_origins':[],
                    'output_directory':str(root),'whole_output_cap_bytes':128<<20})
                schema=pa.schema([('record',pa.string()),('coordinates',pa.list_(pa.float64())),('mask',pa.list_(pa.bool_()))])
                values=[{'record':'opaque','coordinates':[-0.,None,1.0000000000000002],'mask':[True,False,True]}]
                ref=I.write_parquet(root/'geometry.parquet',iter(values),schema)
                got=pq.read_table(I.require(ref)).to_pylist()[0]
                self.assertEqual(struct.pack('<d',got['coordinates'][0]),struct.pack('<d',-0.))
                self.assertIsNone(got['coordinates'][1]);self.assertEqual(got['mask'],values[0]['mask'])
                self.assertEqual(struct.pack('<d',got['coordinates'][2]),struct.pack('<d',values[0]['coordinates'][2]))
                with self.assertRaises(ValueError):I.require(dict(ref,sha256='0'*64))
            self.assertEqual(C.remaining_future(1000,600,0),1000)
            self.assertEqual(C.remaining_future(1000,600,250),750)
            self.assertEqual(C.remaining_future(1000,600,900),400)
            with self.assertRaises(ValueError):C.remaining_future(1000,True,0)
            with self.assertRaises(ValueError):C.remaining_future(500,600,0)
            # Resource-only R2: the Root net total already deducted an initial
            # external allocation. Restore it until a later original quota
            # covers a matching real inventory; never rewrite free_bytes.
            initial={'observed_unix_seconds':10.,'allocated_bytes':140,'size':130,'inode':7,'uid':1278}
            current=dict(initial,observed_unix_seconds=20.,allocated_bytes=160,size=150)
            self.assertEqual(I.covered_external_credit([initial],9.,current,336),0)
            self.assertEqual(I.covered_external_credit([initial],11.,current,336),140)
            self.assertEqual(I.covered_external_credit([initial,current],19.,current,336),140)
            self.assertEqual(I.covered_external_credit([initial,current],21.,current,336),160)
            self.assertEqual(I.covered_external_credit([initial],21.,None,336),0)
            self.assertEqual(I.covered_external_credit([initial],21.,dict(current,inode=8),336),0)
            self.assertEqual(I.covered_external_credit([initial],21.,dict(current,allocated_bytes=100),336),0)
            retained=I.retain_external_samples([initial,*[dict(current,observed_unix_seconds=30.+k) for k in range(20)]],11.)
            self.assertIn(initial,retained);self.assertLessEqual(len(retained),8)
            for bad in (float('nan'),float('inf'),True,-1.):
                with self.assertRaises(ValueError):I.covered_external_credit([initial],bad,current,336)
            self.assertEqual(C.remaining_future(900+140-160,600,200),680)
            spec={'path':I.EXTERNAL_CREDIT_PATH,'cap_bytes':336<<30,'uid':1278,'device':2049,'inode':7,
                'initial_credited_allocated_bytes':140,'device_identity_is_endpoint_local_not_compared_across_login_and_NFS':True,
                'same_storage_as_validated_provider_marker':True,'initial_observation_reference':{'path':'/synthetic/resource.json','bytes':1,'sha256':'a'*64}}
            I.external_source_shape(spec)
            for bad in (dict(spec,path='/another/not_registered.sqlite'),dict(spec,uid=0),dict(spec,cap_bytes=True),dict(spec,inode=False)):
                with self.assertRaises(ValueError):I.external_source_shape(bad)
            resource={'schema':'ROOT_ACTIVE_OUTPUT_ALLOCATED_BYTES_METADATA_OBSERVATION_V1','observed_unix_seconds':10.,
                'database_bodies_read_or_hashed':False,'scientific_adoption_or_C0_claimed':False,
                'files':[{'path':I.EXTERNAL_CREDIT_PATH,'registered_parent':'labels4524729','device':2049,'inode':7,'uid':1278,
                    'size':130,'allocated_bytes':140,'allocated_bytes_after_quota':150,'source_database_body_not_read':True,'mutable_not_scientific_adoption':True}]}
            seed=I.initial_external_inventory(spec,resource);self.assertEqual(seed['allocated_bytes'],140);self.assertEqual(seed['high_water_allocated_bytes'],150)
            with self.assertRaises(ValueError):I.initial_external_inventory(spec,dict(resource,scientific_adoption_or_C0_claimed=True))
            with tempfile.TemporaryDirectory(prefix='dv1_external_metadata_only_') as name:
                path=Path(name)/'synthetic.bin';path.write_bytes(b'x'*8192)
                info=path.lstat();expected={'uid':info.st_uid,'inode':info.st_ino,'cap_bytes':336<<30}
                before={'allocated_bytes':info.st_blocks*512,'size':info.st_size}
                observed=I.external_metadata_inventory(path,expected,info.st_dev,before)
                self.assertFalse(observed['body_opened_or_hashed']);self.assertEqual(observed['inode'],info.st_ino)
                with self.assertRaises(ValueError):I.external_metadata_inventory(path,dict(expected,inode=info.st_ino+1),info.st_dev,before)
                with self.assertRaises(ValueError):I.external_metadata_inventory(path,expected,info.st_dev,dict(before,allocated_bytes=before['allocated_bytes']+512))
                with self.assertRaises(ValueError):I.external_metadata_inventory(path,expected,info.st_dev,dict(before,size=before['size']+1))
                path.unlink()
                with self.assertRaises(FileNotFoundError):I.external_metadata_inventory(path,expected,info.st_dev,before)
        finally:I.ALLOWED,I.ORIGINS,I.ROOT,I.CAP=saved

if __name__=='__main__':unittest.main()
