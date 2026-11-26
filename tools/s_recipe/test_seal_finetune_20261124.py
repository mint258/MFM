"""Only new synthetic retirement logic; no old result/model is read."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import torch
import seal_finetune_20261124 as seal


class SelectedArtifactRetention(unittest.TestCase):
    def state(self):
        return dict(epoch=50,phase='train',offset=0,order=[],selected_epoch=17,
            best_encoder={'w':torch.tensor([1.,2.])},best_head={'w':torch.tensor([3.])},
            encoder={'w':torch.tensor([-1.])},optimizer={'unused':True},
            normalization={'mean':torch.tensor([4.])}, initial_architecture={'kind':'test'},
            identity={'source':'synthetic'},best_error=.1)

    def test_completed_best_is_durable_before_only_continuation_retires(self):
        with tempfile.TemporaryDirectory(prefix='S_seal_newlogic_') as root:
            control=Path(root)
            output=control/'finetune_20261124/test'
            output.mkdir(parents=True)
            state=self.state()
            torch.save(state,output/'complete_state.pt')
            (output/'summary.json').write_text(json.dumps(dict(status='COMPLETE',job_id='1',
                detail=dict(selected_epoch=17))))
            closure=control/'closure.json'
            closure.write_text(json.dumps(dict(status='COMPLETE',job_id=1,exit_code=0,
                owned_descendants_exited=True,observer_joined=True)))
            (output/'prediction.pt').write_bytes(b'unchanged synthetic prediction')
            with patch.object(seal,'CONTROL',control):
                receipt=seal.seal(output,closure)
                self.assertEqual(seal.seal(output,closure),receipt)
            selected=torch.load(output/'selected_model.pt',weights_only=True)
            self.assertTrue(torch.equal(selected['encoder']['w'],state['best_encoder']['w']))
            self.assertTrue(torch.equal(selected['head']['w'],state['best_head']['w']))
            self.assertNotIn('optimizer',selected)
            self.assertFalse((output/'complete_state.pt').exists())
            self.assertEqual((output/'prediction.pt').read_bytes(),b'unchanged synthetic prediction')

    def test_partial_or_unjoined_producer_cannot_retire_any_state(self):
        for missing in ('owned_descendants_exited','observer_joined'):
            closure=dict(status='COMPLETE',exit_code=0,owned_descendants_exited=True,observer_joined=True)
            closure[missing]=False
            with self.assertRaises(ValueError):
                seal.require_closed({'status':'COMPLETE'},closure)
        with self.assertRaises(ValueError):
            seal.require_closed({'status':'COMPLETE'},dict(status='CONTINUATION_REQUIRED'))
        for key,value in (('epoch',49),('offset',32),('order',[0]),('best_encoder',{})):
            with self.assertRaises(ValueError):
                seal.selected_payload(dict(self.state(),**{key:value}))


if __name__=='__main__':
    unittest.main()
