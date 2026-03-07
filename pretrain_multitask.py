#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backward-compatible entrypoint for MFM multi-task pretraining."""

from pretrain.args import get_args
from pretrain.checkpoint import save_checkpoint
from pretrain.pipeline import main
from pretrain.train_loop import DummyScaler, run_epoch

__all__ = [
    "get_args",
    "run_epoch",
    "DummyScaler",
    "save_checkpoint",
    "main",
]


if __name__ == "__main__":
    main()
