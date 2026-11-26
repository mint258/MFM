"""SSH transport for the existing D endpoint statistics and paired comparison.

The shared supervisor verifies the real CPU parent, affinity and deadline.
Original D finalization and P scoring functions retain the scientific gates.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


def run(transport):
    provider_path = Path("/share/home/zixiao/descriptor_analysis/MFM_p_recipe/tools/p_recipe/cpu_ssh_runtime.py")
    sys.path.insert(0, str(provider_path.parent))
    spec = importlib.util.spec_from_file_location("d_cpu_ssh_provider", provider_path)
    provider = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provider)
    provider.verified_deadline(transport)
    if os.environ.get("CUDA_VISIBLE_DEVICES"):
        raise RuntimeError("CPU endpoint statistics require no visible GPU")
    repository = Path(__file__).resolve().parents[2]
    c = json.loads(Path(transport["candidate_configuration"]).read_text())
    sys.path.insert(0, c.get("data_repository", str(repository.parent / "MFM_d_descriptors_20261120")))
    sys.path.insert(0, str(repository / "current"))
    from .shared_admission import admit, atomic_json
    paths = [Path(c["output"]), repository / "results/d_recipe"]
    if transport["operation"] == "compare":
        paths.append(Path(transport["comparison_output"]))
    admit(transport, paths)
    if transport["operation"] == "statistics":
        from .cpu_statistics import finalize
        from .evaluate import existing_evaluator

        def original_scorer(configuration):
            destination = repository / "results/d_recipe/scores.csv"
            with existing_evaluator() as evaluator:
                return evaluator.score(Path(configuration["output"]) / "predictions.json",
                                       configuration["reference_manifest"], destination)

        return finalize(c, scorer=original_scorer,
                        publish=lambda path, value, configuration: atomic_json(path, value))
    if transport["operation"] != "compare":
        raise ValueError("Only original endpoint statistics or paired comparison")
    output = Path(transport["comparison_output"]).resolve()
    if not output.is_relative_to(repository / "results/d_recipe"):
        raise ValueError("D paired comparisons belong in the original result scope")
    if output.exists():
        raise ValueError("Original comparison already published; reuse it without recomputing")
    from .compare import compare_runs
    from .train import closed_training_summary
    control = json.loads(Path(transport["control_configuration"]).read_text())
    # The original afterok chain becomes an actual successful terminal gate.
    for config in (c, control):
        summary = closed_training_summary(config)
        if summary is None or summary.get("status") != "COMPLETE":
            raise ValueError("Both original endpoint statistics must complete first")
    tasks = json.loads((repository / "configs/p_recipe/protocol.json").read_text())["scored_tasks"]
    result = compare_runs(c, control, expected_tasks=tasks)
    atomic_json(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    args = parser.parse_args()
    result = run(json.loads(Path(args.configuration).read_text()))
    print(json.dumps(result, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
