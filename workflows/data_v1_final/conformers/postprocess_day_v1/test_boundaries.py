"""Six actual-CPU synthetic boundaries; no scientific DATA, mocks or native QM."""
import gzip,hashlib,json,pathlib,tempfile,unittest
from . import contract as C,closure,io as I,math_bridge as M,statistics as S

class Boundaries(unittest.TestCase):
    def test_packed_ticks_schema_preserves_original_bytes(self):
        v={'pid_start_ticks':'12345'};raw=C.canonical(v);self.assertEqual(closure.positive_ticks(v['pid_start_ticks']),12345);self.assertEqual(C.canonical(v),raw)
        for bad in (True,0,-1,'','01','1.0',None):
            with self.assertRaises(ValueError):closure.positive_ticks(bad)
        # True origin, not whichever packed parent happened to run last.
        origins={'1':{'root':'/synthetic/first64'},'2':{'root':'/synthetic/next64'}};key='a'*64
        packet={'formal_start':{'resource_scope':'sprime_packed_day_v1','job_id':'1','task_key':key},
            'source':{'path':'/synthetic/first64/packets/'+key+'.json.gz'}}
        self.assertEqual(closure.select_owner(packet,origins),'1')
        with self.assertRaises(ValueError):closure.select_owner(dict(packet,source={'path':'/synthetic/next64/packets/'+key+'.json.gz'}),origins)
        with self.assertRaises(ValueError):closure.select_owner(packet,{'2':origins['2']})
        self.assertIsNone(closure.select_owner({'formal_start':{'resource_scope':'original16'}},origins))
    def test_original_merge_sparse_id_and_se_thresholds(self):
        self.assertEqual(M.merge_counts(1,[{'origin':'data_v1_fill_10N','kernel_sprime_conf_idx':1,'seed':3,'candidate_id':0}],2),2)
        with self.assertRaises(ValueError):M.merge_counts(1,[{'origin':'data_v1_fill_10N','kernel_sprime_conf_idx':1,'seed':3,'candidate_id':0}],1)
        rows=M.append_generated([{'task_key':'a'*64,'seed':3,'candidate_id':0}],1,9);self.assertEqual(rows[0]['sprime_conf_idx'],10)
        rows=[{'effective_role':'TRAIN','common_population':i>=2,'elements_atomic_numbers':[6,34]} for i in range(100)]
        self.assertTrue(M.exclusion_gates(rows)['passed']);rows[2]['common_population']=False;self.assertFalse(M.exclusion_gates(rows)['passed'])
        rare=[{'effective_role':'TRAIN','common_population':i>0,'elements_atomic_numbers':[6,34] if i==0 else [6]} for i in range(1000)]
        self.assertTrue(M.exclusion_gates(rare)['passed']);rare[0]['elements_atomic_numbers']=[6,9];self.assertFalse(M.exclusion_gates(rare)['passed'])
    def test_same_numerical_percentile_and_spearman_objects(self):
        import numpy as np
        from scipy.stats import spearmanr
        x=np.array([np.nextafter(0.,1.),1.,-0.,2.,3.,3.,7.],dtype='<f8');expected={str(p):float(np.percentile(x,p,method='linear')) for p in (0,25,50,75,90,95,99,100)}
        self.assertEqual(S.linear_percentiles(x),expected)
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'real_f64.dat';x.tofile(path);mm=np.memmap(path,dtype='<f8',mode='r',shape=x.shape);self.assertEqual(S.linear_percentiles(mm),expected);del mm
        self.assertTrue(np.isfinite(spearmanr([1,2,2],[2,3,3]).statistic))
    def test_fixed_random_native_ids_and_full_0_5_boundary(self):
        rows=[{'conformer_id':str(k),'coordinates':[],'energy':float(k)} for k in range(3)];distance=lambda a,b:0.5 if a is not b else 0.
        order=M.geometry_orders(rows,distance,'synthetic','pm7');self.assertEqual(len(M.unique_representatives(rows,order['fixed_random'],distance)),3)
        below=lambda a,b:0.49999999999999994;self.assertEqual(len(M.unique_representatives(rows,order['fixed_random'],below)),1)
        self.assertEqual(set(order['energy']),{'0','1','2'})
    def test_exclusive_technical_claim_never_reopens_old_scope(self):
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'claim.json';ref=I.save(path,{'job_id':'64','scientific_once_or_UFF_or_QM':False})
            with self.assertRaises(FileExistsError):I.save(path,{'job_id':'different'})
            self.assertEqual(I.read(ref)['job_id'],'64')
            # Two batch headers are retained independently under concurrent
            # lookup. No shared mutable last-header pointer is passed to binding.
            from concurrent.futures import ThreadPoolExecutor
            from workflows.data_v1_final.conformers.sprime_packed_day_v1 import runtime as PIO
            root=pathlib.Path(d)/'closed64';root.mkdir();plan_ref={'path':'/synthetic/p','bytes':1,'sha256':'c'*64}
            origin={'root':str(root),'job_id':'1','entry':{'producer_plan_reference':plan_ref},'plan':{'cpus':64}}
            reader=closure.OriginReader(origin,{'max_registered_parents':1,'max_files_per_parent':8,'max_bytes_per_parent':1<<20,'max_task_file_bytes':1<<20},lambda:None)
            headers=[]
            for n in range(2):
                bid='batch-00'+str(114+n);directory=root/'internal_prepared'/bid;directory.mkdir(parents=True)
                task={'meta':{'task_key':str(n)*64,'molecule_id':'synthetic'+str(n)}}
                tr=PIO.exclusive(directory/'tasks.jsonl',C.canonical(task)+b'\n')
                hr=I.save(directory/'prepared.json',{'schema':'SPRIME_PACKED_INTERNAL_PREPARED_V1','actual_allocated_cpus':64,
                    'actual_single_parent_job_id':'1','packed_plan_reference':plan_ref,'native_task_keys_and_seed_domains_changed':False,
                    'molecules':1,'batch_id':bid,'tasks_reference':tr});headers.append(hr)
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda r:reader.prepared(r,origin),headers*3))
            for n,(header,tasks) in enumerate(results):self.assertEqual(set(tasks),{str(n%2)*64})
            first=reader.reference(headers[0]['path']);pathlib.Path(first['path']).write_bytes(b'changed')
            with self.assertRaises(ValueError):reader.reference(first['path'])
    def test_one_new_scope_partial_is_not_common_or_child_C0(self):
        p={'original_config_reference':{'path':'/synthetic/config','bytes':1,'sha256':'a'*64},'packed_receipt_reference':{'path':'/synthetic/receipt','bytes':1,'sha256':'b'*64},
          'cpus':64,'node':'compute-0-18','output_cap_bytes':384<<30}
        v=C.parameters(p);self.assertEqual(v['common_conditions'],['S','Sprime','P','Pprime','D']);self.assertEqual(v['new_child_Slurm_jobs'],0)
        self.assertTrue(v['root_final_release_after_actual_parent_C0']);self.assertEqual(v['dedup_threshold_A'],0.5)
        p['packed_origins_review_reference']={'path':'/synthetic/actual-origins-review','bytes':1,'sha256':'d'*64}
        self.assertEqual(C.parameters(p)['packed_origins_review_reference'],p['packed_origins_review_reference'])
        self.assertTrue(C.parameters(p)['no_scientific_retry_or_once_reset'])
        p['packed_receipt_reference']=None;p['packed_operational_metadata_entry_reference']={'path':'/synthetic/actual-lstat-entry','bytes':1,'sha256':'e'*64}
        self.assertEqual(C.parameters(p)['operational_receipt_CPU_only_contract_version'],3)
        self.assertIsNone(C.parameters(p)['packed_receipt_reference']) # An explicit deferred descriptor, never an absence or a fabricated SHA.
        actual={'path':'/synthetic/closed/receipt.json','bytes':2805941,'sha256':'f'*64}
        namespace='POSTPROCESS_READONLY_GEOMETRY_V1';cache_key='real-cache-key'
        self.assertEqual(C.F.sha_value([namespace,cache_key,actual]),C.F.sha_value([namespace,cache_key,dict(actual)]))
        self.assertEqual(C.PACK.origin_resources({'cpus':64}),(64,'compute-0-13',1))
        for node in ('compute-0-14','compute-0-18'):
            self.assertEqual(C.PACK.origin_resources({'cpus':32,'node':node,'packed_resource_contract_version':2}),(32,node,2))
        with self.assertRaises(ValueError):C.PACK.origin_resources({'cpus':64,'node':'compute-0-18'})
        self.assertNotEqual(C.F.sha_value([namespace,cache_key,actual]),C.F.sha_value([namespace,cache_key,None]))
