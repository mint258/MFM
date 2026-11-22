#!/bin/bash
#SBATCH --job-name=B2-remaining-source-access
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=01:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B2_remaining_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import json,os,urllib.request,urllib.error,time,re,subprocess,tarfile,io
from pathlib import Path
from workflows.benchmark_data.admission import protect
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())
root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe(peak=1024**3):protect(root,peak,quota,own_concurrent_bytes=24*1024**3)
safe()
out=b1/'B2_remaining_sources'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
os.environ['TMPDIR']=str(out/'tmp');(out/'tmp').mkdir()
def get(url,name,cap=20*1024**2):
    safe(cap)
    request=urllib.request.Request(url,headers={'User-Agent':'benchmark-b1-research/1'})
    with urllib.request.urlopen(request,timeout=60) as response:
        size=response.headers.get('Content-Length')
        if size is not None and int(size)>cap:raise ValueError('Metadata/source exceeds forecast: '+name)
        payload=response.read(cap+1)
        if len(payload)>cap:raise ValueError('Metadata/source exceeds forecast: '+name)
    (out/name).write_bytes(payload);return payload
records=[]
# Metadata and access checks do not request approval, accept licenses, or register accounts.
token=None
try:
    from huggingface_hub import get_token
    token=get_token()
except ImportError:
    token=os.environ.get('HF_TOKEN')
    token_path=Path(os.environ.get('HF_HOME',str(Path.home()/'.cache/huggingface')))/'token'
    if token is None and token_path.is_file():token=token_path.read_text().strip()
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None
uma={'model':'UMA-S','checkpoint_source':'https://huggingface.co/facebook/UMA','existing_HF_credential_present':bool(token),'permission_application_submitted':False,'license_accepted':False,'access_attempts':[]}
for attempt in range(2):
    try:
        headers={'User-Agent':'benchmark-b1-research/1'}
        if token:headers['Authorization']='Bearer '+token
        request=urllib.request.Request('https://huggingface.co/facebook/UMA/resolve/main/checkpoints/uma-s-1p1.pt',method='HEAD',headers=headers)
        opener=urllib.request.build_opener(NoRedirect)
        try:
            response=opener.open(request,timeout=30);status=response.status;response.close()
        except urllib.error.HTTPError as error:status=error.code
        uma['access_attempts'].append({'attempt':attempt+1,'HTTP_status':status})
        if status in (401,403):uma['status']='NEEDS_USER_ACCESS_APPROVAL';break
        if status in (200,302,303,307,308):uma['status']='DOWNLOAD_ACCESS_AVAILABLE_ENVIRONMENT_AND_INFERENCE_PENDING';break
        uma['status']='UNRESOLVED_ACCESS_HTTP_'+str(status)
    except Exception as error:
        uma['access_attempts'].append({'attempt':attempt+1,'error_type':type(error).__name__});uma['status']='UNRESOLVED_ACCESS_NETWORK'
(out/'UMA_S_access.json').write_text(json.dumps(uma,indent=2)+'\n');print('B2_UMA_ACCESS',json.dumps(uma),flush=True)
for model,repository in [('KPGT','lihan97/KPGT'),('Frad','fengshikun/FradNMI'),('Fallani2025','aidd-msca/GraphQPT'),('Rem3Di','molsuit/Rem3Di')]:
    record={'model':model,'repository':'https://github.com/'+repository,'status':'SOURCE_METADATA_PENDING','weights_loaded':False,'smoke100_complete':False}
    try:
        meta=json.loads(get('https://api.github.com/repos/'+repository,model+'_repository.json'))
        branch=meta['default_branch']
        commit=json.loads(get('https://api.github.com/repos/'+repository+'/commits/'+branch,model+'_commit.json'))['sha']
        record.update(commit=commit,license=meta.get('license',{}),default_branch=branch)
        archive=get('https://codeload.github.com/'+repository+'/tar.gz/'+commit,model+'_source.tar.gz',50*1024**2)
        source=out/(model+'_source');source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as stream:
            members=stream.getmembers()
            total=sum(member.size for member in members if member.isfile())
            safe(total+len(archive))
            for member in members:
                parts=Path(member.name).parts[1:]
                if not parts:continue
                if '..' in parts or Path(*parts).is_absolute():raise ValueError('Unsafe archive member')
                target=source.joinpath(*parts)
                if member.isdir():target.mkdir(parents=True,exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with stream.extractfile(member) as binary:target.write_bytes(binary.read())
                else:raise ValueError('Unsupported archive link/device; do not extract')
        env=b1/'environments'/(model.lower()+'_job_'+os.environ['SLURM_JOB_ID'])
        subprocess.run(['/share/home/zixiao/.conda/envs/chemprop/bin/python','-m','venv','--system-site-packages',str(env/'venv')],check=True)
        record.update(status='SOURCE_PINNED_DEDICATED_ENV_CREATED_DEPENDENCIES_WEIGHTS_AND_INFERENCE_PENDING',source=str(source),python=str(env/'venv/bin/python'))
    except Exception as error:record.update(status='UNRESOLVED_SOURCE_PREPARATION_FIRST_ATTEMPT',error_type=type(error).__name__,error=str(error)[:300])
    records.append(record);print('B2_SOURCE_ACCESS',json.dumps(record),flush=True)
for label,url,name in [('Frad_weights','https://zenodo.org/api/records/12697467','Frad_weight_record.json'),('Fallani_dataset','https://zenodo.org/api/records/13374020','Fallani_published_dataset_record.json'),('QuADMET','https://huggingface.co/api/models/arunraja007/quadmetformer/tree/main?recursive=true','QuADMET_public_files.json'),('FAIRChem_package','https://pypi.org/pypi/fairchem-core/json','fairchem_pypi.json'),('Rem3Di_package','https://pypi.org/pypi/remedi/json','remedi_pypi.json')]:
    try:
        value=json.loads(get(url,name));record={'source':label,'status':'METADATA_FETCHED','file':str(out/name)}
        if label in ('Frad_weights','Fallani_dataset'):record['files']=[{'key':x.get('key'),'size':x.get('size'),'download':x.get('links',{}).get('self')} for x in value.get('files',[])]
        elif label=='QuADMET':record['files']=[{'path':x.get('path'),'type':x.get('type'),'size':x.get('size')} for x in value]
        else:record.update(version=value['info']['version'],requires_python=value['info']['requires_python'],requirements=value['info']['requires_dist'])
        records.append(record);print('B2_PUBLISHED_METADATA',json.dumps(record),flush=True)
    except Exception as error:
        record={'source':label,'status':'UNRESOLVED_METADATA_FIRST_ATTEMPT','error_type':type(error).__name__};records.append(record);print('B2_METADATA_FAILURE',json.dumps(record),flush=True)
report={'job':os.environ['SLURM_JOB_ID'],'UMA_access':uma,'sources':records,'all_models_ready':False,'no_own_conformers':True,'no_account_registration':True,'no_full_embedding_extraction':True}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('B2_SOURCE_DISCOVERY_CLOSED',out/'manifest.json',flush=True)

PY
