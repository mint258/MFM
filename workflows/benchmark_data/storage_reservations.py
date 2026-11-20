"""Resolve the current benchmark NFS future pool; no science, source data or GPU control."""
import json
import os
from pathlib import Path

OWNED_SCOPES=(Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119"),Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119"))
COMPONENTS=frozenset(("model_P_NFS","private_environments","miscellaneous","S_full_study",
                     "D_joint_replaces_old_14GiB","benchmark_B1_C1"))

def declared_concurrent(policy):
    if policy.get("schema")!="benchmark-shared-storage-reservations-v1":
        raise RuntimeError("Unknown shared-storage reservation schema")
    values=policy.get("components",{})
    if set(values)!=COMPONENTS or any(type(value) is not int or value<0 for value in values.values()):
        raise RuntimeError("Shared future components must each occur once with known nonnegative bytes")
    if set(policy.get("owned_scopes",()))!={str(path) for path in OWNED_SCOPES}:
        raise RuntimeError("Storage policy must stay limited to the two owned benchmark output scopes")
    total=sum(values.values())
    if total!=policy.get("concurrent_total_bytes"):
        raise RuntimeError("Shared future total differs from its declared components")
    return total

def local_reserve(stat, needed=16*1024**2):
    total=stat.f_blocks*stat.f_frsize
    floor=max(10*1024**3,total//10)
    if stat.f_bavail*stat.f_frsize<floor+needed or stat.f_favail<2000:
        raise RuntimeError("Actual root/tmp system and Slurm reserve would be crossed")
    return floor

def current_concurrent(root, requested, *, policy_path=None):
    path=Path(root).resolve()
    if not any(path==scope or scope in path.parents for scope in OWNED_SCOPES):
        return requested
    policy_path=Path(policy_path) if policy_path is not None else Path(__file__).with_name("benchmark_storage_reservations.json")
    policy=json.loads(policy_path.read_text())
    concurrent=declared_concurrent(policy)
    for target in ("/","/tmp"):local_reserve(os.statvfs(target))
    return max(requested,concurrent)
