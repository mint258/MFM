"""Guide branch tests; no real server commands or scientific updates."""
import copy,math,unittest
from message_bootstrap_v1 import assess_fallback,GROUPS
def fixture():
    v=dict(A2=[.10,.11],A3=[.08,.09],A4=[.06,.07]);return v,selection(v)
def selection(v):
    scores={name:sum(v[name])/2 for name in GROUPS}
    return dict(scores=scores,selected=min(GROUPS,key=lambda name:(scores[name],GROUPS.index(name))))
def previous():return dict(status='D3_MESSAGE_LAYER_CAPABILITY_FAILED',message_layers=1,local_RMSE_A_by_seed=[.05,.06],lookup_FULL2000_RMSE_A=.04)
class GuideFallbackTests(unittest.TestCase):
    def test_all_original_groups_fail_authorizes_one_message(self):
        v,s=fixture();r=assess_fallback(v,s,.04,1);self.assertEqual(r['selected_original_LR_group'],'A4')
        self.assertFalse(any(r['original_multitask_denoising_capable_by_group'].values()))
    def test_any_capable_original_group_blocks_even_if_other_gates_fail(self):
        v,s=fixture();v['A3']=[.02,.03]
        with self.assertRaisesRegex(AssertionError,'DOES_NOT_AUTHORIZE'):assess_fallback(v,selection(v),.04,1)
    def test_only_one_seed_below_lookup_does_not_make_group_capable(self):
        v,s=fixture();v['A4']=[.03,.05];r=assess_fallback(v,selection(v),.04,1)
        self.assertFalse(r['original_multitask_denoising_capable_by_group']['A4'])
    def test_lookup_equality_is_not_pass(self):
        v,s=fixture();v['A4']=[.04,.04];assess_fallback(v,selection(v),.04,1)
    def test_tie_uses_original_lower_LR_order(self):
        v,s=fixture();v={name:[.06,.06] for name in GROUPS};r=assess_fallback(v,selection(v),.04,1)
        self.assertEqual(r['selected_original_LR_group'],'A2')
    def test_different_selected_LR_or_scores_rejected(self):
        v,s=fixture()
        for changed in [dict(s,selected='A2'),dict(s,scores=dict(s['scores'],A4=.001))]:
            with self.subTest(changed=changed),self.assertRaisesRegex(AssertionError,'SELECTION_DIFFERS'):assess_fallback(v,changed,.04,1)
    def test_invalid_threshold_and_layers_rejected(self):
        v,s=fixture()
        for threshold,layers in [(math.nan,1),(math.inf,1),(0.,1),(-1.,1),(.04,0),(.04,3)]:
            with self.subTest(threshold=threshold,layers=layers),self.assertRaises(AssertionError):assess_fallback(v,s,threshold,layers)
    def test_incomplete_or_nonfinite_results_rejected(self):
        v,s=fixture();cases=[]
        q=copy.deepcopy(v);q.pop('A3');cases.append(q)
        for values in [[.06],[.06,.07,.08],[math.nan,.07],[math.inf,.07],[-.01,.07]]:
            q=copy.deepcopy(v);q['A4']=values;cases.append(q)
        for q in cases:
            with self.subTest(q=q),self.assertRaises(AssertionError):assess_fallback(q,s,.04,1)
    def test_two_messages_require_actual_failed_message1_capability(self):
        v,s=fixture();self.assertEqual(assess_fallback(v,s,.04,2,previous())['message_layers'],2)
        cases=[None,dict(previous(),status='D3_PHASE_COMPLETE_AWAITING_SCIENTIFIC_GATE'),dict(previous(),message_layers=2),
            dict(previous(),local_RMSE_A_by_seed=[.02,.03]),dict(previous(),lookup_FULL2000_RMSE_A=.05)]
        for p in cases:
            with self.subTest(p=p),self.assertRaises(AssertionError):assess_fallback(v,s,.04,2,p)
    def test_message1_one_seed_failure_or_equality_permits_layer2(self):
        v,s=fixture()
        for values in [[.03,.05],[.04,.03]]:
            self.assertEqual(assess_fallback(v,s,.04,2,dict(previous(),local_RMSE_A_by_seed=values))['message_layers'],2)
if __name__=='__main__':unittest.main()
