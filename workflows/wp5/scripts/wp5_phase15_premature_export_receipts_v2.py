"""Read-only metadata/receipt forensics; no frames, labels, QM, or repair writes."""
from __future__ import annotations
import argparse,hashlib,json,os,sqlite3,time,traceback
from pathlib import Path
from urllib.parse import quote
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
QUEUE=ROOT/'queue/pending.sqlite'
PAIRS=(('12','4515290'),('13','4515291'),('14','4515292'),('17','4515293'),('18','4515294'),('19','4515295'))
FAILURE_RID='principal_00600001_00900000.lmdb:950624'

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(doc):return json.dumps(doc,sort_keys=True,separators=(',',':'),allow_nan=False)
def ref(p):return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns}

def ro(p):
    q=sqlite3.connect('file:'+quote(str(p))+'?mode=ro',uri=True,timeout=1,isolation_level=None)
    q.row_factory=sqlite3.Row;q.execute('PRAGMA query_only=ON').close();q.execute('PRAGMA busy_timeout=1000').close();return q

def receipt_rows(path,mids=None):
    if not path.is_file():return {'path':str(path),'exists':False,'rows':[]}
    q=ro(path)
    try:
        cols={r[1] for r in q.execute('PRAGMA table_info(completion_receipts)').fetchall()}
        if not {'molecule_id','record_count','wire_sha256','receipt_json'}.issubset(cols):return {'path':str(path),'exists':True,'schema_unavailable':True,'rows':[]}
        out=[];last=None
        while True:
            if mids is not None:
                rows=q.execute('SELECT molecule_id,record_count,wire_sha256,receipt_json FROM completion_receipts WHERE molecule_id IN ('+','.join('?' for _ in mids)+')',sorted(mids)).fetchall() if mids else []
            else:
                rows=q.execute('SELECT molecule_id,record_count,wire_sha256,receipt_json FROM completion_receipts '+('WHERE molecule_id>? ' if last is not None else '')+'ORDER BY molecule_id LIMIT 64',(() if last is None else (last,))).fetchall()
            for row in rows:
                receipt=json.loads(row['receipt_json']);out.append({'molecule_id':row['molecule_id'],'records':row['record_count'],'wire_sha256':row['wire_sha256'],'receipt':receipt})
            if mids is not None or not rows:break
            last=rows[-1]['molecule_id']
        return {'path':str(path),'exists':True,'rows':out}
    finally:q.close()

def owner_rows(session):
    last=None;out=[];pages=0
    while True:
        q=ro(QUEUE)
        try:
            if last is None:
                rows=q.execute('SELECT molecule_id,state,attempt,owner,record_count,archive_path,receipt_json FROM molecules INDEXED BY owner_state_order WHERE owner=? ORDER BY state,molecule_id LIMIT 64',(session,)).fetchall()
            else:
                rows=q.execute('SELECT molecule_id,state,attempt,owner,record_count,archive_path,receipt_json FROM molecules INDEXED BY owner_state_order WHERE owner=? AND (state>? OR (state=? AND molecule_id>?)) ORDER BY state,molecule_id LIMIT 64',(session,last[0],last[0],last[1])).fetchall()
            rows=[dict(r) for r in rows]
        finally:q.close()
        if not rows:break
        out.extend(rows);pages+=1;last=(rows[-1]['state'],rows[-1]['molecule_id'])
    return out,{'owner':session,'page_size':64,'nonempty_pages':pages,'rows':len(out),'EOF_observed':True,'source_connection_closed_each_page':True,'snapshot_atomic':False}

def point_rows(mids):
    out=[];ids=sorted(mids)
    for start in range(0,len(ids),32):
        part=ids[start:start+32];q=ro(QUEUE)
        try:out.extend(dict(row) for row in q.execute('SELECT molecule_id,state,attempt,owner,record_count,archive_path,receipt_json FROM molecules WHERE molecule_id IN ('+','.join('?' for _ in part)+')',part).fetchall())
        finally:q.close()
    return out

# R13 compute_one appends the two stage byte counts after A5 stage_molecule.
# A5 stage_molecule shallow-copies the receipt and adds only execution_id.
QUEUE_ONLY_TRANSPORT_KEYS={'stage_wire_bytes','stage_compressed_wire_bytes'}
ARCHIVE_ONLY_TRANSPORT_KEYS={'execution_id'}

def compare_receipts(queue_receipt,saved,queue_attempt=None):
    archive_receipt=saved['receipt'];left=set(queue_receipt);right=set(archive_receipt)
    queue_only=sorted(left-right);archive_only=sorted(right-left)
    changed=sorted(k for k in left&right if canonical(queue_receipt[k])!=canonical(archive_receipt[k]))
    issues=[]
    for key in ('molecule_id','records','counts','context'):
        if key not in queue_receipt or key not in archive_receipt:issues.append('REQUIRED_CORE_MISSING:'+key)
    if changed:issues.append('SHARED_FIELDS_DIFFER')
    if set(queue_only)-QUEUE_ONLY_TRANSPORT_KEYS:issues.append('UNKNOWN_QUEUE_ONLY_FIELDS')
    if set(archive_only)-ARCHIVE_ONLY_TRANSPORT_KEYS:issues.append('UNKNOWN_ARCHIVE_ONLY_FIELDS')
    context=queue_receipt.get('context') or {};records=queue_receipt.get('records')
    if queue_attempt is not None and context.get('attempt_id')!=queue_attempt:issues.append('QUEUE_ATTEMPT_DIFFERS')
    if not context.get('execution_id'):issues.append('EXECUTION_ID_MISSING')
    if 'execution_id' in archive_receipt and archive_receipt['execution_id']!=context.get('execution_id'):issues.append('ARCHIVE_EXECUTION_ALIAS_DIFFERS')
    for key in queue_only:
        value=queue_receipt[key]
        if key in QUEUE_ONLY_TRANSPORT_KEYS and (type(value) is not int or value<0):issues.append('STAGE_BYTES_INVALID:'+key)
    if type(records) is not int or records<0 or saved.get('records')!=records:issues.append('ARCHIVE_RECORD_COUNT_DIFFERS')
    if type(records) is not int or queue_receipt.get('requested_outcomes')!=12*records:issues.append('REQUESTED_12N_INVALID')
    wire=saved.get('wire_sha256')
    if not isinstance(wire,str) or len(wire)!=64 or any(c not in '0123456789abcdef' for c in wire):issues.append('ARCHIVE_WIRE_SHA_INVALID')
    # Queue R13 receipt does not carry the SCI wire hash; do not invent a two-source match.
    queue_wire=queue_receipt.get('wire_sha256')
    if queue_wire is not None and queue_wire!=wire:issues.append('QUEUE_ARCHIVE_WIRE_SHA_DIFFERS')
    return {'scientific_receipt_metadata_equivalent':not issues,'issues':issues,
            'queue_only_transport_fields':queue_only,'archive_only_transport_fields':archive_only,
            'common_field_differences':changed,'archive_wire_sha256':wire,
            'queue_wire_sha256_comparison':'MATCH' if queue_wire is not None and queue_wire==wire else 'NOT_PRESENT_IN_ORIGINAL_QUEUE_RECEIPT',
            'SCI_payload_or_frame_read':False}

def check():
    context={'execution_id':'fixture:1','attempt_id':1,'job_id':'fixture','lane':3}
    queue={'molecule_id':'private_fixture','records':2,'counts':{'pm7_B':{'SUCCESS':2}},
           'context':context,'requested_outcomes':24,'retained_raw_calls':0,
           'raw_policy':'FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT',
           'stage_wire_bytes':400,'stage_compressed_wire_bytes':200}
    archive={k:v for k,v in queue.items() if k not in QUEUE_ONLY_TRANSPORT_KEYS};archive['execution_id']=context['execution_id']
    saved={'receipt':archive,'records':2,'wire_sha256':'a'*64}
    comparison=compare_receipts(queue,saved,1);assert comparison['scientific_receipt_metadata_equivalent'],comparison
    changed=json.loads(canonical(archive));changed['counts']['pm7_B']['SUCCESS']=1
    assert not compare_receipts(queue,{**saved,'receipt':changed},1)['scientific_receipt_metadata_equivalent']
    assert not compare_receipts(queue,saved,0)['scientific_receipt_metadata_equivalent']
    assert not compare_receipts(queue,{**saved,'receipt':{**archive,'unknown_extra':True}},1)['scientific_receipt_metadata_equivalent']
    assert not compare_receipts(queue,{**saved,'receipt':{**archive,'execution_id':'other'}},1)['scientific_receipt_metadata_equivalent']
    print(json.dumps({'status':'PRODUCER_SPECIFIC_RECEIPT_TRANSPORT_COMPARISON_PRIVATE_PASS',
       'valid_transport_difference':comparison,'shared_count_difference_rejected':True,
       'attempt_difference_rejected':True,'unknown_extra_rejected':True,'execution_alias_difference_rejected':True,
       'production_SQL_read':False,'SCI_read':False,'QM_started':False}))

def main(args):
    if os.getuid()!=1278 or os.uname().nodename!='compute-0-20':raise ValueError('ACTUAL_UID1278_DEVELOPMENT_COMPUTE20_REQUIRED')
    if args.out is None:raise ValueError('--out is required outside --check')
    obs=load(ROOT/'reports/observation_latest.json');states=obs.get('registered_job_states',{})
    result={'schema':'WP5_PHASE15_PREMATURE_EXPORT_RECEIPT_FORENSICS_V2','status':'READ_ONLY_METADATA_RECEIPT_AUDIT','created_epoch':time.time(),'source':ref(Path(__file__)),'hostname':os.uname().nodename,'observation_time':obs.get('time'),'observation_UID':obs.get('uid'),'observation_sacct_rc':obs.get('sacct',{}).get('returncode'),'queue_receipt_queries_enabled':args.queue_receipts,'roots':[],'foreign_repairs':[],'errors':[],'SCI_frames_or_labels_read':False,'SCI_or_original_LMDB_written':False,'original_LMDB_opened':False,'queue_modified':False,'QM_started':False}
    for node,job in PAIRS:
        roots=list((ROOT/'runtime'/('task_cleanup_'+node)).glob('job_'+job+'_*'))
        if not roots:
            result['roots'].append({'job_id':job,'node':node,'current_observed_state':states.get(job),'runtime_root_present':False});continue
        if len(roots)!=1:raise ValueError('ROOT_COUNT_NOT_UNIQUE:'+job)
        root=roots[0];run=load(root/'run.json');opt=run['options'];prefix_path=root/'export_completion.json';completion_path=root/'completion.json'
        item={'job_id':job,'node':node,'run_root':str(root),'current_observed_state':states.get(job),'runtime_root_present':True,'session':opt['session'],'run_json':ref(root/'run.json'),'export_completion':ref(prefix_path) if prefix_path.exists() else None,'completion':ref(completion_path) if completion_path.exists() else None,'errors':[]}
        repairs_path=root/'previous_export_repairs.json';repairs=load(repairs_path).get('repairs',[]) if repairs_path.exists() else []
        item['previous_export_repairs']=ref(repairs_path) if repairs_path.exists() else None
        for repair in repairs:
            target=Path(repair['run_root']);target_run=load(target/'run.json')['options'];v=repair.get('result') or {}
            result['foreign_repairs'].append({'source_job':job,'source_root':str(root),'target_job':str(target_run['job_id']),'target_root':str(target),'target_current_observed_state':states.get(str(target_run['job_id'])),'repair_metadata_mtime_ns':repairs_path.stat().st_mtime_ns,'records':v.get('records'),'molecules':v.get('molecules'),'error':repair.get('error'),'all_families_F64_readback':all(f.get('float64_exact_readback') is True for f in v.get('families',[])) if v else None})
        completion=load(completion_path) if completion_path.exists() else {}
        errs=[e for w in completion.get('workers',[]) for e in w.get('errors',[])]
        item.update(worker_completed_molecules=sum(w.get('completed',0) for w in completion.get('workers',[])),worker_error_count=sum(w.get('error_count',0) for w in completion.get('workers',[])),known_error_molecule_ids=sorted({e['molecule_id'] for e in errs if e.get('molecule_id')}),completion_status=completion.get('status'))
        prefix=load(prefix_path) if prefix_path.exists() else {};item.update(prefix_molecules=prefix.get('molecules'),prefix_records=prefix.get('records'),prefix_canonical=prefix.get('canonical'),prefix_archive=prefix.get('archive'))
        if args.queue_receipts:
            try:
                permanent=root/'raw_archive.sqlite';prefix_meta=receipt_rows(permanent);prefix_by_mid={r['molecule_id']:r for r in prefix_meta['rows']}
                own_rows,coverage=owner_rows(opt['session']);known=set(prefix_by_mid)|set(item['known_error_molecule_ids'])
                points=point_rows(known);current={r['molecule_id']:r for r in own_rows+points};analysed=[];candidates={}
                for mid,row in current.items():
                    receipt=json.loads(row['receipt_json']) if row['receipt_json'] else None;ctx=(receipt or {}).get('context',{})
                    if str(ctx.get('job_id'))!=job:
                        if mid in known:analysed.append({'molecule_id':mid,'state':row['state'],'attempt':row['attempt'],'owner':row['owner'],'receipt_job_id':ctx.get('job_id'),'classification':'NO_CURRENT_RECEIPT_FROM_THIS_JOB'})
                        continue
                    prefix_row=prefix_by_mid.get(mid);prefix_comparison=compare_receipts(receipt,prefix_row,row['attempt']) if prefix_row is not None else None;prefix_match=bool(prefix_comparison and prefix_comparison['scientific_receipt_metadata_equivalent'])
                    records=(receipt or {}).get('records');n12=isinstance(records,int) and receipt.get('requested_outcomes')==12*records
                    classification='MATCHES_IMMUTABLE_PREFIX_RECEIPT' if prefix_match else 'CURRENT_RECEIPT_NOT_IN_PREFIX'
                    detail={'molecule_id':mid,'state':row['state'],'attempt':row['attempt'],'owner':row['owner'],'execution_id':ctx.get('execution_id'),'records':records,'metadata_requested_12N':n12,'receipt_sha256':hashlib.sha256(canonical(receipt).encode()).hexdigest(),'archive_path':row['archive_path'],'archive_exists':bool(row['archive_path'] and Path(row['archive_path']).is_file()),'prefix_match':prefix_match,'prefix_comparison':prefix_comparison,'classification':classification}
                    if not prefix_match:
                        matches=[]
                        for archive in {str(permanent),row['archive_path']} - {None}:
                            p=Path(archive)
                            if not p.resolve().is_relative_to((ROOT/'runtime').resolve()):continue
                            key=(archive,mid)
                            if key not in candidates:candidates[key]=receipt_rows(p,{mid})
                            for saved in candidates[key]['rows']:
                                if compare_receipts(receipt,saved,row['attempt'])['scientific_receipt_metadata_equivalent']:matches.append({'path':archive,'wire_sha256':saved['wire_sha256'],'comparison':compare_receipts(receipt,saved,row['attempt'])})
                        detail['matching_archive_receipts']=matches
                        if n12 and not matches:detail['classification']='12N_RECEIPT_METADATA_WITHOUT_LOCATABLE_MATCHING_ARCHIVE'
                    analysed.append(detail)
                lane_metas=[]
                for lane in sorted((root/'temporary_lanes').glob('lane_*.sqlite')):
                    data=receipt_rows(lane);lane_metas.append({'path':str(lane),'receipts':len(data['rows']),'not_in_prefix':[{'molecule_id':r['molecule_id'],'records':r['records'],'wire_sha256':r['wire_sha256'],'context':r['receipt'].get('context')} for r in data['rows'] if r['molecule_id'] not in prefix_by_mid or not compare_receipts(r['receipt'],prefix_by_mid[r['molecule_id']],r['receipt'].get('context',{}).get('attempt_id'))['scientific_receipt_metadata_equivalent']]})
                item.update(prefix_archive_receipts=len(prefix_by_mid),prefix_archive_metadata_schema_available=not prefix_meta.get('schema_unavailable',False),queue_receipt_coverage=coverage,current_queue_receipts=analysed,surviving_lane_receipts=lane_metas,receipt_coverage_limit='All current rows owned by this session plus known current errors and prefix molecule IDs. A receipt whose owner changed elsewhere and is absent from both known sets is outside this targeted audit; no whole-queue absence claim. Receipt metadata12N is not proof of preserved numerical SCI payload.')
            except Exception:item['errors'].append(traceback.format_exc(limit=6))
        result['roots'].append(item)
    result['current_receipt_unmatched_cases']=[{'job_id':item['job_id'],'run_root':item.get('run_root'),**row} for item in result['roots'] for row in item.get('current_queue_receipts',[]) if row['classification']=='12N_RECEIPT_METADATA_WITHOUT_LOCATABLE_MATCHING_ARCHIVE']
    result['status']='READ_ONLY_TARGETED_RECEIPT_AUDIT_COMPLETE' if not any(r.get('errors') for r in result['roots']) else 'READ_ONLY_TARGETED_RECEIPT_AUDIT_RECORDED_GAPS'
    result['prior_report']=ref(ROOT/'reports/phase15_premature_export_receipts_actual_v1.json')
    result['receipt_producers']=[ref(ROOT/'scripts/wp5_archive_v5.py'),ref(ROOT/'scripts/wp5_runner_v13.py')]
    result['receipt_comparison_rule']={'required_core':['context','records','counts','molecule_id'],'shared_fields':'EXACT_CANONICAL_JSON','queue_only_transport_fields':sorted(QUEUE_ONLY_TRANSPORT_KEYS),'archive_only_transport_fields':sorted(ARCHIVE_ONLY_TRANSPORT_KEYS),'producer_source_lines':['wp5_archive_v5.py:107-110','wp5_runner_v13.py:845-851'],'SCI_numerical_payload_verified':False}
    with args.out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'status':result['status'],'out':str(args.out),'foreign_repairs':result['foreign_repairs'],'unmatched_12N_metadata_cases':len(result['current_receipt_unmatched_cases']),'roots':[{'job_id':r['job_id'],'state':r.get('current_observed_state'),'worker_completed':r.get('worker_completed_molecules'),'prefix_molecules':r.get('prefix_molecules'),'prefix_archive_receipts':r.get('prefix_archive_receipts'),'queue_owned_rows':r.get('queue_receipt_coverage',{}).get('rows'),'errors':r.get('errors',[])} for r in result['roots']]}))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--queue-receipts',action='store_true');parser.add_argument('--out',type=Path);parser.add_argument('--check',action='store_true');args=parser.parse_args();check() if args.check else main(args)
