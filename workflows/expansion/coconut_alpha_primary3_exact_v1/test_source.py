"""Five stdlib metadata tests; no native initialization or chemistry calls."""
import copy
import json
import os
import unittest
from pathlib import Path
from . import prepare as P


class Source(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt_ref=P.S.pin(Path(os.environ.get('PRIMARY3_EXACT_RECEIPT',str(P.RECEIPT))))
        cls.account_ref=P.S.pin(Path(os.environ.get('PRIMARY3_EXACT_ACCOUNT',str(P.ACCOUNT))))
        _,_,cls.consumer,_=P.context(cls.receipt_ref)

    def identity(self,composition):
        return dict(source_id='entries:fixture:1:1:composition:0',role='ALL_SOURCE_NATIVE_SPLIT_UNKNOWN',
                    subdataset='entries',inchikeys=[],non_h_composition=composition)

    def test_original_composition_only_is_exact_lookup_not_lower_bound(self):
        small=[[6,41],[8,27]];larger=[[6,42],[8,27]]
        keys=self.consumer.identity_keys(self.identity(small))
        self.assertEqual(keys,[('composition',json.dumps(small,separators=(',',':')))])
        self.assertNotEqual(keys,self.consumer.identity_keys(self.identity(larger)))
        self.assertEqual({k for k,_ in keys},{'composition'})

    def test_original_consumer_forbids_provenance_or_target_columns_in_strict5(self):
        for name in ('original_entry_id','target','source_reference'):
            row=self.identity([[6,1]]);row[name]='fixture'
            with self.subTest(name=name),self.assertRaises(ValueError):
                self.consumer.identity_keys(row)

    def test_original_source_composition_requires_sorted_positive_non_H_counts(self):
        for vector in ([],[[1,2]],[[6,0]],[[6,True]],[[8,1],[6,1]],[[6,1],[6,2]]):
            with self.subTest(vector=vector),self.assertRaises(ValueError):
                self.consumer.identity_keys(self.identity(vector))

    def test_actual_parent_accounting_rejects_wrong_UID_exit_or_receipt(self):
        original=P.S.load(self.account_ref)
        self.assertEqual(P.accounting(original,self.receipt_ref)['JobIDRaw'],'1885152')
        variants=[]
        wrong=copy.deepcopy(original);wrong['uid']=1278;variants.append(wrong)
        wrong=copy.deepcopy(original);wrong['actual_sacct']=wrong['actual_sacct'].replace('COMPLETED|0:0','COMPLETED|1:0');variants.append(wrong)
        wrong=copy.deepcopy(original);wrong['receipt']=dict(self.receipt_ref,sha256='0'*64);variants.append(wrong)
        for wrong in variants:
            with self.subTest(wrong=wrong),self.assertRaises(ValueError):P.accounting(wrong,self.receipt_ref)

    def test_actual_three_complete_fields_bind_exact_compositions_and_keep_UNKNOWN(self):
        result=P.build(self.receipt_ref,self.account_ref)
        rows=result['proposed_original_strict5_rows'];bindings=result['source_bindings']
        self.assertEqual([r['original_entry_id'] for r in bindings],list(P.IDS))
        self.assertEqual([r['non_h_composition'] for r in rows],
                         [[[6,46],[7,7],[8,12]],[[6,41],[8,27]],[[6,21],[8,8]]])
        for row,binding in zip(rows,bindings):
            self.assertEqual(set(row),{'source_id','role','subdataset','inchikeys','non_h_composition'})
            self.assertEqual(row['source_id'],binding['original_source_record_id']+':composition:0')
            self.assertEqual(row['inchikeys'],[])
            self.assertTrue(binding['formula_source_fields'] and binding['corroborating_complete_source_fields'])
            self.assertEqual(binding['original_graph_identity_resolution'],'UNKNOWN_UNCHANGED')
            self.assertFalse(binding['applied_to_index_or_candidates'])
        self.assertFalse(result['greater_or_equal_lower_bounds_created'])
        self.assertEqual(result['new_chemical_calls'],0)
        self.assertTrue(result['original_graph_UNKNOWN735_retained'])
        self.assertEqual(result['remaining_rows_outside_this_proposed_scope'],732)
        self.assertFalse(result['all735_exclusion_coverage_claimed'] or result['all11_ready'])


if __name__=='__main__':unittest.main()
