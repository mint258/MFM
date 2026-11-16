"""Run the taskbook's one full CPU core suite in its existing isolated runner."""
import os,pathlib,signal,subprocess,sys,time
from resources import REPO,CONTROL,load,save,guard

def main():
    guard(force=True);job=os.environ['SLURM_JOB_ID'];output=CONTROL/('regression_'+job);scratch=CONTROL/('regression_scratch_'+job)
    argv=[sys.executable,'-B','-u',str(REPO/'tools/p_recipe/regression.py'),'--output',str(output),'--scratch',str(scratch),'--workers','2']
    child=subprocess.Popen(argv,cwd=REPO,start_new_session=True)
    try:
        while child.poll() is None:
            guard(force=True);time.sleep(5)
    except BaseException:
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=30)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        raise
    summary=load(output/'summary.json');summary.update(job_id=job,output=str(output),scratch=str(scratch),source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),scope='Every current/tests/test_*.py module, same existing per-module runner, CPU only')
    save(REPO/'results/p_followup/REGRESSION_FULL.json',summary)
    print('FOLLOWUP_FULL_REGRESSION',summary,flush=True)
    return child.returncode
if __name__=='__main__':raise SystemExit(main())