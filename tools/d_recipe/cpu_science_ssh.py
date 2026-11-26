"""Authenticated CPU SSH transport for existing D diagnostics and A/B/C.

Scientific configurations retain the preceding GPU snapshot's exact binding;
the actual CPU node, affinity, deadline and reservations are separate inputs.
No Slurm identity is created or copied into the native CPU environment.
"""
import argparse
from contextlib import contextmanager
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys

OPERATIONS = ("diagnostic_statistics", "layer_readouts", "development_panel")
REPO = Path(__file__).resolve().parents[2]


def thread_limit(requested, allocated):
    if (type(requested) is not int or type(allocated) is not int
            or requested < 1 or allocated < 1):
        raise ValueError("Positive requested and actually available CPU counts required")
    return min(requested, allocated)


def cpu_configuration(operation, source):
    if operation not in OPERATIONS:
        raise ValueError("Only the registered existing CPU scientific operations")
    c = dict(source)
    if operation in ("layer_readouts", "development_panel"):
        if c.get("phase") not in ("gpu", "cpu"):
            raise ValueError("The actual GPU/CPU configuration snapshot is required")
        c["phase"] = "cpu"
    return c


@contextmanager
def authenticated_site(resources, configuration, verify):
    previous = resources.execution_site
    def cpu_only(candidate, *, cpu):
        if cpu is not True or candidate is not configuration:
            raise ValueError("This authenticated transport belongs only to its exact CPU configuration")
        verify()
    try:
        resources.execution_site = cpu_only
        yield
    finally:
        resources.execution_site = previous


def dispatch(operation, c, guard, cpus, *, importer=importlib.import_module):
    if operation not in OPERATIONS:
        raise ValueError("No unregistered operation may enter the native CPU transport")
    module = importer("tools.d_recipe." + operation)
    if operation == "diagnostic_statistics":
        return module.run(c, guard=guard)
    if operation == "development_panel":
        return module.run_cpu(c, guard=guard, allocated_cpus=cpus)
    return module.run_cpu(c, guard=guard)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    args = parser.parse_args()
    t = json.loads(Path(args.configuration).read_text())
    c = cpu_configuration(t["operation"], json.loads(Path(t["scientific_configuration"]).read_text()))
    path = REPO.parent / "MFM_p_recipe/tools/p_recipe/cpu_ssh_runtime.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("d_registered_CPU_provider", path)
    provider = importlib.util.module_from_spec(spec); spec.loader.exec_module(provider)
    verify = lambda: provider.verified_deadline(t)
    verify()
    if os.environ.get("CUDA_VISIBLE_DEVICES") or os.environ.get("SLURM_JOB_ID"):
        raise ValueError("Native CPU transport requires no CUDA or Slurm identity")
    from .shared_admission import admit
    admit(t, [Path(c["output"])])
    sys.path[:0] = [str(REPO / "current"), str(REPO.parent / "MFM_d_descriptors_20261120")]
    from . import resources
    from .canonical_runtime import guard_class
    # Separate current CPU forecasts, never the old GPU snapshot's resources.
    guard = guard_class(resources)(t, admit=False)
    with authenticated_site(resources, c, verify):
        result = dispatch(t["operation"], c, guard, len(os.sched_getaffinity(0)))
    print(json.dumps(dict(stage="D_ORIGINAL_CPU_SCIENCE_RESULT", execution_id=t["ssh_execution_id"],
        node=t["node"], operation=t["operation"], scientific_configuration=t["scientific_configuration"],
        actual_backend="ssh_cpu", original_result=result), allow_nan=False), flush=True)


if __name__ == "__main__":
    main()

