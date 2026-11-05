"""Materialize a new exact CPU stage with no Slurm memory or exclusivity option."""
import argparse,copy,json
from pathlib import Path
from .shared import ROOT,REPO,PROJECT,PY,load,pin,read_small,on_login,write_new
from .contract import (MEMORY_POLICY,REQUEST_SCHEMA,need,validate_authority,
                       validate_scope_spec,validate_request)

CONTROLLED={'schema','kind','pilot','cpus','memory_policy','wall_seconds','estimated_peak_output_bytes',
            'execution_argv','source_references','data_references','deferred_authority_references'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec',type=Path,required=True);p.add_argument('--authority',type=Path,required=True)
    p.add_argument('--node',required=True);p.add_argument('--job-name',required=True)
    p.add_argument('--afterok',action='append',default=[]);a=p.parse_args();on_login()
    authority=pin(a.authority);validate_authority(authority,read_small=read_small)
    spec=load(a.spec);scope=validate_scope_spec(spec,authority,read_small=read_small)
    import re
    name=a.job_name;need(re.fullmatch(r'dv1_q_[A-Za-z0-9_]+',name),'NEW_SAFE_JOB_NAME_REQUIRED')
    proof=ROOT/'control/queue_startup'/(name+'.json');request_path=ROOT/'control/requests'/(name+'.json')
    script=ROOT/'control/scripts'/(name+'.sbatch')
    for path in (proof,proof.with_suffix('.ready.json'),request_path,script,
                 ROOT/'control/submissions'/(name+'.json'),ROOT/'control/submissions'/(name+'.queue_intent.json'),
                 ROOT/'control/queue_started'/(name+'.json'),ROOT/'control/queue_finished'/(name+'.json')):
        need(not path.exists() and not path.is_symlink(),'NEW_DESTINATION_REQUIRED:'+str(path))
    refs={}
    from .contract import pin as normalized_pin
    def source(value):
        value=normalized_pin(value)
        need(pin(value['path'])==value and (value['path'] not in refs or refs[value['path']]==value),'CURRENT_CONFLICT_FREE_SOURCE_PIN_REQUIRED')
        refs[value['path']]=value
    for value in spec['source_references']:source(value)
    here=REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v1'
    need(Path(__file__).absolute().parent==here,'ROOT_INTEGRATED_MATERIALIZER_REQUIRED')
    extra=[a.spec,a.authority,*here.glob('*.py'),
           REPO/'workflows/data_v1_final/execution/queue_v1/__init__.py',
           REPO/'workflows/data_v1_final/execution/queue_v1/shared.py',
           REPO/'workflows/data_v1_final/execution/queue_v1/queue_contract.py']
    extra += [Path(spec['scope']['review']['path']),*[Path(v['path']) for v in scope['parents']]]
    for path in extra:source(pin(path))
    argv=[s.replace('__ROOT_STARTUP_PROOF__',str(proof)) for s in spec['execution_argv']]
    wall=spec['wall_seconds']
    text=f'''#!/bin/bash
#SBATCH --job-name={name}
#SBATCH --partition=cpu
#SBATCH --nodelist={a.node}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time={wall//3600:02d}:{wall%3600//60:02d}:{wall%60:02d}
#SBATCH --output={ROOT}/control/{name}_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH={REPO}:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
cd {PROJECT}
exec {PY} -B -m workflows.data_v1_final.execution.cpu_auto_memory_queue_v1.launch --request {request_path}
'''
    script.parent.mkdir(parents=True,exist_ok=True)
    with script.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    req={'schema':REQUEST_SCHEMA,'kind':spec['kind'],'partition':'cpu','node':a.node,'job_name':name,'cpus':16,
        'memory_policy':MEMORY_POLICY,'exclusive_requested':False,'wall_seconds':wall,'pilot':spec['pilot'],
        'estimated_peak_output_bytes':spec['estimated_peak_output_bytes'],'estimated_total_core_hours':wall*16/3600,
        'estimate_is_allocation_ceiling_not_forecast':True,'workdir':str(PROJECT),'startup_wait_seconds':120,
        'startup_proof_path':str(proof),'queue_authority_reference':authority,'script_reference':pin(script),
        'source_references':list(refs.values()),'data_references':spec.get('data_references',[]),
        'deferred_authority_references':spec.get('deferred_authority_references',[]),'execution_argv':argv,
        'dependencies':a.afterok,'root_review':{'status':'APPROVED','reviewer':'root','stage_spec_reference':pin(a.spec),
            'scope':'Exact new stage and latest user CPU/memory authority; scientific gates remain.'}}
    for key,value in spec.items():
        if key not in CONTROLLED:
            need(key not in req,'PRODUCER_CANNOT_OVERRIDE_QUEUE_CONTROL:'+key);req[key]=copy.deepcopy(value)
    validate_request(req,read_small=read_small,script_text=text);write_new(request_path,req)
    print(json.dumps({'status':'NEW_AUTO_MEMORY_REQUEST_PREPARED_NOT_SUBMITTED','request':pin(request_path),
                      'memory_policy':MEMORY_POLICY,'memory_admission_evaluated':False}))


if __name__=='__main__':main()
