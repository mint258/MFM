"""Eight synthetic boundaries; no real case bodies, LMDB or QM program."""
import hashlib,unittest
from decimal import Decimal,localcontext
from fractions import Fraction
from . import contract as C,render as T


class Boundaries(unittest.TestCase):
    def test_exact_p90_tokens_keep_headers_symbols_and_units(self):
        raw=b'2\noriginal rid; Angstrom\nC 1.123456789012 -2.000000000001 3.000000000000\nH 4.000000000000 5.000000000000 6.000000000000\n'
        changed=T.p90(raw,'input.xyz')
        self.assertTrue(changed.startswith(b'2\noriginal rid; Angstrom\nC 2.000000000001 1.123456789012'))
        self.assertEqual([r[1] for r in T.rows(changed,'input.xyz')[1]],['C','H'])

    def test_large_decimal_signs_never_use_context_rounded_arithmetic(self):
        token='1234567890123456789012345678901234567890.123456789012'
        raw=('1\nfixed\nC '+token+' -0.000000000001 0.000000000000\n').encode()
        with localcontext() as context:
            context.prec=6
            changed=T.p90(raw,'input.xyz');values=T.rows(changed,'input.xyz')[1][0][2]
            self.assertEqual(Fraction(Decimal(values[1])),Fraction(Decimal(token)))
            self.assertEqual(T.negate(T.negate(token)),token)

    def test_mopac_flags_and_noncoordinate_text_remain_unchanged(self):
        raw=b'PM7 1SCF XYZ THREADS=1\noriginal-rid\nno optimization\nC 1.000000000000 1 2.000000000000 1 3.000000000000 1\n'
        changed=T.p90(raw,'input.mop');self.assertEqual(changed.splitlines()[:3],raw.splitlines()[:3])
        self.assertEqual(changed.splitlines()[3],b'C -2.000000000000 1 1.000000000000 1 3.000000000000 1')
        with self.assertRaisesRegex(ValueError,'FLAGS'):T.p90(raw.replace(b'3.000000000000 1',b'3.000000000000 0'),'input.mop')

    def test_wrong_precision_extra_rows_and_atom_count_fail(self):
        for raw in (b'1\nfixed\nC 1.0 2.000000000000 3.000000000000\n',b'2\nfixed\nC 1.000000000000 2.000000000000 3.000000000000\n'):
            with self.assertRaises(ValueError):T.p90(raw,'input.xyz')

    def test_source_ids_do_not_become_new_record_seeds(self):
        case={'case_id':'case-058','molecule_id':C.MID,'geometry_source':'pm7','condition':'xtb_perturbed_gradient',
            'calc_type':'xtb_perturbed_gradient','arm':'base','row':{'record_id':'vector-audit:'+C.MID+':pm7','molecule_id':C.MID}}
        self.assertEqual(C.source_identity('case-058',case),'xtb_perturbed_gradient')
        case['row']['record_id']+=':new-QA-id'
        with self.assertRaisesRegex(ValueError,'SEED'):C.source_identity('case-058',case)

    def test_fixed15_roster_and_actual900_recipe_are_separate_from_release(self):
        self.assertEqual(len({(condition,arm) for condition in C.CASES for arm in C.ARMS}),15)
        self.assertEqual(C.parameters('prepare')['new_QM_calls'],0);self.assertEqual(C.parameters('execute')['new_QM_calls'],15)
        self.assertEqual(C.parameters('execute')['task_timeout_seconds'],900)
        self.assertFalse(C.parameters('execute')['scientific_PASS']);self.assertEqual(C.parameters('execute')['full_or2000_release'],'HOLD')

    def test_QA_once_keys_are_separate_from_production_and_do_not_compact_ids(self):
        prepared={'path':'/synthetic-only/prepared.json','bytes':10,'sha256':'a'*64}
        self.assertEqual(C.key(prepared,'qa-00'),C.key(prepared,'qa-00'))
        self.assertNotEqual(C.key(prepared,'qa-00'),C.key(prepared,'qa-01'))
        self.assertNotEqual(C.key(prepared,'qa-00'),C.key(dict(prepared,sha256='b'*64),'qa-00'))

    def test_byte_mismatch_is_not_an_epsilon_acceptance_or_a_seed_retry(self):
        class FakeEngine:
            @staticmethod
            def perturb_seed(rid,protocol):return 17
            @staticmethod
            def render_inputs(task,native,row,protocol):return {'input.xyz':b'wrong target bytes\n'}
        case={'symbols':['C'],'atomic_numbers':[6],'pairs':[],'row':{'record_id':'synthetic-unmodified'},'native_atom_order_sha256':'a'*64}
        inputs={'input.xyz':b'1\nfixed\nC 1.000000000000 2.000000000000 3.000000000000\n'}
        with self.assertRaisesRegex(ValueError,'BYTE_MISMATCH_STOP_NO_EPSILON'):
            T.bridge(case,inputs,{'perturbed':True},{'perturb_sigma_A':0.1},FakeEngine)
