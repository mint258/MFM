"""Submit only closed C1 confirmation plans and connect their existing report consumers."""
from pathlib import Path
import re
import shlex

def private_python_prefix(python, owned_root):
    """Keep the registered private venv prefix; its interpreter may link to the shared base."""
    python=Path(python)
    root=Path(owned_root).resolve()
    prefix=python.parent.parent.resolve()
    if (not python.is_absolute() or python.name!="python" or python.parent.name!="bin"
        or not prefix.is_relative_to((root/"environments").resolve())):
        raise ValueError("The registered Python must remain in the owned private environment prefix")
    return prefix

def validated_groups(preparation, owned_root):
    if preparation.get("stage")!="C1" or preparation.get("status")!="CONDITIONAL_NEURAL_SOURCE_PREPARATION_CLOSED" or preparation.get("failures"):
        raise ValueError("C1 conditional source preparation must close successfully")
    root=Path(owned_root).resolve();seen=set();cells=set()
    groups=preparation["prepared_native_groups"]
    for group in groups:
        primary=str(group["primary_job"])
        if not primary.isdigit() or primary in seen or group["learner"]!="TabPFN":
            raise ValueError("Each original TabPFN producer must occur once")
        seen.add(primary)
        for name in ("program","script"):
            if not Path(group[name]).resolve().is_relative_to(root):
                raise ValueError("Prepared source/environment must stay in the owned benchmark root")
        private_python_prefix(group["python"],root)
        declaration=group["declaration"]
        if (declaration["model_seed"]!=20261026 or declaration["split_and_statistics_seed"]!=20261025
            or declaration["original_labels_or_masks_changed"] or declaration["task_roster_reselection"]
            or not declaration["original_model_budget_unchanged"]):
            raise ValueError("The closed original scientific configuration changed")
        if group["node"] not in {"compute-0-5","compute-0-7","compute-0-22"} or not group["uuid"].startswith("GPU-"):
            raise ValueError("Use only the three existing private benchmark GPU backends")
        if not group["required_tasks"]:raise ValueError("Empty confirmation group")
        for row in group["required_tasks"]:
            cell=(row["endpoint_key"],row["feature_group"],row["learner"])
            if (cell in cells or row["reason"]!="FINAL_SIGNIFICANT_IMPROVEMENT"
                or row["frozen_B1_role"] not in {"RETAIN","APPENDIX"}
                or row["learner"]!="TabPFN" or row["feature_group"]!=group["feature_group"] or int(row["confirmation_seed"])!=20261026
                or int(row["primary_seed"])!=20261025):
                raise ValueError("Only the frozen final significant neural plan can acquire a fit")
            cells.add(cell)
    if len(cells)!=preparation["required_configuration_rows"]:
        raise ValueError("Every required C1 configuration must have exactly one prepared source")
    return groups

def script_with_exports(script, exports):
    if not script.startswith("#!/bin/bash\n") or "\nset -euo pipefail\n" not in script:
        raise ValueError("A registered complete native sbatch script is required")
    prefix="".join("export "+key+"="+shlex.quote(str(value))+"\n" for key,value in sorted(exports.items()))
    return script.replace("\nset -euo pipefail\n","\nset -euo pipefail\n"+prefix,1)

def wire(preparation, preparation_path, owned_root, out, source_cache, scripts, submit, release, write):
    """All jobs remain held until exact returned IDs and the complete chain are recorded."""
    groups=validated_groups(preparation,owned_root)
    out=Path(out);bindings_path=out/"dispatch_bindings.json"
    bindings=dict(stage="C1",preparation_manifest=str(preparation_path),groups=[],unresolved_cells=[])
    record=dict(status="PREPARING_HELD_NATIVE_CHAIN",bindings=bindings,native_jobs=[],jobs_released=[])
    write(out/"dispatch_state.json",record)
    last={};gpu_jobs=[]
    def new_job(path,dependency=None):
        job=str(submit(path,dependency))
        if not re.fullmatch(r"[1-9][0-9]*",job) or job in record["native_jobs"]:
            raise ValueError("A unique actual native Slurm job ID is required")
        record["native_jobs"].append(job)
        write(out/"dispatch_state.json",record)
        return job
    for group in groups:
        job=new_job(Path(group["script"]),("afterany:"+last[group["uuid"]]) if group["uuid"] in last else None)
        last[group["uuid"]]=job;gpu_jobs.append(job)
        bindings["groups"].append(dict(primary_job=str(group["primary_job"]),runs=[dict(job=int(job),array=group["array"])]))
        write(bindings_path,bindings)
    write(bindings_path,bindings)
    exports=dict(BENCHMARK_SOURCE_CACHE=str(source_cache),BENCHMARK_CONFIRMATION_BINDINGS_JSON=str(bindings_path))
    report_path=out/"first_C1_confirmation_report.sbatch"
    write(report_path,script_with_exports(scripts["report"],exports))
    report_job=new_job(report_path,("afterany:"+":".join(gpu_jobs)) if gpu_jobs else None)
    report_manifest=Path(owned_root)/"conditional_evidence/C1"/("job_"+report_job)/"manifest.json"
    combine_path=out/"combine_confirmation_evidence.sbatch"
    write(combine_path,script_with_exports(scripts["combine"],dict(
        BENCHMARK_SOURCE_CACHE=str(source_cache),
        BENCHMARK_B1_CONFIRMATION_REPORT=str(Path(owned_root)/"conditional_evidence/B1/job_4537462/manifest.json"),
        BENCHMARK_C1_CONFIRMATION_REPORT=str(report_manifest))))
    combine_job=new_job(combine_path,"afterok:"+report_job)
    evidence=Path(owned_root)/"conditional_evidence/combined"/("job_"+combine_job)/"manifest.json"
    final_path=out/"final_C1_results.sbatch"
    write(final_path,script_with_exports(scripts["final"],dict(BENCHMARK_CONFIRMATION_EVIDENCE_JSON=str(evidence))))
    final_job=new_job(final_path,"afterok:"+combine_job)
    record.update(status="COMPLETE_CHAIN_RECORDED_BEFORE_RELEASE",report_job=int(report_job),
        combination_job=int(combine_job),final_export_job=int(final_job),
        final_manifest=str(Path(owned_root)/"C1_final_results"/("job_"+final_job)/"manifest.json"))
    write(out/"dispatch_state.json",record)
    for job in record["native_jobs"]:
        release(job)
        record["jobs_released"].append(job)
        write(out/"dispatch_state.json",record)
    record["status"]="C1_CONDITIONAL_CHAIN_RELEASED"
    write(out/"dispatch_state.json",record)
    return record
