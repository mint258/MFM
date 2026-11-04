"""Prepare FP-only tail export in an existing authenticated Alpha native step."""
import argparse,copy,os
from pathlib import Path
import runpy,sys
A=Path('/gfshome/alpha/codex_data_v1_20261026');B=A/'control/pubchem_expansion_runtime_20261103';D=A/'control/pubchem_completion_environment_20261103'
BASE=A/'code/pubchem_completion_20261103_497c584';PY=A/'software/pubchem_completion_20261103_venv/bin/python'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--entry',type=Path,required=True);p.add_argument('--tag',required=True);a=p.parse_args()
    if os.getuid()!=1264 or not sys.flags.isolated or os.environ.get('SLURM_JOB_ID')!='1885232' or not os.environ.get('SLURM_STEP_ID','').isdigit():
        raise ValueError('Only actual own Alpha232 native numeric step')
    runpy.run_path(str(a.entry),run_name='_source_bootstrap')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    from workflows.expansion.uff3_alpha_runtime_v1.prepare_pipeline import upstream,terminal_account,literal
    from workflows.expansion.uff3_alpha_runtime_v1 import budget
    cfg=Q.load(a.config);deployment=Q.load(Q.verify(cfg['deployment_reference']))
    Q.need(Q.reference(__file__)==cfg['prepare_script_reference'] and Q.reference(a.entry)==deployment['entry'],'Exact prepared/tested source and entry')
    literal('1885232',a.tag)
    inputs=B/'node_epochs'/(a.tag+'_inputs_job_1885232_step_'+os.environ['SLURM_STEP_ID']);inputs.mkdir(mode=0o700)
    command=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=5','218.192.171.238','sacct']
    closed=upstream('1885209','exact_key_filter_ea3057e',B/'node_epochs')
    folder=inputs/'closed_1885209';folder.mkdir();closed['accounting_reference']=terminal_account('1885209',folder,command)
    binding={k:closed[k]for k in('runtime','plan_reference','startup_proof_reference','accounting_reference')}
    active=cfg['excluded_active_allocations']
    census=budget.census(cfg['baseline_budget_reference'],[dict(scope='exact',**binding)],active,inputs/'native_closed_blocks.json')
    inline=budget.inline(cfg['baseline_budget_reference'],census)
    remaining=inline['remaining_reserved_bytes_by_scope']['exact'];cap=30_000_000_000
    Q.need(cap<=remaining,'Private export including spill fits unchanged exact remaining cap')
    plan=copy.deepcopy(Q.load(Q.verify(cfg['resources_reference'])))
    refs=list(deployment['code_references'])
    for ref in(Q.reference(__file__),Q.reference(a.config)):
        if ref not in refs:refs.append(ref)
    plan.update(schema='ALPHA_EXACT_FP_RESCUE_EXPORT_PLAN_V1',expected_parent_job_id='1885232',
        source_filter_reference=Q.reference(Path(closed['output_directory'])/'manifest.json'),
        reference_manifest_reference=cfg['reference_manifest_reference'],
        md5_hex_text_prefixes=['8','9','a','e','f'],duckdb_threads=4,workers=16,
        parent_rss_cap_bytes=48<<30,software_rss_budget_bytes=48<<30,
        minimum_node_available_bytes=24<<30,sql_memory_bytes=32<<30,spill_cap_bytes=20_000_000_000,
        rows_per_part=200000,output_scope_root=cfg['output_scope_root'],
        output_directory=str(Path(cfg['output_scope_root'])/'producer_LAUNCHER_ASSIGN_REAL_JOB_ID'),
        output_cap_bytes=cap,other_future_reserved_bytes=inline['other_future_reserved_bytes_for_each_scope']['exact']+remaining-cap,
        minimum_free_bytes=inline['minimum_free_after_all_future_bytes'],
        runtime_profile_reference=cfg['runtime_profile_reference'],source_deployment_reference=cfg['deployment_reference'],
        code_references=refs,excluded_active_allocations=active,scope_key='exact_FP_export_tail8_9_a_e_f_v1',
        reviewed_storage_budget_reference=cfg['baseline_budget_reference'],native_closed_census_reference=census,
        actual_future_storage_partition=inline)
    for key in('execution_argv','resume_output_directory','runtime_existing_output_stage_reused','resume_previous_allocations'):
        plan.pop(key,None)
    path=inputs/'input_plan.json';Q.write(path,plan)
    argv=[str(PY),'-I','-B',str(D/'node_launcher_rpc_v3_resume.py'),'--template',str(path),'--base-root',str(BASE),
        '--entry',str(a.entry),'--module','workflows.expansion.main_exact_rescue_queries_v1.run','--tag',a.tag,
        '--control-root',str(B/'node_epochs'),'--gluster-rpc-program',str(D/'gluster_readonly_rpc.py')]
    os.chdir(BASE);os.execv(str(PY),argv)


if __name__=='__main__':main()
