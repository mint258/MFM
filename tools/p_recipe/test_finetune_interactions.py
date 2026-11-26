"""Only new paired four-way algebra and provenance gates."""
import copy
import unittest
from finetune_interactions import difference_in_differences


class InteractionTests(unittest.TestCase):
    def primary(self,condition,draws,point=0):
        return dict(status="COMPLETE",rows=[dict(condition=condition,task="t",
            scratch_improvement_seed_mean=point,ensemble_scratch_improvement=point)],
            retained=dict(identity=dict(groups={"t":["a","b"]},bootstrap_seed=20261025,
                samples=1000,input_identity=dict(scratch="same",random_reference="same")),
                draws={condition+"/t":dict(scratch_improvement=draws)}))

    def test_matched_draw_cancellation(self):
        z=[i/1000 for i in range(1000)]
        p=[self.primary("a",z,.7),self.primary("b",[0]*1000,.2),
           self.primary("c",z,.6),self.primary("d",[0]*1000,.1)]
        result=difference_in_differences(p,["a","b","c","d"],"t")
        self.assertEqual(result["ensemble_ci_lower"],0)
        self.assertEqual(result["ensemble_ci_upper"],0)
        self.assertAlmostEqual(result["delta_seed_mean"],0)
        self.assertEqual(result["new_bootstrap_draws"],0)

    def test_undefined_replicate_preserved(self):
        p=[self.primary(c,[i]*1000,i) for c,i in zip("abcd",[4,1,2,0])]
        p[2]["retained"]["draws"]["c/t"]["scratch_improvement"][1]=None
        result=difference_in_differences(p,list("abcd"),"t")
        self.assertEqual(result["bootstrap_defined"],999)
        self.assertEqual(result["delta_ensemble"],1)
        self.assertEqual(result["ensemble_ci_lower"],1)

    def test_mismatched_identity_and_draw_count_rejected(self):
        p=[self.primary(c,[0]*1000) for c in "abcd"]
        bad=copy.deepcopy(p);bad[3]["retained"]["identity"]["bootstrap_seed"]=1
        with self.assertRaises(ValueError):difference_in_differences(bad,list("abcd"),"t")
        bad=copy.deepcopy(p);bad[2]["retained"]["draws"]["c/t"]["scratch_improvement"].pop()
        with self.assertRaises(ValueError):difference_in_differences(bad,list("abcd"),"t")


if __name__=="__main__":unittest.main()
