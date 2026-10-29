#!/usr/bin/env python3
"""Prepare a fifty-update C wiring successor from an actual admitted D3 pilot."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / "current"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-request", type=Path, required=True)
    parser.add_argument("--base-request-sha256", required=True)
    parser.add_argument("--trial", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    from phychem_mfm.phase1.v3_sample_budget_events import binding, require
    from phychem_mfm.phase1.v3_architecture_smoke import prepare_wiring_request
    reference = binding(args.base_request)
    require(reference["sha256"] == args.base_request_sha256, "Actual base request raw SHA required")
    require(not args.output.exists() and not args.output.resolve().is_relative_to(ROOT.resolve()),
            "Fresh outside-source output required")
    return prepare_wiring_request(reference, args.trial, args.output)


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True, allow_nan=False))
