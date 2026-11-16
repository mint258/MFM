import importlib.util,os,pathlib,tempfile,unittest
from unittest.mock import patch

class FollowupExecutionNamespace(unittest.TestCase):
 def module(self):
  path=pathlib.Path(__file__).resolve().parents[2]/'tools/p_recipe/execution_ledger.py'
  spec=importlib.util.spec_from_file_location('test_followup_ledger_namespace',path)
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
 def test_default_namespace_preserved(self):
  with patch.dict(os.environ,clear=False):
   os.environ.pop('P_RECIPE_CONTROL_DIRECTORY',None)
   self.assertEqual(str(self.module().C),'/share/home/zixiao/descriptor_analysis/runs/p_recipe_20261113')
 def test_followup_ledger_writes_only_its_directory(self):
  with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'P_RECIPE_CONTROL_DIRECTORY':directory}):
   module=self.module()
   with module.locked_ledger() as value:value['runs']['side']=dict(state='PREPARED')
   self.assertTrue((pathlib.Path(directory)/'study_execution.json').is_file())
if __name__=='__main__':unittest.main()