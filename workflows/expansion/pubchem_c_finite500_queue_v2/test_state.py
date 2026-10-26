"""Four synthetic state boundaries. Root must run these on CPU before live use."""
import ast,hashlib,json,re,unittest
from pathlib import Path
MACHINE_PIN_REFERENCE=None  # Root CPU runner supplies the actual small correction JSON triple on either endpoint.
from . import state as S


class Boundaries(unittest.TestCase):
    def initial(self):return {i:{'status':'CLOSED','expected_rows':250000,'actual_state':'COMPLETED','actual_exit':'0:0'} for i in (0,1)}
    def test_initial_running_or_partial_is_not_c0_closure(self):
        self.assertIsInstance(MACHINE_PIN_REFERENCE,dict,'Root runner must supply actual machine correction JSON reference')
        reference=MACHINE_PIN_REFERENCE;raw=Path(reference['path']).read_bytes()
        self.assertLessEqual(len(raw),2<<20);self.assertEqual(len(raw),reference['bytes'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),reference['sha256'])
        machine=json.loads(raw);self.assertEqual(machine['schema'],'ROOT_ACTUAL_PUBCHEM_C_FREEZE_PIN_TRANSCRIPTION_CORRECTION_V1')
        tree=ast.parse(Path(__file__).with_name('controller.py').read_text(encoding='utf-8'))
        nodes=[n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FREEZE' for t in n.targets)]
        self.assertEqual(len(nodes),1);self.assertIsInstance(nodes[0],ast.Dict)
        values=[v for k,v in zip(nodes[0].keys,nodes[0].values) if isinstance(k,ast.Constant) and k.value=='sha256']
        self.assertEqual(len(values),1);actual=ast.literal_eval(values[0])
        self.assertIsInstance(actual,str);self.assertRegex(actual,re.compile(r'^[0-9a-f]{64}$'))
        self.assertEqual(actual,machine['actual_reference']['sha256'])
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
