"""Three CPU source/real multiprocess synthetic IO boundaries;zero native calls."""
import argparse,concurrent.futures as cf,copy,gzip,io,json,multiprocessing as mp,pathlib,unittest
from . import contract as C,edge as E,control,cutover,compat32 as K,runtime_io as R
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as A
FIXTURE_ROOT=None;ACTUAL_PROOF=None;IO_EVIDENCE=[]
def synthetic_batch(name,fail=False):
    C.need(FIXTURE_ROOT is not None and ACTUAL_PROOF is not None,'ACTUAL_SOURCE3_OUTPUT_AND_PROOF_REQUIRED_FOR_SYNTHETIC_IO')
    value={'packet_compressed_limit_bytes':65536,'packet_uncompressed_limit_bytes':262144};out=R.new_output_directory(FIXTURE_ROOT/name,value)
    R.bind_io_context(out,value,ACTUAL_PROOF,{'synthetic_IO_only':True});tasks=[{'meta':{'molecule_id':'synthetic_%03d'%i}} for i in range(32)]
    if fail:tasks[3]['synthetic_failure']=True
    expected={t['meta']['molecule_id']:{'task_sha256':C.sha_value(t)} for t in tasks};ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=K.synthetic_initialize,initargs=(str(out),value,ACTUAL_PROOF,barrier)) as pool:
        results,errors,collection=K.collect_waves(pool,tasks,expected,lambda:None,runner=K.synthetic_one,reservation_bytes=16384)
    refs=[]
    for result in results:
        packet=R.read_packet(result['actual_packet_reference'],value);C.need(packet['synthetic_IO_only'] is True and packet['summary']['molecule_id']==result['molecule_id'],'REAL_SYNTHETIC_PACKET_READBACK')
        refs.append(result['actual_packet_reference'])
    evidence={'name':name,'results':len(results),'errors':len(errors),'collection':collection,'packet_references':refs,
        'starts':len(list((out/'starts').glob('*.json'))),'reservations_retained':len(list((out/'reservations').glob('*.json'))),'science_worker_init_called':False,'new_UFF_QM_calls':0}
    R.write_json_new(out/'synthetic_io_receipt.json',evidence);IO_EVIDENCE.append(evidence)
    return out,value,tasks,results,errors,collection
class Boundaries(unittest.TestCase):
    def test_source_inverse_original_objects_and_new32_excludes_old16(self):
        proof=C.source_inverse_proof();self.assertTrue(proof['inverse_bytes_and_AST_equal']);self.assertFalse(proof['scientific_source_modified']);self.assertEqual(len(proof['rows']),5)
        from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as old
        self.assertIs(R.load_science,old.load_science);self.assertIs(R.read_packet,old.read_packet);self.assertIs(C.task_key,C.ORIGINAL.task_key);self.assertIs(C.seed_for,C.ORIGINAL.seed_for)
        self.assertEqual(C.LEDGER,C.ORIGINAL.LEDGER);self.assertEqual(C.ADMIN,64<<20)
        limits={'packet_compressed_limit_bytes':128<<20};self.assertGreater(32*((128<<20)+(1<<20))+C.ADMIN,4<<30)
        self.assertLessEqual(C.compatibility_minimum_cap(limits),8<<30);self.assertEqual(C.COMPAT_EXTRA_FINALIZATION_HEADROOM,2<<30)
        from .qa_prepare import select
        closed=[{'molecule_id':'synthetic_%03d'%i,'summary':{'status':'SUCCESS','heavy_atoms':10,'expected_conformers':3,'elapsed_seconds':1.},
            'detail':{'new_real_accepted_count':1},'science_worker_seconds':1.} for i in range(49)]
        previous,_,_=select(closed);excluded={r['molecule_id'] for r in previous[:16]};chosen,n,remaining=select(closed,excluded)
        self.assertEqual((len(chosen),n,remaining),(32,49,33));self.assertFalse(excluded&{r['molecule_id'] for r in chosen})
        self.assertEqual([r['molecule_id'] for r in chosen],[r['molecule_id'] for r in select(list(reversed(closed)),excluded)[0]])
        self.assertFalse(select(closed[:31],set())[0]);self.assertFalse(select(closed,excluded|{chosen[0]['molecule_id'],chosen[1]['molecule_id']})[0])
    def test_real16_workers_32_reserved_written_closed_original_reader_packets(self):
        out,value,tasks,results,errors,collection=synthetic_batch('all32_success')
        self.assertEqual((len(results),len(errors),collection['submitted_count']),(32,0,32));self.assertEqual(len({r['pid'] for r in results}),16)
        self.assertTrue(all(r['io_context_bound'] for r in results));self.assertEqual(collection['drained_wave_starts'],[0,16]);self.assertEqual(len(list((out/'reservations').glob('*.json'))),0)
        self.assertEqual(len(list((out/'packets').glob('*.gz'))),32)
        packet=R.read_packet(results[0]['actual_packet_reference'],value);bad=copy.deepcopy(packet);bad['conformers'][0]['geometry_sha256']='0'*64
        ref=R.atomic_bytes(out/'errors'/'synthetic_tamper_rejected.json.gz',gzip.compress(C.canonical(bad),mtime=0))
        with self.assertRaisesRegex(ValueError,'REAL_FLOAT64'):R.read_packet(ref,value)
        item=next(x for x in IO_EVIDENCE if x['name']=='all32_success');item['known_invalid_synthetic_packet_reference']=ref;item['invalid_fixture_is_not_a_native_packet']=True
    def test_first_wave_failure_preserved_stops_new_wave_and_resource_cutover(self):
        out,value,tasks,results,errors,collection=synthetic_batch('first_wave_failure',fail=True)
        self.assertEqual((len(results),len(errors),collection['submitted_count']),(15,1,16));self.assertEqual(collection['drained_wave_starts'],[0])
        self.assertTrue(collection['first_wave_failure_stops_second_wave']);self.assertEqual(len(list((out/'starts').glob('*.json'))),16)
        self.assertEqual(len(list((out/'packets').glob('*.gz'))),15);self.assertEqual(len(list((out/'reservations').glob('*.json'))),1)
        self.assertTrue((out/'errors'/('parent-'+C.sha_value(tasks[3])+'.json')).is_file())
        for task in tasks[16:]:self.assertFalse((out/'dispatch'/(C.sha_value(task)+'.json')).exists())
        limits={'compute-0-11':2,'compute-0-13':2}
        def raw(node,allocated):return {'NodeName':node,'Partitions':'cpu','CPUTot':'64','CPUAlloc':str(allocated)}
        observations={n:raw(n,0) for n in limits}
        self.assertEqual(control.choose_node(observations,limits,{},4,0,old_live=True)['intents'],0)
        self.assertEqual(control.choose_node(observations,limits,{},4,0,lock_busy=True)['reason'],'SERIALIZATION_LOCK_BUSY')
        self.assertEqual(control.choose_node(observations,limits,{},4,4)['action'],'WAIT')
        self.assertEqual(control.choose_node(observations,limits,{'compute-0-11':2},4,2)['node'],'compute-0-13')
        observations['compute-0-13']=raw('compute-0-13',64);self.assertEqual(control.choose_node(observations,limits,{'compute-0-11':2},4,2)['action'],'WAIT')
        ident={'pid':123,'uid':1278,'start_ticks':7,'boot_id':'B','argv':['old-metadata'],'cgroup':['ordinary']}
        self.assertTrue(cutover.same_process(ident,dict(ident)));self.assertFalse(cutover.same_process(ident,dict(ident,start_ticks=8)))
def main():
    global FIXTURE_ROOT,ACTUAL_PROOF
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('plan','root-preflight','output'):p.add_argument('--'+k,type=pathlib.Path,required=True)
    a=p.parse_args();ref=C.ref(a.plan);plan=E.meta(ref);n=C.node(plan['node']);argv=[C.Q.PY,'-B','-m',C.MODULE+'.test_v1','--plan',str(a.plan),'--root-preflight',str(a.root_preflight),'--output',str(a.output)]
    proof=A.require_startup(a.root_preflight,expected_scope_key='sprime_multinode_resource_source3_v2',expected_scope_parameters=C.parameters('source3',n),
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',required_references=[ref,*C.own_sources()])
    C.need(proof['request']['node']==n and proof['request']['cpus']==16 and proof['request']['estimated_peak_output_bytes']==128<<20,'ACTUAL_SOURCE3_CPU16_AND_OUTPUT_CAP')
    C.need(C.DIAG in a.output.parents and not a.output.exists(),'FRESH_SOURCE3_OUTPUT');a.output.mkdir(parents=True);FIXTURE_ROOT=a.output;ACTUAL_PROOF=proof
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);C.need(suite.countTestCases()==3,'EXACT3_NEW_SOURCE_AND_MULTIWORKER_IO_METHODS');text=io.StringIO();r=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    passed=r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses)
    C.Q.write_new(a.output/'receipt.json',{'schema':'ACTUAL_SPRIME_MULTINODE_SOURCE3_V2','status':'PASS' if passed else 'FAIL','tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),
        'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':text.getvalue(),'node':n,'uid':1278,
        'job_id':str(proof['job_id']),'plan_reference':ref,'startup_proof_reference':C.ref(a.root_preflight),'source_references':C.own_sources(),'environment':E.environment(),
        'synthetic_IO_evidence':IO_EVIDENCE,'scientific_DATA_or_UFF_QM_called':False,'production_once_accessed':False});return 0 if passed else 3
if __name__=='__main__':raise SystemExit(main())