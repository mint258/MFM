"""Metadata scope boundaries, without RDKit or production data."""
from pathlib import Path
import tempfile
import types
import unittest
from . import library as L


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


if __name__=='__main__':unittest.main()
