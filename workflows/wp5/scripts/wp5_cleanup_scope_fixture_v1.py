"""One real 16-worker metadata fixture for R13 cleanup task/index boundaries; zero QM."""
import argparse, ast, concurrent.futures, hashlib, json, multiprocessing as mp, os, pickle, socket, sqlite3, time, traceback, uuid, zlib
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
R12=ROOT/'scripts/wp5_runner_v12.py';R13=ROOT/'scripts/wp5_runner_v13.py'
EXPECTED12='91ec1ce7bf82589b647db43502bc86f9bb2c7c0a98a845ef28446703cc48d278'
EXPECTED13='258fd76ec1e0bac38db20fc2f3c0c1ef6f107d0d89261860f95b4b73099aed1f'
_BARRIER=None
def ref(path):return {'path':str(path),'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
def write_new(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if json.loads(path.read_text())!=data:raise ValueError('Preserve existing proof: '+str(path))
        return
    with path.open('x',encoding='utf-8') as f:json.dump(data,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def bridge(path):
    old,new=ast.parse(R12.read_text()),ast.parse(R13.read_text())
    functions=lambda tree:{node.name:node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
    a,b=functions(old),functions(new)
    dump=lambda node:ast.dump(node,include_attributes=False)
    changed=sorted(name for name in set(a)|set(b) if name not in a or name not in b or dump(a[name])!=dump(b[name]))
    classes=lambda tree:{node.name:{method.name:method for method in node.body if isinstance(method,ast.FunctionDef)} for node in tree.body if isinstance(node,ast.ClassDef)}
    ac,bc=classes(old),classes(new);class_changes={}
    for name in set(ac)|set(bc):
        left,right=ac.get(name,{}),bc.get(name,{})
        values=sorted(k for k in set(left)|set(right) if k not in left or k not in right or dump(left[k])!=dump(right[k]))
        if values:class_changes[name]=values
    def main_branch(method):
        for node in ast.walk(method):
            if isinstance(node,ast.If) and isinstance(node.test,ast.Compare) and isinstance(node.test.left,ast.Name) and node.test.left.id=='mode' and len(node.test.comparators)==1 and isinstance(node.test.comparators[0],ast.Constant) and node.test.comparators[0].value=='main':
                return ast.dump(ast.Module(body=node.body,type_ignores=[]),include_attributes=False)
        raise ValueError('Actual main claim branch missing')
    main_same=main_branch(ac['Queue']['claim'])==main_branch(bc['Queue']['claim'])
    imports=lambda tree:[dump(node) for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom))]
    constants=lambda tree:[dump(node) for node in tree.body if isinstance(node,(ast.Assign,ast.AnnAssign))]
    same=changed==['main','prepare_index','worker_loop'] and class_changes=={'Queue':['claim']} and main_same and imports(old)==imports(new) and constants(old)==constants(new)
    oldmain=(ROOT/'scripts/wp5_main_v12.sbatch').read_text()
    newmain=(ROOT/'scripts/wp5_main_v13.sbatch').read_text()
    recipe_same=oldmain.replace('wp5_main12','wp5_main13').replace('wp5_runner_v12.py','wp5_runner_v13.py')==newmain
    report={'schema':'WP5_R13_METADATA_AST_BRIDGE_V1','status':'METADATA_ONLY_AST_BRIDGE_PASS' if same and recipe_same else 'NOT_PASS',
            'runner12':ref(R12),'runner13':ref(R13),'physics_same':same and recipe_same,'main_claim_ast_same':main_same,
            'main_script_recipe_same':recipe_same,'changed_top_level_functions':changed,'changed_class_methods':class_changes,
            'unchanged_top_level_functions':sorted(set(a)&set(b)-set(changed)),
            'unchanged_science_functions':{name:dump(a[name])==dump(b[name]) for name in ('normalize_source_row','compute_one','family_row','canonical_index','verify_retained_scope')},
            'QM_calls':0,'production_queue_written':False,
            'scope':'Only cleanup task snapshot, its possible RUNNING rows, and worker propagation changed. No science/parser/precision/deadline/queue-lock changes.'}
    write_new(path,report)
    if not report['physics_same']:raise ValueError('Actual metadata AST bridge differs beyond allowed scope')
    return report
def initialize(barrier):
    global _BARRIER
    _BARRIER=barrier
def payload_ids(path):
    db=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)
    try:
        rows={row[0]:pickle.loads(zlib.decompress(row[1])) for row in db.execute('SELECT molecule_id,payload FROM rows')}
    finally:db.close()
    return rows
def scenario(parameters):
    number,directory=parameters;_BARRIER.wait(timeout=120)
    private=Path(directory)/('worker_'+str(number));private.mkdir(exist_ok=False)
    import pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    import wp5_runner_v13 as runtime
    runtime.ROOT=private;runtime.STOP=private/'STOP_NEW_MOLECULES.json'
    result={'worker':number,'pid':os.getpid(),'private_queue':str(private/'fixture.sqlite'),'issues':[]}
    queue=None;other=None
    try:
        names={'A_pending':'A','A_running':'A','B_pending':'B'}
        directories={}
        for task in ('A','B'):
            d=private/('records_'+task);d.mkdir();directories[task]=str(d)
            rows=[{'molecule_id':molecule,'record_id':molecule+'_record','conformer_id':0,'molecule_max_heavy_atoms':6,'file_group':1}
                  for molecule,assigned in names.items() if assigned==task]
            pq.write_table(pa.Table.from_pylist(rows),d/'records.parquet',compression='zstd')
        plan_path=private/'tasks.json'
        plan_path.write_text(json.dumps({'tasks':[{'task_id':task,'node':socket.gethostname().split('.')[0],'record_directory':directories[task]} for task in ('A','B')]}))
        assignment=private/'assignments.parquet'
        pq.write_table(pa.Table.from_pylist([{'molecule_id':name,'task_id':task,'file_group':1,'records':1,
             'planned_allocated_seconds':{'A_pending':10.0,'A_running':100.0,'B_pending':1000.0}[name],'sequence_in_task':index}
             for index,(name,task) in enumerate(names.items())]),assignment)
        path=private/'fixture.sqlite';sqlite3.connect(path).close()
        runtime.bootstrap_metadata(path,deadline=time.monotonic()+1200)
        queue=runtime.Queue(path,deadline=time.monotonic()+1200);queue.seed(plan_path,assignment,smoke=True)
        session='fixture_'+uuid.uuid4().hex;other_session='other_'+uuid.uuid4().hex
        job=os.environ['SLURM_JOB_ID'];node=socket.gethostname().split('.')[0]
        queue.start(session,job,'cleanup_A','cleanup',node)
        other=runtime.Queue(path,deadline=time.monotonic()+1200);other.start(other_session,job,'cleanup_other','cleanup',node)
        def before_snapshot():
            queue.db.execute("UPDATE tasks SET state='CLOSED' WHERE task_id='A'")
            queue.db.execute("UPDATE tasks SET state='RUNNING' WHERE task_id='B'")
            queue.db.execute("UPDATE molecules SET state='RUNNING',owner=? WHERE molecule_id='A_running'",(other_session,))
        queue.db.transaction(before_snapshot)
        options={'workers':1,'mode':'cleanup','task_id':'cleanup_A','local_index':str(private/'first_index.sqlite')}
        first=runtime.prepare_index(queue,options);indexed=payload_ids(options['local_index'])
        if first['cleanup_task_scope']!=['A'] or set(indexed)!={'A_pending','A_running'}:
            raise ValueError('First SELECT scope/local index did not include A pending+running only')
        queue.db.execute("UPDATE tasks SET state='CLOSED' WHERE task_id='B'")
        claimed1=queue.claim(session,'cleanup_A','cleanup',3600,0,first['cleanup_task_scope'])
        if claimed1 is None or claimed1['molecule_id']!='A_pending' or claimed1['molecule_id'] not in indexed:
            raise ValueError('Newly closed B escaped the static initial scope')
        # Same-task concurrent cleanup race: a RUNNING row returns to pending.
        other.finish(other_session,{'molecule_id':'A_running','partial':True})
        claimed2=queue.claim(session,'cleanup_A','cleanup',3600,0,first['cleanup_task_scope'])
        if claimed2 is None or claimed2['molecule_id']!='A_running' or claimed2['molecule_id'] not in indexed:
            raise ValueError('Same-task RUNNING->PENDING not covered by the original local index')
        before=queue.db.execute('SELECT claims FROM sessions WHERE session_id=?',(session,)).fetchone()[0]
        empty=queue.claim(session,'cleanup_A','cleanup',3600,0,[])
        after=queue.db.execute('SELECT claims FROM sessions WHERE session_id=?',(session,)).fetchone()[0]
        if empty is not None or before!=after:raise ValueError('Empty scope fell back to global cleanup')
        later={'workers':1,'mode':'cleanup','task_id':'cleanup_B','local_index':str(private/'later_index.sqlite')}
        second=runtime.prepare_index(queue,later);later_index=payload_ids(later['local_index'])
        session_b='later_'+uuid.uuid4().hex;queue.start(session_b,job,'cleanup_B','cleanup',node)
        claimed3=queue.claim(session_b,'cleanup_B','cleanup',3600,0,second['cleanup_task_scope'])
        if 'B' not in second['cleanup_task_scope'] or claimed3 is None or claimed3['molecule_id']!='B_pending' or claimed3['molecule_id'] not in later_index:
            raise ValueError('Later B cleanup could not claim its indexed whole molecule')
        for name,rows in {**indexed,**later_index}.items():
            if len(rows)!=1 or rows[0]['molecule_id']!=name or rows[0]['record_id']!=name+'_record':
                raise ValueError('Frozen whole-molecule source rows changed in local-index metadata preparation')
        result.update(status='PASS',initial_scope=first['cleanup_task_scope'],initial_index_molecules=sorted(indexed),
             claimed_before_release=claimed1['molecule_id'],claimed_after_release=claimed2['molecule_id'],
             empty_scope_claimed=False,later_scope=second['cleanup_task_scope'],later_claimed=claimed3['molecule_id'],
             all_claims_have_original_local_index=True,queue_metadata_retry_stats=dict(queue.db.retry_stats),
             QM_calls=0,scientific_attempts_consumed=0,production_queue_written=False)
    except Exception:
        result.update(status='NOT_PASS',issues=[traceback.format_exc(limit=10)])
    finally:
        if other is not None:other.db.close()
        if queue is not None:queue.db.close()
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--out',type=Path);p.add_argument('--workers',type=int,default=16)
    p.add_argument('--bridge-output',type=Path,default=ROOT/'reports/wp5_runner_v13_cleanup_scope_ast_bridge_v1.json')
    a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('CLEANUP_SCOPE_FIXTURE_AST_PASS_ZERO_QM_NOT_STARTED');return
    if not a.out:p.error('--out new immutable fixture directory required')
    if os.getuid()!=1278 or not os.environ.get('SLURM_JOB_ID') or a.workers!=16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<16:
        raise ValueError('Actual Root Slurm16CPU/16worker metadata allocation required')
    if ref(R12)['sha256']!=EXPECTED12 or ref(R13)['sha256']!=EXPECTED13:raise ValueError('Actual R12/R13 source SHA differs')
    if not a.out.resolve().is_relative_to(ROOT):raise ValueError('Private fixture must remain inside WP5 root')
    a.out.mkdir(parents=True,exist_ok=False)
    ast_proof=bridge(a.bridge_output)
    context=mp.get_context('spawn');barrier=context.Barrier(16);started=time.monotonic()
    with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=initialize,initargs=(barrier,)) as pool:
        results=list(pool.map(scenario,[(i,str(a.out)) for i in range(16)],chunksize=1))
    pids=sorted({row['pid'] for row in results})
    issues=[{'worker':row['worker'],'issues':row['issues']} for row in results if row['status']!='PASS']
    if len(pids)!=16:issues.append({'effective_worker_count':len(pids),'expected':16})
    report={'schema':'WP5_CLEANUP_STATIC_SCOPE_FIXTURE_V1','status':'CLEANUP_STATIC_SCOPE_FIXTURE_PASS' if not issues else 'NOT_PASS',
       'runner12':ref(R12),'runner13':ref(R13),'source':ref(Path(__file__).resolve()),'AST_bridge':ref(a.bridge_output),
       'physics_same':ast_proof['physics_same'],'actual_worker_pids':pids,'effective_worker_count':len(pids),
       'allocated_cpus':int(os.environ['SLURM_CPUS_PER_TASK']),'job_id':os.environ['SLURM_JOB_ID'],
       'actual_node':socket.gethostname().split('.')[0],'seconds':time.monotonic()-started,
       'issues':issues,'scenarios':results,'QM_calls':0,'scientific_attempts_consumed':0,'production_queue_written':False,
       'original_sources_or_results_modified':False,'scope':'One A/B task-boundary and same-task RUNNING-release fixture per actual parallel metadata worker; synthetic private rows only.'}
    write_new(a.out/'report.json',report)
    print(json.dumps({'status':report['status'],'report':ref(a.out/'report.json'),'bridge':ref(a.bridge_output),'effective_workers':len(pids)}))
    if issues:raise SystemExit(2)
if __name__=='__main__':main()
