"""Exactly3 Main synthetic methods: source unions, guards and actual JSONL IO."""
import collections,copy,hashlib,tempfile,unittest
from pathlib import Path
from . import contract as C,projection as P,runtime as I
A='AAAAAAAAAAAAAA-BBBBBBBBBB-C';B='CCCCCCCCCCCCCC-DDDDDDDDDD-E'

def toy(ordinal=0):
    return {'source_id':'marcel_drugs_zip','original_CSV_physical_ordinal':ordinal,'original_name_fields':[{'state':'LITERAL_UTF8','text':'0007/Native','bytes':11}],
        'source_conformers':2,'source_profile_keys_observed_conformers':2,'source_full_keys_observed_conformers':2,
        'native_graph_observed_conformers':2,'native_graph_NOT_YET_EXAMINED_conformers':0,'unknown_observed_native_conformers':0,
        'native_source_key_mismatch_conformers':1,'native_source_key_comparison_known_conformers':2,'native_source_key_comparison_UNKNOWN_conformers':0,
        'distinct_original_SMILES_byte_variants':2,'original_multiple_SMILES_status':True,'source_SMILES_full_key_union':[A],
        'native_graph_full_key_union':[A,B],'conservative_all_observed_full_InChIKey_union':[A,B],
        'conservative_all_observed_WP5_key_union':sorted([P.wp5_key(A),P.wp5_key(B)]),
        'coverage':'FULL558002_NATIVE_1000_ACTUAL_C0_ADOPTED557002_NEW_ALL_VARIANTS_AND_NAMES_RETAINED','representative_chosen':False,
        'native_graph_full_or_pool_release':False,'original_source_profile_count_field_retained_as_legacy_alias':True,'unknown_or_mismatch_is_chemical_exclusion':False}

class Boundaries(unittest.TestCase):
    output_root=None
    def test_complete_conservative_union_unknown_and_mass_guards(self):
        value=toy();before=copy.deepcopy(value);row,counts=P.project(value,0,C.ARCHIVE_SHA)
        self.assertEqual(value,before);self.assertEqual(row['inchikeys'],[A,B]);self.assertEqual(counts['mismatch_conformers'],1)
        self.assertEqual(set(row),{'source_id','role','subdataset','inchikeys','non_h_composition'});self.assertEqual(len(P.identity_keys(row)),4)
        kept,unknown=P.project(dict(value,unknown_observed_native_conformers=1),0,C.ARCHIVE_SHA)
        self.assertEqual(kept['inchikeys'],[A,B]);self.assertEqual(unknown['unresolved'],1)
        for changed in (dict(value,native_graph_observed_conformers=1),dict(value,conservative_all_observed_full_InChIKey_union=[A]),
                        dict(value,representative_chosen=True),dict(value,original_CSV_physical_ordinal=True)):
            with self.assertRaises(ValueError):P.project(changed,0,C.ARCHIVE_SHA)
        full={'conformers':558002,'native_unknown':0,'mismatch_conformers':126,'mismatch_names':31,'multi_SMILES_names':290,'unresolved':0}
        P.mass(75099,collections.Counter(full))
        with self.assertRaises(ValueError):P.mass(75099,collections.Counter(dict(full,mismatch_names=30)))
        with self.assertRaises(ValueError):P.mass(75098,collections.Counter(full))

    def test_large_DATA_and_strict_identity_container_guards(self):
        ref={'path':str(C.UNION),'bytes':87064062,'sha256':'a'*64};self.assertEqual(C.data_reference(ref),ref)
        for key,bad in (('bytes',True),('bytes',0),('bytes',-1),('sha256','a'*65),('path','relative'),('path',str(C.Q.ROOT/'artifacts/../control/bad'))):
            value=dict(ref);value[key]=bad
            with self.assertRaises((ValueError,TypeError)):C.data_reference(value)
        with self.assertRaises(ValueError):C.data_reference(dict(ref,rows=75099))
        with self.assertRaises(ValueError):P.strict_json(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):P.strict_json(b'{"a":NaN}')
        with self.assertRaises(ValueError):P.identity_keys({'source_id':'x','role':'all','inchikeys':[A],'native':{}})

    def test_actual_synthetic_same_FD_SHA_EOF_projection_and_readback(self):
        parent=self.output_root or C.Q.ROOT/'artifacts/expansion'
        with tempfile.TemporaryDirectory(prefix='drugs_decontam_source3_',dir=parent) as directory:
            root=Path(directory);source=root/'source.jsonl';rows=[toy(0),toy(1)];body=b''.join(P.canonical(v)+b'\n' for v in rows);source.write_bytes(body)
            ref={'path':str(source),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()};before=I.file_guard(ref)
            actual=list(I.rows(ref,lambda:None));self.assertEqual([r for r,_ in actual],rows);self.assertEqual(actual[1][1]['offset_bytes'],len(P.canonical(rows[0]))+1)
            target=root/'identities.jsonl';projected=[P.project(v,i,C.ARCHIVE_SHA)[0] for i,(v,_) in enumerate(actual)];raw=b''.join(P.canonical(v)+b'\n' for v in projected);target.write_bytes(raw)
            outref={'path':str(target),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            seen=list(I.rows(outref,lambda:None));self.assertEqual([r for r,_ in seen],projected);self.assertEqual(sum(len(P.identity_keys(r)) for r,_ in seen),8)
            self.assertEqual(I.file_guard(ref),before)
            with self.assertRaises(ValueError):list(I.rows(dict(ref,sha256='0'*64),lambda:None))
            link=root/'link.jsonl';link.symlink_to(source)
            with self.assertRaises(ValueError):I.file_guard(dict(ref,path=str(link)))
            source.write_bytes(body[:-1]);short={'path':str(source),'bytes':len(body)-1,'sha256':hashlib.sha256(body[:-1]).hexdigest()}
            with self.assertRaises(ValueError):list(I.rows(short,lambda:None))
if __name__=='__main__':unittest.main()
