"""Resource-only coverage preparation overlay; retain original scientific modules."""
import importlib,runpy,sys
runpy.run_path('/gfshome/alpha/codex_data_v1_20261026/code/after_coverage_1471c84/layer_entry.py',run_name='_original_after_coverage_bootstrap')
from workflows.expansion.expansion_coverage_followup_v1 import prepare_pipeline as original
original_resource_plan=original.resource_plan

def resource_plan(config,phase,tag):
    plan=original_resource_plan(config,phase,tag)
    if phase=='coverage-after':
        if (plan['workers'],plan['worker_rss_cap_bytes'],plan['parent_rss_cap_bytes'],plan['software_rss_budget_bytes'],plan['minimum_node_available_bytes'])!=(16,2<<30,8<<30,48<<30,24<<30):raise ValueError('Actual original sixteen-worker resource contract required')
        plan.update(workers=32,software_rss_budget_bytes=80<<30)
        if plan['workers']*plan['worker_rss_cap_bytes']+plan['parent_rss_cap_bytes']>plan['software_rss_budget_bytes']:raise ValueError('All private references and parent fit the software allowance')
    return plan
original.resource_plan=resource_plan
if __name__=='__main__':
    module=sys.argv.pop(1);importlib.import_module(module).main()