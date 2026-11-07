"""Metadata scope boundaries, without RDKit or production data."""
from pathlib import Path
import tempfile
import types
import unittest
from . import library as L
from . import expectation


class Metadata(unittest.TestCase):
    def test_original_success_result_is_same_object(self):
        original={'reasons':[],'unchanged':['exact original object']};before=L.STATE
        try:
            L.STATE={'modules':[object()],'original_kernel':lambda *args:original}
            result=L.evaluate(None,'synthetic',0)
            self.assertIs(result['features'],original)
            self.assertFalse(result['representation_repair_applied']);self.assertTrue(result['original_kernel_passed'])
            self.assertEqual(result['events'],[])
        finally:L.STATE=before

    def test_AST_inverse_covers_only_declared_generic_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'original.py'
            path.write_text('def features(cid, smiles, ordinal):\n    mol = chemical_flags(smiles)\n    return identity(mol), Murcko.MakeScaffoldGeneric(mol)\n')
            module=types.SimpleNamespace(__file__=str(path))
            function,proof,original=L.private_function(module,'features',{},1,0)
            self.assertTrue(proof['exact_inverse_AST_equal']);self.assertTrue(proof['original_module_globals_not_modified'])
            self.assertNotIn('__generic_repr',vars(module))
            with self.assertRaises(ValueError):L.private_function(module,'features',{},2,0)
        def event(official,candidate):
            return dict(official_MakeScaffoldGeneric={'status':'PASS','result':{'key':official}},
              diagnostic_deferred_sanitize_candidate={'status':'PASS','key':candidate,'heavy_adjacency_and_allC_SINGLE_invariant':True})
        # A later exact old ring failure restarts the WHOLE original function,
        # so even an earlier successful ring uses the raw/generic-first branch.
        native={'ring_fragments':[
          dict(fragment_index=9,exact_original_fragment_sanitize={'status':'PASS'},
            generic_stages_after_original_fragment_sanitize=event('after9','after9'),
            generic_stages_on_uncorrupted_fragment=event('raw9','different_candidate9')),
          dict(fragment_index=13,exact_original_fragment_sanitize={'status':'ERROR','exception_type':'KekulizeException'},
            generic_stages_on_uncorrupted_fragment=event('raw13','raw13'))]}
        keys,proof=expectation.ring_keys(native)
        self.assertEqual(keys,['raw13','raw9']);self.assertTrue(proof['global_original_Kekulize_compatibility_fallback'])
        self.assertFalse(proof['per_fragment_hybrid_route_used'])
        self.assertEqual(expectation.generic_key(event('original_pass','different_candidate'))[0],'original_pass')


if __name__=='__main__':unittest.main()
