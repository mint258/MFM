"""Metadata-only partition cases; no fake Slurm environment or DATA access."""
import unittest
from .admission import approved_partition


class Admission(unittest.TestCase):
    def policy(self):return dict(schema='PUBCHEM_EXPANSION_USER_CPU21_AUTHORIZATION_V1',status='USER_APPROVED',node='compute-0-21',partition='all',
      GPU_used=False,paid_server_used=False,scope='This PubChem expansion goal only, including statistics, screening and UFF',source='Direct user reply in this conversation')
    def plan(self):return dict(node='compute-0-21',partition='all',resource_authorization_reference=dict(path='/synthetic/user_cpu21_authorization_20261103.json',bytes=1,sha256='0'*64))
    def test_existing_cpu_partition_needs_no_exception(self):
        def unused(ref):raise AssertionError('cpu must not request node21 exception')
        self.assertFalse(approved_partition(dict(node='compute-0-20'),'compute-0-20','cpu',unused)['exception'])
    def test_all21_requires_pinned_actual_authorization(self):
        self.assertTrue(approved_partition(self.plan(),'compute-0-21','all',lambda ref:self.policy())['exception'])
        with self.assertRaises(ValueError):approved_partition(dict(node='compute-0-21',partition='all'),'compute-0-21','all',lambda ref:self.policy())
        bad=self.policy();bad['status']='DRAFT'
        with self.assertRaises(ValueError):approved_partition(self.plan(),'compute-0-21','all',lambda ref:bad)
    def test_all_other_node_or_partition_mismatch_rejected(self):
        for node in ('compute-0-20','compute-0-13'):
            with self.subTest(node=node),self.assertRaises(ValueError):approved_partition(dict(self.plan(),node=node),node,'all',lambda ref:self.policy())
        with self.assertRaises(ValueError):approved_partition(self.plan(),'compute-0-21','cpu',lambda ref:self.policy())


if __name__=='__main__':unittest.main()
