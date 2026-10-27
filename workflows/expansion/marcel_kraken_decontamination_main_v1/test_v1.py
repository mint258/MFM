"""Exactly3 Main CPU synthetic methods; no real scientific DATA or chemistry."""
import copy,hashlib,tempfile,unittest
from pathlib import Path
from . import contract as C,projection as P,runtime as I
A='AAAAAAAAAAAAAA-BBBBBBBBBB-C';B='CCCCCCCCCCCCCC-DDDDDDDDDD-E'


def result(key,unknown=False):return {'identity_state':'TECHNICAL_UNRESOLVED' if unknown else 'MOLBLOCK_GRAPH_FULL_KEY_DERIVED',
    'has_any_unknown':unknown,'full_key_and_WP5_pairs':[[key,P.wp5_key(key)]]}


class Boundaries(unittest.TestCase):
    output_root=None
    def test_all_variants_native_ids_unknown_and_strict_consumer(self):
        root={'root_assignment_ordinal':0,'native_root_ID':P.token('0007/原生'),'all_original_conformer_relationships':2}
        confs=[({'root_assignment_ordinal':0,'native_root_ID':root['native_root_ID'],'native_conformer_ID':P.token('00'+str(i)),
            'global_conformer_assignment_ordinal':i,'secondary_assignment_ordinal':i},result(k)) for i,k in enumerate((A,B))]
        value=P.expected_union(root,result(A),confs);row,unknown=P.identity(value,'0'*64)
        self.assertFalse(unknown);self.assertEqual(row['inchikeys'],[A,B]);self.assertIn('0007/',row['source_id'])
        self.assertTrue(value['multiple_observed_full_keys']);self.assertEqual(value['comparison_counts'],
            {'FULL_SOURCE_KEYS_EQUAL':1,'ROOT_SMILES_AND_NATIVE_MOLBLOCK_FULL_KEYS_DIFFER':1})
        self.assertEqual(set(row),{'source_id','role','subdataset','inchikeys','non_h_composition'})
        self.assertEqual([v for k,v in P.identity_keys(row) if k=='full'],[A,B])
        changed=copy.deepcopy(confs);changed[1][1]['has_any_unknown']=True;changed[1][1]['identity_state']='TECHNICAL_UNRESOLVED'
        uncertain=P.expected_union(root,result(A),changed);kept,unknown=P.identity(uncertain,'0'*64)
        self.assertTrue(unknown);self.assertEqual(kept['inchikeys'],[A,B]);self.assertEqual(len(uncertain['all_selected_native_conformer_key_observations']),2)
        changed=copy.deepcopy(confs);changed[1][0]['native_root_ID']=P.token('7')
        with self.assertRaises(ValueError):P.expected_union(root,result(A),changed)
        changed=copy.deepcopy(confs);changed[1][0]['secondary_assignment_ordinal']=0
        with self.assertRaises(ValueError):P.expected_union(root,result(A),changed)

    def test_large_DATA_locator_is_not_small_metadata_and_bad_refs_reject(self):
        ref={'path':str(C.Q.ROOT/'artifacts/expansion/synthetic_never_opened.jsonl'),'bytes':232046820,'sha256':'a'*64}
        self.assertEqual(C.data_reference(ref),ref)
        for key,bad in (('bytes',True),('bytes',0),('bytes',-1),('sha256','a'*65),('path','relative.jsonl'),('path',str(C.Q.ROOT/'artifacts/../control/bad.json'))):
            value=dict(ref);value[key]=bad
            with self.assertRaises((ValueError,TypeError)):C.data_reference(value)
        with self.assertRaises(ValueError):C.data_reference(dict(ref,rows=1))
        with self.assertRaises(ValueError):P.strict_json(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):P.strict_json(b'{"a":NaN}')
        with self.assertRaises(ValueError):P.identity_keys({'source_id':'x','role':'all','inchikeys':[A],'provenance':{}})

    def test_actual_synthetic_file_SHA_EOF_reopen_and_consumer(self):
        # Main-only: test files live inside the allocation's new artifact output;
        # no Main filesystem alias or UID mock is used on another endpoint.
        parent=self.output_root or C.Q.ROOT/'artifacts/expansion'
        with tempfile.TemporaryDirectory(prefix='fixture3_',dir=parent) as directory:
            path=Path(directory)/'toy.jsonl';row={'source_id':'native:0001','role':'all','subdataset':'','inchikeys':[A,B],'non_h_composition':None}
            raw=P.canonical(row)+b'\n';path.write_bytes(raw)
            ref={'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            observed=list(I.rows(ref,lambda:None));self.assertEqual(observed[0][0],row);self.assertEqual(observed[0][1]['offset_bytes'],0)
            self.assertEqual(len(P.identity_keys(observed[0][0])),4)
            with self.assertRaises(ValueError):list(I.rows(dict(ref,sha256='0'*64),lambda:None))
            path.write_bytes(raw[:-1]);short={'path':str(path),'bytes':len(raw)-1,'sha256':hashlib.sha256(raw[:-1]).hexdigest()}
            with self.assertRaises(ValueError):list(I.rows(short,lambda:None))
            path.write_bytes(b'{"a":1,"a":2}\n');bad=path.read_bytes()
            with self.assertRaises(ValueError):list(I.rows({'path':str(path),'bytes':len(bad),'sha256':hashlib.sha256(bad).hexdigest()},lambda:None))
