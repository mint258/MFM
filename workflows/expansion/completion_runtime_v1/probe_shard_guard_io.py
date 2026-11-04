"""Time one original, unmodified full quota guard on the actual shared scope."""
import hashlib,json,os,pathlib,runpy,socket,time
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026');B=A/'control/pubchem_expansion_runtime_20261103'
def reference(p):
    p=pathlib.Path(p);raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def main():
    if os.getuid()!=1264 or socket.gethostname().split('.')[0]!='sonmi1' or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))!=16:raise ValueError('Actual Alpha idle CPU allocation only')
    runpy.run_path(str(A/'code/inverted_cache_resume_20261104_v1/entry.py'),run_name='_guard_diagnostic')
    from workflows.expansion.alpha_sharded_novelty_v1 import run
    path=B/'node_epochs/main_rescue_resume_20261105_v1_low11_job_1885259/plan.json'
    plan=json.loads(path.read_bytes());guard=run.ShardGuard(plan,pathlib.Path(plan['output_directory']))
    original=guard.checker;stages={}
    def checker(*args,**kwargs):
        began=time.monotonic();stages['actual_scope_allocated_bytes']=args[1]
        result=original(*args,**kwargs);stages.update(native_quota_and_credit_walk_seconds=time.monotonic()-began,original_budget_check=result);return result
    guard.checker=checker;began=time.monotonic();cpu=time.process_time();guard.poll(force=True)
    value=dict(schema='PUBCHEM_ORIGINAL_SHARD_GUARD_IO_PROBE_V1',actual=dict(endpoint='218.192.171.238:22',uid=os.getuid(),node=socket.gethostname(),job_id=os.environ['SLURM_JOB_ID'],allocated_CPUs=16),source_reference=reference(__file__),plan_reference=reference(path),original_module_reference=reference(run.__file__),wall_seconds=time.monotonic()-began,process_CPU_seconds=time.process_time()-cpu,stages=stages,scientific_data_or_running_program_changed=False)
    output=B/('shard_guard_io_probe_job_'+os.environ['SLURM_JOB_ID']+'.json')
    with output.open('x')as f:json.dump(value,f,sort_keys=True);f.write('\n')
    print(json.dumps(value),flush=True)
if __name__=='__main__':main()