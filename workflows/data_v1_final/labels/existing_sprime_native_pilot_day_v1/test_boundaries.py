"""Exactly three native-source boundaries, plus the original3 in one Parent."""
import copy,json,unittest
from . import contract as C,geometry as G

class Boundaries(unittest.TestCase):
    def test_scope_and_original_source_objects_have_no_cache_or_D7_dependency(self):
        from . import run
        from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import run as old
        p={'node':'compute-0-2','output_directory':'synthetic-not-an-actual-plan','whole_output_cap_bytes':32<<30,
          'pilot_input_review_reference':{},'projection_origin_review_reference':{},'base_cache_plan_reference':{},
          'hof_closed_prefix_reuse_review_reference':{},'pilot_priority_review_reference':{},'field_scope':{}}
        scope=C.scope(p);self.assertFalse(scope['energy_diversity_HOF_RMSD_computed']);self.assertNotIn('pm7_prefix_review_reference',scope)
        self.assertEqual(scope['geometry_orders'],['fixed_random']);self.assertEqual(scope['original_TSQR_chunk'],256)
        self.assertIs(run.T,old.T);self.assertIs(run.V,G.COVERAGE);self.assertIs(run.ORIGINAL_COVERAGE,old.V);self.assertIs(run.E,old.E);self.assertIs(run.L,old.L)
        self.assertIs(G.metadata_children,G.OLD.metadata_children);self.assertIs(G.P.checked_uff,G.P.__dict__['checked_uff'])
        self.assertNotEqual(C.MODULE,old.C.MODULE)
        def forbidden(*args):raise AssertionError('DISTANCE_NOT_ALLOWED')
        rows=[{'conformer_id':i,'energy':None}for i in (8,2,1)]
        value=G.Cache.geometry_orders(rows,forbidden,'synthetic','uff_sprime')
        self.assertEqual(len(value['fixed_random']),3);self.assertIsNone(value['energy']);self.assertIsNone(value['diversity'])
        before={key:{'path':'/synthetic/old/'+key,'bytes':i+1,'sha256':str(i+1)*64}for i,key in enumerate(G.AUTHORITY_KEYS)}
        current={key:dict(ref,path='/synthetic/current/'+key)for key,ref in before.items()}
        original=copy.deepcopy(before);view=G.normalize_config_authorities(before,current)
        self.assertEqual(view,current);self.assertEqual(before,original)
        for key in G.AUTHORITY_KEYS:
            for changed in ('bytes','sha256'):
                bad=copy.deepcopy(before);bad[key][changed]=999 if changed=='bytes' else 'f'*64
                with self.subTest(key=key,changed=changed),self.assertRaises(ValueError):G.normalize_config_authorities(bad,current)
        config={'path':'/synthetic/accepted-config.json','bytes':1,'sha256':'a'*64}
        class OriginalIO:
            ALLOWED={config['path']:config}
            def load_data(self,ref,maximum):return before
        io=OriginalIO();proxy=G.AcceptedConfigIO(current,{config['path']:config},io)
        self.assertEqual(proxy.load_data(config),current)
        other=dict(config,path='/synthetic/not-an-accepted-config.json')
        self.assertIs(proxy.load_data(other),before)
        io.ALLOWED={}
        with self.assertRaises(ValueError):proxy.load_data(config)
        function=G.coverage_function(current,{})
        self.assertIs(function.__code__,old.V.build.__code__)
        self.assertTrue(all(function.__globals__[k]is old.V.build.__globals__[k]for k in old.V.build.__globals__ if k!='I'))

    def test_schema_only_header_preserves_units_and_never_exports_numeric_or_MID(self):
        fields=[]
        for i in range(146):
            fields.append({'field_id':i,'field_key':'f'+str(i),'registry_id':i,'task':'synthetic','group':'P','level':'molecule',
              'source_path':'value.synthetic','component':None,'unit':'exact source spelling Å/e','source_unit':None,'shape':['N',3],
              'source_semantic_layout':{'axes':['atom','xyz']},'status':'enabled','observed_audit':{'secret_MID':'FORBIDDEN','mean':12345}})
        registry={'fields':[dict(f)for f in fields]};rows=G.field_schema_rows(fields,registry)
        self.assertEqual(len(rows),146);text=json.dumps(rows,ensure_ascii=False)
        self.assertNotIn('FORBIDDEN',text);self.assertNotIn('observed_audit',text);self.assertNotIn('12345',text)
        self.assertEqual(rows[0]['unit'],'exact source spelling Å/e');self.assertIsNone(rows[0]['source_unit'])
        self.assertEqual(set(rows[0]),{'field_id','field_key','registry_id','task','group','level','source_path','component','unit','source_unit','shape','layout'})
        bad=copy.deepcopy(registry);bad['fields'][3]['source_unit']='invented'
        with self.assertRaises(ValueError):G.field_schema_rows(fields,bad)
        with self.assertRaises(ValueError):G.field_schema_rows(fields[:-1],registry)

    def test_whole_statistics_inverse_and_source_head_provenance(self):
        from . import source_inverse
        proof=source_inverse.proof();self.assertFalse(proof['old_scientific_globals_patched'])
        self.assertTrue(proof['two_numeric_replays_required']);self.assertEqual(proof['logical_groups'],171)
        self.assertEqual(C.KEY,'existing_sprime_native_pilot_day_v1')
        self.assertEqual(len(C.FILES),8)
        # Real original directory census, with deterministic transient removal
        # injected only in this synthetic caller; no original globals are patched.
        import pathlib,tempfile
        events=[];calls=[]
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);partial=root/'synthetic.parquet.partial';partial.write_bytes(b'abc')
            def transient(path):
                calls.append(1)
                if len(calls)==1:
                    partial.unlink();partial.lstat()
                return G.I.unique_bytes(path)
            observed=G.retry_whole_census(transient,root,events.append)
            self.assertEqual(observed,G.I.unique_bytes(root));self.assertGreater(observed,0)
            self.assertEqual(len(calls),2);self.assertEqual([e['status']for e in events],
              ['WHOLE_ORIGINAL_CENSUS_FILE_NOT_FOUND','WHOLE_ORIGINAL_CENSUS_SUCCEEDED'])
            self.assertFalse(events[0]['missing_bytes_assumed_zero'])
            attempts=[];failed=[]
            def absent(path):attempts.append(1);return (root/'permanently-missing').lstat()
            with self.assertRaises(FileNotFoundError):G.retry_whole_census(absent,root,failed.append)
            self.assertEqual(len(attempts),3);self.assertEqual(len(failed),3)
            refused=[]
            def invalid(path):refused.append(1);raise ValueError('OUTPUT_OWNER_OR_TYPE')
            with self.assertRaises(ValueError):G.retry_whole_census(invalid,root,events.append)
            self.assertEqual(len(refused),1)
        # The immutable-ALLOWED lstat remains in the original _observe code;
        # retry is bound only to unique_bytes, never to Path/lstat/ALLOWED.
        for name,changes in (('_observe',{'unique_bytes','R'}),('check',{'unique_bytes'})):
            before=getattr(G.I.Budget,name);after=G.budget_function(name,G.I.unique_bytes)
            self.assertIs(before.__code__,after.__code__)
            self.assertTrue(all(after.__globals__[k]is before.__globals__[k]for k in before.__globals__ if k not in changes))
            self.assertIs(after.__globals__['ALLOWED'],G.I.ALLOWED)
        class Stop:
            def mark_stop(self,reason,observation):return reason,observation
        try:raise FileNotFoundError(2,'synthetic missing','/synthetic/immutable.parquet')
        except FileNotFoundError:
            reason,detail=G.ResourceStopEvidence(Stop()).mark_stop('COMMON_TRAIN_RESOURCE_OBSERVATION_UNKNOWN',{'error':'synthetic'})
        self.assertEqual(detail['missing_filename'],'/synthetic/immutable.parquet')
        self.assertIn('FileNotFoundError',detail['traceback']);self.assertFalse(detail['historical177_cause_inferred'])
        from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import bindings as B
        self.assertEqual(B.verify()['TSQR_chunk'],256)

if __name__=='__main__':unittest.main()
