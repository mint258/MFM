"""Read-only frozen-window evidence, reusing exact frozen scientific objects."""
from __future__ import annotations
import collections,hashlib,json,os
from pathlib import Path
from . import contract as C,io as I
STATE_TABLES={'budget':['id','cap','inodes','charged','charged_inodes'],
 'ranges':['range_id','cursor','stop'],'tickets':['ticket','range_id','lo','amount','inodes','status','receipt'],
 'windows':['range_id','lo','hi','receipt']}
BOOK_TABLES={'meta':['key','value'],'source':['file_id','cursor','stop','lease'],
 'batch':['name','state','cap','inodes','config','receipt'],'assignment':['name','file_id','lo','hi']}
WORK={}


def relative(path):
    p=Path(path);C.need(C.OLD in p.parents and '..' not in p.parts,'DECLARED_OLD_OUTPUT_ONLY')
    return p.relative_to(C.OLD).as_posix()


def audit_books(plan,cfg,locators,deadline):
    files=locators['files'];p=C.OLD/'actual_range_plan.json'
    actual,actual_observation=I.read_json(p,files['actual_range_plan.json'],deadline,64<<20)
    C.need(actual['schema']=='FULL_LABEL_BATCH_ACTUAL_RANGE_PLAN_V1','ACTUAL_OLD_RANGE_PLAN_SCHEMA')
    expected=actual['ranges'];selectors=I.load(I.require(cfg['selector_reference']))['sources']
    master=I.load(I.require(cfg['master_reference']));sources={r['file_id']:r for r in master['sources']}
    C.need(len(expected)==len(selectors)==16 and {r['file_id'] for r in expected}=={r['file_id'] for r in selectors},'EXACT_ORIGINAL16_SOURCES')
    for r in expected:
        s=next(s for s in selectors if s['file_id']==r['file_id'])
        C.need(r['source']==sources[r['file_id']] and r['physical_row_lo']==s['physical_row_lo']
          and r['physical_row_lo']<r['physical_row_hi']<=s['physical_row_hi'],'ACTUAL_RANGE_FROZEN_SOURCE_AND_SELECTOR')
        key=hashlib.sha256(json.dumps([C.triple(r['source']),r['physical_row_lo'],r['physical_row_hi']],sort_keys=True,separators=(',',':')).encode()).hexdigest()[:24]
        C.need(key==r['range_id'],'EXACT_ORIGINAL_RANGE_ID_RECIPE')
        from workflows.data_v1_final.labels.bounded_projection_v1.parts import slices
        groups=list(slices(r['groups'],r['physical_row_lo'],r['physical_row_hi']))
        C.need(len(groups)<=cfg['max_actual_RGs_per_source'],'FROZEN_ACTUAL_RG_LIMIT')
    book,book_observation=I.sqlite_snapshot(C.BOOK,locators['book_frame'],deadline,BOOK_TABLES)
    metadata={r['key']:json.loads(r['value']) for r in book['meta']}
    C.need(metadata['master']==cfg['master_reference'] and metadata['review']==cfg['full_review_reference'],'EXACT_OLD_BOOK_MASTER_REVIEW')
    batch=[b for b in book['batch'] if b['name']=='full_batch0000'];C.need(len(batch)==len(book['batch'])==1,'EXACT_ORIGINAL_BATCH_IN_BOOK')
    b=batch[0]
    C.need(b['state']=='RUNNING' and json.loads(b['config'])==plan['original_references']['config']
      and b['receipt'] is None and b['cap']==cfg['whole_output_cap_bytes'],'ORIGINAL_RUNNING_LEASE_NOT_ACCEPTED_OR_REWRITTEN')
    assignments=[a for a in book['assignment'] if a['name']=='full_batch0000']
    C.need(sorted((a['file_id'],a['lo'],a['hi']) for a in assignments)
      ==sorted((s['file_id'],s['physical_row_lo'],s['physical_row_hi']) for s in selectors),'ORIGINAL_EXACT_ASSIGNMENT_SET')
    byid={r['file_id']:r for r in book['source']}
    C.need(len(byid)==len(book['source'])==len(sources)==2208 and set(byid)==set(sources)
      and all(byid[f]['stop']==sources[f]['rows'] for f in sources) and len(book['assignment'])==16,'EXACT_FULL_SOURCE_DIRECTORY_AND_ONE_ORIGINAL_ASSIGNMENT_SET')
    for s in selectors:
        r=byid[s['file_id']];C.need(r['cursor']==s['physical_row_lo'] and r['lease']=='full_batch0000','LEASE_AND_CROSS_ALLOCATION_CURSOR_UNCHANGED')
    state,state_observation=I.sqlite_snapshot(C.OLD/'state.sqlite',files['state.sqlite'],deadline,STATE_TABLES)
    for row in state['tickets']:
        if row['receipt'] is not None:row['receipt']=json.loads(row['receipt'])
    for row in state['windows']:row['receipt']=json.loads(row['receipt'])
    conservation=C.cursor_chain(state['ranges'],state['tickets'],state['windows'],expected)
    C.need(len(state['budget'])==1 and state['budget'][0]['id']==1,'ONE_OLD_ALLOCATION_BUDGET')
    budget=state['budget'][0]
    C.need(budget['cap']==cfg['whole_output_cap_bytes']-cfg['admin_reserve_bytes']-cfg['observer_reserve_bytes']-cfg['sidecar_reserve_bytes']
      and budget['inodes']==cfg['output_inode_cap']-128
      and budget['charged']==sum(t['amount'] for t in state['tickets'])
      and budget['charged_inodes']==sum(t['inodes'] for t in state['tickets'])
      and 0<=budget['charged']<=budget['cap'] and 0<=budget['charged_inodes']<=budget['inodes'],'ALL_TICKET_BUDGET_CONSERVED_INCLUDING_UNKNOWN')
    return {'actual_range_plan':actual_observation,'book':book_observation,'state':state_observation,
      'metadata_conservation':conservation,'unchanged_book_batch':b,'unchanged_book_assignments':assignments,
      'ticket_budget':budget,'tickets':state['tickets'],'ranges':state['ranges'],'expected':expected,'windows':state['windows']}


def initialize(locators,deadline,enabled,known):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    WORK.update(locators=locators,deadline=deadline,enabled=enabled,known={r["path"]:r for r in known})


def quality(row,payload,stats):
    # Same frozen sidecar extraction and exact original full/run.py denominator/rates.
    from workflows.data_v1_final.labels.full_projection_v1.coverage import sidecar_row
    from workflows.data_v1_final.labels.streaming_v1 import compact
    out,role=sidecar_row(row,payload,WORK['enabled']);candidate=out['candidate']
    if candidate is None:return
    axes={k:set(compact.unpack(candidate[k])) for k in ('in_scope_fields','source_valid_fields','valid_fields','all_leaves_valid_fields','newly_masked_fields')}
    structural=set(compact.unpack(out['structural_invalid_fields']))
    for fid in axes['in_scope_fields']:
        count=stats[str(fid)];count['records']+=1
        for name in ('source_valid_fields','valid_fields','all_leaves_valid_fields','newly_masked_fields'):count[name]+=fid in axes[name]
        count['new_payload_structural_invalid_records']+=fid in structural


def part(spec,body,deadline,stats):
    import pyarrow.parquet as pq
    from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import verify_cache_row
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import TASKS
    ref=C.triple(spec['reference']);name=relative(ref['path']);files=WORK['locators']['files']
    C.need(name in files and Path(name).parent==Path('parts') and files[name]['bytes']==ref['bytes']<=128<<20,'COMMITTED_PART_DECLARED_SIZE_AND_LOCATION')
    C.need(Path(name).name=='part_'+body['ticket']+'_'+spec['row_kind']+'_'+str(spec['task_code'])+'.parquet','EXACT_ORIGINAL_PART_TICKET_NAME')
    count=0;digest=hashlib.sha256();last=None
    with I.reader(ref['path'],files[name],deadline) as (f,current):
        n,sha=I.hash_stream(f,deadline);C.need((n,sha)==(ref['bytes'],ref['sha256']),'COMMITTED_PART_WHOLE_SHA_MISMATCH')
        f.seek(0);source=pq.ParquetFile(f,pre_buffer=False)
        try:
            C.need(source.metadata.num_rows==spec['rows']<=8192,'PART_ROWS_WITHIN_ORIGINAL_WINDOW')
            for batch in source.iter_batches(batch_size=1,use_threads=False):
                I.checkpoint(deadline)
                for row in batch.to_pylist():
                    payload=verify_cache_row(row)
                    C.need(row['row_kind']==spec['row_kind'] and row['task_code']==spec['task_code'],'REOPEN_TYPED_TASK_CHANGED')
                    provenance=payload['provenance'];owner=provenance['owner'];pos=provenance['physical_row_ordinal']
                    C.need(provenance['source_reference']==body['source_reference'] and body['physical_row_lo']<=pos<body['physical_row_hi']
                      and (last is None or pos>last),'EXACT_SOURCE_WINDOW_ORDERED_ROW_BINDING');last=pos
                    C.need(row['record_ordinal']==owner['record_ordinal'] and row['record_id']==owner['record_id']
                      and row['molecule_id']==owner['molecule_id'] and 0<=row['record_ordinal']<11231854,'EXACT_CANONICAL_OWNER_KEY')
                    if row['row_kind']=='task':C.need(TASKS[payload['task']]==row['task_code'],'ORIGINAL_TASK_CODE_BINDING')
                    else:C.need(row['row_kind']=='base' and row['task_code']==255,'ORIGINAL_BASE_KIND')
                    quality(row,payload,stats)
                    digest.update((row['row_kind']+'|'+str(row['record_ordinal'])+'|'+str(row['task_code'])+'|'+row['scientific_signature']).encode());count+=1
        finally:source.close()
    C.need(count==spec['rows'] and digest.hexdigest()==spec['typed_stream_sha256'],'PART_REOPEN_LOGICAL_ORDER_BITS_MASS')
    return {'status':'VERIFIED_TYPED_PART','reference':ref,'rows':count,'typed_stream_sha256':digest.hexdigest(),'current_frame':current}


def verify_window(job):
    window=job['window'];deadline=WORK['deadline'];ref=window['receipt'];result={'kind':'committed_window','window':window,
      'status':'UNKNOWN_UNVERIFIED_COMMITTED_WINDOW','parts':[],'verified_rows':0,'field_stats':{}}
    try:
        relative_name=relative(ref['path']);C.need(relative_name in WORK['locators']['files'],'COMMITTED_WINDOW_RECEIPT_MISSING')
        body,observation=I.read_json(ref['path'],WORK['locators']['files'][relative_name],deadline,256<<10,known=ref)
        C.need(body['ticket']==job['ticket']['ticket'] and relative_name=='parts/window_'+body['ticket']+'.json'
          and body['file_id']==job['range']['file_id'] and body['source_reference']==job['range']['source'],'EXACT_TICKET_SOURCE_RECEIPT')
        C.need(len({p['reference']['path'] for p in body['parts']})==len(body['parts']),'UNIQUE_WINDOW_PARTS')
        stats=collections.defaultdict(collections.Counter)
        for spec in body['parts']:result['parts'].append(part(spec,body,deadline,stats))
        C.completed_window(body,window,result['parts'])
        result.update(status='VERIFIED_COMMITTED_WINDOW',receipt_observation=observation,
          verified_rows=sum(p['rows'] for p in result['parts']),field_stats={k:dict(v) for k,v in stats.items()},
          physical_classifications=body['physical_classifications'])
    except I.SoftStop as exc:result.update(status='PENDING_RESOURCE_OR_DEADLINE',error=str(exc))
    except Exception as exc:result.update(status='UNKNOWN_OR_CONFLICT_COMMITTED_WINDOW',error=type(exc).__name__+':'+str(exc)[:350])
    return result


def hash_uncommitted(job):
    name=job['relative'];result={'kind':'uncommitted_or_auxiliary_file','relative':name,'classification':job['classification'],
      'status':'UNKNOWN_NOT_HASHED','counts_as_completed_window':False}
    try:
        p=C.OLD/name
        with I.reader(p,WORK['locators']['files'][name],WORK['deadline']) as (f,current):
            n,sha=I.hash_stream(f,WORK['deadline'])
            if str(p) in WORK['known']:
                C.need({'path':str(p),'bytes':n,'sha256':sha}==C.triple(WORK['known'][str(p)]),'KNOWN_WORKER_METADATA_SHA_DIFFERS')
                C.need(n<=2<<20 and name.startswith('worker_') and name.endswith('.json'),'ONLY_DECLARED_CLOSED_WORKER_METADATA')
                f.seek(0);report=json.loads(f.read((2<<20)+1))
                C.need(report.get('schema')=='BOUNDED_LABEL_RANGE_WORKER_V1','ORIGINAL_WORKER_CHECKPOINT_SCHEMA')
                result['original_worker_checkpoint']={k:report[k] for k in ('pid','done_ranges','pending_ranges','errors')}
        result.update(status='HASHED_RETAINED_NEVER_SCIENTIFICALLY_ACCEPTED',reference={'path':str(p),'bytes':n,'sha256':sha},current_frame=current)
    except I.SoftStop as exc:result.update(status='PENDING_RESOURCE_OR_DEADLINE',error=str(exc))
    except Exception as exc:result.update(status='UNKNOWN_OR_CONFLICT_FILE',error=type(exc).__name__+':'+str(exc)[:350])
    return result