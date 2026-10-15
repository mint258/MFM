"""Readonly raw evidence for G6 scientific failures; never launch or retry QM."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, multiprocessing, os, re, sqlite3, time
from pathlib import Path
from urllib.parse import quote
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
_BARRIER=None

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return h.hexdigest()

def bind(barrier):
    global _BARRIER
    _BARRIER=barrier

def classify(text,status,returncode=None):
    """A negative code alone does not prove a transient; explicit method evidence wins."""
    patterns={
      'XTB_TOO_MANY_NEIGHBOURS':r'too\s+many\s+neighbou?rs',
      'XTB_SCC_NOT_CONVERGED':r'(?:SCC|SCF)\s+(?:iterations?\s+)?(?:not\s+converged|failed\s+to\s+converge|did\s+not\s+converge)|(?:SCC|SCF)\s+convergence\s+failed',
      'XTB_METHOD_OR_PARAMETER_UNSUPPORTED':r'(?:method|parameter|parametrization|element).{0,100}(?:not\s+(?:available|supported|implemented)|unsupported|missing)|(?:not\s+implemented|not\s+available).{0,80}(?:IPEA|GFN|element)',
    }
    evidence=[{'code':code,'token':m.group(0)} for code,pattern in patterns.items() for m in [re.search(pattern,text,re.I)] if m]
    if evidence:return {'classification':'DETERMINISTIC_METHOD_FAILURE','retry_allowed':False,'evidence':evidence}
    if status=='TIMEOUT':return {'classification':'TIMEOUT_ONE_CLEANUP_RETRY','retry_allowed':True,'evidence':[]}
    if status=='NODE_FAILURE':return {'classification':'NODE_FAILURE_ONE_CLEANUP_RETRY','retry_allowed':True,'evidence':[]}
    if (isinstance(returncode,int) and returncode<0) or status=='SIGNAL_TERMINATION':
        return {'classification':'UNRESOLVED_SIGNAL_REQUIRES_EVIDENCE','retry_allowed':None,'evidence':[]}
    return {'classification':'RECORDED_SCIENTIFIC_FAILURE_NO_TRANSIENT_EVIDENCE','retry_allowed':False,'evidence':[]}

def readonly(path):
    db=sqlite3.connect('file:'+quote(str(Path(path).absolute()))+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    db.execute('PRAGMA query_only=ON');return db

def gather(source_run):
    source_run=Path(source_run);run=json.loads((source_run/'phase_0/run.json').read_text());opt=run['options']
    db=readonly(opt['queue']);items=[]
    try:
        rows=db.execute("SELECT molecule_id,state,attempt,archive_path,receipt_json FROM molecules WHERE state='RETRY_PENDING' ORDER BY molecule_id").fetchall()
        refs=json.loads((source_run/'phase_0/family_exports.json').read_text())['references']
        for row in rows:
            receipt=json.loads(row['receipt_json'])
            for calc,counts in receipt['counts'].items():
                if counts['success']<counts['total']:
                    items.append({'source_run':str(source_run),'molecule_id':row['molecule_id'],'attempt':row['attempt'],
                       'archive_path':row['archive_path'],'dictionaries':opt['dictionaries'],'calc_type':calc,
                       'references':[ref for ref in refs if ref['family']=={'xtb_vipea':'xtb_vipea'}.get(calc,calc)],'options':opt})
    finally:db.close()
    return items

def inspect_one(item):
    from wp5_archive_v4 import ArchiveReader
    from wp5_parquet import decode
    import pyarrow.parquet as pq
    entries=json.loads(Path(item['options']['registry']).read_text())['entries']
    paths={int(e['registry_id']):e['source_path'] for e in entries if e['task']==item['calc_type']}
    details={}
    for ref in item['references']:
        if sha(ref['path'])!=ref['sha256']:raise ValueError('IMMUTABLE_FAMILY_SHA_DIFFERS')
        for batch in pq.ParquetFile(ref['path']).iter_batches(batch_size=64):
            for row in batch.to_pylist():
                if row['molecule_id']!=item['molecule_id'] or row['calc_type']!=item['calc_type']:continue
                cells={paths.get(int(c['registry_id']),str(c['registry_id'])):decode(c) for c in row['values']}
                details[row['record_id']]={'source_status':row['source_status'],'scope_status':row['status'],
                   'failure_code':row.get('failure_code'),'failure_reason':cells.get('detail.failure_reason'),
                   'returncode':cells.get('detail.returncode')}
    reader=ArchiveReader(item['archive_path'],item['dictionaries']);cases=[]
    try:
        for record_id,calc in reader.db.execute('SELECT record_id,calc_type FROM records WHERE molecule_id=? AND calc_type=? ORDER BY record_id',(item['molecule_id'],item['calc_type'])):
            raw=reader.get(record_id,calc);detail=details.get(record_id,{'source_status':raw['source_status'],'scope_status':raw['scope_status']})
            if detail['scope_status']=='SUCCESS':continue
            texts=[];files=[]
            for f in raw['output_files'] or []:
                name=f['name'];data=f['data'];files.append({'name':name,'bytes':len(data),'sha256':f['sha256']})
                if name.endswith(('.out','.err','.log')) or name in {'stderr','stdout'}:
                    texts.append((name,data.decode('utf8','replace')))
            text='\n'.join(value for name,value in texts)
            tokens=[]
            lines=text.splitlines()
            for index,line in enumerate(lines):
                if re.search(r'error|fatal|fail|converg|neighbou?r|signal|abort|stop|backtrace|forrtl|invalid|parameter',line,re.I):
                    tokens.append({'line':index+1,'text':line[:500]})
            cases.append({'record_id':record_id,'molecule_id':item['molecule_id'],'calc_type':calc,'source_run':item['source_run'],
               'archive_path':item['archive_path'],'attempt':item['attempt'],'detail':detail,'files':files,
               'output_tokens':tokens[-60:],'output_tail':lines[-25:],'classification':classify(text+'\n'+str(detail.get('failure_reason') or ''),detail['source_status'],detail.get('returncode'))})
    finally:reader.close()
    return cases

def lane_task(items):
    _BARRIER.wait(timeout=120)
    return {'pid':os.getpid(),'cases':[case for item in items for case in inspect_one(item)]}

def main():
    p=argparse.ArgumentParser();p.add_argument('--source-run',action='append',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--workers',type=int,default=24);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text());assert classify('SCC not converged','CALCULATION_FAILED',-6)['retry_allowed'] is False
        assert classify('terminated signal','SIGNAL_TERMINATION',-6)['retry_allowed'] is None
        print('AST_CLASSIFICATION_PASS_NO_QM');return
    if a.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers:raise ValueError('ALLOCATED_AT_LEAST16_WORKERS_REQUIRED')
    if not a.source_run or not a.output:raise ValueError('source-run/output required')
    started=time.monotonic();items=[item for root in a.source_run for item in gather(root)]
    bins=[items[i::a.workers] for i in range(a.workers)]
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=bind,initargs=(barrier,)) as pool:
        results=list(pool.map(lane_task,bins))
    report={'status':'RAW_EVIDENCE_REVIEW_COMPLETE','job_id':os.environ.get('SLURM_JOB_ID'),'source_sha256':sha(__file__),
      'worker_pids':sorted({r['pid'] for r in results}),'workers':a.workers,'elapsed_seconds':time.monotonic()-started,
      'cases':[case for r in results for case in r['cases']],'new_QM':False,'queue_written':False,'source_runs':[str(root) for root in a.source_run]}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.output.exists():raise FileExistsError('New immutable report required')
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'report':str(a.output),'cases':len(report['cases']),'worker_pids':len(report['worker_pids'])}))
if __name__=='__main__':main()
