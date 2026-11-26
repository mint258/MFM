"""New phase forecast on synthetic metadata; no old output/model is read."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import extension_output_budget_20261124 as budget


class ConcurrentOutputBudget(unittest.TestCase):
    def test_inflight_allocated_bytes_are_not_reserved_twice_and_pool_is_bounded(self):
        unit=1024**2
        with tempfile.TemporaryDirectory(prefix='S_output_budget_newlogic_') as root:
            c=Path(root)/'control'
            r=Path(root)/'repo'
            c.mkdir()
            (r/'configs/s_recipe/confirmation').mkdir(parents=True)
            (r/'configs/s_recipe/extensions_20261124').mkdir()
            (r/'configs/s_recipe/confirmation/S-B0.json').write_text(json.dumps(dict(run='B0',samples=9000000)))
            (r/'configs/s_recipe/extensions_20261124/k1_training.json').write_text(json.dumps(dict(run='k1',samples=3000000)))
            pulse=c/'pulse.json'
            pulse.write_text(json.dumps(dict(cursors={'B0':{'samples':6000000}})))
            (c/'current_state.json').write_text(json.dumps(dict(latest_pipeline_pulse=str(pulse))))
            active=c/'finetune_20261124/S_FT_test'
            active.mkdir(parents=True)
            (active/'complete_state.pt').write_bytes(b'synthetic state')
            physical=budget.allocated(active)
            ledger={'statistics':{'fit':dict(job_id=17,run='S_FT_test',mode='finetune')}}
            with patch.multiple(budget,CONTROL=c,REPO=r,GiB=unit),patch.object(budget,'claim_current',return_value=100*unit):
                result=budget.forecast(ledger,{17:'RUNNING'},incoming_bytes=unit,incoming_finetune=True)
                self.assertTrue(result['admitted'])
                self.assertEqual(result['planned_checkpoint_future'],2*unit)
                self.assertEqual(result['active_phase_future'],unit-physical)
                self.assertEqual(result['unfinished_FT_pool_peak'],2*unit)
                large=budget.forecast(ledger,{17:'RUNNING'},incoming_bytes=8*unit,incoming_finetune=True)
                self.assertFalse(large['admitted'])
            with self.assertRaises(ValueError):budget.unallocated_peak(-1,0)


if __name__=='__main__':unittest.main()
