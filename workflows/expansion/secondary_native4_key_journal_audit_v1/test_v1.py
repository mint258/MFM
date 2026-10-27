"""Only three new pure JSON contracts; no old fixture or chemistry import."""
import copy,unittest
from . import reducer as R
K='AAAAAAAAAAAAAA-BBBBBBBBBB-C';L='CCCCCCCCCCCCCC-DDDDDDDDDD-E'


def source(n=0,boundary=True):return {'source_id':'pdbbind_core','source_format_ordinal':n,'format':'SDF','complete_record_boundary':boundary,
    'raw_record_bytes':100,'raw_record_sha256':'a'*64,'record_ordinal':0,'native_title':{'state':'LITERAL_UTF8','text':'000'},
    'native_non_H_composition_evidence':[[6,1]],'native_table_error':None}


def result(row,native=None,variants=None,errors=None):
    native=[] if native is None else native;variants=[] if variants is None else variants;errors=[] if errors is None else errors
    union=sorted(set(native)|{k for v in variants for k in v['full_keys']})
    return {'source':row,'native_SDF_full_keys':native,'variant_observations':variants,'native_graph_errors':errors,
        'observed_full_key_union':union,'WP5_key_union':[],'has_unknown':bool(errors) or any(v['errors'] for v in variants)}


class Boundaries(unittest.TestCase):
    def test_pair_mass_order_source_equality_duplicates_and_pending_bound(self):
        r=R.Reducer({'pdbbind_core':1},{'pdbbind_core':2});row=source()
        with self.assertRaises(ValueError):r.feed({'event':'RESULT_DURABLE_BEFORE_INDEX_OR_UNION','result':result(row)}, {})
        r=R.Reducer({'pdbbind_core':1},{'pdbbind_core':2});r.feed({'event':'SOURCE_DURABLE_BEFORE_KEY_DISPATCH','source':row},{'offset':0})
        with self.assertRaises(ValueError):r.feed({'event':'SOURCE_DURABLE_BEFORE_KEY_DISPATCH','source':row},{})
        r=R.Reducer({'pdbbind_core':1},{'pdbbind_core':2});r.feed({'event':'SOURCE_DURABLE_BEFORE_KEY_DISPATCH','source':row},{})
        bad=copy.deepcopy(row);bad['raw_record_bytes']=101
        with self.assertRaises(ValueError):r.feed({'event':'RESULT_DURABLE_BEFORE_INDEX_OR_UNION','result':result(bad)}, {})
        r=R.Reducer({'pdbbind_core':1},{'pdbbind_core':2});r.feed({'event':'SOURCE_DURABLE_BEFORE_KEY_DISPATCH','source':row},{})
        with self.assertRaises(ValueError):r.finish()
        r.feed({'event':'RESULT_DURABLE_BEFORE_INDEX_OR_UNION','result':result(row)},{});self.assertEqual(r.finish()['events_seen'],2)
        r=R.Reducer({'pdbbind_core':2},{'pdbbind_core':2},max_pending=1);r.feed({'event':'SOURCE_DURABLE_BEFORE_KEY_DISPATCH','source':source(0)},{})
        with self.assertRaises(ValueError):r.feed({'event':'SOURCE_DURABLE_BEFORE_KEY_DISPATCH','source':source(1)},{})

    def test_error_axes_boundary_only_key_success_and_unknown_subphase(self):
        row=source(boundary=False);v=result(row,[K],errors=[{'axis':'native_record','error':'SOURCE_RECORD_BOUNDARY_UNKNOWN_NOT_REPAIRED'}]);a=R.axes(v)
        self.assertTrue(a['native_keys_present']);self.assertTrue(a['has_unknown']);self.assertFalse(a['boundary_false_is_proven_parser_failure']);self.assertFalse(a['issues'])
        self.assertIn(('native_record','NATIVE_RECORD_BOUNDARY_FLAG_FALSE'),a['causes'])
        self.assertEqual(R.cause('native_SDF_graph','FileNotFoundError: opaque cleanup path'),'NATIVE_SUBPHASE_UNKNOWN_INCLUDES_SUPPLIER_OR_TEMP_CLEANUP')
        self.assertEqual(R.cause('native_SDF_graph','ValueError: SOURCE_SDF_PARSER_NONE_UNKNOWN'),'SUPPLIER_RECORDED_NONE_NO_SUBCAUSE')
        self.assertEqual(R.recorded_type({'error':'FileNotFoundError: opaque cleanup path'}),'FileNotFoundError')
        self.assertEqual(R.recorded_type({'error':'SOURCE_RECORD_BOUNDARY_UNKNOWN_NOT_REPAIRED'}),'NO_EXCEPTION_TYPE_RECORDED')
        technical={'source':source(),'observed_full_key_union':[],'WP5_key_union':[],'has_unknown':True,'technical_error':'Future failed'}
        self.assertIn(('technical','FUTURE_OR_RESULT_VALIDATION_TECHNICAL_ERROR'),R.axes(technical)['causes'])

    def test_native_source_union_and_variant_error_are_independent(self):
        variant={'field':'smiles','variant':0,'full_keys':[L],'errors':[{'message':'unresolved secondary variant'}]}
        v=result(source(),[K],[variant]);a=R.axes(v);self.assertEqual(a['key_axis_relation'],'BOTH_DISJOINT');self.assertTrue(a['has_unknown']);self.assertFalse(a['issues'])
        v['observed_full_key_union']=[K];self.assertIn('NATIVE_AND_PRESENT_SOURCE_KEY_UNION_DISAGREES_WITH_RECORDED_UNION',R.axes(v)['issues'])
        v=result(source(),[K]);v['has_unknown']=True;self.assertIn('HAS_UNKNOWN_DOES_NOT_MATCH_RECORDED_ERROR_AXES',R.axes(v)['issues'])
        with self.assertRaises(ValueError):R.key_set(['not-a-full-key'])
