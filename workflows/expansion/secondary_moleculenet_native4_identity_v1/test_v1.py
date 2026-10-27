"""Three new synthetic boundaries only; old B3 are actual referenced evidence."""
import io,unittest
from . import native as N


def sdf(smiles='[13CH3][NH3+]'):
    from rdkit import Chem
    mol=Chem.AddHs(Chem.MolFromSmiles(smiles));mol.SetProp('_Name','000 native title')
    return Chem.MolToMolBlock(mol).encode()+b'> <ID>\n000\n\n$$$$\n'


class Boundaries(unittest.TestCase):
    functions=None
    def test_all_records_titles_IDs_and_original_CSV_grammar(self):
        raw=sdf();records=[];self.assertEqual(N.records(io.BytesIO(raw+raw),'SDF',lambda n,b,c:records.append((n,b,c)),lambda:None),2)
        self.assertEqual(records,[(0,raw,True),(1,raw,True)])
        spaced=raw.replace(b'$$$$',b' $$$$ ');kept=[];self.assertEqual(N.records(io.BytesIO(spaced+spaced),'SDF',lambda n,b,c:kept.append(b),lambda:None),2);self.assertEqual(kept,[spaced,spaced])
        row=N.project('qm8_sdf','qm8.sdf',0,0,0,'SDF',raw,True,self.functions)
        self.assertEqual(row['native_title']['text'],'000 native title');self.assertEqual(row['literal_identity_properties']['ID'][0]['text'],'000')
        got=[];parser=N.IDCSV(0,lambda n,v,d:got.append((n,v,d)))
        parser.feed(b'id,assay\r\n"000",\xff\r\n"a,b",1\r\n,2\r\n');summary=parser.finish()
        self.assertEqual([v for n,v,d in got],[b'000',b'a,b',b'']);self.assertEqual(summary['physical_rows'],3)
        self.assertIs(N.IDCSV.feed,N.F.CSVProjection.feed);self.assertIs(N.IDCSV.append,N.F.CSVProjection.append);self.assertIs(N.IDCSV.finish,N.F.CSVProjection.finish)
        missing=[];p=N.IDCSV('pdb_id',lambda n,v,d:missing.append(d));p.feed(b'wrong,label\na,3\n');p.finish();self.assertFalse(missing[0]['unambiguous_literal_ID_column'])

    def test_literal_MOL2_elements_not_partial_charge_or_pseudo_atom_guess(self):
        raw=b'@<TRIPOS>MOLECULE\n000 mol\n3 2 0 0 0\nSMALL\nUSER_CHARGES\n@<TRIPOS>ATOM\n1 C1 0 0 0 C.ar 1 LIG -0.7\n2 N1 0 1 0 N.am 1 LIG 9.3\n3 H1 1 0 0 H 1 LIG -8.6\n@<TRIPOS>BOND\n1 1 2 1\n2 1 3 1\n'
        comp,_=N.elements(raw,'MOL2',self.functions);self.assertEqual(comp,[[6,1],[7,1]])
        altered=raw.replace(b'-0.7',b'9999').replace(b'9.3',b'unknown');self.assertEqual(N.elements(altered,'MOL2',self.functions)[0],comp)
        row=N.project('pdbbind_core','v2013-core/0000/0000_ligand.mol2',0,0,0,'MOL2',raw,True,self.functions)
        self.assertEqual(row['native_PDB_path_ID'],'0000');self.assertEqual(row['native_graph_state'],'MOL2_FORMAL_CHARGE_STEREO_UNKNOWN')
        with self.assertRaises(ValueError):N.key_work(row,raw)
        pseudo=N.project('pdbbind_core','v2013-core/0000/0000_ligand.mol2',0,0,0,'MOL2',raw.replace(b'C.ar',b'Du'),True,self.functions)
        self.assertIsNone(pseudo['native_non_H_composition_evidence']);self.assertIsNotNone(pseudo['native_table_error'])
        original=sdf();unterminated=original.rsplit(b'$$$$',1)[0];self.assertEqual(N.elements(unterminated,'SDF',self.functions)[0],[[6,1],[7,1]])

    def test_actual_N_sampler_and_independent_source_SDF_seams(self):
        self.assertEqual(N.sample('qm8_sdf',0),[]);self.assertEqual(N.sample('qm8_sdf',5),list(range(5)))
        picked=N.sample('qm8_sdf',1200);self.assertEqual(picked,N.sample('qm8_sdf',1200));self.assertEqual(len(set(picked)),1000)
        self.assertNotEqual(picked,list(range(1000)));raw=sdf();N.FUNCTIONS=self.functions
        for source in ('qm8_sdf','pdbbind_core'):
            name='qm8.sdf' if source=='qm8_sdf' else 'v2013-core/0000/0000_ligand.sdf'
            row=N.project(source,name,0,0,0,'SDF',raw,True,self.functions);value=N.key_work(row,raw)
            self.assertEqual(value['source'],row);self.assertFalse(value['has_unknown']);self.assertTrue(value['native_SDF_full_keys'])
            self.assertEqual(value['source_only_reader_kwargs'],{'sanitize':True,'removeHs':False,'strictParsing':source!='qm8_sdf'})
            self.assertFalse(value['PDB_source_only_seam_equals_author_repair_loader']);self.assertFalse(value['automatic_composition_exclusion_for_known_keys'])
