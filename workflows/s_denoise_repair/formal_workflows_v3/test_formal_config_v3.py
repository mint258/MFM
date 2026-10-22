import copy
import json
import unittest
from pathlib import Path
from create_configurations_v3 import build
from formal_guard_v3 import validate_configuration


class ConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=build('B1',0,'A2')
        cls.protocol=json.loads(Path(cls.config['frozen_protocol_reference']['path']).read_text())

    def test_real_frozen_inputs_and_new_draft_pass(self):
        validate_configuration(self.config,self.protocol,development=True)
        self.assertEqual(self.config['expected_downstream']['linear_fit_cells'],492)
        self.assertEqual(self.config['expected_downstream']['reported_task_rows'],420)

    def test_draft_cannot_enter_formal_without_actual_gate(self):
        cfg=copy.deepcopy(self.config);cfg['status']='FORMAL_PROTOCOL_RESOLVED_AND_FROZEN'
        with self.assertRaises(KeyError):validate_configuration(cfg,self.protocol,development=False)

    def test_epoch_noise_cannot_be_disabled(self):
        cfg=copy.deepcopy(self.config);cfg['views']['noise_seed_includes_epoch']=False
        with self.assertRaises(AssertionError):validate_configuration(cfg,self.protocol,development=True)

    def test_backbone_and_optimizer_cannot_drift(self):
        for key in ['backbone','optimizer']:
            cfg=copy.deepcopy(self.config)
            if key=='backbone':cfg['model']['backbone']['layers']+=1
            else:cfg['training']['optimizer']['weight_decay']+=.01
            with self.assertRaises(AssertionError):validate_configuration(cfg,self.protocol,development=True)

    def test_gaussian_scale_and_fixed_S_tasks_cannot_drift(self):
        for key in ['sigma','angle','tasks','balancer']:
            cfg=copy.deepcopy(self.config)
            if key=='sigma':cfg['training']['loss']['denoise_sigma']=.2
            elif key=='angle':cfg['training']['loss']['geom_angle_std_deg']=1.
            elif key=='tasks':cfg['training']['loss_policy']['structural_tasks']=['denoise_eps_mse']
            else:cfg['dynamic_balancer_enabled']=True
            with self.assertRaises(AssertionError):validate_configuration(cfg,self.protocol,development=True)

    def test_four_conditions_preserve_seed_and_horizon(self):
        for kind in ['B1','B3']:
            for seed in [0,1]:
                cfg=build(kind,seed,'A2')
                self.assertEqual(cfg['seed'],seed);self.assertEqual(cfg['epochs'],1 if kind=='B1' else 3)


if __name__=='__main__':unittest.main()
