"""Three synthetic methods with actual frozen key functions before source DATA."""
import copy,unittest
from . import source as S,kernel as K,contract as C


def row(kind,text,identifier='000'):
    r={'kind':kind,'root_assignment_ordinal':0,'native_root_ID':S.token(identifier),'source_string':S.token(text),'source_tuple_position':0}
    if kind=='root_SMILES':r['all_original_conformer_relationships']=1
    else:r.update(secondary_assignment_ordinal=0,global_conformer_assignment_ordinal=0,native_conformer_ID=S.token('0'))
    return r


class Boundaries(unittest.TestCase):
    functions=None;chem=None
    def test_author_MolBlock_invocation_and_original_stereo_isotope_key_objects(self):
        calls=[];chem=self.chem
        class Proxy:
            def MolFromMolBlock(self,*args,**kwargs):calls.append(kwargs);return chem.MolFromMolBlock(*args,**kwargs)
            def MolToInchiKey(self,*args,**kwargs):return chem.MolToInchiKey(*args,**kwargs)
        keys=[]
        for smiles in ('C[C@H](F)Cl','C[C@@H](F)Cl','CO','[13CH3]O'):
            block=chem.MolToMolBlock(chem.MolFromSmiles(smiles));graph=K.graph_key(block,self.functions,Proxy())
            source,errors=self.functions['source_smiles_keys']({'original_root_SMILES':smiles})
            self.assertFalse(errors);self.assertEqual(graph,source);keys.append(graph)
        self.assertTrue(all(c=={'removeHs':False} for c in calls));self.assertNotEqual(keys[0],keys[1]);self.assertNotEqual(keys[2],keys[3])

    def test_original_native_IDs_full_source_token_and_relationship_preserved(self):
        original=row('conformer_MolBlock','not a MolBlock','000');before=copy.deepcopy(original)
        result=K.normalize(original,self.functions,self.chem);self.assertEqual(result['source'],before)
        self.assertTrue(result['has_any_unknown']);self.assertFalse(result['unknown_is_chemical_exclusion']);self.assertFalse(result['full_key_and_WP5_pairs'])
        relation=S.relationship(original,False);self.assertEqual(relation['native_root_ID']['text'],'000');self.assertEqual(relation['native_conformer_ID']['text'],'0')
        self.assertEqual(relation['source_string_metadata']['sha256'],original['source_string']['sha256']);self.assertNotIn('text',relation['source_string_metadata'])
        self.assertEqual(relation['secondary_assignment_ordinal'],0);self.assertFalse(relation['selected_for_key_projection'])
        strange=S.token('a\ud800');self.assertFalse(strange['strict_UTF8_valid']);self.assertEqual(strange['text'],'a\ud800')
        unknown=K.normalize(row('root_SMILES',''),self.functions,self.chem);self.assertTrue(unknown['has_any_unknown']);self.assertFalse(unknown['full_key_and_WP5_pairs'])

    def test_mismatch_unknown_axes_and_fixed_without_replacement_sample(self):
        from .run import comparison
        a=K.normalize(row('root_SMILES','CCO'),self.functions,self.chem)
        b=K.normalize(row('conformer_MolBlock',self.chem.MolToMolBlock(self.chem.MolFromSmiles('CCN'))),self.functions,self.chem)
        self.assertEqual(comparison(a,b),'ROOT_SMILES_AND_NATIVE_MOLBLOCK_FULL_KEYS_DIFFER')
        self.assertEqual(len({p[0] for p in a['full_key_and_WP5_pairs']+b['full_key_and_WP5_pairs']}),2)
        unknown=K.normalize(row('conformer_MolBlock',''),self.functions,self.chem)
        self.assertEqual(comparison(a,unknown),'UNKNOWN_NOT_COMPARABLE');self.assertEqual(comparison(None,b),'UNKNOWN_NOT_COMPARABLE')
        first=S.selected('profile');self.assertEqual(first,S.selected('profile'));self.assertEqual(len(first),C.PILOT_N)
        self.assertTrue(all(type(n) is int and 0<=n<C.CONF_N for n in first));self.assertIsNone(S.selected('full'))
