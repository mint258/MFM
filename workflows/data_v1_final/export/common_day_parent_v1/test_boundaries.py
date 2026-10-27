"""Three meaningful synthetic day-parent metadata boundaries, no DATA/mocks."""
import unittest
from . import parent as P
class Boundaries(unittest.TestCase):
    def test_true64_C0_never_old16_or_timeout00(self):
        row={'job_id':'9','node':'compute-0-18','alloc_cpus':64,'state':'COMPLETED','exit_code':'0:0'};P.c0_row(row,'9',row['node'],64)
        for changed,cpus in ((dict(row,state='TIMEOUT'),64),(row,16),(dict(row,alloc_cpus=True),64)):
            with self.assertRaises(ValueError):P.c0_row(changed,'9',row['node'],cpus)
    def test_actual28_and_full_inverse_not_old8_or_skip(self):
        f={'schema':'POSTPROCESS_ANALYSIS_DAY_PREFLIGHT_V1','tests_run':28,'failures':0,'errors':0,'skips':0,'expected_failures':0,'unexpected_successes':0,
          'source_inverse':{'status':'ACTUAL_SOURCE_FULL_INVERSE_AND_DIRECT_OBJECTS','common_complete_inverse_bytes_AST':True,
          'old_common_math_SQL_merge_exclusion_sparse_physical_ID_logic_unchanged':True,'packet_reader_only_explicit_value':True,'original_parent64_and_old_parent16_both_truthful':True}}
        P.fixture_gate(f)
        for bad in (dict(f,tests_run=8),dict(f,skips=1),dict(f,source_inverse=dict(f['source_inverse'],common_complete_inverse_bytes_AST=False))):
            with self.assertRaises(ValueError):P.fixture_gate(bad)
    def test_Root_common_acceptance_and_no_unknown_or_quality_waiver(self):
        r={'schema':'ROOT_CONFORMERS_POSTPROCESS_COMPONENT_ACCEPTANCE_V1','status':'APPROVED_EXACT_ACTUAL_COMPONENTS','reviewer':'root','approve_common':True}
        c={'original_quality_hold':None,'ordinary_Common_D7_geometry_complete':True,'unknown_molecules':0};P.approved(r,c)
        for bad in (dict(c,original_quality_hold={}),dict(c,ordinary_Common_D7_geometry_complete=False),dict(c,unknown_molecules=1)):
            with self.assertRaises(ValueError):P.approved(r,bad)
