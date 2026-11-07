"""Four resource/context adapter boundaries; original17 remain unmodified."""
import copy,unittest
from . import contract as C,compute as K,resources as R


class AdapterBoundaries(unittest.TestCase):
    def test_scientific_inverse_ast_and_direct_original_order_objects(self):
        proof=K.inverse_proof();self.assertTrue(proof['inverse_scientific_AST_and_bytes_equal'])
        self.assertIs(K.geometry_orders,K.ORIGINAL.geometry_orders);self.assertIs(K.unique_representatives,K.ORIGINAL.unique_representatives)
    def test_original_numeric_body_change_is_not_an_allowed_resource_adaptation(self):
        import ast,pathlib
        text=pathlib.Path(K.__file__).read_text();old=pathlib.Path(K.ORIGINAL.__file__).read_text()
        funcs=lambda s:{n.name:n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef)}
        source=funcs(old)['compute'];new=funcs(text)['compute'];self.assertEqual(len(new.args.args),len(source.args.args)+1)
        # A changed scientific bound must change the reconstructed AST. This
        # does not edit or execute another copy of the numerical algorithm.
        raw=''.join(old.splitlines(keepends=True)[source.lineno-1:source.end_lineno]);changed=raw.replace('v>=0','v>0')
        self.assertNotEqual(raw,changed);self.assertNotEqual(ast.dump(ast.parse(raw)),ast.dump(ast.parse(changed)))
        with self.assertRaisesRegex(ValueError,'ONLY_EXPLICIT_LOCAL_SCIENCE_ARGUMENT'):
            K.prove_context_text(old,text.replace('v>=0','v>0'))
    def test_no_node13_alias_and_unique_non_autofs_active_mount(self):
        self.assertEqual(C.NODE,'compute-0-19');self.assertNotEqual(C.NODE,'compute-0-13')
        findmnt={'argv':R.Q.FINDMNT_ARGV,'returncode':0,'stdout':'/share/home systemd-1 autofs /\n/share/home nfs:/share/home nfs4 /\n','stderr':'','raw_output_complete':True}
        df={'argv':R.Q.DF_ARGV,'returncode':0,'stdout':'Filesystem 1024-blocks Used Available Capacity Mounted on\nnfs:/share/home 31251898368 1 31251898367 1% /share/home\n','stderr':'','raw_output_complete':True}
        selected=R.Q.parse_mount(findmnt,df);self.assertEqual(selected['active_mount']['source'],'nfs:/share/home')
        bad=copy.deepcopy(findmnt);bad['stdout']+='/share/home other:/share/home nfs4 /\n'
        with self.assertRaises(ValueError):R.Q.parse_mount(bad,df)
        with self.assertRaisesRegex(ValueError,'REAL_NODE19_METADATA_PROBE'):
            R.validate_edge({'schema':'PM7_NODE19_STORAGE_METADATA_PROBE_RECEIPT_V1',
                'status':'ACTUAL_NODE19_METADATA_OBSERVED_REQUIRES_ROOT_SAME_STORAGE_REVIEW','uid':1278,
                'node':'compute-0-13','endpoint':C.ENDPOINT},{})
    def test_QA_scope_has_no_full_ledger_or_population_and_strict2GIB(self):
        scope=C.scope('compat32');self.assertEqual(scope['output_cap_bytes'],2<<30)
        self.assertEqual(scope['new_population_rows'],0);self.assertFalse(scope['production_ledger_opened']);self.assertFalse(scope['full_release'])
        self.assertEqual(scope['old_pure_methods']+scope['new_adapter_methods'],21)
        self.assertEqual(C.scope('probe')['canonical_body_read'],False)
