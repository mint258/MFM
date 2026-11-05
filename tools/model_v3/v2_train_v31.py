"""Execute one explicitly configured MFM4 development/grid experiment."""
import argparse
import json
from pathlib import Path
from phychem_mfm.phase1.v31_experiments import train_v31

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--configuration', required=True)
if __name__ == '__main__':
    args = parser.parse_args()
    train_v31(json.loads(Path(args.configuration).read_text()))
