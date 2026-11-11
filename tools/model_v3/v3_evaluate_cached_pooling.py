"""Evaluate T0-2 using only the existing C1-0 H0 cache."""
import argparse
import json
from pathlib import Path
from v2_evaluate_s import RememberedStore
from phychem_mfm.phase1.v3_cached_pooling import evaluate_cached_pooling

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True)
    args = parser.parse_args()
    evaluate_cached_pooling(json.loads(Path(args.configuration).read_text()), store_factory=RememberedStore)
