"""Four pure byte/ordinal/unknown boundaries; no files or chemical execution."""
import copy,unittest
from . import projection as P


def source(n,drug='C',native='0000'):
    return {'dataset':'tdc_admet_group_zip','member_name':'admet_group/x/test.csv','endpoint':'x','original_split':'test',
        'physical_record_ordinal':n,'original_Drug_ID':{'state':'LITERAL_UTF8','text':native,'bytes':len(native)},
        'original_Drug':{'state':'LITERAL_UTF8','text':drug,'bytes':len(drug.encode())},'row_width':3,
        'source_identity_state':'EXACT_SOURCE_IDENTITY_COLUMNS','assay_Y_decoded':False}


def events(row):
    return [{'event':'SOURCE_ROW_DURABLE_BEFORE_WORKER_DISPATCH','source':row},
        {'event':'ORIGINAL_ROW_IDENTITY_RESULT_COMPLETE','worker_observation':{'worker_pid':1,'worker_CPU_seconds':0.0,
            'result':{'source':copy.deepcopy(row),'identity_state':'ORIGINAL_SMILES_UNRESOLVED','full_InChIKeys':[],'WP5_keys':[],
                'identity_errors':[{'message':'original failure retained'}]}}}]


def journal():return P.Journal({'admet_group/x/test.csv':2},{'ORIGINAL_SMILES_UNRESOLVED':2})


class Boundaries(unittest.TestCase):
    def test_exact_two_original_variants_IDzeros_and_offsets_retained(self):
        j=journal();offset=0
        for row in (source(0,'N[N]'),source(1,'C@C','ID-2')):
            for event in events(row):
                raw=P.dump(event);j.feed(raw,offset);offset+=len(raw)
        targets=j.finish();self.assertEqual(len(targets),2);self.assertEqual(targets[('admet_group/x/test.csv',0)]['source']['original_Drug_ID']['text'],'0000')
        self.assertEqual(targets[('admet_group/x/test.csv',1)]['source']['original_Drug']['text'],'C@C')
    def test_duplicate_missing_or_literal_source_conflict_rejected(self):
        a,b=events(source(0));j=journal();j.feed(P.dump(a),0)
        with self.assertRaises(ValueError):j.feed(P.dump(a),1)
        with self.assertRaises(ValueError):j.finish()
        b['worker_observation']['result']['source']['original_Drug']['text']='CHANGED'
        with self.assertRaises(ValueError):j.feed(P.dump(b),2)
    def test_original_CSV_CRLF_quoted_newline_Y_invalidUTF8_and_exact_binding(self):
        rows=[];p=P.IdentityCSV('admet_group/x/test.csv',rows.append)
        for block in (b'Drug_ID,Drug,Y\r',b'\n0000,"C\nC",\xff\r',b'\nID-2,N,1\r\n'):p.feed(block)
        p.finish();self.assertEqual(rows[0]['original_Drug']['text'],'C\nC');self.assertEqual(rows[0]['original_Drug_ID']['text'],'0000')
        targets={P.location(r):{'source':r} for r in rows};bindings={};P.bind(rows[0],targets,bindings)
        with self.assertRaises(ValueError):P.bind(rows[0],targets,bindings)
        changed=copy.deepcopy(rows[1]);changed['original_Drug_ID']['text']='OTHER'
        with self.assertRaises(ValueError):P.bind(changed,targets,bindings)
    def test_truncated_oversized_and_fabricated_keys_rejected(self):
        with self.assertRaises(ValueError):journal().feed(b'{}',0)
        with self.assertRaises(ValueError):journal().feed(b' '*(8<<20)+b'\n',0)
        a,b=events(source(0));j=journal();j.feed(P.dump(a),0);b['worker_observation']['result']['full_InChIKeys']=['bad']
        with self.assertRaises(ValueError):j.feed(P.dump(b),1)
