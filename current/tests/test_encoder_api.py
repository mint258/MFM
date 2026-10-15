import torch

from phychem_mfm.supervision import Objective


def test_encoder_and_output_shapes(small_model, mixed_real_batch):
    model = small_model.eval()
    batch = mixed_real_batch
    with torch.no_grad():
        h0 = model.encode_atoms(batch)
        graph = model.encode_graph(batch, pooling="mean")
        outputs = model.forward_pretrain(batch, Objective, include_task_repr=True)
    assert h0.shape == (batch.x.size(0), model.latent_dim)
    assert graph.shape == (batch.num_graphs, model.latent_dim)
    assert torch.equal(h0, outputs.atom_repr)
    assert outputs.energy_pred.shape == (batch.num_graphs, 1)
    assert outputs.charge_pred.shape[:2] == outputs.node_mask.shape[:2]
    assert outputs.element_logits.shape[-1] == model.n_atom_types
    assert outputs.coordinate_pred.shape[-1] == 3
    assert outputs.graph_descriptor_pred.shape[-1] == len(model.graph_descriptor_names)
    assert set(outputs.task_repr) == {"energy", "charge", "element", "geometry", "bond"}


def test_no_gate_fusion_or_moe_state(small_model):
    forbidden = ("gate", "fusion", "balance", "moe", "concat")
    lowered = [name.lower() for name in small_model.state_dict()]
    assert not any(token in name for name in lowered for token in forbidden)
