"""Existing-checkpoint D R1/R3 producer and its separate CPU finalization."""
import argparse
import json
import os
from pathlib import Path
import time

from .budget_readout_plan import AUTHORITY, NATIVE_ARMS, points, require_confirmations

WAITING = "GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS"


def read(path):
    return json.loads(Path(path).read_text())


def validate_source(c, *, resolver):
    closed = {}
    if set(c["closed_confirmation_configurations"]) != set(NATIVE_ARMS):
        raise ValueError("Both original native9M confirmation sources are required")
    for arm, path in c["closed_confirmation_configurations"].items():
        source = read(path)
        summary = read(Path(source["output"]) / "summary.json")
        if (source.get("arm") != arm or source.get("seed") != 0
                or source.get("samples") != 9000000 or summary.get("run") != source["run"]):
            raise ValueError("Original native confirmation identity differs")
        closed[arm] = dict(summary, arm=arm, seed=source["seed"])
    require_confirmations(closed)
    source = read(c["source_configuration"])
    summary = read(Path(source["output"]) / "summary.json")
    if (c.get("authority") != AUTHORITY or c.get("budget_curve") is not True
            or c.get("descriptive_only") is not True or c.get("new_training") is not False
            or c.get("new_seeds") is not False or c.get("source_training_budget") != 9000000
            or c.get("layer") != 6 or c.get("representation") != "H0"
            or c.get("persist_features") is not False or c.get("readout_seed") != 0
            or c["samples"] not in points(source) or c.get("source_run") != source["run"]
            or c.get("source_scientific_binding") != source["d_recipe"]["scientific_binding"]
            or summary.get("run") != source["run"] or summary.get("samples") != 9000000
            or summary.get("status") != "COMPLETE" or summary.get("statistics_complete") is not True):
        raise ValueError("Only the original completed9M trajectory and registered L6/H0 point")
    if not source.get("molecule_scaling") and source["run"] != closed[source["arm"]]["run"]:
        raise ValueError("Native readout source differs from completed confirmation")
    if str(resolver(source, c["samples"])) != c["checkpoint"]:
        raise ValueError("Original checkpoint ancestry changed")
    return source


def run_gpu(c, *, evaluator=None, resolver=None, publish=None):
    if resolver is None:
        from tools.p_recipe.checkpoint_paths import evaluation_checkpoint as resolver
    validate_source(c, resolver=resolver)
    if evaluator is None:
        from .evaluate import run as evaluator
    if publish is None:
        from .train import publish_summary as publish
    output = Path(c["output"])
    path = output / "summary.json"
    previous = read(path) if path.exists() else None
    if previous is not None:
        if (previous.get("run") != c["run"] or previous.get("samples") != c["samples"]
                or previous.get("source_run") != c["source_run"]):
            raise ValueError("Existing readout summary belongs to a different source")
        if previous["status"] in (WAITING, "COMPLETE"):
            return previous
        raise ValueError("Inspect the existing incomplete producer before continuation")
    output.mkdir(parents=True, exist_ok=True)
    config_path = output / "configuration.json"
    if config_path.exists():
        original = read(config_path)
        keys = ("run", "samples", "source_run", "source_configuration", "checkpoint",
                "source_scientific_binding", "layer", "representation")
        if any(original.get(k) != c.get(k) for k in keys):
            raise ValueError("Existing partial readout scientific binding changed")
    else:
        publish(config_path, c, c)
    start = time.monotonic()
    predictions = output / "readout/predictions.json"
    # The original evaluator itself reuses completed task prediction files.
    if not predictions.exists():
        evaluator(dict(c, output=str(output / "readout")))
    manifest = read(predictions)
    if manifest.get("run") != c["run"] or manifest.get("samples") != c["samples"]:
        raise ValueError("Produced prediction manifest identity differs")
    seconds = time.monotonic() - start
    result = dict(run=c["run"], samples=c["samples"], source_run=c["source_run"],
        status=WAITING, statistics_complete=False, source_training_budget=9000000,
        training_performed=False, gpu_readout_seconds=seconds,
        training_and_gpu_readout_seconds=seconds, gpu_job_id=os.environ.get("SLURM_JOB_ID"),
        gpu_node=os.uname().nodename.split(".")[0], gpu_uuid=c["gpu_uuid"],
        predictions=str(predictions), descriptive_only=True)
    publish(path, result, c)
    return result


def finalize_cpu(c, *, execution_id, node, scorer=None, publish=None):
    from .shared_admission import atomic_json
    output = Path(c["output"])
    summary = read(output / "summary.json")
    if (not c.get("budget_curve") or summary.get("run") != c["run"]
            or summary.get("samples") != c["samples"]
            or summary.get("source_run") != c["source_run"]
            or summary.get("status") not in (WAITING, "COMPLETE")):
        raise ValueError("Original GPU readout must close with the same point and source")
    if summary.get("status") == "COMPLETE" and summary.get("statistics_complete") is True:
        return summary
    manifest_path = output / "readout/predictions.json"
    manifest = read(manifest_path)
    if manifest.get("run") != c["run"] or manifest.get("samples") != c["samples"]:
        raise ValueError("Prediction manifest belongs to a different point")
    if scorer is None:
        from .evaluate import existing_evaluator
        def scorer(configuration):
            with existing_evaluator() as module:
                module.score(manifest_path, configuration["reference_manifest"],
                             Path(__file__).resolve().parents[2] / "results/d_recipe/scores.csv")
    publish = atomic_json if publish is None else publish
    wall, cpu = time.monotonic(), time.process_time()
    target = output / "readout/scores.json"
    if not target.exists():
        scorer(c)
    scores = read(target)
    for name in ("R1", "R3"):
        value = scores.get(name, {})
        if (not value.get("complete") or value.get("bootstrap_samples") != 1000
                or value.get("bootstrap_defined") != 1000
                or value.get("paired_bootstrap", {}).get("seed") != 20261025):
            raise ValueError("Original retained molecular bootstrap is not complete")
    result = dict(summary, status="COMPLETE", statistics_complete=True,
        statistics_backend="ssh_cpu", statistics_execution_id=execution_id,
        statistics_node=node, statistics_completed_at=time.time(),
        statistics_wall_seconds=time.monotonic()-wall,
        statistics_process_CPU_seconds=time.process_time()-cpu)
    publish(output / "summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    args = parser.parse_args()
    c = read(args.configuration)
    if c.get("operation") != "budget_statistics":
        from .resources import execution_site, admit_output
        execution_site(c, cpu=False); admit_output(c, Path(c["output"]))
        result = run_gpu(c)
    else:
        import importlib.util
        import sys
        provider_path = Path(__file__).resolve().parents[3] / "MFM_p_recipe/tools/p_recipe/cpu_ssh_runtime.py"
        sys.path.insert(0, str(provider_path.parent))
        spec = importlib.util.spec_from_file_location("d_budget_statistics_provider", provider_path)
        provider = importlib.util.module_from_spec(spec); spec.loader.exec_module(provider)
        provider.verified_deadline(c)
        if os.environ.get("CUDA_VISIBLE_DEVICES"):
            raise ValueError("Budget statistics require a healthy CPU node without CUDA")
        from .shared_admission import admit
        candidate = read(c["candidate_configuration"])
        admit(c, [Path(candidate["output"]), Path(__file__).resolve().parents[2] / "results/d_recipe"])
        import torch
        torch.set_num_threads(1)
        result = finalize_cpu(candidate, execution_id=provider.execution_handle(), node=c["node"])
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()

