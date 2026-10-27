"""Five pure adoption/admission boundaries; no Slurm or scientific payloads."""
import copy,unittest
from . import state as S


def fixture():
    rows={i:{'shard_index':i,'status':'CLOSED','actual_state':'COMPLETED','actual_exit':'0:0','expected_rows':250000,
        'job_id':str(1000+i),'actual_allocated_core_seconds':16} for i in range(51)}
    failed={'shard_index':51,'job_id':'1884853','actual_state':'FAILED','actual_exit':'1:0','actual_allocated_core_seconds':336,'status':'FAILED','expected_rows':250000}
    repaired={'shard_index':51,'job_id':'1884855','actual_state':'COMPLETED','actual_exit':'0:0','actual_allocated_core_seconds':1600,'status':'CLOSED','expected_rows':250000}
    return rows,repaired,failed


class Boundaries(unittest.TestCase):
    def test_failed51_is_never_success_without_actual_repair(self):
        legacy,repaired,failed=fixture()
        with self.assertRaises(ValueError):S.adoption(legacy,failed,failed)
        population,attempts=S.adoption(legacy,repaired,failed)
        self.assertEqual(population[51]['job_id'],'1884855');self.assertEqual(attempts['1884853']['actual_allocated_core_seconds'],336)
        self.assertEqual(len(attempts),53)
    def test_old_closed_import_hole_or_duplicate_parent_rejected(self):
        legacy,repaired,failed=fixture();bad=copy.deepcopy(legacy);del bad[45]
        with self.assertRaises(ValueError):S.adoption(bad,repaired,failed)
        bad=copy.deepcopy(legacy);bad[50]['job_id']=bad[49]['job_id']
        with self.assertRaises(ValueError):S.adoption(bad,repaired,failed)
    def test_next52_uses_original_partition_tail_and_no_physical_alias(self):
        legacy,repaired,failed=fixture();population,_=S.adoption(legacy,repaired,failed)
        action,index,node=S.decision(population,set(),{n:64 for n in S.NODES},0,10)
        self.assertEqual((action,index),('ELIGIBLE',52));self.assertIn(node,S.NODES)
        rows=[{'shard_index':i,'first_part':i,'last_part':i,'first_ordinal':i*250000+1,'last_ordinal':min((i+1)*250000,S.N)} for i in range(500)]
        S.check_partition(rows);self.assertEqual(rows[-1]['last_ordinal']-rows[-1]['first_ordinal']+1,107440)
    def test_max6_and_spare16_are_real_admission_constraints(self):
        legacy,repaired,failed=fixture();population,_=S.adoption(legacy,repaired,failed)
        free={n:0 for n in S.NODES};free[S.NODES[0]]=16
        self.assertTrue(S.decision(population,set(),free,0,10)[0].startswith('WAIT_'))
        for i in range(52,58):population[i]={'status':'RUNNING'}
        self.assertEqual(S.decision(population,set(),{n:64 for n in S.NODES},0,10)[0],'WAIT_AT_ROOT_NONTERMINAL_C_CAP')
    def test_unknown_attempt_and_absolute_deadline_cannot_auto_retry_or_renew(self):
        legacy,repaired,failed=fixture();population,_=S.adoption(legacy,repaired,failed)
        self.assertTrue(S.decision(population,{52},{n:64 for n in S.NODES},0,10)[0].startswith('HOLD_'))
        population[52]={'status':'UNKNOWN'}
        self.assertTrue(S.decision(population,{52},{n:64 for n in S.NODES},0,10)[0].startswith('HOLD_'))
        self.assertEqual(S.decision(population,{52},{n:64 for n in S.NODES},10,10)[0],'FINITE_ABSOLUTE_DEADLINE_NO_RENEWAL')
