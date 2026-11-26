"""Next A1 SSH segments: canonical phase admission, original collector entry.

The current historical configuration stays the exact cursor binding. Its copied
peer budgets are not read for admission. This process-local writer adaptation
does not modify the source or execution of a previously launched segment.
"""
import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import sys


def require_closed_predecessor(receipt, expected_id, identity):
    if (receipt.get("execution_id") != expected_id
            or receipt.get("status") != "CURSOR_SAVED_NOT_COMPLETE"
            or receipt.get("returncode") != 75 or receipt.get("remaining_children") != []
            or receipt.get("owned_tree_reaped") is not True):
        raise ValueError("Original incomplete cursor segment must be saved and fully reaped")
    for key in ("supervisor", "parent"):
        bound = receipt[key]
        if tuple(bound["uids"]) != (os.getuid(),) * 4:
            raise ValueError("Predecessor belongs to a different owner")
        actual = identity(bound["pid"])
        if (actual is not None and actual.start_ticks == bound["start_ticks"]
                and tuple(actual.uids) == tuple(bound["uids"])):
            raise ValueError("Original predecessor process still exists; do not duplicate")


@contextmanager
def scoped_collector_writes(resources, root):
    """After whole-phase admission, keep each original write within that root."""
    root = Path(root).resolve()
    previous = resources.admit_output

    def scoped(configuration, path):
        if not Path(path).resolve().is_relative_to(root):
            raise ValueError("Collector write escaped its admitted local phase")

    try:
        resources.admit_output = scoped
        yield
    finally:
        resources.admit_output = previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    args = parser.parse_args()
    transport = json.loads(Path(args.configuration).read_text())
    provider = Path("/share/home/zixiao/descriptor_analysis/MFM_p_recipe/tools/p_recipe/cpu_ssh_runtime.py")
    sys.path.insert(0, str(provider.parent))
    spec = importlib.util.spec_from_file_location("d_cpu_ssh_provider", provider)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.verified_deadline(transport)
    previous = json.loads(Path(transport["predecessor_receipt"]).read_text())
    require_closed_predecessor(previous, transport["predecessor_execution_id"], module.life.identity)
    original = json.loads(Path(transport["reference_configuration"]).read_text())
    if (Path(original["local_output_root"]).resolve() != Path(transport["local_output_root"]).resolve()
            or original["local_node"] != transport["node"]
            or transport.get("collection_only") is not True):
        raise ValueError("Original owned collection root/node and collection-only phase required")
    from .shared_admission import admit
    # One phase covers all original remaining arrays and serialization margin.
    # Original256-row commits are retained. Fitting is a distinct, later phase.
    admit(transport, [original["output"]])
    from . import resources, reference_segment
    import fcntl
    lock_path = Path(original["output"]) / ".own_segment.lock"
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with scoped_collector_writes(resources, transport["local_output_root"]):
            return reference_segment.main()


if __name__ == "__main__":
    raise SystemExit(main())
