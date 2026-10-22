"""Read only the two final WP5 retry/execution mismatches; no queue writes/QM."""
from pathlib import Path
import argparse, json, os, sqlite3, time, hashlib
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
MIDS=('principal_01100742','principal_01152793')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    if os.uname().nodename!='compute-0-20' or os.getuid()!=1278:raise ValueError('READ_ONLY_PROBE_COMPUTE20_UID1278_ONLY')
    import pyarrow as pa, pyarrow.dataset as ds
    from wp5_archive_v5 import ArchiveReader
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    db=sqlite3.connect('file:'+str(ROOT/'queue/pending.sqlite')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;db.execute('BEGIN')
    result={'schema':'WP5_EXACT_TWO_RETRY_EXECUTION_READ_ONLY_PROBE_V1','host':os.uname().nodename,'uid':os.getuid(),'time':time.time(),'new_QM_calls':0,'queue_written':False,'original_SCI_written':False,'molecules':[]}
    try:
        for mid in MIDS:
            queue=dict(db.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone())
            receipt=json.loads(queue.pop('receipt_json'));declaration=json.loads(queue.pop('export_json'));context=receipt['context']
            session=dict(db.execute('SELECT * FROM sessions WHERE session_id=?',(queue['owner'],)).fetchone())
            root=Path(queue['archive_path']).parent;run=json.loads((root/'run.json').read_text())
            canonical=ds.dataset(root/'canonical_record_attempts.parquet',format='parquet').to_table(filter=ds.field('molecule_id')==mid,use_threads=False).to_pylist()
            qm=[]
            for path in sorted({r['family_parquet_path'] for r in canonical}):
                qm.extend(ds.dataset(path,format='parquet').to_table(filter=ds.field('molecule_id')==mid,use_threads=False).to_pylist())
            selected=[{k:r[k] for k in ('record_id','molecule_id','calc_type','attempt_id','job_id','task_id','lane','status','source_status','failure_code','raw_execution_id','reproduction_package_sha256','input_file_sha256','raw_audit_selected') if k in r} for r in qm]
            reader=ArchiveReader(queue['archive_path'],run['options']['dictionaries'])
            failures=[]
            try:
                completion=reader.completion(mid)
                for row in qm:
                    if row['status']=='SUCCESS':continue
                    raw=reader.get(row['record_id'],row['calc_type'],context['execution_id'])
                    output=[]
                    for f in raw['output_files']:
                        body=f['data'].decode('utf-8',errors='replace');lines=body.splitlines()
                        marked=[line for line in lines if any(t in line.upper() for t in ('SEGMENT','SIGNAL','SIGSEGV','SIGABRT','TIMEOUT','TIMED OUT','ERROR','FAIL','ABORT','TERMINAT','CONVERG','SCF'))]
                        output.append({'name':f['name'],'sha256':f['sha256'],'bytes':len(f['data']),'tail':lines[-25:],'marked_lines':marked[-40:]})
                    failures.append({'SCI_row':{k:v for k,v in row.items() if k!='values'},'raw_metadata':raw['metadata'],'raw_scope_status':raw['scope_status'],'raw_source_status':raw['source_status'],'raw_sha256':raw['raw_sha256'],'output_summaries':output})
                all_executions=[list(r) for r in reader.db.execute('SELECT record_id,calc_type,execution_id,scope_status,source_status FROM records WHERE molecule_id=? ORDER BY record_id,calc_type,execution_id',(mid,))]
            finally:reader.close()
            result['molecules'].append({'queue':queue,'receipt':receipt,'session':session,'run_json':str(root/'run.json'),'run_options_identity':{k:run['options'].get(k) for k in ('session','job_id','mode','task_id','production_contract','production_contract_sha256','reproduction_package','reproduction_package_sha256')},'canonical_rows':canonical,'SCI_task_rows':selected,'failures':failures,'archive_completion':completion,'retained_raw_executions':all_executions})
    finally:db.execute('ROLLBACK');db.close()
    if not args.out.resolve().is_relative_to(ROOT/'acceptance') or args.out.exists():raise ValueError('WRITE_ONCE_ACCEPTANCE_REPORT_REQUIRED')
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'report':str(args.out),'sha256':hashlib.sha256(args.out.read_bytes()).hexdigest(),'molecules':[{'molecule_id':m['queue']['molecule_id'],'queue_attempt':m['queue']['attempt'],'execution_attempt':m['receipt']['context']['attempt_id'],'retryable':m['receipt']['retryable'],'failure_count':len(m['failures']),'failures':[{'record_id':x['SCI_row']['record_id'],'calc_type':x['SCI_row']['calc_type'],'status':x['SCI_row']['status'],'failure_code':x['SCI_row']['failure_code'],'raw_metadata':x['raw_metadata']} for x in m['failures']]} for m in result['molecules']]},ensure_ascii=False))
if __name__=='__main__':main()
