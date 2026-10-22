"""Real CPU validation of the Stage3 command-line repair; no model or gate execution."""
from concurrent.futures import ThreadPoolExecutor
import ast,hashlib,json,os,socket,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
PYTHON='/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
def ref(path):
    path=Path(path);raw=path.read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
def verify(row):
    actual=ref(row['path']);assert actual['sha256']==row['sha256']
    return actual
def main():
    assert os.getuid()==1278 and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-8','compute-0-9','compute-0-10','compute-0-11']
    began=time.monotonic();out=ROOT/'validation'/('stage3_gate_v4_job'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
    refs=[ref(ROOT/'analysis'/n) for n in ['stage3_gate_v4.py','test_stage3_gate_v4.py']]
    for row in refs:ast.parse(Path(row['path']).read_bytes())
    bindings=[ROOT/'configs/D3_source_binding_v4.json',ROOT/'configs/gate_analysis_binding_v1.json',ROOT/'configs/gate_analysis_binding_v2.json']
    with ThreadPoolExecutor(16) as pool:
        frozen=list(pool.map(verify,[row for p in bindings for row in json.loads(p.read_text())['files']]))
    old=ast.parse((ROOT/'analysis/stage3_gate_v3.py').read_text());new=ast.parse((ROOT/'analysis/stage3_gate_v4.py').read_text())
    checked=['judge','denoise_fraction','estimate_cost','query_parents','finite','read_ref']
    for name in checked:
        a=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name)
        b=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name==name)
        assert ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)
    repository=ROOT/'reports/repository_check_v20.json';assert json.loads(repository.read_text())['status']=='PASS'
    command=[PYTHON,'-B','-m','pytest','-q','-p','no:cacheprovider','test_stage3_gate_v4.py','--junitxml='+str(out/'pytest.xml')]
    p=subprocess.run(command,cwd=ROOT/'analysis',stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
    help_p=subprocess.run([PYTHON,'-B',str(ROOT/'analysis/stage3_gate_v4.py'),'--help'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
    assert help_p.returncode==0 and '--baseline-phase' in help_p.stdout
    report={'status':'STAGE3_GATE_V4_CPU_ENTRY_AND_ACTUAL_LOOKUP_PROVENANCE_PASS' if p.returncode==0 else 'STAGE3_GATE_V4_CPU_CHECK_FAILED',
      'job_id':os.environ['SLURM_JOB_ID'],'host':socket.gethostname(),'elapsed_seconds':time.monotonic()-began,
      'source_references':refs,'frozen_files_verified':len(frozen),'frozen_binding_references':[ref(p) for p in bindings],
      'scientific_gate_functions_AST_unchanged':checked,'repository_check':ref(repository),
      'command':command,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,
      'cli_help_returncode':help_p.returncode,'no_model_execution':True,'no_scientific_gate_declared_passed':True,'actual_lookup_closure_reference':ref(ROOT/'configs/lookup_refit_closure_v1.json')}
    (out/'result.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(report['status'],p.stdout,p.stderr,flush=True);assert p.returncode==0
if __name__=='__main__':main()
