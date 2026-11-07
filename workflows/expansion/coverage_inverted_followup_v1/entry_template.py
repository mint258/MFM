"""Full augmented-reference equivalent kernel; original coverage function remains unchanged."""
import importlib,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from workflows.expansion.expansion_coverage_followup_v1 import prepare_pipeline as original
old_resource_plan=original.resource_plan
old_launch_argv=original.launch_argv
def resource_plan(config,phase,tag):
    plan=old_resource_plan(config,phase,tag)
    if phase=='coverage-after':
        if (plan['workers'],plan['worker_rss_cap_bytes'],plan['parent_rss_cap_bytes'],plan['software_rss_budget_bytes'],plan['minimum_node_available_bytes'])!=(16,2<<30,8<<30,48<<30,24<<30):raise ValueError('Exact original resource contract')
        plan.update(workers=32,worker_rss_cap_bytes=5<<29,software_rss_budget_bytes=96<<30,comparison_backend_adoption_reference=config['comparison_backend_adoption_reference'])
        if plan['workers']*plan['worker_rss_cap_bytes']+plan['parent_rss_cap_bytes']>plan['software_rss_budget_bytes']:raise ValueError('All full private references fit budget')
    return plan
def launch_argv(template,phase,*args,**kwargs):
    argv=old_launch_argv(template,phase,*args,**kwargs)
    if phase=='coverage-after':argv[argv.index('--module')+1]='workflows.expansion.coverage_inverted_followup_v1.coverage'
    return argv
original.resource_plan=resource_plan
original.launch_argv=launch_argv
if __name__=='__main__':
    module=sys.argv.pop(1);importlib.import_module(module).main()
