"""Exactly3 meaningful synthetic boundaries, no chemistry kernel or old DATA."""
import copy,hashlib,sqlite3,tempfile,unittest
from pathlib import Path
from workflows.expansion.decontamination import identity_keys
from . import projection as P,io as I,tdc as T,contract as C
K1='AAAAAAAAAAAAAA-BBBBBBBBBB-C';K2='CCCCCCCCCCCCCC-DDDDDDDDDD-E'

class Boundaries(unittest.TestCase):
    workspace=None
    def test_local_multikey_original_roles_composition_and_unknown(self):
        review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root',
            'closed_local6_all44_and_exact2_conservative_identity_only_authorized':True,
            'original_repository_checker_and_six_software_DATA_authorized':True,
            'exact_407_closed_physical_C0_embedded_triples_discovered_on_CPU_only_authorized':True,'global_pool_release_authorized':False}
        self.assertEqual(C.generic_review(review),review)
        for status in ('APPROVED','PENDING_ROOT_REVIEW','USER_AUTHORIZED'):
            with self.assertRaises(Exception):C.generic_review({**review,'status':status})
        with self.assertRaises(Exception):C.generic_review({**review,'global_pool_release_authorized':True})
        row={'dataset':'v1_all_roles_and_embargo','source_id':'physical-row','role':'SOURCE_ROUTINE','inchikeys':[K2,K1],
            'non_h_composition_json':'[[6,2],[8,1]]','memberships':['SOURCE_FULL','SOURCE_ROUTINE'],
            'missing_full_key':False,'missing_identity_or_composition':False,'unresolved_source_variant':True,'conservative_reason':None}
        before=copy.deepcopy(row);value,audit=P.local(row)
        self.assertIs(P.identity_keys,identity_keys);self.assertEqual(row,before);self.assertEqual(value['inchikeys'],[K2,K1])
        self.assertEqual(value['role'],'SOURCE_ROUTINE');self.assertEqual(value['non_h_composition'],[[6,2],[8,1]])
        self.assertTrue(audit['unresolved_source_variant']);self.assertEqual(audit['memberships'],['SOURCE_FULL','SOURCE_ROUTINE'])
        bad={**row,'inchikeys':[],'non_h_composition_json':None,'missing_full_key':True,'missing_identity_or_composition':True}
        with self.assertRaises(Exception):P.local(bad)
        value,audit=P.local({**bad,'dataset':'moleculenet_bbbp','role':'all','memberships':['all']});self.assertIsNone(value);self.assertTrue(audit['missing_identity_or_composition'])
        with self.assertRaises(Exception):P.local({**row,'role':'VAL'})

    def test_tdc_physical_id_exact_pair_and_conservative_unknown(self):
        source={'dataset':'tdc_admet_group_zip','member_name':'admet_group/solubility_aqsoldb/test.csv','endpoint':'solubility_aqsoldb',
            'original_split':'test','physical_record_ordinal':1159,'row_width':3,'assay_Y_decoded':False,'original_Drug_ID':{'text':'same-ID'},'original_Drug':{'text':'opaque'}}
        known={'source':source,'identity_state':'FULL_KEYS_DERIVED','full_InChIKeys':[K2,K1],'WP5_keys':[],'identity_errors':[]}
        result=P.tdc(source,known,'a'*64);self.assertEqual(result['inchikeys'],[K2,K1]);self.assertIsNone(result['non_h_composition'])
        second={**source,'physical_record_ordinal':1160};self.assertNotEqual(result['source_id'],P.tdc(second,{**known,'source':second},'a'*64)['source_id'])
        unknown={**known,'identity_state':'ORIGINAL_SMILES_UNRESOLVED','full_InChIKeys':[],'identity_errors':['UNCHANGED_ORIGINAL_ERROR']}
        accepted={'original_source':source,'original_result':unknown,'composition':[[6,6],[7,1],[8,1]]};before=copy.deepcopy(unknown)
        got=P.tdc(source,unknown,'a'*64,accepted);self.assertEqual(got['inchikeys'],[]);self.assertEqual(got['non_h_composition'],accepted['composition']);self.assertEqual(unknown,before)
        b=I.dump(source);reordered=dict(reversed(list(source.items())))
        binding={**accepted,'original_source':reordered,'original_source_record_bytes':len(b),'original_source_record_sha256':hashlib.sha256(b).hexdigest()}
        self.assertNotEqual(I.dump(reordered),b);T.bind_main_source(binding,source,unknown)
        with self.assertRaises(Exception):T.bind_main_source({**binding,'original_source_record_sha256':'0'*64},source,unknown)
        with self.assertRaises(Exception):P.tdc(source,unknown,'a'*64)
        with self.assertRaises(Exception):P.tdc(source,unknown,'a'*64,{**accepted,'original_result':{**unknown,'identity_errors':['OTHER']}})
        with self.assertRaises(Exception):P.source_key({**source,'member_name':'admet_group/solubility_aqsoldb/train_val.csv'})

    def test_chunk_durability_samefd_readback_and_duplicate_census(self):
        self.assertIsNotNone(self.workspace)
        class SyntheticBudget:
            def __init__(self):self.bytes=0
            def check(self,*a,**k):pass
            def charge(self,n):self.bytes+=n
        with tempfile.TemporaryDirectory(prefix='synthetic_strict7_',dir=self.workspace) as d:
            b=SyntheticBudget();w=I.Lines(Path(d)/'synthetic.jsonl',b)
            for i in range(4097):w.append({'source_id':str(i),'role':'SOURCE_TRAIN','subdataset':'','inchikeys':[K1,K2],'non_h_composition':None})
            ref=w.close();self.assertLessEqual(w.fsync_count,3);self.assertEqual(ref['rows'],4097);self.assertEqual(ref['bytes'],b.bytes)
            result=I.readback(ref,['SOURCE_TRAIN'],[''],b.check);self.assertEqual(result['rows'],4097)
            with self.assertRaises(Exception):list(I.rows({**{k:ref[k] for k in ('path','bytes','sha256')},'sha256':'0'*64},b.check))
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE seen(dataset TEXT,source_id TEXT,PRIMARY KEY(dataset,source_id)) WITHOUT ROWID')
        db.execute('INSERT INTO seen VALUES(?,?)',('source','physical'))
        with self.assertRaises(sqlite3.IntegrityError):db.execute('INSERT INTO seen VALUES(?,?)',('source','physical'))
        db.close()
