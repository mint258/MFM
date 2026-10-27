"""Finite source-TRAIN cache calibration; final Common normalization is locked."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,io,json,multiprocessing as mp,os,time,unittest
from pathlib import Path
from .profile import initialize,run_group
from .reader import equal_bits,need
from workflows.data_v1_final.labels.streaming_v1.calibration import advance,initial_queries,merge_qr
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import load,require,small_ref,new_root,save,unique_bytes
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import start_observer,stop_requested
SCOPE='source_train_typed_cache_512_profile_v2'


def guard(cfg,path,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    provisional=load(proof_path);request=provisional['request'];bp=request['producer_resource_binding_reference'];binding=load(require(bp))
    need(cfg['schema']=='SOURCE_TRAIN_TYPED_CACHE_PROFILE_CONFIG_V1' and cfg['scope_parameters']['records']==4251
      and cfg['scope_parameters']['molecules']==512 and cfg['scope_parameters']['groups']==16
      and cfg['source_role']=='TRAIN' and cfg['full_source_population'] is False
      and cfg['final_Common_normalization_allowed'] is False and cfg['candidate_masks_are_final'] is False,'FINITE_SOURCE_TRAIN_ONLY_NO_COMMON_OR_FINAL_MASKS')
    need(cfg['whole_output_cap_bytes']==4<<30 and cfg['worker_output_cap_bytes']==128<<20
      and cfg['row_serialized_cap_bytes']==64<<20 and cfg['worker_rss_stop_bytes']==3<<30,'EXACT_FINITE_SOFTWARE_CAPS')
    need(binding['schema']=='SOURCE_TRAIN_TYPED_CACHE_PROFILE_RESOURCE_BINDING_V1' and binding['scope_key']==SCOPE
      and binding['scientific_config_reference']==small_ref(path) and binding['scope_parameters']==cfg['scope_parameters']
      and binding['resource_authority_reference']==request['queue_authority_reference']
      and binding['memavailable_soft_floor_bytes']==4<<30,'EXACT_NEW_NOMEM_RESOURCE_BINDING')
    need(request['pilot'] is True and request['cpus']==16 and request['wall_seconds']<=7200
      and request['estimated_peak_output_bytes']>=cfg['whole_output_cap_bytes'],'EXACT_FINITE_PROFILE_ALLOCATION')
    proof=require_startup(proof_path,expected_kind='analysis',expected_scope_key=SCOPE,
      expected_scope_parameters=cfg['scope_parameters'],required_references=[small_ref(path),bp,*cfg['small_references']])
    need(all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),
      'PINNED_SINGLE_THREAD_LINEAR_ALGEBRA_ENVIRONMENT')
    for r in cfg['source_references']:need(r in request['source_references'],'ACTUAL_ROOT_SOURCE_PINS');require(r)
    need(proof['account_free_bytes']>=200000000000+cfg['whole_output_cap_bytes'],'FRESH_QUOTA_200GB_PLUS_FINITE_PROFILE_CAP')
    start_observer(proof,binding);return proof


def fixtures(cfg,root):
    from . import test_cache
    test_cache.SCIENCE=cfg['science']
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_cache.CacheAdapterBoundaries)
    need(suite.countTestCases()==3,'EXACT_THREE_BASE_METADATA_BOUNDARIES')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    passed=result.testsRun==3 and result.wasSuccessful() and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses
    receipt=save(root/'fixture_gate.json',{'status':'PASS' if passed else 'FAIL_NO_BODY','tests_run':result.testsRun,
      'source_reference':small_ref(Path(__file__).with_name('test_cache.py')),'transcript':stream.getvalue(),
      'real_cache_owner_or_histogram_body_read':False,'old_fixture_suites_rerun':False})
    print(stream.getvalue(),flush=True);need(passed,'CACHE_ADAPTER_FIXTURES_BEFORE_REAL_BODY');return receipt


def reduction(cfg,reports,root):
    import pyarrow.parquet as pq
    fields=load(require(cfg['field_map_reference']));counts=collections.defaultdict(collections.Counter)
    merged=collections.Counter();key_limit=1000000
    for r in reports:
        for fid,v in r['field_counts'].items():counts[fid].update(v)
        source=pq.ParquetFile(require(r['radix_histogram']))
        try:
            for batch in source.iter_batches(batch_size=4096,use_threads=False):
                for row in batch.to_pylist():merged[(row['field_id'],row['node_id'],row['prefix_bits'],int(row['prefix']))]+=row['n']
                need(len(merged)<=key_limit,'FINITE_PARENT_HISTOGRAM_KEYS_CAP_NOT_APPROXIMATION')
        finally:source.close()
    expected=load(require(cfg['matched_legacy_reference']))['fields']
    need(all(c['records']==4251 and c['newly_masked_records']/4251<=.01 for c in counts.values()),'UNCHANGED_ONE_PERCENT_NEW_MASK_HOLD')
    need(all(counts[str(f['field_id'])]['TRAIN_valid_leaves']==expected[str(f['field_id'])]['TRAIN_n'] for f in fields),
      'EXACT_SOURCE_TRAIN_VALID_LEAF_MASS_DIFFERS_FROM_ORIGINAL')
    rows=[{'field_id':fid,'node_id':node,'prefix_bits':bits,'prefix':prefix,'n':n} for (fid,node,bits,prefix),n in sorted(merged.items())]
    nxt,done=advance(cfg['queries'],rows);stage=cfg['query_stage'];finished={k:list(v) for k,v in stage['finished'].items()}
    purpose=cfg['queries']['purpose'];finished[purpose].extend(done)
    need(len({r['field_id'] for r in finished[purpose]})==len(finished[purpose]),'NO_DUPLICATE_FINISHED_QUERY_FIELD')
    result={'schema':'SOURCE_TRAIN_TYPED_CACHE_QUERY_STAGE_V1','cache_manifest_reference':cfg['cache_manifest_reference'],
      'field_map_reference':cfg['field_map_reference'],'source_role':'TRAIN','finished':finished,'queries':nxt,
      'final_Common_normalization_allowed':False,'full_source_population':False}
    reference=None
    if not nxt['fields'] and purpose=='median':
        centers={r['field_id']:r['value'] for r in finished['median'] if r['value'] is not None}
        result['queries']=initial_queries(fields,'MAD',centers)
    elif not nxt['fields'] and purpose=='MAD':
        med={r['field_id']:r for r in finished['median']};mad={r['field_id']:r for r in finished['MAD']}
        need(set(med)=={f['field_id'] for f in fields},'ALL146_MEDIANS_REQUIRED')
        values={str(fid):{'median':v['value'],'MAD':mad.get(fid,{}).get('value'),'TRAIN_n':v['n'],
          'MAD_n':mad.get(fid,{}).get('n',0),'status':'EXACT' if v['value'] is not None and mad.get(fid,{}).get('value') is not None else 'UNDEFINED_NO_FINITE_SCALE'} for fid,v in med.items()}
        old=load(require(cfg['matched_legacy_reference']))['fields']
        equal=all(equal_bits(values[k][name],old[k][name]) for k in values for name in ('median','MAD','TRAIN_n','MAD_n'))
        reference=save(root/'SOURCE_TRAIN_median_MAD_provisional.json',{'schema':'SOURCE_TRAIN_TYPED_CACHE_REFERENCE_V1',
          'status':'EXACT_MATCHED_512_SOURCE_TRAIN_NOT_FULL_OR_COMMON','cache_manifest_reference':cfg['cache_manifest_reference'],
          'fields':values,'fit_role':'TRAIN_ONLY','legacy_reference_equal':equal,'candidate_masks_are_final':False,
          'source_full_population_calibration_completed':False,'final_Common_D4':False})
        need(equal,'RECOMPUTED_EXACT512_REFERENCE_DIFFERS_FROM_LEGACY_NO_NEW_TOLERANCE')
    next_ref=save(root/'next_query_stage.json',result)
    models={str(f['field_id']):merge_qr([r['energy_TSQR'][str(f['field_id'])] for r in sorted(reports,key=lambda r:r['group_index'])])
      for f in fields if f['element_reference_eligible']}
    model_ref=save(root/'SOURCE_TRAIN_element_references_provisional.json',{'scope':'MATCHED_512_SOURCE_TRAIN_ONLY_NOT_COMMON',
      'models':models,'cache_manifest_reference':cfg['cache_manifest_reference'],'final_Common_D4':False})
    return next_ref,reference,model_ref,{k:dict(v) for k,v in counts.items()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','startup-proof','output'):p.add_argument('--'+key,required=True)
    a=p.parse_args();started=time.monotonic();cfg=load(a.config);proof=guard(cfg,a.config,a.startup_proof);root=new_root(a.output)
    phase=time.monotonic();timings={'fresh_guard_seconds':phase-started}
    try:
        gate=fixtures(cfg,root);timings['three_base_projection_fixtures_seconds']=time.monotonic()-phase;phase=time.monotonic()
        need(not stop_requested(),'SOFT_STOP_BEFORE_FIRST_CACHE_WAVE_NO_BODY')
        ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(cfg,str(root),barrier)) as pool:
            references=list(pool.map(run_group,cfg['groups'],chunksize=1))
        reports=[load(require(r)) for r in references];timings['cache_worker_pool_seconds']=time.monotonic()-phase;phase=time.monotonic()
        need(len(reports)==len({r['pid'] for r in reports})==16,'SIXTEEN_REAL_CACHE_WORKERS')
        closed=all(r['status']=='COMPATIBLE_CLOSED' for r in reports)
        next_ref=reference=model=None;counts={}
        if closed:next_ref,reference,model,counts=reduction(cfg,reports,root)
        timings['integer_histogram_reduction_and_QA_seconds']=time.monotonic()-phase
        need(unique_bytes(root)+(64<<20)+(2<<20)<=cfg['whole_output_cap_bytes'],'WHOLE_PROFILE_BUDGET_WITH_OBSERVER')
        result={'schema':'SOURCE_TRAIN_TYPED_CACHE_PROFILE_MANIFEST_V1','status':'FINITE_PASS_CLOSED_PROVISIONAL_ONLY' if closed else 'INPUT_COMPATIBILITY_OR_RESOURCE_HOLD',
          'config':small_ref(a.config),'job_id':str(proof['job_id']),'groups':references,'fixture_gate':gate,
          'next_query_stage':next_ref,'exact_matched_512_reference':reference,'element_references':model,'field_counts':counts,
          'phase_seconds':timings,'elapsed_seconds':time.monotonic()-started,'numeric_cache_bytes_verified':sum(g['cache']['bytes'] for g in cfg['groups']),
          'original_source_Parquet_or_LMDB_read':False,'candidate_masks_are_final':False,'final_Common_D4':False,
          'full_source_population_calibration_completed':False,'size_rho_recomputed':False,'native_program_precision_verified':False,
          'automatic_next_job':False,'automatic_retry':False}
        save(root/'manifest.json',result);print(json.dumps({'status':result['status'],'next_query_stage':next_ref}),flush=True)
        need(closed,'COMPATIBILITY_HOLD_EXACT_SOURCE_ROW_RECOVERY_REQUESTS_RETAINED')
    except BaseException as exc:
        save(root/'failure.json',{'error':type(exc).__name__+':'+str(exc),'partials_preserved':True,'automatic_retry':False});raise

if __name__=='__main__':main()
