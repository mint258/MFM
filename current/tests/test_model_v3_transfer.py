"""Custom batch transfer and label-isolation integration tests."""
import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization
from phychem_mfm.phase1.v3_data import V3Batch
from phychem_mfm.phase1.v3_losses import compute_v3_loss


def batch():
    graph = Batch.from_data_list([Data(x=torch.tensor([[5], [0]]), pos=torch.zeros(2, 3))])
    labels = {"p": FieldTarget(torch.tensor([[1.]]), torch.tensor([True])),
              "w": FieldTarget(torch.tensor([[2.]]), torch.tensor([True]), torch.tensor([[0], [1]]))}
    return V3Batch(graph, labels, (), torch.arange(2))


def test_transfer_uses_an_owned_graph_store_without_mutating_original():
    original = batch()
    transferred = original.to("cpu", non_blocking=True)
    assert transferred.encoder_batch is not original.encoder_batch
    assert torch.equal(transferred.encoder_batch.pos, original.encoder_batch.pos)
    assert torch.equal(transferred.targets["w"].pair_index, original.targets["w"].pair_index)
    transferred.encoder_batch.pos = torch.ones_like(transferred.encoder_batch.pos)
    assert torch.equal(original.encoder_batch.pos, torch.zeros(2, 3))


@pytest.mark.skipif(not torch.cuda.is_available(), reason="Actual pinned-memory transfer requires a visible CUDA device")
def test_custom_batch_pin_protocol_and_nonblocking_cuda_transfer():
    original = batch()
    pinned = original.pin_memory()
    assert pinned.encoder_batch.x.is_pinned() and pinned.encoder_batch.pos.is_pinned()
    assert pinned.source_atom_ids.is_pinned()
    assert all(value.values.is_pinned() and value.valid.is_pinned()
               and (value.pair_index is None or value.pair_index.is_pinned()) for value in pinned.targets.values())
    moved = pinned.to("cuda", non_blocking=True)
    torch.cuda.synchronize()
    assert moved.encoder_batch.x.device.type == "cuda"
    assert pinned.encoder_batch.x.device.type == "cpu"
    assert torch.equal(moved.targets["p"].values.cpu(), original.targets["p"].values)


def test_labels_cannot_carry_a_gradient_path_into_the_learner():
    reg = LabelRegistry((FieldSpec("p", "P", "a", "graph"),), "fixture", "a" * 64)
    target = FieldTarget(torch.ones(1, 1, requires_grad=True), torch.tensor([True]))
    normalizer = TrainNormalization((0.,), (1.,), "b" * 64, "fixture")
    with pytest.raises(ValueError, match="detached"):
        compute_v3_loss({"p": torch.zeros(1, 1, requires_grad=True)}, {"p": target}, reg,
                        {"p": normalizer}, enabled_groups=("P",))
