"""One synthetic original-kernel golden and exact shard-resume regression."""
import concurrent.futures as cf,copy,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from . import radix_parts as R,statistics as T,temporary as Temp
from ..window2_normalization_v1 import io as I,run as Original
from ..normalization_compact_runtime_v3 import codec as K

class RadixParts(unittest.TestCase):
    def test_original_golden_exact_refinement_and_interrupted_reordered_resume(self):
        import pyarrow as pa,pyarrow.parquet as pq
        class Runtime:
            def __init__(self):self.checked=[]
            def wait(self,path=None):self.checked.append(str(path))
        class Pool:
            def __init__(self):self.calls=[]
            def submit(self,fn,*args):
                self.calls.append(args);future=cf.Future()
                try:future.set_result(fn(*args))
                except BaseException as error:future.set_exception(error)
                return future
        def bits(value):
            if type(value)is float:return ('f64',struct.pack('<d',value).hex())
            if isinstance(value,dict):return {key:bits(item) for key,item in value.items()}
            if isinstance(value,(list,tuple)):return [bits(item) for item in value]
            return value
        runtime=Runtime()
        with tempfile.TemporaryDirectory() as folder,patch.object(Temp,'activate',return_value=runtime),patch.object(R.cf,'as_completed',side_effect=lambda futures:reversed(list(futures))):
            root=Path(folder)
            fields=[{'field_id':0,'field_key':'P.energy','source_path':'energy','level':'molecule','element_reference_eligible':True,'unit':'eV'},
                {'field_id':1,'field_key':'P.atom','source_path':'atom','level':'atom','element_reference_eligible':False,'unit':'eV'},
                {'field_id':146,'field_key':'P.r73.sigma','source_path':'r73','level':'pair','element_reference_eligible':False,'unit':None}]
            field_ref=I.save(root/'fields.json',fields)
            model_ref=I.save(root/'models.json',{'0':{'basis':[1,6],'coefficients':[0.25,-0.5],'intercept':0.125}})
            packed=[]
            for index,value in enumerate((1.,-0.,8.,1.0000000000000002,-4.,1.)):
                entries=[]
                for fid,values,indices,masks in ((0,[value],None,[True]),(1,[value,value+2.],[0,1],[True,index%3!=0]),(146,[value,value],None,[True,index%2==0])):
                    entries.append({'field_id':fid,'values_float64':values,'atom_indices':indices,'source_value_mask':[True]*len(values),'value_mask':masks,'source_reasons':[],'new_reasons':[],'review_reasons':[]})
                packed.append(dict(record_id='r'+str(index),molecule_id='m'+str(index),fit_eligible=index!=2,atomic_numbers=[1,6],calc_type='toy',**K.pack_entries(entries)))
            parts=[]
            for index in range(3):
                path=root/('part%d.parquet'%index);pq.write_table(pa.Table.from_pylist(packed[index*2:index*2+2]),path)
                parts.append(dict(I.ref(path),records=2,source_job_id='original-source-A',source_order=index))
            group={'group_index':7,'source_job_id':'original-source-A','typed_parts':parts}
            cfg={'mode':'full','field_map_reference':field_ref,'coverage_reference':field_ref,'eligibility_reference':field_ref,'input_release_reference':field_ref,'element_models_reference':model_ref,'element_basis':[1,6],'_temporary_runtime':{}}
            self.assertFalse(R.enabled({},'normalization_quantiles'))
            for purpose in ('element_reference','normalization_moments'):
                self.assertFalse(R.enabled({'shard_radix_typed_parts':True},purpose))
                with self.assertRaisesRegex(ValueError,'INTEGER_RADIX_PURPOSE_ONLY'):R.Shards(dict(cfg,statistics_purpose=purpose),{},root,[group],runtime)
            for purpose,final_key in (('normalization_quantiles','exact_tail_reference'),('diagnostic_median_MAD','diagnostic_median_MAD_reference')):
                self.assertTrue(R.enabled({'shard_radix_typed_parts':True},purpose));current=dict(cfg,statistics_purpose=purpose);round_index=0
                while True:
                    stage=T.Original.initial_stage(current,fields);stage['element_basis']=[1,6]
                    stage_root=root/purpose/str(round_index);stage_root.mkdir(parents=True)
                    stage_ref=I.save(stage_root/'stage.json',stage)
                    golden_root=stage_root/'golden';golden_root.mkdir()
                    golden=I.load_data(T.group_pass((current,stage,str(golden_root),group)))
                    checkpoint=stage_root/'checkpoint.json';state={'groups':{},'pass_index':round_index+1};pool=Pool()
                    attempt=stage_root/'attempt';attempt.mkdir()
                    interrupted=purpose=='normalization_quantiles' and round_index==0
                    if interrupted:
                        store=R.Shards(current,stage_ref,stage_root,[group],runtime);refs={}
                        for index in (2,0):
                            output=stage_root/('closed_part%d'%index);output.mkdir()
                            refs[index]=R.part_pass((current,stage,str(output),dict(group,typed_parts=[parts[index]])),index,stage_ref)
                            store.record(group,index,refs[index])
                        store=R.Shards(current,stage_ref,stage_root,[group],runtime)
                        self.assertEqual(store.remaining(group),[1]);store.record(group,0,refs[0])
                        singleton=dict(group,typed_parts=[parts[0]]);singleton_root=stage_root/'singleton_reuse'
                        singleton_store=R.Shards(current,stage_ref,singleton_root,[singleton],runtime)
                        singleton_store.record(singleton,0,refs[0])
                        with patch.object(pq,'ParquetFile',side_effect=AssertionError('SINGLETON_MUST_NOT_READ_HISTOGRAM')):
                            self.assertEqual(singleton_store.merge(singleton),refs[0])
                        self.assertFalse((singleton_root/'radix_merged').exists())
                        with self.assertRaisesRegex(ValueError,'EXACT_SUBMITTED'):store.record(group,1,refs[0])
                        with self.assertRaisesRegex(ValueError,'CONFLICTING_CLOSED'):store.record(group,0,dict(refs[0],path=refs[2]['path'],bytes=refs[2]['bytes']))
                        bad=I.load_data(refs[0]);bad['moments']={'0':{'mean':1.}}
                        bad_ref=I.save(stage_root/'bad_float.json',bad)
                        with self.assertRaisesRegex(ValueError,'FLOAT_STATE'):store.record(group,0,dict(refs[0],**bad_ref))
                        with self.assertRaisesRegex(ValueError,'SAME_ACTIVE_STAGE'):R.Shards(current,dict(stage_ref,bytes=stage_ref['bytes']+1),stage_root,[group],runtime)
                        with self.assertRaisesRegex(ValueError,'SAME_ACTIVE_STAGE'):R.Shards(current,stage_ref,stage_root,[dict(group,typed_parts=list(reversed(parts)))],runtime)
                    R.run_stage(pool,current,stage,stage_ref,stage_root,attempt,[group],state,checkpoint)
                    self.assertEqual(len(pool.calls),1 if interrupted else 3)
                    merged=I.load_data(state['groups']['7'])
                    for key in ('group_index','source_job_id','statistics_purpose','task_rows','role_task_counts','field_counts','series_mass','energy_TSQR','moments','joint'):
                        self.assertEqual(merged[key],golden[key])
                    for name in stage['queries']:
                        left=Original.histogram_rows([golden],name);right=Original.histogram_rows([merged],name)
                        self.assertEqual(left,right);self.assertEqual(bits(T.Original.B.advance(stage['queries'][name],left)),bits(T.Original.B.advance(stage['queries'][name],right)))
                    calls=len(pool.calls);R.run_stage(pool,current,stage,stage_ref,stage_root,attempt,[group],state,checkpoint)
                    self.assertEqual(len(pool.calls),calls) # closed group dispatches no work
                    resumed=R.Shards(current,stage_ref,stage_root,[group],runtime)
                    self.assertEqual(resumed.remaining(group),[])
                    self.assertEqual(resumed.merge(group),state['groups']['7'])
                    golden_finish=stage_root/'golden_finish';golden_finish.mkdir();merged_finish=stage_root/'merged_finish';merged_finish.mkdir()
                    a=Original.finish_stage(current,stage,golden_finish,[golden]);b=Original.finish_stage(current,stage,merged_finish,[merged])
                    self.assertEqual(set(a),set(b))
                    for key in a:self.assertEqual(bits(I.load_data(a[key])),bits(I.load_data(b[key])))
                    round_index+=1;self.assertLess(round_index,20)
                    if 'query_stage_reference'not in a:
                        self.assertIn(final_key,a);break
                    current=dict(current,query_stage_reference=a['query_stage_reference'])
            self.assertTrue(runtime.checked)