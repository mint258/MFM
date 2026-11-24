import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from final_report_22B import require_closed,ReportNotReady
class E1ReportGateTest(unittest.TestCase):
 def test_pending_E1_blocks_before_old_result_or_weight_consumers(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'configs/p_recipe/E1_k_star.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(dict(status='TRAINING_RUNNING',k_star=None)))
   with patch('final_report_22B.validate_bundle',side_effect=AssertionError('Old primary consumer must not run')):
    with self.assertRaisesRegex(ReportNotReady,'E1'):require_closed(root)
if __name__=='__main__':unittest.main()
