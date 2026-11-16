"""Run selected-architecture S without replacing the original native proxy input."""
import argparse
import json
from pathlib import Path
from phychem_mfm.phase1.v3_selected_native_s import train_selected_native_s

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True)
    args = parser.parse_args()
    train_selected_native_s(json.loads(Path(args.configuration).read_text()))
