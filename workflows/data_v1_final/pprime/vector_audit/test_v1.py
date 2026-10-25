"""Meaningful synthetic frame/units/tensor controls; no QM, LMDB or external child."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from math_v1 import (BOHR_TO_A, ROTATION, checked_rotation, covariance, force_relation,
                    output_frame, rounding_halfwidth, tensor_checks, tensor_covariance,
                    tensor_matrix, tensor_translation)
from read_outputs_v1 import aux_arrays, xtb_gradient, xtb_quadrupole
from prepare_v1 import load_audit, make_cases

CONFIG = None


class FrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.block = patch('subprocess.Popen', side_effect=AssertionError('SYNTHETIC_AUDIT_CANNOT_START_CHILD'))
        cls.block.start()

    @classmethod
    def tearDownClass(cls):
        cls.block.stop()

    def test_registered_audit_configuration_and_proper_rotation(self):
        import numpy as np
        c = load_audit(CONFIG)
        self.assertFalse(c['production_membership'])
        r = checked_rotation(c['rotation_matrix'])
        self.assertAlmostEqual(float(np.linalg.det(r)), 1., places=14)
        with self.assertRaises(ValueError):
            checked_rotation([[1., 0., 0.], [0., 1., 0.], [0., 0., -1.]])

    def test_gradient_actual_input_rotates_noise_not_just_clean_coordinates(self):
        import numpy as np
        native = {'coords': np.asarray([[0., 0., 0.], [1., .2, .3], [.1, 1., -.2]]),
                  'z': np.asarray([6, 1, 8]), 'symbols': ['C', 'H', 'O'],
                  'pairs': [(1, 0), (2, 0)], 'native_atom_order_sha256': 'a'*64}
        protocol = {'seed': 20261010, 'perturb_sigma_A': .1, 'tasks': [
            {'name': 'pm7_B'}, {'name': 'xtb_singlepoint'},
            {'name': 'xtb_perturbed_gradient', 'perturbed': True}]}
        cases = make_cases(native, {'record_id': 'source:1'}, 'm1', 'uff_sprime', protocol)
        self.assertEqual(len(cases), 9)
        indexed = {(c['condition'], c['arm']): c for c in cases}
        b = indexed['xtb_perturbed_gradient', 'base']
        r = indexed['xtb_perturbed_gradient', 'rotated']
        np.testing.assert_allclose(np.asarray(b['expected_actual_coordinates_A']) @ checked_rotation().T,
                                   r['expected_actual_coordinates_A'], rtol=0, atol=1e-14)
        self.assertEqual(b['row']['record_id'], r['row']['record_id'])
        self.assertEqual(b['perturb_seed'], r['perturb_seed'])
        for arm in ('base', 'rotated'):
            np.testing.assert_array_equal(indexed['xtb_singlepoint_noisy_companion', arm]['expected_actual_coordinates_A'],
                                          indexed['xtb_perturbed_gradient', arm]['expected_actual_coordinates_A'])

    def test_output_coordinates_detect_real_reorientation(self):
        import numpy as np
        x = np.asarray([[0., 0., 0.], [1., 0., 0.], [0., 2., .3]])
        self.assertTrue(output_frame(x, x, 1e-8)['supports_input_axes'])
        rotated = x @ checked_rotation().T + [1., 2., 3.]
        result = output_frame(x, rotated, 1e-8)
        self.assertEqual(result['status'], 'PROPER_RIGID_REORIENTATION')
        self.assertFalse(result['supports_input_axes'])
        self.assertLess(result['proper_fit_RMSD_A'], 1e-12)

    def test_vector_covariance_rejects_unrotated_wrong_frame(self):
        import numpy as np
        value = np.asarray([[1., 2., 3.], [-1., .4, .6]])
        tol = {'atol': 1e-10, 'rtol': 1e-10, 'minimum_vector_norm': 1e-6}
        self.assertTrue(covariance(value, value @ checked_rotation().T, 0., 0., tol)['pass'])
        self.assertFalse(covariance(value, value, 0., 0., tol)['pass'])

    def test_source_aux_coordinate_and_interleaved_gradient_reader(self):
        text = '''ATOM_EL[2]= C H
ATOM_X_OPT:ANGSTROMS[6]=
0.0000000000 0.0000000000 0.0000000000
1.0000000000 0.2000000000 0.3000000000
DIP_VEC:DEBYE[3]= 1.000000D+00 2.000000D+00 3.000000D+00
GRADIENTS:KCAL/MOL/ANGSTROM[6]=
1.0 2.0 3.0 4.0 5.0 6.0
'''
        result = aux_arrays(text, 2)
        self.assertEqual(result['GRADIENTS:KCAL/MOL/ANGSTROM']['values'], [[1., 2., 3.], [4., 5., 6.]])
        self.assertEqual(result['ATOM_EL']['values'], ['C', 'H'])
        self.assertAlmostEqual(rounding_halfwidth('1.234D-02'), 5e-6)

    def test_gradient_bohr_coordinates_and_force_sign(self):
        import numpy as np
        text = '$grad\ncycle = 1 SCF energy = -1.0\n1.00000000000000 0.0 0.0 c\n0.0 2.00000000000000 0.0 h\n1.0E-2 2.0E-2 3.0E-2\n-1.0E-2 -2.0E-2 -3.0E-2\n$end\n'
        value = xtb_gradient(text, ['C', 'H'])
        self.assertEqual(value['coordinates_bohr'], [[1., 0., 0.], [0., 2., 0.]])
        self.assertEqual(value['coordinates_A'][0][0], BOHR_TO_A)
        self.assertEqual(len(value['coordinate_conversion_hypotheses_A']), 2)
        g = np.asarray(value['gradient_Eh_bohr'])
        f = -g*27.211386245988/BOHR_TO_A
        self.assertTrue(force_relation(g, f)['pass'])
        self.assertFalse(force_relation(g, -f)['pass'])

    def test_all_six_quadrupole_components_rotate_and_trace_is_not_projected(self):
        import numpy as np
        six = [1., 2., -4., 3., 5., 3.]
        q = tensor_matrix(six)
        self.assertEqual(q[0, 2], 3.)
        qr = checked_rotation() @ q @ checked_rotation().T
        packed = [qr[0, 0], qr[0, 1], qr[1, 1], qr[0, 2], qr[1, 2], qr[2, 2]]
        tol = {'atol': 1e-10, 'rtol': 1e-10, 'minimum_tensor_norm': 1e-6}
        self.assertTrue(tensor_covariance(six, packed, [0.]*6, [0.]*6, tol)['pass'])
        self.assertFalse(tensor_covariance(six, six, [0.]*6, [0.]*6, tol)['pass'])
        self.assertTrue(tensor_checks(six, [0.]*6)['trace_within_rounding'])
        bad = [1., 2., -4., 3., 5., 4.]
        self.assertFalse(tensor_checks(bad, [0.]*6)['trace_within_rounding'])
        with self.assertRaises(ValueError):
            tensor_matrix(six[:5])
        parsed = xtb_quadrupole('molecular quadrupole (traceless):\n xx xy yy xz yz zz\n full: 1.000 2.000 -4.000 3.000 5.000 3.000\n')
        self.assertEqual(parsed['six_components_au'], six)

    def test_origin_rule_against_independent_point_charge_recomputation(self):
        import numpy as np
        charges = np.asarray([1., -.4, -.6])
        xyz = np.asarray([[1., .2, .3], [-.2, .6, -.1], [.3, -.5, .7]])
        shift_A = np.asarray([.317, -.419, .233])
        def moment(positions):
            q = sum(charge*(1.5*np.outer(r, r)-.5*np.dot(r, r)*np.eye(3)) for charge, r in zip(charges, positions))
            return [q[0, 0], q[0, 1], q[1, 1], q[0, 2], q[1, 2], q[2, 2]]
        original, translated = moment(xyz), moment(xyz+shift_A/BOHR_TO_A)
        mu = (charges[:, None]*xyz).sum(0)
        tol = {'atol': 1e-10, 'rtol': 1e-10}
        self.assertTrue(tensor_translation(original, translated, mu, shift_A, [0.]*6, [0.]*6, [0.]*3, tol)['pass'])
        self.assertFalse(tensor_translation(original, original, mu, shift_A, [0.]*6, [0.]*6, [0.]*3, tol)['pass'])


def main():
    global CONFIG
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    CONFIG = p.parse_args().config
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FrameTests))
    print(json.dumps({'status': 'PASS' if result.wasSuccessful() else 'FAIL', 'tests': result.testsRun,
                      'QM_calls': 0, 'LMDB_opened': False, 'Slurm_submitted': False}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
