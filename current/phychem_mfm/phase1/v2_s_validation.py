"""Separate unseen-molecule and seen-molecule/unseen-conformer S readings."""
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path

import pyarrow.parquet as pq
import torch
from torch_geometric.data import Batch

from .v2_s_training import _worker_init, _read_native
from .v3_structural import build_structural_views, StructuralViewConfig
from .v3_architecture_views import build_two_structural_views
from ..training.losses import LossWeights


def validation_populations(rows, unseen):
    if unseen not in ('FULL', 'ROUTINE'):
        raise ValueError('Unseen population must be FULL or its ROUTINE subset')
    return {role: [(i, row) for i, row in enumerate(rows)
                   if (row['role'] == role if role != 'ROUTINE' else row['routine'])]
            for role in (unseen, 'TRAIN_UNSEEN_CONFORMATION')}


def validate_s(model, index_path, *, views='three', batch_size=32, workers=14, unseen='FULL'):
    table = pq.read_table(index_path)
    builder = build_two_structural_views if views == 'two' else build_structural_views
    repo = Path(__file__).absolute().parents[3]
    old_threads = torch.get_num_threads()
    was_training = model.training
    torch.set_num_threads(1)
    model.eval()
    results = {}
    try:
        with ProcessPoolExecutor(max_workers=workers,
                mp_context=multiprocessing.get_context('spawn'),
                initializer=_worker_init, initargs=(str(repo),)) as pool, torch.no_grad():
            for role, selected in validation_populations(table.to_pylist(), unseen).items():
                totals, counts = {}, {}
                for start in range(0, len(selected), batch_size):
                    batch_rows = selected[start:start + batch_size]
                    records = list(pool.map(_read_native, [row for _, row in batch_rows], chunksize=1))
                    data = builder(Batch.from_data_list(records),
                        ordinals=tuple(i for i, _ in batch_rows), config=StructuralViewConfig(seed=0)).to('cuda')
                    prediction = model.forward_pretrain(data, enabled_groups=('S',))
                    loss = model.compute_loss(prediction, data, {}, {}, enabled_groups=('S',),
                                              weights=LossWeights())
                    for field, value in loss.fields.items():
                        n = loss.counts[field]
                        totals[field] = totals.get(field, 0.) + float(value) * n
                        counts[field] = counts.get(field, 0) + n
                means = {field: total / counts[field] if counts[field] else None
                         for field, total in totals.items()}
                noise = means.get('s_noise')
                results[role] = dict(records=len(selected),
                    molecules=len({row['molecule_id'] for _, row in selected}),
                    field_losses=means, valid_counts=counts,
                    noise_component_RMSE_A=None if noise is None else .1 * noise ** .5,
                    selection_use=False)
    finally:
        torch.set_num_threads(old_threads)
        model.train(was_training)
    return results
