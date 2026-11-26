"""Bounded SSH collection of existing A1 observations; never fit partial TRAIN.

The original configuration remains the cursor binding. Transport identity is
verified separately with the existing shared CPU SSH provider; no Slurm ID is
invented. This entry does not generate descriptors, labels or conformers.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    args = parser.parse_args()
    transport = json.loads(Path(args.configuration).read_text())
    provider_path = Path(transport["cpu_ssh_provider"]).resolve()
    expected = Path("/share/home/zixiao/descriptor_analysis/MFM_p_recipe/tools/p_recipe/cpu_ssh_runtime.py")
    if provider_path != expected:
        raise ValueError("Reuse the established CPU SSH provider")
    sys.path.insert(0, str(provider_path.parent))
    spec = importlib.util.spec_from_file_location("d_shared_cpu_ssh", provider_path)
    provider = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provider)
    hard_end = provider.verified_deadline(transport)
    config = json.loads(Path(transport["reference_configuration"]).read_text())
    node = socket.gethostname().split(".")[0]
    root = Path(config["local_output_root"]).resolve()
    output = Path(config["output"]).resolve()
    if (node != config["local_node"] or root.parent != Path("/tmp")
            or not root.name.startswith("d_recipe_") or not output.is_relative_to(root)
            or not root.is_dir() or root.stat().st_uid != os.getuid()
            or os.environ.get("SLURM_JOB_ID")):
        raise ValueError("Original owned node-bound collection root required")
    duration, unit = transport["segment_seconds"], transport["work_unit_seconds"]
    if not 0 < duration <= 4 * 3600 or unit >= duration:
        raise ValueError("A segment must fit within four hours and its cleanup window")
    stop_at = min(time.time() + duration - unit,
                  hard_end - transport["cleanup_seconds"] - unit)
    stop_requested = False

    def request_stop(signum, frame):
        nonlocal stop_requested
        stop_requested = True

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGUSR1):
        signal.signal(sig, request_stop)

    def should_stop():
        return stop_requested or time.time() >= stop_at

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "current"))
    sys.path.insert(0, config["data_repository"])
    from phychem_mfm.phase1.p_recipe_data import dataset_configuration
    from tools.d_recipe.dataset import DRecipeDataset
    from tools.d_recipe.fit_reference import collect
    from tools.d_recipe.resources import admit_output

    protection = dict(config, storage_peak_bytes=config["peak_bytes"])

    def guard(path, peak):
        if not Path(path).resolve().is_relative_to(root):
            raise ValueError("A1 segment writer escaped its existing owned root")
        return admit_output(protection, path)

    guard(output, config["peak_bytes"])
    reader = dataset_configuration({**config, "label_parameters": None, "subset_molecules": None})
    recipe = {**config.get("d_recipe", {}), "label_parameters": None, "split": "TRAIN"}
    dataset = DRecipeDataset(**reader, d_recipe=recipe)
    try:
        state = collect(dataset, output, config, guard=guard, should_stop=should_stop)
    finally:
        dataset.close()
    print(json.dumps(dict(
        stage="D_A1_SSH_SEGMENT_SAVED", execution_id=transport["ssh_execution_id"],
        status=state["status"], closed_rows=state["closed_rows"],
        total_rows=state["binding"]["rows"], checkpoint=str(output / "collection_checkpoint.json"),
        configuration_unchanged=True, partial_TRAIN_fitted=False)), flush=True)
    return 0 if state["status"] == "COLLECTION_COMPLETE" else 75


if __name__ == "__main__":
    raise SystemExit(main())
