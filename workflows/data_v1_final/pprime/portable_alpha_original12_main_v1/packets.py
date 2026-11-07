"""Parallel original native/F64 transport; inherit hashes, never render or invoke."""
import concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,pathlib,stat,time
from multiprocessing.util import Finalize
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from workflows.data_v1_final.pprime import geometry
from workflows.data_v1_final.pprime.formal_packed_day_v1 import io as OriginalIO
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import prepare as OriginalReaders
from workflows.expansion.common_molecular_fp_main_v1.io import Body
from . import contract as C,io as I

MID_PARTITION_BYTES=64<<20
_pack=None;_pack_finalizer=None

def pack_close():
    state=_pack
    if state is None:return
    path=state['out']/'hash_workers'/('worker_%d_closed.json'%os.getpid())
    C.need(path.is_file() and OriginalReaders._hash_engine is None,'ORIGINAL_NOINVOKE_READER_NATURALLY_CLOSED')
    OriginalIO.Store(state['out']/'pack_worker_lifecycle',8<<20).json(
      state['out']/'pack_worker_lifecycle'/('worker_%d_closed.json'%os.getpid()),{
        'schema':'PPRIME_PORTABLE_MID_WORKER_CLOSED_V1','pid':os.getpid(),'start_ticks':OriginalIO.ticks(os.getpid()),
        'job_id':state['session']['job_id'],'MIDs':state['mids'],'records':state['records'],
        'original_reader_closure_reference':C.Q.pin(path),'native_invokes':0,'input_render_calls':0,
        'original_engine_closed':True})

def pack_initialize(session,context,protocol,audit,out,header_reference,ledger_root,ready_event):
    global _pack,_pack_finalizer
    # Entire original initializer/finalizer: one persistent original engine per
    # actual worker, NoInvoke, owned scratch, original reader and natural close.
    OriginalReaders.hash_initialize(session,context,protocol,audit,out)
    _pack={'session':session,'protocol':protocol,'out':pathlib.Path(out),'header':header_reference,
      'ledger_root':pathlib.Path(ledger_root),'mids':0,'records':0}
    # Original hash_close has priority10. This metadata-only closure follows it.
    _pack_finalizer=Finalize(None,pack_close,exitpriority=5)
    OriginalIO.Store(_pack['out']/'pack_worker_lifecycle',8<<20).json(
      _pack['out']/'pack_worker_lifecycle'/('worker_%d_ready.json'%os.getpid()),{
        'schema':'PPRIME_PORTABLE_READER_WORKER_READY_V1','pid':os.getpid(),
        'job_id':session['job_id'],'original_Noinvoke_reader_initialized':True,'native_invokes':0})
    # Parent releases only after every actually requested initializer is ready.
    # On any parent stop it releases in finally so prepaid tasks drain naturally.
    ready_event.wait()

def pack_mid(item):
    import numpy as np
    state=_pack;OriginalReaders.I.continuation(state['session'])
    mid,rows=item;engine=OriginalReaders._hash_engine
    root=state['out']/'mid_packets'/hashlib.sha256(mid.encode()).hexdigest()
    root.mkdir(parents=True,mode=0o700);local=OriginalIO.Store(root,MID_PARTITION_BYTES)
    result=[];source_entries=[]
    with C.P.OriginalInputs.NoInvoke(OriginalReaders._hash_old) as guard:
        for key,pair,hashes,raw,hash_raw,_ in rows:
            C.need(pair['molecule_id']==mid and not (state['ledger_root']/(key+'.json')).exists(),
              'ONE_FROZEN_MID_NO_NEW_GLOBAL_CLAIM_NO_PARTIAL_PAIR_RELEASE')
            original=engine.NATIVE.read_native(pair['source']);graph=engine.source_bond_graph(original['_source_raw'],original)
            C.need(not graph['bond_graph_issues'] and graph['bond_pairs_zero_based'] is not None,'ORIGINAL_NATIVE_GRAPH_WITHOUT_REPAIR')
            native,provenance=geometry.adapt_native(original,dict(pair,bond_pairs=graph['bond_pairs_zero_based']))
            expected=hashes['hashes']
            C.need(len(expected)==12 and {v['task'] for v in expected}==set(C.O.TASKS)
              and provenance['uff_geometry_sha256']==hashes['geometry_sha256'],'INHERITED12_HASHES_AND_ORIGINAL_GEOMETRY')
            source=pair['source'];sid=int(source['shard_id']);real=int(source.get('real_index',source.get('source_record_index')))
            with engine.NATIVE.HANDLES[sid].begin(buffers=False) as transaction:payload=transaction.get(('%09d'%real).encode())
            C.need(payload is not None and hashlib.sha256(payload).hexdigest()==source['record_payload_sha256'],
              'ORIGINAL_FULL_NATIVE_PAYLOAD_BYTES_SHA_NO_REENCODING')
            folder=root/'records'/key
            binary={'pair_reference':('pair.bin',raw),'hashes_reference':('hashes.bin',hash_raw),
              'native_payload_reference':('native_payload.bin',bytes(payload)),
              'atomic_numbers_i64_reference':('atomic_numbers_i64.bin',np.asarray(original['z'],dtype='<i8').tobytes()),
              'native_coordinates_f64_reference':('native_coordinates_f64.bin',np.asarray(original['coords'],dtype='<f8').tobytes()),
              'uff_coordinates_f64_reference':('uff_coordinates_f64.bin',np.asarray(native['coords'],dtype='<f8').tobytes())}
            refs={}
            for name,(filename,data) in binary.items():
                ref=local.write(folder/filename,data)
                # Actual stable-FD readback of every written payload/F64/blob.
                with I.held(ref,[root],[ref]) as (stream,_):
                    C.need(stream.read()==data,'ACTUAL_PACKET_RAW_F64_I64_BYTE_READBACK:'+name)
                refs[name]=ref
            C.need(refs['uff_coordinates_f64_reference']['sha256']==pair['uff_coordinate_sha256']
              and refs['atomic_numbers_i64_reference']['sha256']==original['native_atom_order_sha256']
              and refs['native_coordinates_f64_reference']['sha256']==original['native_coordinates_sha256'],'ORIGINAL_F64_ATOM_BITS')
            preflight=local.json(folder/'preflight.json',{'schema':'PPRIME_ALPHA_ORIGINAL12_CPU_PREFLIGHT_V1',
              'record_id':pair['record_id'],'physical_key':key,'original_pair_sha256':hashes['original_pair_sha256'],
              'geometry_sha256':provenance['uff_geometry_sha256'],'original_12_input_hashes':expected,
              'original_native_payload_sha256':source['record_payload_sha256'],'new_native_invokes':0,
              'new_QM_UFF_embedding_calls':0,'scientific_rules_and_original_roles_unchanged':True,
              'main_recomputed_rendered_inputs':False,'input_hash_authority':'ORIGINAL_CPU_CLOSED_PREPARED_COMPONENT',
              'Alpha_original_rendered_hash_verification_required_before_claim_and_Native':True,
              'actual_packet_bytes_readback_verified':True})
            packet=local.json(folder/'packet.json',{'schema':'PPRIME_ALPHA_ORIGINAL12_PACKET_V1',
              'record_id':pair['record_id'],'molecule_id':mid,'physical_key':key,
              'original_pair_sha256':hashes['original_pair_sha256'],'prepared_header_reference':state['header'],
              'original_protocol_reference':state['protocol'],**refs,'preflight_reference':preflight})
            result.append({'record_id':pair['record_id'],'molecule_id':mid,'physical_key':key,
              'random_order_rank':pair['random_order_rank'],'packet_reference':packet,
              'pair_sha256':hashes['original_pair_sha256']})
            source_entries.append({'shard_id':sid,'real_index':real,'origin_source_path':source['source_path'],
              'original_payload_sha256':source['record_payload_sha256'],'native_payload_reference':refs['native_payload_reference']})
    C.need(guard.attempts==0,'ZERO_NATIVE_OR_RENDER_IN_MID_WORKER')
    closed=local.json(root/'closed.json',{'schema':'PPRIME_PORTABLE_MID_CLOSED_V1','molecule_id':mid,
      'worker_pid':os.getpid(),'records':len(result),'all_packet_bytes_readback_verified':True,
      'native_invokes':0,'input_render_calls':0})
    state['mids']+=1;state['records']+=len(result)
    return {'molecule_id':mid,'records':result,'source_entries':source_entries,'closed_reference':closed,
      'charged_bytes':local.charged,'worker_pid':os.getpid()}

def parallel_packets(plan,proof,out,b,chosen,store,budget):
    grouped={}
    for row in chosen:grouped.setdefault(row[1]['molecule_id'],[]).append(row)
    tasks=list(grouped.items());workers=min(16,len(tasks));results=[]
    freeze=store.json(out/'frozen_mid_assignment.json',{'schema':'PPRIME_PORTABLE_FROZEN_MID_ASSIGNMENT_V1',
      'job_id':str(proof['job_id']),'prepared_header_reference':b['component_header_reference'],
      'MIDs':[{'molecule_id':mid,'physical_keys':[v[0] for v in rows]} for mid,rows in tasks],
      'maximum_workers':workers,'MID_partition_bytes':MID_PARTITION_BYTES,'selection_completed_before_workers':True})
    if not workers:return [],{'worker_count':0,'frozen_assignment_reference':freeze,'all_workers_naturally_closed':True}
    (out/'hash_workers').mkdir();(out/'pack_worker_lifecycle').mkdir()
    # Exact finite lifecycle metadata reservation, separate from MID output roles.
    store.reserve(workers*(64<<10))
    session=OriginalIO.source_session(C.Q.pin(plan['plan_path']),plan,proof)
    cp=b['component_plan'];ledger_root=C.F.ledger(cp)/'physical_records_v1'
    context=mp.get_context('spawn');ready_event=context.Event()
    pool=cf.ProcessPoolExecutor(max_workers=workers,mp_context=context,initializer=pack_initialize,
      initargs=(session,b['context'],cp['original_protocol_reference'],b['component_header']['audit_membership_reference'],
        str(out),b['component_header_reference'],str(ledger_root),ready_event))
    active={};next_task=0;errors=[];processes=[];released=False
    def accept_result(mid,result):
        wanted={v[0] for v in grouped[mid]};actual=[v['physical_key'] for v in result['records']]
        C.need(result['molecule_id']==mid and len(actual)==len(wanted) and set(actual)==wanted,
          'EXACT_FROZEN_MID_PHYSICAL_RECORD_RETURN_NO_LOSS_OR_RESELECTION')
        expected=out/'mid_packets'/hashlib.sha256(mid.encode()).hexdigest()/'closed.json'
        C.need(result['closed_reference']['path']==str(expected),'EXACT_OWN_MID_CLOSED_RECEIPT')
        value=C.meta(result['closed_reference'])
        C.need(value['molecule_id']==mid and value['records']==len(wanted) and value['all_packet_bytes_readback_verified'] is True,
          'ACTUAL_CLOSED_MID_PACKET_READBACK_COUNTS')
        budget.close_mid(mid,result['charged_bytes']);results.append(result)
    try:
        while active or next_task<len(tasks):
            budget.check()
            while next_task<len(tasks) and len(active)<workers:
                mid,rows=tasks[next_task];budget.admit_mid(mid,MID_PARTITION_BYTES)
                try:future=pool.submit(pack_mid,(mid,rows))
                except BaseException:budget.unknown_mid(mid);raise
                active[future]=mid;next_task+=1
            if not released:
                while len(list((out/'pack_worker_lifecycle').glob('worker_*_ready.json')))<workers:
                    budget.check();C.need(not any(f.done() for f in active),'ALL_READER_INITIALIZERS_READY_OR_FAIL_CLOSED')
                    time.sleep(.1)
                ready_event.set();released=True
            done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
            for future in done:
                mid=active.pop(future)
                try:
                    result=future.result();accept_result(mid,result)
                except BaseException as exc:
                    if mid in budget.active_mid_bytes:budget.unknown_mid(mid)
                    errors.append({'molecule_id':mid,'error':repr(exc)})
            if errors:break
    finally:
        ready_event.set();processes=list(pool._processes.values());pool.shutdown(wait=True,cancel_futures=False)
        # Every already-dispatched MID is naturally drained, including after a
        # stop/error. Parent alone settles the finite output role registry.
        for future,mid in list(active.items()):
            try:
                result=future.result();accept_result(mid,result)
            except BaseException as exc:
                if mid in budget.active_mid_bytes:budget.unknown_mid(mid)
                errors.append({'molecule_id':mid,'error':repr(exc)})
        closures=[]
        for process in processes:
            path=out/'pack_worker_lifecycle'/('worker_%d_closed.json'%process.pid)
            C.need(not process.is_alive() and process.exitcode==0 and path.is_file(),'EVERY_ACTUAL_READER_WORKER_NATURALLY_JOINED')
            ref=C.Q.pin(path);value=C.meta(ref)
            C.need(value['original_engine_closed'] is True and value['native_invokes']==value['input_render_calls']==0,
              'REAL_ORIGINAL_READER_CLOSE_NO_NATIVE_OR_INPUT_RENDER')
            closures.append(dict(value,reference=ref))
        store.json(out/'parallel_worker_closure.json',{'schema':'PPRIME_PORTABLE_PARALLEL_WORKER_CLOSURE_V1',
          'actual_worker_count':len(processes),'requested_worker_count':workers,'workers':closures,
          'frozen_assignment_reference':freeze,'completed_MIDs':len(results),'errors':errors,
          'all_workers_naturally_closed':True,'worker_output_partition_bytes':MID_PARTITION_BYTES,
          'parent_only_budget_index_and_authorization_writes':True,'signals_sent':False})
    C.need(not errors and len(results)==len(tasks) and len(processes)==workers
      and sum(v['MIDs'] for v in closures)==len(tasks)
      and sum(v['records'] for v in closures)==len(chosen),'ALL_FROZEN_MIDS_CLOSED_WITH_ACTUAL_PARALLEL_WORKERS')
    results.sort(key=lambda v:v['molecule_id'],reverse=True)
    return results,{'worker_count':len(processes),'frozen_assignment_reference':freeze,
      'worker_closures':closures,'all_workers_naturally_closed':True,'input_render_calls':0,'native_invokes':0}

def original_copy(ref,target,store,budget,software=None):
    """Copy verified ordinary data or the exact registered software target."""
    if software is None:
        holder=Body(C.P.triple(ref),budget);stream=holder.stream
        close=holder.close;check=holder.check
    else:
        path=pathlib.Path(software['actual_CPU_alias_state']['resolved_path'])
        before=OriginalIO.Preparation.software_stamp(path.lstat())
        C.need(before==tuple(software['actual_CPU_alias_state']['frame']),'SAME_REGISTERED_SOFTWARE_TARGET_BEFORE_COPY')
        stream=path.open('rb')
        def check():
            C.need(OriginalIO.Preparation.software_stamp(os.fstat(stream.fileno()))==before
              and OriginalIO.Preparation.software_stamp(path.lstat())==before,'SOFTWARE_TARGET_COPY_CURRENT_FRAME')
        close=stream.close
    source_mode=stat.S_IMODE(os.fstat(stream.fileno()).st_mode)
    target=pathlib.Path(target);target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    C.need(not target.exists(),'FRESH_OPAQUE_PORTABLE_ASSET');store.reserve(ref['bytes']+4096)
    digest=hashlib.sha256();size=0
    try:
        check();stream.seek(0)
        with target.open('xb') as dst:
            while block:=stream.read(1<<20):
                budget.check(False);digest.update(block);size+=len(block);dst.write(block)
            dst.flush();os.fsync(dst.fileno())
        check();C.need(size==ref['bytes'] and digest.hexdigest()==ref['sha256'],'OPAQUE_COPY_BYTES_WHOLE_SHA_EXACT')
    finally:close()
    mode=source_mode;os.chmod(target,mode)
    return {'path':str(target),'bytes':size,'sha256':digest.hexdigest()},mode

def execute(plan,proof,out,b,store,budget):
    import duckdb
    cp=b['component_plan'];h=b['component_header'];root=pathlib.Path(h['index_reference']['path']).parent
    # The shared adopter verifies the published component, not a fictitious
    # terminal PREP Parent. Hash workers may still be alive elsewhere.
    component_qa=b['component_authority'].verify_component(cp,proof,budget,allowed_owner='ALPHA')
    component_qa_ref=store.json(out/'component_cpu_qa.json',component_qa)
    chosen=[];skipped=[]
    with I.held(h['index_reference'],[C.Q.ROOT/'artifacts'],plan['data_references']):
        db=duckdb.connect(h['index_reference']['path'],read_only=True)
        try:
            C.need(db.execute('SELECT count(*),count(DISTINCT rid),count(DISTINCT mid) FROM pairs').fetchone()==(h['records'],h['records'],h['MIDs']),
              'EXACT_CLOSED_COMPONENT_RECORD_AND_MID_CENSUS')
            cursor=db.cursor();cursor.execute('SELECT mid,rank,pair,hashes FROM pairs ORDER BY mid DESC,rank')
            group=[];last=None;selected_mids=0
            def accept(rows):
                if not rows:return False
                C.need(1<=len(rows)<=2 and len({v[1] for v in rows})==len(rows)
                  and all(v[1] in (0,1) for v in rows),'ONLY_ORIGINAL_PREPARED_FIRST2_RANKS_NO_RESELECTION')
                packet=[]
                for mid,rank,pblob,hblob in rows:
                    raw=bytes(pblob);hash_raw=bytes(hblob);pair=json.loads(raw);hashes=json.loads(hash_raw)
                    C.need(pair['molecule_id']==mid and pair['random_order_rank']==rank
                      and pair['record_id']==hashes['record_id'] and pair['geometry_source']=='uff_sprime'
                      and hashlib.sha256(raw).hexdigest()==hashes['original_pair_sha256']
                      and hashlib.sha256(C.O.canonical(pair)).hexdigest()==hashes['original_pair_sha256'],
                      'ORIGINAL_PAIR_BYTES_AND_PREPARED_HASH_UNCHANGED')
                    key=C.F.record_once_key(pair,cp['original_protocol_reference'])
                    claim=C.F.ledger(cp)/'physical_records_v1'/(key+'.json')
                    if claim.exists():skipped.append({'molecule_id':mid,'record_id':pair['record_id'],'physical_key':key,'claim_reference':C.Q.pin(claim)})
                    packet.append((key,pair,hashes,raw,hash_raw,claim.exists()))
                if any(v[-1] for v in packet):return False
                chosen.extend(packet);return True
            while rows:=cursor.fetchmany(128):
                budget.check()
                for row in rows:
                    if last is not None and row[0]!=last:
                        selected_mids+=int(accept(group));group=[]
                        if selected_mids>=plan['maximum_molecules']:break
                    group.append(row);last=row[0]
                if selected_mids>=plan['maximum_molecules']:break
            if selected_mids<plan['maximum_molecules']:selected_mids+=int(accept(group))
            cursor.close()
        finally:db.close()
    C.need(selected_mids<=len(chosen)<=2*selected_mids<=2*plan['maximum_molecules'],
      'ACTUAL_BOUNDED_UNCLAIMED_COMPONENT_SUBSET_NO_MISSING_RANK_REGENERATION')
    (out/'runtime').mkdir();software=C.registered_software_specs(b['context']);software_frames={}
    engine,legacy,old,pilot=T.engine(b['context'],C.meta)
    C.need(old==b['old'] and C.meta(cp['original_protocol_reference'])==old,'ORIGINAL_PROTOCOL_BEFORE_ZERO_INVOKE_EXPORT')
    reproduction_origin=C.P.triple(b['context']['execution_asset_verification_context']['manifest_reference'])
    C.need(legacy['reproduction_package']['path']==reproduction_origin['path']
      and legacy['reproduction_package']['sha256']==reproduction_origin['sha256'],'EXACT_ORIGINAL_REPRODUCTION_LOCATOR')
    registered=[*b['context']['execution_asset_references'],*b['context']['source_references'],*b['data'],*b['refs'],
      *b['pilot']['small_authority_pins'],*b['pilot']['large_authority_pins'],*plan['source_references'],reproduction_origin]
    def complete(ref):
        if 'bytes' in ref:return C.P.triple(ref)
        matches=C.unique([C.P.triple(v) for v in registered if v.get('path')==ref['path']
                          and v.get('sha256')==ref['sha256'] and 'bytes' in v])
        C.need(len(matches)==1,'EXISTING_FULL_CLOSED_LOCATOR_REQUIRED_NOT_FIRST_DATA_HASH_ON_LOGIN')
        return matches[0]
    assets=C.unique([complete(v) for v in [*b['context']['execution_asset_references'],*plan['additional_runtime_source_references'],
      *C.runtime_source_references(),*[v for v in plan['source_references'] if v['path'].endswith('.py')],
      b['context']['pilot_config'],b['pilot']['legacy_contract'],b['pilot']['source_plan'],
      cp['original_protocol_reference'],cp['source_context_reference'],cp['retention_policy_reference'],
      reproduction_origin,C.SOFTWARE_WHITELIST]])
    source_paths={v['path'] for v in b['sources']}
    source_frames=[];asset_rows=[]
    scratch=None;records=[];authorizations=[];source_entries=[]
    try:
        # Original closed whole-LMDB SHA is inherited, never recomputed for a
        # small transport. The original reader checks each full selected entry
        # payload SHA; original current source frames are checked before/after.
        source_frames=C.P.OriginalInputs.lmdb_frames([v[1] for v in chosen],b['context']['execution_asset_references'])
        for ref in assets:
            if ref['path'] in source_paths:continue
            budget.check();spec=None
            if ref['path'] in software:
                spec=OriginalIO.Preparation.hash_software_original(C.P.triple(ref),software[ref['path']],budget)
                software_frames[ref['path']]=spec
            relative=pathlib.PurePosixPath(ref['path']);C.need(relative.is_absolute() and '..' not in relative.parts,'ORIGIN_ABSOLUTE_TREE')
            target=out/'runtime_assets'/pathlib.Path(*relative.parts[1:])
            portable,mode=original_copy(ref,target,store,budget,spec)
            asset_rows.append({'origin_reference':C.P.triple(ref),'portable_reference':portable,'mode':mode,
              'source_kind':'REGISTERED_SOFTWARE_ORIGINAL' if spec else 'ORIGINAL_EXECUTION_ASSET_OR_SOURCE'})
        C.need(set(software)<=set(software_frames),'ALL14_PLUS22_FROZEN_ORIGINAL_SOFTWARE_COPIED_NOT_ALTERNATIVE_VERSIONS')
        selected,_=original_copy(h['audit_selected_reference'],out/'runtime/audit_selected.parquet',store,budget)
        portable_audit=dict(b['audit'],selected_records=dict(selected,rows=b['audit']['selected_records']['rows']))
        audit_ref=store.json(out/'runtime/audit_membership.json',portable_audit)
        source_audit,_=original_copy(h['source_audit_reference'],out/'runtime/source_audit.DATA.json',store,budget)
        reproduction,_=original_copy(reproduction_origin,out/'runtime/reproduction_package.json',store,budget)
        closed_mids,closed=parallel_packets(plan,proof,out,b,chosen,store,budget)
        # The parent imported Source metadata only. Original reader/engine
        # initialization, graph/payload/F64 verification and packet fsyncs ran
        # in the actual persistent workers, never in this serialization loop.
        engine=None;ledger_root=C.F.ledger(cp)/'physical_records_v1'
        for completed_mid in closed_mids:
            budget.check(False);source_entries.extend(completed_mid['source_entries'])
            for row in completed_mid['records']:
                key=row['physical_key'];pair_sha=row.pop('pair_sha256')
                auth=store.json(out/'dispatch_authorizations'/(key+'.json'),{'schema':'PPRIME_ALPHA_DISPATCH_AUTHORIZATION_V1',
                  'record_id':row['record_id'],'molecule_id':row['molecule_id'],'physical_key':key,
                  'pair_sha256':pair_sha,'packet_reference':row['packet_reference'],
                  'prepared_header_reference':b['component_header_reference'],'original_protocol_reference':cp['original_protocol_reference'],
                  'external_assignment_reference':plan['external_assignment_reference'],'original_ledger_path':str(ledger_root/(key+'.json')),
                  'main_export_job_id':str(proof['job_id']),'main_export_boot_id':proof['boot_id'],
                  'target_endpoint':C.ALPHA_ENDPOINT,'target_uid':1264,'packet_is_not_claim':True})
                records.append(dict(row,dispatch_authorization_reference=auth))
                authorizations.append({'physical_key':key,'authorization_reference':auth})
        C.P.OriginalInputs.check_lmdb_frames(source_frames)
        record_index=store.write(out/'record_index.DATA.jsonl',b''.join(C.O.canonical(v)+b'\n' for v in records) or b'\n')
        pages=[]
        for offset in range(0,len(authorizations),128):
            pages.append(store.json(out/'dispatch_authorizations'/('page_%03d.json'%(offset//128)),{
              'schema':'PPRIME_ALPHA_SMALL_DISPATCH_AUTHORIZATION_PAGE_V1','entries':authorizations[offset:offset+128]}))
        inventory=store.json(out/'dispatch_authorization_inventory.json',{'schema':'PPRIME_ALPHA_SMALL_DISPATCH_AUTHORIZATION_INVENTORY_V1',
          'records':len(records),'page_references':pages,'scientific_values_or_coordinates_embedded':False})
        source_entry_index=store.write(out/'portable_source_entries.DATA.jsonl',b''.join(C.O.canonical(v)+b'\n' for v in source_entries) or b'\n')
        source_inventory=store.json(out/'source_inventory.json',{'schema':'PPRIME_ALPHA_ORIGINAL_SOURCE_LOCATORS_V1',
          'sources':b['sources'],'portable_source_entries_reference':source_entry_index,'selected_source_current_frames':source_frames,
          'whole_LMDB_files_copied':False,'whole_LMDB_SHA_inherited_not_rehashed':True,
          'every_exported_payload_complete_SHA_verified':True,'Main_origin_paths_preserved':True})
        assets_ref=store.json(out/'runtime_asset_locators.json',{'schema':'PPRIME_ALPHA_RUNTIME_ASSET_LOCATORS_V1','rows':asset_rows})
        manifest=store.json(out/'portable_manifest.json',{'schema':'PPRIME_ALPHA_ORIGINAL12_PORTABLE_INPUTS_V1',
          'records':len(records),'MIDs':len({v['molecule_id'] for v in records}),'record_index_reference':record_index,
          'dispatch_authorization_inventory_reference':inventory,'prepared_header_reference':b['component_header_reference'],
          'external_assignment_reference':plan['external_assignment_reference'],'component_plan_reference':plan['component_plan_reference'],
          'component_cpu_qa_reference':component_qa_ref,
          'original_protocol_reference':cp['original_protocol_reference'],'source_context_reference':cp['source_context_reference'],
          'retention_policy_reference':cp['retention_policy_reference'],
          'original_audit_membership_reference':h['audit_membership_reference'],'portable_audit_membership_reference':audit_ref,
          'source_audit_reference':source_audit,'source_inventory_reference':source_inventory,
          'runtime_asset_locator_reference':assets_ref,'reproduction_package_reference':reproduction,
          'original_reproduction_package_reference':reproduction_origin,
          'origin_export_root':str(out),'packets_are_not_claims':True,'whole_LMDB_files_copied':False,
          'native_invokes':0,'global_once_claims_created':0,'PREP_parent_C0_claimed':False,
          'scientific_PASS':False,'final_Common_or_training_admission':False})
        skipped_ref=store.json(out/'excluded_existing_claims.json',{'records':skipped,'all_outcomes_consumed_no_retry':True})
        return {'portable_manifest_reference':manifest,'records':len(records),'MIDs':len({v['molecule_id'] for v in records}),
          'component_cpu_qa_reference':component_qa_ref,
          'excluded_existing_claims_reference':skipped_ref,'original_engine_close':closed,'native_invokes':0,'global_once_claims_created':0}
    finally:
        if engine is not None:engine.close_worker()
        if source_frames:C.P.OriginalInputs.check_lmdb_frames(source_frames)
        if scratch is not None and scratch.exists() and not any(scratch.iterdir()):scratch.rmdir()
