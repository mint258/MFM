"""Three synthetic boundaries, before original DATA and resource Client creation."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from . import run as R
WORKSPACE=None

class SyntheticBudget:
    def check(self,*args,**kwargs):pass
    def charge(self,n):R.need(type(n)is int and n>=0,'EXACT_SYNTHETIC_CHARGE')

class Boundaries(unittest.TestCase):
    def test_placeholder_spelling_does_not_release_original_unknown_or_trim(self):
        for literal in ('NA','N/A','NULL','None','nan','-','?'):
            value=R.field_fact(literal,'PRESENT');self.assertEqual(value['placeholder_status'],'SPELLING_ONLY_NOT_SOURCE_PROVEN')
            self.assertFalse(value['identity_ignored_or_accepted']);self.assertEqual(value['UTF8_sha256'],hashlib.sha256(literal.encode()).hexdigest())
        value=R.field_fact(' CCO ','PRESENT');self.assertTrue(value['surrounding_whitespace']);self.assertFalse(value['original_parser_ASCII33_to126_boundary'])
        self.assertEqual(R.field_fact('', 'EMPTY')['placeholder_status'],'SOURCE_EXPLICIT_EMPTY_OR_MISSING_FIELD_NOT_EMPTY_RECORD')
        self.assertEqual(R.field_fact(None,'MISSING')['type'],'null')
        self.assertFalse(R.field_fact('\ud800','PRESENT')['UTF8_valid'])
        self.assertEqual(R.cause('could contain a literal source value'),'UNKNOWN_SUBCAUSE_NOT_INFERRED')
        self.assertFalse(R.PARAMETERS['original_UNKNOWN_or_READY_changed']);self.assertEqual(R.PARAMETERS['existing_unresolved'],21)

    def test_sparse_physical_rows_keep_ordinals_and_same_fd_SHA(self):
        import pyarrow as pa,pyarrow.parquet as pq
        R.need(WORKSPACE is not None,'OWN_PARENT_SYNTHETIC_WORKSPACE')
        with tempfile.TemporaryDirectory(prefix='hold21_synthetic_',dir=WORKSPACE) as directory:
            root=Path(directory);path=root/'original_identity.parquet';pq.write_table(pa.Table.from_pylist([
              {'physical_ordinal':i,'source_id':'synthetic:'+str(i),'identity_field':' CCO ' if i==4 else 'NA'} for i in range(6)]),path,row_group_size=2)
            ref=R.I.data_pin(path,[root],check=lambda:None);plan={'data_references':[ref]}
            rows,facts=R.sparse_rows(ref,[1,4],['physical_ordinal','identity_field'],plan,SyntheticBudget())
            self.assertEqual(set(rows),{1,4});self.assertEqual(rows[4]['physical_ordinal'],4);self.assertEqual(rows[4]['identity_field'],' CCO ')
            self.assertEqual(facts['row_groups_read'],[0,2]);self.assertFalse(facts['full_source_rows_scanned'])
            with self.assertRaises(ValueError):R.sparse_rows(ref,[1,1],['physical_ordinal'],plan,SyntheticBudget())
            with self.assertRaises(ValueError):R.sparse_rows(ref,[6],['physical_ordinal'],plan,SyntheticBudget())
            with self.assertRaises(ValueError):R.sparse_rows(dict(ref,sha256='0'*64),[1],['physical_ordinal'],plan,SyntheticBudget())

    def test_closed_HTTP_missing_axes_do_not_become_network_or_identity_success(self):
        event={'HTTP_status':200,'complete_EOF':True,'error':None};entry={'rcsb_id':'1ABC','nonpolymer_entities':[
          {'nonpolymer_comp':{'chem_comp':{'id':'ABC','formula':None},'rcsb_chem_comp_descriptor':{'InChIKey':None}}}]}
        body=json.dumps({'data':{'entry':entry}}).encode();facts=R.response_facts(body,event,'1abc','ABC')
        self.assertEqual(facts['exact_original_CCD_matches'],1);self.assertEqual(facts['formula_field_types'],['NoneType'])
        self.assertEqual(facts['stored_InChIKey_field_present'],[False]);self.assertFalse(facts['new_call_or_key_validation'])
        facts=R.response_facts(body,event,'1abc','XYZ');self.assertIn('ORIGINAL_CCD_NOT_IN_ENTRY',facts['missing_categories'])
        facts=R.response_facts(b'{"data":{"entry":null}}',event,'1abc','ABC');self.assertIn('ENTRY_ABSENT_OR_NOT_OBJECT',facts['missing_categories'])
        facts=R.response_facts(b'<html>retained error</html>',dict(event,HTTP_status=429),'1abc','ABC')
        self.assertIn('HTTP_NON200',facts['missing_categories']);self.assertIn('NOT_STRICT_JSON_RESPONSE',facts['missing_categories'])
        facts=R.response_facts(None,dict(event,HTTP_status=None,complete_EOF=False,error={'type':'URLError'}),'1abc','ABC')
        self.assertIn('NO_POSITIVE_CLOSED_RESPONSE',facts['missing_categories']);self.assertEqual(facts['recorded_error_type'],'URLError')
