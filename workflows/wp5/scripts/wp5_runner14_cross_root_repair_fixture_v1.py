"""Private regression for foreign active-lane deletion; synthetic output only, no QM."""
from __future__ import annotations
import argparse,ast,hashlib,json,multiprocessing,os,socket,sqlite3,sys,tempfile,time,traceback
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
PARENT_SHA='258fd76ec1e0bac38db20fc2f3c0c1ef6f107d0d89261860f95b4b73099aed1f'
RUNNER_SHA='7d4aa3932be408ff051003446ae7f3fd1eab7b7bdb386d67a41eadb18e3af740'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'path':str(path),'sha256':sha(path),'bytes':Path(path).stat().st_size}
def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.pending');temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');os.replace(temp,path)
def bridge():
    old=ROOT/'scripts/wp5_runner_v13.py';new=ROOT/'scripts/wp5_runner_v14.py'
    assert sha(old)==PARENT_SHA and sha(new)==RUNNER_SHA
    def nodes(p):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text()).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
    a,b=nodes(old),nodes(new);assert a.keys()==b.keys()
    changed=sorted(k for k in a if a[k]!=b[k]);assert changed==['main','repair_unexported'],changed
    unchanged=sorted(k for k in a if a[k]==b[k])
    for key in ('compute_one','initialize_worker','worker_loop','prepare_index','export_family','canonical_index','finalize_run','bounded_finalize','verify_retained_scope','Queue','BusyConnection'):
        assert key in unchanged,key
    contract=json.loads((ROOT/'configs/production_contract_v6.json').read_text())
    scientific={k:v for k,v in contract['current_runtime'].items() if k not in {'wp5_runner_v13.py','wp5_main_v13.sbatch'}}
    assert all(sha(v['path'])==v['sha256'] for v in scientific.values())
    return {'schema':'WP5_R14_METADATA_AST_BRIDGE_V1','status':'METADATA_ONLY_AST_BRIDGE_PASS','runner13':ref(old),'runner14':ref(new),'changed_definitions':changed,'unchanged_definitions':unchanged,'own_finalize_AST_identical':True,'scientific_runtime':scientific,'scientific_runtime_SHA_unchanged':True}

def lane_worker(i,path,options,ready,release,results):
    writer=None
    try:
        from wp5_archive_v5 import ArchiveWriter
        writer=ArchiveWriter(path,options['dictionaries'],options['protocol'],reproduction_package=options['reproduction_package'],audit_membership=options['audit_membership'])
        ready.put({'lane':i,'pid':os.getpid(),'path':path,'opened':True})
        if not release.wait(120):raise TimeoutError('Parent did not release live-writer fixture')
        body=('SYNTHETIC METADATA REGRESSION OUTPUT lane '+str(i)).encode();mid='synthetic_mid_'+str(i)
        record={'record_id':'synthetic_record_'+str(i),'molecule_id':mid,'calc_type':'pm7_B','execution_id':'synthetic_execution_'+str(i),
                'source_status':'TIMEOUT','scope_status':'TIMEOUT','audit_selected':False,'synthetic_fixture':True,
                'input_file_sha256':[],'input_bundle_sha256':None,
                'files':[{'name':'fixture.txt','role':'output','data':body,'sha256':hashlib.sha256(body).hexdigest(),'byte_count':len(body)}]}
        with writer.molecule(mid):locator=writer.put_record(record)
        assert locator['raw_call_durable'] is True
        assert writer.db.execute('SELECT count(*) FROM completion_receipts').fetchone()[0]==0
        results.put({'lane':i,'pid':os.getpid(),'write_after_foreign_repair_durable':True,'raw_ref':locator})
    except BaseException:
        results.put({'lane':i,'pid':os.getpid(),'error':traceback.format_exc()})
    finally:
        if writer is not None:writer.close()

class ForbiddenForeignQueue:
    def __getattribute__(self,name):raise AssertionError('Foreign queue must not be read or mutated: '+name)
class PrivateDB:
    def __init__(self,path):
        self.connection=sqlite3.connect(path);self.connection.row_factory=sqlite3.Row;self.retry_stats={'synthetic_private_queue':True}
        self.connection.execute('CREATE TABLE IF NOT EXISTS molecules(molecule_id TEXT PRIMARY KEY,receipt_json TEXT,owner TEXT)');self.connection.commit()
    def execute(self,*args,**kwargs):return self.connection.execute(*args,**kwargs)
    def close(self):self.connection.close()
class PrivateQueue:
    def __init__(self,path,**kwargs):self.db=PrivateDB(path)
    def publish_export(self,session,references,archive):
        assert not self.db.execute('SELECT * FROM molecules').fetchall()
        assert archive['raw_records']==16 and archive['molecules']==0
        self.published={'session':session,'references':references,'archive':archive}

def run(out):
    assert socket.gethostname().split('.')[0]=='compute-0-20','Development fixture must run on compute-0-20'
    assert os.getuid()==1278
    import wp5_runner_v14 as runner
    from wp5_archive_v5 import ArchiveReader
    ast_report=bridge()
    base=ROOT/'tests';base.mkdir(exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='runner14_foreign_export_'+str(os.getuid())+'_',dir=base))
    active=folder/'active_cleanup';terminal=folder/'terminal_foreign';active.mkdir();terminal.mkdir()
    runner.atomic(active/'run.json',{'synthetic_fixture':True,'job_state':'RUNNING'})
    runner.atomic(terminal/'run.json',{'synthetic_fixture':True,'job_state':'COMPLETED'})
    contract=json.loads((ROOT/'configs/production_contract_v6.json').read_text())
    options={'run_root':str(active),'queue':str(folder/'private_queue.sqlite'),'session':'synthetic_fixture_session','job_id':'0',
             'dictionaries':str(ROOT/'dictionaries/job_4513894/dictionary_manifest.json'),'policy':runner.POLICY,
             'protocol':contract['protocol']['path'],'registry':contract['registry']['path'],
             'reproduction_package':contract['reproduction_package']['path'],'audit_membership':contract['audit_manifest']['path'],
             'job_exit_monotonic':time.monotonic()+600,'sql_deadline_monotonic':time.monotonic()+500}
    ctx=multiprocessing.get_context('spawn');ready=ctx.Queue();results=ctx.Queue();release=ctx.Event();workers=[]
    lanes=[active/'temporary_lanes'/('lane_'+str(i).zfill(2)+'.sqlite') for i in range(16)]
    for i,path in enumerate(lanes):
        p=ctx.Process(target=lane_worker,args=(i,str(path),options,ready,release,results));p.start();workers.append(p)
    try:
        opened=[ready.get(timeout=120) for _ in range(16)]
        assert len({r['pid'] for r in opened})==16
        before={str(p):{'sha256':sha(p),'inode':p.stat().st_ino} for p in lanes}
        run_refs={str(p):sha(p) for p in (active/'run.json',terminal/'run.json')}
        # Poison queue catches even the initial old SELECT. Both active and terminal
        # foreign roots are intentionally delegated, never repaired by a worker job.
        assert runner.repair_unexported(ForbiddenForeignQueue(),options,time.monotonic()+60)==[]
        assert all(sha(p)==before[str(p)]['sha256'] and p.stat().st_ino==before[str(p)]['inode'] for p in lanes)
        assert all(sha(p)==h for p,h in run_refs.items())
        release.set();written=[results.get(timeout=120) for _ in range(16)]
    finally:
        release.set()
        for p in workers:p.join(timeout=130)
    assert all(p.exitcode==0 for p in workers),[p.exitcode for p in workers]
    assert len(written)==16 and all(r.get('write_after_foreign_repair_durable') for r in written),written
    assert len({r['pid'] for r in written})==16
    # Positive closed-own-run regression: real unmodified finalizer, real A5
    # dictionary compression/readback/consolidation; zero scientific rows.
    original_queue=runner.Queue
    runner.Queue=PrivateQueue
    try:final=runner.finalize_run(options)
    finally:runner.Queue=original_queue
    assert final['records']==final['molecules']==0
    assert final['archive']['raw_records']==16 and final['archive']['partial_attempt_retained_raw_calls']==16
    assert final['archive']['scientific_task_outcomes']==0 and final['archive']['same_execution_join_verified'] is True
    assert not any(p.exists() for p in lanes)
    reader=ArchiveReader(final['archive']['path'],options['dictionaries'])
    try:
        for i in range(16):
            raw=reader.get('synthetic_record_'+str(i),'pm7_B','synthetic_execution_'+str(i))
            assert len(raw['output_files'])==1
            assert raw['output_files'][0]['data']==('SYNTHETIC METADATA REGRESSION OUTPUT lane '+str(i)).encode()
            assert not raw['input_files'] and raw['input_bodies_saved'] is False
        assert reader.db.execute('SELECT count(*) FROM completion_receipts').fetchone()[0]==0
    finally:reader.close()
    argv=sys.argv;original_queue=runner.Queue
    runner.Queue=lambda *a,**k: (_ for _ in ()).throw(AssertionError('repair-only must fail before queue access'))
    try:
        sys.argv=[str(ROOT/'scripts/wp5_runner_v14.py'),'--repair-only']
        try:runner.main();raise AssertionError('repair-only was accepted')
        except ValueError as exc:assert str(exc)=='CROSS_ROOT_REPAIR_DELEGATED_TO_ROOT_TERMINAL_EXPORT_TOOL'
    finally:sys.argv=argv;runner.Queue=original_queue
    proof_path=ROOT/'reports/wp5_runner14_cross_root_repair_ast_bridge_v1.json';atomic(proof_path,ast_report)
    report={'schema':'WP5_RUNNER14_CROSS_ROOT_EXPORT_FIXTURE_V1','status':'METADATA_ONLY_FOREIGN_EXPORT_DELEGATION_FIXTURE_PASS',
            'synthetic_fixture':True,'QM_calls':0,'SCI_rows':0,'original_LMDB_opened':False,'production_queue_written':False,
            'fixture_root':str(folder),'actual_worker_pids':sorted(r['pid'] for r in written),'effective_worker_count':16,
            'active_foreign_lanes_untouched':True,'active_writers_durable_after_repair_call':True,
            'terminal_foreign_root_delegated':True,'repair_only_rejected_before_queue':True,
            'closed_own_finalizer_real_A5_readback_PASS':True,'own_finalizer_result':final,
            'worker_reports':written,'AST_bridge':ref(proof_path),'source':ref(Path(__file__)),'issues':[]}
    atomic(out,report);print(json.dumps({'status':report['status'],'report':ref(out),'workers':16,'fixture_root':str(folder)}))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'reports/wp5_runner14_cross_root_repair_fixture_v1.json');p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        ast.parse(Path(__file__).read_text());print(json.dumps(bridge()));return
    run(a.out)
if __name__=='__main__':main()