#!/usr/bin/env python3
"""Write a symbolic plan for review. Never submit or create a training run."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / "current"))
from phychem_mfm.phase1.v3_proxy_plan import (
    Evidence, architecture_plan, recipe_plan, plan_document)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("architecture", "recipe"), required=True)
    parser.add_argument("--sample-budget", type=int, required=True)
    parser.add_argument("--batch-base-samples", type=int, required=True)
    parser.add_argument("--budget-evidence", type=Path, required=True)
    parser.add_argument("--rules-evidence", type=Path, required=True)
    parser.add_argument("--selected-backbone", type=Path)
    parser.add_argument("--preregistration-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Fresh external output required")

    def evidence(path):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Ordinary closed evidence required")
        return Evidence(str(path.absolute()), hashlib.sha256(path.read_bytes()).hexdigest())

    parameters = dict(sample_budget=args.sample_budget, batch_base_samples=args.batch_base_samples,
        budget_evidence=evidence(args.budget_evidence), rules_evidence=evidence(args.rules_evidence))
    if args.kind == "recipe":
        if args.selected_backbone is None:
            raise ValueError("Recipe plan needs a closed architecture-selection reference")
        parameters["selected_backbone"] = evidence(args.selected_backbone)
        trials = recipe_plan(**parameters)
    else:
        if args.selected_backbone is not None:
            raise ValueError("Architecture candidates precede the selected-backbone evidence")
        trials = architecture_plan(**parameters)
    result = plan_document(trials, public_preregistration_sha=args.preregistration_sha)
    result["scope"] = "Symbolic metadata only; content hashes do not certify scientific acceptance of inputs"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False); stream.write("\n")
    print(json.dumps({"status": result["status"], "trials": result["trial_count"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
