"""Original six CSV containers to physical identity observations; no global release."""
import argparse,gzip,hashlib,json,multiprocessing as mp,os,sys,time,traceback,unittest
from collections import Counter,deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_coconut_identity_norm_profile_v1 import run as frozen_B
from secondary_missing11_identity_format_probe_v1 import formats as original
from . import contracts as C,projection,journal
from .guard import require_startup
from .runtime import Budget,frame,owned_bytes
WORKER={}
STRUCTURAL=('literal_header','header_columns','duplicate_literal_header_names','smiles_column_indices','smiles_schema_state',
 'opaque_source_ID_columns','source_ID_semantics','selected_column_observations','record_counts','CSV_EOF_complete','CSV_decoded_bytes_traversed')


def initialize(plan,barrier,logs):
    global WORKER
    directory=Q.literal(logs);directory.mkdir(parents=True,exist_ok=True)
    fd=os.open(directory/('worker_%d.log'%os.getpid()),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.dup2(fd,1);os.dup2(fd,2);os.close(fd)
    functions,proof=frozen_B.load_kernel(plan);WORKER={'functions':functions,'proof':proof};barrier.wait(timeout=180)


def work(row):
    wall=time.monotonic();cpu=time.process_time();observation=projection.normalize(row,WORKER['functions'])
    return {'observation':observation,'worker_pid':os.getpid(),'worker_kernel_proof':WORKER['proof'],
        'worker_wall_seconds':time.monotonic()-wall,'worker_CPU_seconds':time.process_time()-cpu}


def tests(out,functions,budget):
    from . import test_v1
    test_v1.TEST_ROOT=out;frozen_B.KernelFixtures.functions=functions
    suite=unittest.TestSuite((unittest.defaultTestLoader.loadTestsFromTestCase(frozen_B.KernelFixtures),
        unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.CallbackBoundaries)))
    Q.need(suite.countTestCases()==7,'EXACT_ORIGINAL_B3_PLUS_NEW_CALLBACK4_FIXTURES')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    value={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),
        'errors':len(result.errors),'skips':len(result.skipped),'expected_failures':len(result.expectedFailures),
        'unexpected_successes':len(result.unexpectedSuccesses),'original_B_methods':3,'new_callback_methods':4,'before_any_payload_body':True}
    journal.write_json(out/'fixtures7.json',value,budget)
    Q.need(result.wasSuccessful() and result.testsRun==7 and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses),'ALL7_BOUNDARIES_PASS_BEFORE_PAYLOAD')
    return value


class Pipeline:
    def __init__(self,pool,writer,out,budget):
        self.pool,self.writer,self.out,self.budget=pool,writer,out,budget;self.pending=deque();self.dispatched=Counter();self.completed=Counter()
        self.states=Counter();self.workers=Counter();self.worker_proofs={};self.wall=Counter();self.cpu=Counter();self.errors=[];self.error_count=0;self.last=None
    def dispatch(self,row):
        self.budget.check();identity=(C.IDS.index(row['source_id']),row['source_row_ordinal'])
        Q.need(self.last is None or identity>self.last,'STRICT_SOURCE_ORDER_AND_UNIQUE_PHYSICAL_ORDINALS');self.last=identity
        self.writer.dispatch(row);self.dispatched[row['source_id']]+=1
        try:future=self.pool.submit(work,row)
        except Exception as exc:
            self.save(row,None,exc);raise
        self.pending.append((row,future))
        if len(self.pending)>=32:self.collect()
    def save(self,row,value,error=None):
        if error is not None:
            value={'observation':{'source':row,'physical_identity':row['source_id']+':'+str(row['source_row_ordinal']),
                'SMILES_derived_full_keys':[],'WP5_keys':[],'key_state':'TECHNICAL_EXECUTION_UNKNOWN','missing_full_key':True,
                'identity_errors':[{'type':type(error).__name__,'message':str(error),'traceback':''.join(traceback.format_exception(type(error),error,error.__traceback__))}],'unknown_is_chemical_exclusion':False},
                'worker_pid':None,'worker_wall_seconds':None,'worker_CPU_seconds':None}
        Q.need(value['observation']['source']==row,'RETURNED_COMPLETE_PHYSICAL_SOURCE_ROW_UNCHANGED')
        pid=value['worker_pid'];proof=value.pop('worker_kernel_proof',None)
        if pid is not None and str(pid) not in self.worker_proofs:
            Q.need(proof is not None,'ACTUAL_FIRST_WORKER_KERNEL_PROOF_REQUIRED')
            self.worker_proofs[str(pid)]=journal.write_json(self.out/('worker_%d.kernel.json'%pid),proof,self.budget)
        value['worker_kernel_proof_reference']=self.worker_proofs.get(str(pid))
        self.writer.complete(value)  # Full row and result are fsynced BEFORE these counters or any view flush.
        self.completed[row['source_id']]+=1;self.states[value['observation']['key_state']]+=1
        if pid is not None:self.workers[str(pid)]+=1
        if value['worker_wall_seconds'] is not None:self.wall[row['source_id']]+=value['worker_wall_seconds']
        if value['worker_CPU_seconds'] is not None:self.cpu[row['source_id']]+=value['worker_CPU_seconds']
        if error is not None:
            self.error_count+=1
            if len(self.errors)<64:self.errors.append({'source_id':row['source_id'],'source_row_ordinal':row['source_row_ordinal'],
                'type':type(error).__name__,'message_prefix_1024_chars':str(error)[:1024],'full_message_preserved_in_row_journal':True})
            self.budget.mark('TECHNICAL_EXECUTION_ERROR_STOP_NEW_DISPATCH_NATURAL_DRAIN')
    def collect(self):
        row,future=self.pending.popleft()
        try:value=future.result()
        except Exception as exc:self.save(row,None,exc)
        else:self.save(row,value)
    def drain(self):
        while self.pending:self.collect()
    def receipt(self):return {'dispatched_rows_by_source':dict(self.dispatched),'observed_rows_by_source':dict(self.completed),
        'key_states_are_observations_not_exclusions':dict(self.states),'actual_nonempty_workers':dict(self.workers),
        'worker_kernel_proof_references':self.worker_proofs,'sum_worker_wall_not_parent_allocation':dict(self.wall),
        'sum_worker_CPU_seconds':dict(self.cpu),'technical_execution_error_count':self.error_count,'first64_technical_execution_error_examples':self.errors,
        'complete_error_messages_in_durable_row_journal':True,'maximum_pending':32}


def inspect_source(source,wanted,pipeline,out,budget):
    began=time.monotonic();cpu=time.process_time();reference=source['payload_reference'];path=Q.literal(reference['path'])
    before=frame(path);Q.need(journal.pin(path,budget)==reference,'CURRENT_COMPLETE_ORIGINAL_PAYLOAD_SHA')
    old=Q.load_ref(source['format_report_reference']);prior=old['current_payload_after_frame']
    Q.need(before==(prior['device'],prior['inode'],prior['size'],prior['mtime_ns'],prior['uid']),'ACTUAL792_SOURCE_FRAME_UNCHANGED')
    selected=0
    def emit(row):
        nonlocal selected
        if wanted is None or row['source_row_ordinal']-1 in wanted:
            row['payload_reference']=reference;pipeline.dispatch(row);selected+=1
    parser=projection.CallbackCSV(source['source_id'],emit);digest=hashlib.sha256();decoded=0
    with path.open('rb') as raw:
        s=os.fstat(raw.fileno());Q.need(before==(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_uid),'OPENED_ORIGINAL_PAYLOAD_FRAME')
        stream=gzip.GzipFile(fileobj=raw,mode='rb') if source['gzip'] else raw
        try:
            while True:
                budget.check();piece=stream.read(1<<20)
                if not piece:break
                decoded+=len(piece);Q.need(decoded<=source['expected_decoded_bytes'],'ORIGINAL_DECODED_BYTES_EXCEEDED_NO_ROW_EXCLUSION')
                digest.update(piece);parser.feed(piece)
            summary=parser.finish();Q.need(raw.tell()==reference['bytes'],'FULL_COMPRESSED_OR_PLAIN_FILE_EOF')
        finally:
            if stream is not raw:stream.close()
        s=os.fstat(raw.fileno());Q.need(before==(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_uid),'SOURCE_FRAME_DURING_COMPLETE_READ')
    Q.need(frame(path)==before and decoded==source['expected_decoded_bytes'] and digest.hexdigest()==source['expected_decoded_sha256'],'CURRENT_FULL_DECODED_SHA_BYTES_AND_FRAME')
    Q.need(all(summary[key]==source['expected_CSV_summary'][key] for key in STRUCTURAL),'EXACT792_ORIGINAL_HEADER_COUNTS_FIELD_STATS_AND_EOF')
    expected=C.COUNTS[source['source_id']] if wanted is None else len(wanted)
    Q.need(selected==expected,'COMPLETE_SELECTED_OR_FULL_PHYSICAL_ORDINALS')
    report={'source_id':source['source_id'],'reference':reference,'current_frame':list(before),'current_complete_SHA_reverified':True,
        'current_decoded_sha256':digest.hexdigest(),'current_decoded_bytes':decoded,'current_EOF_verified':True,
        'current_gzip_CRC_verified':source['gzip'],'not_gzip_CRC_not_applicable':not source['gzip'],
        'original792_structural_metadata_equal':True,'structural_summary':{k:summary[k] for k in STRUCTURAL},
        'header_raw_record_evidence':parser.header_record,'rows_selected_for_identity':selected,
        'source_reader_parent_CPU_seconds':time.process_time()-cpu,'source_read_dispatch_wall_seconds':time.monotonic()-began,
        'only_identity_values_decoded_and_persisted':True,'assay_values_decoded_or_persisted':False}
    return journal.write_json(out/(source['source_id']+'.source.json'),report,budget),before


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--startup-proof',type=Path,required=True)
    args=parser.parse_args();plan,proof,authority=require_startup(args.plan,args.startup_proof)
    out=Q.literal(plan['output_directory']);out.mkdir(parents=True,mode=0o700,exist_ok=False)
    began=time.monotonic();cpu=time.process_time();budget=Budget(plan,proof,out);writer=None;pipeline=None;source_reports=[];frames=[]
    try:
        environment=frozen_B.observe_environment();environment['called_before_six_CSV_payload_reads']=True;actual=environment['actual_versions']
        Q.need(actual=={'python':'3.11.14','numpy':'2.2.6','RDKit':'2025.09.5','pyarrow':'17.0.0'},'ACTUAL_ALPHA_IDENTITY_ENVIRONMENT')
        journal.write_json(out/'actual_environment.json',environment,budget)
        functions,kernel=frozen_B.load_kernel(plan)
        Q.need(Path(original.__file__).absolute()==C.ROOT/'code/secondary_missing11_identity_format_probe_v1/formats.py'
            and projection.CallbackCSV.__mro__[1] is original.CSVProjection,'ACTUAL_UNMODIFIED_FORMAT_BASE_CLASS')
        kernel['parser_seam']={'original_feed':{'filename':original.CSVProjection.feed.__code__.co_filename,'first_line':original.CSVProjection.feed.__code__.co_firstlineno},
            'new_grammar_defined':False,'new_callback_hooks_reviewed_source':Q.ref(C.HERE/'projection.py'),'original_format_bytes_modified':False,
            'raw_byte_boundary_proof':'CRLF_LOOKAHEAD_DELAY_AND_COMPLETE_OFFSET_CONSERVATION_FIXTURES'}
        journal.write_json(out/'kernel_proof.json',kernel,budget);fixtures=tests(out,functions,budget)
        mode=plan['mode'];selection={s['source_id']:frozen_B.selected_ordinals(s['source_id'],C.COUNTS[s['source_id']]) if mode=='profile' else None for s in authority['sources']}
        if mode=='profile':journal.write_json(out/'selected_physical_ordinals.json',{'zero_based':selection,'seed':20261026,
            'sampler_python':'3.11.14','not_filtered_before_sampling':True},budget)
        context=mp.get_context('spawn');writer=journal.Writer(out,budget)
        with ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=initialize,
                initargs=(plan,context.Barrier(16),str(out/'worker_logs'))) as pool:
            pipeline=Pipeline(pool,writer,out,budget)
            try:
                for source in authority['sources']:
                    wanted=selection[source['source_id']];reference,before=inspect_source(source,None if wanted is None else set(wanted),pipeline,out,budget)
                    source_reports.append(reference);frames.append((source['payload_reference']['path'],before))
                pipeline.drain()
            finally:pipeline.drain()
        outputs=writer.close();writer=None
        for path,before in frames:Q.need(frame(path)==before,'PAYLOAD_CHANGED_DURING_OTHER_SOURCE_WORK')
        import pyarrow.parquet as pq
        n=sum(pipeline.completed.values());expected=C.PROFILE_N if mode=='profile' else C.N
        Q.need(pq.ParquetFile(outputs['Parquet']['path']).metadata.num_rows==n,'DURABLE_JOURNAL_AND_PARQUET_ROW_CONSERVATION')
        expected_by_source={key:min(value,10000) if mode=='profile' else value for key,value in C.COUNTS.items()}
        complete=n==expected and dict(pipeline.completed)==expected_by_source and dict(pipeline.dispatched)==expected_by_source and len(source_reports)==6
        budget.sample();complete=complete and len(pipeline.workers)==16 and not pipeline.errors and budget.reason is None
        status=('SIX_CSV_PROFILE_PHYSICAL_IDENTITY_OBSERVATIONS_COMPLETE' if mode=='profile' else 'SIX_CSV_FULL_PHYSICAL_IDENTITY_OBSERVATIONS_COMPLETE') if complete else 'SIX_CSV_PARTIAL_OR_TECHNICAL_ERROR_OBSERVATIONS_RETAINED'
        receipt={'schema':'MOLECULENET_CSV6_IDENTITY_RECEIPT_V1','status':status,'mode':mode,'job_id':str(proof['job_id']),
            'endpoint':Q.ENDPOINT,'uid':1264,'node':plan['node'],'allocated_cpus':16,'plan_reference':Q.ref(args.plan),'startup_proof_reference':Q.ref(args.startup_proof),
            'format_authority_reference':plan['format_authority_reference'],'format_accounting_reference':plan['format_accounting_reference'],
            'source_references':plan['source_references'],'scope_parameters':plan['scope_parameters'],'role':'ALLSPLITS',
            'fixtures':fixtures,'kernel_proof_reference':journal.pin(out/'kernel_proof.json'),'observed_rows':n,'source_reports':source_reports,
            'full_payload_sha_crc_eof_reverified':len(source_reports)==6,'pipeline':pipeline.receipt(),'outputs':outputs,
            'actual_environment':environment,'runtime':budget.receipt(),'wall_seconds':time.monotonic()-began,'parent_CPU_seconds':time.process_time()-cpu,
            'actual_output_bytes_before_receipt':owned_bytes(out),'all_processed_blank_invalid_duplicate_zero_ID_noKey_rows_retained':True,'all_source_physical_rows_normalized':complete and mode=='full',
            'global_identity_or_decontamination_coverage_accepted':False,'global_pool_UFF_QM_training_export_release':False,
            'QM7b_native_SDF_MOL2_graph_identity':'UNKNOWN_UNCHANGED','signals_sent':False,'new_network_UFF_QM_calls':0,
            'cost_decision_reference':plan['cost_decision_reference'],'cost_overrun_action':'REPORT_AND_CONTINUE','actual_terminal_parent_cost_pending_Root_accounting':True}
        journal.write_json(out/'receipt.json',receipt,budget);print(json.dumps({'status':status,'receipt_reference':journal.pin(out/'receipt.json')}))
        return 0 if complete else 3
    except BaseException as exc:
        if pipeline:pipeline.drain()
        if writer:writer.close();writer=None
        journal.write_json(out/'failure.json',{'schema':'SIX_CSV_IDENTITY_PARTIAL_FAILURE_V1','status':'ALL_PREFIX_EVIDENCE_RETAINED_NOT_COMPLETE',
            'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(),'pipeline':pipeline.receipt() if pipeline else None,
            'source_reports':source_reports,'runtime':budget.receipt(),'global_release':False,'signals_sent':False,
            'actual_terminal_parent_cost_pending_Root_accounting':True})
        raise
    finally:
        if writer:writer.close()
        budget.finish()

if __name__=='__main__':raise SystemExit(main())
