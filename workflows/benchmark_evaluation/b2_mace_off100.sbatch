#!/bin/bash
#SBATCH --job-name=B2-maceoff-100
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-10
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B2_maceoff_100_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import json,os,signal,subprocess,time,urllib.request
from pathlib import Path
from workflows.benchmark_data.admission import protect
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())
root=Path(entry['data_root']); quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,8*1024**3,quota,own_concurrent_bytes=16*1024**3)
safe()
out=root.parent/('benchmark_B1_20261119/environments/maceoff_job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
temp=out/'tmp';temp.mkdir()
environment=dict(os.environ,TMPDIR=str(temp),PIP_NO_CACHE_DIR='1',TORCH_HOME=str(out/'torch_cache'),XDG_CACHE_HOME=str(out/'cache'))
def run(args,**kwargs):
    safe();child=subprocess.Popen(args,env=environment,start_new_session=True,**kwargs)
    try:
        while child.poll() is None:
            safe();time.sleep(5)
    except BaseException:
        os.killpg(child.pid,signal.SIGTERM);child.wait();raise
    if child.returncode:raise RuntimeError('Environment/inference exit '+str(child.returncode))
python='/share/home/zixiao/.conda/envs/chemprop/bin/python'
run([python,'-m','venv','--system-site-packages',str(out/'venv')])
python=str(out/'venv/bin/python')
url='https://raw.githubusercontent.com/ACEsuit/mace-off/main/mace_off23/MACE-OFF23_small.model'
report={'model':'MACE-OFF23-small','job':os.environ['SLURM_JOB_ID'],'source':'https://github.com/ACEsuit/mace','checkpoint_source':url,'code_license':'MIT','checkpoint_license':'Academic Software License (ASL); see https://github.com/gabor1/ASL','geometry':'B0 shared S-prime UFF, fixed100 first accepted conformer','comparison_metrics_computed':False}
try:
    run([python,'-m','pip','install','--disable-pip-version-check','--no-cache-dir','--retries','1','--timeout','30','mace-torch'])
    target=out/'MACE-OFF23_small.model';partial=out/'MACE-OFF23_small.model.partial'
    with urllib.request.urlopen(url,timeout=45) as response,partial.open('xb') as stream:
        while True:
            block=response.read(1024*1024)
            if not block:break
            safe();stream.write(block)
    os.replace(partial,target)
    source_code="import json,os,sys,importlib.metadata\nfrom pathlib import Path\nimport numpy as np,torch\nfrom ase import Atoms\nfrom mace.calculators import MACECalculator\nfrom workflows.benchmark_data.shared_reader import SharedB0Reader\nout=Path(sys.argv[1])\nentry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())\nmanifest=json.loads(Path(entry['manifest']).read_text())\nfixed=Path(entry['data_root']).parent/'benchmark_B1_20261119/smoke100/job_4536859/fixed100.json'\nselected=json.loads(fixed.read_text())['molecules']\ntorch.set_num_threads(2)\ncalc=MACECalculator(model_paths=str(out/'MACE-OFF23_small.model'),device='cpu',default_dtype='float64')\nshapes=[]\nwith SharedB0Reader(manifest['Sprime_and_D']['queue']) as reader:\n    for record in selected:\n        value=reader.get(record['dataset'],record['record_id'])['result']\n        atoms=Atoms(numbers=value['atomic_numbers'],positions=np.asarray(value['conformers'][0]['coordinates_A'],dtype=np.float64))\n        descriptors=np.asarray(calc.get_descriptors(atoms,invariants_only=True))\n        assert descriptors.shape[0]==len(atoms) and np.isfinite(descriptors).all()\n        shapes.append(list(descriptors.shape))\nassert len(shapes)==100\nprint('MACE_OFF_SMOKE100',json.dumps({'version':importlib.metadata.version('mace-torch'),'molecules':len(shapes),'atomic_descriptor_shapes':shapes,'fixed100':str(fixed),'conformer_index':0,'geometry':'shared B0 S-prime UFF, original atom order','dtype':'float64'}),flush=True)\n"
    with (out/'inference_stdout.txt').open('x') as output:run([python,'-B','-c',source_code,str(out)],stdout=output)
    report.update(status='SMOKE100_INFERENCE_COMPLETE',weights_loaded=True,checkpoint_bytes=target.stat().st_size,inference_stdout=str(out/'inference_stdout.txt'))
except Exception as exc:
    report.update(status='ENVIRONMENT_OR_INFERENCE_INCOMPLETE',error_type=type(exc).__name__,weights_loaded=False)
safe()
(out/'availability_attempt.json').write_text(json.dumps(report,indent=2)+'\n')
with (out/'effective_freeze.txt').open('x') as output:subprocess.run([python,'-m','pip','freeze'],stdout=output,env=environment,check=True)
print(json.dumps(report,indent=2),flush=True)
PY
