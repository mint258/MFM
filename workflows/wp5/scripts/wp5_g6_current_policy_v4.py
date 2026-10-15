"""G6 read-only audit4: unchanged strict checks, corrected queue execution context/full archive path. No QM entry."""
from __future__ import annotations
import argparse,ast,collections,hashlib,json,math,os,socket,sqlite3,subprocess,sys,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
SCREEN=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
NODES={'compute-0-'+str(n) for n in (12,13,14,17,18,19)}
POLICY='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT'
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def save(path,value):
    path=Path(path)
    if path.exists():raise FileExistsError('Immutable G6 evidence exists:'+str(path))
    with path.open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
def queue_rows(path):
    db=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:return [dict(row) for row in db.execute('SELECT * FROM molecules')]
    finally:db.close()
def size(heavy):return next(label for limit,label in ((10,'0_10'),(20,'11_20'),(30,'21_30'),(50,'31_50'),(75,'51_75'),(100,'76_100'),(10**9,'above_100')) if heavy<=limit)
def audit(a,phases,ids,stats,queue):
    import pyarrow.parquet as pq,wp5_parquet_v2 as wire,wp5_engine_v2 as engine
    from wp5_archive_v5 import ArchiveReader
    from wp5_reproduction50_v3 import reconstruct,nonqm_issues
    from wp5_acceptance_catalog import CALCS
    protocol=json.loads(a.protocol.read_text());entries={entry['registry_id']:entry for entry in wire.registry(protocol['registry']['path'])}
    manifest=json.loads(a.audit_membership.read_text())
    audit_ids=set(pq.read_table(manifest['selected_records']['path'],columns=['record_id']).column(0).to_pylist())
    latest={row['molecule_id']:row for row in queue_rows(queue)}
    if set(latest)!=set(ids):raise ValueError('CURRENT_G6_QUEUE_MOLECULE_COUNT_DIFFERS')
    if any(row['state'] in ('PENDING','RUNNING','RETRY_PENDING') for row in latest.values()):raise ValueError('CURRENT_G6_AFTER_ONE_CLEANUP_LEFT_UNFINISHED')
    selected_keys=set()
    for row in latest.values():
        receipt=json.loads(row['receipt_json'] or '{}');context=receipt['context']
        selected_keys.add((row['molecule_id'],context['attempt_id'],int(context['job_id']),str(context['task_id']),int(receipt['lane'])))
    quantum={};families={};intervals=[];scopes=[];compressed=[];raw_total=0;raw_latest=set();expected_raw=set()
    heavy={r[0]:r[2] for r in stats}
    for ordinal,(root,info) in enumerate(phases):
        if not info.get('archive') or not info.get('families'):raise ValueError('CURRENT_G6_EXPORT_NOT_COMPLETE')
        refs=info['families']+[info['archive']]
        for ref in refs:
            if digest(ref['path'])!=ref['sha256']:raise ValueError('CURRENT_G6_IMMUTABLE_EXPORT_CHANGED')
        for ref in info['families']:
            for batch in pq.ParquetFile(ref['path']).iter_batches(batch_size=128):
                for row in batch.to_pylist():
                    family=ref['family'];rid=row['record_id']
                    if row['molecule_id'] not in ids:raise ValueError('CURRENT_G6_EXPANDED_MOLECULE_SCOPE')
                    selector=(row['molecule_id'],row['attempt_id'],int(row['job_id']),str(row['task_id']))
                    selected=any(key[:4]==selector for key in selected_keys)
                    if not selected:continue
                    if family in ('base_geometry','D20','D3','QC'):
                        if rid in families.setdefault(family,{}):raise ValueError('CURRENT_G6_DUPLICATE_LATEST_FAMILY')
                        families[family][rid]=row
                    else:
                        key=(rid,row['calc_type'])
                        if key in quantum:raise ValueError('CURRENT_G6_DUPLICATE_LATEST_RECORD_TASK')
                        if row['status'] not in ('SUCCESS','PROPERTY_FAILED','CALCULATION_FAILED','TIMEOUT'):raise ValueError('CURRENT_G6_PIPELINE_OR_UNFINISHED_STATUS:'+row['status'])
                        if row['raw_audit_selected']!=(rid in audit_ids):raise ValueError('CURRENT_G6_AUDIT_RECORD_FLAG_DIFFERS')
                        if row['status']!='SUCCESS' or row['raw_audit_selected']:expected_raw.add(key)
                        quantum[key]=row
        reader=ArchiveReader(info['archive']['path'],a.dictionaries)
        try:
            if reader.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('CURRENT_G6_ARCHIVE_INTEGRITY_FAILURE')
            for record_id,calc,molecule,execution in reader.db.execute('SELECT record_id,calc_type,molecule_id,execution_id FROM records'):
                raw=reader.get(record_id,calc,execution);raw_total+=1
                if raw['input_files'] or raw['input_bodies_saved']:raise ValueError('CURRENT_G6_INPUT_BODY_SAVED')
                receipt=json.loads(latest[molecule]['receipt_json'] or '{}')
                if receipt['context']['execution_id']==execution and Path(latest[molecule]['archive_path']).absolute()==Path(info['archive']['path']).absolute():
                    # The latest queue owner archive is additionally constrained by the run's context.
                    complete=reader.completion(molecule)
                    if complete and complete['receipt'].get('execution_id')==execution:
                        context=complete['receipt']['context']
                        key=(molecule,context['attempt_id'],int(context['job_id']),str(context['task_id']),int(complete['receipt']['lane']))
                        if key in selected_keys:
                            pair=(record_id,calc)
                            if pair in raw_latest:raise ValueError('CURRENT_G6_DUPLICATE_LATEST_RAW')
                            raw_latest.add(pair)
                packed=reader.db.execute('SELECT raw_bytes,metadata_bytes,length(raw_frame),length(metadata_frame) FROM records WHERE record_id=? AND calc_type=? AND execution_id=?',(record_id,calc,execution)).fetchone()
                compressed.append({'record_id':record_id,'molecule_id':molecule,'calc_type':calc,'execution_id':execution,'size_stratum':size(heavy[molecule]),'logical_output_bundle_bytes':packed[0],'logical_metadata_bytes':packed[1],'raw_frame_bytes':packed[2],'metadata_frame_bytes':packed[3],'input_bodies_bytes':0,'retention_reason':raw['retention_reason']})
                for item in raw['output_files']:
                    scopes.append({'record_id':record_id,'molecule_id':molecule,'calc_type':calc,'execution_id':execution,'size_stratum':size(heavy[molecule]),'name':item['name'],'role':'output','bytes':item['byte_count'],'sha256':item['sha256']})
            if ordinal==0:
                for molecule,text in reader.db.execute('SELECT molecule_id,receipt_json FROM completion_receipts'):
                    r=json.loads(text);intervals.append((r['molecule_started_epoch'],r['completed_epoch'],r['worker_pid']))
        finally:reader.close()
    expected_records=sum(row[1] for row in stats)
    record_ids={rid for rid,calc in quantum}
    if len(record_ids)!=expected_records or set(quantum)!={(rid,calc) for rid in record_ids for calc in CALCS}:raise ValueError('CURRENT_G6_LATEST_RECORD_TIMES12_NOT_CLOSED')
    for family in ('base_geometry','D20','D3','QC'):
        if set(families.get(family,{}))!=record_ids:raise ValueError('CURRENT_G6_LATEST_NONQM_FAMILY_NOT_CLOSED:'+family)
        for rid,row in families[family].items():
            n=len(families['base_geometry'][rid]['atomic_numbers'] or [])
            problems=nonqm_issues(family,row,n)
            if problems:raise ValueError('CURRENT_G6_NONQM_N_FINITE_STATUS:'+repr(problems))
    for (rid,calc),row in quantum.items():
        expected={key for key,e in entries.items() if e['task']==calc};cells=row['values']
        if len(cells)!=len(expected) or {cell['registry_id'] for cell in cells}!=expected:raise ValueError('CURRENT_G6_REGISTRY_CELL_OMISSION')
        detail=reconstruct(row,entries);z=families['base_geometry'][rid]['atomic_numbers']
        if row['total_atoms']!=len(z) or engine.validate_atomic_arrays(detail,z):raise ValueError('CURRENT_G6_QM_N_FINITE_QC')
        for cell in cells:
            if cell['kind']==10:raise ValueError('CURRENT_G6_EXPLICIT_NONFINITE_VALUE')
            if cell['kind'] in (5,6,7):
                data=cell[{5:'array_f64',6:'array_i64',7:'array_bool'}[cell['kind']]]
                if math.prod(cell['shape'])!=len(data):raise ValueError('CURRENT_G6_TYPED_ARRAY_SHAPE')
    if raw_latest!=expected_raw:raise ValueError('CURRENT_G6_LATEST_RETAINED_RAW_EXACT_SUBSET_DIFFERS:'+repr({'missing':len(expected_raw-raw_latest),'extra':len(raw_latest-expected_raw)}))
    active=set();peak=0
    for when,change,pid in sorted([(s,1,p) for s,e,p in intervals]+[(e,-1,p) for s,e,p in intervals]):
        if change==1:active.add(pid)
        else:active.discard(pid)
        peak=max(peak,len(active))
    if len({p for s,e,p in intervals})<16 or peak<16:raise ValueError('CURRENT_G6_ACTUAL_CONCURRENT_SCIENTIFIC_CPU_BELOW16')
    def table(name,rows):
        if rows:
            import pyarrow as pa
            pq.write_table(pa.Table.from_pylist(rows),a.out/name,compression='zstd')
        else:save(a.out/(name+'.empty.json'),{'rows':0,'reason':'No current-policy failed/audited output members; never substituted for ordinary-success scientific rows'})
    table('raw_scope_members.parquet',scopes);table('raw_compression_by_record.parquet',compressed)
    return {'records':expected_records,'latest_quantum_rows':len(quantum),'historical_raw_rows':raw_total,'latest_required_raw_rows':len(expected_raw),'latest_raw_rows':len(raw_latest),'ordinary_success_raw_not_saved':True,'input_bodies_saved':False,'max_scientific_workers':peak,'status_counts':dict(collections.Counter(row['status'] for row in quantum.values()))}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    if not a.check:p.error('Read-only module; use wp5_g6_reaudit_v1.py, no molecule claims or QM entry')
    ast.parse(Path(__file__).read_text());print('G6_REAUDIT4_AST_PASS_NO_QM_NO_QUEUE_MUTATION')
