"""Small synthetic CPU tests for new fine-tune logic; no real model/label replay."""
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pytest
import torch
from torch import nn
from torch_geometric.data import Data

from finetune import (ContinuationRequired, configure_encoder, internal_split,
                      run_finetune)
from phychem_mfm.phase1.v3_dev_evaluation import TaskMolecule, TaskSpec


class TinyEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.backbone = nn.Module()
        self.backbone.atom_emb = nn.Embedding(3, 2)
        self.backbone.layers = nn.ModuleList(nn.Linear(2, 2) for _ in range(6))
        self.backbone.out_norm = nn.LayerNorm(2)

    def encode_atoms(self, batch):
        h = self.backbone.atom_emb(batch.x.reshape(-1))
        for layer in self.backbone.layers:
            h = torch.tanh(layer(h))
        return h  # synthetic network; source rows use this same exact transform


class Tracker:
    def __init__(self):
        self.updates = 0

    def log(self, row, *, step, commit):
        self.updates = max(self.updates, step)


def initial():
    with torch.random.fork_rng():
        torch.manual_seed(71)
        encoder = TinyEncoder().eval()
    geometries, rows = {}, []
    for i in range(8):
        uid = "record-"+str(i)
        sample = SimpleNamespace(x=torch.tensor([0, 1, 2]),
            pos=torch.zeros(3, 3), source_atom_ids=torch.arange(3))
        geometries[uid] = sample
        with torch.no_grad():
            h0 = encoder.encode_atoms(Data(x=sample.x.reshape(-1, 1))).detach().clone()
        rows.append(TaskMolecule("molecule-"+str(i), h0, sample.source_atom_ids,
            torch.tensor([i/10], dtype=torch.float64), torch.tensor([True]),
            torch.tensor([True]), uid))
    return encoder, tuple(rows[:6]), tuple(rows[6:]), geometries


def run(directory, tracker, should_stop, *, binding=None):
    encoder, train, validation, geometries = initial()
    task = TaskSpec("exp.LogD", "expansionrx", "LogD", "graph", "mae")
    return run_finetune(encoder, train, validation, geometries, task,
        mode="full", seed=0, n_ref=3, output=directory, tracker=tracker,
        should_stop=should_stop, source_binding=binding or {"checkpoint": "synthetic-source"},
        initial_architecture={"synthetic": True}, device="cpu")


def test_internal_holdout_is_molecular_and_preserves_duplicate_records():
    _, train, _, _ = initial()
    duplicate = TaskMolecule(train[0].molecule_uid, train[0].h0,
        train[0].source_atom_ids, train[0].targets, train[0].candidate_mask,
        train[0].supervision_mask, "second-native-record")
    fit, held = internal_split(train+(duplicate,))
    assert not {r.molecule_uid for r in fit} & {r.molecule_uid for r in held}
    assert len(fit)+len(held) == len(train)+1
    assert (duplicate in fit) == (train[0] in fit)


def test_top2_freezes_embeddings_first_four_layers_and_separate_output_norm():
    encoder, _, _, _ = initial()
    configure_encoder(encoder, "top2")
    active = {name for name, value in encoder.named_parameters() if value.requires_grad}
    assert active == {"backbone.layers."+str(i)+"."+p for i in (4, 5) for p in ("weight", "bias")}
    ids = torch.tensor([[0], [1], [2]])
    encoder.encode_atoms(Data(x=ids)).square().sum().backward()
    assert all(value.grad is None for name, value in encoder.named_parameters() if name not in active)
    assert all(value.grad is not None for name, value in encoder.named_parameters() if name in active)


def test_interrupted_complete_state_resume_matches_uninterrupted_training(tmp_path):
    old_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        direct, direct_detail = run(tmp_path/"direct", Tracker(), lambda: False)
        tracker = Tracker()
        with pytest.raises(ContinuationRequired):
            run(tmp_path/"resumed", tracker, lambda: tracker.updates >= 5)
        saved = torch.load(tmp_path/"resumed/complete_state.pt", weights_only=True)
        assert saved["updates"] == 5
        assert saved["optimizer"]["state"] and saved["shuffle_rng"].numel()
        resumed, resumed_detail = run(tmp_path/"resumed", Tracker(), lambda: False)
        assert np.array_equal(resumed.predictions, direct.predictions)
        assert resumed_detail["selected_epoch"] == direct_detail["selected_epoch"]
        assert resumed_detail["updates"] == direct_detail["updates"] == 50
        assert resumed_detail["evaluation_mae"] == direct_detail["evaluation_mae"]
        state = torch.load(tmp_path/"resumed/complete_state.pt", weights_only=True)
        assert state["epoch"] == 50 and all(g["lr"] == 0 for g in state["optimizer"]["param_groups"])
        with pytest.raises(ValueError, match="identity"):
            run(tmp_path/"resumed", Tracker(), lambda: False,
                binding={"checkpoint": "different-source"})
    finally:
        torch.set_num_threads(old_threads)