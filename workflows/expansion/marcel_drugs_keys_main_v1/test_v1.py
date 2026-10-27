"""Three synthetic methods before original producer-log body; real frozen keys."""
import copy,tempfile,unittest
from pathlib import Path
from workflows.expansion.marcel_identity_format_probe_v1.projection import encoded
from . import rows as V,kernel as K


def sdf(ordinal,smiles,name=b'native-name',identifier=b'000'):
    return {'source_id':'marcel_drugs_zip','member':'Drugs.sdf','physical_ordinal':ordinal,
        'name_pairing_basis':'EXACT_UNNORMALIZED_BYTES','chemical_key_computed':False,
        'details':{'title_name':encoded(name),'properties':{'ID':[encoded(identifier)],'smiles':[encoded(s) for s in smiles],'_Name':[]},
            'record_sha256':'0'*64,'record_bytes':123,'terminated':True,'M_END_observed':True,
            'format_state':'SELECTED_SOURCE_FIELDS_OBSERVED','issues':[],'graph_and_stereo_verified':False}}


class FakeBudget:
    def check(self,*args,**kwargs):pass


class Boundaries(unittest.TestCase):
    functions=None
    def test_original_all_variants_stereo_isotope_and_ID_preserved(self):
        row=sdf(0,[b'C[C@H](F)Cl',b'C[C@@H](F)Cl',b'CO',b'[13CH3]O']);before=copy.deepcopy(row)
        value=K.normalize(row,self.functions);self.assertEqual(value['source'],before)
        variants=value['variant_observations'];self.assertEqual(len(variants),4)
        self.assertTrue(all(v['state']=='FULL_KEYS_DERIVED' for v in variants))
        self.assertNotEqual(variants[0]['full_InChIKeys'],variants[1]['full_InChIKeys'])
        self.assertNotEqual(variants[2]['full_InChIKeys'],variants[3]['full_InChIKeys'])
        self.assertEqual({p[0] for p in value['full_key_and_WP5_pairs']},{k for v in variants for k in v['full_InChIKeys']})
        self.assertEqual(value['source']['details']['properties']['ID'][0]['text'],'000')
        self.assertTrue(all(w==self.functions['wp5_key'](k) for k,w in value['full_key_and_WP5_pairs']))
        self.assertFalse(value['SMILES_repair_or_representative_choice'])

    def test_name_relationship_retains_every_conformer_and_SMILES_union(self):
        with tempfile.TemporaryDirectory() as directory:
            relation=V.Relations(Path(directory),FakeBudget())
            try:
                for ordinal,smiles in enumerate((b'CCO',b'CCN')):
                    row=sdf(ordinal,[smiles],identifier=(b'0' if ordinal==0 else b'000'))
                    relation.add(row);relation.result(K.normalize(row,self.functions))
                relation.db.commit()
                self.assertEqual(relation.db.execute('SELECT count(*) FROM conformers').fetchone()[0],2)
                self.assertEqual(relation.db.execute('SELECT count(DISTINCT value) FROM source_smiles').fetchone()[0],2)
                self.assertEqual(relation.db.execute('SELECT value FROM native_ids ORDER BY ordinal').fetchall(),[(b'0',),(b'000',)])
                union=relation.db.execute('SELECT DISTINCT full_key FROM keys ORDER BY full_key').fetchall()
                self.assertEqual(len(union),2)
                with self.assertRaises(ValueError):relation.add(sdf(3,[b'CCO']))
            finally:relation.db.close()

    def test_missing_empty_invalid_and_uniform_selection_are_never_silent_exclusion(self):
        for variants in ([],[b''],[b'not-a-smiles'],[b'\xff']):
            row=sdf(0,variants,identifier=b'0');value=K.normalize(row,self.functions)
            self.assertEqual(value['source'],row);self.assertTrue(value['has_any_unknown'])
            self.assertFalse(value['full_key_and_WP5_pairs']);self.assertFalse(value['unknown_is_chemical_exclusion'])
        self.assertIsNone(V.token({'state':'MISSING','bytes':None}))
        with self.assertRaises(ValueError):V.token({'state':'INVALID_UTF8_UNKNOWN','bytes':1,'base64':'QQ=='})
        from .run import selected
        from . import contract as C
        first=selected('profile');self.assertEqual(first,selected('profile'));self.assertEqual(len(first),C.PILOT_N)
        self.assertTrue(all(type(n) is int and 0<=n<C.N for n in first));self.assertIsNone(selected('full'))
