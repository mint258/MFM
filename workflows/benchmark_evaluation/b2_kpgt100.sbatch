#!/bin/bash
#SBATCH --job-name=B2-KPGT-fixed100
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=01:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B2_kpgt100_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import json,os,time,subprocess,signal,urllib.request,zipfile,shutil
from pathlib import Path
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.shared_reader import SharedB0Reader
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,2*1024**3,quota,own_concurrent_bytes=24*1024**3)
safe()
out=b1/'environments'/('kpgt_smoke100_job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
temp=out/'tmp';temp.mkdir()
python=str(b1/'environments/kpgt_job_4536914/venv/bin/python')
source=b1/'B2_remaining_sources/job_4536914/KPGT_source'
env=dict(os.environ,TMPDIR=str(temp),PIP_NO_CACHE_DIR='1',DGLBACKEND='pytorch',DGLDEFAULTDIR=str(out/'dgl_cache'),XDG_CACHE_HOME=str(out/'cache'),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
def run(args,**kwargs):
    safe();process=subprocess.Popen(args,env=env,start_new_session=True,**kwargs)
    try:
        while process.poll() is None:safe();time.sleep(5)
    except BaseException:
        os.killpg(process.pid,signal.SIGTERM);process.wait();raise
    return process.wait()
report={'model':'KPGT','job':os.environ['SLURM_JOB_ID'],'commit':'47dc1646c70b2138a157de481d24a1ac35d174cd','code_license':'Apache-2.0','weight_license':'MIT, official figshare record','weights_source':'https://figshare.com/s/d488f30c23946cf6898f','python':python,'fixed100':str(b1/'smoke100/job_4536859/fixed100.json'),'status':'PREPARING','weights_loaded':False,'full_representation_extraction':False}
try:
    with (out/'pip_install.log').open('x') as log:
        rc=run([python,'-m','pip','install','--no-cache-dir','--disable-pip-version-check','--retries','1','--timeout','30','dgl==1.1.3','dgllife==0.3.2','descriptastorus'],stdout=log,stderr=subprocess.STDOUT)
    if rc:raise RuntimeError('DEPENDENCY_INSTALL_EXIT_'+str(rc))
    url='https://figshare.com/ndownloader/files/35369662?private_link=d488f30c23946cf6898f&benchmark_b1_time='+str(int(time.time()))
    packed=out/'pretrained.zip'
    safe()
    with urllib.request.urlopen(url,timeout=120) as response,packed.open('xb') as stream:
        total=0
        while True:
            block=response.read(8*1024**2)
            if not block:break
            total+=len(block)
            if total>512*1024**2:raise ValueError('KPGT weight archive exceeds 512MiB forecast')
            safe();stream.write(block)
    checkpoint=out/'base.pth'
    with zipfile.ZipFile(packed) as archive:
        choices=[x for x in archive.infolist() if x.filename.endswith('/base.pth') or x.filename=='base.pth']
        if len(choices)!=1 or choices[0].file_size>1024**3:raise ValueError('Expected one KPGT base pretrained checkpoint')
        safe()
        with archive.open(choices[0]) as binary,checkpoint.open('xb') as sink:shutil.copyfileobj(binary,sink,8*1024**2)
    manifest=json.loads(Path(entry['manifest']).read_text());selected=json.loads(Path(report['fixed100']).read_text())['molecules']
    with SharedB0Reader(manifest['Sprime_and_D']['queue']) as reader:
        molecules=[reader.get(record['dataset'],record['record_id'])['result']['model_smiles'] for record in selected]
    molecule_file=out/'fixed100_smiles.json';molecule_file.write_text(json.dumps(molecules))
    source_code="\nimport json,sys,torch,numpy as np\nfrom pathlib import Path\nfrom rdkit import Chem\ntorch.set_num_threads(1)\nsource,checkpoint,molecule_file=sys.argv[1:]\nsys.path.insert(0,source)\nfrom src.data.featurizer import Vocab,N_ATOM_TYPES,N_BOND_TYPES,smiles_to_graph_tune\nfrom src.data.descriptors.rdNormalizedDescriptors import RDKit2DNormalized\nfrom src.data.collator import Collator_tune\nfrom src.model.light import LiGhTPredictor\nfrom src.model_config import config_dict\nconfig=config_dict['base'];vocab=Vocab(N_ATOM_TYPES,N_BOND_TYPES)\nmodel=LiGhTPredictor(d_node_feats=config['d_node_feats'],d_edge_feats=config['d_edge_feats'],d_g_feats=config['d_g_feats'],d_hpath_ratio=config['d_hpath_ratio'],n_mol_layers=config['n_mol_layers'],path_length=config['path_length'],n_heads=config['n_heads'],n_ffn_dense_layers=config['n_ffn_dense_layers'],input_drop=0,attn_drop=0,feat_drop=0,n_node_types=vocab.vocab_size)\npayload=torch.load(checkpoint,map_location='cpu',weights_only=True)\nmodel.load_state_dict({key.removeprefix('module.'):value for key,value in payload.items()},strict=True)\nmodel.eval();generator=RDKit2DNormalized();samples=[]\nmolecules=json.loads(Path(molecule_file).read_text());collator=Collator_tune(config['path_length'])\nfor smiles in molecules:\n    graph=smiles_to_graph_tune(smiles,max_length=config['path_length'],n_virtual_nodes=2)\n    if graph is None:raise ValueError('Official KPGT graph featurization failed')\n    fp=torch.tensor(list(Chem.RDKFingerprint(Chem.MolFromSmiles(smiles),minPath=1,maxPath=7,fpSize=512)),dtype=torch.float32)\n    descriptor=np.asarray(generator.process(smiles)[1:],dtype=np.float32)\n    if descriptor.shape!=(200,):raise ValueError('Official KPGT descriptor interface changed')\n    # Exact official finetune_dataset.py preprocessing for missing descriptors.\n    md=torch.from_numpy(np.where(np.isnan(descriptor),0,descriptor))\n    samples.append((smiles,graph,fp,md,torch.zeros(1)))\noutputs=[]\nwith torch.inference_mode():\n    for index in range(0,100,8):\n        _,graph,fp,md,_=collator(samples[index:index+8])\n        values=model.generate_fps(graph,fp,md)\n        if not torch.isfinite(values).all():raise ValueError('Nonfinite output')\n        outputs.append(values.cpu())\nresult=torch.cat(outputs)\nassert len(molecules)==100 and result.shape[0]==100\nprint('KPGT_SMOKE100_INFERENCE_COMPLETE',json.dumps({'shape':list(result.shape),'weights_loaded_strict':True,'graph_adapter':'Official smiles_to_graph_tune + Collator_tune + generate_fps','descriptor_adapter':'Official RDKit2DNormalized200 + official NaN-to-zero preprocessing','no_own_conformers':True}),flush=True)\n"
    with (out/'inference_stdout.txt').open('x') as log:
        rc=run([python,'-B','-c',source_code,str(source),str(checkpoint),str(molecule_file)],stdout=log,stderr=subprocess.STDOUT)
    if rc:raise RuntimeError('SMOKE100_INTERFACE_EXIT_'+str(rc))
    report.update(status='SMOKE100_INFERENCE_COMPLETE',weights_loaded=True,checkpoint=str(checkpoint),checkpoint_bytes=checkpoint.stat().st_size,output_dimension=2304)
except Exception as error:report.update(status='FAILED_FIRST_ATTEMPT',error_type=type(error).__name__,error=str(error)[:300])
safe();(out/'availability_attempt.json').write_text(json.dumps(report,indent=2)+'\n')
with (out/'effective_freeze.txt').open('x') as stream:run([python,'-m','pip','freeze'],stdout=stream)
print('B2_KPGT_ATTEMPT',json.dumps(report),flush=True)

PY
