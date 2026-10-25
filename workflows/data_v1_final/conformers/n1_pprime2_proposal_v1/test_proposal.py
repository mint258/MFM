"""Six pure proposal tests; no geometry generation, LMDB, or Slurm."""
import unittest
from plan import budget_evidence,choose_second,expanded_orders,proposed_seed,stable_key


class N1Tests(unittest.TestCase):
    def old(self):return {"origin":"accepted_sprime","candidate_key":"old:0","seed":1,"energy":0.,"x":0.}
    def candidate(self,x=.1,key=0,energy=1.):
        return {"origin":"data_v1_n1_pprime2","candidate_key":f"n1p2:{key}","seed":7,"candidate_id":key,
                "energy":energy,"x":x,"optimizer_code":0,"stereo_valid":True,"finite":True}
    def distance(self,a,b):return abs(a["x"]-b["x"])
    def test_distant_candidate_selected_before_below_threshold(self):
        result=choose_second(self.old(),[self.candidate(.1),self.candidate(.7,1,2.)],self.distance)
        self.assertEqual(result["second"]["candidate_id"],1);self.assertFalse(result["second"]["below_dedup_threshold"])
    def test_fallback_is_real_farthest_candidate_and_explicitly_flagged(self):
        result=choose_second(self.old(),[self.candidate(.1),self.candidate(.3,1,2.)],self.distance)
        self.assertEqual(result["second"]["candidate_id"],1);self.assertTrue(result["second"]["below_dedup_threshold"])
    def test_no_candidate_does_not_copy_old_geometry(self):
        self.assertIsNone(choose_second(self.old(),[],self.distance)["second"])
        with self.assertRaisesRegex(ValueError,"NEW_PROPOSAL_SEED"):
            choose_second(self.old(),[dict(self.candidate(),seed=1)],self.distance)
    def test_duplicate_candidate_identity_rejected(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_CANDIDATE"):
            choose_second(self.old(),[self.candidate(),self.candidate()],self.distance)
    def test_expanded_orders_stable_but_original_count_remains_one(self):
        old=self.old();second=self.candidate(.7);order=expanded_orders("m",old,second,self.distance)
        ids=[0,"n1p2:7:0"]
        self.assertEqual(order["fixed_random"],sorted(ids,key=lambda key:(stable_key(20261025,"m","uff_sprime",key),str(key))))
        self.assertEqual(set(order["energy"]),set(ids));self.assertEqual(order["diversity"][0],0)
        self.assertNotIn("conformer_id",old);self.assertEqual(proposed_seed("m"),proposed_seed("m"))
    def test_budget_is_disclosed_coarse_not_calibrated(self):
        report=budget_evidence([{},{}],[{"summary":{"elapsed_seconds":10.}}],160)
        self.assertEqual(report["candidate_optimization_calls_max"],20)
        self.assertAlmostEqual(report["coarse_scenario_core_hours"],320/3600)
        self.assertFalse(report["calibrated_n1_cost"])


if __name__=="__main__":unittest.main()
