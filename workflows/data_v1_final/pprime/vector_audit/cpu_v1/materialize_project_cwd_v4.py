"""Prepare the identical vector read with its historical project-relative assets."""
import json,pathlib,subprocess
from workflows.data_v1_final.execution.cpu_analysis_v1 import policy
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'

def save(path,obj):
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2);f.write('\n')

def main():
    root=policy.ROOT;repo=policy.REPO;name='dv1_vector_cpu_v4'
    old=root/'control/requests/dv1_vector_cpu_v2.bound.json'
    request=policy.load(old)
    boundary=root/'control/vector_cpu_boundaries_v2.json'
    result=policy.load(boundary)
    policy.require(result['status']=='PASS' and result['tests_run']==3 and not result['failures'] and not result['errors'],'ACTUAL_THREE_VECTOR_BOUNDARIES_REQUIRED')
    observation=subprocess.run(['sacct','-j','4520542','--format=JobIDRaw,State,ExitCode','-P'],capture_output=True,text=True,check=True)
    policy.require('4520542|FAILED|1:0' in observation.stdout,'EXACT_FAILED_VECTOR_PARENT_REQUIRED')
    evidence=root/'control/vector_cpu_project_cwd_v4.json'
    save(evidence,{'schema':'VECTOR_PROJECT_RELATIVE_ASSET_BINDING_V1','sacct_stdout':observation.stdout,
        'previous_request':policy.ref(old),'actual_three_boundary_tests':policy.ref(boundary),
        'working_directory':str(root.parent.parent),'scientific_changes':False,'new_QM_calls':0})
    stage=policy.load(root/'control/stages/dv1_vector_cpu_v2.json')['stages'][1]
    previous_output=str(root/'artifacts/vector_frame_audit/prepared_cpu_v2')
    output=root/'artifacts/vector_frame_audit/prepared_cpu_v4'
    policy.require(not output.exists(),'FRESH_VECTOR_OUTPUT_REQUIRED')
    intent=root/'control/submissions'/(name+'.intent.json')
    stage['argv']=[v.replace('dv1_vector_cpu_v2',name).replace(previous_output,str(output)) for v in stage['argv']]
    stages=root/'control/stages'/(name+'.json')
    save(stages,{'scope_key':'vector_prepare_1000','stages':[stage],
        'prior_three_boundaries_reused':policy.ref(boundary),'working_directory':str(root.parent.parent)})
    command=root/'control/commands'/(name+'.json')
    save(command,[PY,'-B','-m','workflows.data_v1_final.execution.cpu_analysis_v1.run_stages_v1',
        '--stages',str(stages),'--root-preflight',str(intent),'--receipt',str(root/'control/vector_cpu_stages_v4.json')])
    sources=[pathlib.Path(__file__).absolute(),evidence,old,boundary,stages]
    sources += [pathlib.Path(pin['path']) for pin in request['source_references']]
    pilot=policy.load(repo/'configs/data_v1/pprime/pilot_v1.json')
    contract=policy.load(pilot['legacy_contract']['path'])
    manifest=contract['reproduction_package']
    manifestpath=pathlib.Path(manifest['path'])
    if manifestpath.is_dir():manifestpath=manifestpath/'manifest.json'
    metadata=policy.load(manifestpath)
    # Historical metadata may use project-relative paths. Preserve those values;
    # the new script restores their original resolution base.
    def walk(value):
        if isinstance(value,dict):
            if value.get('source_path') and pathlib.Path(value['source_path']).suffix in {'.py','.sh','.sbatch'}:
                path=pathlib.Path(value['source_path'])
                if not path.is_absolute():path=root.parent.parent/path
                pin=policy.ref(path)
                policy.require(pin['sha256']==value['sha256'],'HISTORICAL_REPRODUCTION_SOURCE_CHANGED')
                sources.append(path)
            for child in value.values():walk(child)
        elif isinstance(value,list):
            for child in value:walk(child)
    walk(metadata)
    argv=[PY,'-B','-m','workflows.data_v1_final.execution.cpu_analysis_v1.prepare_request_v2',
        '--scope','vector_prepare_1000','--node','compute-0-17','--job-name',name,'--command-file',str(command)]
    for path in dict.fromkeys(sources):argv+=['--source',str(path)]
    subprocess.run(argv,cwd=repo,check=True)
    base=root/'control/requests'/(name+'.json');new=policy.load(base)
    original=policy.read_small(new['script_reference']['path']).decode()
    needle='cd '+str(repo)+'\n'
    policy.require(original.count(needle)==1,'EXACT_ORIGINAL_LAUNCH_CWD_REQUIRED')
    text=original.replace(needle,'cd '+str(root.parent.parent)+'\n')
    script=root/'control/scripts'/(name+'.project_cwd.sbatch')
    with script.open('x',encoding='utf-8') as f:f.write(text)
    new['script_reference']=policy.ref(script);new['partition']='cpu'
    new['data_references']=request['data_references']
    new['project_cwd_binding']=policy.ref(evidence)
    new['source_references'] += [policy.ref(base)]
    policy.scope(new);policy.job_name(new)
    bound=root/'control/requests'/(name+'.bound.json');save(bound,new)
    print(json.dumps({'status':'PREPARED_NOT_SUBMITTED','request':policy.ref(bound)}))
if __name__=='__main__':main()