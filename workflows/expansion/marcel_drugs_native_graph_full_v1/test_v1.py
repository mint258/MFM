"""Three full-only boundaries; original native profile3 are reused unchanged."""
import copy,sqlite3,unittest,hashlib
from workflows.expansion.marcel_drugs_native_graph_profile_v1 import kernel as K,reader as V
from workflows.expansion.marcel_drugs_native_graph_profile_v1.test_v1 import synthetic
from workflows.expansion.marcel_drugs_keys_main_v1 import kernel as OLD
from . import contract as C,cache as F


class Boundaries(unittest.TestCase):
    functions=None
    @classmethod
    def setUpClass(cls):
        if cls.functions is None:cls.functions,_=K.load([C.Q.pin(p) for p in C.source_paths()])
    def cache(self,db,rows):
        cache=F.FullKeys(db,self.functions,expected=len(rows));results=[]
        for row in rows:
            result=OLD.normalize(row,self.functions);results.append(result)
            cache.consume({'event':'ORIGINAL_CONFORMER_SOURCE_DURABLE_BEFORE_DISPATCH','source':row})
        for result in reversed(results):cache.consume({'event':'ORIGINAL_CONFORMER_IDENTITY_RESULT_DURABLE','worker_observation':{'result':result}})
        cache.finish();return cache,results

    def test_streamed_full_source_cache_all_variants_and_out_of_order_results_bind_exact_intents(self):
        _,a,_=synthetic();_,b,_=synthetic(smiles='[13CH3][C@@H](F)Cl');b['physical_ordinal']=1
        db=sqlite3.connect(':memory:')
        try:
            cache,results=self.cache(db,[a,b]);self.assertEqual(cache.get(a),results[0]);self.assertEqual(cache.get(b),results[1])
            changed=copy.deepcopy(a);changed['details']['properties']['ID'][0]=V.P.encoded(b'0')
            with self.assertRaisesRegex(ValueError,'EXACT_SOURCE'):cache.get(changed)
            with self.assertRaises(sqlite3.IntegrityError):cache.consume({'event':'ORIGINAL_CONFORMER_IDENTITY_RESULT_DURABLE','worker_observation':{'result':results[0]}})
            self.assertEqual(cache.get(a)['source']['details']['properties']['ID'][0]['text'],'000')
        finally:db.close()

    def test_actual_closed_native_adoption_preserves_old_packet_and_rejects_wrong_raw_or_source(self):
        raw,row,_=synthetic();db=sqlite3.connect(':memory:')
        try:
            cache,results=self.cache(db,[row]);cached=results[0];pairs=cached['full_key_and_WP5_pairs']
            blob={'path':'/synthetic/selected_original_records.raw','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            ref={'container_path':blob['path'],'offset':0,'bytes':len(raw),'sha256':blob['sha256']}
            payload={'source':row,'cached_source_keys':cached,'raw_record_reference':ref,'allocation':{'job_id':'4523547'}}
            result={'source':row,'cached_source_SMILES_observation':cached,'raw_record_reference':ref,
                'native_graph_full_key_and_WP5_pairs':pairs,'has_any_unknown':False,
                'native_graph_vs_source_key_set_mismatch':False,'identity_state':'NATIVE_GRAPH_FULL_KEY_DERIVED',
                'conservative_all_observed_full_key_and_WP5_pairs':copy.deepcopy(pairs)}
            observed={'worker_pid':123,'worker_CPU_seconds':0.1,'result':result};original=copy.deepcopy(observed)
            adopted=F.adopted_observation(payload,observed,cache,raw,blob,self.functions)
            self.assertEqual(adopted['original_worker_observation'],original);self.assertEqual(observed,original)
            with self.assertRaisesRegex(ValueError,'SEGMENT_SHA'):F.adopted_observation(payload,observed,cache,raw[:-1]+b'x',blob,self.functions)
            bad=copy.deepcopy(observed);bad['result']['has_any_unknown']=True
            with self.assertRaisesRegex(ValueError,'SUCCESSFUL_NATIVE'):F.adopted_observation(payload,bad,cache,raw,blob,self.functions)
        finally:db.close()

    def test_full_name_union_coverage_unknown_retention_and_large_DATA_locator_are_independent(self):
        class Collect:
            def __init__(self):self.values=[]
            def write(self,value,dispatch):self.values.append(copy.deepcopy(value))
        target=Collect();writer=F.FullNames(target)
        row={'source_conformers':2,'source_profile_keys_observed_conformers':2,'native_graph_observed_conformers':2,
            'native_graph_NOT_YET_EXAMINED_conformers':0,'unknown_observed_native_conformers':1,'native_source_key_mismatch_conformers':1,
            'conservative_all_observed_full_InChIKey_union':['first','second'],'conservative_all_observed_WP5_key_union':['a','b'],
            'representative_chosen':False,'coverage':'PARTIAL_NATIVE1000_AND_SOURCE_KEY10000_PROFILE_ALL_PHYSICAL_RELATIONSHIPS_RETAINED'}
        before=copy.deepcopy(row);writer.write(row)
        self.assertEqual(row,before);self.assertEqual(target.values[0]['conservative_all_observed_full_InChIKey_union'],before['conservative_all_observed_full_InChIKey_union'])
        self.assertEqual(target.values[0]['unknown_observed_native_conformers'],1);self.assertFalse(target.values[0]['unknown_or_mismatch_is_chemical_exclusion'])
        bad=copy.deepcopy(row);bad['native_graph_NOT_YET_EXAMINED_conformers']=1
        with self.assertRaisesRegex(ValueError,'FULL_NAME'):writer.write(bad)
        self.assertEqual(C.triple({'path':'/declared/full_journal','bytes':1218689688,'sha256':'a'*64})['bytes'],1218689688)
        for size in (True,0,-1):
            with self.assertRaises(ValueError):C.triple({'path':'/declared/full_journal','bytes':size,'sha256':'a'*64})
