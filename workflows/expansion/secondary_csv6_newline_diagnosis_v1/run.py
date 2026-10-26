"""Full retained-byte newline census; never a chemical identity acceptance."""
import argparse,gzip,hashlib,json,os,sys,threading,time,traceback,unittest,zlib
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_missing11_identity_format_probe_v1 import formats as F,test_profile as old_tests
from secondary_moleculenet_csv6_identity_v1 import journal as J
from . import contracts as C
from .analysis import ByteCensus
from .guard import require_startup
from .runtime import Budget,frame
STRUCTURAL=('literal_header','header_columns','duplicate_literal_header_names','smiles_column_indices','smiles_schema_state',
 'opaque_source_ID_columns','source_ID_semantics','selected_column_observations','record_counts','CSV_EOF_complete','CSV_decoded_bytes_traversed')


def run_fixtures(out,budget):
    from . import test_v1
    suite=unittest.TestSuite((unittest.defaultTestLoader.loadTestsFromTestCase(old_tests.InputFormatFixtures),
        unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.NewlineBoundaries)))
    Q.need(suite.countTestCases()==11,'EXACT_ORIGINAL8_PLUS_NEW3_BYTE_FIXTURES')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    value={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),
        'errors':len(result.errors),'skips':len(result.skipped),'expected_failures':len(result.expectedFailures),
        'unexpected_successes':len(result.unexpectedSuccesses),'unchanged_format_methods':8,'new_byte_census_methods':3,'before_any_payload':True}
    J.write_json(out/'fixtures11.json',value,budget)
    Q.need(result.wasSuccessful() and result.testsRun==11 and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses),'ALL11_PASS_BEFORE_SOURCE_BYTES')
    return value


def observe(source,budget):
    started=time.monotonic();cpu=time.thread_time();reference=source['payload_reference'];path=Q.literal(reference['path']);before=frame(path)
    Q.need(J.pin(path,budget)==reference,'ACTUAL_COMPLETE_PAYLOAD_SHA_REQUIRED')
    old=Q.load_ref(source['format_report_reference']);previous=old['current_payload_after_frame']
    Q.need(before==(previous['device'],previous['inode'],previous['size'],previous['mtime_ns'],previous['uid']),'SAME_RETAINED792_PAYLOAD_FRAME')
    census=ByteCensus();parser=F.CSVProjection(source['source_id']);digest=hashlib.sha256();decoded=0
    with path.open('rb') as raw:
        info=os.fstat(raw.fileno());Q.need(before==(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_uid),'OPENED_RETAINED_SOURCE_FRAME')
        stream=gzip.GzipFile(fileobj=raw,mode='rb') if source['gzip'] else raw
        try:
            while True:
                budget.check();data=stream.read(1<<20)
                if not data:break
                decoded+=len(data);Q.need(decoded<=source['expected_decoded_bytes'],'EXPECTED_COMPLETE_DECODED_BYTE_BOUND')
                digest.update(data);census.feed(data);parser.feed(data)
            summary=parser.finish();byte_summary=census.finish()
            Q.need(raw.tell()==reference['bytes'],'FULL_COMPRESSED_OR_PLAIN_SOURCE_EOF')
        finally:
            if stream is not raw:stream.close()
        info=os.fstat(raw.fileno());Q.need(before==(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_uid),'RETAINED_OPEN_SOURCE_UNCHANGED')
    Q.need(frame(path)==before and decoded==source['expected_decoded_bytes'] and digest.hexdigest()==source['expected_decoded_sha256'],'CURRENT_FULL_DECODED_SHA_BYTES_FSTAT')
    Q.need(all(summary[key]==source['expected_CSV_summary'][key] for key in STRUCTURAL),'ACTUAL_FROZEN792_ORIGINAL_CSV_SUMMARY_REQUIRED')
    lines=byte_summary['quote_agnostic_physical_line_counts'];records=summary['record_counts']['physical_data_records']
    return {'source_id':source['source_id'],'payload_reference':reference,'full_current_payload_SHA_verified':True,
        'source_frame':list(before),'decoded_SHA256':digest.hexdigest(),'decoded_bytes':decoded,'full_EOF_verified':True,
        'gzip_CRC_verified':source['gzip'],'gzip_CRC_not_applicable_to_plain_file':not source['gzip'],
        'byte_census':byte_summary,'original_CSV_structural_summary':{k:summary[k] for k in STRUCTURAL},'original792_summary_equal':True,
        'comparison':{'physical_line_count_including_header':lines['physical_lines_including_header'],
          'CSV_data_records_excluding_one_logical_header':records,'difference_lines_minus_CSV_records_minus_one_header':lines['physical_lines_including_header']-records-1,
          'below_header_CSV_records':summary['record_counts']['field_count_below_header'],
          'literal_empty_physical_lines_including_any_inside_quotes':lines['literal_empty_lines'],
          'source_cause':'OBSERVED_BYTE_COUNTS_ONLY_REQUIRES_REVIEW_NO_AUTOMATIC_CAUSAL_OR_CHEMICAL_INFERENCE'},
        'effective_molecule_count':'UNKNOWN_NOT_ESTIMATED_BY_NEWLINE_COUNTS','key_calls':0,'text_or_raw_context_values_persisted':False,
        'actual_thread_id':threading.get_native_id(),'thread_CPU_seconds':time.thread_time()-cpu,'wall_seconds':time.monotonic()-started}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--startup-proof',type=Path,required=True)
    args=parser.parse_args();plan,proof,authority=require_startup(args.plan,args.startup_proof)
    Q.need(sys.version.split()[0]=='3.11.14','EXACT_ACTUAL_ALPHA_PYTHON31114')
    Q.need(Path(F.__file__).absolute()==C.ROOT/'code/secondary_missing11_identity_format_probe_v1/formats.py','ACTUAL_FROZEN_ORIGINAL_FORMAT_MODULE')
    out=Q.literal(plan['output_directory']);out.mkdir(parents=True,mode=0o700,exist_ok=False);budget=Budget(plan,proof,out)
    started=time.monotonic();results={};failures=[]
    try:
        fixtures=run_fixtures(out,budget)
        with ThreadPoolExecutor(max_workers=6) as pool:
            pending={pool.submit(observe,source,budget):source['source_id'] for source in authority['sources']}
            for future in as_completed(pending):
                source_id=pending[future]
                try:value=future.result()
                except Exception as exc:
                    budget.mark('SOURCE_BYTE_CENSUS_UNKNOWN_STOP_NEW_CHUNKS_NATURAL_RETURN')
                    failure={'source_id':source_id,'status':'UNKNOWN_OR_PARTIAL_BYTES','type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
                    failures.append(failure);J.write_json(out/(source_id+'.failure.json'),failure,budget)
                else:results[source_id]=J.write_json(out/(source_id+'.newline.json'),value,budget)
        budget.sample();complete=set(results)==set(C.IDS) and not failures and budget.reason is None
        receipt={'schema':'SIX_CSV_NEWLINE_DIAGNOSIS_RECEIPT_V1','status':'SIX_SOURCE_FULL_BYTE_CENSUS_COMPLETE_REQUIRES_INTERPRETATION' if complete else 'SIX_SOURCE_BYTE_CENSUS_PARTIAL_UNKNOWNS_RETAINED',
            'job_id':str(proof['job_id']),'uid':1264,'endpoint':Q.ENDPOINT,'node':plan['node'],'allocated_cpus':16,
            'maximum_source_threads':6,'sixteen_busy_workers_claimed':False,'plan_reference':Q.ref(args.plan),'startup_proof_reference':Q.ref(args.startup_proof),
            'format_authority_reference':plan['format_authority_reference'],'format_accounting_reference':plan['format_accounting_reference'],
            'scope_parameters':plan['scope_parameters'],'source_references':plan['source_references'],'fixtures':fixtures,
            'source_results':[results[k] for k in C.IDS if k in results],'failure_reports':failures,
            'actual_software':{'python':sys.version,'executable':sys.executable,'zlib_compile':zlib.ZLIB_VERSION,'zlib_runtime':zlib.ZLIB_RUNTIME_VERSION},
            'runtime':budget.receipt(),'wall_seconds':time.monotonic()-started,'identity_key_calls':0,'new_UFF_QM_or_network_calls':0,
            'source_values_or_raw_context_persisted':False,'source_payloads_or_old_reports_modified':False,
            'effective_molecule_count':'UNKNOWN','new_keys_or_global_decontamination_pool_release':False,'signals_sent':False,
            'cost_decision_reference':plan['cost_decision_reference'],'cost_overrun_action':'REPORT_AND_CONTINUE','actual_terminal_parent_cost_pending_Root_accounting':True}
        J.write_json(out/'receipt.json',receipt,budget);print(json.dumps({'status':receipt['status'],'receipt_reference':J.pin(out/'receipt.json')}))
        return 0 if complete else 3
    except BaseException as exc:
        J.write_json(out/'failure.json',{'status':'BYTE_CENSUS_FAILED_PARTIALS_RETAINED','error':type(exc).__name__+': '+str(exc),
            'traceback':traceback.format_exc(),'source_results':results,'runtime':budget.receipt(),'global_release':False,'signals_sent':False})
        raise
    finally:budget.finish()

if __name__=='__main__':raise SystemExit(main())
