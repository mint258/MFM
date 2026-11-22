"""Reuse an idle original GPU7 queue only for still-zero-start CPU successor slots."""
import copy
from workflows.benchmark_evaluation.infrastructure_handover import native_fields,require_owned_pending
from workflows.benchmark_evaluation.reference_cpu_primary import REFERENCE_DATASETS,REFERENCE_GROUPS

ACTIVE=frozenset({"RUNNING","COMPLETING","CONFIGURING","SUSPENDED","RESIZING"})
TERMINAL=frozenset({"COMPLETED","FAILED","CANCELLED","TIMEOUT","OUT_OF_MEMORY","NODE_FAIL","BOOT_FAIL","PREEMPTED","DEADLINE"})

def select_zero_start_cpu_successors(plan,native_by_job):
    if plan.get("schema")!="REGISTERED_REFERENCE_CPU_PRIMARY_PLAN_V1" or plan.get("maximum_parallel_CPU_models")!=8 or plan.get("declared_joint_benchmark_NFS_pool_bytes")!=40*1024**3:
        raise ValueError("Keep the original bounded CPU primary plan and40GiB pool")
    rows=plan.get("models",[])
    jobs=[int(r["new_native_job"]) for r in rows]
    if len(jobs)!=len(set(jobs)):raise ValueError("Duplicate actual primary job")
    eligible=[];skipped=[]
    for row in rows:
        if row["original_CPU_predecessor"] is None:continue
        job=int(row["new_native_job"])
        if row["dataset"] not in REFERENCE_DATASETS or row["feature_group"] not in REFERENCE_GROUPS or row["original_model_fits_started"]!=0:
            raise ValueError("Only original never-started reference successor configurations are covered")
        raw=native_by_job.get(job)
        if raw is None:
            skipped.append(dict(job=job,state="NATIVE_HANDLE_MISSING_NO_REPLAY"));continue
        fields=native_fields(raw)
        if fields.get("JobId")!=str(job) or fields.get("UserId")!="zixiao(1278)":
            raise ValueError("Actual source identity or owner differs")
        state=fields.get("JobState")
        if state=="PENDING":
            if fields.get("Reason")=="JobHeldUser":
                skipped.append(dict(job=job,state="USER_HELD_NOT_REASSIGNED"));continue
            require_owned_pending(raw)
            if fields.get("Restarts")!="0":raise ValueError("A restarted source is never eligible for replay")
            eligible.append(copy.deepcopy(row))
        elif state in ACTIVE|TERMINAL:
            skipped.append(dict(job=job,state=state))
        else:raise ValueError("Unknown native source state; no transfer is permitted")
    return eligible,skipped

def remap_zero_start_cpu_to_gpu_specs(specs,mapping):
    mapping={int(k):int(v) for k,v in mapping.items()}
    if not mapping or any(k<=0 or v<=0 or k==v for k,v in mapping.items()) or len(set(mapping.values()))!=len(mapping):
        raise ValueError("Actual distinct replacement GPU IDs required")
    if any(sum(int(r["job"])==j for r in specs)!=1 for j in mapping):
        raise ValueError("Each declared pending source must occur exactly once")
    result=copy.deepcopy(specs)
    for row in result:
        old=int(row["job"])
        if old not in mapping:continue
        if row["learner"]!="TabPFN" or row["dataset"] not in REFERENCE_DATASETS or row["feature_group"] not in REFERENCE_GROUPS or row.get("primary_execution_backend")!="CPU":
            raise ValueError("Only registered molecular reference CPU primaries may change backend")
        if row["folder"]!="reference_cv_models/job_"+str(old):raise ValueError("Original native source namespace differs")
        row.update(job=mapping[old],folder="reference_cv_models/job_"+str(mapping[old]),
            zero_start_CPU_primary_reassignment_of_job=old,primary_execution_backend="GPU",actual_primary_GPU_node="compute-0-7")
    return result
