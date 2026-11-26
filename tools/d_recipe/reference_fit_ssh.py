"""Original full-TRAIN A1 fitter with authenticated SSH phase admission.

This entry never collects or fits partial TRAIN. It reuses the existing frozen
fitter, retaining an already committed local result after an interrupted publish.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time


def require_final_collector(receipt, expected_id, node, identity):
    if (receipt.get("execution_id") != expected_id or receipt.get("node") != node
            or receipt.get("status") != "COMPLETE" or receipt.get("returncode") != 0
            or receipt.get("remaining_children") != [] or receipt.get("owned_tree_reaped") is not True):
        raise ValueError("Actual final collection must complete and reap before fitting")
    for key in ("supervisor", "parent"):
        bound = receipt[key]
        if tuple(bound["uids"]) != (os.getuid(),) * 4:
            raise ValueError("Final collection belongs to another owner")
        actual = identity(bound["pid"])
        if (actual is not None and actual.start_ticks == bound["start_ticks"]
                and tuple(actual.uids) == tuple(bound["uids"])):
            raise ValueError("Final collector process still exists")


def require_full_collection(configuration, marker):
    binding = marker["binding"]
    if (marker.get("schema") != "D_A1_COLLECTION_V1"
            or marker.get("status") != "COLLECTION_COMPLETE"
            or marker.get("closed_rows") != binding["rows"]
            or binding.get("split") != "TRAIN"
            or binding["configuration"] != configuration):
        raise ValueError("Complete original full-TRAIN cursor/configuration required")


def fit_or_reuse(configuration, *, build_dataset, fitter, guard, may_start):
    output = Path(configuration["output"])
    source = output / "label_parameters.json"
    if source.is_file():
        return source
    if not may_start():
        raise RuntimeError("Insufficient actual work window for the original fitting unit")
    dataset = build_dataset()
    try:
        if not may_start():
            raise RuntimeError("Insufficient remaining work window after reader initialization")
        return Path(fitter(dataset, output, configuration, guard=guard))
    finally:
        dataset.close()


def publish_once(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.is_file():
        return "REUSE_PUBLISHED_PARAMETERS"
    if not source.is_file() or source.is_symlink() or source.stat().st_uid != os.getuid():
        raise ValueError("Committed owned original fitter output required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = destination.with_name(destination.name + ".partial." + str(os.getpid()) + "." + str(time.time_ns()))
    with source.open("rb") as reader, pending.open("xb") as writer:
        shutil.copyfileobj(reader, writer)
        writer.flush()
        os.fsync(writer.fileno())
    os.replace(pending, destination)
    return "FROZEN_PARAMETERS_PUBLISHED"


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
    hard_end = module.verified_deadline(transport)
    previous = json.loads(Path(transport["predecessor_receipt"]).read_text())
    require_final_collector(previous, transport["predecessor_execution_id"], transport["node"], module.life.identity)
    c = json.loads(Path(transport["reference_configuration"]).read_text())
    root, output = Path(c["local_output_root"]).resolve(), Path(c["output"]).resolve()
    if (root != Path(transport["local_output_root"]).resolve() or c["local_node"] != transport["node"]
            or not output.is_relative_to(root) or transport.get("fit_only") is not True):
        raise ValueError("Original node-bound owned full-TRAIN fit phase required")
    marker = json.loads((output / "collection_checkpoint.json").read_text())
    require_full_collection(c, marker)
    expected = transport["expected_fit_seconds"]
    if not isinstance(expected, (int, float)) or not 0 < expected <= 4 * 3600:
        raise ValueError("A short SSH fitting phase needs a finite <=4h expected unit")
    destination = Path(c["shared_parameters_output"]).resolve()
    from .shared_admission import admit
    admit(transport, [output, destination.parent])
    import fcntl
    with (output / ".own_segment.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if destination.is_file():
            print(json.dumps(dict(stage="D_A1_SSH_FIT", status="REUSE_PUBLISHED_PARAMETERS",
                                  path=str(destination), fitted_again=False)), flush=True)
            return 0
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "current"))
        sys.path.insert(0, c["data_repository"])
        from .fit_reference import fit_collected
        from . import resources
        from .reference_runtime_storage import local_runtime_guard
        physical = local_runtime_guard(root, guard_class=resources.Guard)

        def guard(path, peak):
            if not Path(path).resolve().is_relative_to(root):
                raise ValueError("Original fitter write escaped its admitted local phase")
            return physical.check(path)

        def build_dataset():
            from phychem_mfm.phase1.p_recipe_data import dataset_configuration
            from .dataset import DRecipeDataset
            reader = dataset_configuration({**c, "label_parameters": None, "subset_molecules": None})
            recipe = {**c.get("d_recipe", {}), "label_parameters": None, "split": "TRAIN"}
            return DRecipeDataset(**reader, d_recipe=recipe)

        local_existed = (output / "label_parameters.json").is_file()
        source = fit_or_reuse(c, build_dataset=build_dataset, fitter=fit_collected, guard=guard,
            may_start=lambda: time.time() + expected < hard_end - transport["cleanup_seconds"])
        status = publish_once(source, destination)
        print(json.dumps(dict(stage="D_A1_SSH_FIT", status=status, path=str(destination),
            local_result_reused=local_existed, fit_role="TRAIN", full_collection_rows=marker["closed_rows"],
            configuration_unchanged=True, original_D4_modified=False)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
