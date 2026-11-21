env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps srun --overlap --jobid=4537025 --cpus-per-task=1 --ntasks=1 --cpu-bind=cores --chdir=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119 /share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'CU128_LUSTRE_BACKEND_CPU_PREPARATION' >/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_CUDA128_Lustre_backend_CPU_prepare.log 2>&1 &
import os,sys,types,json
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119')
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
protect(root,1024**2,quota,own_concurrent_bytes=40*1024**3)
import signal,time,subprocess
GIB=1024**3
def capacity():
    for location in ('/','/tmp'):
        stat=os.statvfs(location);reserve=max(10*GIB,.10*stat.f_blocks*stat.f_frsize)
        if stat.f_bavail*stat.f_frsize<reserve+16*1024**2 or stat.f_favail<2000:
            raise RuntimeError('Actual CPU-node system/tmp reserve would be crossed')
    target=Path('/lfshome/zixiao')
    stat=os.statvfs(target)
    if stat.f_bavail*stat.f_frsize<.10*stat.f_blocks*stat.f_frsize+16*GIB or stat.f_favail<100000:
        raise RuntimeError('Actual Lustre bytes/inodes cannot cover the package/unpack peak')
    result=subprocess.run(['lfs','quota','-u',str(os.getuid()),'/lfshome'],text=True,capture_output=True,timeout=15)
    if result.returncode:raise RuntimeError('Actual destination Lustre UID quota observation failed')
    line=next((line for line in result.stdout.splitlines() if line.strip().startswith('/lfshome ')),None)
    if line is None:raise RuntimeError('No actual destination quota row')
    fields=line.split();used=int(fields[1].rstrip('*'));limit=int(fields[3].rstrip('*'))
    if limit<=0 or (limit-used)*1024<100*GIB+16*GIB:
        raise RuntimeError('Lustre UID quota must retain100GiB after the16GiB package/unpack peak')
    return dict(actual_destination='/lfshome',uid=os.getuid(),quota_raw=result.stdout,
                available_bytes=stat.f_bavail*stat.f_frsize,available_inodes=stat.f_favail,
                planned_package_and_unpack_peak_bytes=16*GIB,account_floor_bytes=100*GIB,
                model_future_bytes_on_this_filesystem=0,
                model_future_scope='Existing P/D model outputs resolve to/share; native data labels/geometry remain/share; this prefix is packages only')
capacity()
out=Path('/lfshome/zixiao/benchmark_B1_environments_20261120/gpu_cu128_backend_node22_v1')
out.mkdir(parents=True,exist_ok=False)
temporary=out/'tmp';temporary.mkdir();backend=out/'packages';backend.mkdir()
environ=dict(os.environ,TMPDIR=str(temporary),TMP=str(temporary),TEMP=str(temporary),
             PIP_NO_INPUT='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PIP_NO_CACHE_DIR='1',
             CUDA_VISIBLE_DEVICES='')
command=[sys.executable,'-m','pip','install','--no-cache-dir','--target',str(backend),
         '--index-url','https://download.pytorch.org/whl/cu128','torch==2.7.1+cu128']
started=time.monotonic()
print('CPU_CU128_BACKEND_PREPARATION_STARTED',os.environ['SLURM_JOB_ID'],os.environ['SLURM_STEP_ID'],str(out),flush=True)
with (out/'pip.log').open('x') as stream:
    process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                             env=environ,start_new_session=True)
    try:
        while process.poll() is None:
            capacity();time.sleep(20)
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait()
        raise
report=dict(status='CU128_PACKAGES_INSTALLED' if process.returncode==0 else 'CU128_ENVIRONMENT_UNRESOLVED',
    job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],backend=str(backend),
    returncode=process.returncode,elapsed_seconds=time.monotonic()-started,
    actual_CPU_node=os.uname().nodename,maximum_future_package_and_unpack_bytes=16*GIB,
    known_D_stage0_reserve_on_share_bytes=4*GIB,destination_reserve=capacity(),no_scientific_payload_read=True,original_environments_modified=False)
if process.returncode==0:
    capacity()
    program="import sys,json,torch; assert torch.__version__=='2.7.1+cu128'; assert 'sm_120' in torch._C._cuda_getArchFlags(); print(json.dumps(dict(python=sys.version.split()[0],torch=torch.__version__,cuda=torch.version.cuda,arch_flags=torch._C._cuda_getArchFlags(),source=torch.__file__)))"
    inspect_env=dict(environ,PYTHONPATH=str(backend)+':'+environ.get('PYTHONPATH',''))
    result=subprocess.run([sys.executable,'-B','-c',program],text=True,capture_output=True,env=inspect_env)
    (out/'CPU_imports.log').write_text(result.stdout+result.stderr)
    report['CPU_import_returncode']=result.returncode
    if result.returncode==0:
        report['runtime']=json.loads(result.stdout.strip().splitlines()[-1])
        report['status']='BLACKWELL_CUDA128_BACKEND_CPU_READY'
    else:report['status']='CU128_ENVIRONMENT_UNRESOLVED'
capacity();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('CPU_CU128_BACKEND_PREPARATION_CLOSED',json.dumps(report),flush=True)
if report['status']!='BLACKWELL_CUDA128_BACKEND_CPU_READY':raise SystemExit(1)
CU128_LUSTRE_BACKEND_CPU_PREPARATION
printf 'CU128_CPU_PREPARATION_SRUN_PID|%s\n' "$!"
