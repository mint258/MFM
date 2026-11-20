#!/bin/bash
#SBATCH --job-name=B2-QuADMET-fixed100
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B2_quadmet100_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import json,os,time,subprocess,signal,urllib.request,tarfile,io
from pathlib import Path
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.shared_reader import SharedB0Reader
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,2*1024**3,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'environments'/('quadmetformer_job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
temp=out/'tmp';temp.mkdir()
env=dict(os.environ,TMPDIR=str(temp),PIP_NO_CACHE_DIR='1',MAX_JOBS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',XDG_CACHE_HOME=str(out/'cache'))
def run(args,**kwargs):
    safe();process=subprocess.Popen(args,env=env,start_new_session=True,**kwargs)
    try:
        while process.poll() is None:safe();time.sleep(5)
    except BaseException:
        os.killpg(process.pid,signal.SIGTERM);process.wait();raise
    return process.wait()
python='/share/home/zixiao/.conda/envs/chemprop/bin/python'
subprocess.run([python,'-m','venv','--system-site-packages',str(out/'venv')],check=True);python=str(out/'venv/bin/python')
commit='b5789c52a2701009005b98930fae24f8c136142f'
weight_path='single_conf/dipole_moment_e3fp_hl_gap_total_energy_lowdin.ckpt'
report={'model':'QuADMET-Former','job':os.environ['SLURM_JOB_ID'],'repository':'https://github.com/arunraja-hub/quadmetformer','commit':commit,'code_license':'MIT','weights_license':'MIT badge in official HF model-card commit dbc6095bc85f1fd52b4f6d1001a7003f43db8adf','checkpoint_source':'https://huggingface.co/arunraja007/quadmetformer/blob/main/'+weight_path,'variant':'Published ALL-target single-conformer pretrained checkpoint, fixed before downstream model results','python':python,'fixed100':str(b1/'smoke100/job_4536859/fixed100.json'),'status':'PREPARING','weights_loaded':False,'no_own_conformers':True,'full_representation_extraction':False}
try:
    safe()
    with urllib.request.urlopen('https://codeload.github.com/arunraja-hub/quadmetformer/tar.gz/'+commit,timeout=90) as response:archive=response.read(50*1024**2+1)
    if len(archive)>50*1024**2:raise ValueError('Source archive exceeds forecast')
    (out/'source.tar.gz').write_bytes(archive);source=out/'source';source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as stream:
        members=stream.getmembers()
        if sum(x.size for x in members)>512*1024**2:raise ValueError('Source extraction exceeds forecast')
        for member in members:
            parts=Path(member.name).parts[1:]
            if not parts:continue
            if '..' in parts or Path(*parts).is_absolute():raise ValueError('Unsafe source archive path')
            target=source.joinpath(*parts)
            if member.isdir():target.mkdir(parents=True,exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True,exist_ok=True)
                with stream.extractfile(member) as binary:target.write_bytes(binary.read())
            else:raise ValueError('Unsupported archive link')
    with (out/'pip_install.log').open('x') as log:
        rc=run([python,'-m','pip','install','--disable-pip-version-check','--no-cache-dir','--retries','1','--timeout','30','--find-links','https://data.pyg.org/whl/torch-2.10.0+cpu.html','torch-scatter==2.1.2','torch-cluster==1.6.3','torch-geometric','e3nn'],stdout=log,stderr=subprocess.STDOUT)
    if rc:raise RuntimeError('DEPENDENCY_INSTALL_EXIT_'+str(rc))
    checkpoint=out/'quadmet_ALL_single_conf.ckpt';safe()
    url='https://hf-mirror.com/arunraja007/quadmetformer/resolve/main/'+weight_path
    with urllib.request.urlopen(url,timeout=120) as response,checkpoint.open('xb') as stream:
        total=0
        while True:
            block=response.read(4*1024**2)
            if not block:break
            total+=len(block)
            if total>64*1024**2:raise ValueError('Checkpoint exceeds public size forecast')
            safe();stream.write(block)
    manifest=json.loads(Path(entry['manifest']).read_text());selected=json.loads(Path(report['fixed100']).read_text())['molecules'];molecules=[]
    with SharedB0Reader(manifest['Sprime_and_D']['queue']) as reader:
        for record in selected:
            molecule=reader.get(record['dataset'],record['record_id'])['result']
            molecules.append({'atomic_numbers':molecule['atomic_numbers'],'coordinates_A':molecule['conformers'][0]['coordinates_A']})
    inputs=out/'shared_Sprime100_inputs.json';inputs.write_text(json.dumps(molecules))
    source_code="\nimport json,sys,types,re,torch,numpy as np\nfrom pathlib import Path\nfrom torch_geometric.data import Data\ntorch.set_num_threads(1)\nsource,checkpoint,inputs_path,metadata_path=sys.argv[1:]\nsys.path.insert(0,source)\n# The author imports this absent module for the unused multi-conformer branch.\n# B2 uses one common fixed conformer and invokes only the published encode method.\nsys.modules['models.conformerAttention']=types.ModuleType('models.conformerAttention')\nfrom models.torchmdnet import TorchMD_ET\nmodel=TorchMD_ET(hidden_channels=128,num_layers=6,final_embedding_size=128,mol_targets={},atom_targets={},pretrain_or_downstream='pretrain',multiple_conformer=False).cpu().eval()\npayload=torch.load(checkpoint,map_location='cpu',weights_only=True)\nstate=payload['state_dict'] if 'state_dict' in payload else payload\nstate={re.sub(r'^model\\.','',key):value for key,value in state.items()}\nprefix='shared_backbone.'\nencoder={key[len(prefix):]:value for key,value in state.items() if key.startswith(prefix)}\nnorm={key[len('out_norm.'):]:value for key,value in state.items() if key.startswith('out_norm.')}\nif not encoder or not norm:raise ValueError('Published encoder or output normalization state unavailable')\nmodel.shared_backbone.load_state_dict(encoder,strict=True);model.out_norm.load_state_dict(norm,strict=True)\nmolecules=json.loads(Path(inputs_path).read_text());widths=set();total_atoms=0;graphs=[]\nwith torch.inference_mode():\n    for record in molecules:\n        z=torch.tensor(record['atomic_numbers'],dtype=torch.long)\n        positions=torch.tensor(record['coordinates_A'],dtype=torch.float32)\n        data=Data(atomic_numbers=z,z=z,pos=positions,batch=torch.zeros(len(z),dtype=torch.long))\n        value=model.encode(data)\n        if value.shape!=(len(z),128) or not torch.isfinite(value).all():raise ValueError('Invalid published QuADMET atom encoder output')\n        widths.add(int(value.shape[-1]));total_atoms+=len(z);graphs.append(value.mean(0))\nassert len(molecules)==100\nmetadata={'status':'SMOKE100_INFERENCE_COMPLETE','molecules':100,'atomic_scalar_widths':sorted(widths),'mean_pooled_shape':[len(graphs),int(graphs[0].shape[-1])],'total_atoms':total_atoms,'encoder_and_out_norm_loaded_strict':True,'architecture_source':'Pinned pretraining/pretrain.py 128 channels and six layers; trainer.py uses the published constructor defaults, including 16 attention heads','adapter':'Official single-conformer encode with an empty import shim solely for an absent unused multi-conformer module','geometry':'Shared B0 first accepted UFF conformer, unchanged atom order; input-only float32 conversion','full_representation_extraction':False}\nPath(metadata_path).write_text(json.dumps(metadata,indent=2)+'\\n');print('QUADMET_SMOKE100_INFERENCE_COMPLETE',json.dumps(metadata),flush=True)\n"
    with (out/'inference_stdout.txt').open('x') as log:
        rc=run([python,'-B','-c',source_code,str(source),str(checkpoint),str(inputs),str(out/'interface_metadata.json')],stdout=log,stderr=subprocess.STDOUT)
    if rc:raise RuntimeError('SMOKE100_INTERFACE_EXIT_'+str(rc))
    report.update(status='SMOKE100_INFERENCE_COMPLETE',weights_loaded=True,interface_metadata=str(out/'interface_metadata.json'))
except Exception as error:report.update(status='FAILED_FIRST_ATTEMPT',error_type=type(error).__name__,error=str(error)[:300])
safe();(out/'availability_attempt.json').write_text(json.dumps(report,indent=2)+'\n')
with (out/'effective_freeze.txt').open('x') as stream:run([python,'-m','pip','freeze'],stdout=stream)
print('B2_QUADMET_ATTEMPT',json.dumps(report),flush=True)

PY
