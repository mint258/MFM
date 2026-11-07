"""Root metadata-only preparation for the preserved TIMEOUT package audit."""
from __future__ import annotations
import argparse,datetime,json,pathlib,subprocess,sys
from workflows.data_v1_final.execution.cpu_analysis_v1 import policy
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'

def write(path,value):
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--node',default='compute-0-17')
    p.add_argument('--job-name',default='dv1_partial_sprime_audit_cpu_v2')
    a=p.parse_args();root=policy.ROOT;repo=policy.REPO;name=a.job_name
    out=root/'artifacts/conformers/partial_pilot_audit_v1/audit_v1'
    intent=root/'control/submissions'/(name+'.intent.json')
    evidence=root/'control'/(name+'.sacct_evidence.json')
    raw=root/'control'/(name+'.sacct.txt')
    stagefile=root/'control'/(name+'.stages.json')
    cmdfile=root/'control'/(name+'.command.json')
    bound=root/'control/requests'/(name+'.bound.json')
    for dest in (out,intent,evidence,raw,stagefile,cmdfile,bound):
        policy.require(not dest.exists(),'FRESH_AUDIT_DESTINATION_REQUIRED:'+str(dest))
    argv=['sacct','-j','4520364','--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList','-P']
    result=subprocess.run(argv,capture_output=True,text=True,check=True)
    with raw.open('x',encoding='utf-8') as f:f.write(result.stdout)
    write(evidence,{'schema':'DATA_V1_SACCT_QUERY_EVIDENCE_V1',
        'observed_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'query_returncode':result.returncode,'command_argv':argv,
        'requested_parent_job_ids':['4520364'],'raw_sacct_reference':policy.ref(raw)})
    src=repo/'workflows/data_v1_final/conformers'
    cfg=repo/'configs/data_v1/conformers'
    closure=cfg/'pilot_closure_v1.json';runconfig=cfg/'partial_pilot_cpu_runconfig_v2.json'
    audit=cfg/'partial_pilot_audit_v1.json';c=policy.load(closure)
    prepared=policy.load(c['prepared']['path'])
    original=root/'control/submissions/dv1_sb2_fill_32g_v1.json'
    outputs={pathlib.Path(r['path']).name:r for r in prepared['outputs']}
    shared=['--config',str(closure),'--cpu-runconfig',str(runconfig),'--root-preflight',str(intent)]
    stages={'scope_key':'sprime_pilot_closure_336','stages':[
        {'name':'four_partial_audit_boundaries','argv':[PY,'-B',str(src/'partial_pilot_audit_v1/test_partial.py'),*shared]},
        {'name':'readonly_partial_package_audit','argv':[PY,'-B',str(src/'partial_pilot_audit_v1/audit_partial.py'),*shared,
            '--audit-config',str(audit),'--sacct-evidence',str(evidence),
            '--original-submission',str(original),'--output',str(out)]}]}
    write(stagefile,stages)
    write(cmdfile,[PY,'-B','-m','workflows.data_v1_final.execution.cpu_analysis_v1.run_stages_v1',
        '--stages',str(stagefile),'--root-preflight',str(intent),
        '--receipt',str(root/'control'/(name+'.stages_receipt.json'))])
    sources=[pathlib.Path(__file__).absolute(),closure,runconfig,audit,evidence,raw,original,stagefile,
        pathlib.Path(c['prepared']['path']),pathlib.Path(c['pilot_config']['path'])]
    sources += list((src/'partial_pilot_audit_v1').glob('*.py'))
    sources += [src/'pilot_closure_v1/close_pilot.py',src/'common.py',src/'formal_v1/full_common.py']
    sources += [pathlib.Path(outputs['selected_molecules.parquet']['path'])]
    command=[PY,'-B','-m','workflows.data_v1_final.execution.cpu_analysis_v1.prepare_request_v2',
        '--scope','sprime_pilot_closure_336','--node',a.node,'--job-name',name,'--command-file',str(cmdfile)]
    for source in sources:command += ['--source',str(source)]
    subprocess.run(command,check=True,cwd=repo)
    request=policy.load(root/'control/requests'/(name+'.json'))
    request['data_locator_authorization']={
        'schema':'PARTIAL_SPRIME_PILOT_AUDIT_DATA_LOCATORS_V1','read_only':True,
        'expected_molecules':336,'original_pilot_job':'4520364',
        'pilot_output_directory':policy.load(audit)['pilot_output_directory'],
        'prepared_reference':c['prepared'],'pilot_config_reference':c['pilot_config'],
        'selected_molecules_reference':outputs['selected_molecules.parquet'],
        'tasks_reference':outputs['tasks.jsonl'],'original_submission_reference':policy.ref(original),
        'sacct_evidence_reference':policy.ref(evidence),
        'allow_tasks_body_only_in_actual_cpu_allocation':True,'new_UFF_QM_calls':0,'formal_acceptance_allowed':False}
    request['data_references'] += [outputs['tasks.jsonl']]
    policy.scope(request);policy.job_name(request);write(bound,request)
    print(json.dumps({'status':'PREPARED_NOT_SUBMITTED','request':policy.ref(bound),
        'preserved_base_request':policy.ref(root/'control/requests'/(name+'.json'))}))
if __name__=='__main__':main()