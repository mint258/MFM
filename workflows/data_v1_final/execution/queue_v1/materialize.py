"""Build a concrete, immutable queued request from a Root reviewed small stage spec."""
import argparse,pathlib,shlex,re
from .shared import ROOT,REPO,PROJECT,PY,load,need,on_login,pin,read_small,write_new
from .queue_contract import validate_request

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--spec',type=pathlib.Path,required=True)
    p.add_argument('--node',required=True);p.add_argument('--job-name',required=True);p.add_argument('--afterok',action='append',default=[])
    a=p.parse_args();on_login();spec=load(a.spec);need(spec['schema']=='ROOT_REVIEWED_QUEUED_STAGE_SPEC_V1','EXACT_STAGE_SPEC')
    need(spec['pilot'] is True,'QUEUE_V1_TESTS_AND_PILOTS_ONLY')
    name=a.job_name;need(re.fullmatch(r'dv1_[A-Za-z0-9_]+',name),'SAFE_JOB_NAME_REQUIRED');proof=ROOT/'control/queue_startup'/(name+'.json');reqpath=ROOT/'control/requests'/(name+'.json')
    script=ROOT/'control/scripts'/(name+'.sbatch')
    for path in (script,reqpath,ROOT/'control/submissions'/(name+'.json'),proof):need(not path.exists(),'NEW_DESTINATIONS_ONLY:'+str(path))
    authority=REPO/'configs/data_v1/queued_execution_decision_20261026_v1.json'
    need(len({r['path'] for r in spec['source_references']})==len(spec['source_references']),'UNIQUE_STAGE_SOURCE_REFS')
    refs={r['path']:r for r in spec['source_references']}
    extra=[a.spec,authority,*pathlib.Path(__file__).parent.glob('*.py'),REPO/'workflows/data_v1_final/execution/cpu_prefix_replay_v1/probe_memory.py']
    for path in extra:
        actual=pin(path);need(str(path) not in refs or refs[str(path)]==actual,'CONFLICTING_PIN');refs[str(path)]=actual
    argv=[v.replace('__ROOT_STARTUP_PROOF__',str(proof)) for v in spec['execution_argv']]
    wall=spec['wall_seconds'];need(type(wall) is int and 0<wall<=14400,'FINITE_QUEUE_WALL')
    text=f'''#!/bin/bash
#SBATCH --job-name={name}
#SBATCH --partition=cpu
#SBATCH --nodelist={a.node}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --exclusive=user
#SBATCH --time={wall//3600:02d}:{wall%3600//60:02d}:{wall%60:02d}
#SBATCH --output={ROOT}/control/{name}_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH={REPO}:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
cd {PROJECT}
exec {PY} -B -m workflows.data_v1_final.execution.queue_v1.launch --request {reqpath}
'''
    with script.open('x',encoding='utf-8') as f:f.write(text)
    req={'schema':'DATA_V1_QUEUED_REQUEST_V1','kind':spec['kind'],'partition':'cpu','job_name':name,'node':a.node,
        'cpus':16,'memory_gib':64,'wall_seconds':wall,'estimated_peak_output_bytes':spec['estimated_peak_output_bytes'],
        'pilot':spec['pilot'],'estimated_total_core_hours':wall*16/3600,'estimate_is_allocation_ceiling_not_runtime_forecast':True,
        'workdir':str(PROJECT),'exclusive_user':True,'startup_proof_path':str(proof),'startup_wait_seconds':120,
        'queue_authority_reference':pin(authority),'script_reference':pin(script),'source_references':list(refs.values()),
        'data_references':spec.get('data_references',[]),'deferred_authority_references':spec.get('deferred_authority_references',[]),'execution_argv':argv,'dependencies':a.afterok,
        'root_review':{'status':'APPROVED','reviewer':'root','scope':'Exact frozen stage spec; scientific acceptance gates remain. Queued authority is latest user continuous submission instruction.',
            'stage_spec_reference':pin(a.spec),'resource_policy':'CPU16/64GiB/all-user declared85% and fresh live memory/quota; exclusive=user verified before release. No formal resource exemption.'}}
    validate_request(req,read_small=read_small,script_text=text);write_new(reqpath,req)
    print(__import__('json').dumps({'status':'CONCRETE_QUEUED_REQUEST_PREPARED_NOT_SUBMITTED','request':pin(reqpath)}))
if __name__=='__main__':main()
