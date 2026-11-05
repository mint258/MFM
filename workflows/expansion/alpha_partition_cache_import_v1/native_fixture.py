"""Main20 bounded validation of copied real score rows; no NN/chemistry or import."""
import argparse,hashlib,json,os,pathlib,socket,time
from . import checks

def ref(path):
    path=pathlib.Path(path);raw=path.read_bytes();return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def main():
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    ap=argparse.ArgumentParser();ap.add_argument('--origin',type=pathlib.Path,required=True);ap.add_argument('--scores',type=pathlib.Path,required=True);ap.add_argument('--keys',type=pathlib.Path,required=True);ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
    checks.need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20','Actual Main20 bounded metadata test')
    start=time.perf_counter();cpu=time.process_time();origin=json.loads(a.origin.read_bytes())
    checks.need(origin['source_endpoint']=='218.192.171.238:22'and origin['source_uid']==1264 and origin['reference_records']==1196122,'Honest Alpha source identity, no Main relabel')
    replicas=[]
    for source,path in((origin['source_score_part_reference'],a.scores),(origin['reference_keys'],a.keys)):
        local=ref(path);checks.need((source['bytes'],source['sha256'])==(local['bytes'],local['sha256']),'Explicit whole-SHA byte-identical fixture replica');replicas.append(dict(source_reference=source,replica_reference=local))
    checks.schema(pq.read_schema(a.scores));payload=a.keys.read_bytes();n=1196122;checks.need(len(payload)==n*28,'Complete original key ordinal map')
    db=duckdb.connect();db.execute('SET threads=2');db.execute("SET memory_limit='1GB'");checks.install(db)
    db.execute('CREATE TABLE ref_keys(ordinal BIGINT,full_key VARCHAR)')
    for start_key in range(0,n,65536):
        rows=[dict(ordinal=i,full_key=payload[i*28:i*28+27].decode('ascii'))for i in range(start_key,min(start_key+65536,n))];db.register('_keys',pa.Table.from_pylist(rows));db.execute('INSERT INTO ref_keys SELECT *FROM _keys');db.unregister('_keys')
    db.read_parquet(str(a.scores)).create_view('incoming');count=checks.validate(db,'incoming',['6'],n,origin['source_score_part_reference']['rows'])
    db.execute('CREATE TABLE existing AS SELECT *FROM incoming LIMIT 1024');checks.validate(db,'existing',['6'],n)
    overlap,new=checks.overlap_and_new(db);checks.need((overlap,new)==(1024,count-1024),'Actual native rows retain exact overlapping results once')
    db.execute('DROP TABLE new_scores');fp,e=db.execute('SELECT ecfp4_2048_hex,evaluated_references FROM existing ORDER BY ecfp4_2048_hex LIMIT 1').fetchone();delta=-1 if e else 1
    db.execute('UPDATE existing SET evaluated_references=evaluated_references+?,strictly_bound_pruned_references=strictly_bound_pruned_references-? WHERE ecfp4_2048_hex=?',[delta,delta,fp]);checks.validate(db,'existing',['6'],n)
    try:checks.overlap_and_new(db)
    except ValueError as exc:checks.need('all9'in str(exc),'Expected exact-counter mismatch failure')
    else:raise ValueError('Actual native counter mutation was accepted')
    db.close();result=dict(schema='ALPHA_PARTITION_IMPORT_NATIVE_FIXTURE_RESULT_V1',status='PASS',actual=dict(endpoint='202.38.247.57:22',uid=os.getuid(),node=socket.gethostname(),pid=os.getpid()),origin=origin,origin_replica_reference=ref(a.origin),replicas=replicas,score_rows=count,reference_records=n,matching_overlap=overlap,new_rows=new,all_real_score_fields_and_F64_and_original_key_ordinals_pass=True,changed_native_counter_with_equal_reference_sum_rejected=True,wall_seconds=time.perf_counter()-start,process_CPU_seconds=time.process_time()-cpu,source_references=[ref(__file__),ref(checks.__file__)],no_scientific_NN_recomputation_or_Alpha_import=True,full_rescue_completion_not_certified=True)
    with a.output.open('x')as f:json.dump(result,f,sort_keys=True);f.write('\n')
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()