#!/usr/bin/env python3
"""Prepare source-bound C architecture proposals; never submit, admit or freeze."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / "current"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("resolve", "prepare", "repeat"))
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--inputs-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    from phychem_mfm.phase1.v3_architecture_readiness import resolve_inputs, prepare_trial
    from phychem_mfm.phase1.v3_decision_evidence import bound_json, digest
    from phychem_mfm.phase1.v3_decision_rules import registered_policy
    from phychem_mfm.phase1.v3_proxy_plan import PlannedTrial
    from phychem_mfm.phase1.v3_sample_budget_events import binding, write_once, require

    reference = binding(args.inputs)
    require(reference["sha256"] == digest(args.inputs_sha256),
            "Exact input manifest raw SHA required")
    manifest = bound_json(reference)
    if args.command == "resolve":
        required = {"policy", "policy_sha256", "resolution_inputs"}
    elif args.command == "repeat":
        required = {"policy", "policy_sha256", "first_seed_trials", "selected_name", "selection", "base_request"}
    else:
        required = {"policy", "policy_sha256", "trial", "base_request"}
    optional = set() if args.command == "resolve" else {"resolution_inputs"}
    require(type(manifest) is dict and required <= set(manifest) <= required | optional,
            "Only the declared architecture command inputs are accepted")
    require(not args.output.exists()
            and not args.output.resolve().is_relative_to(ROOT.resolve()),
            "Fresh outside-Git output required")
    policy = registered_policy(manifest["policy"], expected_sha256=manifest["policy_sha256"])

    if args.command == "resolve":
        result = resolve_inputs(manifest["resolution_inputs"], policy)
        result["input_manifest"] = reference
        return write_once(args.output, result)

    if args.command == "repeat":
        from phychem_mfm.phase1.v3_architecture_repeats import prepare_repeat
        resolutions = (resolve_inputs(manifest["resolution_inputs"], policy)
                       if "resolution_inputs" in manifest else {})
        return prepare_repeat(manifest["first_seed_trials"], manifest["selected_name"],
                              bound_json(manifest["base_request"]), resolutions, policy, args.output,
                              base_request_ref=manifest["base_request"], selection_reference=manifest["selection"])

    raw = manifest["trial"]
    require(type(raw) is dict and set(raw) == {
        "name", "stage", "condition", "pretraining_seed", "sample_budget", "parameters", "requires"}
        and type(raw["parameters"]) is list
        and all(type(pair) is list and len(pair) == 2 and type(pair[0]) is str
                for pair in raw["parameters"])
        and type(raw["requires"]) is list and all(type(item) is str for item in raw["requires"]),
        "Original complete PlannedTrial JSON transport required")
    trial = PlannedTrial(**{**raw, "parameters": tuple(tuple(pair) for pair in raw["parameters"]),
                           "requires": tuple(raw["requires"])})
    resolutions = (resolve_inputs(manifest["resolution_inputs"], policy)
                   if "resolution_inputs" in manifest else {})
    return prepare_trial(trial, bound_json(manifest["base_request"]), resolutions,
                         policy, args.output, base_request_ref=manifest["base_request"])


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True, allow_nan=False))
