"""New delivery boundaries: distinct estimands and no partial source consumption."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import budget_curve_delivery_20261127 as budget
from fullft_delivery_20261127 import aggregate, TASKS


class ReportingBoundaries(unittest.TestCase):
    def test_seed_mean_and_ensemble_intervals_remain_separate(self):
        point = 'example'
        primary = dict(status='COMPLETE', rows=[dict(condition=point, task=task, seed_count=3,
            scratch_improvement_seed_mean=.2, ensemble_scratch_improvement=.8) for task in TASKS],
            retained=dict(completed_draws=1000, identity=dict(seed_mean_draws=True),
                draws={point+'/'+task:dict(scratch_improvement=[.8]*1000,
                    scratch_improvement_seed_mean=[.2]*1000) for task in TASKS}))
        value = aggregate(primary, point)
        self.assertAlmostEqual(value['scratch_improvement_seed_mean'], .2)
        self.assertEqual(value['ensemble_ci'], [.8, .8])
        self.assertEqual(value['E1_seed_mean_ci'], [.2, .2])

    def test_missing_last_prefix_cannot_consume_any_original_scores(self):
        consumed = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def read(path):
                path = Path(path)
                if path.name == 'scores.json':
                    consumed.append(str(path))
                    raise AssertionError('Raw score consumption before all metadata closed')
                if path.name == 'record.json':
                    return dict(status='COMPLETE', exit_code=0, owned_descendants_exited=True, observer_joined=True)
                if path.name == 'command_exit.json': return dict(exit_code=0)
                if path.name.endswith('_resource_close.json'):
                    stem = path.name.removesuffix('_resource_close.json')
                    run, samples = stem.rsplit('__', 1)
                    return dict(status='OWN_RESOURCES_CLOSED', exit_code=0, run=run, samples=int(samples))
                run, boundary = path.parent.parent.name, int(path.parent.name.removeprefix('readout_'))
                if path.name == 'snapshot_gpu_status.json':
                    return dict(resource_handle=run+'__'+str(boundary))
                if (run, boundary) == (budget.RUNS[-1], 8000000):
                    raise FileNotFoundError('Final registered CPU producer is still missing')
                return dict(status='COMPLETE', owned_descendants_exited=True, run=run, samples=boundary,
                    native_record=str(root/'record.json'))
            with patch.object(budget, 'C', root), patch.object(budget, 'read', side_effect=read):
                with self.assertRaises(FileNotFoundError): budget.collect()
        self.assertEqual(consumed, [])
