"""Fresh CPU full native XYZ -> existing conservative non-H identity fallback."""
import argparse,collections,hashlib,io,os,stat,sys,time,traceback,unittest
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.marcel_drugs_keys_main_v1 import runtime as B
from . import contract as C,projection as P
Q=C.Q


def frame(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid]


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_PURE_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    proof={name:{'module':fn.__module__,'filename':fn.__code__.co_filename,'first_line':fn.__code__.co_firstlineno}
        for name,fn in (('native_composition',P.native_composition),('identity',P.identity))}
    result={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),
        'before_original_XYZ_body':True,'direct_unchanged_function_objects':proof,'new_UFF_QM_or_key_computations':0}
    Q.write_new(out/'fixtures3.json',result);Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS_BEFORE_XYZ')
    return result


def observe(plan,baseline,out,budget,check,progress,writers):
    ref=plan['data_references'][0];path=Path(ref['path'])
    Q.need(path.is_absolute() and Q.ROOT/'artifacts' in path.parents and '..' not in path.parts
        and not any(p.is_symlink() for p in (path,*path.parents)),'ONLY_LITERAL_ORIGINAL_XYZ_SOURCE')
    info=path.lstat();Q.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and info.st_size==ref['bytes'],'ACTUAL_MAIN_OWNER_AND_DECLARED_SOURCE_BYTES')
    sha=hashlib.sha256();md5=hashlib.md5();n=0;symbols=collections.Counter();hist=collections.Counter();compositions=collections.Counter();frames=0
    source_writer=B.Writer(out/'all7211_native_source_frames.jsonl',budget);writers.append(source_writer)
    identity_writer=B.Writer(out/'all7211_conservative_composition_identities.jsonl',budget);writers.append(identity_writer)
    with path.open('rb') as f:
        before=os.fstat(f.fileno());Q.need(frame(before)==frame(info),'SAME_ACTUAL_SOURCE_FD')
        for block in iter(lambda:f.read(1<<20),b''):
            check();sha.update(block);md5.update(block);n+=len(block);progress.update(phase='CURRENT_WHOLE_SOURCE_CHECKSUM',bytes=n)
        Q.need(n==ref['bytes'] and sha.hexdigest()==ref['sha256'] and md5.hexdigest()==C.MD5
            and frame(os.fstat(f.fileno()))==frame(before),'CURRENT_WHOLE_AUTHOR_SHA_PUBLISHED_MD5_STABLE_FSTAT')
        f.seek(0)
        while True:
            progress.update(phase='NATIVE_SOURCE_FRAME',next_physical_frame_ordinal=frames,next_source_offset=f.tell())
            source=P.read_frame(f,frames,check)
            if source is None:break
            Q.need(frames<7211,'NO_UNDECLARED_EXTRA_SOURCE_FRAME')
            event={'event':'ORIGINAL_NATIVE_FRAME_DURABLE_BEFORE_COMPOSITION','source':source,'original_XYZ_reference':ref}
            start=source_writer.bytes;source_writer.write(event,dispatch=False)
            # The exact original source-count event has been fsynced by the
            # unchanged Writer before the unchanged identity functions run.
            row=P.project(source,ref);row.update(source_frame_event_offset=start,source_frame_event_bytes=source_writer.bytes-start,
                source_frame_event_sha256=hashlib.sha256(P.canonical(event)).hexdigest())
            identity_writer.write(row,dispatch=False);symbols.update(source['native_symbol_counts']);hist[str(source['atoms'])]+=1
            compositions[tuple(map(tuple,row['non_h_composition']))]+=1;frames+=1
            progress.update(completed_native_source_rows=source_writer.rows,completed_identity_rows=identity_writer.rows)
        Q.need(frame(os.fstat(f.fileno()))==frame(before)==frame(path.lstat()) and f.tell()==ref['bytes'],'SOURCE_UNCHANGED_AND_EXACT_EOF_AFTER_ALL_FRAMES')
    Q.need(frames==source_writer.rows==identity_writer.rows==7211 and dict(symbols)==baseline['symbols']
        and dict(hist)==baseline['atom_count_histogram'] and sum(compositions.values())==7211,'EXACT1897_NATIVE_SYMBOL_ATOM_HISTOGRAM_AND_ALL7211_COUNT_CONSERVATION')
    return {'source_rows':source_writer.rows,'identity_rows':identity_writer.rows,'native_symbol_counts':dict(symbols),'atom_count_histogram':dict(hist),
        'unique_non_H_composition_count':len(compositions),'composition_population_mass':sum(compositions.values()),
        'all_source_rows_retained_even_when_composition_repeats':True,'current_whole_SHA_and_published_MD5_verified':True,
        'current_same_FD_before_after_frame':frame(before),'data_references':[source_writer.reference(),identity_writer.reference()],
        'graph_full_key_UNKNOWN_rows':7211,'conservative_composition_rows':7211,'new_key_or_WP5_computation_rows':0,
        'coverage_basis':'AUTHOR_ALL7211_SET_ASSERTION_PLUS_COMPLETE_NATIVE_XYZ_CONSERVATIVE_COMPOSITION_NOT_MAT_ID_MAPPING'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan=Q.load(args.plan);baseline,parents=C.inputs(plan)
    Q.need(plan['schema']=='QM7B_AUTHOR_NATIVE_COMPOSITION_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS and plan['output_cap_bytes']==C.CAP,'EXACT_NEW_COMPOSITION_ONLY_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(args.plan),'--startup-proof',str(args.startup_proof)]
    proof=R.require_startup(args.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(args.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];authority=C.T.meta(req['queue_authority_reference']);allowed={'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']}
    Q.need(req['node'] in allowed and req['kind']=='analysis' and req['pilot'] is False and req['cpus']==16
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['wall_seconds']==plan['wall_seconds']
        and type(plan['wall_seconds']) is int and 600<=plan['wall_seconds']<=1800 and plan['wall_seconds']%60==0
        and req['estimated_peak_output_bytes']==req['stage_output_cap_bytes']==C.CAP and req['data_references']==plan['data_references']
        and not req.get('deferred_authority_references') and proof['account_free_bytes']-C.CAP>=200000000000,'FRESH_ACTUAL_MAIN_CPU16_NO_MEMORY_BOUNDED128MIB_ACCOUNT_RESERVE')
    review=C.T.meta(req['scope']['review']);Q.need(req['scope']['mode']=='BOUNDED_METADATA_PREPARATION'
        and review['author_asserted_all7211_set_conservative_composition_only_authorized'] is True
        and review['exact_MAT_ID_native_graph_or_pool_release_authorized'] is False,'INDEPENDENT_ROOT_AUTHOR_SET_ONLY_REVIEW_NO_GRAPH_RELEASE')
    cost=C.T.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_COST_AND_QUALITY_AUTHORITY')
    for path in [*(C.HERE/name for name in C.FILES),*C.OLD]:Q.need(Q.pin(path) in req['source_references'],'ALL_FROZEN_AND_NEW_SOURCE_PINS')
    for name,module in list(sys.modules.items()):
        file=getattr(module,'__file__',None)
        if name.startswith('workflows.expansion') and file and Path(file).suffix=='.py':Q.need(Q.pin(file) in req['source_references'],'ACTUAL_IMPORTED_EXPANSION_SOURCE_PIN:'+name)
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'EXACT_INTEGRATED_PRIMARY_FULL_ARGV')
    out=Path(plan['output_directory']);Q.need(out.is_absolute() and '..' not in out.parts and Q.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_OUTPUT_NO_SOURCE_MODIFICATION');out.mkdir(parents=True,mode=0o700)
    budget=B.Budget(plan,proof,out);gate=None;progress={};writers=[];started=time.monotonic()
    def check():budget.check(dispatch=False);Q.need(budget.stop_new is None,budget.stop_new or 'ORIGINAL_RESOURCE_STOP_NO_NEW_FRAME')
    try:
        gate=fixtures(out);check();result=observe(plan,baseline,out,budget,check,progress,writers)
        Q.write_new(out/'receipt.json',{'schema':'QM7B_AUTHOR_NATIVE_COMPOSITION_RECEIPT_V1','status':'ALL7211_CONSERVATIVE_COMPOSITION_ROWS_OBSERVED_GRAPH_KEYS_UNKNOWN_ROOT_REVIEW_REQUIRED',
            'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22','plan_reference':Q.pin(args.plan),
            'startup_proof_reference':Q.pin(args.startup_proof),'accepted_format_receipt_reference':plan['accepted_format_receipt_reference'],
            'accepted_format_accounting_reference':plan['accepted_format_accounting_reference'],'author_transport_reference':plan['author_transport_reference'],
            'decontamination_policy_reference':plan['decontamination_policy_reference'],'original_XYZ_reference':plan['data_references'][0],
            'fixtures':gate,'result':result,'source_ID_namespace':C.NAMESPACE,'native_author_IDs_present':False,'MAT_row_or_native_graph_mapping':False,
            'full_keys_graph_charge_stereo_isotope_UNKNOWN':True,'conservative_non_H_composition_policy_applied':True,
            'global_decontamination_pool_training_release':False,'new_network_UFF_QM_calls':0,'production_once_opened_or_modified':False,
            'elapsed_seconds':time.monotonic()-started,'observed_RSS_peak_bytes':budget.peak,'minimum_MemAvailable_bytes':budget.minimum,
            'runtime_statvfs_is_not_refreshed_account_quota':True,'actual_new_parent_cost':'PENDING_ROOT_TERMINAL_ACCOUNTING','cost_overrun_action':'REPORT_AND_CONTINUE'})
        return 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'QM7B_NATIVE_COMPOSITION_FAILURE_V1','error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(),
            'fixtures':gate,'actual_progress':progress,'durable_prefix_DATA_references':[w.reference() for w in writers],
            'all7211_closed':False,'graph_MAT_or_pool_release':False,'actual_cost':'PENDING_ROOT_ACCOUNTING','source_or_once_modified':False})
        raise
    finally:
        for writer in writers:
            if not writer.stream.closed:writer.close()


if __name__=='__main__':raise SystemExit(main())
