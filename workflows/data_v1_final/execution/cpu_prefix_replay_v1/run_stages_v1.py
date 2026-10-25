"""Run a reviewed finite test/audit sequence in one monitored CPU allocation."""
import argparse,json,pathlib,subprocess,sys
from . import policy,runtime_v2 as runtime

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stages',type=pathlib.Path,required=True)
    p.add_argument('--root-preflight',type=pathlib.Path,required=True)
    p.add_argument('--receipt',type=pathlib.Path,required=True)
    a=p.parse_args();spec=policy.load(a.stages);proof=policy.load(a.root_preflight)
    r=proof['request'];scope=policy.load(policy.POLICY)['scopes'][r['scope_key']]
    runtime.root_guard(a.root_preflight,a.stages,scope['output_cap_bytes'],scope['wall_seconds'])
    policy.require(spec['scope_key']==r['scope_key'] and 1<=len(spec['stages'])<=4,'EXACT_REVIEWED_SMALL_STAGE_SEQUENCE_REQUIRED')
    policy.require(not a.receipt.exists(),'NEW_STAGE_RECEIPT_ONLY')
    rows=[];code=1;failure=None
    try:
        for stage in spec['stages']:
            runtime.checkpoint();argv=stage['argv']
            policy.require(argv and argv[0]=='/share/home/zixiao/.conda/envs/chemprop/bin/python' and all(isinstance(v,str) for v in argv),'REVIEWED_LOGICAL_PYTHON_STAGE_REQUIRED')
            result=subprocess.run(argv,stdin=subprocess.DEVNULL)
            rows.append({'name':stage['name'],'argv':argv,'returncode':result.returncode})
            if result.returncode:code=result.returncode;break
        else:code=0
        runtime.checkpoint()
    except BaseException as e:failure=repr(e);code=1
    result={'schema':'FINITE_CPU_STAGE_SEQUENCE_V1','status':'ALL_STAGES_COMPLETED' if code==0 and failure is None else 'STAGE_FAILED_NO_RETRY','scope_key':r['scope_key'],'stages_reference':policy.ref(a.stages),'root_preflight':policy.ref(a.root_preflight),'stages':rows,'failure':failure,'forced_signals_sent':False,'automatic_submission_or_retry':False,'formal_generation_authorized':False}
    with a.receipt.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result),flush=True);return 0 if result['status']=='ALL_STAGES_COMPLETED' else 1
if __name__=='__main__':sys.exit(main())
