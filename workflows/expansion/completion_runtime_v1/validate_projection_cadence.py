"""Bounded Main20 paired production-writer test; no NN recalculation or Alpha import."""
import argparse,ast,hashlib,json,os,pathlib,socket,struct,time,types
BEFORE='        result.append(closed(path, batch.num_rows, bucket, journal))\n        guard.poll(force=True)'
AFTER='        result.append(closed(path, batch.num_rows, bucket, journal))\n        guard.poll()  # Retain the real 30-second resource cadence across small closed projections.'
def need(value,message):
    if not value:raise RuntimeError(message)
def ref(path):
    path=pathlib.Path(path);before=path.stat()
    with path.open('rb')as f:
        first=os.fstat(f.fileno());raw=f.read();last=os.fstat(f.fileno())
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_uid,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    need(stamp(before)==stamp(first)==stamp(last)==stamp(path.stat()),'Same-FD immutable fixture source')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def writer(path):
    tree=ast.parse(path.read_bytes(),filename=str(path))
    functions=[node for node in tree.body if isinstance(node,ast.FunctionDef)and node.name in('closed','write_arrow')]
    need({node.name for node in functions}=={'closed','write_arrow'},'Actual original writer and close bodies')
    namespace=dict(Path=pathlib.Path,os=os,json=json,require=need,Q=types.SimpleNamespace(reference=ref))
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(path),'exec'),namespace)
    return namespace['write_arrow']
class ObserveGuard:
    def __init__(self,fail_at=None):self.calls=[];self.fail_at=fail_at
    def poll(self,force=False,reserve=0):
        self.calls.append(force)
        if len(self.calls)==self.fail_at:raise RuntimeError('ACTUAL_POLL_ERROR_PROPAGATED')
def run(old,new,scores,origin,out):
    import duckdb,pyarrow.parquet as pq
    need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20','Bounded Main20 metadata validation only')
    wall=time.monotonic();cpu=time.process_time();old_text=old.read_text();fresh=new.read_text()
    need(old_text.count(BEFORE)==1 and fresh.count(AFTER)==1 and fresh.replace(AFTER,BEFORE)==old_text,'Whole module byte identity after exactly one resource-call inversion')
    source=json.loads(origin.read_bytes());score_ref=ref(scores);actual=source['source_score_part_reference']
    need(score_ref['bytes']==actual['bytes']and score_ref['sha256']==actual['sha256']and source['source_job_id']=='1885267'and source['not_a_full_source_completion']is True,'Byte-identical real Alpha score fixture, never fake full completion')
    out.mkdir(mode=0o700,parents=True,exist_ok=False);db=duckdb.connect()
    try:
        db.read_parquet(str(scores)).create_view('score');sql='SELECT *FROM score LIMIT 13'
        expected=db.execute(sql).fetch_arrow_table();entries=[]
        for name,path in(('previous',old),('fresh',new)):
            guard=ObserveGuard();journal_path=out/(name+'.jsonl')
            with journal_path.open('x')as journal:parts=writer(path)(db,sql,out/name,'0',journal,guard,rows_per_part=5)
            table=__import__('pyarrow').concat_tables([pq.read_table(part['path'])for part in parts])
            need(table.equals(expected)and sum(part['rows']for part in parts)==13,'Real complete row/schema/value preservation')
            need([struct.pack('<d',v)for v in table['nearest_v1_tanimoto'].to_pylist()]==[struct.pack('<d',v)for v in expected['nearest_v1_tanimoto'].to_pylist()],'All native sample F64 bits unchanged')
            need(guard.calls==([True]*3 if name=='previous'else[False]*3),'Only declared forced-poll scheduling differs')
            lines=journal_path.read_text().splitlines();need(len(lines)==3 and journal_path.read_bytes().endswith(b'\n'),'All original close/fsync/journal checkpoints retained')
            entries.append(dict(source_reference=ref(path),parts=parts,poll_force_arguments=guard.calls,journal_reference=ref(journal_path)))
        need([(v['bytes'],v['sha256'])for v in entries[0]['parts']]==[(v['bytes'],v['sha256'])for v in entries[1]['parts']],'Paired Parquet bodies byte-identical, beyond equal numerical values')
        failing=ObserveGuard(fail_at=2);journal_path=out/'failure.jsonl'
        with journal_path.open('x')as journal:
            try:writer(new)(db,sql,out/'interrupted','0',journal,failing,rows_per_part=5)
            except RuntimeError as exc:need(str(exc)=='ACTUAL_POLL_ERROR_PROPAGATED','Exact resource error propagated')
            else:raise RuntimeError('Resource exception swallowed')
        closed=[json.loads(line)for line in journal_path.read_text().splitlines()]
        need([part['rows']for part in closed]==[5,5]and not(out/'interrupted'/'part_000002.parquet').exists(),'Two valid immutable closed outputs retained before resource stop')
        for part in closed:need(ref(part['path'])=={key:part[key]for key in('path','bytes','sha256')},'Interrupted closed data retained unchanged')
        before=[ref(part['path'])for part in entries[1]['parts']]
        with(out/'overwrite_rejected.jsonl').open('x')as journal:
            try:writer(new)(db,sql,out/'fresh','0',journal,ObserveGuard(),rows_per_part=5)
            except RuntimeError as exc:need(str(exc)=='Never overwrite a closed shard','Existing closed-part overwrite rejected')
            else:raise RuntimeError('Closed part overwritten')
        need(before==[ref(part['path'])for part in entries[1]['parts']],'Prior paired data byte-identical after rejected overwrite')
    finally:db.close()
    result=dict(schema='PUBCHEM_PROJECTION_CADENCE_NATIVE_VALIDATION_V1',status='PASS',actual=dict(endpoint='202.38.247.57:22',uid=os.getuid(),node=socket.gethostname(),pid=os.getpid()),tests=3,source_score_fixture=actual,replica_score_fixture=score_ref,fixture_rows=13,paired_writers=entries,whole_module_identical_after_one_resource_inversion=True,paired_Parquet_bytes_and_all_F64_equal=True,resource_poll_exceptions_propagate_and_closed_outputs_retained=True,closed_output_overwrite_rejected=True,original_guard_class_and_scientific_SQL_unchanged=True,new_NN_or_chemistry_calls=0,full_pool_completion_or_speedup_not_certified=True,wall_seconds=time.monotonic()-wall,process_CPU_seconds=time.process_time()-cpu,validator_source=ref(__file__))
    path=out/'result.json'
    with path.open('x')as f:json.dump(result,f,sort_keys=True);f.write('\n')
    print(json.dumps(dict(result_reference=ref(path),tests=3,status='PASS',wall_seconds=result['wall_seconds'])),flush=True)
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in('old','new','scores','origin','output'):parser.add_argument('--'+name,required=True,type=pathlib.Path)
    args=parser.parse_args();run(args.old,args.new,args.scores,args.origin,args.output)
if __name__=='__main__':main()
