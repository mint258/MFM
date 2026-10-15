"""Current-policy six-node G6:20 whole molecules,16+4 resume,one cleanup,output-only archive."""
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
def run_phase(a,out,base,phase,hours,cap=0,cleanup=False):
    root=out/phase;command=base+['--run-root',str(root),'--claim-cap',str(cap),'--hours',str(hours)]
    if cleanup:command+=['--mode','cleanup','--task-id','cleanup_'+socket.gethostname().split('.')[0].split('-')[-1]]
    started=time.time();p=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True)
    save(out/(phase+'_invocation.json'),{'argv':command,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'seconds':time.time()-started})
    if p.returncode:raise RuntimeError('CURRENT_G6_RUNNER_NONZERO:'+phase)
    info=json.loads((root/'completion.json').read_text())
    if info['error'] or not info['scratch_clean'] or any(row['error_count'] for row in info['workers']):raise ValueError('CURRENT_G6_PIPELINE_OR_SCRATCH_FAILURE:'+phase)
    if any(not row['cleanup']['work_root_removed'] or not row['cleanup']['LMDB_handles_closed'] for row in info['workers']):raise ValueError('CURRENT_G6_WORKER_CLEANUP_FAILURE')
    return root,info
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
                if receipt.get('execution_id')==execution and Path(latest[molecule]['archive_path']).name==Path(info['archive']['path']).name:
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
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('dictionaries','audit-membership','reproduction-package','production-contract','out'):p.add_argument('--'+name,type=Path)
    p.add_argument('--protocol',type=Path,default=ROOT/'configs/protocol.json');p.add_argument('--node-authority',type=Path,default=ROOT/'gates/wp5_node_replacement_user_approved.json')
    p.add_argument('--hours',type=float,default=8);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('CURRENT_POLICY_G6_AST_PASS_NO_QM');return
    node=socket.gethostname().split('.')[0];designed={'compute-0-12':'compute-0-15','compute-0-13':'compute-0-16'}.get(node,node);job=os.environ['SLURM_JOB_ID']
    if node not in NODES or int(os.environ['SLURM_CPUS_PER_TASK'])<24:raise ValueError('CURRENT_G6_ACTUAL_APPROVED24_CPU_REQUIRED')
    if not all((a.dictionaries,a.audit_membership,a.reproduction_package,a.production_contract)):raise ValueError('Actual closed current-policy package/audit/contract/dictionaries required')
    from wp5_submit_formal_v9 import validate_current_contract
    validate_current_contract(a.production_contract,a.node_authority)
    a.out=a.out or ROOT/'gates/g6_current'/node/('job_'+job);out=a.out;out.mkdir(parents=True,exist_ok=False)
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    db=duckdb.connect();db.execute('SET threads=24');db.execute("SET memory_limit='20GB'")
    def q(path):return "'"+str(path).replace("'","''")+"'"
    molpath=ROOT/"population/molecule_index.parquet"
    pilot=SCREEN/"c_engineering/xyz/analysis_geometry.parquet"
    db.execute("CREATE VIEW eligible AS SELECT m.* FROM read_parquet("+q(molpath)+") m "
               "WHERE molecule_id IN (SELECT DISTINCT molecule_id FROM read_parquet("+q(pilot)+"))")
    # Twenty whole molecules in one test cover all formal size strata, five
    # file groups and the pilot-eligible largest total-atom representative.
    # Node-specific ordering gives additional samples; the largest is shared.
    chosen=[];selected_info={}
    columns="molecule_id,records,max_heavy_atoms,max_total_atoms,file_group"
    def add(row):
        if row[0] not in selected_info:chosen.append((row[0],));selected_info[row[0]]=row
    def pick(condition,params=()):
        clause=" AND molecule_id NOT IN ("+",".join(q(molecule) for molecule in selected_info)+")" if selected_info else ""
        row=db.execute("SELECT "+columns+" FROM eligible WHERE "+condition+clause+
                       " ORDER BY CASE WHEN records>=4 THEN 0 ELSE 1 END,md5(molecule_id || ?) LIMIT 1",tuple(params)+(designed,)).fetchone()
        if row is None:raise ValueError("G6_REQUIRED_COHORT_HAS_NO_ELIGIBLE_WHOLE_MOLECULE")
        add(row)
    largest=db.execute("SELECT "+columns+" FROM eligible ORDER BY max_total_atoms DESC,max_heavy_atoms DESC,molecule_id LIMIT 1").fetchone()
    if largest is None:raise ValueError("G6_PILOT_ELIGIBLE_FRAME_EMPTY")
    add(largest)
    ranges=[(0,10),(11,20),(21,30),(31,50),(51,75),(76,100),(101,1000000)]
    for lower,upper in ranges:
        if not any(lower<=row[2]<=upper for row in selected_info.values()):
            pick("max_heavy_atoms BETWEEN ? AND ?",(lower,upper))
    for group in range(1,6):
        if not any(row[4]==group for row in selected_info.values()):pick("file_group=?",(group,))
    while len(chosen)<20:
        group=min(range(1,6),key=lambda value:(sum(row[4]==value for row in selected_info.values()),value))
        pick("file_group=?",(group,))
    ids=[row[0] for row in chosen]
    if len(ids)!=20 or len(set(ids))!=20:raise ValueError("G6_WHOLE_MOLECULE_SELECTION_NOT20")
    save(out/"selected_molecules.json",{"selection":"all7strata/all5filegroups/piloteligible largest; node-specific deterministic ordering",
        "node":node,"source_pilot_geometry_sha256":digest(pilot),"largest_pilot_eligible_molecule":largest[0],
        "largest_total_atoms":largest[3],"molecules":[dict(zip(columns.split(","),row)) for row in selected_info.values()]})
    db.register("selected",pa.table({"molecule_id":ids}))
    directory=out/"record_index";directory.mkdir()
    db.execute("COPY (SELECT p.* FROM read_parquet("+q(ROOT/"population/formal_record_index.parquet")+
               ") p JOIN selected s USING(molecule_id) ORDER BY p.molecule_id,p.conformer_id,p.record_id) TO "+
               q(directory/"records.parquet")+" (FORMAT PARQUET, COMPRESSION ZSTD)")
    stats=db.execute("SELECT molecule_id,records,max_heavy_atoms,max_total_atoms,file_group FROM eligible JOIN selected USING(molecule_id)").fetchall()
    measured=db.execute("SELECT a.molecule_id,a.planned_allocated_seconds FROM read_parquet("+
                        q(ROOT/"packing/molecule_assignments.parquet")+") a JOIN selected s USING(molecule_id)").fetchall()
    costs=dict(measured)
    if len(costs)!=20 or any(not isinstance(value,(int,float)) or value<=0 for value in costs.values()):
        raise ValueError("G6_REAL_PACKING_COSTS_NOT_CLOSED")
    stats.sort(key=lambda row:(-costs[row[0]],row[0]))
    assignments=[{"molecule_id":mol,"records":records,"file_group":group,"task_id":0,
                  "sequence_in_task":i,"planned_allocated_seconds":costs[mol]}
                 for i,(mol,records,heavy,natoms,group) in enumerate(stats)]
    pq.write_table(pa.Table.from_pylist(assignments),out/"assignments.parquet",compression="zstd")
    save(out/"tasks.json",{"tasks":[{"task_id":0,"node":node,"record_directory":str(directory)}]})
    expected_records=sum(r[1] for r in stats);db.close()

    runner=ROOT/'scripts/wp5_runner_v9.py';queue=out/'queue.sqlite'
    base=[sys.executable,'-B',str(runner),'--plan',str(out/'tasks.json'),'--assignments',str(out/'assignments.parquet'),
        '--queue',str(queue),'--task-id','0','--dictionaries',str(a.dictionaries),'--protocol',str(a.protocol),'--node-authority',str(a.node_authority),
        '--node-scope-plan',str(ROOT/'packing/node_assignment_v3/tasks.json'),'--audit-membership',str(a.audit_membership),
        '--reproduction-package',str(a.reproduction_package),'--production-contract',str(a.production_contract),'--policy',POLICY,'--export-reserve-hours','0.5','--smoke','--workers','24']
    ratio=4.671507082406139/1.71
    first=max(a.hours,max(costs[r[0]] for r in stats[:16])*ratio/3600+.7)
    second=max(a.hours,max(costs[r[0]] for r in stats[16:])*ratio/3600+.7)
    cleanup_hours=max(a.hours,first)
    if first+second+cleanup_hours>45:raise ValueError('CURRENT_G6_PHASE_PLUS_ONCE_CLEANUP_P99_BUDGET_EXCEEDS45H')
    save(out/'phase_deadlines.json',{'phase0_hours':first,'phase1_hours':second,'cleanup_hours':cleanup_hours,'total_hours':first+second+cleanup_hours,'deadline_hours':46,'science_ratio':ratio})
    phases=[];initial_hashes={}
    root,info=run_phase(a,out,base,'phase_0',first,16);phases.append((root,info))
    state=queue_rows(queue)
    if info['completed_molecules_this_run']!=16 or sum(r['state']=='PENDING' for r in state)!=4:raise ValueError('CURRENT_G6_CUTOFF_NOT16_DURABLE_PLUS4_UNCLAIMED')
    if len({row['pid'] for row in info['workers'] if row['completed']})<16:raise ValueError('CURRENT_G6_EFFECTIVE16_PID_PROOF_MISSING')
    for ref in info['families']+[info['archive']]:initial_hashes[ref['path']]=ref['sha256']
    root,info=run_phase(a,out,base,'phase_1',second);phases.append((root,info))
    if info['completed_molecules_this_run']!=4 or any(row['state']=='PENDING' for row in queue_rows(queue)):raise ValueError('CURRENT_G6_RESUME_DID_NOT_COMPUTE_EXACT_REMAINING4')
    if any(row['state']=='RETRY_PENDING' for row in queue_rows(queue)):
        root,info=run_phase(a,out,base,'cleanup_once',cleanup_hours,cleanup=True);phases.append((root,info))
    for path,sha in initial_hashes.items():
        if digest(path)!=sha:raise ValueError('CURRENT_G6_RESUME_CHANGED_FIRST_PHASE_PERMANENT_FILE')
    summary=audit(a,phases,ids,stats,queue)
    save(out/'report.json',{'status':'G6_CURRENT_POLICY_FULL_CHAIN_PASSED','node':node,'original_designed_node':designed,'job_id':job,'molecules':20,**summary,
        'five_file_groups':sorted({r[4] for r in stats}),'seven_size_strata':sorted({size(r[2]) for r in stats}),'largest_pilot_eligible_total_atoms':largest[3],
        'phase_completions':[str(root/'completion.json') for root,info in phases],'artificial_cutoff_completed':16,'resume_new_completed':4,'one_cleanup_max':True,
        'first_phase_permanent_unchanged':True,'resource_peaks':[info['resource_peaks'] for root,info in phases],
        'staged_compressed_wire_bytes':[info.get('staged_compressed_wire_bytes') for root,info in phases],
        'staged_uncompressed_wire_bytes':[info.get('staged_uncompressed_wire_bytes') for root,info in phases],
        'bindings':{name:{'path':str(path),'sha256':digest(path)} for name,path in [('runner',runner),('script',Path(__file__)),('audit_manifest',a.audit_membership),('package',a.reproduction_package),('contract',a.production_contract),('dictionaries',a.dictionaries)]},
        'new_QM':True,'original_data_written':False,'final200_waived':False})
    print(json.dumps({'report':str(out/'report.json'),'status':'G6_CURRENT_POLICY_FULL_CHAIN_PASSED'}))
if __name__=='__main__':main()
