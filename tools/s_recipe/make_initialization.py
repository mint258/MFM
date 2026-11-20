"""Publish one random S initialization per authorized seed, without training."""
import argparse
from pathlib import Path

import torch

from phychem_mfm.phase1.v2_s_training import s_model
from phychem_mfm.phase1.p_recipe_handoff import publish_checkpoint


def make_initialization(seed, output):
    torch.set_num_threads(1)
    torch.manual_seed(seed)
    model, architecture = s_model('C1-0', 'three')
    publish_checkpoint(dict(schema='S_RECIPE_RANDOM_INITIALIZATION_V1', seed=seed,
                            model=model.state_dict(), architecture=architecture,
                            torch_rng=torch.get_rng_state(), training_samples=0), output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, choices=(0, 1), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Root creates seed1 only when the registered seed0 rule actually triggers.
    make_initialization(args.seed, args.output)
