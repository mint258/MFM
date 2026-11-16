"""Run one of the six taskbook-v3 report-only molecular finetunes."""
import argparse
import json
from pathlib import Path

from v2_evaluate_s import RememberedStore
from phychem_mfm.phase1.v3_finetuning import finetune

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True)
    args = parser.parse_args()
    finetune(json.loads(Path(args.configuration).read_text()), store_factory=RememberedStore)
