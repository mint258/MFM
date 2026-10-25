"""Root metadata-only request preparation; never probes, submits, or runs science."""
from __future__ import annotations
import argparse,datetime,json,os,pathlib,shlex,socket
from . import policy

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--scope',required=True);a.add_argument('--node',required=True);a.add_argument('--job-name',required=True);a.add_argument('--source',action='append',default=[]);a.add_argument('--command-file',type=pathlib.Path,required=True);x=a.parse_args()
    policy.require(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','ROOT_METADATA_ONLY_ON_SONMI')
    cfg=policy.load(policy.POLICY);scope=cfg['scopes'][x.scope]
    policy.require(x.node in policy.CPU_NODES,'CPU_NODE_ONLY')
    base=policy.load(scope['base_request_reference']['path'])
    command=policy.load(x.command_file);policy.require(isinstance(command,list) and all(isinstance(v,str) and '\n' not in v and '\r' not in v for v in command),'EXACT_COMMAND_ARRAY_REQUIRED')
    policy.require(command and command[0]=='/share/home/zixiao/.conda/envs/chemprop/bin/python','EXACT_LOGICAL_PYTHON_REQUIRED')
    name=x.job_name;script=policy.ROOT/'control/scripts'/(name+'.sbatch');request_path=policy.ROOT/'control/requests'/(name+'.json');intent=policy.ROOT/'control/submissions'/(name+'.intent.json')
    for p in (script,request_path,intent,policy.ROOT/'control/submissions'/(name+'.json'),policy.ROOT/'artifacts/cpu_analysis_guards'/name):policy.require(not p.exists(),'NEW_DESTINATION_REQUIRED_NO_OVERWRITE:'+str(p))
    refs={r['path']:r for r in base['source_references']}
    additions=[scope['base_request_reference'],base['script_reference'],policy.ref(policy.DECISION),policy.ref(policy.POLICY),policy.ref(x.command_file),policy.ref(policy.REPO/'docs/data_v1/cpu_analysis_resource_policy_v1.md')]
    additions += [policy.ref(p) for p in pathlib.Path(__file__).parent.glob('*.py')]
    additions += [policy.ref(pathlib.Path(p)) for p in x.source]
    for r in additions:
        policy.verify(r);policy.require(r['path'] not in refs or refs[r['path']]==r,'CONFLICTING_NEW_SOURCE_PIN');refs[r['path']]=r
    text=f'''#!/bin/bash
#SBATCH --job-name={name}
#SBATCH --partition=cpu
#SBATCH --nodelist={x.node}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem={scope['memory_gib']}G
#SBATCH --time={scope['wall_seconds']//3600:02d}:{scope['wall_seconds']%3600//60:02d}:{scope['wall_seconds']%60:02d}
#SBATCH --output={policy.ROOT}/control/{name}_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH={policy.REPO}:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
cd {policy.REPO}
exec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m workflows.data_v1_final.execution.cpu_export_fixture_v1.launch_v2 --intent {intent} -- {shlex.join(command)}
'''
    with script.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    request={'kind':'analysis','node':x.node,'cpus':16,'memory_gib':scope['memory_gib'],'wall_seconds':scope['wall_seconds'],'estimated_peak_output_bytes':scope['output_cap_bytes']+policy.GUARD_CAP,'pilot':True,'estimated_total_core_hours':scope['wall_seconds']*16/3600,'resource_policy':policy.BASIS,'scope_key':x.scope,'scope_parameters':scope['parameters'],'base_request_reference':scope['base_request_reference'],'decision_reference':policy.ref(policy.DECISION),'scope_policy_reference':policy.ref(policy.POLICY),'formal_generation_authorized':False,'script_reference':policy.ref(script),'source_references':list(refs.values()),'data_references':base.get('data_references',[]),'execution_argv':command,'root_review':{'status':'APPROVED','reviewer':'root','observed_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'scope':'Root personal invocation for the exact finite scope parameters. New CPU sources and explicit command pinned; no formal or full-population acceptance.','resources':'Actual cpu partition,16CPU,finite memory+wall+output budget. Other memory0 declarations stay unbounded in evidence; small-test operational measured-memory policy only,1s monitor/5s heartbeat/selfRSS75%/node envelope85%,positive other reservations+full own request,200GBreserve. No forced termination, automatic submission or retry.','science':'Original science/masks/thresholds/population unchanged; newguard/checkpoint variants require separate equivalence/static and actual boundary evidence. Actual parent+monitor closure must be reviewed before downstream use.'}}
    policy.scope(request);policy.job_name(request)
    with request_path.open('x',encoding='utf-8') as f:json.dump(request,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'status':'PREPARED_NOT_SUBMITTED','request':policy.ref(request_path),'script':policy.ref(script),'scope':x.scope,'node':x.node}))
if __name__=='__main__':main()
