"""Terminal packed64 history, read-only; original packets/once are never rewritten."""
import hashlib,json,os,pathlib,stat,types
from workflows.data_v1_final.conformers.postprocess_day_v1.closure import binding,positive_ticks
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as OLD
from . import contract as C,runtime as I
from . import operational as O

REVIEW='ROOT_REVIEWED_TERMINAL_PACKED_CONTINUATION_V2'
ARCHIVE='PACKED_PARENT_EXACT_SOURCE_ARCHIVE_V2'
ORIGINAL10=('__init__.py','contract.py','runtime.py','census.py','prepare.py','worker.py','run.py','metadata.py','test_boundaries.py','README.md')
TERMINAL={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}


def limits(value):
    wanted={'max_registered_parents','max_files_per_parent','max_bytes_per_parent','max_task_file_bytes'}
    C.need(type(value)is dict and set(value)==wanted and all(type(n)is int and n>0 for n in value.values()),'EXACT_POSITIVE_PACKED_HISTORY_READ_LIMITS')
    C.need(value['max_registered_parents']<=100 and value['max_files_per_parent']<=1000000
        and value['max_bytes_per_parent']<=C.G.WAVE_RESERVE and value['max_task_file_bytes']<=1<<30,'BOUNDED_PACKED_HISTORY_NOT_A_GLOBAL_SCAN')
    return value


def archive(ref,proof):
    value=C.metadata_ref(ref);rows=value['entries'];wanted={r['path']:r for r in proof['request']['source_references'] if pathlib.Path(r['path']).parent==C.HERE}
    C.need(value['schema']==ARCHIVE and value['status']=='EXACT_SOURCE_BYTES_ARCHIVED_BEFORE_REPLACEMENT'
        and len(rows)==len(wanted) and {pathlib.Path(p).name for p in wanted} in (set(ORIGINAL10),set(ORIGINAL10)|{'history.py'},set(ORIGINAL10)|{'history.py','operational.py'}),
        'ACTUAL_OLD10_OR_CONTINUATION11_SOURCE_SNAPSHOT')
    found={};refs=[ref]
    for row in rows:
        origin=C.reference_shape(row['origin_reference']);snapshot=row['snapshot_reference'];path=pathlib.Path(snapshot['path'])
        C.need(origin['path'] not in found and C.ROOT/'control/source_snapshots' in path.parents and '..' not in path.parts
            and origin['bytes']==snapshot['bytes'] and origin['sha256']==snapshot['sha256'] and C.small_pin(path)==snapshot,
            'ARCHIVED_OLD_SOURCE_BYTE_IDENTITY_AND_SAFE_SNAPSHOT_PATH')
        found[origin['path']]=origin;refs.append(snapshot)
    C.need(found==wanted,'ARCHIVE_MATCHES_ALL_ACTUAL_OLD_PROOF_PACKED_SOURCE_PINS')
    return refs


def describe(plan):
    ref=plan['packed_history_review_reference'];review=C.metadata_ref(ref)
    C.need(review['schema']==REVIEW and review['status']=='APPROVED_FOR_EXACT_TERMINAL_HISTORY_READBACK' and review['reviewer']=='root'
        and review['original_config_reference']==plan['original_config_reference'] and review['original_plan_reference']==plan['original_plan_reference']
        and review['new_inputs_review_reference']==plan['inputs_review_reference']
        and all(review[k]is True for k in ('all_registered_packed_parents_declared','all_original_claim_owners_in_registered_terminal_inventory',
            'preserve_all_prior_success_failure_unknown_and_shared_once','no_retry_claim_reset_or_reexecution')),'ROOT_EXACT_CONTINUATION_NOT_AN_OLD_SCIENCE_GRANT')
    bounds=limits(review['read_limits']);entries=review['registered_packed_parents']
    C.need(type(entries)is list and 0<len(entries)<=bounds['max_registered_parents'],'REAL_TERMINAL_PACKED_PARENTS_REQUIRED')
    refs=[ref];parents=[];ids=set();roots=set()
    for declared_entry in entries:
        entry,operation_refs=O.expand(declared_entry);refs.extend(operation_refs)
        req=C.metadata_ref(entry['request_reference']);sub=C.metadata_ref(entry['submission_reference'])
        old=C.metadata_ref(entry['producer_plan_reference']);proof=C.metadata_ref(entry['startup_proof_reference']);jid=str(sub['job_id']);cpus,node,version=C.origin_request(old,req)
        ar,av,rows=C.G.account(entry['terminal_accounting_reference']['path'],[jid]);parent=rows[jid]
        C.need(ar==entry['terminal_accounting_reference'] and parent['state'] in TERMINAL and parent['alloc_cpus']==cpus
            and parent['node']==node and req['cpus']==req['requested_cpus']==old['cpus']==cpus
            and req['wall_seconds']==old['wall_seconds']==86400 and req['kind']=='conformer' and req['pilot']is False
            and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['node']==node and req['scope_key']==C.KEY,
            'ACTUAL64_TERMINAL_RAW_ACCOUNT_NOT_OLD16_C0_PREDICATE')
        C.need(sub['schema']=='CPU_PACKED_DAY_SUBMISSION_V'+str(version) and proof['schema']=='FRESH_CPU_PACKED_DAY_EXECUTION_ADMISSION_V'+str(version) and proof['node']==node and proof['actual_cpus']==cpus and sub['request_reference']==entry['request_reference']
            and sub['request']==req and sub['returncode']==0 and str(proof['job_id'])==jid and proof['uid']==1278
            and proof['request_reference']==entry['request_reference'] and proof['request']==req
            and req['producer_plan_reference']==entry['producer_plan_reference'] and proof['source_references']==req['source_references']
            and req['execution_argv']==[C.PY,'-B','-m',C.MODULE,'--plan',entry['producer_plan_reference']['path'],'--startup-proof',entry['startup_proof_reference']['path']],
            'REAL_PACKED_SUBMISSION_REQUEST_PROOF_FULL_ARGV_AND_SOURCE_CLOSURE')
        C.need(all(r in req['source_references'] for r in C.F.sources().values()),'SAME_FROZEN_ORIGINAL_SCIENCE_KERNEL_RECIPE_AND_SOFTWARE_SOURCES')
        identity=proof['parent_identity'];positive_ticks(identity['start_ticks']);old_inputs=C.metadata_ref(old['inputs_review_reference'])
        C.need(type(identity['pid'])is int and identity['pid']>0 and identity['uid']==1278 and identity['boot_id']==proof['boot_id']
            and old['original_plan_reference']==plan['original_plan_reference'] and old['original_config_reference']==plan['original_config_reference'],
            'ONE_ACTUAL_OLD_PACKED_PARENT_AND_SAME_ORIGINAL_POPULATION')
        root=pathlib.Path(old['output_directory']);C.need(C.ROOT/'artifacts/conformers' in root.parents and '..' not in root.parts
            and jid not in ids and str(root) not in roots,'UNIQUE_DECLARED_TERMINAL_PACKED_OUTPUT_ROOTS')
        ids.add(jid);roots.add(str(root))
        if O.deferred(entry):O.describe(entry,jid,old,proof,av['raw_sacct_reference'])
        for name,schema in (('producer_receipt_reference','SPRIME_PACKED_DAY_RECEIPT_V1'),('producer_failure_reference','SPRIME_PACKED_DAY_FAILURE_V1')):
            item=entry.get(name)
            if name=='producer_receipt_reference' and O.deferred(entry):continue # Body is never opened on login, even if a prior CPU header knows its SHA.
            if item is not None:
                report=C.metadata_ref(item);C.need(report['schema']==schema and report['actual_single_parent_job_id']==jid
                    and report['plan_reference']==entry['producer_plan_reference'] and root in pathlib.Path(item['path']).parents,'REAL_OLD_TERMINAL_REPORT_NOT_A_SYNTHETIC_C0')
                if name=='producer_receipt_reference':C.need(report['startup_proof_reference']==entry['startup_proof_reference'] and report['allocated_cpus']==cpus and report['node']==node,'OLD_RECEIPT_PROOF_CPU_BINDING')
                refs.append(item)
        if not O.deferred(entry) and entry.get('producer_receipt_reference') is None and entry.get('producer_failure_reference') is None:
            C.need(entry.get('terminal_report_absence_reviewed')is True,'NO_INVENTED_RECEIPT_AFTER_TIMEOUT')
        refs.extend([entry[k] for k in ('request_reference','submission_reference','producer_plan_reference','startup_proof_reference')])
        refs.extend((ar,av['raw_sacct_reference'],old['inputs_review_reference']));refs.extend(archive(entry['source_archive_manifest_reference'],proof))
        parents.append({'entry':entry,'request':req,'plan':old,'proof':proof,'job_id':jid,'root':str(root),
            'large_operational_receipt_CPU_read_pending':O.deferred(entry),
            'inputs_review':old_inputs,'owner_parent':{'actual':parent,'accounting_reference':ar,'raw_reference':av['raw_sacct_reference']}})
    return review,parents,C.unique(refs)


class ClosedReader:
    """First hash only inside this CPU and these registered terminal roots."""
    def __init__(self,root,bounds,check):
        self.root=pathlib.Path(root);self.bounds=bounds;self.check=check;self.refs={};self.frames={};self.total=0
    def safe(self,path,ledger=False):
        p=pathlib.Path(path)
        if ledger:C.need(p==C.F.ledger_path(p.stem) and len(p.stem)==64,'ONLY_EXACT_CANONICAL_LEDGER_LOCATOR')
        else:C.need(self.root in p.parents and '..' not in p.parts,'ONLY_THIS_REGISTERED_TERMINAL_ROOT')
        for q in (p,*p.parents):
            C.need(not q.is_symlink(),'NO_OLD_ROOT_OR_OUTPUT_SYMLINK')
            if q==self.root:break
        v=p.lstat();C.need(stat.S_ISREG(v.st_mode) and v.st_uid==1278 and v.st_nlink==1,'OLD_CLOSED_SINGLE_LINK_REGULAR_UID1278')
        return p
    def reference(self,path):
        p=pathlib.Path(path);ledger=p==C.F.ledger_path(p.stem) if len(p.stem)==64 else False;p=self.safe(p,ledger)
        if str(p) in self.refs:
            C.need(I.frame(p.lstat())==self.frames[str(p)],'OLD_CLOSED_FRAME_CHANGED_AFTER_FIRST_SHA');return self.refs[str(p)]
        C.need(len(self.refs)<self.bounds['max_files_per_parent'] and self.total+p.lstat().st_size<=self.bounds['max_bytes_per_parent'],'EXACT_TERMINAL_HISTORY_READ_BUDGET')
        ref=I.sha_file(p,check=self.check);self.total+=ref['bytes'];self.refs[str(p)]=ref;self.frames[str(p)]=I.frame(p.lstat());return ref
    def require(self,ref):
        C.need(self.reference(ref['path'])==C.F.triple(ref),'OLD_PRODUCER_OR_FIRST_OBSERVED_SHA_MISMATCH');return pathlib.Path(ref['path'])
    def read(self,ref,maximum=2<<20):
        C.need(ref['bytes']<=maximum,'BOUNDED_OLD_JSON_CONTAINER');path=self.require(ref);before=path.lstat()
        with path.open('rb') as stream:
            C.need(I.frame(os.fstat(stream.fileno()))==I.frame(before),'EXACT_OLD_JSON_SAME_FD')
            raw=stream.read(maximum+1);C.need(I.frame(os.fstat(stream.fileno()))==I.frame(before)==I.frame(path.lstat()),'OLD_JSON_FD_UNCHANGED')
        C.need(len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'],'OLD_JSON_EXACT_EOF_AND_SHA_BEFORE_PARSE')
        value=json.loads(raw);self.require(ref);return value


def task_rows(reader,header,root,jid,plan_ref,owner_plan):
    cpus,node,version=C.origin_resources(owner_plan)
    C.need(header['schema']=='SPRIME_PACKED_INTERNAL_PREPARED_V1' and C.header_resources(header,owner_plan)
        and header['actual_single_parent_job_id']==jid and header['packed_plan_reference']==plan_ref
        and header['native_task_keys_and_seed_domains_changed']is False and type(header['molecules'])is int and 0<header['molecules']<=500,
        'ACTUAL_INTERNAL500_HEADER_NOT_A_CHILD_C0')
    ref=header['tasks_reference'];C.need(ref['bytes']<=reader.bounds['max_task_file_bytes']
        and pathlib.Path(ref['path'])==pathlib.Path(root)/'internal_prepared'/header['batch_id']/'tasks.jsonl','EXACT_BOUNDED_OLD_INTERNAL_TASK_FILE')
    path=reader.require(ref);rows={}
    with path.open('rb') as stream:
        while True:
            raw=stream.readline((8<<20)+1)
            if not raw:break
            C.need(len(raw)<=8<<20 and raw.endswith(b'\n'),'BOUNDED_COMPLETE_OLD_TASK_JSONL_EVENT')
            task=json.loads(raw);key=task['meta']['task_key'];C.need(key not in rows and len(rows)<header['molecules'],'DUPLICATE_OR_EXCESS_PACKED_INTERNAL_TASK_KEY');rows[key]=task
    reader.require(ref);C.need(len(rows)==header['molecules'],'COMPLETE_INTERNAL_TASK_HEADER_MASS');return rows


def dispatch_binding(claim,start,proof,plan_ref,task):
    identity=proof['parent_identity'];meta=task['meta'];jid=str(proof['job_id'])
    C.need(claim['job_id']==jid and claim['uid']==1278 and claim['node']==proof['node']
        and claim['parent_pid']==identity['pid'] and positive_ticks(claim['parent_start_ticks'])==positive_ticks(identity['start_ticks'])
        and claim['boot_id']==proof['boot_id'] and claim['packed_plan_reference']==plan_ref and claim['single_real_parent']is True
        and claim['kernel_sha256']==C.F.KERNEL_SHA and claim['task_key']==meta['task_key']==C.F.task_key(meta['molecule_id'],meta['cohort'])
        and claim['task_sha256']==C.F.sha_value(task) and claim['seed']==C.F.seed_for(meta['molecule_id'],meta['cohort']=='retry_once'),
        'EXACT_OLD_PACKED_CLAIM_TASK_PARENT_TICKS_AND_ORIGINAL_SEED')
    if start is not None:
        positive_ticks(start['pid_start_ticks']);C.need(start['uid']==1278 and start['node']==proof['node'] and start['boot_id']==proof['boot_id']
            and start['job_id']==jid and start['task_key']==claim['task_key'],'EXACT_OLD_START_IDENTITY_WITH_STORED_STRING_TICKS')


def anti_join(eligible,consumed):
    C.need(set(eligible).isdisjoint(consumed),'CONSUMED_OR_UNKNOWN_PACKED_KEY_REENTERED_NEW_DISPATCH_SET');return len(eligible)

def operational_index(census,parent,reader,receipt):
    if receipt is None:return None
    import pyarrow.parquet as pq
    ref=receipt['resolution_index_reference'];path=reader.require(ref);seen=set();observed={}
    source=pq.ParquetFile(path);columns=('molecule_id','task_key','cohort','expected_conformers','original_batch_id',
        'within_root_remainder_descriptor_scope','resolution','evidence_json','original_effective_role',
        'packed_readback_parent_job_id','packed_plan_reference_json')
    C.need(len(source.schema_arrow.names)==len(columns) and set(source.schema_arrow.names)==set(columns),
        'EXACT_ORIGINAL_WRITER_OPERATIONAL_INDEX_SCHEMA_NO_COLUMN_FALLBACK')
    for batch in source.iter_batches(batch_size=1024):
        census.check()
        for row in batch.to_pylist():
            key=row['task_key'];meta=census.db.execute('SELECT mid,meta FROM metas WHERE k=?',(key,)).fetchone()
            C.need(meta is not None and key not in seen,'OLD_OPERATIONAL_INDEX_UNIQUE_ORIGINAL_META_DOMAIN');seen.add(key);value=json.loads(meta[1])
            C.need(row['molecule_id']==meta[0] and row['cohort']==value['cohort'] and row['expected_conformers']==value['expected_conformers'],
                'OLD_OPERATIONAL_INDEX_ORIGINAL_MID_COHORT_N_MASS')
            e=json.loads(row['evidence_json']) if row['evidence_json'] else {}
            if e.get('science_result_observed')is True:observed[key]=e['package_reference']
    C.need(len(seen)==census.db.execute('SELECT count(*) FROM metas').fetchone()[0],'COMPLETE_OLD_OPERATIONAL_INDEX_NOT_A_GUESSED_REMAINDER')
    reader.require(ref);reader.require(receipt['complete_errors_reference']);return {'reference':ref,'rows':len(seen),'old_observed_packages':observed}


def ingest(census):
    review,parents,_=describe(census.plan);bounds=limits(review['read_limits']);reports=[];all_consumed=set()
    for parent in parents:
        census.check();entry=parent['entry'];jid=parent['job_id'];root=pathlib.Path(parent['root']);reader=ClosedReader(root,bounds,census.check)
        C.need(root.is_dir() and not root.is_symlink() and root.lstat().st_uid==1278,'REGISTERED_TERMINAL_ROOT_EXISTS_UNCHANGED')
        def header_writer(owner,raw):return census.budget.write(census.out/'operational_parent_headers'/(owner+'.json'),raw)
        receipt,actual_receipt_ref,header_ref=O.read(parent,reader,header_writer,{'job_id':str(census.proof['job_id']),
            'plan_reference':C.small_pin(census.plan['_plan_path']),'startup_proof_reference':C.small_pin(census.proof['request']['startup_proof_path']),
            'SOURCE9_and_quota_before_body':True})
        index=operational_index(census,parent,reader,receipt) if O.deferred(entry) else None
        census.parents[jid]=parent['owner_parent'];keys=set();headers={};tasks={};directory_names={}
        for name in ('dispatch','starts','packets','errors'):
            directory=root/name;C.need(directory.is_dir() and not directory.is_symlink(),'EXACT_OLD_PACKED_OUTPUT_SUBDIRECTORY')
            paths=list(directory.iterdir());C.need(len(paths)<=bounds['max_files_per_parent'],'BOUNDED_OLD_OUTPUT_DIRECTORY_ENTRIES');directory_names[name]={p.name for p in paths}
            for path in paths:
                census.check();suffix='.json.gz' if name=='packets' else '.json';key=path.name[:-len(suffix)] if path.name.endswith(suffix) else ''
                C.need(len(key)==64 and all(c in '0123456789abcdef' for c in key),'NO_UNCLASSIFIED_PACKED_OUTPUT_OR_PARTIAL_FILENAME')
                reader.safe(path);keys.add(key);C.need(len(keys)<=bounds['max_files_per_parent'],'BOUNDED_PACKED_KEY_DISCOVERY')
        # Walk the frozen original meta domain, including claims with no start/output.
        for key,mid in census.db.execute('SELECT k,mid FROM metas').fetchall():
            ledger=C.F.ledger_path(key)
            if ledger.exists():
                claim=reader.read(reader.reference(ledger))
                if str(claim.get('job_id'))==jid:keys.add(key)
        counters={'valid_packet':0,'consumed_unknown':0,'orphan_output':0,'validation_error':0}
        for key in sorted(keys):
            census.check();meta_row=census.db.execute('SELECT mid,meta FROM metas WHERE k=?',(key,)).fetchone()
            C.need(meta_row is not None,'PACKED_OUTPUT_OUTSIDE_ORIGINAL_POPULATION');mid,meta_raw=meta_row;ledger=C.F.ledger_path(key)
            evidence={'origin':'REGISTERED_PACKED64_PARENT','owner_parent':parent['owner_parent'],'source_registration':entry,
                'producer_receipt_reference':actual_receipt_ref,'producer_operational_header_reference':header_ref,'science_result_observed':False,'scientific_status':None,
                'package_reference':None,'execution_resolution':'CONSUMED_UNKNOWN_NO_RETRY','original_outputs_mutated':False}
            if not ledger.exists():
                evidence['execution_resolution']='ORPHAN_OUTPUT_WITHOUT_CLAIM_NO_RETRY';counters['orphan_output']+=1
                census.record_prior(key,mid,evidence);all_consumed.add(key);continue
            lr=reader.reference(ledger);claim=reader.read(lr);evidence['ledger_reference']=lr;all_consumed.add(key)
            error_path=root/'errors'/(key+'.json')
            if error_path.exists():evidence['original_error_reference']=reader.reference(error_path)
            try:
                C.need(str(claim.get('job_id'))==jid,'PACKED_OUTPUT_HAS_DIFFERENT_CANONICAL_CLAIM_OWNER')
                bid=claim['internal_batch_id'];C.need(bid in parent['inputs_review']['candidate_batch_ids'],'OLD_BATCH_IN_ACTUAL_ROOT_REMAINDER_SCOPE')
                prepared=claim['prepared_reference'];C.need(pathlib.Path(prepared['path'])==root/'internal_prepared'/bid/'prepared.json','ACTUAL_PACKED_PREPARED_HEADER_LOCATION')
                if bid not in headers:
                    header=reader.read(prepared);C.need(header['original_config_reference']==census.plan['original_config_reference']
                        and header['original_plan_reference']==census.plan['original_plan_reference'] and header['batch_id']==bid
                        and header['kernel_sha256']==C.F.KERNEL_SHA,'SAME_ORIGINAL_CONFIG_POPULATION_INTERNAL_BATCH_AND_KERNEL')
                    headers[bid]=header;tasks[bid]=task_rows(reader,header,root,jid,entry['producer_plan_reference'],parent['plan'])
                task=tasks[bid][key];C.need(task['meta']==json.loads(meta_raw),'ORIGINAL_FULL_META_UNCHANGED_FOR_REUSED_PACKED_TASK')
                packet_path=root/'packets'/(key+'.json.gz');start_path=root/'starts'/(key+'.json')
                start=reader.read(reader.reference(start_path)) if start_path.exists() else None
                C.need(claim['recipe_config']==census.value['recipe_config'] and claim['plan_reference']==census.plan['original_plan_reference'],
                    'UNCHANGED_ORIGINAL_RECIPE_AND_ORDINARY_PLAN_FOR_REUSED_CLAIM')
                dispatch_binding(claim,start,parent['proof'],entry['producer_plan_reference'],task)
                dispatch_path=root/'dispatch'/(key+'.json')
                if dispatch_path.exists():
                    observed=reader.read(reader.reference(dispatch_path));C.need(observed=={'ledger_reference':lr,'record':claim},'DURABLE_PACKED_DISPATCH_EQUALS_CANONICAL_ONCE')
                if packet_path.exists():
                    ref=reader.reference(packet_path);C.need(ref['bytes']<=census.value['packet_compressed_limit_bytes'],'ORIGINAL_PACKET_COMPRESSED_LIMIT_UNCHANGED')
                    packet=OLD.read_packet(ref,census.value);reader.require(ref)
                    ctx=types.SimpleNamespace(packed_plan=parent['plan'],packed_receipt={'plan_reference':entry['producer_plan_reference'],
                        'startup_proof_reference':entry['startup_proof_reference'],'actual_single_parent_job_id':jid},
                        reference=reader.reference,read=reader.read,require=reader.require,_task_header=prepared,_task_rows=tasks[bid])
                    normalized={'molecule_id':mid,'source':ref,'summary':packet['summary'],'formal_start':packet.get('formal_start')}
                    bound=binding(ctx,normalized,census.value,{})
                    C.need(bound['once_ledger_sha256']==lr['sha256'] and packet.get('formal_start')==start,'ORIGINAL_POSTPROCESS_PACKED_BINDING_AND_EXACT_START')
                    evidence.update(package_reference=ref,start_reference=reader.reference(start_path),science_result_observed=True,
                        scientific_status=packet['summary']['status'],execution_resolution='DURABLE_PACKAGE_VALIDATED_UNDER_ORIGINAL_PACKED64_PARENT',
                        task_sha256=claim['task_sha256'],prepared_reference=prepared,actual_float64_geometry_SHA_readback=True)
                    counters['valid_packet']+=1
                else:counters['consumed_unknown']+=1
            except Exception as exc:
                evidence['validation_error']=repr(exc);counters['validation_error']+=1;census.error('OLD_PACKED64_PACKET_CLOSURE',key,exc)
            census.record_prior(key,mid,evidence);census.db.commit()
        if index is not None:
            for key,ref in index['old_observed_packages'].items():
                prior=census.db.execute('SELECT evidence FROM prior WHERE k=?',(key,)).fetchone();current=json.loads(prior[0]) if prior else {}
                C.need(current.get('science_result_observed')is True and current.get('package_reference')==ref,
                    'OLD_OPERATIONAL_INDEX_VALID_PACKAGES_PRESERVED_WITH_THEIR_TRUE_ORIGINS')
        for name,names in directory_names.items():C.need({p.name for p in (root/name).iterdir()}==names,'TERMINAL_PACKED_OUTPUT_SET_CHANGED')
        for path in reader.frames:C.need(I.frame(pathlib.Path(path).lstat())==reader.frames[path],'OLD_HISTORY_FRAME_CHANGED_BEFORE_NEW_DISPATCH')
        reports.append({'actual_parent_job_id':jid,'actual_terminal':parent['owner_parent'],'old_root':str(root),'counts':counters,
            'discovered_keys':len(keys),'first_CPU_hashed_files':len(reader.refs),'first_CPU_hashed_bytes':reader.total,
            'source_operational_receipt_reference':actual_receipt_ref,'actual_CPU_small_header_reference':header_ref,
            'old_operational_index_reference':None if index is None else index['reference'],'old_operational_index_rows':None if index is None else index['rows'],
            'receipt_absence_not_promoted_to_C0':not O.deferred(entry) and entry.get('producer_receipt_reference')is None,'old_SQLite_opened':False})
    result={'schema':'PACKED_TERMINAL_HISTORY_READBACK_V2','parents':reports,'consumed_keys':len(all_consumed),
        'new_native_calls':0,'once_writes':0,'old_source_or_outputs_modified':False,'scientific_failure_UNKNOWN_never_retried':True}
    return result,all_consumed
