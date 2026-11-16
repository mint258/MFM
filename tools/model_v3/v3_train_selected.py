"""Run an explicitly registered selected-architecture development segment."""
import argparse
import json
from pathlib import Path
from phychem_mfm.phase1.v3_selected_training import train_selected

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True)
    args = parser.parse_args()
    train_selected(json.loads(Path(args.configuration).read_text()))
