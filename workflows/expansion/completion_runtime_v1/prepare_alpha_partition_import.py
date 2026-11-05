"""Prepare a native closed rescue6/7 import or the original low11 continuation."""
import argparse,copy,os,pathlib,runpy,subprocess,sys
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103'
D=A/'control/pubchem_completion_environment_20261103'
BASE=A/'code/pubchem_completion_20261103_497c584'
PY=A/'software/pubchem_completion_20261103_venv/bin/python'
COMMAND=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=5','218.192.171.238','sacct']

def native(Q,parent,job,folder,complete):
    folder.mkdir(mode=0o700)
    raw=subprocess.check_output([*COMMAND,'-j',job,'--parsable2','--format=JobIDRaw%40,State%24,ExitCode,UID,ElapsedRaw,AllocCPUS,NodeList%128'],text=True)
    lines=raw.splitlines();Q.need(lines,'Native parent and step header')
    names=lines[0].split('|');rows=[dict(zip(names,line.split('|')))for line in lines[1:]if line]
    path=folder/'native_sacct.psv'
    with path.open('x')as f:f.write(raw)
    runtime=dict(endpoint=Q.ENDPOINT,uid=Q.UID,job_id=job)
    account=Q.write(folder/'native_accounting.json',dict(endpoint=Q.ENDPOINT,uid=Q.UID,actual_parents=[r for r in rows if r.get('JobIDRaw')==job],raw_sacct_reference=Q.reference(path)))
    parent(runtime,account,require_C0=complete)
    return runtime,account

def upstream(Q,parent,item,folder,complete):
    job=str(item['job_id']);tag=item['tag']
    Q.need(job.isdigit()and tag and all(c.isalnum()or c in '_-'for c in tag),'Literal producer identity')
    control=B/'node_epochs'/(tag+'_job_'+job)
    plan_ref=Q.reference(control/'plan.json');startup_ref=Q.reference(control/'startup.json')
    plan=Q.load(Q.verify(plan_ref));startup=Q.load(Q.verify(startup_ref))
    runtime,account=native(Q,parent,job,folder,complete)
    Q.need(startup['request']['producer_plan_reference']==plan_ref and str(startup['job_id'])==job and startup['uid']==plan['uid']==1264 and startup['endpoint']==plan['endpoint']==Q.ENDPOINT,'Actual closed upstream plan/startup/native identity')
    return dict(runtime=runtime,plan_reference=plan_ref,startup_proof_reference=startup_ref,accounting_reference=account,root=plan['output_directory']),plan

def preserve_resume(seed,previous,old,receipt,imported):
    """Preserve original Main import and every previous NN writer, append this import."""
    if seed['resume_output_directory']!=previous['output_directory']or seed['partition_id']!='low11':raise ValueError('Original low11 root')
    for key in('external_score_import_references','external_score_import_completed'):
        if key in previous and seed.get(key)!=previous[key]:raise ValueError('Original Main import lineage must be retained')
    writers=copy.deepcopy(previous.get('resume_previous_allocations',[]))
    value={k:old[k]for k in('runtime','plan_reference','startup_proof_reference','accounting_reference')}
    if not any(item['runtime']==value['runtime']for item in writers):writers.append(value)
    refs=list(previous.get('alpha_partition_score_import_references',[]))
    if receipt not in refs:refs.append(receipt)
    seed.update(resume_previous_allocations=writers,alpha_partition_score_import_references=refs,alpha_partition_score_import_completed={k:imported[k]for k in('runtime','plan_reference','startup_proof_reference','accounting_reference')})
    return seed

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',required=True,choices=['import','resume']);parser.add_argument('--config',required=True,type=pathlib.Path)
    parser.add_argument('--entry',required=True,type=pathlib.Path);parser.add_argument('--tag',required=True);args=parser.parse_args()
    if os.getuid()!=1264 or not sys.flags.isolated or not os.environ.get('SLURM_JOB_ID'):raise ValueError('Actual isolated Alpha allocation')
    runpy.run_path(str(args.entry),run_name='_closed_partition_prepare')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    from workflows.expansion.uff3_alpha_runtime_v1.terminal import parent
    from workflows.expansion.alpha_sharded_novelty_v1.prepare_pipeline import prepare
    cfg=Q.load(args.config);deployment=Q.load(Q.verify(cfg['deployment_reference']))
    Q.need(Q.reference(__file__)==cfg['prepare_script_reference']and Q.reference(args.entry)==deployment['entry'],'Immutable actual preparation/source entry')
    Q.need(args.tag and all(c.isalnum()or c in '_-'for c in args.tag),'Literal stage tag')
    inputs=B/'node_epochs'/(args.tag+'_inputs_job_'+os.environ['SLURM_JOB_ID']);inputs.mkdir(mode=0o700)
    old,previous=upstream(Q,parent,cfg['target'],inputs/'original_low',False)
    seed=copy.deepcopy(Q.load(Q.verify(cfg['seed_reference'])))
    Q.need(previous['partition_id']=='low11'and previous['output_directory']==cfg['expected_target_root']and not(pathlib.Path(previous['output_directory'])/'manifest.json').exists(),'Only incomplete original low11 cache')
    if args.mode=='import':
        sources=[]
        for index,item in enumerate(cfg['sources']):
            value,_=upstream(Q,parent,item,inputs/('source_'+str(index)),True)
            value['manifest_reference']=Q.reference(pathlib.Path(value['root'])/'manifest.json');sources.append(value)
        old['additional_terminal_writers']=previous.get('resume_previous_allocations',[])
        seed.update(schema='PUBCHEM_ALPHA_PARTITION_CACHE_IMPORT_PLAN_V1',target=old,sources=sources,reference_manifest_reference=previous['reference_manifest'],filtered_pool_reference=previous['filtered_pool_reference'],authoritative_nn_deployment_reference=previous['source_deployment_reference'])
        module='workflows.expansion.alpha_partition_cache_import_v1.run'
    else:
        imported,ip=upstream(Q,parent,cfg['importer'],inputs/'completed_import',True)
        receipt=Q.reference(pathlib.Path(imported['root'])/'manifest.json');value=Q.load(Q.verify(receipt))
        Q.need(value['schema']=='PUBCHEM_ALPHA_PARTITION_CACHE_IMPORT_V1'and value['status']=='COMPLETE'and value['actual']['uid']==1264 and str(value['actual']['job_id'])==str(cfg['importer']['job_id'])and value['resource_plan']==imported['plan_reference']and value['startup_proof_reference']==imported['startup_proof_reference']and value['target']['plan_reference']==old['plan_reference']and value['target']['startup_proof_reference']==old['startup_proof_reference']and value['target']['runtime']==old['runtime']and value['target']['root']==old['root']and value['reference_manifest_reference']==previous['reference_manifest']and value['filtered_pool_reference']==previous['filtered_pool_reference']and value['old_binding_journals_and_data_rewritten']is False and value['next_epoch_must_reference_this_import_manifest']is True,'Actual completed import bound to this original root and full inputs')
        Q.need(Q.reference(pathlib.Path(old['root'])/'source_binding.json')==value['original_binding_reference'],'Original binding still immutable')
        for ref in value['current_derived_binding_references']:Q.verify(ref)
        seed=preserve_resume(seed,previous,old,receipt,imported)
        seed=prepare(seed,'nn',inputs,Q.verify(previous['filtered_pool_reference']),[])
        module='workflows.expansion.alpha_sharded_novelty_v1.run'
    refs=list(deployment['code_references'])
    for ref in(Q.reference(__file__),Q.reference(args.config),cfg['seed_reference']):
        if ref not in refs:refs.append(ref)
    seed.update(code_references=refs,source_deployment_reference=cfg['deployment_reference'])
    for key in('execution_argv','runtime_existing_output_stage_reused','launcher_startup_proof_reference'):seed.pop(key,None)
    path=inputs/'input_plan.json';Q.write(path,seed)
    argv=[str(PY),'-I','-B',str(D/'node_launcher_rpc_v3_resume.py'),'--template',str(path),'--base-root',str(BASE),'--entry',str(args.entry),'--module',module,'--tag',args.tag,'--control-root',str(B/'node_epochs'),'--gluster-rpc-program',str(D/'gluster_readonly_rpc.py')]
    os.chdir(BASE);os.execv(str(PY),argv)
if __name__=='__main__':main()
