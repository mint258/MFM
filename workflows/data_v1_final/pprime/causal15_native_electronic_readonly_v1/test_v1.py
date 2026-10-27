"""Three meaningful synthetic native-evidence boundaries; no original body."""
import unittest
from . import evidence as E


class Boundaries(unittest.TestCase):
    def test_explicit_scf_normal_exit_and_incomplete_stage_stay_distinct(self):
        a=E.SCF.extract_scf('xtb_singlepoint',[{'name':'process.out','data':b'normal termination of xtb\n'}]);self.assertIsNone(a['converged'])
        b=E.SCF.extract_scf('xtb_singlepoint',[{'name':'process.out','data':b'convergence criteria satisfied after 7 iterations\niter E dE RMSdq gap\n1 -1.000 0.100 0.01\n'}])
        self.assertIsNone(b['converged']);self.assertIsNone(b['scf_iterations'])
        c=E.SCF.extract_scf('pm7_B',[{'name':'input.out','data':b'SCF CALCULATIONS = 42\nSCF FIELD WAS ACHIEVED\n'}]);self.assertTrue(c['converged']);self.assertIsNone(c['scf_iterations'])
    def test_AUX_repeated_occurrences_and_anchored_ENGRAD_count(self):
        text='DIP_VEC:DEBYE[3]=1.0D+00 2.0D+00 3.0D+00\nDIP_VEC:DEBYE[3]=4.0D+00 5.0D+00 6.0D+00\n'
        a=E.aux(text,'input.aux','0'*64);self.assertEqual(len(a['selected_native_fields_all_occurrences']),2);self.assertEqual(a['selected_native_fields_all_occurrences'][0]['tokens'][0],'1.0D+00')
        e=E.engrad('# The current gradient in Eh/bohr\n1.0D+00\n2.0D+00\n3.0D+00\n','input.engrad','0'*64,1)
        self.assertTrue(e['gradient_exact3N_and_unique']);self.assertFalse(E.engrad('# no unit\n1\n2\n3\n','input.engrad','0'*64,1)['gradient_exact3N_and_unique'])
    def test_XTB_components_au_total_Debye_and_native_interval_no_added_tolerance(self):
        v=E.stdout('molecular dipole:\n x y z tot (Debye)\n full: 1.000 0.000 0.000 2.542\n','process.out','0'*64,True)
        self.assertEqual(v['xTB_dipole_native_rows'][0]['component_units'],['a.u.','a.u.','a.u.','Debye'])
        self.assertTrue(E.overlap('1.000D+00','1.0004E+00'));self.assertFalse(E.overlap('1.000D+00','1.0020E+00'))
        j=E.json_fields('{"dipole / a.u.":[1.0,0.0,0.0],"atomic dipoles / a.u.":[[0.1,0.0,0.0]]}')
        self.assertEqual(len(j['selected_key_occurrences']),2);self.assertFalse(j['charges_only_reconstruction_of_full_dipole'])
