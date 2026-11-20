"""Consume existing paired P-format scores under the D taskbook rules.

No prediction, resampling, training or job submission happens here. The CLI
runs on a CPU allocation and emits the required comparison result, not a new
receipt or an independent scientific audit.
"""
import argparse
import json
import os
from pathlib import Path
import platform

from .protocol import decide
from .training import ARMS


def paired_scores(candidate, control, *, expected_tasks):
    """Verify the pairing metadata carried by the existing bootstrap outputs."""
    tasks = tuple(expected_tasks)
    if len(tasks) != 7 or len(set(tasks)) != 7:
        raise ValueError("The registered primary score has exactly seven tasks")
    for score in (candidate, control):
        if (score.get("complete") is not True or score.get("bootstrap_samples") != 1000
                or score.get("bootstrap_defined") != 1000
                or score.get("bootstrap_unit") != "molecule"
                or score.get("bootstrap_seed") != 20261025):
            raise ValueError("Complete registered molecular bootstrap outputs are required")
        if (set(score.get("included_tasks", ())) != set(tasks)
                or len(score["included_tasks"]) != 7 or set(score.get("tasks", {})) != set(tasks)):
            raise ValueError("The R3 primary mean must cover the frozen seven tasks")
    a, b = candidate["paired_bootstrap"], control["paired_bootstrap"]
    for paired in (a, b):
        if (paired.get("seed"), paired.get("samples"), paired.get("confidence")) != (20261025, 1000, .95):
            raise ValueError("Use the registered seed, draws and percentile confidence")
        if not paired.get("groups"):
            raise ValueError("Original molecule pairing metadata is missing")
    if a["groups"] != b["groups"]:
        raise ValueError("Candidate/control bootstrap molecule groups differ")
    if candidate.get("architecture_sha256") != control.get("architecture_sha256"):
        raise ValueError("Random-reference architecture differs")
    return decide(candidate["mean_normalized_improvement"], control["mean_normalized_improvement"],
                  a["values"], b["values"])


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_runs(candidate_configuration, control_configuration, *, expected_tasks):
    a, b = candidate_configuration, control_configuration
    if any(c.get("condition") != "D" or c.get("arm") not in ARMS for c in (a, b)):
        raise ValueError("Only registered D runs enter D decisions")
    if a["seed"] != b["seed"] or a["seed"] not in (0, 1):
        raise ValueError("Candidate/control must share the same registered training seed")
    if a["samples"] != b["samples"] or a["samples"] not in (3000000, 9000000):
        raise ValueError("Compare matched registered 3M or 9M endpoints")
    if a["samples"] == 9000000 and a["seed"] != 0:
        raise ValueError("9M confirmation has seed0 only")
    scores, sources = [], []
    for c in (a, b):
        directory = Path(c["output"])
        stored = _load(directory / "configuration.json")
        for key in ("run", "condition", "arm", "seed", "samples", "source", "corpus"):
            if stored.get(key) != c.get(key):
                raise ValueError("Output belongs to a different requested condition: " + key)
        manifest = _load(directory / "readout/predictions.json")
        if manifest.get("run") != c["run"] or manifest.get("samples") != c["samples"]:
            raise ValueError("Readout belongs to a different run or sample endpoint")
        source = directory / "readout/scores.json"
        scores.append(_load(source))
        sources.append(str(source))
    primary = paired_scores(scores[0]["R3"], scores[1]["R3"], expected_tasks=expected_tasks)
    # R1 and CYP are reporting outputs of the unchanged evaluator; they never
    # authorize follow-up training or override the R3 primary decision.
    r1 = [{key: score.get("R1", {}).get(key) for key in
           ("mean_normalized_improvement", "bootstrap_ci", "included_tasks")}
          for score in scores]
    return {"candidate": a["run"], "control": b["run"], "seed": a["seed"],
            "samples": a["samples"], "primary": "mean_seven_task_R3_normalized_improvements",
            "R3": primary, "R1_report_only": {"candidate": r1[0], "control": r1[1]},
            "CYP_report_only": "existing evaluator task rows; excluded from primary mean",
            "score_sources": sources, "bootstrap_unit": "molecule", "bootstrap_draws": 1000,
            "bootstrap_seed": 20261025, "confidence": .95,
            "CI_scope": "molecule sampling uncertainty conditional on the fitted models",
            "multiple_comparison_correction": False, "resampling_repeated": False,
            "selection_change_allowed": a["samples"] == 3000000}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--control", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    node = platform.node().split(".")[0]
    if not os.environ.get("SLURM_JOB_ID") or not node.startswith("compute-0-") or not 8 <= int(node.rsplit("-", 1)[-1]) <= 19:
        raise RuntimeError("D statistics require an allocated CPU node 8-19")
    repository = Path(__file__).resolve().parents[2]
    tasks = _load(repository / "configs/p_recipe/protocol.json")["scored_tasks"]
    result = compare_runs(_load(arguments.candidate), _load(arguments.control), expected_tasks=tasks)
    output = Path(arguments.output).resolve()
    if not output.is_relative_to(repository / "results/d_recipe"):
        raise ValueError("D comparisons belong in this worktree's results/d_recipe")
    from workflows.data_d_descriptors.storage import guard
    guard(output.parent, 2**20)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, allow_nan=False))
