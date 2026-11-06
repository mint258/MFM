"""Run the two actual M2 acceptance stages on delivered v3.1 data."""
import argparse
from phychem_mfm.phase1.v31_m2 import run_m2

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', required=True)
parser.add_argument('--training-view', required=True)
parser.add_argument('--normalizations', required=True,
                    help='Data-line D4 field mapping or published dataset/target routes; no fitted fallback')
parser.add_argument('--output', required=True)
parser.add_argument('--mode', choices=['overfit', 'sdp'], required=True)
parser.add_argument('--overfit-updates', type=int, default=10000)
parser.add_argument('--batch-size', type=int, default=8)
parser.add_argument('--seed', type=int, default=0)
parser.add_argument('--lr', type=float, default=3e-4)
if __name__ == '__main__':
    run_m2(**vars(parser.parse_args()))
