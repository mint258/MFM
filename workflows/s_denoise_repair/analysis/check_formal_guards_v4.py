"""Bounded CPU checks of new entry guards plus the unchanged scientific repository."""
from concurrent.futures import ThreadPoolExecutor
import ast,hashlib,json,os,socket,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
SOURCE=ROOT/'source_v3'
WORKFLOW=ROOT/'formal_workflows_v4'
PYTHON='/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'


def syntax(path):
    raw=path.read_bytes();assert b'\r' not in raw;ast.parse(raw)
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest())


def run(arguments,cwd):
    p=subprocess.run([PYTHON,'-B']+arguments,cwd=cwd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
    return dict(arguments=arguments,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)


def main():
    assert os.getuid()==1278 and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-8','compute-0-9','compute-0-10','compute-0-11']
    output=ROOT/'validation'/('formal_guards_v4_job'+os.environ['SLURM_JOB_ID']);output.mkdir(exist_ok=False)
    began=time.monotonic()
    with ThreadPoolExecutor(16) as pool:
        refs=list(pool.map(syntax,sorted(WORKFLOW.glob('*.py'))))
        futures=[pool.submit(run,['-m','unittest','test_formal_config_v4','test_guarded_entry_v4','-v'],WORKFLOW),
                 pool.submit(run,['tools/check_repository.py'],SOURCE)]
        results=[f.result() for f in futures]
    report=dict(status='FORMAL_V4_GUARDS_AND_REPOSITORY_PASS' if all(r['returncode']==0 for r in results) else 'FORMAL_V4_GUARDS_OR_REPOSITORY_FAILED',
        job_id=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),source_references=refs,checks=results,
        no_model_execution=True,no_training_submission=True,formal_gate_not_declared_passed=True,elapsed_seconds=time.monotonic()-began)
    (output/'result.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('FORMAL_V4_CHECK',report['status'],len(refs),flush=True)
    for row in results: print(row['stdout'][-1800:]+row['stderr'][-1800:],flush=True)
    assert all(row['returncode']==0 for row in results)


if __name__=='__main__':main()
