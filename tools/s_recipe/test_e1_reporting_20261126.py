"""New S reporting logic only: synthetic retained draws, no real outputs."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

from e1_reporting_20261126 import (
    AUTHORITY, KS, TASKS, TIMEBOX, decide, markdown, original_p_algebra,
    validate_missing, validate_source,
)


def cell(k, score=.4):
    run = 'S_R1_s0_3M' if k == 10 else f'S_E1_k{k}_s0_3M'
    output = '/synthetic/S/training/'+run
    group = 'S_R1_3M' if k == 10 else f'S_E1_k{k}_3M'
    frozen = {r:dict(complete=True, bootstrap_samples=1000, bootstrap_defined=1000,
        mean_normalized_improvement=score,
        paired_bootstrap=dict(groups={'task':['MID']}, seed=20261025, values=[score]*1000))
        for r in ('R1','R3')}
    full = dict(status='COMPLETE', rows=[dict(condition=group, task=t, seed_count=3,
        scratch_improvement_seed_mean=score) for t in TASKS], retained=dict(
            identity=dict(seed_mean_draws=True, groups={'task':['MID']}, bootstrap_seed=20261025,
                samples=1000, input_identity=dict(scratch='original_scratch', random_reference='original_reference')),
            completed_draws=1000, draws={group+'/'+t:dict(scratch_improvement_seed_mean=[score]*1000) for t in TASKS}))
    fits = [dict(ready=True, mode='full', pretraining_seed=0, task=t, seed=s,
        source_binding=dict(run=run, checkpoint=output+'/samples_3000000.pt',
            samples=3000000, source_training_budget=3000000)) for t in TASKS for s in (0,1,2)]
    return dict(native=dict(run=run, output=output, samples=3000000, seed=0, conformer_cap=k),
        evaluation=dict(run=run, samples=3000000), summary=dict(status='COMPLETE', samples=3000000, updates=93750),
        fits=fits, producer_closure_complete=True, frozen=frozen, full=full, full_group=group,
        sources=dict(frozen='synthetic_scores.json', full='synthetic_primary.json'))


class Reporting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        before = {k:sys.modules.get(k) for k in ('finetune_statistics','phychem_mfm.phase1.p_recipe_seed_policy')}
        cls.algebra = original_p_algebra(Path(__file__).resolve().parents[3]/'MFM_p_recipe')
        assert all(sys.modules.get(k) is value for k,value in before.items())

    def report(self, cells):
        return decide(dict(ready=True, authority=AUTHORITY), cells, self.algebra)

    def test_smallest_nonloss_and_unselected_win_needs_no_seed1(self):
        cells = {k:cell(k) for k in KS}
        cells[1] = cell(1, .35)
        cells[5] = cell(5, .45)
        result = self.report(cells)
        self.assertEqual(result['k_star'], 2)
        self.assertFalse(result['conditional_seed1_required'])
        self.assertEqual(result['new_bootstrap_draws'], 0)

    def test_selected_win_remains_provisional(self):
        cells = {k:cell(k) for k in KS}
        cells[1] = cell(1, .45)
        result = self.report(cells)
        self.assertEqual(result['provisional_k_star'], 1)
        self.assertIsNone(result['k_star'])
        self.assertEqual(result['status'], 'WAITING_CONDITIONAL_SEED1')
        self.assertIn('尚待', markdown(result))

    def test_both_panels_required(self):
        cells = {k:cell(k) for k in KS}
        cells[1]['full'] = cell(1, .35)['full']
        self.assertEqual(self.report(cells)['k_star'], 2)

    def test_missing_scientific_only_and_k10_required(self):
        timebox = dict(authority=TIMEBOX, failure_class='engineering', same_root_cause=True,
            root_cause='synthetic', unsuccessful_repairs=99, active_diagnosis_repair_seconds=99999)
        with self.assertRaises(ValueError): validate_missing(1,timebox)
        timebox['failure_class'] = 'scientific_method'
        validate_missing(1,timebox)
        with self.assertRaises(ValueError): validate_missing(10,timebox)
        timebox.update(unsuccessful_repairs=1,active_diagnosis_repair_seconds=14399)
        with self.assertRaises(ValueError): validate_missing(1,timebox)

    def test_reject_trajectory_and_layer_selection(self):
        source = cell(10)
        for changed in ('trajectory','layer','fit_source'):
            c = deepcopy(source)
            if changed == 'trajectory': c['native'].update(run='S_final_s0_9M',samples=9000000)
            elif changed == 'layer': c['evaluation']['layer'] = 3
            else: c['fits'][0]['source_binding']['source_training_budget'] = 9000000
            with self.assertRaises(ValueError):
                validate_source(10,c['native'],c['evaluation'],c['summary'],c['fits'])

    def test_off_by_default_and_no_ensemble_ci_substitution(self):
        cells = {k:cell(k) for k in KS}
        with self.assertRaises(ValueError): decide(dict(authority=AUTHORITY),cells,self.algebra)
        cells[1]['full']['retained']['identity']['seed_mean_draws'] = False
        with self.assertRaises(ValueError): self.report(cells)


if __name__ == '__main__':
    unittest.main()
