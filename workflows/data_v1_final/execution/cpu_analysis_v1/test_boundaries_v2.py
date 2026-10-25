"""Eight new CPU resource boundaries, with one actual allocation/heartbeat check."""
import copy,json,os,pathlib,unittest
from . import policy,runtime_v2 as runtime

class Boundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.intent=pathlib.Path(os.environ['DATA_V1_CPU_INTENT']);cls.request=policy.load(cls.intent)['request']
    def test_actual_cpu_allocation_and_heartbeat(self):
        proof=runtime.root_guard(self.intent,pathlib.Path(__file__),64*1024**2,wall_limit=600)
        self.assertEqual(proof['request']['scope_key'],'cpu_runtime_boundaries')
        runtime.checkpoint()
        self.assertTrue(runtime.heartbeat_is_fresh({'observed_monotonic_seconds':100},105))
        self.assertFalse(runtime.heartbeat_is_fresh({'observed_monotonic_seconds':100},105.001))
        self.assertFalse(runtime.heartbeat_is_fresh({'observed_monotonic_seconds':100},99))
        self.assertEqual(runtime.local_guard_directory('sample','123'),pathlib.Path('/tmp/dv1_cpu_guard_1278_123_sample'))
    def test_only_actual_cpu_partition_node_pool(self):
        self.assertEqual(policy.CPU_NODES,{f'compute-0-{n}' for n in (2,*range(8,20))})
        for node in ('compute-0-20','compute-0-21','compute-0-22'):
            r=copy.deepcopy(self.request);r['node']=node
            with self.assertRaisesRegex(ValueError,'CPU_SCOPE'):policy.scope(r,False)
    def test_formal_or_quantum_or_nonpilot_cannot_use_test_guard(self):
        for key,value in (('kind','qm'),('pilot',False),('formal_generation_authorized',True)):
            r=copy.deepcopy(self.request);r[key]=value
            with self.assertRaises(ValueError):policy.scope(r,False)
    def test_scientific_scope_or_memory_cannot_grow(self):
        for key,value in (('scope_parameters',{'records':999999}),('memory_gib',64),('cpus',32)):
            r=copy.deepcopy(self.request);r[key]=value
            with self.assertRaises(ValueError):policy.scope(r,False)
    def test_node_memory_exact_boundary_and_known_other_reservations(self):
        sample={'available_bytes':550,'total_bytes':1000,'used_bytes':450}
        self.assertIsNone(runtime.memory_denial(sample,1000,200,200,0))
        sample={'available_bytes':549,'total_bytes':1000,'used_bytes':451}
        self.assertIn('OVER85',runtime.memory_denial(sample,1000,200,200,0))
    def test_smaller_real_or_os_memory_is_the_limit(self):
        sample={'available_bytes':600,'total_bytes':1000,'used_bytes':400}
        self.assertIn('OVER85',runtime.memory_denial(sample,700,100,100,0))
        self.assertIsNone(runtime.memory_denial(sample,1000,100,100,0))
    def test_self_rss_and_invalid_memory_fail_closed(self):
        sample={'available_bytes':1000,'total_bytes':1000,'used_bytes':0}
        self.assertIn('OWN_PROCESS',runtime.memory_denial(sample,1000,0,100,75))
        self.assertIsNone(runtime.memory_denial(sample,1000,0,100,74))
        self.assertEqual(runtime.memory_denial(dict(sample,available_bytes=0),1000,0,100,0),'INVALID_MEMORY_SAMPLE')
    def test_whole_output_budget_and_source_authority_are_enforced(self):
        r=copy.deepcopy(self.request);r['estimated_peak_output_bytes']=0
        with self.assertRaises(ValueError):policy.scope(r,False)
        r=copy.deepcopy(self.request);r['source_references']=[p for p in r['source_references'] if p['path']!=str(policy.DECISION)]
        with self.assertRaises(ValueError):policy.scope(r,False)

if __name__=='__main__':unittest.main(verbosity=2)
