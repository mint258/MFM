"""New CPU13 resource entry; all old readonly scientific functions are direct."""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures as cf,datetime,hashlib,inspect,io,json,multiprocessing as mp,os,socket,time,unittest
from pathlib import Path
from . import contract as A
from workflows.data_v1_final.labels.full_timeout_inventory_v1 import contract as C,io as I,inventory as V,run as O
old_parent=O.old_parent

def guard(a,plan):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    C.need(plan['schema']==A.SCHEMA and plan['scope_key']==A.KEY and plan['scope_parameters']==dict(A.PARAMETERS,
      other_storage_scope_unwritten_cap_upper_bound_bytes=plan['other_storage_scope_unwritten_cap_upper_bound_bytes']), 'FIXED_READONLY_PLAN')
    proof=require_startup(a.startup_proof,expected_kind='analysis',expected_source=__file__,expected_scope_key=A.KEY,
      expected_scope_parameters=plan['scope_parameters'],required_references=[I.pin(a.plan),*plan['source_references']])
    request=proof['request'];sources={r['path']:r for r in request['source_references']}
    A.validate_current_request(request)
    C.need(proof['uid']==1278 and proof['node']=='compute-0-13','CURRENT_CPU13_MAIN_IDENTITY_NOT_OLD17')
    for name in A.FILES:C.need(I.pin(A.HERE/name) in request['source_references'],'EXACT_NEW_RESOURCE_ADAPTER_SOURCE')
    C.need(request['pilot'] is False and request['cpus']==16 and request['node']=='compute-0-13'
      and request['wall_seconds']==1800 and request['estimated_peak_output_bytes']==2<<30
      and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','CPU13_READONLY_16_NOMEM_1800_2GIB')
    C.need(request['execution_argv']==[C.PY,'-B','-m',A.MODULE,'--plan',str(Path(a.plan).absolute()),
      '--startup-proof',str(Path(a.startup_proof).absolute()),'--output',str(Path(a.output).absolute())], 'EXACT_ALL_PRIMARY_OPTIONS')
    for ref in plan['source_references']:C.need(sources.get(ref['path'])==ref,'EXACT_AUTHORIZED_READONLY_SOURCE');I.require(ref)
    C.need(request['queue_authority_reference']==plan['resource_authority_reference'],'EXACT_NEW_RESOURCE_AUTHORITY')
    C.need(request.get('deferred_authority_references',[])==[plan['closed_locator_inventory_reference']]
      and request.get('data_references',[])==plan['known_data_references'],'EXACT_TRANSITIVE_CLOSED_OUTPUT_AUTHORITY')
    C.need(proof['account_free_bytes']>=200000000000+(2<<30)+plan['other_storage_scope_unwritten_cap_upper_bound_bytes'],
      'FRESH_ACCOUNT_QUOTA_ALL_OTHER_FUTURE_CAPS_AND_200GB')
    output=Path(a.output).absolute();C.need(output==Path(plan['output']) and C.RUN/'artifacts/labels/source_status_v1' in output.parents
      and output!=C.OLD and C.OLD not in output.parents and not any(p.is_symlink() for p in (output,*output.parents)), 'NEW_INDEPENDENT_AUDIT_OUTPUT')
    # Real scontrol start time, interpreted in this node's local timezone; no wall ceiling forecast.
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.slurm_format import fields
    start=fields(proof['job_metadata']).get('StartTime');C.need(start is not None,'REAL_ALLOCATION_START_REQUIRED')
    epoch=datetime.datetime.fromisoformat(start).timestamp();C.need(0<=time.time()-epoch<1500,'ALLOCATION_ELAPSED_FINITE_START')
    return proof,epoch+1500


def source_inverse():
    old=inspect.getsource(O.main);new=inspect.getsource(main)
    new=new.replace("'scope_key':A.KEY,'stage_cap_including_observer_bytes'","'scope_key':C.KEY,'stage_cap_including_observer_bytes'")
    block="    summary['resource_adapter']={'schema':A.ADAPTER,'current_node':proof['node'],'historical_node':'compute-0-17',\n      'historical_job_id':'4521904','old_parent_state':'TIMEOUT','current_primary_reference':I.pin(__file__),'old_producer_source_reference':I.pin(O.__file__)}\n"
    new=new.replace(block,'')
    C.need(new==old and ast.dump(ast.parse(new),include_attributes=False)==ast.dump(ast.parse(old),include_attributes=False),
      'EXACT_RESOURCE_PROVENANCE_ONLY_COORDINATOR_INVERSE')
    C.need(C is O.C and I is O.I and V is O.V and old_parent is O.old_parent and A.parent_chain is C.parent_chain,
      'UNCHANGED_HISTORICAL17_PARENT_AND_READONLY_SCIENCE_OBJECTS')
    return {'status':'EXACT_CPU13_RESOURCE_ONLY_BYTES_AST_INVERSE','scientific_function_copies':False,
      'old_parent17_validator_direct':True,'old_reader_and_inventory_objects_direct':True}


def fixture_gate(root):
    original=O.fixture_gate(root)
    from .test_resource import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);C.need(suite.countTestCases()==3,'EXACT_THREE_RESOURCE_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    good=r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses)
    ref=I.write_new(root/'resource_adapter_fixtures.json',{'status':'PASS' if good else 'FAIL_NO_DATA','tests_run':r.testsRun,
      'transcript':stream.getvalue(),'source_reference':I.pin(A.HERE/'test_resource.py'),'input_DATA_opened':False})
    C.need(good,'NEW_RESOURCE3_BEFORE_OLD_BODY');return {'original_three':original,'resource_three':ref,'source_inverse':source_inverse()}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('plan','startup-proof','output'):p.add_argument('--'+key,required=True)
    a=p.parse_args();plan=I.load(a.plan);proof,deadline=guard(a,plan);root=Path(a.output).absolute()
    root.mkdir(parents=True,exist_ok=False,mode=0o700)
    summary={'schema':'LABELS_FULL_TIMEOUT_READONLY_INVENTORY_RECEIPT_V1','status':C.STATUS,'job_id':str(proof['job_id']),
      'node':socket.gethostname().split('.')[0],'uid':os.getuid(),'boot_id':proof['boot_id'],'plan_reference':I.pin(a.plan),
      'startup_proof_request_reference':proof['request_reference'],'original_parent_c0':False,'old_book_written':False,
      'old_cache_files_modified':False,'all_old_member_frames_unchanged':None,'dispatch_lease_released':False,'original_batch_accepted':False,'new_UFF_QM_calls':0,
      'full_population_completed':False,'candidate_masks_frozen':False,'normalization_completed':False,'automatic_retry':False,
      'inventory_verification_complete':False,'unverified_is_not_proven_unstarted':True,'errors':[]}
    summary['resource_adapter']={'schema':A.ADAPTER,'current_node':proof['node'],'historical_node':'compute-0-17',
      'historical_job_id':'4521904','old_parent_state':'TIMEOUT','current_primary_reference':I.pin(__file__),'old_producer_source_reference':I.pin(O.__file__)}
    detail=root/'evidence.jsonl';details_bytes=0;result_count=0;results=[];stats=collections.defaultdict(collections.Counter)
    book=None;windows=[];locators=None;cursor=[];counts=collections.Counter();worker_checkpoints=[]
    def emit(value):
        nonlocal details_bytes,result_count
        raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
        C.need(len(raw)<=2<<20 and details_bytes+len(raw)<=128<<20,'BOUNDED_AUDIT_DETAILS_WITH_SUMMARY_AND_OBSERVER_RESERVE')
        with detail.open('ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
        details_bytes+=len(raw);result_count+=1
    try:
        summary['fixture_gate']=fixture_gate(root)
        binding={'memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20,
          'resource_evidence_output':str(root)+'_resource_observation','scope_key':A.KEY,'stage_cap_including_observer_bytes':2<<30}
        from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import start_observer
        start_observer(proof,binding)
        summary['original_parent'],cfg=old_parent(plan)
        from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import verify_cache_row
        from workflows.data_v1_final.labels.full_projection_v1.coverage import sidecar_row
        from workflows.data_v1_final.labels.streaming_v1.compact import unpack
        from workflows.data_v1_final.labels.bounded_projection_v1.parts import slices
        summary['direct_frozen_object_bindings']=[{'module':f.__module__,'function':f.__name__} for f in (verify_cache_row,sidecar_row,unpack,slices)]
        summary['scientific_function_copies_or_monkeypatches']=False
        locators=I.load(I.require(plan['closed_locator_inventory_reference']))
        C.need(locators['original_root']==str(C.OLD) and locators['book_path']==str(C.BOOK)
          and locators['pending_cpu_whole_SHA'] is True,'EXACT_TRANSITIVE_POST_TERMINAL_LOCATORS')
        observations=I.load(I.require(plan['root_post_terminal_lstat_reference']))
        expected={r['path']:r for r in observations['lstat_frames']}
        I.original_match(I.frame(C.OLD.lstat()),expected[str(C.OLD)])
        I.original_match(I.frame(C.BOOK.lstat()),expected[str(C.BOOK)])
        I.original_match(I.frame((C.OLD/'state.sqlite').lstat()),expected[str(C.OLD/'state.sqlite')])
        book=V.audit_books(plan,cfg,locators,deadline)
        I.write_new(root/'book_inventory.json',{k:v for k,v in book.items() if k not in ('expected','windows')},cap=32<<20)
        emit({'kind':'old_readonly_database_observations','actual_range_plan':book['actual_range_plan'],
          'book':book['book'],'state':book['state'],'metadata_conservation':book['metadata_conservation']})
        windows=sorted(book['windows'],key=lambda w:(w['range_id'],w['lo']));byrange={r['range_id']:r for r in book['expected']}
        jobs=[];committed=set();owners={};all_receipts_indexed=True
        for w in windows:
            name=V.relative(w['receipt']['path']);committed.add(name)
            try:
                body,_=I.read_json(w['receipt']['path'],locators['files'][name],deadline,256<<10,known=w['receipt'])
                for part in body['parts']:
                    part_name=V.relative(part['reference']['path'])
                    C.need(part_name not in owners,'NO_PART_SHARED_BETWEEN_COMMITTED_WINDOWS')
                    owners[part_name]=(w['range_id'],w['lo']);committed.add(part_name)
                ts=[t for t in book['tickets'] if t['status']=='CLOSED' and t['range_id']==w['range_id'] and t['lo']==w['lo']]
                C.need(len(ts)==1,'ONE_WINDOW_TICKET');jobs.append({'window':w,'ticket':ts[0],'range':byrange[w['range_id']]})
            except Exception as exc:
                all_receipts_indexed=False
                r={'kind':'committed_window','window':w,'status':'UNKNOWN_OR_PENDING_WINDOW_RECEIPT',
                  'error':type(exc).__name__+':'+str(exc)[:350],'verified_rows':0,'parts':[],'field_stats':{}}
                results.append(r);emit(r)
        registry=I.load(I.require(cfg['science']['sources']['registry']))['fields']
        enabled={f['field_key']:i for i,f in enumerate(sorted((f for f in registry if f['status']=='enabled'),key=lambda f:f['field_key']))}
        C.need(len(enabled)==146 and len(registry)==264,'UNCHANGED264_146_FIELDS')
        extra=[]
        for name in sorted(locators['files']):
            if name in committed or name in ('state.sqlite','actual_range_plan.json'):continue
            classification=C.file_class(name,committed)
            if not all_receipts_indexed and name.startswith('parts/') and not name.endswith('.partial'):
                classification='UNREFERENCED_WITH_INCOMPLETE_RECEIPT_INDEX_UNKNOWN_NOT_PROVEN_ORPHAN'
            extra.append({'relative':name,'classification':classification})
        counts=collections.Counter(r['status'] for r in results);dispatched=0
        def execute(pool,items,function):
            nonlocal dispatched
            iterator=iter(items);pending={};ended=False
            while pending or not ended:
                try:I.checkpoint(deadline)
                except I.SoftStop:ended=True
                while not ended and len(pending)<16:
                    try:item=next(iterator)
                    except StopIteration:ended=True;break
                    pending[pool.submit(function,item)]=item;dispatched+=1
                if not pending:break
                done,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    item=pending.pop(future)
                    try:r=future.result()
                    except Exception as exc:
                        r={'kind':'worker_exception','item':item,'status':'UNKNOWN_WORKER_EXCEPTION','error':type(exc).__name__+':'+str(exc)[:350]}
                    counts[r['status']]+=1;emit(r)
                    if 'original_worker_checkpoint' in r:worker_checkpoints.append({'relative':r['relative'],**r['original_worker_checkpoint']})
                    if 'window' in r:results.append(r)
                    if r['status']=='VERIFIED_COMMITTED_WINDOW':
                        for key,value in r['field_stats'].items():stats[key].update(value)
            # No kill, signal, cancellation or rerun. Unsubmitted items remain explicit.
            for item in iterator:
                r={'kind':'not_dispatched','status':'PENDING_NOT_VERIFIED_NO_AUTOMATIC_RETRY','item':item};counts[r['status']]+=1;emit(r)
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=V.initialize,initargs=(locators,deadline,enabled,plan["known_data_references"])) as pool:
            execute(pool,jobs,V.verify_window);execute(pool,extra,V.hash_uncommitted)
        cursor=[]
        for e in book['expected']:
            committed_cursor=next(r['cursor'] for r in book['ranges'] if r['range_id']==e['range_id']);pos=e['physical_row_lo']
            for w in [w for w in windows if w['range_id']==e['range_id']]:
                r=next((r for r in results if r.get('window')==w),None)
                if r is None or r['status']!='VERIFIED_COMMITTED_WINDOW':break
                C.need(w['lo']==pos,'VERIFIED_PREFIX_NO_GAP');pos=w['hi']
            cursor.append({'range_id':e['range_id'],'file_id':e['file_id'],'original_lo':e['physical_row_lo'],
              'old_committed_cursor':committed_cursor,'cpu_verified_contiguous_prefix_cursor':pos,'tile_stop':e['physical_row_hi']})
        # Whole old DBs must remain byte-identical over the entire audit, not only the read transaction.
        for path,fr,observed in ((C.BOOK,locators['book_frame'],book['book']),
          (C.OLD/'state.sqlite',locators['files']['state.sqlite'],book['state'])):
            I.check_sidecars(path)
            with I.reader(path,fr,deadline) as (f,_):n,sha=I.hash_stream(f,deadline)
            I.check_sidecars(path)
            C.need((n,sha)==(observed['reference']['bytes'],observed['reference']['sha256']),'OLD_BOOK_CHANGED_OVER_AUDIT')
        final_listing=I.locator_inventory(C.OLD,C.BOOK)
        C.need(set(final_listing['files'])==set(locators['files']) and set(final_listing['directories'])==set(locators['directories']),
          'OLD_MEMBER_SET_CHANGED_OVER_AUDIT')
        for group in ('files','directories'):
            for name,current in final_listing[group].items():
                C.need(all(current[k]==locators[group][name][k] for k in C.FRAME if k!='device'),'OLD_MEMBER_PORTABLE_FRAME_CHANGED_OVER_AUDIT')
        C.need(all(final_listing['book_frame'][k]==locators['book_frame'][k] for k in C.FRAME if k!='device'),
          'OLD_BOOK_PORTABLE_FRAME_CHANGED_OVER_AUDIT')
        holds=sorted(fid for fid,s in stats.items() if s['newly_masked_fields']/11231854>.01
          or s['new_payload_structural_invalid_records']/11231854>.01
          or s['records'] and (s['newly_masked_fields']/s['records']>.01 or s['new_payload_structural_invalid_records']/s['records']>.01))
        verified=sum(r.get('status')=='VERIFIED_COMMITTED_WINDOW' for r in results)
        summary.update(old_committed_windows=len(windows),cpu_verified_committed_windows=verified,
          old_unpublished_tickets=book['metadata_conservation']['unpublished_tickets'],source_cursors=cursor,
          result_status_counts=dict(counts),field_stats_verified_windows={k:dict(v) for k,v in stats.items()},quality_hold_fields_verified_windows=holds,
          quality_scope='VERIFIED_WINDOWS_ONLY_NOT_FULL_POPULATION_PASS',all_old_member_frames_unchanged=True,
          inventory_verification_complete=verified==len(windows) and not any(k.startswith(('UNKNOWN','PENDING')) for k in counts),
          old_input_logical_bytes_from_lstat=sum(f['bytes'] for f in locators['files'].values())+locators['book_frame']['bytes'],
          original_closed_worker_metadata_count=observations['worker_metadata_count'],missing_worker_metadata_not_zero_commits=True)
    except I.SoftStop as exc:summary['soft_stop_reason']=str(exc)
    except Exception as exc:summary['errors'].append(type(exc).__name__+':'+str(exc)[:500])
    finally:
        summary['cpu_verified_committed_windows']=sum(r.get('status')=='VERIFIED_COMMITTED_WINDOW' for r in results)
        summary['old_committed_windows']=len(windows) if book is not None else None
        summary['source_cursors']=cursor
        summary['result_status_counts']=dict(counts)
        summary['field_stats_verified_windows']={k:dict(v) for k,v in stats.items()}
        summary['quality_scope']='VERIFIED_WINDOWS_ONLY_NOT_FULL_POPULATION_PASS'
        summary['quality_hold_fields_verified_windows']=sorted(fid for fid,s in stats.items() if s['newly_masked_fields']/11231854>.01
          or s['new_payload_structural_invalid_records']/11231854>.01
          or s['records'] and (s['newly_masked_fields']/s['records']>.01 or s['new_payload_structural_invalid_records']/s['records']>.01))
        if book is not None:summary['old_unpublished_tickets']=book['metadata_conservation']['unpublished_tickets']
        summary['original_scientific_batch_complete']=False
        summary['original_worker_checkpoints_cpu_verified_count']=len(worker_checkpoints)
        summary['original_worker_reported_error_count']=sum(len(r['errors']) for r in worker_checkpoints)
        summary['original_worker_checkpoint_metadata_preserved_in_evidence']=True
        if locators is not None:
            summary['original_missing_worker_reports']=['worker_'+str(i).zfill(2)+'.json' for i in range(16)
              if 'worker_'+str(i).zfill(2)+'.json' not in locators['files']]
        summary.update(evidence_records=result_count,evidence_bytes=details_bytes,finished_unix_seconds=time.time(),
          original_output_directory=str(C.OLD),original_dispatcher_book=str(C.BOOK),new_output_cap_bytes=2<<30,
          future_parent_actual_C0_not_assumed=True,old_raw_or_F64_payload_in_logs=False)
        if detail.exists():
            h=hashlib.sha256()
            with detail.open('rb') as f:
                for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
            summary['evidence_reference']={'path':str(detail),'bytes':details_bytes,'sha256':h.hexdigest()}
        I.write_new(root/'receipt.json',summary)
        print(json.dumps({'status':C.STATUS,'verified_windows':summary.get('cpu_verified_committed_windows'),
          'verification_complete':summary['inventory_verification_complete'],'errors':len(summary['errors'])}),flush=True)
    C.need(not summary['errors'],'AUDIT_FAILURE_EVIDENCE_RETAINED_NO_OLD_ACCEPT')

if __name__=='__main__':main()
