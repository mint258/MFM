"""Add an actual submitter-v3 pin to a fresh independent request; never submit."""
import argparse,json,pathlib
from . import policy

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',required=True,type=pathlib.Path)
    p.add_argument('--output',required=True,type=pathlib.Path)
    a=p.parse_args();request=policy.load(a.request);policy.scope(request)
    name=policy.job_name(request)
    for path in (a.output,policy.ROOT/'control/submissions'/(name+'.intent.json'),
                 policy.ROOT/'control/submissions'/(name+'.json')):
        policy.require(not path.exists(),'NEW_UNREGISTERED_BINDING_REQUIRED:'+str(path))
    refs={r['path']:r for r in request['source_references']}
    for path in (pathlib.Path(__file__).absolute(),pathlib.Path(__file__).parent/'submit_cpu_pilot_v3.py',a.request):
        pin=policy.ref(path)
        policy.require(pin['path'] not in refs or refs[pin['path']]==pin,'CONFLICTING_SOURCE_PIN')
        refs[pin['path']]=pin
    request['source_references']=list(refs.values())
    request['submitter_v3_binding']={'preserved_base_request_reference':policy.ref(a.request),
        'timestamp_basis':'TARGET_NODE_ACTIVE_MEMORY_PROBE_CLOCK','scientific_or_resource_changes':False}
    policy.scope(request);policy.job_name(request)
    with a.output.open('x',encoding='utf-8') as f:json.dump(request,f,indent=2);f.write('\n')
    print(json.dumps({'status':'BOUND_NOT_SUBMITTED','request':policy.ref(a.output)}))
if __name__=='__main__':main()