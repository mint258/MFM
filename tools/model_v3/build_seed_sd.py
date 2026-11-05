#!/usr/bin/env python3
"""Build one externally preregistered seed-SD artifact; no experiment selection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).absolute().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--registration-sha256", required=True,
                        help="Independent fixed SHA from the preregistration review, never inferred from results")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT/"current"))
    from phychem_mfm.phase1.v3_decision_evidence import bound_json, build_global_seed_sd
    output = Path(args.output).absolute()
    if output.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Actual evidence products must stay outside the source tree")
    inputs = bound_json({"path": args.manifest, "sha256": args.manifest_sha256})
    artifact = build_global_seed_sd(inputs, expected_registration_sha256=args.registration_sha256)
    raw = (json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False)+"\n").encode()
    # Parent is deliberately not created on a failed evidence verification.
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(raw)
    print(json.dumps({"status": artifact["status"], "anchor_id": artifact["anchor_id"],
                      "sample_standard_deviation": artifact["sample_standard_deviation"], "frozen": False}))


if __name__ == "__main__":
    main()
