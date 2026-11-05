"""Prepare the locked, terminal Alpha import of actual closed Main rescue scores."""
import argparse,copy,os,runpy,subprocess,sys
from pathlib import Path
A=Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103'
D=A/'control/pubchem_completion_environment_20261103'
BASE=A/'code/pubchem_completion_20261103_497c584'
PY=A/'software/pubchem_completion_20261103_venv/bin/python'
COMMAND=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=5','218.192.171.238','sacct']
def terminal_target(Q,parent,job,folder):
    raw=subprocess.run([*COMMAND,'-j',job,'--parsable2','--format=JobIDRaw%40,State%24,ExitCode,UID,ElapsedRaw,AllocCPUS,NodeList%128'],
        capture_output=True,text=True,check=False)
    Q.need(raw.returncode==0,'Actual Alpha native terminal accounting unavailable')
    lines=raw.stdout.splitlines();Q.need(lines,'Actual accounting header required')
    names=lines[0].split('|');rows=[dict(zip(names,line.split('|')))for line in lines[1:]if line]
    path=folder/'native_sacct.txt'
    with path.open('x')as f:f.write(raw.stdout)
    ref=Q.write(folder/'native_accounting.json',dict(endpoint=Q.ENDPOINT,uid=Q.UID,
        actual_parents=[row for row in rows if row.get('JobIDRaw')==job],raw_sacct_reference=Q.reference(path)))
    parent(dict(endpoint=Q.ENDPOINT,uid=Q.UID,job_id=job),ref,require_C0=False)
    return ref
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True,type=Path)
    p.add_argument('--entry',required=True,type=Path);p.add_argument('--tag',required=True);a=p.parse_args()
    if os.getuid()!=1264 or not sys.flags.isolated or not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('Actual isolated Alpha allocation only')
    runpy.run_path(str(a.entry),run_name='_import_source_bootstrap')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    from workflows.expansion.main_exact_rescue_v1 import common as C
    from workflows.expansion.uff3_alpha_runtime_v1.prepare_pipeline import upstream,terminal_account,literal
    from workflows.expansion.uff3_alpha_runtime_v1.terminal import parent
    from workflows.expansion.uff3_alpha_runtime_v1 import budget
    cfg=Q.load(a.config);source=Q.load(Q.verify(cfg['deployment_reference']))
    Q.need(Q.reference(__file__)==cfg['prepare_script_reference']and Q.reference(a.entry)==source['entry'],
        'Actual immutable import preparation and namespace')
    literal(os.environ['SLURM_JOB_ID'],a.tag)
    inputs=B/'node_epochs'/(a.tag+'_inputs_job_'+os.environ['SLURM_JOB_ID']);inputs.mkdir(mode=0o700,parents=True)
    transport=C.Transport(cfg['transport_reference'],C.MAIN,C.ALPHA,1264)
    main=C.body(transport.resolve(cfg['main_manifest_reference']))
    C.need(main['schema']=='MAIN_EXACT_FP_RESCUE_SCORES_V1'and main['status']=='COMPLETE','Closed actual Main result only')
    C.native_closed(main['actual'],transport.resolve(cfg['main_native_sacct_reference']),1278,parent_required=True)
    targets=[]
    for item in cfg['score_jobs']:
        job=str(item['job_id']);old=upstream(job,item['tag'],B/'node_epochs')
        folder=inputs/literal(job,item['tag']);folder.mkdir()
        account=terminal_target(Q,parent,job,folder)
        targets.append(dict(root=old['output_directory'],runtime=old['runtime'],plan_reference=old['plan_reference'],
            startup_proof_reference=old['startup_proof_reference'],accounting_reference=account))
    Q.need(len(targets)==2,'Exactly the original two logical target roots')
    filtered=upstream('1885209','exact_key_filter_ea3057e',B/'node_epochs')
    folder=inputs/'closed_1885209';folder.mkdir()
    filtered['accounting_reference']=terminal_account('1885209',folder,COMMAND)
    binding={k:filtered[k]for k in('runtime','plan_reference','startup_proof_reference','accounting_reference')}
    census=budget.census(cfg['baseline_budget_reference'],[dict(scope='exact',**binding)],
        cfg['excluded_active_allocations'],inputs/'native_closed_blocks.json')
    inline=budget.inline(cfg['baseline_budget_reference'],census)
    Q.need(inline['scope_total_caps_bytes']['exact']==300000000000,'Unchanged whole exact scope300GB')
    plan=copy.deepcopy(Q.load(Q.verify(cfg['resources_reference'])))
    refs=list(source['code_references'])
    for ref in(Q.reference(__file__),Q.reference(a.config)):
        if ref not in refs:refs.append(ref)
    plan.update(schema='ALPHA_MAIN_EXACT_RESCUE_IMPORT_PLAN_V1',
        main_manifest_reference=cfg['main_manifest_reference'],main_native_sacct_reference=cfg['main_native_sacct_reference'],
        transport_reference=cfg['transport_reference'],reference_manifest_reference=main['reference_manifest_reference'],
        targets=targets,workers=32,parent_rss_cap_bytes=64<<30,software_rss_budget_bytes=80<<30,
        minimum_node_available_bytes=24<<30,sql_memory_bytes=48<<30,spill_cap_bytes=30000000000,
        output_scope_root='/gfshome/alpha/pubchem_expansion_20261103/exact',
        output_directory='/gfshome/alpha/pubchem_expansion_20261103/exact/producer_LAUNCHER_ASSIGN_REAL_JOB_ID',
        output_cap_bytes=300000000000,other_future_reserved_bytes=inline['other_future_reserved_bytes_for_each_scope']['exact'],
        minimum_free_bytes=inline['minimum_free_after_all_future_bytes'],
        runtime_profile_reference=cfg['runtime_profile_reference'],source_deployment_reference=cfg['deployment_reference'],
        code_references=refs,scope_key='terminal_Main_exact_FP_import_into_original_two_logical_roots_v1',
        reviewed_storage_budget_reference=cfg['baseline_budget_reference'],native_closed_census_reference=census,
        actual_future_storage_partition=inline,excluded_active_allocations=cfg['excluded_active_allocations'])
    for key in('execution_argv','resume_output_directory','runtime_existing_output_stage_reused','resume_previous_allocations'):
        plan.pop(key,None)
    path=inputs/'input_plan.json';Q.write(path,plan)
    argv=[str(PY),'-I','-B',str(D/'node_launcher_rpc_v3_resume.py'),'--template',str(path),
        '--base-root',str(BASE),'--entry',str(a.entry),'--module','workflows.expansion.main_exact_rescue_v1.importer',
        '--tag',a.tag,'--control-root',str(B/'node_epochs'),'--gluster-rpc-program',str(D/'gluster_readonly_rpc.py')]
    os.chdir(BASE);os.execv(str(PY),argv)
if __name__=='__main__':main()
