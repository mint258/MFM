"""Compact a closed EA diagnostic on its CPU host; metadata only, no source reads."""
import argparse,collections,hashlib,json,os,pathlib,socket,stat
BASE=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
INPUT=BASE/'artifacts/labels/ea_diagnostic_v1/dv1_ea_known_seven_io_v4/diagnostic.json'

def reference(path,raw):return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def read_metadata(path,limit):
    assert not path.is_symlink()
    with path.open('rb') as f:
        before=os.fstat(f.fileno());assert stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size<=limit
        raw=f.read(limit+1);after=os.fstat(f.fileno())
    assert len(raw)==before.st_size and (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
    return raw

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args();assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-17'
    assert a.output.parent==BASE/'control' and not a.output.exists()
    raw=read_metadata(INPUT,8*1024**2);d=json.loads(raw)
    assert d['status']=='ACTUAL_BOUNDED_DIAGNOSIS_CAUSAL_REVIEW_PENDING'
    assert len(d['cases'])==7 and len(d['formal_context_rows'])==14 and len(set(d['actual_worker_pids']))==16
    assert d['new_masks']==0 and d['new_QM_calls']==0 and d['source_values_or_status_changed'] is False
    workers=d['worker_receipts'];assert len(workers)==16
    io=[w['parquet_io_lifecycle'] for w in workers]
    assert all(r['opens']==r['closes'] and r['current_open_handles']==0 and r['max_simultaneously_open_handles']==1 for r in io)
    intentpath=pathlib.Path(d['root_preflight']['path'])
    assert reference(intentpath,read_metadata(intentpath,2*1024**2))==d['root_preflight']
    monitorpath=BASE/'artifacts/cpu_analysis_guards/dv1_ea_known_seven_io_v4/closure.json'
    monitorraw=read_metadata(monitorpath,2*1024**2);monitor=json.loads(monitorraw)
    assert monitor['job_id']=='4520570' and monitor['status']=='COMPLETED_NO_MEMORY_DENIAL'
    assert monitor['intent_reference']==d['root_preflight'] and monitor['first_denial'] is None and monitor['durable_evidence_exported']
    summary={'schema':'EA_CLOSED_CPU_DIAGNOSTIC_COMPACT_METADATA_V1','status':d['status'],
        'job_id':'4520570','diagnostic_reference':reference(INPUT,raw),'monitor_reference':reference(monitorpath,monitorraw),
        'cases':len(d['cases']),'contexts':len(d['formal_context_rows']),'actual_workers':len(workers),
        'max_worker_rss_bytes':max(w['maxrss_bytes'] for w in workers),'elapsed_worker_phase_seconds':d['elapsed_seconds'],
        'parquet_handles_opened':sum(r['opens'] for r in io),'parquet_handles_closed':sum(r['closes'] for r in io),
        'parquet_reuses':sum(r['reuses'] for r in io),'max_simultaneous_handles_per_worker':1,'all_handles_closed':True,
        'raw_evidence_counts':dict(collections.Counter(r['evidence_status'] for r in d['raw_context'])),
        'raw_outputs_found':sum(bool(r['canonical_output_found']) for r in d['raw_context']),
        'comparisons':d['comparisons'],'cause':d['cause'],'new_QM_calls':0,'new_masks':0,
        'guide_approximately_390_population_reestablished':d['guide_approximately_390_SUCCESS_NULL_population_count_reestablished'],
        'source_reference':reference(pathlib.Path(__file__),pathlib.Path(__file__).read_bytes()),
        'metadata_only':True,'original_parquet_or_archives_read':False}
    payload=json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False).encode()+b'\n';assert len(payload)<32768
    with a.output.open('xb') as f:f.write(payload)
    print(json.dumps({'status':'CLOSED_METADATA_COMPACTED','reference':reference(a.output,payload),
        'cases':7,'contexts':14,'workers':16,'max_worker_rss_bytes':summary['max_worker_rss_bytes'],
        'raw_outputs_found':summary['raw_outputs_found'],'diagnostic_reference':summary['diagnostic_reference']}))
if __name__=='__main__':main()