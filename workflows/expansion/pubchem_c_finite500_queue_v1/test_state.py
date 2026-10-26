"""Four synthetic state boundaries. Root must run these on CPU before live use."""
import unittest
from . import state as S


class Boundaries(unittest.TestCase):
    def initial(self):return {i:{'status':'CLOSED','expected_rows':250000,'actual_state':'COMPLETED','actual_exit':'0:0'} for i in (0,1)}
    def test_initial_running_or_partial_is_not_c0_closure(self):
        value=self.initial();self.assertTrue(S.initial_gate(value));value[1]['status']='RUNNING'
        self.assertFalse(S.initial_gate(value));self.assertEqual(S.next_shard({},set(),value)[1],None)
        value=self.initial();value[1]['expected_rows']=249999;self.assertFalse(S.initial_gate(value))
    def test_nonterminal_limit_and_contiguous_diagnosis_reserve(self):
        rows={2:{'status':'PENDING'},3:{'status':'RUNNING'}}
        self.assertEqual(S.next_shard(rows,{2,3},self.initial())[1],None)
        self.assertIsNone(S.choose_node(dict(zip(S.NODES,(16,8,8)))))
        self.assertEqual(S.choose_node(dict(zip(S.NODES,(32,0,0)))),S.NODES[0])
        six={i:{'status':'RUNNING'} for i in range(2,8)}
        self.assertIsNone(S.next_shard(six,set(six),self.initial(),6)[1])
        del six[7];self.assertEqual(S.next_shard(six,set(six),self.initial(),6)[1],7)
        self.assertIsNone(S.choose_node(dict(zip(S.NODES,(16,0,0)))))  # Current CPU changes invalidate an earlier32-free snapshot.
    def test_failed_unknown_attempts_are_never_automatically_retried(self):
        for status in S.BLOCKED:self.assertIsNone(S.next_shard({2:{'status':status}},{2},self.initial())[1])
        rows={i:{'status':'CLOSED'} for i in range(2,500) if i!=23}
        self.assertEqual(S.next_shard(rows,{23},self.initial())[0],'HOLD_ATTEMPTED_WITHOUT_UNAMBIGUOUS_PARENT_NO_RETRY')
    def test_fixed500_partition_and_last_short_shard(self):
        rows=[{'shard_index':i,'first_part':i,'last_part':i,'first_ordinal':i*250000+1,'last_ordinal':min((i+1)*250000,S.N)} for i in range(500)]
        S.check_partition(rows);self.assertEqual(rows[-1]['last_ordinal']-rows[-1]['first_ordinal']+1,107440)
        rows[42]['first_ordinal']+=1
        with self.assertRaises(ValueError):S.check_partition(rows)
