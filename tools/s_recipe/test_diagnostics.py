from types import SimpleNamespace

import torch
from torch_geometric.data import Batch, Data

from diagnostics import noise_statistics, relative_error


def test_zero_and_perfect_predictors_geometry_mask_and_target_sign():
    records = []
    for view_id in range(3):
        records.append(Data(pos=torch.tensor([[.1, -.2, .3], [.2, 0., -.1]]),
                            target_pos=torch.zeros(2, 3),
                            sample_type_id=torch.tensor([view_id])))
    batch = Batch.from_data_list(records)
    views = SimpleNamespace(batch=batch, base_graph_index=torch.tensor([0, 0, 0]))
    outputs = SimpleNamespace(node_mask=torch.ones(3, 2, 1, dtype=torch.bool),
                              noise_pred=torch.zeros(3, 2, 3))
    statistics = noise_statistics(outputs, views)
    assert statistics['atoms'] == 2
    assert relative_error(statistics) == 1.
    grouped = noise_statistics(outputs, views, group_labels=['sigma_0.1'])
    assert grouped['groups']['sigma_0.1']['atoms'] == statistics['atoms']
    assert relative_error(grouped['groups']['sigma_0.1']) == 1.
    outputs.noise_pred = torch.stack([record.pos for record in records])
    assert relative_error(noise_statistics(outputs, views)) == 0.
    outputs.noise_pred = -outputs.noise_pred
    assert relative_error(noise_statistics(outputs, views)) == 4.
