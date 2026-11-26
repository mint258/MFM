"""Validate only S authorization and source/resource adapter boundaries."""
import copy
import unittest
from finetune_extension_20261124 import validate, CONTROL, AUTHORITY, PROTOCOL


class FullFTAuthorization(unittest.TestCase):
    def config(self):
        return dict(invoking_authority=AUTHORITY, authority=PROTOCOL, kind='F', mode='full',
            ready=True, task='exp.LogD', seed=0, pretraining_seed=0, run='S_FT_B0_LogD_s0',
            internal_split_seed=20261112, bootstrap_seed=20261025,
            output=str(CONTROL/'finetune_20261124/S_FT_B0_LogD_s0'),
            source_binding=dict(checkpoint=str(CONTROL/'training/S_B0_s0_3M/samples_3000000.pt'),
                samples=3000000, source_training_budget=3000000, run='S_B0_s0_3M'),
            output_mount='/share', cleanup_seconds=900, peak_ram_bytes=64*1024**3,
            cpus=16, minimum_free_gpu_mib=22000, work_unit_seconds=120, node='compute-0-6')

    def test_exact_s_authority_with_original_p_protocol(self):
        c = self.config()
        self.assertIs(validate(c), c)
        for key, value in (('invoking_authority', None), ('authority', AUTHORITY),
                ('mode', 'scratch'), ('mode', 'top2'), ('ready', False), ('seed', True),
                ('pretraining_seed', 1), ('node', 'compute-0-21'), ('output_mount', '/lfshome'),
                ('cpus', 1), ('cleanup_seconds', 0), ('task', 'extra')):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate(dict(c, **{key: value}))

    def test_source_budget_and_output_binding(self):
        c = self.config()
        for key, value in (('samples', 9000000), ('source_training_budget', 6000000),
                ('checkpoint', '/foreign/samples_3000000.pt')):
            other = copy.deepcopy(c)
            other['source_binding'][key] = value
            with self.assertRaises(ValueError):
                validate(other)
        with self.assertRaises(ValueError):
            validate(dict(c, output='/tmp/S_FT_B0_LogD_s0'))
        trajectory=copy.deepcopy(c)
        trajectory['source_binding'].update(run='S_final_s0_9M',samples=1000000,
            source_training_budget=9000000,
            checkpoint=str(CONTROL/'training/S_final_s0_9M/samples_1000000.pt'))
        self.assertIs(validate(trajectory),trajectory)
        trajectory['source_binding'].update(samples=2000000,
            checkpoint=str(CONTROL/'training/S_final_s0_9M/samples_2000000.pt'))
        with self.assertRaises(ValueError):validate(trajectory)


if __name__ == '__main__':
    unittest.main()
