"""One post-C3 closed-output metadata pass; NOPOLAR archive calibration, no QM.

Use >=16 real workers. Repeated rounds are execution observations, never new
unique molecules. Initial closed round selection is used for unique-pilot
comparison, and failures/raw/Parquet are left intact.
"""
from __future__ import annotations
import argparse,ast
from collections import Counter,defaultdict
import concurrent.futures,hashlib,json,multiprocessing,os
from pathlib import Path
import sys,time
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
DEPS=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps')
sys.path.insert(0,str(DEPS))

def read(path):return json.loads(Path(path).read_text())
def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):value.update(block)
    return value.hexdigest()
def save(path,value):
    pending=Path(str(path)+'.pending');pending.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');pending.replace(path)
def init(barrier):
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);barrier.wait(timeout=180)
def one(item):
    import pyarrow.parquet as pq
    node,round_,receipt=item;ref=receipt['parquet'];path=Path(ref['path'])
    issue=None
    if path.stat().st_size!=ref['bytes'] or sha(path)!=ref['sha256']:issue='Closed C3 Parquet binding mismatch'
    rows=pq.read_table(path,columns=['record_id','size_stratum','task','status','archive_bytes','details_json'],use_threads=False).to_pylist()
    keys={row['size_stratum'] for row in rows};calls=[];percall=0;missing=0
    for row in rows:
        detail=json.loads(row['details_json']);amount=detail.get('archive',{}).get('per_call_compressed_bytes',row['archive_bytes'])
        launched=bool(detail.get('argv')) and not row['status'].startswith(('SKIPPED_','Q03_SOURCE','NOT_STARTED_'))
        if amount is None:
            if launched:missing+=1
            amount=0
        percall+=amount
        calls.append({'task':row['task'],'status':row['status'],'record_id':row['record_id'],'percall_compressed_bytes':amount})
    archive=receipt.get('archive');size=archive['bytes'] if archive else (0 if not percall else None)
    if archive and Path(archive['path']).stat().st_size!=archive['bytes']:issue='Closed C3 archive bytes differ'
    if len(keys)!=1:issue='Molecule stratum differs'
    return {'node':node,'round':round_,'molecule_id':receipt['molecule_id'],'size_stratum':next(iter(keys)),
        'records':receipt['records'],'outcomes':len(rows),'closed_archive_bytes':size,'percall_compressed_bytes':percall,
        'missing_measurements':missing,'issue':issue,'worker_pid':os.getpid(),'calls':calls,
        'source_Parquet':ref,'source_archive':archive}
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workers',type=int,default=16)
    parser.add_argument('--output',default=str(ROOT/'c_engineering/c3_archive_recheck.json'));parser.add_argument('--check',action='store_true');args=parser.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());print(json.dumps({'status':'AST_PASS','QM_started':False}));return 0
    if args.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<args.workers:raise ValueError('16 actual allocated workers required')
    sources=[];probe_refs=[]
    for path in sorted((ROOT/'c_engineering/nodes').rglob('node_probe_report.json')):
        probe=read(path);probe_refs.append({'path':str(path),'sha256':sha(path),'node':probe['hostname'],'job_id':probe['job_id']})
        for round_ in probe['rounds']:
            if not round_.get('summary'):continue
            for receipt in round_['summary']['receipts']:
                if receipt.get('status')=='COMPLETE_WITH_RECORDED_OUTCOMES':sources.append((probe['hostname'],round_['round'],receipt))
    context=multiprocessing.get_context('spawn');barrier=context.Barrier(args.workers);start=time.monotonic()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,initializer=init,initargs=(barrier,)) as pool:rows=list(pool.map(one,sources,chunksize=1))
    pids=sorted({row['worker_pid'] for row in rows})
    if len(pids)<16:raise ValueError('Fewer than16 actual metadata reader workers')
    issues=[{'node':row['node'],'round':row['round'],'molecule_id':row['molecule_id'],'issue':row['issue'],'missing':row['missing_measurements']}
        for row in rows if row['issue'] or row['missing_measurements'] or row['closed_archive_bytes'] is None]
    first={}
    for row in sorted(rows,key=lambda row:(row['round'],row['node'])):first.setdefault(row['molecule_id'],row)
    output=[]
    for scope,selected in (('ALL_RECORDED_EXECUTIONS',rows),('UNIQUE_MOLECULE_FIRST_CLOSED_ROUND',list(first.values()))):
        for key in sorted({row['size_stratum'] for row in selected}):
            group=[row for row in selected if row['size_stratum']==key];closed=sum(row['closed_archive_bytes'] or 0 for row in group);percall=sum(row['percall_compressed_bytes'] for row in group)
            valid=all(not row['issue'] and not row['missing_measurements'] and row['closed_archive_bytes'] is not None for row in group)
            output.append({'scope':scope,'size_stratum':key,'molecule_executions':len(group),'unique_molecules':len({row['molecule_id'] for row in group}),
                'record_executions':sum(row['records'] for row in group),'unique_records':len({call['record_id'] for row in group for call in row['calls']}),
                'closed_archive_bytes':closed,'percall_compressed_bytes':percall,'archive_pack_factor':closed/percall if percall and valid else None})
    old_path=OLD/'wp4_storage_benchmark/job_4513016/benchmark_summary.json';old=read(old_path) if old_path.is_file() else None
    report={'status':'C3_NOPOLAR_ARCHIVE_METADATA_RECHECK_CLOSED','nodes_closed':len(probe_refs),'probe_refs':probe_refs,
        'unique_molecules':len(first),'molecule_executions':len(rows),'actual_worker_pids':pids,'calibrations':output,
        'WITH_POLAR_full10020_reference':old['storage']['strata'] if old else None,
        'issues':issues,'source_refs':[{'node':row['node'],'round':row['round'],'molecule_id':row['molecule_id'],'parquet':row['source_Parquet'],'archive':row['source_archive']} for row in rows],
        'science_and_all_failure_outputs_preserved':True,'raw_repacked_or_deleted':False,'QM_started':False,
        'seconds':time.monotonic()-start,'script_sha256':sha(__file__),
        'scope_note':'Fresh C3 NOPOLAR resource-test output; repeated benchmark round executions do not enlarge unique population. Node subsets/partial molecules explicitly remain smaller than full10020 universe. Same-pack future raw-policy estimate remains a calibration model, not actual selective repacking.'}
    output_path=Path(args.output).absolute()
    if not output_path.is_relative_to(ROOT/'c_engineering'):raise ValueError('Own output only')
    save(output_path,report);print(json.dumps({'status':report['status'],'nodes':len(probe_refs),'unique_molecules':len(first),'executions':len(rows),'issues':len(issues)}));return 0
if __name__=='__main__':raise SystemExit(main())
