"""Run the taskbook's one full CPU core suite in its existing isolated runner."""
import os,pathlib,signal,subprocess,sys,time
from resources import REPO,CONTROL,load,save,guard

def source_commit():
    gitdir=REPO/'.git'
    if gitdir.is_file():gitdir=(REPO/gitdir.read_text().strip().split(':',1)[1].strip()).resolve()
    head=(gitdir/'HEAD').read_text().strip()
    if not head.startswith('ref: '):return head
    reference=head[5:];common=gitdir
    if (gitdir/'commondir').exists():common=(gitdir/(gitdir/'commondir').read_text().strip()).resolve()
    for root in [gitdir,common]:
        if (root/reference).exists():return (root/reference).read_text().strip()
    for line in (common/'packed-refs').read_text().splitlines():
        if line.endswith(' '+reference):return line.split()[0]
    raise ValueError('Current source ref unavailable')

def main():
    import argparse
    from resources import disk,GIB,allocated
    parser=argparse.ArgumentParser();parser.add_argument('--repair-from');args=parser.parse_args()
    guard(force=True);job=os.environ['SLURM_JOB_ID'];output=CONTROL/('regression_'+job)
    scratch=pathlib.Path('/tmp')/('mpTests_'+job);private=pathlib.Path('/tmp')/('mv3n_'+job)
    def capacity():
        guard(force=True)
        future=max(0,10*GIB-allocated(scratch)-allocated(private))
        disk.m.require_capacity(disk.m.filesystem_status('/tmp'),future,10000)
    capacity();started_commit=source_commit();base=load(args.repair_from) if args.repair_from else None
    sys.path.insert(0,str(REPO/'tools/model_v3'))
    from private_runtime_storage import PrivateStorage,_write_exclusive
    output.mkdir();storage=PrivateStorage(private,budget_bytes=2*GIB)
    pin=_write_exclusive(output/'private_storage.json',storage.bindings)
    os.environ.update(storage.bindings['environment'])
    os.environ.update(MODEL_V3_STORAGE_BINDINGS_PATH=str(output/'private_storage.json'),MODEL_V3_STORAGE_BINDINGS_SHA256=pin)
    storage.start()
    # The established runner creates its output itself; keep the binding separate.
    core_output=output/'core'
    argv=[sys.executable,'-B','-u',str(REPO/'tools/p_recipe/regression.py'),'--output',str(core_output),'--scratch',str(scratch),'--workers','2','--preserve-storage-environment']
    if base:argv+=['--modules',*[r['module'] for r in base['failed_modules']]]
    child=subprocess.Popen(argv,cwd=REPO,start_new_session=True)
    try:
        while child.poll() is None:capacity();time.sleep(5)
    except BaseException:
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=30)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        raise
    finally:
        try:storage.stop();observer_error=None
        except ValueError as error:observer_error=str(error)
    summary=load(core_output/'summary.json')
    if observer_error:summary['post_test_storage_observer_error']=observer_error
    if base:
        repaired_counts=dict(summary['counts']);repaired_modules=summary['modules']
        summary['counts']={k:base['counts'][k]-sum(r['counts'][k] for r in base['failed_modules'])+repaired_counts[k] for k in repaired_counts}
        summary.update(modules=base['modules'],repair_modules=repaired_modules,repair_counts=repaired_counts,
            preserved_pass_modules=base['modules']-len(base['failed_modules']),original_full_result=str(pathlib.Path(args.repair_from).resolve()),original_source_commit=base.get('source_commit'))
    summary.update(job_id=job,output=str(core_output),scratch=str(scratch),private_scratch=str(private),source_commit=started_commit,
        source_commit_at_finish=source_commit(),scope='Full current/tests CPU suite; on repair, rerun every failed module with real16CPU/local storage/native imports and preserve successful modules')
    save(output/'summary.json',summary);save(REPO/'results/p_followup/REGRESSION_FULL.json',summary)
    print('FOLLOWUP_FULL_REGRESSION',summary,flush=True)
    return child.returncode
if __name__=='__main__':raise SystemExit(main())
