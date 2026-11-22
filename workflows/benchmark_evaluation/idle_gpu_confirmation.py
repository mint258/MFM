"""Restore two never-started required CPU queue tails to their original idle GPU body."""
import re
from .confirmation_cpu_pool import validate_required_group
PLACEMENTS={4538359:(29,"compute-0-5","GPU-dac07d74-6269-c7db-8832-340dd3c0b377"),4538360:(30,"compute-0-6","GPU-bdb3e139-15a8-755e-2e80-f2b8abaf66ef")}
def prepare_script(row,script):
    old=row["replaced_CPU_job"]
    if old not in PLACEMENTS:raise ValueError("Only the two recorded zero-start tails")
    index,node,uuid=PLACEMENTS[old]
    if row["group_index"]!=index:raise ValueError("Original group identity changed")
    group=row["group"];validate_required_group(group)
    if (group["learner"]!="TabPFN" or len(group["required_tasks"])!=1
        or group["environment"]!=row["execution_environment"]):
        raise ValueError("Preserve the original single neural task and complete selectors")
    if script.count("#SBATCH --cpus-per-task=2")!=1 or script.count("_gpu_runtime=module.GpuRuntime(")!=1:
        raise ValueError("Original two-CPU GPU runtime wrapper required")
    if script.count("#SBATCH --nodelist="+group["node"])!=1 or script.count("expected_node="+repr(group["node"]))!=1 or script.count("gpu_uuid="+repr(group["uuid"]))!=1:
        raise ValueError("Original physical GPU binding must be exact")
    for key,value in group["environment"].items():
        if script.count("export "+key+"="+str(value)+"\n")!=1:raise ValueError("An original model/task selector is absent")
    result=script.replace("#SBATCH --nodelist="+group["node"],"#SBATCH --nodelist="+node)
    result=result.replace("expected_node="+repr(group["node"]),"expected_node="+repr(node))
    result=result.replace("gpu_uuid="+repr(group["uuid"]),"gpu_uuid="+repr(uuid))
    result=re.sub(r"(?m)^#SBATCH --output=.*$", "#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_idle_GPU5_6_%j.log",result,count=1)
    if result.count("program=Path(")!=script.count("program=Path("):
        raise ValueError("Scientific body loading changed")
    return result
