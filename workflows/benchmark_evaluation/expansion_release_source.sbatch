#!/bin/bash
#SBATCH --job-name=B0-ExpansionRx-public-label-source
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B0_ExpansionRx_release_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import csv,json,os,time,urllib.request,urllib.error
from pathlib import Path
from workflows.benchmark_data.admission import protect
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root'])
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,16*1024**2,quota,own_concurrent_bytes=24*1024**3)
safe();out=root/'raw/ExpansionRx_official_release'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
report={'status':'PREPARING_PUBLIC_SOURCE','job':os.environ['SLURM_JOB_ID'],'source_entry':str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),'repository':'openadmet/openadmet-expansionrx-challenge-data','official_dataset_page':'https://openadmet.org/datasetsmodels/','license':'CC-BY-4.0, publisher dataset card','files':[],'credentials_sent':False,'account_registered':False,'gate_accepted':False,'original_B0_sources_modified':False,'new_endpoints_added':False,'source_registration_needed_in_B0_delivery':True,'model_fits_run':False}
def download(url,target,cap):
    safe()
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'benchmark-b1-research/1'}),timeout=60) as response,target.open('xb') as stream:
        total=0
        while True:
            block=response.read(65536)
            if not block:break
            total+=len(block)
            if total>cap:raise ValueError('Public source exceeds declared peak forecast')
            safe();stream.write(block)
    return total
try:
    metadata_path=out/'upstream_dataset_metadata.json'
    download('https://hf-mirror.com/api/datasets/'+report['repository'],metadata_path,2*1024**2)
    metadata=json.loads(metadata_path.read_text())
    report['publisher_gated']=metadata.get('gated')
    if metadata.get('gated') is not False:raise PermissionError('Public ungated status has not been verified; no file download')
    revision=metadata['sha'];report['publisher_revision']=revision
    for filename in ('README.md','expansion_data_train.csv','expansion_data_test.csv'):
        target=out/filename
        url='https://hf-mirror.com/datasets/'+report['repository']+'/resolve/'+revision+'/'+filename
        size=download(url,target,4*1024**2)
        record={'filename':filename,'path':str(target),'bytes':size,'publisher_url':'https://huggingface.co/datasets/'+report['repository']+'/resolve/'+revision+'/'+filename}
        if filename.endswith('.csv'):
            with target.open(newline='',encoding='utf-8-sig') as stream:
                reader=csv.DictReader(stream);record['fields']=reader.fieldnames;record['source_rows']=sum(1 for _ in reader)
        report['files'].append(record)
    report['status']='PUBLIC_POST_CHALLENGE_SOURCE_DOWNLOADED_IDENTITY_AND_ENDPOINT_BINDING_PENDING'
except PermissionError as error:report.update(status='NEEDS_USER_DATA_ACCESS_OR_UNVERIFIED_GATE',error_type=type(error).__name__)
except Exception as error:report.update(status='SOURCE_ACQUISITION_FIRST_ATTEMPT_FAILED',error_type=type(error).__name__,error=str(error)[:300])
# License metadata is independent of any produced model outputs.
try:
    path=out/'CheMeleon_Zenodo_record.json'
    download('https://zenodo.org/api/records/15460715',path,2*1024**2)
    value=json.loads(path.read_text());report['CheMeleon_weight_license']=value.get('metadata',{}).get('license')
except Exception as error:report['CheMeleon_license_metadata_error_type']=type(error).__name__
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('B0_EXPANSIONRX_PUBLIC_RELEASE_SOURCE',json.dumps(report),flush=True)

PY
