"""Three synthetic grammar/API/selection boundaries before producer DATA."""
import copy,io,random,tempfile,unittest
from pathlib import Path
from workflows.expansion.marcel_drugs_keys_main_v1 import kernel as OLD
from . import contract as C,reader as V,kernel as K


def synthetic(smiles='[13CH3][C@H](F)Cl',property_smiles=None):
    from rdkit import Chem
    mol=Chem.AddHs(Chem.MolFromSmiles(smiles));mol.SetProp('_Name','synthetic-name')
    raw=Chem.MolToMolBlock(mol).encode()+b'> <ID>\n000\n\n> <smiles>\n'+(property_smiles or smiles).encode()+b'\n\n$$$$\n'
    _,_,details=V.P.sdf_record(raw,True);return raw,V.source_row('Drugs.sdf',0,details),mol.GetNumAtoms()


class Boundaries(unittest.TestCase):
    functions=None
    def test_original_grammar_byte_capture_and_wrong_binding_rejected(self):
        raw=b'name\r\nprogram\r\n\r\nM  END\r\n> <ID>\r\n000\r\n\r\n> <smiles>\r\nCO\r\n\r\n$$$$\r\n'
        tracked=V.TrackedRecord(io.BytesIO(raw+raw));got=[]
        def emit(ordinal,name,fields,details):
            row=V.source_row('Drugs.sdf',ordinal,details);got.append((row,tracked.take(row)))
        self.assertEqual(V.P.sdf_rows(tracked,emit,lambda:None),2);self.assertEqual([b for r,b in got],[raw,raw]);self.assertFalse(tracked.current)
        self.assertEqual(got[0][0]['details']['properties']['ID'][0]['text'],'000')
        for key,value in (('record_sha256','0'*64),('record_bytes',1)):
            row=copy.deepcopy(got[0][0]);row['details'][key]=value
            with self.assertRaises(ValueError):V.bind_raw(raw,row)
        row=copy.deepcopy(got[0][0]);row['details']['properties']['ID'][0]=V.P.encoded(b'0')
        with self.assertRaises(ValueError):V.bind_raw(raw,row)

    def test_author_supplier_keeps_explicit_H_and_both_mismatching_keys(self):
        for alternate in (None,'[13CH3][C@@H](F)Cl'):
            raw,row,atoms=synthetic(property_smiles=alternate);cached=OLD.normalize(row,self.functions)
            with tempfile.TemporaryDirectory(prefix='drugs_native_synthetic_') as directory:
                path=Path(directory)/'original.sdf';path.write_bytes(raw);value=K.graph_file(path,row,cached,self.functions)
            self.assertEqual(value['source'],row);self.assertEqual(value['author_reader_atom_count_including_explicit_H'],atoms)
            self.assertGreater(atoms,4);self.assertEqual(value['literal_author_properties']['ID']['text'],'000')
            self.assertFalse(value['has_any_unknown']);self.assertFalse(value['representative_or_SMILES_fallback_used'])
            self.assertEqual(value['native_graph_vs_source_key_set_mismatch'],alternate is not None)
            self.assertEqual(len(value['conservative_all_observed_full_key_and_WP5_pairs']),1 if alternate is None else 2)
        bad=b'bad\n\n\nM  END\n> <ID>\n0\n\n> <smiles>\nCO\n\n$$$$\n';_,_,d=V.P.sdf_record(bad,True);row=V.source_row('Drugs.sdf',1,d);cached=OLD.normalize(row,self.functions)
        with tempfile.TemporaryDirectory(prefix='drugs_native_invalid_synthetic_') as directory:
            path=Path(directory)/'invalid.sdf';path.write_bytes(bad)
            try:value=K.graph_file(path,row,cached,self.functions)
            except ValueError:value={'has_any_unknown':True,'native_graph_full_key_and_WP5_pairs':[]}
        self.assertTrue(value['has_any_unknown']);self.assertFalse(value['native_graph_full_key_and_WP5_pairs'])

    def test_draw_order_not_completion_order_and_cached_source_exact(self):
        original,native=V.selections();self.assertEqual(original,random.Random(20261027).sample(range(558002),10000));self.assertEqual(native,original[:1000])
        self.assertEqual(len(set(native)),1000);self.assertNotEqual(native,sorted(original)[:1000]);self.assertNotEqual(set(native),set(list(reversed(original))[:1000]))
        raw,row,_=synthetic();cached=OLD.normalize(row,self.functions);before=copy.deepcopy(cached)
        self.assertEqual(V.cached_result(cached,row,self.functions),before)
        other=copy.deepcopy(row);other['physical_ordinal']=1
        with self.assertRaises(ValueError):V.cached_result(cached,other,self.functions)
        bad=copy.deepcopy(cached);bad['variant_observations'][0]['original_token']=V.P.encoded(b'CO')
        with self.assertRaises(ValueError):V.cached_result(bad,row,self.functions)
        self.assertEqual(cached,before)
