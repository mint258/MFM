"""Use the established GPU admission/handoff scheduler with a separate ledger."""
import os,pathlib,sys
R=pathlib.Path('/share/home/zixiao/descriptor_analysis');CONTROL=R/'runs/p_followup_20261116';REPO=pathlib.Path(__file__).resolve().parents[2]
os.environ['P_RECIPE_CONTROL_DIRECTORY']=str(CONTROL)
sys.path.insert(0,str(REPO/'tools/p_recipe'))
import launch_plan as scheduler
# User 2026-11-17 permits suitable development nodes; inherit established
# 5090 > 4090 > 3090 admission and same-task full-state handoff policy.
launch=scheduler.launch
from resources import load,save,guard
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--configuration',required=True);a=p.parse_args()
    script=(REPO/'tools/p_recipe/hybrid.sbatch').read_bytes()
    if b'\r' in script:raise ValueError('Slurm script must be LF')
    guard(force=True)
    inventory=CONTROL/'batch_gpu_inventory.json'
    if not inventory.exists():save(inventory,load(R/'runs/p_recipe_20261113/batch_gpu_inventory.json'))
    plan=dict(configurations=[str(pathlib.Path(a.configuration).resolve())])
    launch(plan)