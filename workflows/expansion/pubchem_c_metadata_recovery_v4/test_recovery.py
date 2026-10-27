"""Exactly three no-DATA boundaries; unchanged old state and source inverse."""
import copy,unittest
from secondary_cpu_queue_v1 import common as Q
from pubchem_c_finite500_continuation_v3 import state as S
from pubchem_c_finite500_continuation_v3.test_state import fixture
from . import recovery as R,controller as N


class Boundaries(unittest.TestCase):
    def test_large_data_locator_small_metadata_denial_and_bad_references(self):
        value={'path':str(Q.ROOT/'artifacts/pubchem_continuation_alpha_v3/shard-0052/synthetic-large-journal.json'),
          'bytes':200<<20,'sha256':'a'*64}
        with self.assertRaises(ValueError):Q.normalized(value)
        N.data_locator(value);self.assertIn(value['path'],N.DENIED)
        with self.assertRaises(ValueError):N.meta(value)
        for bad in (dict(value,bytes=True),dict(value,bytes=0),dict(value,bytes=-1),dict(value,sha256='A'*64),
          dict(value,sha256='a'*63),dict(value,extra=True),dict(value,path='/tmp/x'),
          dict(value,path=str(Q.ROOT/'artifacts/a/../x'))):
            with self.subTest(bad=bad),self.assertRaises(ValueError):R.locator_shape(bad)
        self.assertEqual(R.locator_shape(dict(value,bytes=1))['bytes'],1)

    def test_six_terminal_producers_are_adopted_never_science_failed_or_repeated(self):
        legacy,repaired,failed=fixture();population,attempts=S.adoption(legacy,repaired,failed)
        for i in range(52,58):
            population[i]={'shard_index':i,'status':'CLOSED','actual_state':'COMPLETED','actual_exit':'0:0',
              'expected_rows':250000,'job_id':R.EXPECTED[i],'actual_allocated_core_seconds':16}
        free={n:64 for n in S.NODES};attempted=set(range(52,58))
        action,index,node=S.decision(population,attempted,free,0,10)
        self.assertEqual((action,index),('ELIGIBLE',58));self.assertIn(node,S.NODES)
        self.assertEqual(attempts['1884853']['actual_allocated_core_seconds'],336)
        bad=copy.deepcopy(population);bad[54]['status']='UNKNOWN'
        self.assertTrue(S.decision(bad,attempted,free,0,10)[0].startswith('HOLD'))
        self.assertEqual(S.decision(population,attempted,free,10,10)[0],'FINITE_ABSOLUTE_DEADLINE_NO_RENEWAL')
        self.assertIs(N.S,S)

    def test_same_grant_deadline_and_exact_three_group_source_inverse(self):
        grant={'path':str(Q.ROOT/'control/synthetic-old-grant.json'),'bytes':10,'sha256':'b'*64}
        root={'deadline_unix_seconds':100,'authorized_unix_seconds':0,'source_references':[{'old13':'unchanged'}],
          'max_nonterminal_C_parents':6,'reserved_non_C_cpus':16,'controller_metadata_cap_bytes':16<<20,
          'no_automatic_retry':True,'no_automatic_renewal':True,'no_signals_or_cancel':True}
        binding={'root_range_review_reference':grant,'deadline_unix_seconds':100}
        review={'original_root_range_review_reference':grant,'original_state_directory':str(R.STATE),
          'original_deadline_unix_seconds':100,'original_authorized_unix_seconds':0,
          'source_references_for_future_children':root['source_references'],'future_children_use_old13_approved_template':True,
          'new_scientific_attempt_for52_57':False,'no_automatic_retry':True,'no_automatic_renewal':True,'no_signals_or_cancel':True}
        R.same_binding(review,root,grant,binding,R.STATE)
        for key,value in (('original_deadline_unix_seconds',101),('original_state_directory',str(Q.ROOT/'control/newstate')),
          ('new_scientific_attempt_for52_57',True),('source_references_for_future_children',[])):
            bad=copy.deepcopy(review);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):R.same_binding(bad,root,grant,binding,R.STATE)
        report=R.inverse();self.assertEqual(report['declared_delta_groups'],3)
        self.assertEqual(report['status'],'EXACT_METADATA_LOCATOR_RECOVERY_BYTES_AND_AST_INVERSE')