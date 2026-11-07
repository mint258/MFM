"""Prepare actual Alpha IO reservations for a concrete closed Main return index."""
import argparse,copy,os,runpy
from pathlib import Path
A=Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103';D=A/'control/pubchem_completion_environment_20261103'
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--summary',type=Path,required=True)
    p.add_argument('--base-config',type=Path,required=True);p.add_argument('--entry',type=Path,required=True);p.add_argument('--tag',required=True)
    a=p.parse_args()
    if os.getuid()!=1264 or not __import__('sys').flags.isolated:raise ValueError('Actual isolated Alpha IO preparation')
    runpy.run_path(str(a.entry),run_name='_Alpha_IO_budget_bootstrap')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    from workflows.expansion.uff3_alpha_runtime_v1.prepare_pipeline import upstream,terminal_account,literal
    from workflows.expansion.uff3_alpha_runtime_v1 import budget
    cfg=Q.load(a.base_config);summary=Q.load(a.summary);literal('0',a.tag)
    Q.need(summary['score_rows']==27735005 and summary['file_count']==summary['score_parts']+8
        and summary['index_reference']['bytes']<=64<<20,'Concrete original Main875 closed-score index summary')
    work=D/(a.tag+'_io_inputs');work.mkdir(mode=0o700)
    meta=upstream('1885209','exact_key_filter_ea3057e',B/'node_epochs');folder=work/'closed209';folder.mkdir()
    command=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=5','218.192.171.238','sacct']
    meta['accounting_reference']=terminal_account('1885209',folder,command)
    binding={k:meta[k]for k in('runtime','plan_reference','startup_proof_reference','accounting_reference')}
    census=budget.census(cfg['baseline_budget_reference'],[dict(scope='exact',**binding)],
        cfg['excluded_active_allocations'],work/'native_closed_blocks.json')
    inline=budget.inline(cfg['baseline_budget_reference'],census);cap=5000000000
    remaining=inline['remaining_reserved_bytes_by_scope']['source_transport']
    Q.need(cap<=remaining and summary['total_file_bytes']+summary['index_reference']['bytes']+16_000_000<=cap,
        'Real remaining source_transport20GB includes data/index/catalog and all-future reserve')
    template=Q.load(Q.verify(cfg['resources_reference']))
    plan={k:template[k]for k in('endpoint','uid','quota_snapshot','quota_authority')}
    output=A/'inputs'/a.tag
    plan.update(schema='ALPHA_NATIVE_RESCUE_TRANSPORT_IO_PLAN_V1',scientific_computation=False,
        no_Slurm_parent_or_C0_claimed=True,source_entry=str(a.entry),output_scope_root=str(output),output_directory=str(output),
        output_cap_bytes=cap,other_future_reserved_bytes=inline['other_future_reserved_bytes_for_each_scope']['source_transport']+remaining-cap,
        minimum_free_bytes=inline['minimum_free_after_all_future_bytes'],software_rss_budget_bytes=2<<30,minimum_node_available_bytes=4<<30,
        source_index_reference=summary['index_reference'],main_manifest_reference=summary['main_manifest_reference'],
        main_native_sacct_reference=summary['main_native_sacct_reference'],reviewed_storage_budget_reference=cfg['baseline_budget_reference'],
        native_closed_census_reference=census,actual_future_storage_partition=inline,
        preparation_source_reference=Q.reference(__file__),source_summary_reference=Q.reference(a.summary),
        source_base_config_reference=Q.reference(a.base_config))
    path=D/(a.tag+'_io_resources.json');result=Q.write(path,plan)
    from workflows.expansion.alpha_runtime_v1.quota import budget_check
    output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    Q.need(not output.exists(),'Preserve all previous IO results/partials')
    # Use the existing own parent only for a conservative no-credit quota probe.
    probe=dict(plan,output_scope_root=str(output.parent))
    observed=budget_check(probe,0,output.parent,prequery_credit_provider=lambda cutoff:0)
    print(__import__('json').dumps(dict(io_plan_reference=result,output_directory=str(output),resource_observation=observed,
        scientific_import_completed=False)),flush=True)
if __name__=='__main__':main()
