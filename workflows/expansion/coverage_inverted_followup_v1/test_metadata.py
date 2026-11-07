"""Contract/identity checks; actual augmented native equivalence occurs inside the producer."""
import pathlib,struct,unittest
from . import admission,general_workers
from ..expansion_coverage_followup_v1 import general_workers as original
class Tests(unittest.TestCase):
    def test_only_native_provider_imports_changed(self):
        new=pathlib.Path(general_workers.__file__).read_text()
        back=new.replace('from ..exact_nn_inverted_cpp_v1 import backend','from ..exact_nn_popcount_cpp_v1 import backend').replace('from ..exact_nn_inverted_production_v1 import authority','from ..exact_nn_popcount_production_v1 import authority')
        self.assertEqual(back,pathlib.Path(original.__file__).read_text())
    def test_complete_after_contract_and_reject_partial(self):
        ref={'path':'original','bytes':1,'sha256':'f'*64}
        m=dict(status='COMPLETE',targets_present=False,schema='EXPANSION_EXACT_AUGMENTED_REFERENCE_V1',base_reference_manifest=ref,added_molecules=2500000,molecules=3696122,original_reference_ordinals_preserved_as_exact_prefix=True)
        self.assertEqual(general_workers.target_contract(m,{},'after',ref),3696122)
        for key,value in [('molecules',1196122),('added_molecules',1),('original_reference_ordinals_preserved_as_exact_prefix',False),('targets_present',True)]:
            wrong=dict(m);wrong[key]=value
            with self.assertRaises(ValueError):general_workers.target_contract(wrong,{},'after',ref)
    def test_query_boundaries_and_repeat_identity(self):
        fetched=[]
        def fetch(i):fetched.append(i);return bytes([i])*256
        cases=admission.query_cases([bytes([i])*256 for i in range(64)],fetch,20,10)
        self.assertEqual(fetched,[0,1,9,10,11,19]);self.assertEqual(len(cases),80)
        self.assertEqual([r[1]for r in cases[-6:]],[r[1]for r in cases[:6]])
        self.assertEqual(cases[70][1],bytes(256));self.assertEqual(cases[71][1],bytes([255])*256)
    def test_changed_counters_with_same_total_rejected(self):
        one=dict(score=0.5,reference_ordinal=1,score_numerator=1,score_denominator=2,evaluated_references=7,strictly_bound_pruned_references=3,reference_molecules=10,searched_popcount_groups=(2,3))
        admission.equal(one,dict(one),10)
        bad=dict(one,evaluated_references=6,strictly_bound_pruned_references=4)
        with self.assertRaises(ValueError):admission.equal(one,bad,10)
    def test_f64_and_fullN_are_not_weakened(self):
        one=dict(score=0.0,reference_ordinal=0,score_numerator=0,score_denominator=1,evaluated_references=10,strictly_bound_pruned_references=0,reference_molecules=10,searched_popcount_groups=(1,))
        for bad in (dict(one,score=-0.0),dict(one,reference_molecules=9),dict(one,score=0)):
            with self.assertRaises(ValueError):admission.equal(one,bad,10)
if __name__=='__main__':unittest.main()
