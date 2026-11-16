import unittest
from types import SimpleNamespace
from phychem_mfm.phase1.p_recipe import selected_training_fields, normalized_field_weights

class FollowupFieldSelection(unittest.TestCase):
    def registry(self):
        fields=[SimpleNamespace(name='P.'+str(i)) for i in range(109)]
        return SimpleNamespace(enabled=lambda groups: fields)
    def test_disabled_preserves_order_and_exact_selection(self):
        self.assertEqual(selected_training_fields(self.registry(),{}),tuple('P.'+str(i) for i in range(109)))
        self.assertEqual(selected_training_fields(self.registry(),{},['P.12']),('P.12',))
    def test_ten_exclusions_remove_only_named_columns(self):
        exclusions=['P.'+str(i) for i in range(10)]
        names=selected_training_fields(self.registry(),{'excluded_fields':exclusions})
        self.assertEqual(names,tuple('P.'+str(i) for i in range(10,109)))
        weights=normalized_field_weights({n:'family' for n in names})
        self.assertTrue(all(abs(float(v)-1/99)<1e-8 for v in weights.values()))
    def test_unknown_field_fails_before_training(self):
        with self.assertRaisesRegex(ValueError,'Unknown excluded'):
            selected_training_fields(self.registry(),{'excluded_fields':['typo']})
if __name__=='__main__':unittest.main()