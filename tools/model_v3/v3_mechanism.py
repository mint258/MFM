"""Run taskbook-v3 report-only functional-group probes from closed caches."""
import argparse
import json
from pathlib import Path

from v2_evaluate_s import RememberedStore
from phychem_mfm.phase1.v3_mechanism import run

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True)
    args = parser.parse_args()
    run(json.loads(Path(args.configuration).read_text()), store_factory=RememberedStore)
