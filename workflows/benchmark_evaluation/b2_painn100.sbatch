#!/bin/bash
#SBATCH --job-name=B2-PaiNN-fixed100
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=01:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B2_painn100_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import json,os,time,subprocess,signal
from pathlib import Path
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.shared_reader import SharedB0Reader
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,6*1024**3,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'environments'/('painn_job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
temp=out/'tmp';temp.mkdir()
env=dict(os.environ,TMPDIR=str(temp),PIP_NO_CACHE_DIR='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',XDG_CACHE_HOME=str(out/'cache'))
def run(args,**kwargs):
    safe();process=subprocess.Popen(args,env=env,start_new_session=True,**kwargs)
    try:
        while process.poll() is None:safe();time.sleep(5)
    except BaseException:
        os.killpg(process.pid,signal.SIGTERM);process.wait();raise
    return process.wait()
python='/share/home/zixiao/.conda/envs/chemprop/bin/python'
subprocess.run([python,'-m','venv','--system-site-packages',str(out/'venv')],check=True);python=str(out/'venv/bin/python')
report={'model':'PaiNN (SchNetPack)','job':os.environ['SLURM_JOB_ID'],'infrastructure_continuation_of_job':4536933,'source':'https://github.com/atomistic-machine-learning/schnetpack','python':python,'weights':'Not applicable: from-scratch reference, random initialization seed20261025','license':'MIT SchNetPack','fixed100':str(b1/'smoke100/job_4536859/fixed100.json'),'no_own_conformers':True,'status':'PREPARING','full_representation_extraction':False}
try:
    with (out/'pip_install.log').open('x') as log:
        rc=run([python,'-m','pip','install','--disable-pip-version-check','--no-cache-dir','--retries','1','--timeout','30','schnetpack==2.1.1'],stdout=log,stderr=subprocess.STDOUT)
    if rc:raise RuntimeError('DEPENDENCY_INSTALL_EXIT_'+str(rc))
    manifest=json.loads(Path(entry['manifest']).read_text());selected=json.loads(Path(report['fixed100']).read_text())['molecules'];molecules=[]
    with SharedB0Reader(manifest['Sprime_and_D']['queue']) as reader:
        for record in selected:
            molecule=reader.get(record['dataset'],record['record_id'])['result']
            molecules.append({'atomic_numbers':molecule['atomic_numbers'],'coordinates_A':molecule['conformers'][0]['coordinates_A']})
    inputs=out/'shared_Sprime100_inputs.json';inputs.write_text(json.dumps(molecules))
    source_code="\nimport json,sys,torch,numpy as np\nfrom pathlib import Path\nfrom ase import Atoms\nimport schnetpack as spk\nfrom schnetpack import properties\ntorch.set_num_threads(1);torch.manual_seed(20261025)\nconverter=spk.interfaces.AtomsConverter(neighbor_list=spk.transform.ASENeighborList(cutoff=5.0),dtype=torch.float32,device='cpu')\nrepresentation=spk.representation.PaiNN(n_atom_basis=128,n_interactions=3,radial_basis=spk.nn.GaussianRBF(n_rbf=20,cutoff=5.0),cutoff_fn=spk.nn.CosineCutoff(5.0)).eval()\ndistances=spk.atomistic.PairwiseDistances()\nmolecules=json.loads(Path(sys.argv[1]).read_text());widths=set();vector_shapes=set();atoms_total=0\nwith torch.inference_mode():\n    for record in molecules:\n        atoms=Atoms(numbers=record['atomic_numbers'],positions=np.asarray(record['coordinates_A'],dtype=np.float64),pbc=False)\n        inputs=distances(converter(atoms));output=representation(inputs)\n        scalar=output[properties.scalar_representation];vector=output[properties.vector_representation]\n        assert scalar.shape[0]==len(atoms) and scalar.shape[1]==128 and torch.isfinite(scalar).all() and torch.isfinite(vector).all()\n        widths.add(int(scalar.shape[-1]));vector_shapes.add(tuple(vector.shape[1:]));atoms_total+=len(atoms)\nassert len(molecules)==100\nprint('PAINN_SMOKE100_INFERENCE_COMPLETE',json.dumps({'molecules':len(molecules),'atomic_scalar_widths':sorted(widths),'atomic_vector_shapes':sorted(vector_shapes),'total_atoms':atoms_total,'weights':'Random initialization seed20261025, from-scratch baseline; no pretrained weights required','coordinates':'Shared B0 first accepted UFF, unchanged atom ordering; input-only float32 conversion'}),flush=True)\n"
    with (out/'inference_stdout.txt').open('x') as log:
        rc=run([python,'-B','-c',source_code,str(inputs)],stdout=log,stderr=subprocess.STDOUT)
    if rc:raise RuntimeError('SMOKE100_INTERFACE_EXIT_'+str(rc))
    report.update(status='SMOKE100_INFERENCE_COMPLETE',package_version='2.1.1',atomic_scalar_dimension=128,scalar_and_vector_outputs=True)
except Exception as error:report.update(status='FAILED_FIRST_ATTEMPT',error_type=type(error).__name__,error=str(error)[:300])
safe();(out/'availability_attempt.json').write_text(json.dumps(report,indent=2)+'\n')
with (out/'effective_freeze.txt').open('x') as stream:run([python,'-m','pip','freeze'],stdout=stream)
print('B2_PAINN_ATTEMPT',json.dumps(report),flush=True)

PY
