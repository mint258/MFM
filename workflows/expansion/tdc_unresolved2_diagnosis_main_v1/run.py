"""Actual CPU only: preserve exact2 original unknown events and bind original ZIP."""
import argparse,collections,hashlib,io,json,os,socket,stat,sys,time,traceback,unittest,zipfile,zlib
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.marcel_drugs_keys_main_v1 import runtime as B
from workflows.expansion.marcel_archive_bootstrap_v1 import archive as A
from workflows.expansion.tdc_zip44_header_probe_v2 import projection as H
from . import contract as C,projection as P
Q=C.Q


def frame(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid]


def checked_path(ref):
    path=Path(ref['path']);Q.need(path.is_absolute() and Q.ROOT/'artifacts' in path.parents and '..' not in path.parts
        and not any(p.is_symlink() for p in (path,*path.parents)),'LITERAL_EXISTING_MAIN_DATA_LOCATOR')
    info=path.lstat();Q.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and info.st_size==ref['bytes'],'ACTUAL_ORIGINAL_DATA_OWNER_SIZE')
    return path,info


def fixtures(out):
    from .test_v1 import Boundaries
    proof=P.grammar_proof();suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==4,'EXACT4_PURE_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),
        'before_journal_and_ZIP_bodies':True,'original_CSV_function_objects':proof,'new_identity_key_computations':0,'new_UFF_QM_calls':0}
    Q.write_new(out/'fixtures4.json',value);Q.need(r.wasSuccessful() and r.testsRun==4 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE4_PASS_BEFORE_BODY')
    return value


def select_two(ref,counts,states,source_writer,result_writer,check,progress):
    path,before=checked_path(ref);journal=P.Journal(counts,states);digest=hashlib.sha256();offset=0
    with path.open('rb') as f:
        Q.need(frame(os.fstat(f.fileno()))==frame(before),'SAME_JOURNAL_OPEN_FD')
        while True:
            check();raw=f.readline(C.LINE_CAP+1)
            if not raw:break
            digest.update(raw);journal.feed(raw,offset);offset+=len(raw)
            progress.update(phase='ORIGINAL_JOURNAL_PAIR_SCAN',journal_bytes=offset,journal_lines=journal.lines)
        targets=journal.finish();Q.need(offset==ref['bytes'] and digest.hexdigest()==ref['sha256']
            and frame(os.fstat(f.fileno()))==frame(before),'CURRENT_WHOLE_JOURNAL_SHA_STABLE_FSTAT')
        for key,item in sorted(targets.items()):
            for field,writer in (('original_source_event',source_writer),('original_result_event',result_writer)):
                check();locator=item[field];f.seek(locator['offset']);raw=f.read(locator['bytes'])
                Q.need(len(raw)==locator['bytes'] and hashlib.sha256(raw).hexdigest()==locator['sha256'],'SAME_FD_LITERAL_ORIGINAL_EVENT_SEEK_READBACK')
                value=json.loads(raw);Q.need(P.dump(value)==raw,'ORIGINAL_EVENT_BYTES_EXACT_BEFORE_FROZEN_WRITER')
                writer.write(value,dispatch=False)
        Q.need(frame(os.fstat(f.fileno()))==frame(before)==frame(path.lstat()),'JOURNAL_IDENTITY_UNCHANGED_AFTER_EXACT2_COPY')
    return targets,{'lines':journal.lines,'source_rows':sum(journal.source_counts.values()),'result_rows':sum(journal.result_counts.values()),
        'identity_state_counts':dict(journal.states),'current_whole_SHA_stable_fstat':True,'original_unknowns_retained':2}


def bind_zip(ref,entries,headers,parent,targets,check,progress):
    path,before=checked_path(ref);digest=hashlib.sha256();size=0;bindings={};counts={};members=[]
    expected={r['member_name']:r for r in parent['result']['members']}
    with path.open('rb') as f:
        Q.need(frame(os.fstat(f.fileno()))==frame(before),'SAME_ZIP_OPEN_FD')
        for block in iter(lambda:f.read(1<<20),b''):check();digest.update(block);size+=len(block)
        Q.need(size==ref['bytes'] and digest.hexdigest()==ref['sha256'] and frame(os.fstat(f.fileno()))==frame(before),'CURRENT_WHOLE_ZIP_SHA_STABLE_FSTAT')
        pre=A.preflight(f,size);f.seek(0)
        with zipfile.ZipFile(f,'r') as z:
            infos,_=A.directory(z,pre,5434789);H.checked_inventory(infos,entries)
            for info in infos:
                if info.is_dir():continue
                old=expected[info.filename];sha=hashlib.sha256();crc=0;n=0
                parser=P.IdentityCSV(info.filename,lambda row:P.bind(row,targets,bindings)) if info.filename in headers else None
                with z.open(info) as member:
                    while True:
                        check();block=member.read(1<<16)
                        if not block:break
                        n+=len(block);Q.need(n<=info.file_size,'BOUNDED_DECLARED_MEMBER_SIZE');sha.update(block);crc=zlib.crc32(block,crc)
                        if parser:parser.feed(block)
                summary=parser.finish() if parser else None
                Q.need(n==info.file_size==old['decoded_bytes'] and sha.hexdigest()==old['decoded_sha256']
                    and crc&0xffffffff==info.CRC==old['CRC32'],'EVERY_ORIGINAL_REGULAR_MEMBER_EOF_CRC_SHA')
                if parser:
                    Q.need(summary['record_counts']==headers[info.filename]['CSV']['record_counts'],'ALL44_ORIGINAL_PHYSICAL_RECORD_COUNTS')
                    counts[info.filename]=summary['record_counts']['physical_data_records']
                members.append({'member_name':info.filename,'decoded_bytes':n,'decoded_sha256':sha.hexdigest(),'CRC32':crc&0xffffffff,'EOF_CRC_complete':True})
                progress.update(phase='ORIGINAL_ZIP_BINDING',regular_members_completed=len(members),selected_original_rows_bound=len(bindings))
        Q.need(frame(os.fstat(f.fileno()))==frame(before)==frame(path.lstat()),'ZIP_UNCHANGED_AFTER_ALL_MEMBER_READS')
    Q.need(counts==parent['result']['member_result_counts'] and len(counts)==44 and sum(counts.values())==81809
        and set(bindings)==set(targets) and len(bindings)==2,'BOTH_ORIGINAL_UNKNOWNS_AND_ALL44_ROWS_BOUND_NO_REKEY')
    return bindings,{'current_whole_SHA_stable_fstat':True,'regular_members':len(members),'members':members,
        'physical_CSV_rows_replayed_without_new_keys':sum(counts.values()),'member_counts':counts,'selected_rows_bound':2}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan=Q.load(args.plan);parent,entries,headers,parents=C.inputs(plan)
    Q.need(plan['schema']=='TDC_UNRESOLVED2_DIAGNOSIS_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS
        and plan['output_cap_bytes']==C.CAP,'EXACT_DIAGNOSIS_PLAN_NO_ORIGINAL_STATE_CHANGE')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(args.plan),'--startup-proof',str(args.startup_proof)]
    proof=R.require_startup(args.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(args.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];authority=C.T.meta(req['queue_authority_reference']);allowed={'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']}
    Q.need(req['node'] in allowed and req['pilot'] is False and req['cpus']==16 and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and req['wall_seconds']==plan['wall_seconds'] and type(plan['wall_seconds']) is int and 600<=plan['wall_seconds']<=3600
        and plan['wall_seconds']%60==0 and req['estimated_peak_output_bytes']==req['stage_output_cap_bytes']==C.CAP
        and req['data_references']==plan['data_references'] and not req.get('deferred_authority_references')
        and proof['account_free_bytes']-C.CAP>=200000000000,'ACTUAL_CPU16_NO_MEMORY_ALLOWED_ANALYSIS_NODE_FRESH_ACCOUNT_RESERVE')
    review=C.T.meta(req['scope']['review']);Q.need(review['only_exact2_original_unknowns_ZIP_binding_authorized'] is True
        and review['global_decontamination_pool_training_release'] is False and req['scope']['mode']=='BOUNDED_METADATA_PREPARATION','EXPLICIT_ROOT_FINITE_READONLY_SCOPE')
    cost=C.T.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'COST_REPORT_CONTINUE_NO_QC_CHANGE')
    for path in [*(C.HERE/n for n in C.FILES),*C.OLD]:Q.need(Q.pin(path) in req['source_references'],'ALL_CURRENT_IMPORTED_AND_FROZEN_SOURCE_PINS')
    for name,module in list(sys.modules.items()):
        file=getattr(module,'__file__',None)
        if name.startswith('workflows.expansion') and file and Path(file).suffix=='.py':Q.need(Q.pin(file) in req['source_references'],'ACTUAL_IMPORTED_EXPANSION_SOURCE_PIN:'+name)
    Q.need(Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'ACTUAL_INTEGRATED_PRIMARY_FULL_ARGV')
    out=Path(plan['output_directory']);Q.need(out.is_absolute() and '..' not in out.parts and Q.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_JOB_OWN_OUTPUT_ONLY');out.mkdir(parents=True,mode=0o700)
    budget=B.Budget(plan,proof,out);gate=None;progress={};writers=[];started=time.monotonic()
    # No new worker dispatch. Keep the frozen 2MiB drain mode for128MiB,
    # explicitly honor its original latched memory/wall STOP before every read.
    def check():budget.check(dispatch=False);Q.need(budget.stop_new is None,budget.stop_new or 'ORIGINAL_RESOURCE_STOP_NO_FURTHER_READS')
    try:
        gate=fixtures(out);check()
        source_writer=B.Writer(out/'exact2_original_source_events.jsonl',budget);writers.append(source_writer)
        result_writer=B.Writer(out/'exact2_original_result_events.jsonl',budget);writers.append(result_writer)
        targets,journal=select_two(plan['data_references'][0],parent['result']['member_result_counts'],parent['result']['identity_state_counts'],source_writer,result_writer,check,progress)
        bindings,archive=bind_zip(plan['data_references'][1],entries,headers,parent,targets,check,progress)
        details=[]
        for key,item in sorted(targets.items()):
            row=dict(bindings[key],original_source_event=item['original_source_event'],original_result_event=item['original_result_event'],
                original_identity_error_count=len(item['original_result']['identity_errors']))
            details.append(row)
        data_refs=[w.reference() for w in writers]
        Q.write_new(out/'diagnosis_summary.json',{'schema':'TDC_EXACT2_ORIGINAL_UNKNOWN_READONLY_DIAGNOSIS_V1','status':'BOTH_ORIGINAL_UNKNOWN_ROWS_BYTE_BOUND_STATE_UNCHANGED',
            'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22','plan_reference':Q.pin(args.plan),
            'startup_proof_reference':Q.pin(args.startup_proof),'accepted_identity_receipt_reference':plan['accepted_identity_receipt_reference'],
            'accepted_identity_accounting_reference':plan['accepted_identity_accounting_reference'],'fixtures':gate,'journal':journal,'ZIP':archive,
            'selected_original_event_DATA_references':data_refs,'exact2_bindings':details,'original_stderr_reference':plan.get('original_stderr_reference'),
            'stderr_observations_are_not_row_or_cause_binding':True,'original2_UNKNOWN_unchanged':True,'new_identity_key_computations':0,
            'new_network_UFF_QM_calls':0,'production_once_opened_or_modified':False,'global_decontamination_pool_training_release':False,
            'observed_RSS_peak_bytes':budget.peak,'minimum_MemAvailable_bytes':budget.minimum,'elapsed_seconds':time.monotonic()-started,
            'runtime_statvfs_is_not_refreshed_account_quota':True,'actual_new_parent_cost':'PENDING_ROOT_TERMINAL_ACCOUNTING','cost_overrun_action':'REPORT_AND_CONTINUE'})
        return 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'TDC_EXACT2_READONLY_DIAGNOSIS_FAILURE_V1','error':type(exc).__name__+': '+str(exc),
            'traceback':traceback.format_exc(),'fixtures':gate,'actual_progress':progress,'completed_prefix_DATA_references':[w.reference() for w in writers],
            'original2_UNKNOWN_unchanged':True,'original_source_or_once_modified':False,'global_release':False,'actual_new_cost':'PENDING_ROOT_ACCOUNTING'})
        raise
    finally:
        for writer in writers:
            if not writer.stream.closed:writer.close()


if __name__=='__main__':raise SystemExit(main())
