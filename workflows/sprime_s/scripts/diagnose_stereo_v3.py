"""Check the reviewed parity/3D fix against the exact 28 original stereo flags."""
import concurrent.futures as cf,multiprocessing as mp,json,os
from prepare import ROOT,save
from sprime import read,graph,fix_stereo,worker_init,field

def check(task):
    mid,rows=task
    lowest=min(rows,key=lambda r:(float(r['energy_raw']) if r['energy_raw'] is not None else float('inf'),r['record_id']))
    raw=read(lowest);mol,_,_=graph(raw)
    result={'molecule_id':mid,'source_record_id':lowest['record_id'],'smiles':str(field(raw,'smiles'))}
    try:
        source,signature=fix_stereo(mol,result['smiles']);result.update(status='STEREO_FIXED',stereo_source=source,stereo_signature=signature)
    except Exception as exc:result.update(status='UNRESOLVED',error=repr(exc))
    return result

def main():
    import pyarrow.parquet as pq
    cases=json.loads((ROOT/'reports/stereo_diagnosis.json').read_text())
    mids={r['molecule_id'] for r in cases};index={m:[] for m in mids}
    rows=pq.read_table(ROOT/'prepared/pilot_records.parquet',columns=['molecule_id','record_id','source_path','real_index','record_payload_sha256','total_atoms','energy_raw'],filters=[('file_group','=',1)]).to_pylist()
    for r in rows:
        if r['molecule_id'] in index:index[r['molecule_id']].append(r)
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=worker_init) as pool:results=list(pool.map(check,sorted(index.items())))
    save(ROOT/'reports/stereo_diagnosis_v3.json',results)
    print(json.dumps({'cases':len(results),'fixed':sum(r['status']=='STEREO_FIXED' for r in results),'remaining':[r for r in results if r['status']!='STEREO_FIXED']}))

if __name__=='__main__':main()
