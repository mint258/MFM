"""Root-only small-metadata batch constructor. No DATA read or submission."""
import argparse,hashlib,json,os,pathlib,re,sys

ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
PLANNER_OUTPUT=ROOT/'artifacts/pprime_ready_mid_partition_v1/main_ready38_excluding190_resource_r2'
MODULE='workflows.data_v1_final.pprime.formal_packed_sharded_day_v3.metadata'
PRODUCER='workflows.data_v1_final.pprime.formal_packed_sharded_day_v3.run'
SMALL=2<<20

def need(ok,why):
    if not ok:raise ValueError(why)

def reference(ref):
    need(type(ref)is dict and set(ref)=={'path','bytes','sha256'} and type(ref['path'])is str
      and pathlib.Path(ref['path']).is_absolute() and type(ref['bytes'])is int and 0<ref['bytes']<=SMALL
      and type(ref['sha256'])is str and re.fullmatch('[0-9a-f]{64}',ref['sha256']),'EXACT_SMALL_METADATA_POSITIVE_REFERENCE')
    need('.DATA.' not in pathlib.Path(ref['path']).name and not ref['path'].endswith(('.parquet','.sqlite','.sqlite3','.duckdb','.jsonl')),'NO_SCIENTIFIC_BODY_IN_METADATA_HELPER')
    return ref

def small(ref,json_body=True):
    reference(ref);p=pathlib.Path(ref['path']);need(not any(x.is_symlink() for x in (p,*p.parents)),'NO_METADATA_ALIAS')
    before=p.stat();need(before.st_uid==1278 and before.st_size==ref['bytes'] and before.st_nlink==1,'OWN_EXACT_METADATA_FILE')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        first=os.fstat(f.fileno());raw=f.read(SMALL+1);last=os.fstat(f.fileno())
    frame=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode,s.st_nlink)
    need(frame(before)==frame(first)==frame(last)==frame(p.stat()) and len(raw)==ref['bytes']
      and hashlib.sha256(raw).hexdigest()==ref['sha256'],'STABLE_SMALL_METADATA_WHOLE_SHA')
    return json.loads(raw) if json_body else raw

def pin_small(path):
    p=pathlib.Path(path);need(p.is_absolute() and '.DATA.' not in p.name
      and not str(p).endswith(('.parquet','.sqlite','.sqlite3','.duckdb','.jsonl')),'PURE_METADATA_FILENAME_BEFORE_OPEN')
    need(p.stat().st_size<=SMALL,'PURE_SMALL_PRODUCER_HEADER_ONLY')
    raw=p.read_bytes();ref={'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};small(ref,False);return ref

def write_new(path,value):
    p=pathlib.Path(path);raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
    need(len(raw)<=SMALL and not p.exists(),'FRESH_SMALL_METADATA_OUTPUT');p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return pin_small(p)

def contains(value,target):
    if value==target:return True
    if isinstance(value,dict):return any(contains(v,target) for v in value.values())
    if isinstance(value,list):return any(contains(v,target) for v in value)
    return False

def closed_parent(entry,scope_key,module,receipt_schema):
    keys={'receipt_reference','plan_reference','proof_reference','request_reference','submission_reference','accounting_reference','raw_sacct_reference'}
    need(set(entry)==keys,'EXACT_ACTUAL_PARENT_SEVEN_SMALL_REFS')
    r,p,proof,req,sub,account=(small(entry[k]) for k in ('receipt_reference','plan_reference','proof_reference','request_reference','submission_reference','accounting_reference'))
    raw=small(entry['raw_sacct_reference'],False).decode();lines=[v for v in raw.splitlines() if v];need(lines and 'JobIDRaw' in lines[0],'REAL_SACCT_HEADER')
    columns=lines[0].split('|');rows=[dict(zip(columns,line.split('|'))) for line in lines[1:]];job=str(proof['job_id'])
    actual=[v for v in rows if v.get('JobIDRaw')==job];need(len(actual)==1,'ONE_TRUE_PARENT_NOT_BATCH_EXTERN')
    actual=actual[0];need(actual['State']=='COMPLETED' and actual['ExitCode']=='0:0'
      and int(actual['AllocCPUS'])==16 and actual['NodeList']==req['node'],'ACTUAL_C0_SIXTEEN_CPU_PARENT_REQUIRED')
    need(contains(account,entry['raw_sacct_reference']),'ACCOUNT_METADATA_BINDS_ACTUAL_RAW_REF')
    need(r['schema']==receipt_schema and str(r['job_id'])==job==str(sub['job_id']) and r['uid']==proof['uid']==sub['uid']==1278
      and sub['sbatch_returncode']==0 and proof['execution_admission_granted']is True and sub['request']==proof['request']==req
      and sub['request_reference']==proof['request_reference']==entry['request_reference']
      and req['scope_key']==scope_key and req['cpus']==16 and req['wall_seconds']==86400
      and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['pilot'] is False
      and req['execution_argv']==[sys.executable,'-B','-m',module,'--plan',entry['plan_reference']['path'],'--startup-proof',entry['proof_reference']['path']]
      and entry['plan_reference'] in req['source_references']
      and r['plan_reference']==entry['plan_reference'] and r['startup_proof_reference']==entry['proof_reference'],
      'ACTUAL_RECEIPT_PLAN_PROOF_SUBMISSION_PARENT_BINDING')
    return r,p,proof,actual

def planning(cfg):
    entry=cfg['planner_parent'];need(pathlib.Path(entry['receipt_reference']['path'])==PLANNER_OUTPUT/'receipt.json','EXACT_ACTUAL197_PLANNER_OUTPUT')
    receipt,plan,proof,actual=closed_parent(entry,'pprime_ready_mid_partition_v1',
      'workflows.data_v1_final.pprime.ready_mid_partition_v1.run','PPRIME_READY_MID_PARTITION_RECEIPT_V1')
    need(str(proof['job_id'])=='4525197' and receipt['native_init_invoke_calls']==0 and receipt['actual_once_writes']==0
      and receipt['active_DB_read'] is False,'REAL197_ZERO_NATIVE_MID_PARTITION')
    qref=receipt['partition_QA_reference'];qa=small(qref);review=small(cfg['partition_root_review_reference'])
    need(qa['schema']=='PPRIME_READY_MID_PARTITION_QA_V1' and qa['status']=='CPU_CLOSED_PARTITION_REQUIRES_ROOT_REVIEW'
      and all(qa[k]is True for k in ('pairwise_disjoint','union_covers_original_ready_MID_universe','roles_equal_original_frozen_authority','source_MID_ids_preserved'))
      and qa['physical_conformer_IDs_verified']is False,'CPU_CLOSED_MID_QA_NOT_PHYSICAL_ID_PROOF')
    need(review['schema']=='PPRIME_DISJOINT_READY_MID_PARTITION_ROOT_REVIEW_V1'
      and review['status']=='APPROVED_EXACT_CPU_CLOSED_DISJOINT_MID_PARTITION' and review['reviewer']=='root'
      and review['partition_QA_reference']==qref and review['shard_header_references']==qa['shard_header_references']
      and all(review[k]==qa[k] for k in ('main190_exclusion_header_reference','legacy_pilot_exclusion_header_reference')),
      'EXACT_ROOT_PARTITION_ACCEPTANCE_REQUIRED_NOT_AUTOSIGNED')
    gate=small(receipt['Source3_reference']);need(gate['tests']==3 and gate['failures']==gate['errors']==gate['skipped']==0,'ACTUAL_PLANNER_SOURCE3_PASS')
    return qref,qa,plan,actual

def slots(cfg):
    budget=small(cfg['budget_basis_reference']);limit=budget['parent_metadata_slots']
    schema=re.fullmatch(r'ROOT_PPRIME_SHARED_POOLS_([0-9]+)_PARENT_METADATA_ADMISSION_V1',budget['schema'])
    need(schema and int(schema.group(1))==limit and budget['status']=='APPROVED'
      and budget['reviewer']=='root' and type(limit)is int and limit>0
      and budget['per_parent_metadata_log_observer_provider_future_bytes']==384<<20
      and budget['shared_PREP_pool_cap_bytes']==budget['shared_EXEC_pool_cap_bytes']==32<<30
      and budget['shared_pools_counted_once']is True and budget['all_existing_used_closed_failed_UNKNOWN_and_live_futures_retained']is True,
      'REAL_CURRENT_ROOT_SLOT_COUNT_GLOBAL_SHARED_POOLS_ADMISSION')
    allowed=cfg.get('allowed_metadata_slot_ids',[r['slot_id'] for r in cfg['slots']]);cfg['allowed_metadata_slot_ids']=allowed;rows=cfg['slots']
    need(type(allowed)is list and 1<=len(allowed)<=limit and len(set(allowed))==len(allowed)
      and all(type(s)is str and re.fullmatch('[A-Za-z0-9_]+',s) for s in allowed),'ROOT_EXPLICIT_SLOTS_WITHIN_ACTUAL_ADMISSION')
    need(1<=len(rows)<=len(allowed) and len({r['slot_id'] for r in rows})==len(rows)
      and all(r['slot_id'] in allowed for r in rows),'ONLY_EXPLICIT_UNIQUE_CURRENT_METADATA_SLOTS')
    pool=small(cfg['shared_pool_root_review_reference'])
    need(pool['schema']=='ROOT_APPROVED_PPRIME_BOUNDED_SHARED_PUBLICATION_POOLS_V2'
      and pool['status']=='APPROVED_EXACT_SHARED_POOLS_COUNTED_ONCE' and pool['reviewer']=='root'
      and pool['total_PREP_and_EXEC_future_bytes']==64<<30
      and all(pool['pools'][k]['cap_bytes']==32<<30 for k in ('PREP','EXEC')),'REAL_GLOBAL_CAS32_PLUS32_ONCE_ROOT_AUTHORITY')
    return rows

def common_request(cfg,slot,qref,mode,headers):
    from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import contract as C
    needed=('pilot_execution_plan_reference','pilot_closure_reference','user_release_reference','generation_release_reference')
    common={k:cfg['generation_references'][k] for k in needed}
    if 'resources' in slot:resources=slot['resources']
    else:
        catalog=small(cfg['provider_catalog_reference']);need(catalog['schema']=='ROOT_ACTUAL_FRESH_DUAL_PARALLEL_NODE_PROVIDERS_V1' and catalog['errors']==[],'ACTUAL_NINE_CLOSED_PROVIDER_METADATA')
        matches=[p for p in catalog['nodes'] if p['node']==slot['node']];need(len(matches)==1,'ONE_REAL_NODE_PROVIDER')
        resources=dict(cfg['common_resource_references'],quota_provider_review_reference=matches[0]['quota_provider_review_reference'],
          quota_provider_identity_reference=matches[0]['quota_provider_identity_reference'],root_carveout_review_reference=slot['root_carveout_review_reference'])
    need(set(resources)==set(C.RESOURCE),'EXACT_NODE_PROVIDER_IDENTITY_CARVEOUT_RESOURCE_REFS')
    for ref in (*common.values(),*resources.values()):small(ref)
    node=slot['node'];allow=(*C.NODES,'compute-0-2','compute-0-8') if mode=='SHARED_PREPARE' else C.NODES
    need(node in allow,'PREP_ANALYSIS2_8_11_TO19_QM_ONLY11_TO19')
    output=pathlib.Path(slot.get('output_directory',str(C.BASE/cfg['batch_id']/slot['slot_id'])));need(C.BASE in output.parents,'FRESH_PRODUCER_OUTPUT_NAMESPACE')
    return {'schema':'ROOT_REQUESTED_PPRIME_FORMAL_SHARDED_DAY_V2','status':'REQUESTED_FOR_REVIEW','requested_by':'root',
      'mode':mode,'node':node,'output_cap_bytes':32<<30 if mode=='SHARED_PREPARE' else slot['output_cap_bytes'],
      'output_directory':str(output),**common,**resources,
      'generation_partition_QA_reference':qref,'generation_partition_root_review_reference':cfg['partition_root_review_reference'],
      'generation_shard_header_references':headers,'shared_pool_root_review_reference':cfg['shared_pool_root_review_reference']}

def draft_request(req,path):
    from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import metadata
    ref=write_new(path,req);draft=metadata.draft(str(path),str(path.parent/'spec'))
    d=small(draft);need(d.get('schema')=='PPRIME_FORMAL_SHARDED_DAY_DRAFT_V2','REAL_INSTALLED_METADATA_DRAFT_OR_REPORT_NONEXECUTABLE')
    return {'root_request_reference':ref,'draft_reference':draft,
      'root_review_template_reference':d['template_reference'],
      'finalize_argv':[sys.executable,'-B','-m',MODULE,'finalize','--draft',draft['path'],'--root-review','ROOT_MUST_SUPPLY_EXACT_STAGE_REVIEW'],
      'submitted':False}

def prepare_batch(cfg,out,qref,qa):
    available={small(ref)['shard_id']:ref for ref in qa['shard_header_references']};seen=set();result=[];rows=slots(cfg)
    if cfg.get('automatic_header_assignment')=='ROUND_ROBIN_ALL_CLOSED_HEADERS':
        need(all('shard_ids' not in r for r in rows),'EXPLICIT_IDS_OR_ROOT_REQUESTED_ROUND_ROBIN_NOT_BOTH')
        for r in rows:r['shard_ids']=[]
        for i,key in enumerate(available):rows[i%len(rows)]['shard_ids'].append(key)
    for slot in rows:
        ids=slot['shard_ids'];need(type(ids)is list and 1<=len(ids)<=64 and len(set(ids))==len(ids),'BOUNDED_REAL_HEADER_SUBSET_PER_PREPARATION_PARENT')
        need(not(set(ids)&seen) and all(i in available for i in ids),'DISJOINT_REAL197_HEADER_SUBSETS');seen.update(ids)
        request=common_request(cfg,slot,qref,'SHARED_PREPARE',[available[i] for i in ids])
        result.append(dict(slot_id=slot['slot_id'],shard_ids=ids,**draft_request(request,out/slot['slot_id']/'root_request.json')))
    return result

def accept_preparations(cfg,out,qref,approve):
    need(approve,'ROOT_MUST_EXPLICITLY_REQUEST_ACTUAL_C0_ACCEPTANCE_NO_AUTOSIGN')
    result={};receipts={}
    for number,entry in enumerate(cfg['preparation_parents']):
        # Preparation receipt intentionally has no duplicated plan/proof fields;
        # validate registration directly, then its CPU header links below.
        r=small(entry['receipt_reference']);p=small(entry['plan_reference']);proof=small(entry['proof_reference'])
        need(r['schema']=='PPRIME_SHARED_PAIRS_PREPARATION_RECEIPT_V2' and r['status']=='CLOSED_PUBLISHED_SUBSET_PENDING_PARENT_C0_ROOT_ACCEPTANCE'
          and str(r['job_id'])==str(proof['job_id']) and r['native_invokes']==0 and r['original_pilot_reinvoked']is False,
          'REAL_ZERO_NATIVE_SHARED_PREPARATION_RECEIPT')
        actual=closed_preparation(entry,p,proof)
        need(p['mode']=='SHARED_PREPARE' and p['generation_partition_QA_reference']==qref,'SAME_ACTUAL197_PARTITION')
        headers=[v['prepared_shard_header_reference'] for v in r['prepared_shards']]
        need(headers,'NONEMPTY_ACTUAL_PUBLISHED_PREPARATION_SUBSET')
        fixture_ref=pin_small(pathlib.Path(p['output_directory'])/'source3.json');fixture=small(fixture_ref)
        need(fixture['tests_run']==3 and all(fixture[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
          'ACTUAL_SAME_PARENT_PREPARATION_SOURCE3_PASS')
        workers=r['input_hash_worker_closures'];need(1<=len(workers)<=16
          and all(w['native_invokes']==0 and w['original_engine_closed']is True and w['original_NoInvoke_in_each_worker']is True for w in workers),
          'ACTUAL_ZERO_INVOKE_HASH_WORKERS_CLOSED_NOT_EXTRA_Slurm_PARENTS')
        for ref in headers:
            h=small(ref);need(h['schema']=='PPRIME_CPU_CLOSED_ASSIGNED_PAIRS_HEADER_V2' and h['native_invokes']==0
              and h['shared_prepare_plan_reference']==entry['plan_reference'] and h['shared_prepare_proof_reference']==entry['proof_reference']
              and h['generation_partition_QA_reference']==qref and h['generation_shard_header_reference'] in p['generation_shard_header_references'],
              'POSITIVE_CPU_PREPARED_HEADER_TRANSITIVE_PARENT_LINK')
        acceptance=write_new(out/('actual_preparation_%03d_root_acceptance.json'%number),{
          'schema':'ROOT_ACCEPTED_PPRIME_SHARED_PAIRS_PREPARATION_V2','status':'ACTUAL_C0_SHARED_PAIRS_ACCEPTED_FOR_ASSIGNED_GENERATION',
          'reviewer':'root','explicit_operator_flag':'--approve-actual-c0','actual_parent':actual,
          'prepared_shard_header_references':headers,'plan_reference':entry['plan_reference'],'startup_proof_reference':entry['proof_reference'],
          'accounting_reference':entry['accounting_reference'],'raw_sacct_reference':entry['raw_sacct_reference'],
          'actual_receipt_reference':entry['receipt_reference'],'partition_QA_reference':qref,
          'actual_source3_reference':fixture_ref,'unpublished_other_shards_preserved_not_accepted':r['unpublished'],
          'not_final_Common_or_training_admission':True})
        for ref in headers:
            h=small(ref);key=small(h['generation_shard_header_reference'])['shard_id']
            need(key not in result,'NO_DUPLICATE_PHYSICAL_SHARD_PREPARATION_ADOPTION');result[key]=(ref,acceptance,h)
    return result

def closed_preparation(entry,p,proof):
    # Same real-parent checker, except the actual receipt omits plan/proof. Its
    # exact produced headers bind both refs; no replacement receipt is written.
    req=small(entry['request_reference']);sub=small(entry['submission_reference']);account=small(entry['accounting_reference'])
    # Old actual-C0 preparations and this resource version share the same V2
    # scientific wire schema; each must retain its exact registered producer.
    from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import contract as V2
    from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import contract as V3
    versions={V2.MODULE:V2,V3.MODULE:V3};argv=req['execution_argv']
    need(type(argv)is list and len(argv)==8 and argv[3] in versions,'EXACT_V2_OR_V3_PREPARATION_PRODUCER')
    producer=argv[3];contract=versions[producer];scope_key=contract.MODES['SHARED_PREPARE']
    need(p['mode']=='SHARED_PREPARE' and req['scope_parameters']==p['scope_parameters']==contract.parameters(p),
      'ORIGINAL_REGISTERED_PREPARATION_RESOURCE_PARAMETERS')
    raw=small(entry['raw_sacct_reference'],False).decode();lines=[v for v in raw.splitlines() if v];need(lines,'ACTUAL_PREPARE_RAW_ACCOUNT')
    columns=lines[0].split('|');actual=[dict(zip(columns,v.split('|'))) for v in lines[1:] if v.split('|')[0]==str(proof['job_id'])]
    need(len(actual)==1,'ONE_ACTUAL_PREPARATION_PARENT');actual=actual[0]
    need(actual['State']=='COMPLETED' and actual['ExitCode']=='0:0' and int(actual['AllocCPUS'])==16 and actual['NodeList']==req['node']
      and contains(account,entry['raw_sacct_reference']) and proof['uid']==sub['uid']==1278 and sub['sbatch_returncode']==0
      and proof['execution_admission_granted']is True
      and str(sub['job_id'])==str(proof['job_id']) and sub['request']==proof['request']==req
      and sub['request_reference']==proof['request_reference']==entry['request_reference']
      and req['scope_key']==scope_key and req['cpus']==16 and req['wall_seconds']==86400
      and req['kind']=='analysis' and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['pilot']is False
      and req['execution_argv']==[sys.executable,'-B','-m',producer,'--plan',entry['plan_reference']['path'],'--startup-proof',entry['proof_reference']['path']]
      and entry['plan_reference'] in req['source_references'],'EXACT_ACTUAL_C0_PREPARATION_PARENT_CHAIN')
    return actual

def execute_batch(cfg,out,qref,qa,approve):
    prepared=accept_preparations(cfg,out,qref,approve);result=[];seen=set();rows=slots(cfg)
    if cfg.get('automatic_header_assignment')=='ONE_ACCEPTED_SHARD_PER_SLOT_IN_QA_ORDER':
        need(all('shard_id' not in r for r in rows),'EXPLICIT_EXEC_IDS_OR_ROOT_ORDER_POLICY_NOT_BOTH')
        ordered=[small(ref)['shard_id'] for ref in qa['shard_header_references'] if small(ref)['shard_id'] in prepared]
        need(len(rows)<=len(ordered),'ONLY_ACTUAL_ACCEPTED_SHARDS_CAN_FILL_EXECUTION_SLOTS')
        for slot,key in zip(rows,ordered):slot['shard_id']=key
    for slot in rows:
        key=slot['shard_id'];need(key in prepared and key not in seen,'ONE_EXECUTION_PARENT_PER_ACCEPTED_SHARD_IN_THIS_BATCH');seen.add(key)
        ref,accepted,h=prepared[key]
        need(h['records']>0,'EMPTY_PREPARATION_NEEDS_NO_EXECUTION')
        request=common_request(cfg,slot,qref,'EXECUTE',[h['generation_shard_header_reference']])
        request.update(prepared_shard_header_reference=ref,shared_preparation_root_acceptance_reference=accepted)
        result.append(dict(slot_id=slot['slot_id'],shard_id=key,**draft_request(request,out/slot['slot_id']/'root_request.json')))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare-batch','execute-batch'))
    parser.add_argument('--inputs',required=True);parser.add_argument('--output',required=True);parser.add_argument('--approve-actual-c0',action='store_true');a=parser.parse_args()
    need(os.getuid()==1278 and pathlib.Path.cwd().is_absolute(),'MAIN_ROOT_OPERATOR_ONLY')
    from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import contract as C
    C.Q.on_login();need(sys.executable==C.Q.PY,'USE_ORIGINAL_FROZEN_PYTHON_FOR_METADATA_ONLY')
    cfg=small(pin_small(a.inputs));need(cfg['schema']=='ROOT_REQUESTED_PPRIME_SHARDED_BATCH_METADATA_V1'
      and cfg['status']=='REQUESTED_FOR_REVIEW' and cfg['requested_by']=='root','ACTUAL_ROOT_BATCH_INPUT_NOT_SOURCE_TEMPLATE')
    out=pathlib.Path(a.output);need(ROOT/'control' in out.parents and not out.exists() and not any(p.is_symlink() for p in (out,*out.parents)),'FRESH_CONTROL_ONLY_BATCH_METADATA')
    out.mkdir(parents=True);qref,qa,plan,actual=planning(cfg)
    legacy_ref=plan['main190_registration']['plan'];legacy=small(legacy_ref)
    inherited={k:legacy[k] for k in ('pilot_execution_plan_reference','pilot_closure_reference','user_release_reference','generation_release_reference')}
    if 'generation_references' in cfg:need(cfg['generation_references']==inherited,'EXACT_SAME_GENERATION_RELEASE_PARENT_AS_REAL197')
    else:cfg['generation_references']=inherited
    need(type(cfg['batch_id'])is str and re.fullmatch('[A-Za-z0-9_]+',cfg['batch_id']),'SAFE_FRESH_METADATA_BATCH_NAME')
    results=prepare_batch(cfg,out,qref,qa) if a.action=='prepare-batch' else execute_batch(cfg,out,qref,qa,a.approve_actual_c0)
    ref=write_new(out/'batch_constructed_receipt.json',{'schema':'PPRIME_SHARDED_BATCH_METADATA_CONSTRUCTION_RECEIPT_V1','action':a.action,
      'input_reference':pin_small(a.inputs),'actual_planner_parent':actual,'partition_QA_reference':qref,'requests':results,
      'generation_references_inherited_from_actual_plan_reference':legacy_ref,
      'budget_basis_reference':cfg['budget_basis_reference'],'allowed_metadata_slot_ids':cfg['allowed_metadata_slot_ids'],
      'shared_POOLS_future_counted_once_by_Root_not_modified_here':True,'SCI_DATA_read':False,'Slurm_submitted':False,
      'generic_exact_stage_reviews_not_signed_by_helper':True,'existing_parts_or_claims_modified':False})
    print(json.dumps(ref))
if __name__=='__main__':main()
