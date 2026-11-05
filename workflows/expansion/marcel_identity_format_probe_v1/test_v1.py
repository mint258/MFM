"""Synthetic bytes only; all three methods must precede original bodies."""
import io,unittest
from . import projection as P,opcodes as O


class Boundaries(unittest.TestCase):
    def test_csv_literal_names_quotes_CRLF_and_missing(self):
        rows=[];p=P.NameCSV(lambda *a:rows.append(a));data=b'name,energy\r\n"a,\r\nb",not-a-number\r\n,1\r\nzero\r\n'
        for b in data:p.feed(bytes([b]))
        summary=p.finish();self.assertEqual([r[1] for r in rows],[b'a,\r\nb',b'',b'zero'])
        self.assertEqual(summary['counts']['physical_data_records'],3);self.assertEqual(summary['counts']['field_count_below_header'],1)
        self.assertEqual(len(P.grammar_proof()),3);self.assertFalse(summary['assay_values_decoded'])
    def test_sdf_exact_name_ID_smiles_and_ambiguity(self):
        raw=b' 000 \r\nheader\r\n\r\ncounts\r\nM  END\r\n> <ID>\r\n0\r\n\r\n> <smiles>\r\n[C@H](F)(Cl)Br\r\n\r\n$$$$\r\n'
        name,fields,row=P.sdf_record(raw,True);self.assertEqual(name,b' 000 ');self.assertEqual(fields['ID'],[b'0'])
        self.assertEqual(fields['smiles'],[b'[C@H](F)(Cl)Br']);self.assertEqual(row['format_state'],'SELECTED_SOURCE_FIELDS_OBSERVED')
        _,_,unknown=P.sdf_record(raw.replace(b'$$$$',b'> <ID>\r\n1\r\n\r\n$$$$'),False)
        self.assertIn('ID_MISSING_OR_DUPLICATE_UNKNOWN',unknown['issues']);self.assertFalse(unknown['terminated'])
    def test_pickle_GLOBAL_REDUCE_and_STACK_GLOBAL_are_never_executed(self):
        data=b'\x80\x04\x8c\x08builtins\x94\x8c\x04eval\x94\x93\x8c\x011\x85R.'
        result=O.inventory(io.BytesIO(data),lambda:None)
        self.assertTrue(result['STOP_observed']);self.assertEqual(result['global_symbols'],[{'module':'builtins','name':'eval','occurrences':1}])
        self.assertEqual(result['opcode_counts']['REDUCE'],1);self.assertFalse(result['pickle_load_or_Unpickler_called'])
        self.assertEqual(O.inventory(io.BytesIO(b'cbuiltins\neval\n.'),lambda:None)['global_symbols'][0]['name'],'eval')
        self.assertEqual(O.inventory(io.BytesIO(data+b'x'),lambda:None)['status'],'OPCODE_STRUCTURE_UNKNOWN_HOLD')
