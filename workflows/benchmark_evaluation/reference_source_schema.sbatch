#!/bin/bash
#SBATCH --job-name=B1-reference-binding-schema
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:15:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_reference_schema_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import json,os,tarfile
from pathlib import Path
import pyarrow.parquet as pq
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.nmr_graph_source import restricted_graph_load
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
protect(root,1048576,quota,own_concurrent_bytes=24*1024**3)
out=b1/'reference_binding_schema'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
manifest=json.loads(Path(entry['manifest']).read_text());report={'job':os.environ['SLURM_JOB_ID'],'source_entry':str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),'schemas':{},'source_metadata':{}}
def structural(value,depth=0):
    if isinstance(value,dict):return {str(k):structural(v,depth+1) if depth<2 else type(v).__name__ for k,v in value.items()}
    if isinstance(value,list):return {'type':'list','length':len(value),'element_structure':structural(value[0],depth+1) if value and depth<2 else None}
    if isinstance(value,str):return {'type':'str','sample':value[:150]} if depth<2 else 'str'
    return type(value).__name__
for name in ('adme-fang-hclint-reg-v1.json','adme-fang-hppb-reg-v1.json','adme-fang-reg-v1.json','dataset_metadata.json'):
    path=root/'raw/Biogen_ADME'/name
    data=json.loads(path.read_text())
    report['source_metadata']['Biogen_'+name]=structural(data)
    print('B1_BIOGEN_SOURCE_SCHEMA',name,json.dumps(report['source_metadata']['Biogen_'+name]),flush=True)
c7_path=Path(manifest['C7_targets']);c7=json.loads(c7_path.read_text())
report['source_metadata']['C7_targets']=c7
for name,path in [('PPE_targets',manifest['PPE_targets']['path'])]:
    report['schemas'][name]={'path':path,'schema':str(pq.ParquetFile(path).schema_arrow)}
for name in ('C7H10O2','PPE1694'):
    path=manifest['source_groups'][name]['records']
    report['schemas'][name+'_domain']={'path':path,'schema':str(pq.ParquetFile(path).schema_arrow)}
for path in manifest['reference_D3']['manifests']:
    report['source_metadata'][Path(path).parent.name+'_D3']=json.loads(Path(path).read_text())
source=root/'raw/NMRShiftDB2_Jonas2019/13321_2019_374_MOESM2_ESM.gz'
with tarfile.open(source,'r:gz') as archive:
    for member in archive:
        if not member.name.endswith('.pickle'):continue
        nucleus='13C' if '.13C.' in member.name else '1H'
        data=restricted_graph_load(archive.extractfile(member).read())
        row=data['train_df'].iloc[0];value=row['value']
        info={'member':member.name,'label_container_type':type(value).__name__,'label_container_structure':structural(value),'graph_atom_count_first_record':row['rdmol'].GetNumAtoms(),'original_split_metadata_reference':str(b1/'nmr_split/job_4536856/split_metadata.json')}
        report['source_metadata']['NMR_'+nucleus]=info
        print('B1_NMR_LABEL_INTERFACE',nucleus,json.dumps(info),flush=True)
print('B1_REFERENCE_BINDING_SCHEMAS',json.dumps(report['schemas']),flush=True)
(out/'source_schema.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
print('B1_REFERENCE_SOURCE_SCHEMA_CLOSED',out/'source_schema.json',flush=True)

PY
