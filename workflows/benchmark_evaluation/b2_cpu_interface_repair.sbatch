#!/bin/bash
#SBATCH --job-name=B2-cpu-interface-repair
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B2_cpu_interface_repair_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MAX_JOBS=2 LOKY_MAX_CPU_COUNT=2 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import json,os,signal,subprocess,time,urllib.request
from pathlib import Path
from workflows.benchmark_data.admission import protect
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())
root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,8*1024**3,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'environments'/('cpu_interface_repair_job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
temp=out/'tmp';temp.mkdir()
environment=dict(os.environ,TMPDIR=str(temp),PIP_NO_CACHE_DIR='1',TORCH_HOME=str(out/'torch_cache'),XDG_CACHE_HOME=str(out/'cache'))
def run(args,**kwargs):
    safe();child=subprocess.Popen(args,env=environment,start_new_session=True,**kwargs)
    try:
        while child.poll() is None:safe();time.sleep(5)
    except BaseException:
        os.killpg(child.pid,signal.SIGTERM);child.wait();raise
    if child.returncode:raise RuntimeError('Inference exit '+str(child.returncode))
results=[]
mono=b1/'environments/monroe_job_4536881'
report={'model':'Monroe','job':os.environ['SLURM_JOB_ID'],'retry_of_job':4536881,'source_commit':'de075eabe98e4adbbedbc86ca9e877f4bfd9b629','environment':str(mono/'venv'),'checkpoint':str(mono/'checkpoint'),'repair':'Official config/state loader with device=cpu, strict encoder parameter load; no weight or scientific input changes','code_license':'MIT','checkpoint_license':'MIT repository','full_representation_extraction':False}
try:
    source_code="import json,sys,importlib.metadata\nfrom pathlib import Path\nimport numpy as np,torch\nfrom rdkit import Chem\nfrom torch_geometric.data import Data\nfrom monroe.model.ckpt import _load_config_and_weights,_build_encoder\nfrom monroe.model.featurizer import build_from_mol_and_coords\nfrom workflows.benchmark_data.shared_reader import SharedB0Reader\nout=Path(sys.argv[1])\nentry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())\nmanifest=json.loads(Path(entry['manifest']).read_text())\nfixed=Path(entry['data_root']).parent/'benchmark_B1_20261119/smoke100/job_4536859/fixed100.json'\nselected=json.loads(fixed.read_text())['molecules']\ntorch.set_num_threads(2)\nconfig,state=_load_config_and_weights(out/'checkpoint',device=torch.device('cpu'))\nencoder=_build_encoder(config).cpu()\nencoder_state={key[len('encoder.'):]:value for key,value in state.items() if key.startswith('encoder.')}\nassert encoder_state, 'No pretrained encoder parameters found'\nencoder.load_state_dict(encoder_state,strict=True)\nencoder.eval()\nshapes=[]\nwith SharedB0Reader(manifest['Sprime_and_D']['queue']) as reader:\n    for record in selected:\n        value=reader.get(record['dataset'],record['record_id'])['result']\n        params=Chem.SmilesParserParams();params.removeHs=False\n        mol=Chem.AddHs(Chem.MolFromSmiles(value['model_smiles'],params))\n        assert [a.GetAtomicNum() for a in mol.GetAtoms()]==value['atomic_numbers']\n        positions=np.asarray(value['conformers'][0]['coordinates_A'],dtype=np.float32)\n        graph=build_from_mol_and_coords(mol,pos_rdkit=positions,stereo_augmentation=True,symmetrize=True)\n        data=Data(x=torch.as_tensor(graph['node_float'],dtype=torch.float32),node_codes=torch.as_tensor(graph['node_codes'],dtype=torch.long),edge_index=torch.as_tensor(graph['edge_index'],dtype=torch.long),edge_codes=torch.as_tensor(graph['edge_codes'],dtype=torch.long),pos_in=torch.as_tensor(positions,dtype=torch.float32),batch=torch.zeros(len(mol.GetAtoms()),dtype=torch.long))\n        with torch.no_grad():embedding,_=encoder(data)\n        assert torch.isfinite(embedding).all()\n        shapes.append(list(embedding.shape))\nassert len(shapes)==100\nprint('MONROE_SMOKE100',json.dumps({'version':importlib.metadata.version('monroe'),'output_shapes':shapes,'fixed100':str(fixed),'geometry':'B0 shared S-prime UFF, first conformer, original model atom order','model_conformer_generation_called':False}),flush=True)\n"
    with (out/'monroe_inference_stdout.txt').open('x') as output:run([str(mono/'venv/bin/python'),'-B','-c',source_code,str(mono)],stdout=output)
    report.update(status='SMOKE100_INFERENCE_COMPLETE',weights_loaded=True,inference_stdout=str(out/'monroe_inference_stdout.txt'))
except Exception as exc:report.update(status='UNRESOLVED',error_type=type(exc).__name__,weights_loaded=False)
safe();(out/'monroe_availability.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True);results.append(report)
uni=b1/'environments/unimol_job_4536882';weights=out/'unimol_weights';weights.mkdir()
(weights/'mol.dict.txt').symlink_to('/share/home/zixiao/descriptor_analysis/ckpt/mol.dict.txt')
environment['UNIMOL_WEIGHT_DIR']=str(weights)
report={'model':'Uni-Mol-v1-all-H','job':os.environ['SLURM_JOB_ID'],'retry_of_job':4536882,'environment':str(uni/'venv'),'repair':'Acquire the missing original all-H checkpoint explicitly; source package 0.1.5 does not auto-download it','code_license':'MIT','checkpoint_license':'Not separately verified','full_representation_extraction':False}
try:
    target=weights/'mol_pre_all_h_220816.pt'
    for host in ('https://hf-mirror.com','https://huggingface.co'):
        url=host+'/dptech/Uni-Mol-Models/resolve/main/mol_pre_all_h_220816.pt'
        partial=weights/('mirror.partial' if 'mirror' in host else 'official.partial')
        try:
            safe()
            with urllib.request.urlopen(url,timeout=45) as response,partial.open('xb') as stream:
                while True:
                    block=response.read(1024*1024)
                    if not block:break
                    safe();stream.write(block)
            os.replace(partial,target);report['checkpoint_download_url']=url;break
        except Exception as exc:print('UNIMOL_CHECKPOINT_TRANSPORT',host,type(exc).__name__,flush=True)
    if not target.is_file():raise RuntimeError('Public original checkpoint transport unresolved')
    source_code="import json,sys,importlib.metadata\nfrom pathlib import Path\nimport numpy as np,torch\nfrom rdkit.Chem import GetPeriodicTable\nfrom unimol_tools import UniMolRepr\nfrom workflows.benchmark_data.shared_reader import SharedB0Reader\nentry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())\nmanifest=json.loads(Path(entry['manifest']).read_text())\nfixed=Path(entry['data_root']).parent/'benchmark_B1_20261119/smoke100/job_4536859/fixed100.json'\nselected=json.loads(fixed.read_text())['molecules']\natoms=[];coordinates=[]\nwith SharedB0Reader(manifest['Sprime_and_D']['queue']) as reader:\n    for record in selected:\n        value=reader.get(record['dataset'],record['record_id'])['result']\n        atoms.append([GetPeriodicTable().GetElementSymbol(int(z)) for z in value['atomic_numbers']])\n        coordinates.append(np.asarray(value['conformers'][0]['coordinates_A'],dtype=np.float64))\ntorch.set_num_threads(2)\nmodel=UniMolRepr(data_type='molecule',remove_hs=False,model_name='unimolv1',use_cuda=False,batch_size=8)\nresult=model.get_repr({'atoms':atoms,'coordinates':coordinates},return_atomic_reprs=True)\ngraph=np.asarray(result['cls_repr'])\natomic=result['atomic_reprs']\nassert graph.shape[0]==100 and np.isfinite(graph).all() and len(atomic)==100\nfor symbols,features in zip(atoms,atomic):assert len(symbols)==len(features) and np.isfinite(features).all()\nprint('UNIMOL_SMOKE100',json.dumps({'version':importlib.metadata.version('unimol-tools'),'graph_shape':list(graph.shape),'atomic_shapes':[list(np.asarray(x).shape) for x in atomic],'fixed100':str(fixed),'geometry':'B0 shared S-prime UFF, first conformer, original model atom order','remove_hs':False,'model_conformer_generation_called':False}),flush=True)\n"
    with (out/'unimol_inference_stdout.txt').open('x') as output:run([str(uni/'venv/bin/python'),'-B','-c',source_code],stdout=output)
    report.update(status='SMOKE100_INFERENCE_COMPLETE',weights_loaded=True,checkpoint_bytes=target.stat().st_size,inference_stdout=str(out/'unimol_inference_stdout.txt'))
except Exception as exc:report.update(status='UNRESOLVED',error_type=type(exc).__name__,weights_loaded=False)
safe();(out/'unimol_availability.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True);results.append(report)
(out/'summary.json').write_text(json.dumps({'job':os.environ['SLURM_JOB_ID'],'models':results},indent=2)+'\n')
PY
