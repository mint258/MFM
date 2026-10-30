"""New-Parent selected typed coverage; preserve every original failed origin.

Only closed windows explicitly bound by Root are read. No raw numeric label is
parsed/reprojected, no old SQLite/ledger/book is modified, and no missing part
or unknown ticket is interpreted as an accepted source record.
"""
import collections,hashlib,json,pathlib,sqlite3,struct
from . import contract as C,io as I,bindings as B
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import contract as Legacy
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import sqlite_ro,lookup_batch,identity
from workflows.data_v1_final.labels.common_train_normalization_day_v1.audit import quality_fields
from workflows.data_v1_final.labels.payload_audit_v1.payload import STRUCTURAL

def cohort(prefix,old):
    import pyarrow.parquet as pq
    pre=I.load_data(prefix['preselection_reference'],8<<20)
    C.need(pre['schema']=='EXISTING_COMPLETE_SPRIME_PILOT_PRESELECTION_V1' and pre['pilot_ready_scalar_only']is True
        and pre['pilot_counts']==C.PILOT_COUNTS and pre['seed']==20261025 and pre['final_Common']is False,
        'TRUE_ORIGINAL55K_SCALAR_COHORT_NOT_LABEL_SUCCESS_OR_FINAL_COMMON')
    values={}
    for name in ('pilot55k','complete_old_mother','diagnostic20k_molecule_preselection'):
        ref=pre['tables'][name];I.allow(ref,origin=old['output_directory']);values[name]=pq.read_table(I.require(ref)).to_pylist()
    selected={r['molecule_id']:r for r in values['pilot55k']};C.need(len(selected)==55000,'EXACT_UNIQUE55K_MOLECULAR_IDS')
    result={r['molecule_id']:r for r in values['complete_old_mother'] if r['molecule_id'] in selected}
    C.need(len(result)==55000 and collections.Counter(r['effective_role'] for r in result.values())==C.PILOT_COUNTS,
        'OLD_COMPLETE_MOTHER_AND_FROZEN_ROUTINE_VAL_COUNTS_NOT_RECORD_COUNTS')
    for mid,r in result.items():
        C.need(r['scalar_complete_old_Sprime']is True and r['effective_role']==selected[mid]['effective_role']
            and r['selection_rank']==selected[mid]['selection_rank'],'SAME_FULL_MOTHER_FIXED_SEED_PRESELECTION')
    diagnostic={r['molecule_id'] for r in values['diagnostic20k_molecule_preselection']}
    C.need(len(diagnostic)==20000,'UNCHANGED_FULL_MOTHER20K_DIAGNOSTIC_MID_SELECTION')
    return pre,result,diagnostic

def field_counts(stats,entries):
    """Same original masks and structural reason enum, no new mask formula."""
    for e in entries:
        fid=str(e['field_id']);s=stats[fid];s['records']+=1
        s['source_valid_records']+=bool(any(e['source_value_mask']));s['final_valid_records']+=bool(any(e['value_mask']))
        s['source_masked_records_any_leaf']+=not e['source_value_mask'] or not all(e['source_value_mask'])
        s['masked_records_any_leaf']+=not e['value_mask'] or not all(e['value_mask'])
        s['newly_masked_records']+=any(a and not b for a,b in zip(e['source_value_mask'],e['value_mask']))
        # source_value_mask appends the original component/parser reason itself.
        # The stored SR prefix therefore exactly retains evaluate.observations'
        # structural predicate, including the original reason precedence.
        s['new_payload_structural_invalid_records']+=any(r.split(':',1)[0] in STRUCTURAL for r in e['source_reasons'])

def build(plan,proof,root,budget,members):
    import pyarrow as pa,pyarrow.parquet as pq
    root=pathlib.Path(root);root.mkdir();parts_dir=root/'parts';parts_dir.mkdir()
    review=C.projection_origins(plan);book=I.load_data(plan['source_inventory_reference'],2<<20);byfile={r['file_id']:r for r in book['files']}
    fields=I.load_data(plan['field_map_reference'],2<<20);byfield={r['field_id']:r for r in fields};C.need(set(byfield)==set(range(146)),'ORIGINAL146_FIELDS_NO_PILOT_ID_REASSIGNMENT')
    canonical=sqlite_ro(I.require(plan['canonical_index']));frame=identity(plan['canonical_index']['path']);wanted={};group_records=collections.Counter()
    # Read only canonical identity metadata once, not the raw label values.
    cur=canonical.execute('SELECT record_id,molecule_id FROM records ORDER BY record_ordinal');batch=[]
    while True:
        rows=cur.fetchmany(8192)
        if not rows:break
        budget.check();ids=[rid for rid,mid in rows if mid in members]
        owners=lookup_batch(canonical,ids) if ids else {}
        for rid,owner in owners.items():
            C.need(owner['molecule_id'] in members and owner['new_role']==members[owner['molecule_id']]['effective_role'],
                'FULL_ORIGINAL_ROLES_PRESERVED_NO_VAL_FULL_TRAIN_LEAK')
            C.need(rid not in wanted,'UNIQUE_ORIGINAL_NATIVE_RECORD_ID');wanted[rid]=owner;group_records[owner['job_id']]+=1
    expected=sum(r['S_conformers'] for r in members.values());C.need(len(wanted)==expected,'EVERY_ORIGINAL_N_PM7_RECORD_OF_SELECTED_MIDS')
    actual_mid=collections.Counter(r['molecule_id'] for r in wanted.values())
    C.need(set(actual_mid)==set(members) and all(actual_mid[mid]==r['S_conformers'] for mid,r in members.items()),'WHOLE_MOLECULE_COUNTS_NOT_FIRST_RECORDS_OR_CONFORMER_SUBSAMPLE')
    pointers={};formal=pq.ParquetFile(I.require(plan['formal_record_index_reference']))
    try:
        for batch in formal.iter_batches(batch_size=8192,columns=['record_id','molecule_id','record_payload_sha256','total_atoms'],use_threads=False):
            budget.check()
            for row in batch.to_pylist():
                rid=row['record_id']
                if rid in wanted:
                    C.need(rid not in pointers and row['molecule_id']==wanted[rid]['molecule_id'] and row['total_atoms']==wanted[rid]['total_atoms'],'EXACT_FORMAL_POINTER_OWNER_NOT_GUESSED_ROW')
                    pointers[rid]=row
    finally:formal.close()
    C.need(set(pointers)==set(wanted),'ALL_SELECTED_FORMAL_SOURCE_PAYLOAD_SHA_POINTERS')
    db=sqlite3.connect(root/'numeric_catalog.sqlite');db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA cache_size=-16384')
    db.executescript('CREATE TABLE parts(file INTEGER,lo INTEGER,hi INTEGER,task INTEGER,kind TEXT,ref TEXT,window TEXT,parent TEXT,PRIMARY KEY(file,lo,task));'
        'CREATE TABLE base(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,numbers BLOB,meta TEXT,owner_sha BLOB,usable INTEGER);'
        'CREATE TABLE selected(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,mid TEXT,job TEXT,role TEXT,owner TEXT,seen INTEGER DEFAULT 0);')
    db.executemany('INSERT INTO selected(ordinal,rid,mid,job,role,owner) VALUES(?,?,?,?,?,?)',[(o['record_ordinal'],rid,o['molecule_id'],o['job_id'],o['new_role'],K.canonical(o).decode()) for rid,o in wanted.items()]);db.commit()
    stats=collections.defaultdict(collections.Counter);origins=[];old_parts=[];new_parts=[];windows_seen=set();base_rows=task_rows=0;sequence=0
    try:
        for origin in review['projection_origins']:
            manifest_ref=origin['manifest_reference'];m=I.load_data(manifest_ref,512<<20);oldroot=pathlib.Path(origin['parts_output_root'])
            roots=[pathlib.Path(r) for r in origin.get('parts_output_roots',[str(oldroot)])]
            C.need(str(m['job_id'])==str(C.meta(origin['proof_reference'])['job_id']),'EXACT_MANIFEST_PRODUCING_ACTUAL_PARENT_NOT_OLD_PART_PARENT_ALIAS')
            if m.get('old_actual_failed_accounting_reference') is not None:
                historical=m['old_actual_failed_accounting_reference'];C.need(historical in origin.get('historical_parent_evidence_references',[]),'PRESERVE_ADOPTED_OLD_FAILED_PART_PARENT_AUTHORITY')
                account=C.meta(historical);C.need(account['query_returncode']==0 and account['raw_sacct_reference']in origin['historical_parent_evidence_references'],'TRUE_OLD_FAILED_PARENT_RAW_EVIDENCE_PRESERVED')
            C.need(m['schema']==Legacy.BATCH and m['status'] in (
                'CLOSED_WINDOWS_ACTUAL_PARENT_ACCOUNTING_REQUIRED','DAY_INTERNAL_COMMITTED_WINDOWS_NOT_CHILD_C0','ROOT_ADOPTED_FAILED_DAY_CLOSED_WINDOWS_CURRENT_PARENT_VERIFIED')
                and not(m['errors'] or m['quality_hold_fields'] or m['unpublished_tickets']),'ONLY_ACTUAL_CLEAN_COMMITTED_WINDOWS_NOT_ACCEPTANCE_OF_FAILED_PARENT')
            oldcfg=I.load_data(m['config'],8<<20)
            for key in ('canonical_index','field_map_reference','source_inventory_reference','logical_group_plan_reference'):
                C.need(oldcfg[key]==plan[key],'EXACT_INHERITED_NUMERIC_SOURCE_AUTHORITY:'+key)
            origins.append({'manifest_reference':manifest_ref,'parts_output_root':str(oldroot),'actual_parent_state':origin['actual_parent_state'],
                'accounting_reference':origin['accounting_reference'],'raw_reference':origin['raw_reference'],'old_parent_C0_asserted':False})
            for wr in m['verified_window_receipts']:
                budget.check();C.need(wr['path'] not in windows_seen,'DUPLICATE_WINDOW_HISTORY_NO_SILENT_DEDUP');windows_seen.add(wr['path'])
                owner_root=next((r for r in roots if r in pathlib.Path(wr['path']).parents),None);C.need(owner_root is not None,'WINDOW_UNDER_EXPLICIT_REVIEWED_ACTUAL_PART_PARENT_ROOT')
                I.allow(wr,origin=owner_root);window=I.load_data(wr,16<<20);fid=window['file_id'];source=byfile[fid]
                C.need(window['schema']=='COMPACT_NUMERIC_PHYSICAL_WINDOW_V1' and C.reference(window['source_reference'])==C.reference(source)
                    and window['all_part_reopen_bits_verified']is True,'EXACT_ORIGINAL_SOURCE_WINDOW_AND_PART_READBACK_CHAIN')
                lo,hi=window['physical_row_lo'],window['physical_row_hi']
                for part in window['parts']:
                    pr=part['reference'];C.need(pathlib.Path(pr['path']).parent==owner_root/'parts','ONLY_EXACT_BOUND_OLD_COMMITTED_PART')
                    I.allow(pr,origin=owner_root);path=I.require(pr);before=identity(path);src=pq.ParquetFile(path);digest=hashlib.sha256();rows=0;selected_part=None
                    try:
                        C.need(src.schema_arrow.equals(K.schema(pa),check_metadata=False),'EXACT_ORIGINAL_BINARY_TYPED_CACHE_SCHEMA')
                        # The full old part's SHA and stored stream digest are
                        # checked. Only selected rows are decoded or copied.
                        for batch in src.iter_batches(batch_size=128,use_threads=False):
                            budget.check()
                            for row in batch.to_pylist():
                                rows+=1;digest.update(row['view_sha256']);owner=wanted.get(row['record_id'])
                                if owner is None:continue
                                K.validate_row_buffers(row)
                                C.need(K.row_signature(row)==row['view_sha256'] and row['file_id']==fid and lo<=row['physical_row']<hi
                                    and K.owner_signature(owner)==row['owner_sha256'] and owner['record_ordinal']==row['record_ordinal']
                                    and owner['job_id']==source['source_job_id'] and B.ROLES[owner['new_role']]==row['role_code'],
                                    'SELECTED_ORIGINAL_OWNER_ROLE_SOURCE_ROW_AND_F64_BINARY_BITS')
                                task=row['task_code'];bit=1<<(14 if row['row_kind']=='base' else task)
                                C.need((row['row_kind']=='base' and task==255) or (row['row_kind']=='task' and type(task)is int and 0<=task<14),'ORIGINAL_BASE_OR_TASK_CODES')
                                old_seen=db.execute('SELECT seen FROM selected WHERE ordinal=?',(row['record_ordinal'],)).fetchone()[0]
                                C.need(not old_seen&bit,'DUPLICATE_SELECTED_RECORD_TASK_OR_BASE');db.execute('UPDATE selected SET seen=? WHERE ordinal=?',(old_seen|bit,row['record_ordinal']))
                                if row['row_kind']=='base':
                                    pool=[struct.unpack_from('<d',row['base_f64'],i)[0] for i in range(0,len(row['base_f64']),8)];g=B.decode(row['base_json'],pool);z=g['atomic_numbers']
                                    usable=(type(z)is list and len(z)==owner['total_atoms'] and all(type(v)is int and 1<=v<=118 for v in z)
                                        and hashlib.sha256(b''.join(struct.pack('<q',v) for v in z)).hexdigest()==g['native_atom_order_sha256']
                                        and g['source_payload_sha256']==pointers[row['record_id']]['record_payload_sha256'] and g['geometry_status']=='ORIGINAL_PM7_GEOMETRY')
                                    C.need(usable,'REAL_SELECTED_SOURCE_Z_PAYLOAD_AND_ATOM_ORDER_NOT_UNKNOWN_FIT')
                                    db.execute('INSERT INTO base VALUES(?,?,?,?,?,?)',(row['record_ordinal'],row['record_id'],b''.join(struct.pack('<q',v) for v in z),row['base_json'],row['owner_sha256'],1));base_rows+=1
                                else:
                                    entries=K.unpack_entries(row,byfield);mask=K.binary_json_loads(row['compact_mask_json'])
                                    C.need(B.compact.encode(row['record_ordinal'],task,entries)==mask,'ORIGINAL_PERSISTENT_MASKS_REASONS_INDICES_BIT_PARITY')
                                    field_counts(stats,entries);task_rows+=1
                                if selected_part is None:selected_part=K.TypedPart(part['row_kind'],part['task_code'],plan['typed_part_cap_bytes'],plan['row_serialized_cap_bytes'])
                                selected_part.add(row)
                        C.need(identity(path)==before and rows==part['rows'] and digest.hexdigest()==part['typed_stream_sha256'],'WHOLE_OLD_PART_SHA_FRAME_STREAM_DIGEST_AND_MASS')
                    finally:src.close()
                    old_parts.append({'reference':pr,'window_reference':wr,'manifest_reference':manifest_ref,'actual_parent_state':origin['actual_parent_state']})
                    if selected_part is not None:
                        sequence+=1;out=selected_part.finish(parts_dir/('part_%06d.parquet'%sequence));I.allow(out['reference']);new_parts.append(out)
                        # parent is replaced by the actual current coverage ref
                        # only after the complete selected cache has been sealed.
                        db.execute('INSERT INTO parts VALUES(?,?,?,?,?,?,?,?)',(fid,lo,hi,part['task_code'],part['row_kind'],K.canonical(out['reference']).decode(),K.canonical(wr).decode(),K.canonical(manifest_ref).decode()))
                    db.commit()
        C.need(base_rows==expected and task_rows==14*expected and db.execute('SELECT count(*) FROM selected WHERE seen<>32767').fetchone()[0]==0,
            'EVERY_SELECTED_CANONICAL_BASE_AND14_TASKS_EXACT_ONCE_NO_GAP_OR_UNKNOWN')
        C.need(len(stats)==146 and all(s['records']==expected for s in stats.values()),'OWN_TASK_SELECTED_RECORD_DENOMINATOR_NO_ROLE_OR_COMMON_DILUTION')
        holds=quality_fields(stats,active_field_ids=plan['field_scope']['active_field_ids'])
        report={'schema':'BOUNDED_COMPLETE_SPRIME_TYPED_COVERAGE_V1','status':'EXACT_NUMERIC_SOURCE_COVERAGE_NOT_FINAL_MASKS',
            'mode':'bounded_pilot55k','job_id':str(proof['job_id']),'records':expected,'molecules':55000,'task_rows':task_rows,'base_rows':base_rows,
            'field_stats':{k:dict(v) for k,v in stats.items()},'selected_group_record_counts':dict(group_records),'quality_hold_fields':holds,'errors':[],
            'original_projection_origins':origins,'old_parent_states_and_costs_unchanged':True,'old_FAILED_or_TIMEOUT_not_promoted':True,
            'all14task_and_base_exact_once':True,'original_values_masks_None_IEEE_bits_and_indices_unchanged':True,
            'original_source_full_population_counts':C.GLOBAL_SOURCE_COUNTS,'full_Common_or_D4_D5_D3_D6_release':False}
        for key in ('canonical_index','field_map_reference','logical_group_plan_reference','source_inventory_reference'):report[key]=plan[key]
        source_parts=I.save(root/'original_part_lineage.DATA.json',{'parts':old_parts})
        origin_ref=I.save(root/'current_parent_typed_origin.json',{'schema':'CURRENT_PARENT_SELECTED_TYPED_ORIGIN_V1',
            'status':'ACTUAL_CLOSED_SUBSET_WITHIN_PARENT_NOT_CHILD_C0','job_id':str(proof['job_id']),
            'Root_projection_review_reference':plan['projection_origin_review_reference'],'original_part_lineage_reference':source_parts,
            'original_failed_timeout_states_preserved':True,'full_Common_D4_D5_D3_D6_release':False})
        # No manifest/catalog hash cycle: this independent origin locator has
        # no reference to the mutable catalog or the future final manifest.
        db.execute('UPDATE parts SET parent=?',(K.canonical(origin_ref).decode(),));db.commit();db.close();db=None
        report['parts_catalog']=I.allow(I.pin(root/'numeric_catalog.sqlite'));report['base_index']=report['parts_catalog']
        report['current_parent_typed_origin_reference']=origin_ref;report['original_part_lineage_reference']=source_parts
        ref=I.save(root/'manifest.json',report)
        return ref,report,old_parts
    finally:
        canonical.close()
        if db is not None:db.close()
        C.need(identity(plan['canonical_index']['path'])==frame,'ORIGINAL_CANONICAL_FD_FRAME_UNCHANGED_DURING_SELECTED_COVERAGE')
