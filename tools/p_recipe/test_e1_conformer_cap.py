"""Only E1 cap logic: published rank, D5 exclusion and unchanged off path."""
import unittest
import numpy as np
from phychem_mfm.phase1.p_recipe_conformers import training_conformer_cap
from phychem_mfm.phase1.v31_loader import MFM4Dataset
from phychem_mfm.phase1.p_recipe_data import dataset_configuration
from unittest.mock import patch

class E1ConformerTests(unittest.TestCase):
    def data(self, cap):
        d=MFM4Dataset.__new__(MFM4Dataset)
        d.source="PM7";d.order="fixed_random";d.k=cap;d.diagnostic=False
        d.pprime=False;d.evaluation=False;d.indices=np.array([0,1,2])
        order=np.array([4,1,3,0,2])
        records={i:{7:order.copy(),13:np.array([False,False,i==2,False,True])} for i in d.indices}
        records[1]={7:np.array([1,0]),13:np.array([False,False])}
        d.record=lambda kind,m:records[m]
        d.read=lambda m,c:(m,c)
        return d
    def config(self):
        return dict(root="unused",source="PM7",order="fixed_random",training_view="view",normalizations="norm")
    def test_off_preserves_draws_and_rng_bytes(self):
        c=self.config();a=self.data(10);b=self.data(training_conformer_cap(c))
        ra=np.random.default_rng(0);rb=np.random.default_rng(0)
        self.assertEqual([a.sample(ra) for _ in range(1000)],[b.sample(rb) for _ in range(1000)])
        self.assertEqual(ra.bit_generator.state,rb.bit_generator.state)
    def test_nested_published_order_and_D5_before_cap(self):
        for m in [0,1,2]:
            all_allowed=self.data(10).choices(m)
            previous=set()
            for k in [1,2,5,10]:
                got=self.data(k).choices(m)
                np.testing.assert_array_equal(got,all_allowed[:k])
                self.assertLessEqual(previous,set(got));previous=set(got)
                self.assertNotIn(4,got)
            self.assertEqual(len(self.data(10).choices(1)),2)
        self.assertEqual(self.data(1).choices(0).tolist(),[1])
    def test_only_training_cap_changes_validation_stays_original(self):
        c=self.config()
        with patch("phychem_mfm.phase1.p_recipe_data.read_json",return_value={}),patch("phychem_mfm.phase1.p_recipe_data.train_indices",return_value=np.array([0,1])),patch("phychem_mfm.phase1.p_recipe_data.validation_indices",return_value=np.array([2])):
            off=dataset_configuration(c)
            explicit=dataset_configuration(dict(c,conformer_cap=None))
            for key in off:
                if isinstance(off[key],np.ndarray):np.testing.assert_array_equal(off[key],explicit[key])
                else:self.assertEqual(off[key],explicit[key])
            for k in [1,2,5,10]:
                self.assertEqual(dataset_configuration(dict(c,conformer_cap=k))["k"],k)
                self.assertEqual(dataset_configuration(dict(c,conformer_cap=k),validation=True)["k"],10)
    def test_reject_unregistered_values_and_order(self):
        for k in [True,0,3,11,1.0,"2"]:
            with self.assertRaises(ValueError):training_conformer_cap(dict(self.config(),conformer_cap=k))
        for edit in [dict(source="UFF"),dict(order="energy")]:
            with self.assertRaises(ValueError):training_conformer_cap(dict(self.config(),conformer_cap=2,**edit))
if __name__=="__main__":unittest.main()
