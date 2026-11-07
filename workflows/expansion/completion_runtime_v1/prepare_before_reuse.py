"""Prepare an independent missing-only fixed1M coverage plan inside Alpha Slurm."""
import argparse
import copy
import os
from pathlib import Path
import runpy
import sys

A=Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103'
D=A/'control/pubchem_completion_environment_20261103'
BASE=A/'code/pubchem_completion_20261103_497c584'
PY=A/'software/pubchem_completion_20261103_venv/bin/python'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--entry',required=True,type=Path)
    parser.add_argument('--tag',required=True)
    args=parser.parse_args()
    if os.getuid()!=1264 or not sys.flags.isolated or not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('Actual isolated Alpha allocation required')
    runpy.run_path(str(args.entry),run_name='_before_source_bootstrap')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    from workflows.expansion.uff3_alpha_runtime_v1.prepare_pipeline import upstream,terminal_account,literal
    from workflows.expansion.uff3_alpha_runtime_v1 import budget
    literal(os.environ['SLURM_JOB_ID'],args.tag)
    config=Q.load(args.config)
    Q.need(Q.reference(__file__)==config['prepare_script_reference'],'Actual source-pinned preparation script')
    source=Q.load(Q.verify(config['deployment_reference']))
    Q.need(source['entry']==Q.reference(args.entry),'Actual immutable tested entry')
    inputs=B/'node_epochs'/(args.tag+'_inputs_job_'+os.environ['SLURM_JOB_ID'])
    inputs.mkdir(mode=0o700)
    command=config['accounting_command_prefix']
    Q.need(command==['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=5','218.192.171.238','sacct'],
           'Actual Alpha native accounting RPC, never compute-local localhost6819')
    actual={}
    for item in config['closed_allocation_sources']:
        job=str(item['job_id']);tag=item['tag']
        meta=upstream(job,tag,B/'node_epochs')
        folder=inputs/literal(job,tag);folder.mkdir()
        meta['accounting_reference']=terminal_account(job,folder,command)
        actual[job]=meta
    def binding(job):
        value=actual[str(job)]
        return {k:value[k]for k in('runtime','plan_reference','startup_proof_reference','accounting_reference')}
    allocations=[dict(scope=item['scope'],**binding(item['job_id']))for item in config['closed_allocation_sources']]
    active=config['excluded_active_allocations']
    census=budget.census(config['baseline_budget_reference'],allocations,active,inputs/'native_closed_blocks.json')
    inline=budget.inline(config['baseline_budget_reference'],census)
    cap=config['output_cap_bytes'];remaining=inline['remaining_reserved_bytes_by_scope']['exact']
    Q.need(type(cap)is int and 0<cap<=remaining,'Private coverage cap within inherited remaining exact budget')
    template=copy.deepcopy(Q.load(Q.verify(config['resources_reference'])))
    rank_job=str(config['rank_job_id']);rank=binding(rank_job)
    rank['receipt_reference']=Q.reference(Path(actual[rank_job]['output_directory'])/'receipt.json')
    scores=[]
    for item in config['score_jobs']:
        value=binding(item['job_id'])
        value['manifest_reference']=Q.reference(Path(actual[str(item['job_id'])]['output_directory'])/'manifest.json')
        scores.append(value)
    probe=source['actual_metadata_probe']
    borrowed={name:probe[name]for name in('engine','coverage','cache','contracts','workers','authority')}
    code=list(source['code_references'])
    for ref in(Q.reference(__file__),Q.reference(args.config)):
        if ref not in code:code.append(ref)
    template.update(schema='PUBCHEM_FIXED1M_CLOSED_FP_REUSE_COVERAGE_PLAN_V1',reference_role='before',
        reference_manifest=config['reference_manifest'],baseline_receipt=config['baseline_receipt'],
        backend_adoption_reference=config['backend_adoption_reference'],
        compiled_backend_implementation='INTEGER_INVERTED_CSR_PRIVATE_COPY_PROTOTYPE_V1',
        rank_completed=rank,closed_score_sources=scores,excluded_active_allocations=active,
        borrowed_source_references=borrowed,code_references=code,
        source_deployment_reference=config['deployment_reference'],
        runtime_profile_reference=config['runtime_profile_reference'],
        workers=16,worker_rss_cap_bytes=1<<30,parent_rss_cap_bytes=40<<30,
        software_rss_budget_bytes=56<<30,minimum_node_available_bytes=24<<30,
        sqlite_cache_bytes=1<<30,sql_memory_bytes=24<<30,spill_cap_bytes=2000000000,
        query_batch=128,output_scope_root=config['output_scope_root'],
        output_directory=str(Path(config['output_scope_root'])/'producer_LAUNCHER_ASSIGN_REAL_JOB_ID'),
        output_cap_bytes=cap,
        other_future_reserved_bytes=inline['other_future_reserved_bytes_for_each_scope']['exact']+remaining-cap,
        minimum_free_bytes=inline['minimum_free_after_all_future_bytes'],
        reviewed_storage_budget_reference=config['baseline_budget_reference'],
        native_closed_census_reference=census,before_reuse_storage_partition=inline,
        scope_key='same183_fixed1M_closed_score_reuse_before_v1')
    for key in('execution_argv','resume_output_directory','runtime_existing_output_stage_reused','resume_previous_allocations'):
        template.pop(key,None)
    path=inputs/'input_plan.json';Q.write(path,template)
    argv=[str(PY),'-I','-B',str(D/'node_launcher_rpc_v3_resume.py'),
        '--template',str(path),'--base-root',str(BASE),'--entry',str(args.entry),
        '--module','workflows.expansion.before_coverage_reuse_v1.run','--tag',args.tag,
        '--control-root',str(B/'node_epochs'),'--gluster-rpc-program',str(D/'gluster_readonly_rpc.py')]
    os.chdir(BASE)
    os.execv(str(PY),argv)


if __name__=='__main__':
    main()
