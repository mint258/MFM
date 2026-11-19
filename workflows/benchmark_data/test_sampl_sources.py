import json
import unittest
from .sampl_sources import build_overlay

class SourceIdentityTests(unittest.TestCase):
    def test_local_compound_ids_reused_between_challenges_are_not_merged(self):
        raw=[(0,{'dataset':'SAMPL6','rawdataID':'r','molid':'SM01','Exp_Macro_pKa_processed':'1.2345678901234567'}),
             (1,{'dataset':'SAMPL7','rawdataID':'r','molid':'SM01','Exp_Macro_pKa_processed':'9.87'})]
        unified=[(12,{'dataset':'SAMPL6','rawdataID':'r','molid':'global-six'}),
                 (31,{'dataset':'SAMPL7','rawdataID':'r','molid':'global-seven'})]
        domains={12:{'record_id':'pka:12','domain_eligible':True,'model_smiles':'CCC'},
                 31:{'record_id':'pka:31','domain_eligible':False,'model_smiles':'CC[NH3+]'}}
        out=build_overlay(raw,unified,domains)
        self.assertEqual([json.loads(r['unified_links_json'])[0]['unified_global_molid'] for r in out],['global-six','global-seven'])
        self.assertEqual(out[0]['original_pKa_lexeme'],'1.2345678901234567')
        self.assertEqual([r['source_row'] for r in out],[0,1])
        self.assertTrue(all(r['benchmark_role'].startswith('NOT_FROZEN') for r in out))

    def test_excluded_unmatched_and_multiple_links_remain_explicit(self):
        raw=[(2,{'dataset':'SAMPL6','rawdataID':'excluded'}),(3,{'dataset':'SAMPL6','rawdataID':'absent'})]
        unified=[(5,{'dataset':'SAMPL6','rawdataID':'excluded','exclude_flag':' EXCLUDE '}),
                 (6,{'dataset':'SAMPL6','rawdataID':'excluded','exclude_flag':''})]
        out=build_overlay(raw,unified,{})
        self.assertEqual(len(out),2)
        self.assertEqual(out[0]['link_state'],'MULTIPLE_UNIFIED_SOURCE_ID_MATCHES_RETAINED')
        links=json.loads(out[0]['unified_links_json'])
        self.assertEqual([r['source_link_state'] for r in links],['AUTHOR_EXCLUDED','CURATED_DOMAIN_LINK_UNAVAILABLE'])
        self.assertEqual(out[1]['link_state'],'NO_UNIFIED_SOURCE_ID_MATCH')
        self.assertFalse(out[0]['atomic_site_labels_inferred'])

if __name__=='__main__':unittest.main()