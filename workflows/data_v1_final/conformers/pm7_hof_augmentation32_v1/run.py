"""Fresh CPU canonical-HOF/order augmentation of actual geometry-only cache32."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,hashlib,io,multiprocessing as mp,os,pathlib,socket,sys,time,unittest
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.pm7_hof_augmentation32_v1 import contract as C,derive
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import io as I,inheritance as H
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1.prepare32 import canonical_hof
OPTIONS=('plan','root-preflight','quota-reuse-review','output');WORK={}


def write_json(path,value,out):
    raw=C.canonical(value)+b'\n'
    C.need(pathlib.Path(out) in pathlib.Path(path).parents,'ONLY_NEW_OWN_OUTPUT')
    with I.R.lock(out):
        C.need(I.R.disk_bytes(out)+len(raw)+(64<<20)<=C.CAP,'AUGMENTATION_WHOLE_OUTPUT_CAP')
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        I.R.fsync_dir(pathlib.Path(path).parent)
    reference=I.ref(path)
    C.need(reference['bytes']==len(raw) and reference['sha256']==hashlib.sha256(raw).hexdigest(),'EXACT_DURABLE_AUGMENTATION_READBACK')
    return reference


def admit(args):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import PY
    script=pathlib.Path(__file__).absolute();argv=[PY,'-B',str(script)];required=[]
    C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==script and
      pathlib.Path(sys.argv[0]).absolute()==script,'ACTUAL_NEW_AUGMENTATION_PRIMARY')
    for name in OPTIONS:
        path=getattr(args,name.replace('-','_'));C.need(path.is_absolute() and '..' not in path.parts,'LITERAL_NEW_CLI_LOCATOR')
        argv+=['--'+name,str(path)]
        if name not in ('root-preflight','output'):required.append(I.request_ref(args.root_preflight,path))
    plan_ref=I.request_ref(args.root_preflight,args.plan);plan=I.read(plan_ref)
    C.need(plan['schema']=='ROOT_PM7_HOF_AUGMENTATION32_PLAN_V1' and plan['status']=='APPROVED_EXACT32_DERIVED_ORDERS'
      and plan['reviewer']=='root' and plan['endpoint']=='202.38.247.57:22' and plan['uid']==1278
      and plan['scope_parameters']==C.scope() and plan['hof_mode']=='CANONICAL_VERIFIED'
      and plan['common'] is False and plan['full_cache_release'] is False,'INDEPENDENT_EXACT_NEW_ROOT_PLAN')
    own=[I.ref(C.HERE/name) for name in C.FILES];quota=I.request_ref(args.root_preflight,args.quota_reuse_review)
    reuse,Q,resources=I.R.quota_reuse(quota,I.F.sources())
    proof=runtime.require_startup(args.root_preflight,expected_scope_key=C.SCOPE,expected_scope_parameters=C.scope(),
      expected_execution_argv=argv,expected_source=script,expected_kind='analysis',
      required_references=(*required,*own,*I.sources(),*resources,*plan['metadata_source_references']))
    request=proof['request'];C.need(request['pilot'] is False and request['node']=='compute-0-13' and request['cpus']==16
      and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and request['scope']['mode']=='BOUNDED_METADATA_PREPARATION'
      and 0<request['wall_seconds']<=3600 and request['estimated_peak_output_bytes']>=C.CAP,'NEW_CPU16_NO_MEM_NONPILOT_SCOPE')
    os.environ.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    os.environ['CUDA_VISIBLE_DEVICES']=''
    session={'proof_reference':I.ref(args.root_preflight),'main_source':I.ref(script),'execution_argv':argv,
      'parent_pid':os.getpid(),'parent_start_ticks':I.R.proc_ticks(os.getpid()),'boot_id':proof['boot_id'],
      'job_id':str(proof['job_id']),'quota_reuse_review_reference':quota,'output_root':str(args.output),
      'source_references':[*own,*I.sources()]}
    return plan,plan_ref,proof,session


def fixtures(out):
    # Existing source-only inverse/AST proof is not a rerun of the old8 fixtures.
    inheritance=H.proof();source=write_json(out/'source_inheritance.json',inheritance,out)
    from workflows.data_v1_final.conformers.pm7_hof_augmentation32_v1.test_derive import DerivedBoundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(DerivedBoundaries);stream=io.StringIO()
    C.need(suite.countTestCases()==3,'EXACT_THREE_DERIVED_CACHE_FIXTURES')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    passed=(result.testsRun==3 and result.wasSuccessful() and not result.skipped
      and not result.expectedFailures and not result.unexpectedSuccesses)
    reference=write_json(out/'fixtures3.json',{'status':'PASS' if passed else 'FAIL_NO_BODY','tests_run':result.testsRun,
      'source_inheritance_reference':source,'transcript':stream.getvalue(),'scientific_body_opened':False},out)
    print(stream.getvalue(),flush=True);C.need(passed,'THREE_FIXTURES_BEFORE_CACHE_OR_HOF_BODY');return reference


def parent_inputs(plan,proof):
    refs=[plan[k] for k in ('geometry_receipt_reference','geometry_accounting_reference','prepared_reference','source_authority_reference')]
    I.authorized(proof,refs);receipt=I.read(refs[0]);account=I.read(refs[1]);prepared=I.read(refs[2]);authority=I.read(refs[3])
    C.need(receipt['schema']=='PM7_INDEPENDENT_CACHE32_RECEIPT_V1' and
      receipt['status']=='ACTUAL32_PM7_GEOMETRY_AND_GOLDEN16_CLOSED_REQUIRES_ROOT_REVIEW'
      and receipt['job_id']=='4521602' and receipt['geometry_complete']==receipt['completed_packets']==32
      and receipt['golden_geometry_equal_count']==16 and not(receipt['errors'] or receipt['unstarted_molecule_ids']
      or receipt['dispatched_without_validated_return_ids']),'ACTUAL_CLOSED_GEOMETRY32_NOT_FUTURE')
    I.authorized(proof,[account['raw_sacct_reference']]);parents=I.F.accounting(refs[1],[receipt['job_id']]);parent=parents[receipt['job_id']]
    C.need(account['endpoint']=='202.38.247.57:22' and account['uid']==1278 and parent['state']=='COMPLETED'
      and parent['exit_code']=='0:0' and int(parent['alloc_cpus'])==16,'REAL_MAIN_PARENT_C0_RAW_ACCOUNTING')
    C.need(receipt['prepared_reference']==refs[2] and prepared['source_authority_reference']==refs[3]
      and authority['common'] is False and authority['full_execution_authorized'] is False,'EXACT_ACTUAL_PREPARED_AND_MOTHER_AUTHORITY')
    C.need(len(receipt['packets'])==32 and len({r['molecule_id'] for r in receipt['packets']})==32,'EXACT_32_PACKET_ROSTER')
    return receipt,authority


def provenance(plan,records,proof):
    """Record→current owner→unique producer file; no new chemistry or source values."""
    authority=I.read(plan['hof_authority_review']);owner_ref=authority['latest_owner_reference']
    I.authorized(proof,[owner_ref,authority['projection_receipt_reference']]);I.source_check(owner_ref)
    projection=I.read(authority['projection_receipt_reference']);I.authorized(proof,[projection['source_files']])
    sources=I.read(projection['source_files'])
    import duckdb,pyarrow as pa
    db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='12GB'")
    try:
        db.register('wanted',pa.table({'molecule_id':sorted({r['molecule_id'] for r in records})}))
        rows=db.execute('SELECT o.molecule_id,o.attempt_id,o.job_id,o.task_id,o.lane FROM read_parquet('+I.C.q(owner_ref['path'])+
          ") o JOIN wanted USING(molecule_id) WHERE state='COMPLETE' AND receipt_context_consistent AND export_published").fetch_arrow_table().to_pylist()
    finally:db.close()
    by_mid={}
    for row in rows:C.need(row['molecule_id'] not in by_mid,'DUPLICATE_CANONICAL_OWNER_MOLECULE');by_mid[row['molecule_id']]=row
    result={}
    for row in records:
        owner=by_mid.get(row['molecule_id']);candidates=[]
        if owner is not None:
            candidates=[s for s in sources if s['family']=='pm7_neutral' and s['source_job_id']==owner['job_id']
                        and s['source_file_group']==row['file_group']]
        result[row['record_id']]={'native_pointer':row,'canonical_owner':owner,'latest_owner_reference':owner_ref,
          'source_files_reference':projection['source_files'],'source_file_candidates':candidates,
          'provenance_state':'CANONICAL_OWNER_AND_UNIQUE_SOURCE_LOCATOR' if len(candidates)==1 else 'PENDING_OWNER_OR_UNIQUE_SOURCE_LOCATOR',
          'source_file_SHA_policy':'INHERITED_PRODUCER_FULL_READBACK_AND_CURRENT_READER_STABLE_IDENTITY'}
    I.source_check(owner_ref);return result


def initialize(session,barrier):WORK.update(session=session,barrier=barrier)


def worker(item):
    I.continuation(WORK['session']);WORK['barrier'].wait(timeout=120) if item['first_wave'] else None
    task=item['task'];mid=task['molecule_id'];out=pathlib.Path(WORK['session']['output_root']);name=C.digest(mid)
    runtime={'job_id':WORK['session']['job_id'],'pid':os.getpid(),'parent_pid':os.getppid(),'uid':os.getuid(),
      'node':socket.gethostname().split('.')[0],'start_ticks':I.R.proc_ticks(os.getpid()),'boot_id':WORK['session']['boot_id']}
    start=write_json(out/'starts'/(name+'.json'),{'molecule_id':mid,'runtime':runtime,
      'geometry_packet_reference':task['geometry_packet_reference']},out)
    old=I.read_packet(task['golden_reference']) if task['golden_reference'] is not None else None
    result=derive.augment(task,item['hof'],item['provenance'],old)
    result.update(runtime=runtime,worker_start_reference=start)
    packet=write_json(out/'results'/(name+'.json'),result,out)
    C.need(I.read(packet)==result,'EXACT_AUGMENTATION_PACKET_READBACK')
    return {'molecule_id':mid,'packet_reference':packet,'runtime':runtime,'worker_start_reference':start,
      'status':result['status'],'hof_valid_count':result['hof_valid_count'],'records':result['records'],
      'golden_comparison':result['golden_comparison'],'convergence_null_review_records':result['convergence_null_review_records']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in OPTIONS:parser.add_argument('--'+name,type=pathlib.Path,required=True)
    args=parser.parse_args();plan,plan_ref,proof,session=admit(args);out=I.new_output(args.output)
    for name in ('dispatch','starts','results'):(out/name).mkdir()
    budget=I.budget(proof,session,out);C.need(budget.observe() is None,'FRESH_QUOTA_AND_RESOURCE_OBSERVATION_BEFORE_BODY');budget.start_monitor()
    results=[];errors=[];dispatched=[];queue=[];started=time.monotonic()
    try:
        fixture_ref=fixtures(out);receipt,authority=parent_inputs(plan,proof);tasks=[];all_records=[]
        I.authorized(proof,[plan['hof_authority_review']]);hreview=I.read(plan['hof_authority_review'])
        C.need(hreview['status']=='VERIFIED_FROZEN_PM7_B_SCALAR_READER','REAL_ROOT_CANONICAL_HOF_AUTHORITY_ONLY')
        for entry in receipt['packets']:
            C.need(budget.observe() is None,'RESOURCE_STOP_BEFORE_NEXT_CACHE_BODY')
            reference=entry['packet_reference'];golden=entry['golden_comparison'].get('golden_reference')
            I.authorized(proof,[reference]+([golden] if golden is not None else []));packet=I.read_packet(reference)
            C.need(packet['molecule_id']==entry['molecule_id'] and packet['cache_key']==entry['cache_key']
              and packet['runtime']['job_id']==receipt['job_id'],'ACTUAL_C0_PACKET_IDENTITY')
            task=derive.view(packet,reference,golden);tasks.append(task);all_records.extend(task['source_records'])
        C.need(len(all_records)==len({r['record_id'] for r in all_records})==203
          and {t['molecule_id'] for t in tasks}==set(authority['selected_molecule_ids'])
          and sum(t['golden_reference'] is not None for t in tasks)==16,'EXACT_EXISTING32_203_AND_GOLDEN16')
        record_provenance=provenance(plan,all_records,proof)
        hof,observations=canonical_hof({'hof_mode':'CANONICAL_VERIFIED','hof_authority_review':plan['hof_authority_review']},
           all_records,proof,out,budget)
        C.need(set(hof)=={r['record_id'] for r in all_records},'ALL203_HOF_STATES_RETAINED')
        for rid,value in hof.items():
            if value['valid']:C.need(record_provenance[rid]['provenance_state']=='CANONICAL_OWNER_AND_UNIQUE_SOURCE_LOCATOR',
               'VALID_CANONICAL_HOF_REQUIRES_UNIQUE_OWNER_FILE_PROVENANCE')
        hof_ref=write_json(out/'canonical_hof_source_observations.json',{'hof':hof,'record_provenance':record_provenance,
          'source_observations':observations,'root_hof_authority_review':plan['hof_authority_review'],
          'reader':'UNMODIFIED_prepare32.canonical_hof_AND_profile_common.read_hof_file',
          'native_energy_fallback_used':False,'new_tolerance_or_mask':False},out)
        queue=[{'task':t,'hof':{rid:hof[rid] for rid in t['ids']},
          'provenance':{rid:record_provenance[rid] for rid in t['ids']},'first_wave':i<16} for i,t in enumerate(tasks)]
        ctx=mp.get_context('spawn');barrier=ctx.Barrier(16);next_index=0
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(session,barrier)) as pool:
            pending={}
            while pending or (next_index<len(queue) and budget.observe() is None):
                # First16 form one observed/admitted atomic wave for the barrier.
                # Subsequent work stops at the latched soft STOP; running work drains.
                while len(pending)<16 and next_index<len(queue) and (next_index<16 or budget.stop is None):
                    item=queue[next_index];mid=item['task']['molecule_id']
                    write_json(out/'dispatch'/(C.digest(mid)+'.json'),{'molecule_id':mid,'stage':'HOF_DERIVED_ONLY',
                      'new_UFF_QM_calls':0,'original_geometry_packet_reference':item['task']['geometry_packet_reference']},out)
                    pending[pool.submit(worker,item)]=mid;dispatched.append(mid);next_index+=1
                if not pending:break
                done,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED);budget.observe()
                for future in done:
                    mid=pending.pop(future)
                    try:
                        record=future.result();C.need(record['molecule_id']==mid,'WORKER_MOLECULE_ID_CHANGED')
                        actual=I.read(record['packet_reference']);C.need(actual['runtime']==record['runtime'],'ACTUAL_WORKER_RETURN_AND_DURABLE_PACKET')
                        results.append(record)
                    except Exception as exc:errors.append({'molecule_id':mid,'error':repr(exc),'automatic_retry':False})
        goldens=[r for r in results if r['golden_comparison']['status']!='NOT_A_GOLDEN_MEMBER']
        counts=collections.Counter(r['golden_comparison']['status'] for r in goldens)
        complete=sum(r['status']=='CANONICAL_HOF_AND_DERIVED_ORDERS_COMPLETE' for r in results)
        closed=(len(results)==complete==32 and len({r['runtime']['pid'] for r in results})==16
          and counts=={'GOLDEN_CANONICAL_HOF_BITS_STATE_AND_ORDERS_EQUAL':16} and not(errors or budget.stop))
        report={'schema':'PM7_HOF_AUGMENTATION32_RECEIPT_V1','status':'ACTUAL32_HOF_ORDER_AND_GOLDEN16_CLOSED_REQUIRES_ROOT_REVIEW' if closed else 'HOF_ORDER_AUGMENTATION_PENDING_OR_GOLDEN_HOLD',
          'job_id':str(proof['job_id']),'plan_reference':plan_ref,'geometry_parent_receipt_reference':plan['geometry_receipt_reference'],
          'geometry_parent_accounting_reference':plan['geometry_accounting_reference'],'hof_observations_reference':hof_ref,
          'fixtures_reference':fixture_ref,'startup_proof_reference':session['proof_reference'],'completed_packets':len(results),
          'complete_molecules':complete,'records':sum(r['records'] for r in results),'valid_hof_records':sum(r['hof_valid_count'] for r in results),
          'actual_worker_pids':sorted({r['runtime']['pid'] for r in results}),'golden_comparison_counts':dict(counts),
          'packets':results,'errors':errors,'unstarted_molecule_ids':[q['task']['molecule_id'] for q in queue if q['task']['molecule_id'] not in dispatched],
          'dispatched_without_validated_return_ids':sorted(set(dispatched)-{r['molecule_id'] for r in results}),
          'elapsed_seconds':time.monotonic()-started,'budget':budget.report(),'new_UFF_calls':0,'new_QM_calls':0,
          'new_LMDB_reads':0,'new_geometry_or_RMSD_calls':0,'old_geometry_cache_modified':False,'common':False,
          'full_cache_release':False,'physical_int64_or_order_manifest_release':False}
        write_json(out/'receipt.json',report,out);print({'status':report['status'],'complete':complete,'goldens':dict(counts)})
        return 0 if closed else 3
    except BaseException as exc:
        write_json(out/'failure.json',{'error':repr(exc),'closed_packets':results,'dispatched_ids':dispatched,
          'automatic_retry':False,'original_cache_unchanged':True},out);raise
    finally:
        budget.close_monitor();write_json(out/'resource_observations.json',budget.report(),out)

if __name__=='__main__':raise SystemExit(main())
