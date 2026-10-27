"""One actual analysis-day allocation; all checkpoints are internal DATA."""
import argparse,concurrent.futures as cf,gzip,io,json,multiprocessing as mp,os,pathlib,time,traceback,unittest
from . import contract as C,io as I,closure,common,hof,cache,worker,statistics,source_inverse

def preflight(out):
    from .test_boundaries import Boundaries
    from workflows.data_v1_final.execution.cpu_analysis_day_v1.test_v1 import Boundaries as Resource
    from workflows.data_v1_final.conformers.formal_cpu_auto_finalize_mapping_v2.test_adapter import FinalizerBoundaries
    from workflows.data_v1_final.conformers.pm7_independent_cache32_v1.test_cache import CacheBoundaries
    from workflows.data_v1_final.conformers.pm7_hof_augmentation32_v1.test_derive import DerivedBoundaries
    suites=[unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (Boundaries,Resource,FinalizerBoundaries,CacheBoundaries,DerivedBoundaries)]
    C.need([s.countTestCases() for s in suites]==[6,3,8,8,3],'EXACT_ONCE_28_BOUNDARIES_BEFORE_DATA')
    inverse=source_inverse.proof();stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite(suites))
    ref=I.save(out/'preflight28.json',{'schema':'POSTPROCESS_ANALYSIS_DAY_PREFLIGHT_V1','tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),
      'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),'source_inverse':inverse,'DATA_opened':False})
    C.need(r.testsRun==28 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'ALL28_ACTUAL_CPU_PASS_REQUIRED_BEFORE_DATA');return ref

def own_claim(ctx,task,d7_task):
    key=C.F.sha_value(['POSTPROCESS_READONLY_GEOMETRY_V1',task['cache_key'],ctx.plan['packed_receipt_reference']]);root=C.ROOT/'artifacts/conformers/postprocess_day_v1/claims'
    root.mkdir(parents=True,exist_ok=True,mode=0o700);path=root/(key+'.json')
    if path.exists():return key,None,ctx.read(ctx.reference(path))
    value={'schema':'POSTPROCESS_READONLY_MOLECULE_CLAIM_V1','cache_key':task['cache_key'],'key':key,'molecule_id':task['meta']['molecule_id'],
      'job_id':ctx.job_id,'uid':1278,'node':ctx.plan['node'],'plan_reference':ctx.plan_ref,'packed_receipt_reference':ctx.plan['packed_receipt_reference'],
      'output_directory':str(ctx.out),'original_records_SHA':C.F.sha_value(task['records']),'canonical_HOF_SHA':C.F.sha_value(task['hof']),
      'scientific_once_or_UFF_or_QM':False,'automatic_retry':False}
    ref=I.save(path,value);ctx.written+=ref['bytes'];return key,ref,value

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=C.G.load(a.plan);proof=I.admit(a,plan);out=pathlib.Path(plan['output_directory'])
    C.need(out.is_absolute() and C.ROOT/'artifacts/conformers/postprocess_day_v1' in out.parents and not out.exists()
      and not any(x.is_symlink() for x in (out,*out.parents)),'ONE_FRESH_POSTPROCESS_OUTPUT_NO_OLD_FILE_WRITES')
    out.mkdir(parents=True,mode=0o700)
    for name in ('molecules','starts','progress','orders','geometry_witnesses','checkpoints','duckdb_tmp'):(out/name).mkdir()
    ctx=None;db=None;active={};fatal=None;gates=None;expected_common=None;catalog_rows=[];pre=None;collector=None
    try:
        pre=preflight(out);value,receipt,packed,original,prior,cache_plan,parents,data=C.inputs(plan)
        ctx=I.Context(plan,proof,C.G.meta_pin(a.plan),out);ctx.authorized(parents);ctx.authorized(data);C.need(ctx.observe(force=True) is None,'ACTUAL_DAY_QUOTA_MEMORY_AND_CLOCK_BEFORE_DATA');ctx.start()
        import duckdb,pyarrow as pa,pyarrow.parquet as pq
        db=duckdb.connect(str(out/'work.duckdb'));db.execute('SET threads='+str(ctx.cpus));db.execute("SET memory_limit='32GB'");db.execute('SET temp_directory='+C.q(out/'duckdb_tmp'));ctx.db=db
        ctx.formal_reference=cache_plan['formal_source'];ctx.require(ctx.formal_reference)
        index_ref,index=closure.build(ctx,receipt,packed,original)
        if index['status']=='ALL_SPRIME_ATTEMPTS_TERMINAL':
            try:common.build(ctx,index_ref)
            except SystemExit as exc:
                C.need(exc.code==2,'ONLY_ORIGINAL_QUALITY_HOLD_CAN_CONTINUE_PM7_CACHE');gates={'quality_hold':True,'original_gate_exit':2}
        member_paths=sorted((ctx.common_out/'membership').glob('*.parquet')) if (ctx.common_out/'membership').exists() else []
        if member_paths:
            db.execute('CREATE VIEW final_common AS SELECT * FROM read_parquet(['+','.join(C.q(p) for p in member_paths)+'])')
            expected_common=db.execute('SELECT count(*) FROM final_common WHERE common_population').fetchone()[0]
        else:db.execute('CREATE TABLE final_common(molecule_id VARCHAR,common_population BOOLEAN)')
        uff=sorted((ctx.common_out/'physical_geometry').glob('uff_sprime-*.parquet')) if (ctx.common_out/'physical_geometry').exists() else []
        if uff:db.execute('CREATE VIEW uff_sources AS SELECT * FROM read_parquet(['+','.join(C.q(p) for p in uff)+'])')
        else:db.execute('CREATE TABLE uff_sources(molecule_id VARCHAR)');expected_common=None
        roles_ref,role_parts=ctx.roles(value);db.execute('CREATE VIEW all_roles AS SELECT * FROM read_parquet(['+','.join(C.q(r['path']) for r in role_parts)+'])')
        C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM all_roles').fetchone()==(1220466,1220466),'ALL_FROZEN_SOURCE_ROLES_UNCHANGED')
        descriptors=cache.setup(ctx,db,cache_plan)
        if expected_common is not None:cache.project_old_uff(ctx,db)
        h_ref=hof.project(ctx,db,cache_plan);collector=statistics.Collector(ctx,db)
        context={'proof':proof};count=0;unknown=[]
        def collect(pool,wait_all=False):
            while active:
                ctx.observe([p.pid for p in pool._processes.values() if p.pid]);done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    key,mid,is_common=active.pop(future)
                    try:
                        r=future.result();ctx.written+=r['packet_reference']['bytes'];collector.add(r['packet_reference'],mid,is_common)
                        if r['status']=='READONLY_MOLECULE_UNKNOWN':
                            unknown.append({'molecule_id':mid,'key':key,'packet_reference':r['packet_reference'],'status':r['status']});ctx.stop=ctx.stop or 'READONLY_EXECUTION_UNKNOWN_STOP_NEW_WORK'
                        catalog_rows.append(dict(r,claim_reference=ctx.reference(C.ROOT/'artifacts/conformers/postprocess_day_v1/claims'/(key+'.json'))))
                    except BaseException as exc:unknown.append({'molecule_id':mid,'key':key,'error':repr(exc),'traceback':traceback.format_exc()});ctx.stop=ctx.stop or 'READONLY_EXECUTION_UNKNOWN_STOP_NEW_WORK'
                    finally:
                        for name in ('starts/'+key+'.json','progress/'+key+'.jsonl'):
                            path=out/name
                            if path.exists():ctx.written+=path.stat().st_size
                        ctx.release(key)
                if done and not wait_all:return
        with cf.ProcessPoolExecutor(max_workers=ctx.cpus,mp_context=mp.get_context('spawn'),initializer=worker.initialize,initargs=(context,)) as pool:
            for descriptor in descriptors:
                if ctx.observe() is not None:break
                metas,by=cache.batch(ctx,db,descriptor)
                for meta in metas:
                    while len(active)>=ctx.cpus:collect(pool)
                    if ctx.observe() is not None:break
                    mid=meta['molecule_id'];role=db.execute('SELECT source_role,effective_role FROM all_roles WHERE molecule_id=?',[mid]).fetchone();C.need(role is not None,'ONE_TRUE_FROZEN_ROLE_PER_MOLECULE')
                    meta=dict(meta,split_role=role[0],effective_role=role[1]);task=cache.task(ctx,meta,by[mid],cache_plan,h_ref)
                    prior_cache=cache.reuse(ctx,db,task,cache_plan);d7_task=cache.d7_task(ctx,db,meta,by[mid],task['hof']) if expected_common is not None else None
                    reserve=min((256<<20),max(8<<20,2*task['software_bound']['packet_reserve_bytes']+(16<<20)));key=C.F.sha_value(['POSTPROCESS_READONLY_GEOMETRY_V1',task['cache_key'],plan['packed_receipt_reference']]);ctx.reserve(key,reserve)
                    key,claim_ref,claim=own_claim(ctx,task,d7_task)
                    if claim_ref is None:
                        try:
                            recovered=cache.recover_day(ctx,db,task,key,claim,d7_task);collector.add(recovered['packet_reference'],mid,d7_task is not None)
                            catalog_rows.append(recovered)
                        except BaseException as exc:
                            unknown.append({'molecule_id':mid,'key':key,'claim':claim,'status':'EXISTING_READONLY_CLAIM_HOLD','error':repr(exc),'traceback':traceback.format_exc()});ctx.stop=ctx.stop or 'EXISTING_CONSUMED_READONLY_CLAIM_HOLD'
                        finally:ctx.release(key)
                        if ctx.stop:break
                        continue
                    future=pool.submit(worker.one,task,prior_cache,d7_task,str(out/'molecules'/(key+'.json.gz')),claim_ref);active[future]=(key,mid,d7_task is not None);count+=1
                ctx.write_json_new(out/'checkpoints'/('group-%d-shard-%d.json'%(descriptor['file_group'],descriptor['shard_index'])),{'descriptor':descriptor,'dispatch_count':count,
                  'actual_one_parent_job_id':ctx.job_id,'child_job_or_child_C0':False,'native_tasks_may_still_be_running':True})
                if ctx.stop is not None:break
            collect(pool,True)
        stats=collector.report(expected_common);stats_ref=ctx.write_json_new(out/'conformer_statistics.json',stats)
        ctx.finish();resource_ref=ctx.write_json_new(out/'resource_observations.json',{'observations':ctx.samples,'complete_within_this_finite_parent':True,'failure':ctx.failure})
        catalog_ref=ctx.write_parquet_new(out/'molecule_catalog.parquet',pa.Table.from_pylist(catalog_rows) if catalog_rows else pa.table({'molecule_id':pa.array([],type=pa.string())}))
        unknown_ref=ctx.write_json_new(out/'unknown_molecules.json',unknown);manifest_ref=ctx.reference(ctx.common_out/'manifest.json') if (ctx.common_out/'manifest.json').exists() else None
        ctx.write_json_new(out/'receipt.json',{'schema':'CONFORMERS_POSTPROCESS_DAY_RECEIPT_V1','status':'ONE_PARENT_DRAINED_ACTUAL_TERMINAL_AND_ROOT_REVIEW_REQUIRED',
          'job_id':ctx.job_id,'runtime':{'job_id':ctx.job_id,'node':plan['node'],'uid':1278,'cpus':ctx.cpus},'plan_reference':ctx.plan_ref,
          'startup_proof_reference':C.G.meta_pin(a.startup_proof),'preflight_reference':pre,'outcome_index_reference':index_ref,'common_candidate_reference':manifest_ref,
          'statistics_reference':stats_ref,'order_tables':stats['order_tables'],'geometry_witness_tables':stats['geometry_readback_witness_tables'],'catalog_reference':catalog_ref,'unknown_reference':unknown_ref,'unknown_molecules':len(unknown),
          'actual_PM7_molecule_packets':len(catalog_rows),'expected_PM7_molecules':1220466,'resource_report':dict(ctx.report(),full_observations_reference=resource_ref),'original_quality_hold':gates,
          'PM7_full_source_cache_complete':stats['PM7_full_source_cache_complete'],'ordinary_Common_D7_geometry_complete':stats['ordinary_Common_D7_geometry_complete'],
          'three_order_Common_release_eligible':stats['three_order_Common_release_eligible'],'actual_parent_C0':'PENDING_ROOT_SACCT','Common_or_D7_or_training_release':False,
          'current_parent_cost_append_required':True,'no_new_UFF_or_QM':True,'no_child_Slurm_jobs':True,'N1_extra_domain_still_independent':True})
        return 0
    except BaseException as exc:
        failure={'schema':'CONFORMERS_POSTPROCESS_DAY_FAILURE_V1','error':repr(exc),'traceback':traceback.format_exc(),'preflight_reference':pre,
          'actual_parent_job_id':str(proof['job_id']),'old_DATA_and_claims_untouched':True,'resource':ctx.report() if ctx else None,'actual_cost_pending':True}
        if ctx:ctx.write_json_new(out/'failure.json',failure)
        else:I.save(out/'failure.json',failure)
        raise
    finally:
        if ctx:ctx.finish()
        if db:db.close()

if __name__=='__main__':raise SystemExit(main())
