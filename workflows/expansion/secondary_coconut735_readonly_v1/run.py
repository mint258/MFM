"""One existing735 read-only evidence audit; no strict5/candidate/READY writes."""
import argparse,collections,concurrent.futures as cf,contextlib,hashlib,io,json,multiprocessing as mp,os,re,sqlite3,stat,time,unittest
from pathlib import Path
from . import contracts as C
from secondary_coconut_strict5_day_v1 import kernel as K,io as I
from secondary_coconut_identity_norm_profile_v1.runtime import Budget

def physical(locator):
    t,b,o=locator['source_table'],locator['copy_block'],locator['source_row_ordinal']
    C.need(t in ('molecules','entries','structures') and type(b) is int and b>0 and type(o) is int and o>=0,'EXACT_ORIGINAL_TABLE_BLOCK_ORDINAL_NO_RENUMBERING')
    return t,b,o
def source_hash(src):
    C.need(type(src['source_offset']) is int and src['source_offset']>=0 and type(src['source_bytes']) is int and src['source_bytes']>0
      and re.fullmatch('[0-9a-f]{64}',src['source_row_sha256']) is not None,'POSITIVE_ORIGINAL_SQL_ROW_OFFSET_SIZE_SHA_NOT_INVENTED')
def selected_parquet(ref,keys,budget,*,norm,expected_rows=None):
    """Whole producer SHA first, then only RGs intersecting requested ordinals."""
    import pyarrow.parquet as pq
    wanted=set(keys);found=set();names=['source_table','copy_block','source_row_ordinal','observation_json'] if norm else list(C.OLD.RAW_COLUMNS)
    with I.held(ref,budget) as fd:
        with os.fdopen(os.dup(fd),'rb') as stream:
            pf=pq.ParquetFile(stream,pre_buffer=False)
            try:
                C.need(set(names)==set(pf.schema_arrow.names),'EXACT_CLOSED_NORM_OR_RAW_IDENTITY_SCHEMA')
                if expected_rows is not None:C.need(pf.metadata.num_rows==expected_rows,'ACTUAL_PRODUCER_CLOSED_PART_FULL_ROW_COUNT')
                col=pf.schema_arrow.get_field_index('source_row_ordinal')
                for group in range(pf.num_row_groups):
                    stats=pf.metadata.row_group(group).column(col).statistics
                    if stats is not None and stats.has_min_max and not any(stats.min<=k[2]<=stats.max for k in wanted-found):continue
                    for batch in pf.iter_batches(batch_size=1,row_groups=[group],columns=names,use_threads=False):
                        budget.dispatch_check();C.need(batch.nbytes<=128<<20,'COMPLETE_SINGLE_ROW_BOUND_NO_TRUNCATION');row=batch.to_pylist()[0];key=physical(row)
                        if key not in wanted:continue
                        C.need(key not in found,'NO_DUPLICATE_ORIGINAL_PHYSICAL_LOCATOR');found.add(key)
                        if norm:
                            observation=json.loads(row['observation_json']);src=observation['source']
                            C.need(physical(src)==key,'ORIGINAL_OUTER_INNER_NORM_LOCATOR');source_hash(src);yield key,observation
                        else:source_hash(row);yield key,row
            finally:pf.close()
    C.need(found==wanted,'ALL_AND_ONLY_REQUESTED_ORIGINAL_LOCATORS_FOUND')
def no_sidecars(path):
    C.need(not any(Path(str(path)+suffix).exists() for suffix in ('-wal','-shm','-journal')),'CLOSED_IMMUTABLE_SQLITE_NO_SIDECARS_REQUIRED')
def observed_frame(s):return {'bytes':s.st_size,'uid':s.st_uid,'nlink':s.st_nlink,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns}
def same_expected(s,expected):
    C.need(stat.S_ISREG(s.st_mode) and all(observed_frame(s)[k]==expected[k] for k in observed_frame(s)),'EXACT_ROOT_LSTAT_CLOSED_INDEX_FRAME_DEVICE_NOT_COMPARED_ACROSS_MOUNTS')
@contextlib.contextmanager
def bootstrap_index(authority,budget):
    path=Path(authority['fixed_index_path']);root=Path(authority['fixed_output_root'])
    C.need(path==root/'identity_links.sqlite' and C.ROOT/'artifacts' in root.parents and not any(p.is_symlink() for p in (path,*path.parents)),'ONLY_ROOT_FIXED_CLOSED_INDEX_PATH')
    no_sidecars(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd);same_expected(before,authority['actual_lstat']);h=hashlib.sha256();n=0
        while True:
            budget.dispatch_check();block=os.read(fd,1<<20)
            if not block:break
            h.update(block);n+=len(block)
        C.need(n==before.st_size and I.frame(before)==I.frame(os.fstat(fd))==I.frame(path.lstat()),'FIRST_CPU_WHOLE_FD_SHA_EOF_AND_FRAME_REQUIRED')
        ref={'path':str(path),'bytes':n,'sha256':h.hexdigest()};no_sidecars(path)
        db=sqlite3.connect('file:/proc/self/fd/'+str(fd)+'?mode=ro&immutable=1',uri=True)
        try:yield db,ref,{'current_device':before.st_dev,'authority_device_provenance_only':authority['actual_lstat']['device'],'first_hash_performed_in_this_CPU':True}
        finally:db.close();C.need(I.frame(before)==I.frame(os.fstat(fd))==I.frame(path.lstat()),'FIXED_INDEX_STABLE_THROUGH_READONLY_QUERIES');no_sidecars(path)
    finally:os.close(fd)
@contextlib.contextmanager
def producer_sqlite(ref,budget):
    no_sidecars(ref['path'])
    with I.held(ref,budget) as fd:
        db=sqlite3.connect('file:/proc/self/fd/'+str(fd)+'?mode=ro&immutable=1',uri=True)
        try:yield db
        finally:db.close();no_sidecars(ref['path'])
def a_row(db,src):
    t,b,o=physical(src);rows=db.execute('SELECT id,identity_fields_json FROM records WHERE source_table=? AND copy_block=? AND row_ordinal=?',(t,b,o)).fetchall()
    C.need(len(rows)==1 and rows[0][1]==src['identity_fields_json'],'EXACT_A_PHYSICAL_PRIMARY_KEY_ORIGINAL_FIELDS_JSON')
    return json.loads(rows[0][1])
def replay_init(plan,root):
    # Preserve RDKit diagnostics as DATA, including native stderr, never QA text.
    folder=Path(root)/'worker_logs_DATA';folder.mkdir(exist_ok=True)
    fd=os.open(folder/(str(os.getpid())+'.DATA.log'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    os.dup2(fd,1);os.dup2(fd,2);os.close(fd);K.configure(plan)
def replay_batch(items):
    values=[]
    for original,observation,formulas,parent in items:
        try:result=K.project(observation,formulas,parent);error=None
        except Exception as exc:result=None;error={'type':type(exc).__name__,'message':str(exc)}
        values.append({'original_unresolved':original,'norm_observation':observation,'original_formula_rows':formulas,'original_parent_payload':parent,
          'replay':result,'replay_error':error,'original_UNKNOWN_unchanged':True,'new_authoritative_keys':False,'strict5_written':False,'worker_pid':os.getpid()})
    return values
def reason_summary(value):
    original=value['original_unresolved'];out={'source_table':original['locator']['source_table'],'FK_state':original['FK_state'],
      'field_availability':original['field_availability'],'replay_error_type':None if value['replay_error'] is None else value['replay_error']['type'],
      'replay_covered':None,'evidence_reason_tokens':[]}
    if value['replay'] is not None:
        result=value['replay'];out['replay_covered']=result['covered'];out['replay_FK_state']=result['FK_state']
        out['original_FK_or_field_availability_changed_in_replay']=result['FK_state']!=original['FK_state'] or result['field_availability']!=original['field_availability']
        out['evidence_reason_tokens']=[str(e.get('result',{}).get('reason','PARENT_ASSOCIATION_NO_GRAPH_IDENTITY')) for e in result['evidence']]
    return out
def opaque_row(fd,source,budget,root,sequence):
    source_hash(source);n=source['source_bytes'];C.need(n<=16<<20,'OPAQUE_ROW_OVER16M_RETAIN_LOCATOR_NO_PREFIX_READ');budget.dispatch_check()
    raw=os.pread(fd,n,source['source_offset']);C.need(len(raw)==n and hashlib.sha256(raw).hexdigest()==source['source_row_sha256'],'EXACT_ORIGINAL_SQL_OFFSET_BYTES_ROW_SHA')
    path=root/('row_%06d.DATA.raw'%sequence);budget.capacity(len(raw))
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return I.pin(path)
def fixtures(root,plan):
    from . import test_v1
    from secondary_coconut_identity_norm_profile_v1.run import observe_environment
    environment=observe_environment();C.need(environment['actual_versions']==C.OLD.ENV,'ACTUAL_ORIGINAL_ALPHA_ENVIRONMENT_BEFORE_SYNTHETIC_OR_SCI_DATA')
    test_v1.ROOT=root/'source3_fixture_io';test_v1.ROOT.mkdir();K.configure(plan)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries);C.need(suite.countTestCases()==3,'EXACT3_MEANINGFUL_PREFLIGHT_METHODS')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    report={'tests':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),'skips':len(result.skipped),'expected_failures':len(result.expectedFailures),
      'unexpected_successes':len(result.unexpectedSuccesses),'transcript':stream.getvalue(),'before_SCI_DATA_Budget_or_index_hash':True,
      'actual_environment':environment,'new_QM_UFF_network_calls':0,'not_actual735_or_science_acceptance':True}
    C.write_new(root/'source3.json',report);C.need(result.wasSuccessful() and result.testsRun==3 and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses),'SOURCE3_FAILED_NO_REAL_DATA')
    return C.pin(root/'source3.json')
def execute(plan,proof,root,budget,gate):
    context,data=C.parents(plan);originals=list(I.read_jsonl(plan['unknown_locator_reference'],budget));C.need(len(originals)==735,'EXACT735_UNKNOWN_LOCATOR_ROWS')
    parts={p['reference']['path']:p for p in context['parts']}
    groups=collections.defaultdict(dict);allkeys=set()
    for row in originals:
        loc=row['locator'];key=physical(loc);C.need(key not in allkeys and row['reason']=='NO_ORIGINAL_FULL_KEY_OR_TRUSTWORTHY_NATIVE_COMPOSITION','735_UNIQUE_OLD_UNRESOLVED_PHYSICAL_ROWS')
        allkeys.add(key);path=loc['reference']['path'];C.need(path in parts and C.triple(loc['reference'])==parts[path]['reference'] and key[0]==parts[path]['table'],'EXACT_PRODUCER_NORM_REFERENCE_NOT_PATH_ONLY')
        group=groups[path];C.need(key not in group,'NO_DUPLICATE_UNKNOWN');group[key]=row
    C.need(set(groups)<=set(parts),'ONLY_PRODUCER_CLOSED_NORM_PARTS')
    details=I.Jsonl(root/'diagnosis735.DATA.jsonl',budget);associations=I.Jsonl(root/'associated_original_source_rows.DATA.jsonl',budget)
    counts=collections.Counter();reasons=collections.Counter();availability=collections.Counter();source_rows=[];done=0;errors=[];deferred_ref=None;opaque_count=opaque_bytes=0;opaque_stop=None
    ddl_structures=next(t for t in context['DDL']['tables'] if t['table_identifiers'][-1]=='structures')
    C.write_new(root/'observed_structures_DDL_metadata.json',{'schema_source_reference':context['DDL_reference'],'actual_table_identifiers':ddl_structures['table_identifiers'],
      'actual_columns':ddl_structures['columns'],'columns_selected_by_name_guess':False,'structure_payload_decoded':False})
    ctx=mp.get_context('spawn');pending=collections.deque();mids=set();structure_keys=set()
    def collect():
        nonlocal done
        future,n=pending.popleft();values=future.result();C.need(len(values)==n,'EXACT_BOUNDED_BATCH_RETURN')
        for value in values:
            details.add(value);qa=reason_summary(value);counts['table/'+qa['source_table']]+=1;counts['FK/'+qa['FK_state']]+=1
            counts['kernel_exception']+=qa['replay_error_type'] is not None;counts['replay_covered_candidate_only']+=qa['replay_covered'] is True
            counts['replay_FK_or_availability_disagreement']+=qa.get('original_FK_or_field_availability_changed_in_replay',False)
            for token in qa['evidence_reason_tokens']:reasons[token]+=1
            availability[json.dumps(qa['field_availability'],sort_keys=True,separators=(',',':'))]+=1;done+=1
    try:
        with bootstrap_index(context['index_authority'],budget) as (closed,ref,frame),producer_sqlite(context['A_index'],budget) as native:
            deferred_ref=ref;C.write_new(root/'actual_first_CPU_index_reference.json',{'reference':ref,'metadata_authority_reference':plan['fixed_index_authority_reference'],**frame,
              'scientific_acceptance':False,'source_metadata_or_old_DB_changed':False})
            with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=replay_init,initargs=(plan,str(root))) as pool:
                items=[]
                for path,wanted in groups.items():
                    for key,observation in selected_parquet(parts[path]['reference'],wanted,budget,norm=True,expected_rows=parts[path]['rows']):
                        original=wanted[key];src=observation['source'];fields=a_row(native,src)
                        C.need(fields['id']==original['original_id'] and physical(src)==key,'EXACT735_NATIVE_ID_AND_ROW_NOT_NAME_MATCH')
                        if key[0]=='molecules':
                            formulas=[json.loads(r[0]) for r in closed.execute('SELECT payload FROM properties WHERE mid=?',(fields['id'],))];parent=None;mid=fields['id']
                        else:
                            formulas=[];mid=fields['molecule_id'];parentrow=closed.execute('SELECT payload FROM molecules WHERE mid=?',(mid,)).fetchone() if mid is not None else None;parent=json.loads(parentrow[0]) if parentrow else None
                        C.need(len(json.dumps(formulas).encode())<=8<<20,'COMPLETE_ORIGINAL_FORMULA_LIST_BOUND_NOT_TRUNCATED')
                        if mid is not None:mids.add(mid)
                        source_rows.append(src);items.append((original,observation,formulas,parent))
                        if len(items)==16:
                            budget.dispatch_check();pending.append((pool.submit(replay_batch,items),len(items)));items=[];budget.workers=list(pool._processes.values())
                            if len(pending)>=32:collect()
                if items:pending.append((pool.submit(replay_batch,items),len(items)));budget.workers=list(pool._processes.values())
                while pending:collect()
            C.need(done==735,'ALL735_DIAGNOSTIC_RESULTS_NO_DOWNSIZE')
            # Exact declared original links are evidence, never identity aliases.
            for mid in sorted(mids):
                for row in native.execute("SELECT source_table,copy_block,row_ordinal,identity_fields_json FROM records WHERE source_table='molecules' AND id=?",(mid,)):
                    associations.add({'basis':'EXACT_ORIGINAL_MOLECULE_ID_NOT_GRAPH_EQUIVALENCE','table':row[0],'copy_block':row[1],'source_row_ordinal':row[2],'original_fields_json':row[3]})
            if mids:
                placeholders=','.join('?' for _ in mids)
                for row in native.execute("SELECT copy_block,row_ordinal,id,molecule_id FROM records WHERE source_table='structures' AND molecule_id IN ("+placeholders+")",tuple(sorted(mids))):
                    if len(structure_keys)>=4096:opaque_stop='STRUCTURE_ROW_CANDIDATE_LIMIT_NOT_ALL_STRUCTURE_COVERAGE';break
                    structure_keys.add(('structures',row[0],row[1]));associations.add({'basis':'EXACT_ORIGINAL_STRUCTURE_FK_NOT_OBSERVED_SAME_GRAPH','table':'structures','copy_block':row[0],'source_row_ordinal':row[1],'original_structure_id':row[2],'original_molecule_id':row[3]})
        # SQL is not executed/parsed here. Original row bytes are opaque DATA.
        if structure_keys:
            for _,row in selected_parquet(context['structures'],structure_keys,budget,norm=False):source_rows.append(row)
        rawroot=root/'opaque_SQL_source_rows_DATA';rawroot.mkdir();opaque=I.Jsonl(root/'opaque_SQL_source_rows_manifest.DATA.jsonl',budget)
        try:
            with I.held(context['SQL'],budget) as fd:
                seen=set()
                for src in source_rows:
                    key=physical(src)
                    if key in seen:continue
                    seen.add(key)
                    if opaque_count>=4096 or opaque_bytes+src['source_bytes']>64<<20:opaque_stop='OPAQUE_CAPTURE_BOUNDED_LIMIT_NOT_SOURCE_EXCLUSION';break
                    if src['source_bytes']>16<<20:
                        opaque.add({'source':src,'state':'ORIGINAL_ROW_OVER16M_LOCATOR_RETAINED_BYTES_NOT_TRUNCATED'});continue
                    r=opaque_row(fd,src,budget,rawroot,opaque_count);opaque.add({'source':src,'opaque_original_row_reference':r,'field_values_decoded':False,'not_graph_identity_acceptance':True})
                    opaque_count+=1;opaque_bytes+=r['bytes']
        finally:opaque_ref=opaque.close()
    except RuntimeError as exc:
        if not budget.stop:raise
        while pending:collect()
        errors.append({'type':type(exc).__name__,'resource_stop':str(exc),'partial_preserved':True})
    finally:
        detail_ref=details.close();association_ref=associations.close()
    complete=done==735 and not errors
    summary={'schema':'COCONUT735_READONLY_DIAGNOSIS_SUMMARY_V1','actual_source_parent_job_id':'1885088','diagnostic_rows':done,'expected_rows':735,
      'diagnosis_complete':complete,'counts':dict(counts),'original_evidence_reason_token_counts':dict(reasons),'field_availability_counts':dict(availability),
      'diagnosis_DATA_reference':detail_ref,'associated_source_DATA_reference':association_ref,'opaque_SQL_DATA_reference':locals().get('opaque_ref'),
      'actual_first_CPU_fixed_index_reference':deferred_ref,'opaque_rows_captured':opaque_count,'opaque_bytes_captured':opaque_bytes,'opaque_capture_bound_state':opaque_stop,
      'original_UNKNOWN735_not_upgraded':True,'graph_identity_acceptance':False,'new_full_key_computations':0,'identity_norm_recomputed':False,
      'network_QM_UFF_calls':0,'strict5_candidate_READY_or_pool_release':False,'errors':errors}
    C.write_new(root/'summary.json',summary);C.write_new(root/'receipt.json',{'schema':'COCONUT735_READONLY_DIAGNOSIS_RECEIPT_V1',
      'status':'EXACT735_EXISTING_EVIDENCE_DIAGNOSED_NOT_IDENTITY_ACCEPTANCE' if complete else 'PARTIAL_DIAGNOSIS_HOLD_ORIGINAL_UNKNOWNS_PRESERVED',
      'job_id':str(proof['job_id']),'uid':1264,'endpoint':C.q.ENDPOINT,'node':plan['node'],'plan_reference':C.pin(plan['plan_path']),
      'startup_proof_reference':plan['startup_proof_reference'],'source3_reference':gate,'summary_reference':C.pin(root/'summary.json'),
      'original_parent_chain':plan['strict_parent'],'runtime':budget.receipt(),'new_QM_UFF_network_calls':0,'original_strict5_outputs_changed':False,'READY':False})
    return 0 if complete else 3
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan,proof=C.startup(Path(a.plan),Path(a.startup_proof),__file__);root=C.literal(plan['output_directory']);C.need(not root.exists(),'FRESH_735_DIAGNOSIS_OUTPUT');root.mkdir(parents=True,mode=0o700)
    gate=fixtures(root,plan);budget=Budget(plan,proof,root);budget.thread.start()
    try:plan['plan_path']=a.plan;plan['startup_proof_reference']=C.pin(a.startup_proof);return execute(plan,proof,root,budget,gate)
    except BaseException as exc:
        import traceback
        C.write_new(root/'failure.DATA.json',{'error_type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'all_old_unknowns_and_partials_preserved':True,'no_retry_or_identity_acceptance':True});raise
    finally:budget.close()
if __name__=='__main__':raise SystemExit(main())
