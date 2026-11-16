"""Run a preregistered S member of model-line taskbook v2 under Slurm."""
import argparse
from phychem_mfm.phase1.v2_s_training import train_s

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--index-path', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--distance-bias', choices=['C1-0', 'C1-a', 'C1-b'], default='C1-0')
parser.add_argument('--views', choices=['two', 'three'], default='three')
parser.add_argument('--seed', type=int, default=0)
parser.add_argument('--samples', type=int, default=6_000_000)
parser.add_argument('--batch-size', type=int, default=32)
parser.add_argument('--lr', type=float, default=3e-4)
parser.add_argument('--schedule', choices=['cosine', 'wsd'], default='cosine')
parser.add_argument('--clip', type=float, default=1.)
parser.add_argument('--workers', type=int, default=14)
parser.add_argument('--resume')
parser.add_argument('--microbatch-size', type=int, default=4)
if __name__ == '__main__':
    train_s(**vars(parser.parse_args()))
