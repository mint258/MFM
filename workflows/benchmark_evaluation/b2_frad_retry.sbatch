#!/bin/bash
#SBATCH --job-name=B2-Frad-fixed100-retry
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B2_frad_retry_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import json,os,time,subprocess,signal,urllib.request
from pathlib import Path
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.shared_reader import SharedB0Reader
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,4*1024**3,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'environments'/('frad_smoke100_job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
temp=out/'tmp';temp.mkdir()
python=str(b1/'environments/frad_job_4536914/venv/bin/python');source=b1/'B2_remaining_sources/job_4536914/Frad_source'
env=dict(os.environ,TMPDIR=str(temp),PIP_NO_CACHE_DIR='1',MAX_JOBS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',XDG_CACHE_HOME=str(out/'cache'))
def run(args,**kwargs):
    safe();process=subprocess.Popen(args,env=env,start_new_session=True,**kwargs)
    try:
        while process.poll() is None:safe();time.sleep(5)
    except BaseException:
        os.killpg(process.pid,signal.SIGTERM);process.wait();raise
    return process.wait()
weight_record=json.loads((b1/'B2_remaining_sources/job_4536914/Frad_weight_record.json').read_text())
chosen=[row for row in weight_record['files'] if row['key'].startswith('step=399999-')]
assert len(chosen)==1
weight=chosen[0]
report={'model':'Frad','job':os.environ['SLURM_JOB_ID'],'source':'https://github.com/fengshikun/FradNMI','commit':'d4af0a60727b8d4fabb9f51f5332cba87468afe7','code_license':'MIT','checkpoint_record':'https://zenodo.org/records/12697467','checkpoint_rights':weight_record['metadata'].get('rights'),'checkpoint_name':weight['key'],'python':python,'fixed100':str(b1/'smoke100/job_4536859/fixed100.json'),'no_own_conformers':True,'status':'PREPARING_RETRY','attempt_number':2,'previous_attempt_job':4536939,'full_representation_extraction':False}
try:
    checkpoint=b1/'environments/frad_smoke100_job_4536939/frad_qm9_pretrained.ckpt'
    assert checkpoint.is_file()
    manifest=json.loads(Path(entry['manifest']).read_text());selected=json.loads(Path(report['fixed100']).read_text())['molecules'];molecules=[]
    with SharedB0Reader(manifest['Sprime_and_D']['queue']) as reader:
        for record in selected:
            molecule=reader.get(record['dataset'],record['record_id'])['result']
            molecules.append({'atomic_numbers':molecule['atomic_numbers'],'coordinates_A':molecule['conformers'][0]['coordinates_A']})
    inputs=out/'shared_Sprime100_inputs.json';inputs.write_text(json.dumps(molecules))
    source_code="\nimport json,sys,re,torch,numpy as np\nfrom pathlib import Path\ntorch.set_num_threads(2)\nsource,checkpoint,inputs_path,metadata_path=sys.argv[1:]\nsys.path.insert(0,source)\nfrom torchmdnet.models.torchmd_et import TorchMD_ET\npayload=torch.load(checkpoint,map_location='cpu',weights_only=False)\nparameters=payload['hyper_parameters']\nif parameters['model']!='equivariant-transformer':raise ValueError('Unexpected official encoder architecture')\nshared_keys=('embedding_dimension','num_layers','num_rbf','rbf_type','trainable_rbf','activation','neighbor_embedding','cutoff_lower','cutoff_upper','max_z','max_num_neighbors')\noptions={key:parameters[key] for key in shared_keys}\noptions['hidden_channels']=options.pop('embedding_dimension')\n# The pinned author's CLI defaults for fields absent from this older checkpoint.\noptions.update(attn_activation=parameters['attn_activation'],num_heads=parameters['num_heads'],distance_influence=parameters['distance_influence'],layernorm_on_vec=parameters['layernorm_on_vec'],md17=parameters.get('md17',False),seperate_noise=parameters.get('seperate_noise',False))\nmodel=TorchMD_ET(**options).cpu().eval()\nstate={re.sub(r'^model\\.','',key):value for key,value in payload['state_dict'].items()}\nprefix='representation_model.'\nencoder_state={key[len(prefix):]:value for key,value in state.items() if key.startswith(prefix)}\nif not encoder_state:raise ValueError('Official checkpoint lacks encoder state')\nmodel.load_state_dict(encoder_state,strict=True)\nmolecules=json.loads(Path(inputs_path).read_text());widths=set();vector_shapes=set();total_atoms=0\nwith torch.inference_mode():\n    for record in molecules:\n        z=torch.tensor(record['atomic_numbers'],dtype=torch.long)\n        positions=torch.tensor(record['coordinates_A'],dtype=torch.float32)\n        batch=torch.zeros(len(z),dtype=torch.long)\n        value=model(z,positions,batch=batch)\n        x=value[0];v=value[1]\n        if x.shape[0]!=len(z) or not torch.isfinite(x).all() or (v is not None and not torch.isfinite(v).all()):raise ValueError('Invalid atom feature interface')\n        widths.add(int(x.shape[-1]));total_atoms+=len(z)\n        if v is not None:vector_shapes.add(tuple(v.shape[1:]))\nassert len(molecules)==100\nmetadata={'status':'SMOKE100_INFERENCE_COMPLETE','model':'Frad','molecules':100,'atomic_scalar_widths':sorted(widths),'atomic_vector_shapes':sorted(vector_shapes),'total_atoms':total_atoms,'weights_loaded_encoder_strict':True,'model_hyperparameters':parameters,'compatibility_defaults_source':'Pinned Frad scripts/train.py md17=False and seperate_noise=False; strict encoder weight load, no output heads required for features','geometry':'Shared first accepted B0 UFF conformer, exact atom ordering, input-only float32 conversion','own_geometry_generated':False}\nPath(metadata_path).write_text(json.dumps(metadata,indent=2,default=str)+'\\n')\nprint('FRAD_SMOKE100_INFERENCE_COMPLETE',json.dumps({'atomic_scalar_widths':sorted(widths),'atomic_vector_shapes':sorted(vector_shapes),'molecules':100}),flush=True)\n"
    with (out/'inference_stdout.txt').open('x') as log:
        rc=run([python,'-B','-c',source_code,str(source),str(checkpoint),str(inputs),str(out/'interface_metadata.json')],stdout=log,stderr=subprocess.STDOUT)
    if rc:raise RuntimeError('SMOKE100_INTERFACE_EXIT_'+str(rc))
    report.update(status='SMOKE100_INFERENCE_COMPLETE',interface_metadata=str(out/'interface_metadata.json'),weights_loaded=True)
except Exception as error:report.update(status='UNRESOLVED_AFTER_TWO_FAILURES',error_type=type(error).__name__,error=str(error)[:300])
safe();(out/'availability_attempt.json').write_text(json.dumps(report,indent=2)+'\n')
with (out/'effective_freeze.txt').open('x') as stream:run([python,'-m','pip','freeze'],stdout=stream)
print('B2_FRAD_ATTEMPT',json.dumps(report),flush=True)

PY
