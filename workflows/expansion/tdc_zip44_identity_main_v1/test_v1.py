"""Three synthetic methods, real frozen kernel, no original archive reads."""
import unittest
from . import projection as P,kernel as K


def source(drug,identifier='000'):
    return {'dataset':'tdc_admet_group_zip','member_name':'admet_group/synthetic/train_val.csv','endpoint':'synthetic',
        'original_split':'train_val','physical_record_ordinal':0,'original_Drug_ID':P.text(identifier.encode()),
        'original_Drug':P.text(drug),'row_width':3,'source_identity_state':'EXACT_SOURCE_IDENTITY_COLUMNS','assay_Y_decoded':False}


class Boundaries(unittest.TestCase):
    functions=None
    def test_original_grammar_CRLF_quotes_and_assay_invalid_UTF8_skipped(self):
        rows=[];p=P.IdentityCSV('admet_group/synthetic/test.csv',rows.append)
        data=b'Drug_ID,Drug,Y\r\n"000","C[C@H](F)Cl",\xff\r\n,CCO,"x,y"\r\n\r\n'
        for b in data:p.feed(bytes([b]))
        result=p.finish();self.assertEqual(len(rows),3);self.assertEqual(rows[0]['original_Drug_ID']['text'],'000')
        self.assertEqual(rows[0]['original_Drug']['text'],'C[C@H](F)Cl');self.assertEqual(rows[1]['original_Drug_ID']['text'],'')
        self.assertEqual(result['record_counts']['field_count_below_header'],1);self.assertEqual(len(P.grammar_proof()),3)
        self.assertTrue(all(not row['assay_Y_decoded'] for row in rows))
    def test_original_full_keys_preserve_stereo_and_isotope(self):
        observations=[K.normalize(source(s.encode()),self.functions) for s in ('C[C@H](F)Cl','C[C@@H](F)Cl','CO','[13CH3]O')]
        self.assertTrue(all(x['identity_state']=='FULL_KEYS_DERIVED' for x in observations))
        self.assertNotEqual(observations[0]['full_InChIKeys'],observations[1]['full_InChIKeys'])
        self.assertNotEqual(observations[2]['full_InChIKeys'],observations[3]['full_InChIKeys'])
        for x in observations:
            self.assertEqual(x['WP5_keys'],sorted({self.functions['wp5_key'](k) for k in x['full_InChIKeys']}))
            self.assertEqual(x['source']['original_Drug_ID']['text'],'000')
    def test_empty_invalid_zero_ID_and_original_row_never_disappear(self):
        for raw in (b'',b'not-a-smiles',b'\xff'):
            row=source(raw,'0');r=K.normalize(row,self.functions);self.assertEqual(r['source'],row)
            self.assertFalse(r['full_InChIKeys']);self.assertNotEqual(r['identity_state'],'FULL_KEYS_DERIVED')
            self.assertFalse(r['technical_or_chemical_unknown_is_exclusion'])
