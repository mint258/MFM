"""Reuse P's frozen R1/R3 readouts and molecular bootstrap for D outputs."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform

from .training import ResultRoot


@contextmanager
def existing_evaluator(module=None):
    if module is None:
        from tools.p_recipe import evaluate as module
    original_root = module.REPO
    try:
        module.REPO = ResultRoot(Path(__file__).resolve().parents[2])
        yield module
    finally:
        module.REPO = original_root


def run(configuration, *, module=None):
    """GPU feature/readout pass only; CPU bootstrap is a separate command."""
    with existing_evaluator(module) as evaluator:
        return evaluator.run(configuration)


def score(configuration, *, module=None):
    """Use the existing predictions once; do not rerun an encoder or readout."""
    node = platform.node().split(".")[0]
    if not os.environ.get("SLURM_JOB_ID") or not node.startswith("compute-0-") or not 8 <= int(node.rsplit("-", 1)[-1]) <= 19:
        raise RuntimeError("D bootstrap/statistics require an allocated CPU node 8-19")
    destination = Path(__file__).resolve().parents[2] / "results/d_recipe/scores.csv"
    with existing_evaluator(module) as evaluator:
        return evaluator.score(Path(configuration["output"]) / "predictions.json",
                               configuration["reference_manifest"], destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "score"))
    parser.add_argument("--configuration", required=True)
    arguments = parser.parse_args()
    configuration = json.loads(Path(arguments.configuration).read_text())
    result = (run if arguments.command == "run" else score)(configuration)
    print(json.dumps(result))
