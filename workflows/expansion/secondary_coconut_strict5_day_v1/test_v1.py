"""Three actual synthetic boundaries, once in the same allocation before DATA."""
import json,tempfile,unittest
from pathlib import Path
from . import contracts as C,kernel as K,io as I
ROOT=None

def observation(table,fields,stored=None,derived=None,unresolved=None):
    names=('canonical_smiles',) if table=='molecules' else ('canonical_smiles','standardized_canonical_smiles','parent_canonical_smiles')
    variants=[];derived=derived or {};unresolved=unresolved or set();keys=set()
    for name in names:
        value=fields[name];v=derived.get(name,[]);keys.update(v)
        variants.append({'source_field':name,'state':'MISSING_OR_EMPTY' if value is None or value=='' else 'UNRESOLVED_ORIGINAL_VARIANT' if name in unresolved else 'KEYS_DERIVED','keys':v,'errors':[]})
    valid=[stored] if stored else [];union=sorted(set(valid)|keys)
    source={'source_table':table,'copy_block':1,'source_row_ordinal':1,'source_offset':0,'source_bytes':1,'source_row_sha256':'a'*64,'identity_fields_json':json.dumps(fields)}
    return {'source':source,'source_full_keys_valid':valid,'source_full_keys_invalid':[],'variant_observations':variants,'SMILES_derived_full_keys':sorted(keys),
      'conservative_full_key_union':union,'WP5_keys':[],'has_any_valid_full_key':bool(union),'unresolved_present_variants':len(unresolved),
      'missing_variants':sum(v['state']=='MISSING_OR_EMPTY' for v in variants),'stored_vs_computed_disagreement':bool(valid and keys and set(valid)!=keys)}

class Boundaries(unittest.TestCase):
    def test_union_disagreement_full_keys_and_original_strict5_rejection(self):
        a='LFQSCWFLJHTTHZ-UHFFFAOYSA-N';b='QUSNBJAOOMFDIB-UHFFFAOYSA-N'
        f={'id':'m','canonical_smiles':'CCO','standard_inchi_key':a,'standard_inchi':None}
        o=observation('molecules',f,a,{'canonical_smiles':[b]})
        result=K.project(o,[],None);self.assertEqual(result['keys'],sorted([a,b]));self.assertEqual(result['original_norm_counters']['disagreement'],1)
        row={'source_id':'original','role':'ALL_SOURCE_NATIVE_SPLIT_UNKNOWN','subdataset':'molecules','inchikeys':result['keys'],'non_h_composition':None}
        self.assertEqual(len(K.STATE['consumer'](row)),4)
        with self.assertRaises(ValueError):K.STATE['consumer'](dict(row,molecular_weight=46.))
        with self.assertRaises(ValueError):K.STATE['consumer'](dict(row,inchikeys=[a[:14]]))

    def test_original_atoms_formula_conflict_and_orphan_stays_unknown(self):
        parsed=K.composition('C[N](C)(C)C',K.STATE['Chem'],{'native_composition':K.STATE['native']})
        self.assertEqual(parsed['composition'],[[6,4],[7,1]])
        self.assertEqual(K.formula('2H2O.C6H6')['composition'],[[6,6],[8,2]])
        self.assertIsNone(K.formula('C6H6garbage')['composition'])
        f={'id':'e','molecule_id':None,'canonical_smiles':None,'standardized_canonical_smiles':None,'parent_canonical_smiles':None}
        o=observation('entries',f);r=K.project(o,[],None);self.assertFalse(r['covered']);self.assertEqual(r['FK_state'],'NULL')
        f=dict(f,molecule_id='absent');r=K.project(observation('entries',f),[],None);self.assertFalse(r['covered']);self.assertEqual(r['FK_state'],'ORPHAN')
        parent={'molecule_id':'absent','keys':[],'compositions':[[[6,2],[8,1]],[[6,2],[7,1]]],'locator':{'source':'synthetic_native_parent'}}
        r=K.project(observation('entries',f),[],parent);self.assertTrue(r['covered']);self.assertEqual(len(r['compositions']),2)
        self.assertEqual(r['FK_state'],'MATCHED');self.assertFalse(r['graph_identity_repaired'])

    def test_real_batched_jsonl_reopen_full_sha_and_no_future_source_small_cap(self):
        class Budget:
            def dispatch_check(self):pass
            def capacity(self,n=0):pass
        budget=Budget();C.need(ROOT is not None,'ACTUAL_FIXTURE_ROOT_REQUIRED')
        with tempfile.TemporaryDirectory(prefix='strict5_synthetic_',dir=ROOT) as tmp:
            path=Path(tmp)/'rows.jsonl';writer=I.Jsonl(path,budget)
            row={'source_id':'native','role':'ALL_SOURCE_NATIVE_SPLIT_UNKNOWN','subdataset':'molecules',
              'inchikeys':['LFQSCWFLJHTTHZ-UHFFFAOYSA-N'],'non_h_composition':None}
            for _ in range(8):writer.add(row)
            ref=writer.close();seen=list(I.read_jsonl(ref,budget));self.assertEqual(seen,[row]*8)
            for value in seen:K.STATE['consumer'](value)
            with path.open('ab') as f:f.write(b'changed')
            with self.assertRaises(ValueError):list(I.read_jsonl(ref,budget))
            large=Path(tmp)/'large.bin';large.write_bytes(b'x'*(3<<20));actual=I.pin(large)
            with I.held(actual,budget) as fd:self.assertGreater(actual['bytes'],2<<20)
            alias=Path(tmp)/'alias.bin';alias.symlink_to(large)
            with self.assertRaises(ValueError):
                with I.held(dict(actual,path=str(alias)),budget):pass
