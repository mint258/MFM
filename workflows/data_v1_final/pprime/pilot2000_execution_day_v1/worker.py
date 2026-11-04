"""Persistent original engine, original compute_pair, no replacement native callable."""
import hashlib,json,os,pathlib,sys,tempfile,threading,time,traceback
from multiprocessing.util import Finalize
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from workflows.data_v1_final.pprime.strict_numerics20_qa_v1.resources import Scratch
from . import contract as C,io as I,source_boundary
Q=C.Q;ENGINE=None;SESSION=None;STOP=None;SCRATCH=None;DEADLINE=None;OUT=None;PROTOCOL=None;FINALIZER=None;OBSERVER=None;WATCH=None;DONE=None
def close():
    global ENGINE
    value={'pid':os.getpid(),'job_id':SESSION['job_id'],'boot_id':SESSION['boot_id'],'engine_initialized':ENGINE is not None}
    if DONE is not None:DONE.set()
    if WATCH is not None:WATCH.join()
    if OBSERVER is not None:
        OBSERVER.observe();value['scratch_observation']=OBSERVER.report()
        if value['scratch_observation']['observation_errors']:value['close_error']='SCRATCH_OBSERVATION_UNKNOWN';STOP.set()
    try:value['engine_close']=ENGINE.close_worker() if ENGINE is not None else {'initialized':False};ENGINE=None
    except BaseException as exc:value['close_error']=repr(exc);STOP.set()
    value['scratch_preserved']=str(SCRATCH) if SCRATCH is not None and SCRATCH.exists() and any(SCRATCH.iterdir()) else None
    if SCRATCH is not None and SCRATCH.exists() and not any(SCRATCH.iterdir()):SCRATCH.rmdir()
    store=I.Store(OUT/'workers',8<<20);store.json(OUT/'workers'/('worker_%d_closed.json'%os.getpid()),value)
def initialize(session,event,output,source,protocol_reference,audit_reference,reproduction_sha,deadline):
    global ENGINE,SESSION,STOP,SCRATCH,DEADLINE,OUT,PROTOCOL,FINALIZER,OBSERVER,WATCH,DONE
    SESSION=session;STOP=event;OUT=pathlib.Path(output);DEADLINE=deadline;plan=I.continuation(session,check_sources=True)
    C.need(C.precision(plan,C.meta(session['execution_root_review_reference']))==protocol_reference,'SAME_ACTUAL_PRECISION_AUTHORITY_BEFORE_INITIALIZE')
    ENGINE,legacy,original,pilot=T.engine(source,C.meta);PROTOCOL=C.meta(protocol_reference)
    SCRATCH=pathlib.Path(tempfile.mkdtemp(prefix='pprime2000_'+session['job_id']+'_'+str(os.getpid())+'_',dir='/tmp'))
    OBSERVER=Scratch(SCRATCH,event);DONE=threading.Event();OBSERVER.observe()
    def watch():
        while not DONE.wait(1):OBSERVER.observe()
    WATCH=threading.Thread(target=watch,name='owned_pprime2000_scratch',daemon=False);WATCH.start()
    FINALIZER=Finalize(None,close,exitpriority=10)
    # Resource event is NOT passed to the unchanged native lifecycle. Admitted
    # calls finish naturally under the original900s and finite Parent deadline.
    ENGINE.initialize_worker(pilot['source_plan']['path'],protocol=protocol_reference['path'],node_scratch_root=str(SCRATCH),deadline=deadline,
      audit_membership=audit_reference['path'],reproduction_package=legacy['reproduction_package']['path'])
    original_protocol_with_owned_scratch(ENGINE.CONFIG,PROTOCOL,SCRATCH)
    T.invoke_identity(ENGINE,original)
    I.Store(OUT/'workers',8<<20).json(OUT/'workers'/('worker_%d_started.json'%os.getpid()),{'pid':os.getpid(),'pid_start_ticks':I.ticks(os.getpid()),
      'parent_pid':session['parent_pid'],'parent_ticks':session['parent_ticks'],'job_id':session['job_id'],'node':session['node'],'boot_id':session['boot_id'],'protocol_reference':protocol_reference})
class Sink:
    def __init__(self,delegate,folder):self.delegate=delegate;self.calls=[];self.folder=folder
    def __call__(self,raw):
        # Observed only after the original invoke/enrichment has returned; no
        # intent is upgraded to an actual returned call when the wrapper fails.
        row={'record_id':raw['record_id'],'calc_type':raw['calc_type'],'execution_id':raw['execution_id'],
          'status':raw.get('status'),'source_status':raw.get('source_status'),'raw_ref':None,
          'elapsed_seconds':raw.get('elapsed_seconds'),'native_return_observed_by_original_raw_sink':True}
        self.calls.append(row);ref=self.delegate(raw);row['raw_ref']=ref
        return ref

def original_protocol_with_owned_scratch(actual,protocol,scratch):
    C.need(actual.get('scratch_base')==str(scratch)
      and {k:v for k,v in actual.items() if k!='scratch_base'}=={k:v for k,v in protocol.items() if k!='scratch_base'}
      and actual['timeout_seconds']==900,'ONLY_ORIGINAL_INITIALIZER_OWNED_SCRATCH_NOT_NUMERICAL_PROTOCOL_CHANGE')

def one(pair,hashes,claim_reference,output,reproduction_sha):
    plan=I.continuation(SESSION);C.precision(plan,C.meta(SESSION['execution_root_review_reference']));C.need(not STOP.is_set(),'STOP_NEW_RECORD_BEFORE_SCIENCE')
    rid=pair['record_id'];claim=C.meta(claim_reference);key=C.record_once_key(pair,plan['original_protocol_reference'])
    C.need(claim['record_id']==rid and claim['pair_sha256']==hashlib.sha256(C.O.canonical(pair)).hexdigest() and claim['job_id']==SESSION['job_id']
      and claim['boot_id']==SESSION['boot_id'] and claim['record_once_key']==key and claim['prepared2000_reference']==plan['prepared2000_reference'],
      'REAL_PHYSICAL_RECORD_CLAIM_NOT_OUTPUT_OR_PRECISION_ESCAPE')
    C.need(claim_reference['path']==str(C.ledger(plan)/'physical_records_v1'/(key+'.json'))
      and hashes['record_id']==rid and hashes['original_pair_sha256']==claim['pair_sha256'],'EXACT_GLOBAL_CLAIM_AND_PREPARED_HASH_ROW')
    folder=pathlib.Path(output);folder.mkdir(mode=0o700);store=I.Store(folder,C.RESULT_CAP+(16<<20));sink=None;record=None;calls=[];error=None;worker_entered=False
    store.json(folder/'worker_start.json',{'record_id':rid,'pid':os.getpid(),'pid_start_ticks':I.ticks(os.getpid()),'claim_reference':claim_reference,
      'job_id':SESSION['job_id'],'boot_id':SESSION['boot_id'],'pair_sha256':claim['pair_sha256'],'native_return_claimed':False})
    try:
        C.need(DEADLINE-time.time()>=12*900+120,'WHOLE12_ORIGINAL900_PLUS_DRAIN_ADMISSION')
        source=dict(pair['source']);original=ENGINE.NATIVE.read_native(source);graph=ENGINE.source_bond_graph(original['_source_raw'],original)
        from workflows.data_v1_final.pprime.geometry import adapt_native
        native,geometry=adapt_native(original,dict(pair,bond_pairs=graph['bond_pairs_zero_based']))
        C.need(geometry['uff_geometry_sha256']==hashes['geometry_sha256'],'EXACT_PREPARED_PHYSICAL_GEOMETRY_SHA')
        row=dict(source,record_id=rid,conformer_id=int(pair['conformer']['sprime_conf_idx']))
        before='original_input_file_sha256' if plan['precision_mode']=='ORIGINAL_WP5' else 'candidate_input_file_sha256'
        expected={r['task']:r[before] for r in hashes['hashes']};C.need(set(expected)==set(C.O.TASKS),'ALL12_FROZEN_PRECALL_INPUT_HASHES')
        for task in ENGINE.CONFIG['tasks']:
            actual,_=ENGINE.rendered_input_hashes(task,native,row);C.need(actual==expected[task['name']],'EXACT_PREPARED_INPUT_BEFORE_ANY_NATIVE_CALL')
        sys.path[:0]=[str(Q.REPO/'workflows/data_v1_final/pprime')]
        originals=source_boundary.objects();compute_pair=originals['compute_pair'];RawSink=originals['RawSink']
        C.need(pathlib.Path(compute_pair.__code__.co_filename).absolute()==Q.REPO/'workflows/data_v1_final/pprime/engine_adapter.py','DIRECT_ORIGINAL_COMPUTE_PAIR_OBJECT')
        delegate=RawSink(folder/'raw_outputs.sqlite',ENGINE.OUTPUT_ARCHIVE,C.RAW_CAP);sink=Sink(delegate,folder)
        started=time.monotonic();worker_entered=True;record=compute_pair(ENGINE,pair,sink,{'job_id':int(SESSION['job_id']),'lane':int(claim['dispatch_slot']),
          'pprime_reproduction_manifest_sha256':reproduction_sha})
        record['lane']=int(claim['dispatch_slot']);calls=sink.calls
        C.need(len(record['tasks'])==len(calls)==12 and {d['task'] for d in record['tasks']}==set(C.O.TASKS),'ALL12_OBSERVED_RETURNED_TASKS')
        for detail in record['tasks']:C.need(detail['provenance']['input_file_sha256']==expected[detail['task']],'ACTUAL_RETURNED_INPUT_HASHES_EQUAL_PREPARED')
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()};STOP.set()
        if ENGINE is not None:ENGINE.PRESERVE_ARCHIVE_FAILURE=True
    finally:
        if sink is not None:
            calls=sink.calls
            try:sink.delegate.close()
            except BaseException as exc:error=error or {'raw_close_error':repr(exc)};STOP.set()
        raw_path=folder/'raw_outputs.sqlite';raw_ref=C.P.ResourceOrigin.I.data_pin(raw_path,[folder]) if raw_path.exists() else None
        result_ref=None
        if record is not None:
            import wp5_parquet_v2 as wire
            payload=C.O.staging_bytes(wire.native(record))+b'\n'
            if len(payload)<=C.RESULT_CAP:result_ref=store.write(folder/'record.DATA.json',payload)
            else:error=error or {'parsed_record_error':'FULL_ORIGINAL_RESULT_EXCEEDS128M_PRESERVED_RAW_SCRATCH_NO_TRUNCATION'};STOP.set()
        observed=store.json(folder/'call_observations.DATA.json',{'record_id':rid,'calls':calls,'compute_pair_entered':worker_entered,
          'exact_native_return_count':len(calls),'unobserved_native_attempts':'UNKNOWN' if error else 0,'error':error,
          'node_scratch_preserved_on_error':str(SCRATCH) if error else None,'original_status_not_backfilled':True})
        actual=I.quiescent(folder);valid=error is None and result_ref is not None and len(calls)==12
        C.need(actual+(2<<20)<=C.WORKER_CAP,'WHOLE_PRIVATE_RECORD_AND_TERMINAL_WITHIN_RESERVED1G')
        return store.json(folder/'finished.json',{'schema':'PPRIME2000_RECORD_TERMINAL_V1','record_id':rid,'claim_reference':claim_reference,
          'record_reference':result_ref,'raw_container':raw_ref,'call_observations_reference':observed,'technical_record_complete':valid,
          'original_all12_statuses_not_promoted':True,'actual_bytes_before_terminal':actual,'native_return_count':len(calls),'UNKNOWN_attempts_retained':bool(error),
            'record_worker_elapsed_seconds':time.monotonic()-started if worker_entered else None,
            'scientific_elapsed_seconds':record.get('elapsed_seconds') if record is not None else None,
            'failure':error,'scratch_preserved_on_error':str(SCRATCH) if error else None,'automatic_retry':False})
