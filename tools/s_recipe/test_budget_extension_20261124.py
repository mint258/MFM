"""New trajectory authorization only; synthetic metadata, no old fits/weights."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import budget_readouts_extension_20261124 as extension


class TrajectoryAuthorization(unittest.TestCase):
    def test_exact_new_points_require_full_original_endpoint_and_owned_exit(self):
        with tempfile.TemporaryDirectory(prefix='S_budget_newlogic_') as root:
            control=Path(root)
            output=control/'training/S_final_s0_9M'
            output.mkdir(parents=True)
            summary=output/'summary.json'
            summary.write_text(json.dumps(dict(status='COMPLETE',samples=9000000)))
            closure=control/'exit.json'
            closure.write_text(json.dumps(dict(owned_descendants_exited=True)))
            c=dict(readout_authority='docs/s_recipe/USER_DIRECTIVE_20261123C.md',
                samples=9000000,seed=0,run='S_final_s0_9M',output=str(output),
                training_closure_record=str(closure))
            with patch.object(extension,'CONTROL',control):
                for count in range(1000000,9000000,1000000):
                    (output/('samples_'+str(count)+'.pt')).write_bytes(b'synthetic')
                    extension.registered(c,count)
                for count in (0,500000,9000000,True):
                    with self.assertRaises(ValueError):extension.registered(c,count)
                for key,value in (('samples',3000000),('seed',1),('run','S_G1_s0_9M'),
                        ('readout_authority',None),('output',str(control/'foreign'))):
                    with self.assertRaises(ValueError):
                        extension.registered(dict(c,**{key:value}),1000000)
                summary.write_text(json.dumps(dict(status='TRAINING_COMPLETE_READOUT_PENDING',samples=9000000)))
                with self.assertRaises(ValueError):extension.registered(c,1000000)
                summary.write_text(json.dumps(dict(status='COMPLETE',samples=9000000)))
                closure.write_text(json.dumps(dict(owned_descendants_exited=False)))
                with self.assertRaises(ValueError):extension.registered(c,1000000)


if __name__=='__main__':unittest.main()
