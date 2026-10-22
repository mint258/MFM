"""C6 checks for an isolated optional execution candidate; never trains D3 or accepts a gate."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,inspect,json,os,socket,subprocess,time,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
SOURCE=ROOT/'source_v4'
PYTHON='/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
def ref(path):
    raw=Path(path).read_bytes();return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
def check(row):assert ref(row['path'])['sha256']==row['sha256'];return row
def junit(path):
    root=ET.parse(path).getroot();suites=[root] if root.tag=='testsuite' else root.findall('testsuite')
    return {key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ['tests','failures','errors','skipped']}
def main():
    assert os.getuid()==1278 and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-8','compute-0-9','compute-0-10','compute-0-11']
    start=time.monotonic();out=ROOT/'validation'/('atom_projection_cpu_job'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
    pins=json.loads((ROOT/'configs/D3_source_binding_v4.json').read_text())['files']
    with ThreadPoolExecutor(16) as pool:list(pool.map(check,pins))
    candidate=[ref(Path(p['path'].replace('/source_v3/','/source_v4/'))) for p in pins]
    candidate.extend(ref(p) for p in [SOURCE/'current/tests/test_atom_projection_execution.py',SOURCE/'docs/SOURCE_MANIFEST.json',ROOT/'analysis/legacy_bitexact_source4_v1.py',Path(__file__)])
    for row in candidate:
        if row['path'].endswith('.py'):compile(Path(row['path']).read_bytes(),row['path'],'exec')
    repository=ROOT/'reports/source_v4_repository_check_v1.json';assert json.loads(repository.read_text())['status']=='PASS'
    import phychem_mfm.model.heads as heads
    actual=Path(inspect.getfile(heads.EquivariantDenoisingHead)).absolute()
    assert actual.is_relative_to(SOURCE/'current')
    checks=[]
    document={'status':'ATOM_PROJECTION_CPU_C6_IN_PROGRESS_NOT_ADOPTED','job_id':os.environ['SLURM_JOB_ID'],
      'source_references':candidate,'imported_head_source':str(actual),'checks':checks,'scientific_gate_pass_claimed':False,'formal_training_authorized':False}
    commands=[('new_execution_tests',['-m','pytest','-q','-p','no:cacheprovider','current/tests/test_atom_projection_execution.py','--junitxml='+str(out/'new_execution.xml')]),
      ('original_tests',['-m','pytest','-q','-p','no:cacheprovider','current/tests','--ignore=current/tests/test_atom_projection_execution.py','--junitxml='+str(out/'original_tests.xml')])]
    commands.extend(('legacy_'+mode,[str(ROOT/'analysis/legacy_bitexact_source4_v1.py'),mode]) for mode in ['old','new','compare'])
    try:
        for name,args in commands:
            run=subprocess.run([PYTHON,'-B']+args,cwd=SOURCE,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=2400)
            row={'name':name,'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr};checks.append(row)
            (out/(name+'.stdout.txt')).write_text(run.stdout);(out/(name+'.stderr.txt')).write_text(run.stderr)
            print(name,run.returncode,run.stdout[-1500:],run.stderr[-1500:],flush=True)
            assert run.returncode==0,(name,run.returncode)
        counts={name:junit(out/(name+'.xml')) for name in ['new_execution','original_tests']}
        assert counts['new_execution']=={'tests':12,'failures':0,'errors':0,'skipped':0}
        assert counts['original_tests']['failures']==counts['original_tests']['errors']==0
        assert counts['original_tests']['tests']-counts['original_tests']['skipped']==2016
        legacy=json.loads((out/'legacy_bitexact/result.json').read_text());assert legacy['status']=='LEGACY_V2_BITEXACT_PASS' and legacy['compared_tensors']>0
        with ThreadPoolExecutor(16) as pool:list(pool.map(check,pins));list(pool.map(check,candidate))
        document.update(status='ATOM_PROJECTION_CPU_C6_AND_LEGACY_PASS_NOT_ADOPTED',test_counts=counts,
          legacy_reference=ref(out/'legacy_bitexact/result.json'),original_99_sources_unchanged=True)
    except BaseException as exc:document.update(status='ATOM_PROJECTION_CPU_C6_FAILED_NOT_ADOPTED',error=repr(exc));raise
    finally:
        document['elapsed_seconds']=time.monotonic()-start
        with (out/'result.json').open('x') as f:json.dump(document,f,indent=2,allow_nan=False);f.write('\n')
if __name__=='__main__':main()
