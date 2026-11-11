"""Run one explicitly configured taskbook-v3 latent experiment."""
import argparse
import json
from pathlib import Path
from phychem_mfm.phase1.v3_latent_training import train_latent

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True)
    args = parser.parse_args()
    train_latent(json.loads(Path(args.configuration).read_text()))
