"""Read-only replay of FAILED4524583 closed local outputs, no Parquet projection."""
import collections,concurrent.futures as cf,hashlib,sqlite3
from pathlib import Path
from urllib.parse import quote
from . import contract as C,io as I,projection as P

def derive(plan,units,data):
    keys=C.RECOVERY_KEYS;refs=[C.triple(plan[k]) for k in keys];old=C.meta(plan['recovery_parent_receipt_reference']);inventory=C.meta(plan['recovery_inventory_reference'])
    archive=C.meta(plan['recovery_source_archive_reference']);review=C.meta(plan['recovery_root_review_reference'])
    C.need(old['schema']=='LOCAL6_TDC_DECONTAMINATION_DAY_RECEIPT_V1' and old['job_id']=='4524583' and old['uid']==1278
      and old['node']=='compute-0-14' and old['status']=='INCOMPLETE_STRICT7_EXPORT_HOLD' and old['error']['type']=='ValueError','TRUE_FAILED_R2_PARENT_NOT_C0')
    raw=C.account(plan['recovery_parent_accounting_reference'],'4524583','compute-0-14',state='FAILED',exit_code='3:0',elapsed=1351)
    oldplan=C.meta(old['plan_reference']);proof=C.meta(old['startup_proof_reference']);request=proof['request'];root=Path(oldplan['output_directory']);local=root/'local'
    C.need(C.BASE in root.parents and root.name=='day02_r2' and oldplan['data_references']==data and oldplan['authority']['units']==units
      and request['scope_key']==C.KEY and request['scope_parameters']==oldplan['scope_parameters'] and request['cpus']==16
      and request['node']=='compute-0-14' and proof['uid']==1278 and str(proof['job_id'])=='4524583'
      and old['plan_reference'] in request['source_references'] and proof['execution_admission_granted'] is True,'ACTUAL_R2_FROZEN_INPUTS_AND_PRIMARY_SCOPE')
    C.generic_review(C.meta(request['scope']['review']))
    gate=C.meta(old['source3_reference']);checker=C.meta(old['repository_check_actual_reference'])
    C.need(gate['tests_run']==3 and all(gate[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes'))
      and checker['status']=='PASS' and checker['returncode']==0,'OLD_ACTUAL_PURE_AND_WHOLE_SOURCE_CHECK_NOT_SCIENTIFIC_C0')
    C.need(archive['schema']=='LOCAL7_FAILED_PARENT_SOURCE11_ARCHIVE_V1' and archive['job_id']=='4524583'
      and archive['uid']==1278 and archive['old_FAILED_preserved'] is True and archive['source_archive_never_executed'] is True
      and len(archive['entries'])==11,'ACTUAL_R2_SOURCE_ARCHIVE11')
    expected=set(C.FILES)-{'recovery.py'};names=set();snapshots=[]
    for e in archive['entries']:
        origin=C.triple(e['origin_reference']);snapshot=C.triple(e['snapshot_reference']);p=Path(origin['path']);names.add(p.name)
        C.need(p.parent==C.HERE and origin in request['source_references'] and (snapshot['bytes'],snapshot['sha256'])==(origin['bytes'],origin['sha256'])
          and C.Q.pin(snapshot['path'])==snapshot,'EXACT_ORIGINAL_SOURCE_BYTES_ARCHIVED_NOT_CURRENT_R3_SOURCE')
        snapshots.append(snapshot)
    C.need(names==expected,'ALL11_R2_SOURCES_NO_SUBSTITUTION')
    C.need(inventory['schema']=='LOCAL7_FAILED_CLOSED_OUTPUT_LSTAT_V1' and inventory['job_id']=='4524583' and inventory['uid']==1278
      and inventory['node']=='compute-0-14' and inventory['observation_node']=='sonmi' and inventory['cross_node_device_numbers_not_equal_or_substituted'] is True
      and inventory['old_output_directory']==str(root) and inventory['accounting_reference']==plan['recovery_parent_accounting_reference']
      and inventory['failed_receipt_reference']==plan['recovery_parent_receipt_reference'] and inventory['plan_reference']==old['plan_reference']
      and inventory['startup_proof_reference']==old['startup_proof_reference'] and not inventory['missing_expected_paths'] and not inventory['unexpected_local_files'],
      'ACTUAL_FIXED_OUTPUT_LSTAT_NOT_CPU_HASH_OR_DEVICE_ALIAS')
    fixed={str(local/'source_id_readback.sqlite'),*(str(local/(d+'.strict5.jsonl')) for d in {**C.PRIMARY,**C.PARTIAL})}
    required=set(fixed)
    for u in units:
        directory=local/'units'/u['unit_id'];required.add(str(directory/'provenance.DATA.jsonl'));fixed.add(str(directory/'provenance.DATA.jsonl'))
        fixed.update(str(directory/(d+'.jsonl')) for d in u['datasets'])
    observations={r['path']:r for r in inventory['observations']}
    C.need(len(observations)==len(inventory['observations']) and required<=set(observations)<=fixed,'EXACT_CLOSED_NAMES_ONLY_NO_ARBITRARY_CPU_DISCOVERY')
    for row in observations.values():
        C.need(row['uid']==1278 and row['regular'] is True and row['bytes']>0 and row['nlink']==1,'POSITIVE_OWNED_CLOSED_DATA_FRAME')
    C.need(review['schema']=='ROOT_LOCAL7_FAILED_CLOSED_OUTPUT_RECOVERY_V1' and review['status']=='APPROVED_FOR_READONLY_FAILED_PARENT_RECOVERY'
      and review['reviewer']=='root' and review['failed_receipt_reference']==plan['recovery_parent_receipt_reference']
      and review['failed_accounting_reference']==plan['recovery_parent_accounting_reference'] and review['inventory_reference']==plan['recovery_inventory_reference']
      and review['source_archive_reference']==plan['recovery_source_archive_reference'] and review['old_output_directory']==str(root)
      and review['exact_exception_literal']=='SMALL_METADATA_ONLY' and review['closed_SQLite_small_pin_only_after_all_local_readbacks'] is True
      and review['fixed_closed_files_first_CPU_SHA_authorized'] is True and review['old_FAILED_preserved_no_projection_or_strict_output_copy'] is True,
      'INDEPENDENT_EXACT_FAILED_PREFIX_RECOVERY_AUTHORITY')
    refs.extend([raw,old['plan_reference'],old['startup_proof_reference'],old['source3_reference'],old['repository_check_actual_reference'],
      request['scope']['review'],archive['request_reference'],*snapshots])
    return {'failed_parent_job_id':'4524583','failed_parent_actual_allocated_core_seconds':21616,'old_output_directory':str(root),
      'observations':observations,'inventory_reference':plan['recovery_inventory_reference'],'old_plan_reference':old['plan_reference'],
      'source_archive_reference':plan['recovery_source_archive_reference'],'first_SHA_is_pending_actual_CPU':True},refs

def _ref(path,authority,budget,seen):
    p=str(path);C.need(p in authority['observations'],'DECLARED_LSTAT_NAME_BEFORE_FIRST_DATA_OPEN')
    ref=I.data_pin(p,[Path(authority['old_output_directory'])/'local'],expected=authority['observations'][p],check=budget.check);seen.add(p);return ref

def _strict(v):
    C.need(set(v)==P.ALLOWED_IDENTITY_FIELDS,'UNCHANGED_STRICT_FIVE_FIELDS');P.identity_keys(v)

def require_closed_sqlite(path):
    for suffix in ('-wal','-shm','-journal'):C.need(not Path(str(path)+suffix).exists(),'ORIGINAL_SQLITE_MUST_BE_CLOSED_WITH_NO_SIDECARS')

def run(plan,authority,out,budget):
    """Rebuild reports from source/provenance pairs and byte-identical merges.

    The auxiliary new SQLite stores ONLY dataset/source_id audit keys; it is not
    a second strict identity export. The original twelve strict files and all
    unit files remain in place, read-only. No original Parquet is projected.
    """
    a=authority['recovery'];old=Path(a['old_output_directory'])/'local';out.mkdir(parents=True,mode=0o700);seen=set();reports=[]
    def opaque_original_hash(entry):
        budget.check()
        with I.held(entry['file'],[C.ROOT/'artifacts/expansion/identity'],plan['data_references']):pass
        return entry['file']
    # Refresh original producer SHA without decoding/reprojecting any Parquet
    # row. All identity/provenance values below come only from closed outputs.
    with cf.ThreadPoolExecutor(max_workers=16) as pool:verified_originals=list(pool.map(opaque_original_hash,authority['units']))
    digests={d:hashlib.sha256() for d in {**C.PRIMARY,**C.PARTIAL}};totals=collections.Counter();emitted=collections.Counter();role_counts={d:collections.Counter() for d in digests}
    audit_path=out/'source_ids_only_audit.sqlite';budget.db_paths.append(audit_path);db=sqlite3.connect(audit_path,uri=True)
    def progress():
        try:budget.check();return 0
        except Exception:return 1 # Stop this own analysis query, never a science process/signal.
    db.set_progress_handler(progress,100000)
    db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA temp_store=MEMORY')
    db.execute('CREATE TABLE seen(dataset TEXT NOT NULL,source_id TEXT NOT NULL,PRIMARY KEY(dataset,source_id)) WITHOUT ROWID');tx=0
    try:
        for u in authority['units']:
            directory=old/'units'/u['unit_id'];pr=_ref(directory/'provenance.DATA.jsonl',a,budget,seen);parts={};iterators={};part_rows=collections.Counter()
            for dataset in u['datasets']:
                path=directory/(dataset+'.jsonl')
                if str(path) in a['observations']:
                    parts[dataset]=_ref(path,a,budget,seen);iterators[dataset]=iter(I.rows(parts[dataset],budget.check))
            counts=collections.Counter();datasets=collections.Counter();roles=collections.Counter();unresolved=collections.Counter();flags=collections.Counter()
            try:
                for event,location in I.rows(pr,budget.check):
                    C.need(event['original_unit']==u['unit_id'] and event['source_reference']==u['file'] and event['physical_row_ordinal']==counts['records']
                      and event['graph_or_error_state_upgraded'] is False,'EXACT_ORIGINAL_UNIT_SOURCE_ORDINAL_PROVENANCE')
                    s=event['original_status_and_memberships'];dataset=s['dataset'];C.need(dataset in u['datasets'] and type(event['strict_identity_emitted'])is bool,'EXACT_SOURCE_DATASET_AND_EMISSION_FLAG')
                    datasets[dataset]+=1;roles[s['role']]+=1;counts['records']+=1
                    for key in ('missing_full_key','missing_identity_or_composition','unresolved_source_variant'):
                        C.need(type(s[key])is bool,'ORIGINAL_BOOL_STATUS_PRESERVED');flags[key]+=s[key]
                    if event['strict_identity_emitted']:
                        C.need(dataset in iterators,'NONEMPTY_EMITTED_PART_REQUIRED');v,loc=next(iterators[dataset]);_strict(v)
                        C.need(v['source_id']==s['source_id'] and v['role']==s['role'] and v['subdataset']=='','SOURCE_ID_ROLE_EXACT_PROVENANCE_PAIR')
                        raw=I.dump(v);C.need(len(raw)==loc['line_bytes'] and hashlib.sha256(raw).hexdigest()==loc['line_sha256'],'EXACT_RETAINED_PART_LINE_BYTES_NOT_REPROJECTION')
                        digests[dataset].update(raw);part_rows[dataset]+=1;emitted[dataset]+=1;role_counts[dataset][v['role']]+=1
                        db.execute('INSERT INTO seen VALUES(?,?)',(dataset,v['source_id']));tx+=1
                        if tx>=4096:db.commit();tx=0;budget.check()
                    else:C.need(dataset in C.PARTIAL,'PRIMARY_UNRESOLVED_NEVER_DROPPED');unresolved[dataset]+=1
                for dataset,it in iterators.items():C.need(next(it,None) is None,'NO_ORPHAN_PART_IDENTITIES_AFTER_PROVENANCE')
            finally:
                for it in iterators.values():it.close()
            C.need(counts['records']==u['counts']['records'] and dict(datasets)==u['datasets'] and dict(roles)==u['roles']
              and all(flags[k]==u['counts'][k] for k in flags),'ALL_UNIT_ROW_ROLE_FLAG_CONSERVATION')
            totals.update(datasets)
            reports.append({'unit_id':u['unit_id'],'records':counts['records'],'datasets':dict(datasets),'roles':dict(roles),'unresolved':dict(unresolved),
              'identity_parts':{d:{**ref,'rows':part_rows[d]} for d,ref in parts.items()},'provenance_DATA_reference':{**pr,'rows':counts['records']},'reused_failed_parent':'4524583'})
        db.commit();C.need(len(reports)==404 and dict(totals)==authority['local_counts']['datasets'],'WHOLE404_11398552_SOURCE_ROWS')
        olddb=old/'source_id_readback.sqlite'
        require_closed_sqlite(olddb)
        dbref=_ref(olddb,a,budget,seen);uri='file:'+quote(str(olddb),safe='/')+'?mode=ro&immutable=1'
        # Keep a validated old FD open while SQLite reads a separate immutable
        # readonly FD; verify current CPU frame again after all SQL queries.
        with I.held(dbref,[old],[dbref]) as (held,_):
            db.execute('ATTACH DATABASE ? AS origin',(uri,))
            C.need(db.execute('PRAGMA origin.integrity_check').fetchall()==[('ok',)],'CLOSED_ORIGINAL_SQLITE_INTEGRITY')
            schema=db.execute("SELECT sql FROM origin.sqlite_master WHERE type='table' AND name='seen'").fetchone()
            C.need(schema is not None and 'WITHOUT ROWID' in schema[0].upper(),'ORIGINAL_UNIQUE_SOURCE_ID_TABLE')
            n=sum(emitted.values());C.need(db.execute('SELECT count(*) FROM origin.seen').fetchone()[0]==db.execute('SELECT count(*) FROM main.seen').fetchone()[0]==n,'ORIGINAL_AND_REPLAY_UNIQUE_TOTAL')
            for dataset in digests:
                C.need(db.execute('SELECT count(*) FROM origin.seen WHERE dataset=?',(dataset,)).fetchone()[0]==emitted[dataset],'PER_DATASET_UNIQUE_COUNT')
            C.need(db.execute('SELECT * FROM (SELECT dataset,source_id FROM main.seen EXCEPT SELECT dataset,source_id FROM origin.seen) LIMIT 1').fetchone() is None
              and db.execute('SELECT * FROM (SELECT dataset,source_id FROM origin.seen EXCEPT SELECT dataset,source_id FROM main.seen) LIMIT 1').fetchone() is None,
              'EXACT_BIDIRECTIONAL_SOURCE_ID_SET_NOT_DIGEST_OR_COUNT_APPROXIMATION')
            db.execute('DETACH DATABASE origin')
        outputs={};partial={}
        for dataset in sorted(digests):
            ref=_ref(old/(dataset+'.strict5.jsonl'),a,budget,seen);C.need(ref['sha256']==digests[dataset].hexdigest(),'MERGED_FILE_BYTES_EXACT_ORDERED_PART_CONCATENATION')
            ref={**ref,'rows':emitted[dataset]};missing=sum(r['unresolved'].get(dataset,0) for r in reports);expected={**C.PRIMARY,**C.PARTIAL}[dataset]
            C.need(ref['rows']+missing==expected and (dataset not in C.PRIMARY or missing==0),'SOURCE_ROW_MASS_AND_PRIMARY_NO_UNKNOWN_EXCLUSION')
            read=I.readback(ref,list(role_counts[dataset]),[''],budget.check)
            value={'dataset':dataset,'identities':ref,'records':ref['rows'],'original_physical_rows':expected,'unresolved_without_identity_or_composition':missing,
              'role_counts':dict(role_counts[dataset]),'required_roles':sorted(role_counts[dataset]),'required_subdatasets':[''],
              'raw_artifacts':C.unique([u['file'] for u in authority['units'] if dataset in u['datasets']]),'readback':read,
              'role_semantics':'ORIGINAL_PHYSICAL_RECORD_MEMBERSHIP_ONLY','Common_or_effective_roles_applied':False,'reused_failed_parent':'4524583'}
            (outputs if dataset in C.PRIMARY else partial)[dataset]=value
        C.need(seen==set(a['observations']),'ALL_FIXED_CLOSED_LSTAT_OUTPUTS_USED_NO_OMITTED_FILES')
    finally:db.close()
    auditref=I.data_pin(audit_path,[out],check=budget.check)
    evidence=I.write(out/'readonly_recovery_evidence.json',{'schema':'LOCAL7_FAILED_OUTPUTS_READBACK_V1','old_parent':'4524583','old_state':'FAILED','old_actual_allocated_core_seconds':21616,
      'closed_files_first_SHA_and_readback':len(seen),'inventory_reference':a['inventory_reference'],'all404_provenance_paired':True,
      'original_Parquet_files_opaque_whole_SHA_only_no_rows_decoded':len(verified_originals),
      'all12_strict5_original_readbacks':True,'original_SQLite_reference':dbref,'new_source_ID_only_audit_index':auditref,
      'all_source_IDs_exact_bidirectional_SQL_set_comparison':True,'original_outputs_copied_modified_or_deleted':False,
      'old_Parquet_projection_calls':0,'new_graph_key_UFF_QM_calls':0,'cross_node_st_dev_compared':False,'current_CPU_sameFD_dev_and_all_frames_verified':True},budget)
    return {'primary6':outputs,'original_Molnet6_partial_only':partial,'all_source_rows':sum(totals.values()),'unit_results':reports,
      'source_ID_census_reference':dbref,'readonly_recovery_evidence_reference':evidence,'new_source_ID_only_audit_reference':auditref,'new_graph_or_key_calls':0}
