"""Read-only true old/new parent index; never invent500 childC0 or attempt."""
import csv,io,json,pathlib,threading,types
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import identity as OLD_ID
from . import contract as C

def positive_ticks(v):
    C.need((type(v) is int and v>0) or (type(v) is str and v.isdecimal() and int(v)>0 and str(int(v))==v),'EXACT_POSITIVE_STORED_PROC_TICKS')
    return int(v)

def binding(ctx,packet,value,imports):
    start=packet.get('formal_start')
    if not isinstance(start,dict) or start.get('resource_scope')!='sprime_packed_day_v1':return OLD_ID.attempt_binding(packet,value,imports)
    mid=packet['molecule_id'];key=OLD_ID.require_task_key(start['task_key']);ledger=C.F.ledger_path(key);lr=ctx.reference(ledger);claim=ctx.read(lr)
    root=pathlib.Path(ctx.packed_plan['output_directory']);source=packet['source'];header=ctx.read(claim['prepared_reference'])
    C.need(source['path']==str(root/'packets'/(key+'.json.gz')) and ctx.read(ctx.reference(root/'starts'/(key+'.json')))==start
      and claim['schema']=='SPRIME_DISPATCH_INTENT_V3' and claim['resource_scope']=='sprime_packed_day_v1'
      and claim['packed_plan_reference']==ctx.packed_receipt['plan_reference']==header['packed_plan_reference']
      and header['schema']=='SPRIME_PACKED_INTERNAL_PREPARED_V1' and header['actual_single_parent_job_id']==ctx.packed_receipt['actual_single_parent_job_id']
      and C.PACK.header_resources(header,ctx.packed_plan) and claim['node']==start['node']==C.PACK.origin_resources(ctx.packed_plan)[1] and header['native_task_keys_and_seed_domains_changed'] is False
      and claim['job_id']==start['job_id']==header['actual_single_parent_job_id'] and claim['uid']==start['uid']==1278
      and claim['boot_id']==start['boot_id'] and claim['task_key']==key and claim['molecule_id']==start['molecule_id']==mid
      and claim['task_sha256']==start['task_sha256'] and claim['seed']==start['seed']==packet['summary']['seed']
      and claim['prepared_reference']['path']==str(root/'internal_prepared'/start['internal_batch_id']/'prepared.json')
      and start['dispatch_reference']==lr and type(start['pid']) is int and start['pid']>0,'REAL_PACKED64_PACKET_START_CLAIM_SOURCE_AND_ORIGINAL_SEED')
    positive_ticks(start['pid_start_ticks']) # Stored original string is not rewritten.
    C.need(claim['boot_id']==C.meta(ctx.packed_receipt['startup_proof_reference'])['boot_id'],'REAL_PACKED64_BOOT_SOURCE')
    if getattr(ctx,'_task_header',None)!=claim['prepared_reference']:
        ctx._task_header=claim['prepared_reference'];ref=header['tasks_reference'];ctx.require(ref)
        with pathlib.Path(ref['path']).open() as f:ctx._task_rows={t['meta']['task_key']:t for t in (json.loads(line) for line in f)}
        C.need(len(ctx._task_rows)==header['molecules'],'EXACT_INTERNAL_TASK_UNION')
    C.need(key in ctx._task_rows and C.F.sha_value(ctx._task_rows[key])==claim['task_sha256'],'ORIGINAL_EXACT_TASK_PAYLOAD_AND_NEW_PARENT_BINDING')
    return {'task_key':key,'once_ledger_path':str(ledger),'once_ledger_sha256':lr['sha256'],'once_ledger_bytes':lr['bytes']}

def select_owner(packet,origins):
    start=packet.get('formal_start')
    if not isinstance(start,dict) or start.get('resource_scope')!='sprime_packed_day_v1':return None
    owner=str(start['job_id']);key=OLD_ID.require_task_key(start['task_key'])
    C.need(owner in origins and packet['source']['path']==str(pathlib.Path(origins[owner]['root'])/'packets'/(key+'.json.gz')),
        'PACKED_PACKAGE_MUST_USE_ITS_TRUE_REGISTERED_OWNER_ROOT')
    return owner

class OriginReader:
    """One bounded closed-root reader; per-packet binding contexts are private."""
    def __init__(self,origin,bounds,check):
        from workflows.data_v1_final.conformers.sprime_packed_day_v1 import history as H
        self.reader=H.ClosedReader(origin['root'],bounds,check);self.lock=threading.RLock();self.tasks={}
    def reference(self,path):
        with self.lock:return self.reader.reference(path)
    def require(self,ref):
        with self.lock:return self.reader.require(ref)
    def read(self,ref):
        with self.lock:return self.reader.read(ref)
    def prepared(self,ref,origin):
        from workflows.data_v1_final.conformers.sprime_packed_day_v1 import history as H
        with self.lock:
            header=self.reader.read(ref);key=(ref['path'],ref['bytes'],ref['sha256'])
            if key not in self.tasks:self.tasks[key]=H.task_rows(self.reader,header,origin['root'],origin['job_id'],origin['entry']['producer_plan_reference'],origin['plan'])
            return header,self.tasks[key]

def source_witness_proof(plan):
    from .source_inverse import function
    review=C.meta(plan['packed_origins_review_reference']);found,_=C.source_witness(review['postprocess_source_witness_reference'])
    old=pathlib.Path(found[str(C.HERE/'closure.py')]['path']).read_text()
    from workflows.data_v1_final.execution.cpu_packed_day_v2 import contract as R4
    R4.inverse();current=R4.hardware_restore('workflows/data_v1_final/conformers/postprocess_day_v1/closure.py')
    for name in ('binding','positive_ticks','accounting'):
        C.need(function(old,name)==function(current,name),'ORIGINAL_COMPLETE_PACKED_OR_LEGACY_BINDING_ACCOUNTING_BODY_UNCHANGED:'+name)
    for name in ('__init__.py','io.py','common.py','math_bridge.py','hof.py','worker.py','statistics.py','source_inverse.py'):
        ref=found[str(C.HERE/name)];C.need(C.G.meta_pin(C.HERE/name)['sha256']==ref['sha256'],'UNCHANGED_ORIGINAL_POSTPROCESS_SCIENCE_AND_IO_SOURCE:'+name)
    cached=pathlib.Path(C.HERE/'cache.py').read_text();old_cache=pathlib.Path(found[str(C.HERE/'cache.py')]['path']).read_text()
    C.need(cached.count('ctx.actual_packed_receipt_reference')==1 and cached.replace('ctx.actual_packed_receipt_reference',"ctx.plan['packed_receipt_reference']")==old_cache,
        'FULL_CACHE_SOURCE_ONLY_CPU_OBSERVED_RECEIPT_REFERENCE_CONTEXT_DELTA')
    return {'schema':'POSTPROCESS_MULTI_OWNER_SOURCE_WITNESS_V2','original15_archive_reference':review['postprocess_source_witness_reference'],
        'binding_positive_ticks_accounting_full_source_body_equal':True,'common_math_PM7_HOF_D7_statistics_IO_source_bytes_equal':True,
        'cache_complete_text_only_actual_receipt_reference_context_delta':True,
        'DATA_opened_or_new_UFF_QM':False}

def setup_origins(ctx,receipt,packed):
    review,history,origins,_,_=C.packed_origins(ctx.plan,receipt,packed)
    ctx.packed_origins=origins;ctx.packed_origin_readers={jid:OriginReader(origin,history['read_limits'],ctx.check) for jid,origin in origins.items()}
    ctx.packed_declared_sources={};ctx.original_index_metas={}
    return review

def resolve_receipts(ctx,receipt,packed):
    """After Source28+quota, before SCI: actual large receipts and data refs."""
    from workflows.data_v1_final.conformers.sprime_packed_day_v1 import operational as O
    setup_origins(ctx,receipt,packed);headers=[];latest=str(ctx.plan['packed_parent_job_id'])
    creator={'job_id':ctx.job_id,'plan_reference':ctx.plan_ref,
        'startup_proof_reference':C.G.meta_pin(ctx.proof['request']['startup_proof_path']),'SOURCE28_and_quota_before_body':True}
    for owner,origin in ctx.packed_origins.items():
        reader=ctx.packed_origin_readers[owner]
        def write_header(jid,raw):return ctx.write(ctx.out/'operational_parent_headers'/(jid+'.json'),raw)
        value,actual,header=O.read(origin,reader.reader,write_header,creator)
        origin['resolved_receipt']=value;origin['actual_receipt_reference']=actual;origin['actual_operational_header_reference']=header
        if value is not None:
            reader.require(value['resolution_index_reference']);reader.require(value['complete_errors_reference'])
        if header is not None:headers.append(header)
    selected=ctx.packed_origins[latest];C.need(selected['resolved_receipt']is not None,'ACTUAL_LATEST_RECEIPT_BODY_REQUIRED_BEFORE_ANY_DATA_MATH')
    ctx.actual_packed_receipt_reference=selected['actual_receipt_reference']
    C.need(ctx.plan['packed_receipt_reference']is None or ctx.plan['packed_receipt_reference']==ctx.actual_packed_receipt_reference,
        'CPU_ACTUAL_RECEIPT_SHA_MATCHES_ANY_PRIOR_DECLARATION')
    ctx.operational_header_references=headers;return selected['resolved_receipt']

def owner_binding(ctx,packet,value,imports):
    from workflows.data_v1_final.conformers.sprime_packed_day_v1 import history as H
    owner=select_owner(packet,ctx.packed_origins)
    if owner is None:return binding(ctx,packet,value,imports) # exact original16/historical branch
    origin=ctx.packed_origins[owner];reader=ctx.packed_origin_readers[owner];start=packet['formal_start'];key=start['task_key']
    source=C.F.triple(packet['source']);C.need(ctx.packed_declared_sources.get(source['path'])==source,'PACKED_SOURCE_TRANSFERRED_FROM_EXACT_CURRENT_INDEX_BEFORE_PARSE')
    reader.require(source);lr=reader.reference(C.F.ledger_path(key));claim=reader.read(lr)
    C.need(pathlib.Path(claim['prepared_reference']['path'])==pathlib.Path(origin['root'])/'internal_prepared'/start['internal_batch_id']/'prepared.json',
        'EXACT_TRUE_OWNER_PREPARED_HEADER_BEFORE_OPEN')
    header,tasks=reader.prepared(claim['prepared_reference'],origin)
    C.need(key in tasks and tasks[key]['meta']==ctx.original_index_metas[key] and claim['recipe_config']==value['recipe_config']
        and claim['plan_reference']==origin['plan']['original_plan_reference'] and header['original_plan_reference']==origin['plan']['original_plan_reference']
        and header['original_config_reference']==ctx.plan['original_config_reference'] and header['kernel_sha256']==C.F.KERNEL_SHA,
        'TRUE_OWNER_ORIGINAL_META_RECIPE_KERNEL_AND_TASK_PAYLOAD')
    H.dispatch_binding(claim,start,origin['proof'],origin['entry']['producer_plan_reference'],tasks[key])
    # Each call has a private header/task pointer: simultaneous500 boundaries
    # cannot overwrite a shared mutable _task_header/_task_rows pair.
    selected=types.SimpleNamespace(packed_plan=origin['plan'],packed_receipt={'plan_reference':origin['entry']['producer_plan_reference'],
        'startup_proof_reference':origin['entry']['startup_proof_reference'],'actual_single_parent_job_id':owner},
        reference=reader.reference,read=reader.read,require=reader.require,_task_header=claim['prepared_reference'],_task_rows=tasks)
    result=binding(selected,packet,value,imports);reader.require(source);return result

def retain_origin_indices(ctx,current_by_key,original_by_key):
    """Metadata axes only; old UNKNOWN and terminal states remain in audit DATA."""
    import pyarrow.parquet as pq
    reports=[]
    for jid,origin in sorted(ctx.packed_origins.items()):
        ref=origin['actual_receipt_reference']
        if ref is None:
            reports.append({'owner_job_id':jid,'receipt_reference':None,'index_reference':None,'terminal':origin['owner_parent'],'no_old_index_synthesized':True});continue
        receipt=origin['resolved_receipt'];index=receipt['resolution_index_reference'];seen=set();states={};observed=0
        C.need(pathlib.Path(origin['root']) in pathlib.Path(index['path']).parents and '..' not in pathlib.Path(index['path']).parts,'INDEX_IN_ITS_TRUE_PRODUCER_ROOT')
        path=ctx.require(index)
        for batch in pq.ParquetFile(path).iter_batches(batch_size=1024):
            ctx.check()
            for row in batch.to_pylist():
                key=row['task_key'];C.need(key in original_by_key and key not in seen,'OLD_INDEX_EXACT_ORIGINAL_TASK_DOMAIN');seen.add(key)
                meta=original_by_key[key];C.need(row['molecule_id']==meta['molecule_id'] and row['cohort']==meta['cohort']
                    and row['expected_conformers']==meta['expected_conformers'],'OLD_INDEX_ORIGINAL_META_MASS')
                states[row['resolution']]=states.get(row['resolution'],0)+1
                evidence=json.loads(row['evidence']) if row['evidence'] else {}
                if evidence.get('science_result_observed')is True:
                    observed+=1;current=current_by_key[key];latest=json.loads(current['evidence']) if current['evidence'] else {}
                    C.need(latest.get('science_result_observed')is True and latest.get('package_reference')==evidence['package_reference'],
                        'OLD_VALID_PACKAGE_REFERENCE_NOT_DROPPED_OR_REPLACED_BY_LATEST_INDEX')
        C.need(seen==set(original_by_key),'EVERY_REAL_OLD_INDEX_FULL_ORIGINAL_ROLE_DOMAIN');ctx.require(index)
        reports.append({'owner_job_id':jid,'receipt_reference':ref,'index_reference':index,'terminal':origin['owner_parent'],
            'rows':len(seen),'state_counts':states,'observed_package_rows':observed,'original_UNKNOWN_not_relabelled_in_this_audit':True})
    return reports

def accounting(ctx,required):
    review=C.meta(ctx.plan['related_parent_review_reference']);accounted={}
    for ref in review['accounting_references']:
        C.need(C.G.meta_pin(ref['path'])==ref,'EXACT_REAL_ACCOUNTING_PIN');_,value,parents=C.G.account(ref['path'])
        for jid,row in parents.items():C.need(jid not in accounted or accounted[jid]==row,'PARENT_ACCOUNTING_CONFLICT');accounted[jid]=row
    master=C.meta(review['owned_master_reference']);rows={str(r['JobIDRaw']):r for r in master['actual_parents']}
    classes={str(r['job_id']):r for r in review['parent_classifications']}
    C.need(master['query_returncode']==0 and len(rows)==len(master['actual_parents']) and set(classes)==set(rows)
      and len(classes)==len(review['parent_classifications']),'EVERY_OWNED_PARENT_HAS_EXPLICIT_ROOT_COST_CLASSIFICATION')
    related=set()
    for jid,r in classes.items():
        C.need(r['decision'] in ('RELATED_TERMINAL','RELATED_ACTIVE_APPEND_PENDING','UNRELATED_ROOT_REVIEWED') and r['reason'],'NO_NAME_OR_MISSING_ARGV_COST_FALLBACK')
        if r['decision']=='RELATED_TERMINAL':related.add(jid)
    C.need(set(accounted)==related==set(review['related_parent_ids']) and set(required)<=related,'ALL_REQUIRED_PARENTS_AND_ALL_RELATED_COSTS_INCLUDED')
    for jid,r in accounted.items():
        a=rows[jid];C.need(r['state']==a['State'].split()[0] and r['exit_code']==a['ExitCode'] and r['alloc_cpus']==int(a['AllocCPUS'])
          and r['elapsed_raw_seconds']==int(a['ElapsedRaw']),'COST_ROWS_MATCH_COMPLETE_INDEPENDENT_MASTER')
    return accounted,sum(r['alloc_cpus']*r['elapsed_raw_seconds'] for r in accounted.values())

def build(ctx,receipt,packed_plan,original):
    import pyarrow.parquet as pq
    ctx.packed_receipt,ctx.packed_plan=receipt,packed_plan
    C.need(hasattr(ctx,'actual_packed_receipt_reference'),'OPERATIONAL_RECEIPTS_RESOLVED_IN_THIS_CPU_PARENT')
    ctx.attempt_binding=lambda packet,value,imports:owner_binding(ctx,packet,value,imports)
    ref=receipt['resolution_index_reference'];table=pq.read_table(ctx.require(ref));rows=table.to_pylist()
    expected=pq.read_table(ctx.require(original['original_deficits'])).to_pylist();by_key={r['task_key']:r for r in expected}
    C.need(len(rows)==len(by_key)==99351 and {r['task_key'] for r in rows}==set(by_key),'EXACT99351_SUPPORTED_PLUS_UNSUPPORTED_INDEX_UNION')
    ctx.original_index_metas=by_key;origin_indices=retain_origin_indices(ctx,{r['task_key']:r for r in rows},by_key)
    outcomes=[];unstarted=[];states={};parents=set(ctx.packed_origins);transfers=[]
    for row in sorted(rows,key=lambda r:(r.get('original_batch_id') or '',r['molecule_id'])):
        ctx.check();key=row['task_key'];meta=by_key[key];C.need(row['molecule_id']==meta['molecule_id'] and row['cohort']==meta['cohort']
          and row['expected_conformers']==meta['expected_conformers'],'ORIGINAL_INDEX_MOLECULE_COHORT_N_UNCHANGED')
        states[row['resolution']]=states.get(row['resolution'],0)+1
        if meta['cohort']=='unsupported':continue
        ledger=C.F.ledger_path(key)
        if not ledger.exists():unstarted.append({'task_key':key,'molecule_id':meta['molecule_id'],'resolution':row['resolution']});continue
        lr=ctx.reference(ledger);claim=ctx.read(lr);e=json.loads(row['evidence']) if row['evidence'] else {}
        owner=claim.get('job_id')
        if owner is not None:parents.add(str(owner))
        if claim.get('resource_scope')=='sprime_packed_day_v1':
            C.need(str(owner) in ctx.packed_origins,'EVERY_PACKED64_CLAIM_INCLUDING_UNKNOWN_HAS_REAL_TERMINAL_ORIGIN')
        parents.update(map(str,claim.get('historical_parent_ids',[])))
        observed=e.get('science_result_observed') is True;package=e.get('package_reference') if observed else None
        C.need(not observed or package is not None,'OBSERVED_PACKAGE_MUST_HAVE_REAL_REFERENCE')
        if package is not None and str(owner) in ctx.packed_origins:
            origin=ctx.packed_origins[str(owner)];reader=ctx.packed_origin_readers[str(owner)];package=C.F.triple(package)
            C.need(package['path']==str(pathlib.Path(origin['root'])/'packets'/(key+'.json.gz')),'CURRENT_INDEX_PACKAGE_TRUE_OWNER_ROOT')
            reader.require(package);C.need(package['path'] not in ctx.packed_declared_sources,'UNIQUE_TRANSFERRED_PACKED_PACKAGE')
            ctx.packed_declared_sources[package['path']]=package;transfers.append({'owner_job_id':str(owner),'task_key':key,'package_reference':package,
                'transfer_authority':receipt['resolution_index_reference'],'original_terminal':origin['owner_parent']})
        outcome={'molecule_id':meta['molecule_id'],'task_key':key,'cohort':meta['cohort'],'expected_conformers':meta['expected_conformers'],
          'seed':C.F.seed_for(meta['molecule_id'],meta['cohort']=='retry_once'),'ledger_reference':lr,'owner_job_id':None if owner is None else str(owner),
          'science_result_observed':observed,'package_reference':package,'scientific_status':e.get('scientific_status') if observed else None,
          'execution_resolution':'DURABLE_PACKAGE_VALIDATED' if observed else 'EXECUTION_UNRESOLVED','truthful_origin_resolution':row['resolution']}
        C.need(claim.get('molecule_id')==meta['molecule_id'] and claim.get('task_key')==key and claim.get('seed')==outcome['seed'],'ONCE_TASK_MID_SEED_UNCHANGED')
        outcomes.append(outcome)
    cost,coresec=accounting(ctx,parents)
    origins_ref=ctx.write_json_new(ctx.out/'packed_origin_indices_readback.json',{'schema':'ALL_TERMINAL_PACKED_INDICES_READBACK_V2','origins':origin_indices})
    transfers_ref=ctx.write(ctx.out/'packed_package_transfer_manifest.DATA.jsonl',b''.join(C.canonical(r)+b'\n' for r in transfers))
    orf=ctx.write_json_new(ctx.out/'exact_outcomes.json',outcomes);urf=ctx.write_json_new(ctx.out/'proven_unstarted_or_unresolved.json',unstarted)
    status='ALL_SPRIME_ATTEMPTS_TERMINAL' if len(outcomes)==90069 and not unstarted else 'PARTIAL_NO_COMMON_FINALIZATION'
    result={'schema':'PACKED_SPRIME_EXACT_OUTCOME_INDEX_V1','status':status,'config':ctx.plan['original_config_reference'],
      'consumed_count':len(outcomes),'expected_deficits':90069,'unsupported_count':9282,'root_draft':original['root_draft'],
      'outcomes':orf,'pilot_imports':original['pilot_imports'],'actual_parent_rows':cost,'actual_accounted_core_seconds':coresec,
      'packed_true64_parent_receipt':ctx.actual_packed_receipt_reference,'original_state_counts':states,'unstarted_reference':urf,
      'actual_operational_parent_headers':ctx.operational_header_references,
      'all_terminal_packed_origin_indices_reference':origins_ref,'actual_CPU_declared_packed_packages_reference':transfers_ref,
      'packed_origin_parent_job_ids':sorted(ctx.packed_origins),'all_packed_parent_contexts_selected_by_true_owner':True,
      'current_postprocess_parent_cost':'PENDING_ACTUAL_ROOT_TERMINAL_ACCOUNTING','old_PARENT_states_unchanged':True,'Common_release':False}
    return ctx.write_json_new(ctx.out/'exact_outcome_index.json',result),result
