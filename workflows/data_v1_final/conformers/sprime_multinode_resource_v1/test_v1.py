"""Three meaningful pure boundaries;no DATA,science initialize or native call."""
import argparse,copy,io,json,pathlib,tempfile,types,unittest
from . import contract as C,edge as E,control,cutover
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as A
class Boundaries(unittest.TestCase):
    def test_full_source_inverse_and_exact_original_callable_identities(self):
        proof=C.source_inverse_proof();self.assertTrue(proof['inverse_bytes_and_AST_equal']);self.assertFalse(proof['scientific_source_modified']);self.assertEqual(len(proof['rows']),5)
        from . import runtime_io as R
        from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as old
        self.assertIs(R.load_science,old.load_science);self.assertIs(R.read_packet,old.read_packet);self.assertIs(C.task_key,C.ORIGINAL.task_key);self.assertIs(C.seed_for,C.ORIGINAL.seed_for)
        import ast
        # Synthetic wrong implementation cannot masquerade as an unchanged AST.
        self.assertNotEqual(ast.dump(ast.parse('x=1')),ast.dump(ast.parse('x=2')))
    def test_identity_frame_diagnostic_selection_and_no_zero_DATA_alias(self):
        self.assertEqual(C.task_key('MID','retry_once'),C.ORIGINAL.task_key('MID','retry_once'));self.assertEqual(C.LEDGER,C.ORIGINAL.LEDGER)
        before={'device':1,'inode':2,'size':3,'mtime_ns':4,'uid':1278};after=dict(before,device=90);C.same_source(before,after)
        for field in ('inode','size','mtime_ns','uid'):
            with self.assertRaises(ValueError):C.same_source(before,dict(after,**{field:999}))
        for n in C.NODES:self.assertEqual(C.node(n),n)
        with self.assertRaises(ValueError):C.node('compute-0-20')
        with self.assertRaises(ValueError):C.node('compute-0-1')
        zero={'path':str(C.HERE/'synthetic/__init__.py'),'bytes':0,'sha256':'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}
        self.assertEqual(C.source_shape(zero),zero)
        with self.assertRaises(ValueError):C.triple(zero)
        from .qa_prepare import select
        closed=[{'molecule_id':'synthetic_%03d'%i,'summary':{'status':'SUCCESS','heavy_atoms':10,'expected_conformers':3,'elapsed_seconds':1.},
            'detail':{'new_real_accepted_count':1},'science_worker_seconds':1.} for i in range(40)]
        chosen,n=select(closed);self.assertEqual((len(chosen),n),(32,40));self.assertEqual([r['molecule_id'] for r in chosen],[r['molecule_id'] for r in select(list(reversed(closed)))[0]])
        self.assertFalse(select(closed[:31])[0]);self.assertNotEqual(C.sha_value(['diagnostic32','node',chosen[0]['molecule_id']]),C.task_key(chosen[0]['molecule_id'],'retry_once'))
    def test_live_cutover_lock_capacity_limits_and_instantaneous_changes(self):
        limits={'compute-0-11':2,'compute-0-13':2}
        def raw(node,allocated):return {'NodeName':node,'Partitions':'cpu','CPUTot':'64','CPUAlloc':str(allocated)}
        observations={n:raw(n,0) for n in limits}
        self.assertEqual(control.choose_node(observations,limits,{},4,0,old_live=True)['intents'],0)
        self.assertEqual(control.choose_node(observations,limits,{},4,0,lock_busy=True)['reason'],'SERIALIZATION_LOCK_BUSY')
        self.assertEqual(control.choose_node(observations,limits,{},4,4)['action'],'WAIT')
        selected=control.choose_node(observations,limits,{'compute-0-11':2},4,2);self.assertEqual(selected['node'],'compute-0-13')
        observations['compute-0-13']=raw('compute-0-13',64)
        self.assertEqual(control.choose_node(observations,limits,{'compute-0-11':2},4,2)['action'],'WAIT')
        observations['compute-0-13']=raw('compute-0-13',48)
        self.assertEqual(control.choose_node(observations,limits,{'compute-0-11':2},4,2,reserved_free=80)['action'],'WAIT')
        bad=copy.deepcopy(observations);bad['compute-0-11']['CPUAlloc']='65'
        with self.assertRaises(ValueError):control.choose_node(bad,limits,{},4,0)
        ident={'pid':123,'uid':1278,'start_ticks':7,'boot_id':'B','argv':['root-old-metadata'],'cgroup':['ordinary']}
        self.assertTrue(cutover.same_process(ident,dict(ident)));self.assertFalse(cutover.same_process(ident,dict(ident,start_ticks=8)))
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('plan','root-preflight','output'):p.add_argument('--'+k,type=pathlib.Path,required=True)
    a=p.parse_args();ref=C.ref(a.plan);plan=E.meta(ref);n=C.node(plan['node']);argv=[C.Q.PY,'-B','-m',C.MODULE+'.test_v1','--plan',str(a.plan),'--root-preflight',str(a.root_preflight),'--output',str(a.output)]
    proof=A.require_startup(a.root_preflight,expected_scope_key='sprime_multinode_resource_source3_v1',expected_scope_parameters=C.parameters('source3',n),
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',required_references=[ref,*C.own_sources()])
    C.need(proof['request']['node']==n and proof['request']['cpus']==16,'ACTUAL_PURE_TEST_MAIN_CPU16')
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);C.need(suite.countTestCases()==3,'EXACT3_NEW_SOURCE_BOUNDARIES');text=io.StringIO();r=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    passed=r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses)
    C.need(C.DIAG in a.output.parents and not a.output.exists(),'FRESH_SOURCE3_OUTPUT');a.output.mkdir(parents=True)
    C.Q.write_new(a.output/'receipt.json',{'schema':'ACTUAL_SPRIME_MULTINODE_SOURCE3_V1','status':'PASS' if passed else 'FAIL','tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),
        'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':text.getvalue(),'node':n,'uid':1278,
        'job_id':str(proof['job_id']),'plan_reference':ref,'startup_proof_reference':C.ref(a.root_preflight),'source_references':C.own_sources(),'environment':E.environment(),
        'scientific_DATA_or_UFF_QM_called':False,'production_once_accessed':False});return 0 if passed else 3
if __name__=='__main__':raise SystemExit(main())
