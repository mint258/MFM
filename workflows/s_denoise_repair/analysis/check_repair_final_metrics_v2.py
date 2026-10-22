"""Bounded CPU tests of strict final-result extraction; fixtures add zero training updates."""
from concurrent.futures import ThreadPoolExecutor
import ast,hashlib,json,os,socket,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
PYTHON='/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
def ref(path):
    path=Path(path);raw=path.read_bytes();return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
def verify(row):assert ref(row['path'])['sha256']==row['sha256'];return row
def main():
    assert os.getuid()==1278 and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-8','compute-0-9','compute-0-10','compute-0-11']
    began=time.monotonic();out=ROOT/'validation'/('repair_final_metrics_v2_job'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
    paths=[ROOT/'analysis'/name for name in ['repair_final_metrics_v2.py','test_repair_final_metrics_v2.py','s_convergence_rules_v3.py','capture_repair_accounting_v1.py']]
    for path in paths:ast.parse(path.read_bytes())
    bindings=[ROOT/'configs/D3_source_binding_v4.json',ROOT/'configs/gate_analysis_binding_v1.json',ROOT/'configs/gate_analysis_binding_v2.json']
    with ThreadPoolExecutor(16) as pool:list(pool.map(verify,[row for p in bindings for row in json.loads(p.read_text())['files']]))
    command=[PYTHON,'-B','-m','pytest','-q','-p','no:cacheprovider','test_repair_final_metrics_v2.py','--junitxml='+str(out/'pytest.xml')]
    p=subprocess.run(command,cwd=ROOT/'analysis',stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
    result={'status':'REPAIR_FINAL_METRICS_V2_COUNTS_DIRECTIONS_AND_MISSING_VALUES_PASS' if p.returncode==0 else 'REPAIR_FINAL_METRICS_V2_CHECK_FAILED',
      'job_id':os.environ['SLURM_JOB_ID'],'host':socket.gethostname(),'elapsed_seconds':time.monotonic()-began,
      'source_references':[ref(p) for p in paths],'frozen_bindings_verified':[ref(p) for p in bindings],
      'command':command,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,
      'no_model_execution':True,'no_training_updates_added':True,'formal_science_not_declared_complete':True}
    (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(result['status'],p.stdout,p.stderr,flush=True);assert p.returncode==0
if __name__=='__main__':main()
