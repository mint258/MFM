"""Bounded training-only development CV; never load final-test data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phychem_mfm.phase1.dev_probe import DEFAULT_TRAIN_CSV, load_phase1_probe_checkpoint, run_train_only_cv


def main():
    parser = argparse.ArgumentParser(description="DEV ONLY: frozen H0, fixed training-only three-fold CV")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--train-csv", default=str(DEFAULT_TRAIN_CSV))
    parser.add_argument("--cache-dir")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-molecules", type=int, default=192)
    parser.add_argument("--max-atoms", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--wandb-project", default="phychem-mfm-phase1-dev")
    args = parser.parse_args()
    model, metadata = load_phase1_probe_checkpoint(args.checkpoint, device=args.device)
    summary = run_train_only_cv(model, train_csv=args.train_csv, output_dir=args.output_dir,
                                cache_dir=args.cache_dir, max_molecules=args.max_molecules,
                                max_atoms=args.max_atoms, epochs=args.epochs, batch_size=args.batch_size,
                                seed=args.seed, device=args.device, project_root=PROJECT_ROOT,
                                model_metadata=metadata, wandb_project=args.wandb_project)
    print(json.dumps({"scope": summary["scope"], "status": summary["status"],
                      "wandb_run_id": summary["wandb_run_id"], "output_dir": args.output_dir,
                      "retained_unique_molecules": summary["data"]["retained_unique_molecules"],
                      "resources": summary["resources"]}, sort_keys=True))


if __name__ == "__main__":
    main()
