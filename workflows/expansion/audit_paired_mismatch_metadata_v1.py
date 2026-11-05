"""Read only the completed paired diagnostic database; no chemistry or source replay."""
import argparse,hashlib,json,os,pathlib,socket,sqlite3
BASE=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
RECEIPT=BASE/'artifacts/expansion/diagnostics/paired_prefix_cpu_v1/candidate_evaluation/receipt.json'

def ref(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        before=os.fstat(f.fileno());assert before.st_uid==1278
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        after=os.fstat(f.fileno())
    assert (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
    return {'path':str(path),'bytes':before.st_size,'sha256':h.hexdigest()}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-17'
    assert a.output.parent==BASE/'control' and not a.output.exists()
    receipt=json.loads(RECEIPT.read_text());pin=receipt['paired_result_database'];path=pathlib.Path(pin['path'])
    assert path.parent==RECEIPT.parent and not path.is_symlink() and ref(path)==pin
    db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('PRAGMA query_only=ON')
    queries={
        'paired_difference_keys':"SELECT j.key,count(*) FROM mismatches m,json_each(m.details,'$.comparisons.paired_all_fields') j GROUP BY j.key",
        'historical_difference_keys':"SELECT j.key,count(*) FROM mismatches m,json_each(m.details,'$.comparisons.historical_stored_all_fields') j GROUP BY j.key",
        'mismatch_codes':"SELECT j.value,count(*) FROM mismatches m,json_each(m.details,'$.mismatch_codes') j GROUP BY j.value",
        'original_exception_types':"SELECT json_extract(details,'$.pair.legacy.exception_type'),json_extract(details,'$.pair.legacy.phase'),count(*) FROM feature_failure_cases GROUP BY 1,2",
        'oldpass_fragment_audit_missing':"SELECT count(*) FROM paired_cases WHERE classification='OLD_PASS_HAS_DRIFT' AND json_type(pair,'$.fragment_order_audit')='null'"}
    results={name:db.execute(sql).fetchall() for name,sql in queries.items()}
    samples=[]
    sql="SELECT p.ordinal,p.cid,json_extract(p.pair,'$.source_smiles'),json_extract(p.pair,'$.legacy.output.generic_ring_systems'),json_extract(p.pair,'$.candidate.output.generic_ring_systems'),m.details FROM mismatches m JOIN paired_cases p USING(ordinal,cid) ORDER BY p.ordinal LIMIT 6"
    for ordinal,cid,smiles,old,new,details in db.execute(sql):
        samples.append({'ordinal':ordinal,'cid':cid,'smiles':smiles,'old_ring':json.loads(old) if old else old,
            'proposed_ring':json.loads(new) if new else new,'details':json.loads(details)})
    db.close();assert ref(path)==pin
    result={'schema':'PAIRED_PREFIX_COMPLETED_MISMATCH_METADATA_AUDIT_V1','status':'READONLY_CAUSE_AUDIT_NOT_ACCEPTANCE',
        'receipt':ref(RECEIPT),'database':pin,'queries':queries,'results':results,'samples':samples,
        'chemical_functions_called':False,'source_raw_or_legacy_pool_read':False,'repair_or_release':False,
        'source_reference':ref(pathlib.Path(__file__).absolute())}
    raw=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False).encode()+b'\n';assert len(raw)<128*1024
    with a.output.open('xb') as f:f.write(raw)
    print(json.dumps({'reference':ref(a.output),'results':results}))
if __name__=='__main__':main()