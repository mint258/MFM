"""Three pure resource boundaries; original inventory3 are also retained."""
import unittest
from . import contract as A


def request():
    return {'kind':'analysis','pilot':False,'cpus':16,'node':'compute-0-13','wall_seconds':1800,
      'estimated_peak_output_bytes':2<<30,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED'}


class Boundaries(unittest.TestCase):
    def test_actual13_resources_never_alias_historical17(self):
        A.validate_current_request(request())
        for key,value in (('node','compute-0-17'),('cpus',True),('cpus',1),('wall_seconds',1801),
          ('pilot',True),('estimated_peak_output_bytes',1),('memory_policy','FAKE64G')):
            with self.subTest(key=key),self.assertRaises(ValueError):A.validate_current_request(dict(request(),**{key:value}))
        with self.assertRaises(ValueError):A.validate_current_request(dict(request(),memory_gib=64))
        self.assertEqual(A.PARAMETERS['historical_original_node'],'compute-0-17')
        self.assertEqual(A.PARAMETERS['historical_original_job_id'],'4521904')

    def test_exact_primary_all_options_not_old_module_or_duplicate(self):
        p='/share/home/zixiao/descriptor_analysis/runs/x/plan.json';q=p+'.proof';out=p+'.out'
        argv=A.execution_argv(p,q,out);A.validate_execution(argv,p,q,out)
        bad=list(argv);bad[3]=A.ORIGINAL.MODULE
        for value in (bad,argv+['--output',out],argv[:-1],argv[:5]+[q]+argv[6:]):
            with self.assertRaises(ValueError):A.validate_execution(value,p,q,out)

    def test_coordinator_inverse_and_old_readonly_functions_are_direct(self):
        from . import run
        from workflows.data_v1_final.labels.full_timeout_inventory_v1 import run as old
        self.assertIs(run.I,old.I);self.assertIs(run.V,old.V);self.assertIs(run.old_parent,old.old_parent)
        self.assertIs(A.parent_chain,old.C.parent_chain)
        self.assertEqual(run.source_inverse()['status'],'EXACT_CPU13_RESOURCE_ONLY_BYTES_AST_INVERSE')
