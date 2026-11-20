env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps srun --overlap --jobid=4536985 --cpus-per-task=1 --ntasks=1 --cpu-bind=cores --chdir=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119 /share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'GPU_CU118_PRIVATE_ENVIRONMENTS'
import json,os,subprocess,sys
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119')
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,256*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe();out=root.parent/'benchmark_B1_20261119/environments'/('gpu_cu118_job_'+os.environ['SLURM_JOB_ID']+'_step_'+os.environ['SLURM_STEP_ID']);out.mkdir(parents=True)
base=Path(sys.prefix)/'lib/python3.11/site-packages'
old=Path('/share/home/zixiao/.venvs/model_v2_cu118_20261105/lib/python3.11/site-packages')
tab=root.parent/'benchmark_B1_20261119/environments/tabpfn_job_4536852/venv/lib/python3.11/site-packages'
backend=('torch','torchgen','functorch','nvidia','triton','sympy')
optional=('torchvision','torchaudio')
def belongs(name,package):
    return name==package or name.startswith(package+'-') or name.startswith(package+'.') or package=='nvidia' and name.startswith('nvidia_')
def skip(path):
    return path.name=='__pycache__' or path.suffix=='.pth' or any(belongs(path.name,x) for x in backend+optional)
if not (old/'torch').is_dir():raise RuntimeError('Existing closed CUDA11.8 Torch package is unavailable')
inspect_program="""import sys,json,importlib.metadata as m,torch,rdkit,chemprop
from lightning import pytorch as pl
versions={n:m.version(n) for n in ('torch','chemprop','lightning','torchmetrics','numpy','scikit-learn','rdkit')}
assert torch.__version__=='2.7.1+cu118' and torch.version.cuda=='11.8'
assert versions['chemprop']=='2.2.2' and rdkit.__version__=='2025.09.5'
if len(sys.argv)>1:
    import tabpfn
    from tabpfn import TabPFNRegressor
    versions['tabpfn']=m.version('tabpfn')
    assert versions['tabpfn']=='10.2.0'
print(json.dumps(dict(versions=versions,python=sys.version.split()[0],torch_source=torch.__file__,RDKit_source=rdkit.__file__,optional_vision_audio_not_exposed=True)))
"""
records=[]
for kind in ('chemprop','tabpfn'):
    env=out/kind;safe();subprocess.run([sys.executable,'-m','venv','--without-pip',str(env)],check=True)
    site=env/'lib/python3.11/site-packages'
    chosen={path.name:path for path in base.iterdir() if not skip(path)}
    if kind=='tabpfn':
        chosen.update({path.name:path for path in tab.iterdir() if not skip(path)})
    chosen.update({path.name:path for path in old.iterdir()
        if path.name!='__pycache__' and path.suffix!='.pth' and any(belongs(path.name,x) for x in backend)})
    for name,source in sorted(chosen.items()):
        destination=site/name
        if destination.exists() or destination.is_symlink():raise FileExistsError('Preserve existing private-environment entry: '+str(destination))
        destination.symlink_to(source,target_is_directory=source.is_dir())
    safe();python=env/'bin/python'
    result=subprocess.run([str(python),'-B','-c',inspect_program]+(['tabpfn'] if kind=='tabpfn' else []),text=True,capture_output=True)
    (out/(kind+'_imports.log')).write_text(result.stdout+result.stderr)
    record=dict(kind=kind,python=str(python),returncode=result.returncode,environment=str(env),source_package_links=len(chosen),base_packages=str(base),CUDA11_8_backend=str(old),original_environments_unchanged=True)
    if result.returncode==0:record['runtime']=json.loads(result.stdout.strip().splitlines()[-1])
    else:record['status']='IMPORT_FAILURE_PRESERVED'
    records.append(record);print('PRIVATE_CU118_RUNTIME',json.dumps(record),flush=True)
report=dict(status='PRIVATE_CUDA11_8_ENVIRONMENTS_READY' if all(r['returncode']==0 for r in records) else 'ENVIRONMENT_IMPORT_FAILURE_PRESERVED',job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],records=records,new_downloads=False,scientific_inputs_or_model_versions_changed=False,Torch_backend_compatibility_change='2.10.0+cu126 to existing2.7.1+cu118 for driver11.8 only',optional_vision_audio_excluded_from_private_search_path=True,existing_files_deleted=False)
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('GPU_CU118_ENVIRONMENT_SOURCE_CLOSED',out/'manifest.json',report['status'],flush=True)
GPU_CU118_PRIVATE_ENVIRONMENTS
