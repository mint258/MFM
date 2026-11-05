"""Create the actual Main CPU rescue plan inside its native CPU allocation."""
import argparse,hashlib,json,os,pathlib,socket,sys
R=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
CONTROL=R/'control/pubchem_alpha_return_20261103'
WORKTREE=R/'worktrees/pubchem_completion_20261103'
NODE=socket.gethostname().split('.')[0]
WORKERS=96 if NODE=='compute-0-16'else 64
SCRATCH=pathlib.Path(('/dev/shm/'if NODE=='compute-0-16'else '/tmp/')+'zixiao_pubchem_rescue_20261104')


def ref(p):
    p=pathlib.Path(p);before=p.stat();h=hashlib.sha256()
    with p.open('rb')as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    after=p.stat()
    if(before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns)or after.st_uid!=1278:
        raise ValueError('Actual Main immutable source/metadata required')
    return dict(path=str(p),bytes=after.st_size,sha256=h.hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--entry',required=True,type=pathlib.Path);a=parser.parse_args()
    if(os.getuid()!=1278 or not sys.flags.isolated or NODE not in ('compute-0-16','compute-0-21')
       or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))!=WORKERS or not os.environ.get('SLURM_JOB_ID')
       or os.environ.get('SLURM_JOB_GPUS')or os.environ.get('SLURM_STEP_GPUS')):
        raise ValueError('Actual Main16/96CPU or Main21/64CPU isolated noGPU allocation only')
    index=json.loads((SCRATCH/'alpha_queries_v1/_transport_index.json').read_text())
    complete=json.loads((SCRATCH/'alpha_queries_v1/transfer_completed.json').read_text())
    if complete['actual_uid']!=1278 or complete['node'].split('.')[0]!=NODE:
        raise ValueError('Actual completed same-node input transport required')
    transport=ref(SCRATCH/'alpha_queries_v1/transport.json')
    if transport!=complete['transport_reference']:
        raise ValueError('Closed transport changed')
    paths=[]
    for folder in['main_exact_rescue_v1','exact_nn_inverted_cpp_v1','exact_nn_popcount_cpp_v1']:
        base=WORKTREE/'workflows/expansion'/folder
        paths.extend(p for p in base.iterdir()if p.suffix in('.py','.c'))
    paths.extend([WORKTREE/'workflows/expansion/exact_nn_cached_v1/engine.py',
        WORKTREE/'workflows/expansion/alpha_runtime_v1/guard.py',a.entry,pathlib.Path(__file__)])
    code=[ref(p)for p in paths]
    directory=CONTROL/'node_epochs'/('main_exact_rescue_job_'+os.environ['SLURM_JOB_ID'])
    directory.mkdir(mode=0o700,parents=True)
    plan=dict(schema='MAIN_EXACT_FP_RESCUE_PLAN_V1',origin_export_manifest_reference=index['original_export_manifest_reference'],
        origin_export_native_sacct_reference=index['original_export_native_sacct_reference'],
        reference_manifest_reference=index['reference_manifest_reference'],test_queries_reference=index['test_queries_reference'],
        historical206_reference=index['historical206_reference'],transport_reference=transport,
        compiler='/usr/bin/cc',entry_reference=ref(a.entry),code_references=code,
        output_directory=str(SCRATCH/('main_exact_rescue_job_'+os.environ['SLURM_JOB_ID'])),
        expected_node=NODE,scratch_root=str(SCRATCH),workers=WORKERS,query_batch=128,worker_rss_cap_bytes=1<<30,parent_rss_cap_bytes=24<<30,
        software_rss_budget_bytes=(WORKERS+24)<<30,minimum_node_available_bytes=24<<30,preflight_rss_cap_bytes=3<<30,
        output_cap_bytes=(60000000000 if NODE=='compute-0-16'else 200000000000),other_scratch_reserved_bytes=0,
        minimum_scratch_free_bytes=(100000000000 if NODE=='compute-0-16'else 200000000000),
        future_tmpfs_output_bytes=(60000000000 if NODE=='compute-0-16'else 0),
        all_bulk_data_on_actual_node_local_scratch=True,shared_home_new_metadata_bound_bytes=100<<20,
        actual_memory_reservation_environment={k:os.environ.get(k)for k in('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU')},
        preparation_source_reference=ref(__file__),input_transfer_completion_reference=ref(SCRATCH/'alpha_queries_v1/transfer_completed.json'))
    path=directory/'plan.json'
    with path.open('x')as f:json.dump(plan,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
    print(json.dumps(dict(event='MAIN_RESCUE_NATIVE_PLAN_READY',job_id=os.environ['SLURM_JOB_ID'],uid=os.getuid(),
        node=socket.gethostname(),resource_plan=ref(path),bulk_output=plan['output_directory'])),flush=True)
    argv=[sys.executable,'-I','-B',str(a.entry),'workflows.expansion.main_exact_rescue_v1.run','--plan',str(path)]
    os.chdir(WORKTREE);os.execv(sys.executable,argv)


if __name__=='__main__':main()
