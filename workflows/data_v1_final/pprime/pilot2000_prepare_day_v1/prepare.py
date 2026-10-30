"""Revalidate the existing2000 geometries and render two protocol choices; invoke0."""
import argparse,collections,concurrent.futures as cf,hashlib,io,json,os,pathlib,stat,sys,tempfile,traceback,unittest
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from workflows.data_v1_final.pprime import geometry
from workflows.expansion.common_molecular_fp_main_v1.io import Body,BorrowedFile
from . import contract as C
Q=C.Q;I=C.ResourceOrigin.I;M=C.ResourceOrigin

def software_stamp(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode,s.st_nlink)

def software_alias_state(path):
    """Bounded actual CPU alias chain; no body load, import or program execution."""
    path=pathlib.Path(path);C.need(path.is_absolute() and '..' not in path.parts,'LITERAL_REGISTERED_SOFTWARE_ALIAS')
    pending=collections.deque(path.parts[1:]);resolved=pathlib.Path('/');links=[];directories=[];steps=0
    while pending:
        steps+=1;C.need(steps<=512 and len(links)<=40,'FINITE_SOFTWARE_SYMLINK_RESOLUTION')
        name=pending.popleft()
        if name in ('','.') :continue
        if name=='..':resolved=resolved.parent;continue
        current=resolved/name;info=current.lstat()
        if stat.S_ISLNK(info.st_mode):
            C.need(info.st_uid in (0,1278),'ONLY_ROOT_OR_MAIN_USER_SOFTWARE_ALIAS_OWNER');target=os.readlink(current)
            links.append({'path':str(current),'target':target,'frame':software_stamp(info)})
            value=pathlib.Path(target)
            if value.is_absolute():resolved=pathlib.Path('/');pending.extendleft(reversed(value.parts[1:]))
            else:pending.extendleft(reversed(value.parts))
            continue
        resolved=current
        if pending:
            C.need(stat.S_ISDIR(info.st_mode),'SOFTWARE_PARENT_IS_DIRECTORY')
            directories.append((str(current),info.st_dev,info.st_ino,info.st_uid,info.st_mode))
        else:C.need(stat.S_ISREG(info.st_mode),'SOFTWARE_TERMINAL_REGULAR_NOT_DEVICE_OR_PIPE')
    info=resolved.lstat();C.need(stat.S_ISREG(info.st_mode) and info.st_uid in (0,1278),'REGISTERED_SOFTWARE_TARGET_REGULAR_OWNER')
    return {'alias':str(path),'resolved_path':str(resolved),'frame':software_stamp(info),'links':links,'directories':directories}

def hash_software_original(ref,spec,budget):
    """Only caller-registered frozen software; regular scientific Body is untouched."""
    C.need(C.triple(ref)==spec['reference'],'EXACT_FROZEN_SOFTWARE_TRIPLE_NOT_ARBITRARY_EXTERNAL_DATA');first=software_alias_state(ref['path'])
    target=pathlib.Path(first['resolved_path']);before=target.lstat()
    C.need(before.st_size==ref['bytes'] and (spec['source_uid'] is None or before.st_uid==spec['source_uid'])
      and (spec['mode'] is None or stat.S_IMODE(before.st_mode)==spec['mode']),'FROZEN_SOFTWARE_SIZE_UID_PERMISSION_MODE')
    frozen_target=spec['resolved_source_path']
    # Older packages sometimes record the source locator itself as "resolved";
    # no distinct historical link target then exists. Preserve that declaration
    # and prove the entire current chain plus identical frozen terminal bytes.
    if frozen_target not in (None,ref['path']):C.need(str(target)==frozen_target,'EXACT_DISTINCT_FROZEN_RESOLVED_SOFTWARE_TARGET')
    fd=os.open(target,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW);h=hashlib.sha256();n=0
    with os.fdopen(fd,'rb') as stream:
        C.need(software_stamp(os.fstat(stream.fileno()))==first['frame'],'SAME_RESOLVED_SOFTWARE_FD_BEFORE_HASH')
        while block:=stream.read(1<<20):h.update(block);n+=len(block);budget.check(False)
        C.need(software_stamp(os.fstat(stream.fileno()))==first['frame'] and software_alias_state(ref['path'])==first
          and n==ref['bytes'] and h.hexdigest()==ref['sha256'],'WHOLE_SOFTWARE_SHA_AND_ALIAS_TARGET_SAME_FD_FRAME')
    return {'reference':ref,'frozen_registration':spec,'actual_CPU_alias_state':first,'whole_SHA_verified':True,
      'system_library_compatibility_not_proven_until_original_initialize':True,'legacy_alias_value_not_invented_as_historical_link_chain':frozen_target==ref['path']}

def software_reader_boundaries(out):
    root=out/'synthetic_software_reader';root.mkdir();payload=b'synthetic frozen software\n'*(140000);target=root/'program.bin';target.write_bytes(payload)
    alias=root/'program';alias.symlink_to('program.bin');ref={'path':str(alias),'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
    spec={'reference':ref,'source_uid':os.getuid(),'mode':stat.S_IMODE(target.stat().st_mode),'resolved_source_path':str(target)}
    class Budget:
        def check(self,*args,**kwargs):pass
    observed=hash_software_original(ref,spec,Budget());C.need(observed['whole_SHA_verified'] and observed['actual_CPU_alias_state']['links'],'SYNTHETIC_ALIAS_FD_HASH')
    bad=dict(ref,sha256='0'*64)
    try:hash_software_original(bad,dict(spec,reference=bad),Budget())
    except ValueError:pass
    else:raise ValueError('SYNTHETIC_SOFTWARE_SHA_DRIFT_NOT_REJECTED')
    loop=root/'loop';loop.symlink_to('loop')
    try:software_alias_state(loop)
    except ValueError:pass
    else:raise ValueError('SYNTHETIC_SOFTWARE_ALIAS_CYCLE_NOT_REJECTED')
    alias.unlink();loop.unlink()
    return {'synthetic_only':True,'registered_alias_whole_FD_SHA':True,'wrong_SHA_rejected':True,'alias_cycle_rejected':True,
      'scientific_Body_or_actual_software_opened':False,'does_not_replace_original3_methods':True}

class Budget(M.Budget):
    def __init__(self,plan,proof,out):
        I.OriginalBudget.__init__(self,plan,proof,out);self.carve=C.meta(plan['root_carveout_review_reference'])
        M.carveout(self.carve,{'scope_key':C.KEY,'node':proof['request']['node'],'resource_authority_reference':plan['resource_authority_reference'],'estimated_peak_output_bytes':self.cap})
        self.total=self.carve['total_future_reserved_bytes'];node=proof['request']['node'];C.parameters(node)
        if node=='compute-0-13':client=M.Client
        elif node=='compute-0-19':
            from workflows.data_v1_final.execution.cpu_analysis_cpu19_v1.quota_provider import Client
            client=Client
        else:
            from workflows.data_v1_final.execution.cpu_analysis_day_v1.quota_provider import Client
            client=Client
        self.client=client(plan['quota_provider_review_reference'],proof['request']);self.next_quota=0;self.quota=None;self.written=0
        self.quota_guard_events=out/'quota_guard_events';self.quota_guard_events.mkdir(mode=0o700);self.quota_guard_event_references=[]

def selected_population(reference,mids,columns,budget):
    import pyarrow.parquet as pq
    found={};body=Body(reference,budget)
    try:
        src=pq.ParquetFile(BorrowedFile(body.stream))
        try:
            C.need(set(columns)<=set(src.schema_arrow.names),'ACTUAL_REQUIRED_SOURCE_COLUMNS')
            for batch in src.iter_batches(batch_size=8192,columns=columns,use_threads=False):
                budget.check()
                for row in batch.to_pylist():
                    if row['molecule_id'] in mids:
                        C.need(row['molecule_id'] not in found,'UNIQUE_SELECTED_SOURCE_MID');found[row['molecule_id']]=row
        finally:src.close()
        body.check();return found
    finally:body.close()

def input_hashes(engine,native,pair,old,new):
    row=dict(pair['source'],record_id=pair['record_id'],molecule_id=pair['molecule_id'],geometry_source='uff_sprime')
    result=[]
    for before,after in zip(old['tasks'],new['tasks']):
        original=engine.render_inputs(before,native,row,old);candidate=engine.render_inputs(after,native,row,new)
        C.need(set(original)==set(candidate),'IDENTICAL_ORIGINAL_INPUT_FILE_NAMES')
        for name in original:
            if name=='input.xyz':C.need(original[name]==candidate[name],'EXACT_XYZ_BODY_NO_GEOMETRY_CHANGE')
            if name=='input.mop':C.need(original[name].splitlines(keepends=True)[3:]==candidate[name].splitlines(keepends=True)[3:],'EXACT_MOPAC_COORDINATE_BYTES_NO_GEOMETRY_CHANGE')
        result.append({'task':before['name'],'original_input_file_sha256':[{'name':n,'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(original.items())],
          'candidate_input_file_sha256':[{'name':n,'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(candidate.items())]})
    C.need(len(result)==12,'EXACT12_TASK_HASH_SETS');return result

def fixtures(out):
    from . import test_v1
    test_v1.WORKSPACE=out;suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries);C.need(suite.countTestCases()==3,'EXACT3_BEFORE_DATA_BUDGET_INITIALIZE')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    software_checks=software_reader_boundaries(out) if r.wasSuccessful() else None
    value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),
      'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),'before_DATA_Budget_initialize_invoke':True}
    value['software_reader_synthetic_boundary_checks']=software_checks
    ref=Q.write_new(out/'source3.json',value);C.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_FAILED_NO_DATA');return ref

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=C.meta(Q.pin(a.plan));old,new,diff,context,pilot,saved,pair_ref,sprime,population,val_ref,data,parents=C.parents(plan);params=C.parameters(plan['node'])
    C.need(plan['schema']=='PPRIME_ORIGINAL2000_ZERO_INVOKE_PLAN_V1' and plan['scope_parameters']==params and plan['data_references']==data,'EXACT_CLOSED2000_PREPARE_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=require_startup(a.startup_proof,expected_kind='analysis',expected_scope_key=C.KEY,expected_scope_parameters=params,expected_execution_argv=argv,
      expected_source=HERE_SOURCE,required_references=[Q.pin(a.plan),*plan['source_references']]);req=proof['request']
    C.need(req['node']==plan['node'] and req['cpus']==16 and req['wall_seconds']==plan['wall_seconds']==C.WALL and req['pilot'] is False
      and req['data_references']==data and req['estimated_peak_output_bytes']==plan['output_cap_bytes']==C.CAP,'ACTUAL_GENERIC16_2G_PREPARE_ONLY')
    C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==HERE_SOURCE and sys.argv==[str(HERE_SOURCE),*argv[4:]],'PRIMARY_SOURCE_FULL_ARGV_NOT_WRAPPER')
    for ref in C.sources(plan):C.need(ref in req['source_references'],'ALL_REAL_FROZEN_SOURCES_PINNED')
    review=C.meta(req['scope']['review']);C.need(review['original2000_readonly_prepare_authorized'] is True and review['native_invoke_or_new_QM_authorized'] is False,'ONLY_ZERO_INVOKE_PREPARATION')
    out=M.fresh(plan['output_directory'],'artifacts');C.need(Q.ROOT/'artifacts/pprime2000_day_v1' in out.parents,'FRESH_OWN_OUTPUT');out.mkdir(parents=True,mode=0o700)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    fixture=fixtures(out);budget=Budget(plan,proof,out);engine=None;scratch=None;guard=C.OriginalInputs.NoInvoke(old);initialized=0;closed=None
    try:
        budget.check(force=True)
        asset_bytes=0;software_specs=C.software_original_specs(context);software_frames=[]
        for ref in context['execution_asset_references']:
            if ref['path'] in software_specs:
                software_frames.append(hash_software_original(C.triple(ref),software_specs[ref['path']],budget));asset_bytes+=ref['bytes'];continue
            body=Body(C.triple(ref),budget)
            try:body.check();asset_bytes+=ref['bytes']
            finally:body.close()
        C.need(len(software_frames)==14,'ALL14_DECLARED_SOFTWARE_ORIGINALS_HASHED_NO_OMISSION')
        pairs,pair_check=C.OriginalInputs.pairs(pair_ref,budget);grouped=C.pairs_matrix(pairs)
        first=[next(p for p in grouped[mid] if p['random_order_rank']==0) for mid in sorted(grouped)];mids=set(grouped)
        per=selected_population(population[0],mids,['molecule_id','split_role','S_conformers','Sprime_conformers'],budget)
        index=selected_population(population[1],mids,['molecule_id','file_group','max_heavy_atoms','max_total_atoms'],budget)
        C.need(set(per)==mids and all(r['S_conformers']>=2 and r['Sprime_conformers']>=r['S_conformers'] for r in per.values()),'ALL_SELECTED_MIDs_ALREADY_COMPLETE_NOT_ACTIVE_FILL_OR_N1')
        C.need(set(index)==mids and all(p['source']['file_group']==index[p['molecule_id']]['file_group'] for p in pairs),'ACTUAL_ORIGINAL_SELECTED_INDEX_GROUPS')
        import pyarrow as pa,pyarrow.parquet as pq
        val=Body(val_ref,budget)
        try:validation=set(pq.read_table(BorrowedFile(val.stream),columns=['molecule_id'],use_threads=False)['molecule_id'].to_pylist());val.check()
        finally:val.close()
        C.need(len(validation)==7610,'EXACT_ORIGINAL_FULL_ROUTINE_VAL_MEMBERSHIP')
        for pair in pairs:
            mid=pair['molecule_id'];role='VAL' if mid in validation else 'TRAIN'
            C.need((per[mid]['split_role']=='TRAIN' or mid in validation) and pair['source']['effective_role']==role,'ORIGINAL_TRAIN_VAL_NOT_NEW_COMMON_ROLES')
        by_mid,frames=C.OriginalInputs.selected_conformers(sprime,first,pairs,budget)
        C.need(all(len(by_mid[mid])==int(per[mid]['Sprime_conformers']) for mid in mids),'COMPLETE_SELECTED_SPRIME_COUNTS_NOT_JUST_FIRST2')
        science=C.OriginalInputs.load_science(plan);engine,legacy,original_protocol,pilot=T.engine(context,C.meta)
        C.need(original_protocol==old,'ACTUAL_ORIGINAL_ONLY_ENGINE_PROTOCOL')
        audit_refs=[r for r in saved['outputs'] if pathlib.Path(r['path']).name=='audit_selected.parquet'];C.need(len(audit_refs)==1,'ACTUAL_ORIGINAL20_RECORD_AUDIT')
        audited=Body(C.triple(audit_refs[0]),budget)
        try:old20=pq.read_table(BorrowedFile(audited.stream),use_threads=False).to_pylist();audited.check()
        finally:audited.close()
        C.need(len(old20)==20,'EXACT_ORIGINAL20_RECORDS_NOT20_MIDs')
        parent=Q.REPO/'workflows/data_v1_final/pprime';sys.path[:0]=[str(parent),str(parent/'retention_v1')]
        import retention_policy_v1 as retention
        source_paths=retention.source_paths(C.meta(pilot['source_plan']));rows=[retention.source_audit(pair,source_paths) for pair in pairs]
        by_record={r['record_id']:r for r in rows}
        for original in old20:
            actual=by_record[original['record_id']]
            C.need(original['file_group']==actual['legacy_engine_file_group'] and original['size_stratum']==actual['size_stratum'],'ORIGINAL20_AUDIT_STRATUM_UNCHANGED')
        union=retention.selector.pilot_union(rows,[r['record_id'] for r in old20]);selected={r['record_id'] for r in union}
        membership_rows=[{'record_id':r['record_id'],'file_group':r['legacy_engine_file_group'],'size_stratum':r['size_stratum']} for r in union]
        buffer=pa.BufferOutputStream();pq.write_table(pa.Table.from_pylist(membership_rows),buffer,compression='zstd')
        # I.write serializes JSON; Parquet bytes use the original atomic Store.
        from workflows.data_v1_final.pprime.strict_numerics15_qa_v1.io import Store
        store=Store(out,C.CAP);selected_ref=store.write(out/'audit_selected_union.parquet',buffer.getvalue().to_pybytes())
        audit_ref=I.write(out/'audit_membership.json',{'schema':'WP5_STRATIFIED_RECORD_AUDIT_V1','status':'AUDIT_MEMBERSHIP_CLOSED',
          'selected_records':dict(selected_ref,rows=len(union)),'audit_policy':plan['retention_policy_reference'],'original20':audit_refs[0],
          'full12_stable_hits_plus_original20_extra_reproduction':True},budget)
        source_rows=[dict(row,retain_all_twelve_raw=row['record_id'] in selected) for row in rows];source_audit=I.write(out/'source_audit.DATA.json',source_rows,budget)
        scratch=pathlib.Path(tempfile.mkdtemp(prefix='pprime2000_readers_'+str(proof['job_id'])+'_',dir='/tmp'));orders=I.Lines(out/'orders_and_lineage.DATA.jsonl',budget);targets=I.Lines(out/'record_input_hashes.DATA.jsonl',budget)
        try:
            with guard:
                initialized+=1;engine.initialize_worker(pilot['source_plan']['path'],protocol=plan['original_protocol_reference']['path'],node_scratch_root=str(scratch),
                  audit_membership=audit_ref['path'],reproduction_package=legacy['reproduction_package']['path'])
                lmdb_frames=C.OriginalInputs.lmdb_frames(pairs,data);geometry_count=0
                for mid in sorted(grouped):
                    budget.check();values=sorted(grouped[mid],key=lambda p:p['random_order_rank']);base,provenance,ordering=C.OriginalInputs.source_native(values[0],by_mid[mid],engine,science)
                    C.need(ordering['orders']['fixed_random'][:2]==[p['conformer']['sprime_conf_idx'] for p in values],'ORIGINAL_FIXED_FIRST2_NOT_NEW_NATIVE_ORDER')
                    orders.append(dict(ordering,source_provenance=provenance,selected_physical_ids=[p['conformer']['sprime_conf_idx'] for p in values]))
                    native_rows=[(values[0],base)]
                    original=engine.NATIVE.read_native(values[1]['source']);graph=engine.source_bond_graph(original['_source_raw'],original)
                    C.need(not graph['bond_graph_issues'] and graph['bond_pairs_zero_based'] is not None,'UNCHANGED_SOURCE_GRAPH_NO_GUESS')
                    native,prov=geometry.adapt_native(original,dict(values[1],bond_pairs=graph['bond_pairs_zero_based']));native_rows.append((values[1],native))
                    C.distinct_geometry(geometry.geometry_hash(base['z'].tolist(),base['coords'].tolist()),geometry.geometry_hash(native['z'].tolist(),native['coords'].tolist()))
                    for pair,native in native_rows:
                        targets.append({'record_id':pair['record_id'],'molecule_id':mid,'random_order_rank':pair['random_order_rank'],
                          'original_pair_sha256':hashlib.sha256(O_CANONICAL(pair)).hexdigest(),'physical_id':pair['conformer']['sprime_conf_idx'],
                          'geometry_sha256':geometry.geometry_hash(native['z'].tolist(),native['coords'].tolist()),'atom_count':len(native['z']),
                          'hashes':input_hashes(engine,native,pair,old,new),'native_invoke_calls':0});geometry_count+=1
                C.OriginalInputs.check_lmdb_frames(lmdb_frames);closed=engine.close_worker();engine=None
            C.need(guard.attempts==0 and geometry_count==2000,'EXACT2000_SOURCE_READBACK_AND_ZERO_INVOKE');order_ref=orders.close();target_ref=targets.close()
        finally:orders.close();targets.close()
        budget.check(dispatch=False,force=True)
        result={'schema':'PPRIME_ORIGINAL2000_ZERO_INVOKE_PREPARED_V1','status':'ACTUAL2000_INPUTS_CLOSED_NOT_QM_AUTHORITY','job_id':str(proof['job_id']),
          'uid':1278,'node':req['node'],'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),'fixtures_reference':fixture,
          'original_prepared_reference':plan['original_prepared_reference'],'original_pairs_reference':pair_ref,'pair_whole_SHA_verification':pair_check,
          'MIDs':1000,'UFF_geometries':2000,'maximum_formal_native_calls':24000,'all12_tasks':list(C.O.TASKS),'role_counts':dict(collections.Counter(p['source']['effective_role'] for p in first)),
          'no_atom_count_exclusion':True,'over80_atoms_retained':sum(p['source']['total_atoms']>80 for p in first),'full_selected_Sprime_count_checked':True,
          'original5_source_frames':frames,'original_selected_LMDB_frames':lmdb_frames,'execution_assets_whole_SHA_count':len(context['execution_asset_references']),
          'execution_assets_whole_SHA_bytes':asset_bytes,'software_original_alias_FD_verification':software_frames,
          'software_original_count':len(software_frames),'ordinary_Body_asset_count':len(context['execution_asset_references'])-len(software_frames),
          'orders_and_lineage_reference':order_ref,'record_input_hashes_reference':target_ref,
          'audit_membership_reference':audit_ref,'stable_source_audit_reference':source_audit,'union_full12_raw_records':len(union),'stable_rates':retention.rates(rows),
          'original_protocol_reference':plan['original_protocol_reference'],'candidate_protocol_reference':plan['candidate_protocol_reference'],'protocol_diff':diff,
          'original_initialize_calls':initialized,'candidate_initialize_calls':0,'native_invoke_attempts':guard.attempts,'new_QM_UFF_calls':0,'engine_close':closed,
          'scientific_PASS':False,'production_precision_choice_approved':False,'full_release':False,'production_once_written':False,'proposal':C.proposal()}
        prepared_reference=Q.write_new(out/'prepared2000.json',result)
        # A pure producer header: counts/locators only; scientific indexes remain DATA.
        header={'schema':'PPRIME_ORIGINAL2000_ZERO_INVOKE_PURE_CLOSURE_HEADER_V1',
          'status':'ACTUAL_PREPARED_OUTPUT_CLOSED_ACCOUNTING_PENDING_NOT_NATIVE_AUTHORITY',
          'prepared_reference':prepared_reference,'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],
          'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),'fixtures_reference':fixture,
          'MIDs':1000,'UFF_geometries':2000,'maximum_formal_native_calls':24000,'all12_tasks':list(C.O.TASKS),
          'original_protocol_reference':plan['original_protocol_reference'],'candidate_protocol_reference':plan['candidate_protocol_reference'],
          'source_context_reference':plan['source_context_reference'],'original_pairs_reference':pair_ref,
          'orders_and_lineage_reference':order_ref,'record_input_hashes_reference':target_ref,
          'audit_membership_reference':audit_ref,'stable_source_audit_reference':source_audit,
          'execution_assets_whole_SHA_count':len(context['execution_asset_references']),'software_original_count':len(software_frames),
          'original_initialize_calls':initialized,'candidate_initialize_calls':0,'native_invoke_attempts':guard.attempts,
          'new_QM_UFF_calls':0,'production_once_written':False,'production_precision_choice_approved':False,
          'scientific_PASS':False,'actual_terminal_accounting_required':True,'scientific_ids_coordinates_and_values_in_header':False}
        Q.write_new(out/'prepared2000_closure_header.json',header);return 0
    except BaseException as exc:
        I.write(out/'failure.DATA.json',{'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),'native_invoke_attempts':guard.attempts,
          'new_QM_UFF_calls':0,'scientific_PASS':False,'partial_preserved':True},budget);raise
    finally:
        if engine is not None:engine.close_worker()
        if scratch is not None and scratch.exists() and not any(scratch.iterdir()):scratch.rmdir()

O_CANONICAL=C.O.canonical;HERE_SOURCE=C.HERE/'prepare.py'
if __name__=='__main__':raise SystemExit(main())
