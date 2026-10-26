"""Three pure methods, run only in a fresh CPU allocation before any body IO."""
import unittest
from . import analysis as A
from . import contract as C
from . import frozen_scf as S

class EvidenceBoundaries(unittest.TestCase):
    def test_scf_is_explicit_not_process_success_or_limits(self):
        value=S.extract_scf('xtb_singlepoint',[{'name':'process.out','data':b'normal termination of xtb\nmax. iterations 250'}],status='SUCCESS')
        self.assertIsNone(value['converged']);self.assertIsNone(value['scf_iterations'])
        value=S.extract_scf('xtb_perturbed_gradient',[{'name':'process.out','data':b'convergence criteria satisfied after 7 iterations\nSIGSEGV'}],status='FAILED')
        self.assertTrue(value['converged']);self.assertEqual(value['scf_iterations'],7)
        value=S.extract_scf('pm7_B',[{'name':'input.out','data':b'SCF FIELD WAS ACHIEVED\nSCF CALCULATIONS = 1'}])
        self.assertTrue(value['converged']);self.assertIsNone(value['scf_iterations'])

    def test_missing_own_frame_and_conflicting_termination_remain_unknown(self):
        value=A.frame_info('xtb_singlepoint',[],['H'],[[0.,0.,0.]],{'read_outputs_v1':object(),'math_v1':object()},{})
        self.assertEqual(value['status'],'UNKNOWN_NO_IDENTIFIED_OWN_OUTPUT_COORDINATE_ARTIFACT')
        self.assertFalse(value['companion_frame_borrowed'])
        value=A.terminal_evidence('xtb_singlepoint',[{'name':'process.out','data':b'normal termination of xtb\nSCC IS NOT CONVERGED'}])
        self.assertEqual(value['status'],'CONFLICTING_TERMINAL_MARKERS');self.assertFalse(value['cause_proven'])
        self.assertEqual(value['events'][1]['line_1_based'],2)

    def test_exact_fixed24_selector_rejects_missing_binding(self):
        groups=[(*g,'pm7_B') for g in C.PM7_GROUPS]+[(*g,task) for g in C.NOISY_GROUPS for task in ('xtb_perturbed_gradient','xtb_singlepoint_noisy_companion')]
        orbits=[];checks=[]
        for index,group in enumerate(groups):
            a,b='case-'+str(index*2),'case-'+str(index*2+1)
            orbits.append({'group':list(group),'base_case':a,'variant_case':b})
            checks.extend({'case_id':name,'all_actual_input_bindings_and_target_verified':True} for name in (a,b))
        checks.extend({'case_id':'unused-'+str(i),'all_actual_input_bindings_and_target_verified':True} for i in range(48))
        report={'schema':'PPRIME_NATIVE72_READONLY_ALPHA_DIAGNOSIS_V2','runtime':{'job_id':'1884773'},'all72_inputs_closed':True,
            'actual_cases_read':72,'case_read_errors':[],'synthetic_test_receipt':{'status':'PASS','tests_run':4},
            'original_failures':C.EXPECTED_FAILURES,'geometry_orbits':orbits,'input_checks':checks}
        original={'contradictions':C.EXPECTED_FAILURES};summary={'original15FAIL_preserved':True,
            'per_original_failure_invariant_summary':[{'original_failure':row} for row in C.EXPECTED_FAILURES]}
        rows=A.choose_cases(report,original,summary);self.assertEqual(len(rows),24)
        self.assertEqual(sum(row['identity'][2]=='pm7_B' for row in rows),12)
        checks[0]['all_actual_input_bindings_and_target_verified']=False
        with self.assertRaises(ValueError):A.choose_cases(report,original,summary)
