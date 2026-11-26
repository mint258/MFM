"""Only the new opt-in population transformation, no old-result replay."""
import unittest
import copy
import json
import numpy as np
from extension_population_20261124 import conformer_rows, intersect_saved_mids
from extension_training_20261124 import validate as validate_training, REPO, CONTROL
from s_data import paired_choices


class ExtensionPopulation(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(molecule_id='a', PM7=[8, 2, 9, 1, 5, 7], UFF=[4, 1]),
                     dict(molecule_id='b', PM7=[3], UFF=[6])]

    def test_disabled_identity_and_no_rng_consumption(self):
        self.assertIs(conformer_rows(self.rows), self.rows)
        rows = [dict(row, molecule_index=i) for i, row in enumerate(self.rows)]
        a, b = np.random.default_rng(0), np.random.default_rng(0)
        original = paired_choices(a, rows, 'PM7', seed=0, start=128, count=1000)
        disabled = paired_choices(b, conformer_rows(rows), 'PM7', seed=0, start=128, count=1000)
        self.assertEqual(original, disabled)
        self.assertEqual(a.bit_generator.state, b.bit_generator.state)
        # A cap changes only the keyed conformer draw, never molecule/ordinal.
        candidate = paired_choices(np.random.default_rng(0), conformer_rows(rows, 1),
                                   'PM7', seed=0, start=128, count=1000)
        self.assertEqual([(m,o) for m,_,o in original], [(m,o) for m,_,o in candidate])

    def test_nested_rank_prefix_without_padding_or_uff_change(self):
        views = {k: conformer_rows(self.rows, k) for k in (1, 2, 5, 10)}
        for left, right in ((1, 2), (2, 5), (5, 10)):
            for a, b in zip(views[left], views[right]):
                self.assertEqual(a['PM7'], b['PM7'][:len(a['PM7'])])
        self.assertEqual(views[10], self.rows)
        self.assertEqual(views[5][1]['PM7'], [3])
        self.assertIs(views[1][0]['UFF'], self.rows[0]['UFF'])
        self.assertEqual(self.rows[0]['PM7'], [8, 2, 9, 1, 5, 7])

    def test_subset_uses_saved_membership_and_original_order(self):
        self.assertEqual(intersect_saved_mids(self.rows, ['b', 'absent']), [self.rows[1]])
        self.assertEqual(intersect_saved_mids(self.rows, ['b', 'a']), self.rows)
        with self.assertRaises(ValueError):
            intersect_saved_mids(self.rows, ['a', 'a'])

    def test_reject_unregistered_caps_and_duplicate_source(self):
        for cap in (True, 0, 3, 11):
            with self.assertRaises(ValueError):
                conformer_rows(self.rows, cap)
        with self.assertRaises(ValueError):
            conformer_rows([dict(PM7=[2, 2])], 1)


class ExtensionRecipeBinding(unittest.TestCase):
    def test_only_registered_population_change_enters_original_recipe(self):
        baseline = json.loads((REPO/'configs/s_recipe/screening/S-R1.json').read_text())
        population = json.loads((REPO/'configs/s_recipe/population.json').read_text())
        population['conformer_cap'] = 1
        c = dict(baseline, extension_kind='E1', conformer_cap=1,
            extension_authority='docs/s_recipe/USER_DIRECTIVE_20261123.md',
            population='new_registered_population.json', run='S_E1_k1_s0_3M',
            output=str(CONTROL/'training/S_E1_k1_s0_3M'))
        self.assertIs(validate_training(c, baseline, population), c)
        for key, value in (('disabled',[]),('lr',0.001),('normalization','refitted'),
                ('initialization','other.pt'),('seed',1),('samples',9000000),
                ('batch_size',16),('output',baseline['output'])):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_training(dict(c, **{key:value}), baseline, population)
        other = copy.deepcopy(population)
        other['validation'] = 'different_VAL.parquet'
        with self.assertRaises(ValueError):
            validate_training(c, baseline, other)

    def test_subset_keeps_frozen9M_and_uses_actual_P_intersection_size(self):
        baseline=json.loads((REPO/'configs/s_recipe/confirmation/S-final.json').read_text())
        population=json.loads((REPO/'configs/s_recipe/population.json').read_text())
        population.update(P_source_arm='T5',subset_seed=20261112,TRAIN_molecules=249000,
            original_P_selected_molecules=250000,
            selection='original_P_selected_MIDs_intersect_S_TRAIN')
        c=dict(baseline,extension_kind='molecule_subset',
            extension_authority='docs/s_recipe/USER_DIRECTIVE_20261123C.md',
            population='registered_T5_population.json',run='S_subset_T5_s0_9M',
            output=str(CONTROL/'training/S_subset_T5_s0_9M'))
        self.assertIs(validate_training(c,baseline,population),c)
        for key,value in (('subset_seed',0),('TRAIN_molecules',250001),
                ('original_P_selected_molecules',500000),('selection','resampled_S_TRAIN')):
            with self.subTest(key=key),self.assertRaises(ValueError):
                validate_training(c,baseline,dict(population,**{key:value}))


if __name__ == '__main__':
    unittest.main()
