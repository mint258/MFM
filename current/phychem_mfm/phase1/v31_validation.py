"""Actual MFM4 validation with separate unseen/diagnostic populations."""
from __future__ import annotations

import numpy as np
import pyarrow.parquet as pq
import torch

from .v31_loader import collate_samples
from .v31_m2 import FieldMoments
from .v3_structural import build_structural_views, StructuralViewConfig
from .v3_architecture_views import build_two_structural_views
from ..training.losses import LossWeights


def validation_choices(dataset, ordinal_offset=0):
    """Stream existing ID metadata; source payload is read only for evaluation."""
    kind = 'P' if dataset.source == 'PM7' else 'U'
    file = pq.ParquetFile(dataset.directory/'id_map.parquet')
    ordinal = ordinal_offset
    cached_molecule, allowed = None, set()
    try:
        for batch in file.iter_batches(batch_size=8192, use_threads=False,
                columns=['record_kind','molecule_index','conformer_index','holdout']):
            for row in batch.to_pylist():
                current = ordinal
                ordinal += 1
                if (row['record_kind'] == kind and row['molecule_index'] in dataset._index_set
                        and bool(row['holdout']) == dataset.diagnostic):
                    if hasattr(dataset, 'choices'):
                        if cached_molecule != row['molecule_index']:
                            cached_molecule = row['molecule_index']
                            allowed = set(map(int, dataset.choices(cached_molecule)))
                        if row['conformer_index'] not in allowed:
                            continue
                    yield current, int(row['molecule_index']), int(row['conformer_index'])
    finally:
        file.close()


@torch.no_grad()
def validate_v31(populations, *, pd_model=None, structural_model=None, groups=('D','P'),
                 views='three', batch_size=4):
    """Each population gets its own losses, original-unit R²/MAE and counts.

    FULL or ROUTINE and TRAIN_UNSEEN_CONFORMATION are reported separately.
    These pretraining diagnostics never replace the TRAIN-only dev panel.
    """
    model = pd_model if pd_model is not None else structural_model
    device = next(model.parameters()).device
    states = [(m, m.training) for m in (pd_model, structural_model) if m is not None]
    for m, _ in states:
        m.eval()
    builder = build_two_structural_views if views == 'two' else build_structural_views
    pd_groups = tuple(g for g in groups if g != 'S')
    result, ordinal_offset = {}, 0
    try:
        for role, dataset in populations.items():
            moments, totals, counts, molecules = FieldMoments(), {}, {}, set()
            records, pending = 0, []
            def consume(selected):
                nonlocal records
                samples = [dataset.read(molecule, conformer) for ordinal,molecule,conformer in selected]
                molecules.update(molecule for ordinal,molecule,conformer in selected)
                records += len(samples)
                clean = collate_samples(samples)
                structural_prediction = None
                if 'S' in groups:
                    data = builder(clean, ordinals=tuple(row[0] for row in selected),
                        config=StructuralViewConfig(seed=0)).to(device)
                    structural_prediction = structural_model.forward_pretrain(data, enabled_groups=('S',))
                    loss = structural_model.compute_loss(structural_prediction, data, {}, {},
                        enabled_groups=('S',), weights=LossWeights())
                    accumulate(loss)
                if pd_groups:
                    prediction = pd_model.predict(samples, groups=pd_groups,
                        clean_features=None if structural_prediction is None else structural_prediction.clean_h0,
                        clean_batch=None if structural_prediction is None else clean.to(device))
                    loss = pd_model.loss(prediction, samples, groups=pd_groups)
                    accumulate(loss)
                    original = pd_model.original_predictions(prediction, samples)
                    for name, value in original.items():
                        moments.add(name, value.cpu().numpy(), np.concatenate([s['targets'][name].raw for s in samples]))
            def accumulate(loss):
                for name, value in loss.fields.items():
                    n = loss.counts[name]
                    totals[name] = totals.get(name, 0.) + float(value) * n
                    counts[name] = counts.get(name, 0) + n
            for row in validation_choices(dataset, ordinal_offset):
                pending.append(row)
                if len(pending) == batch_size:
                    consume(pending)
                    pending = []
            if pending:
                consume(pending)
            means = {name: total/counts[name] if counts[name] else None for name,total in totals.items()}
            fields = {row['field']: {k:v for k,v in row.items() if k not in ('field','passed')}
                      for row in moments.results()}
            result[role] = dict(records=records, molecules=len(molecules), field_losses=means,
                loss_observation_counts=counts, source_column_metrics=fields, selection_use=False,
                noise_component_RMSE_A=None if means.get('s_noise') is None else .1 * means['s_noise']**.5)
            # FULL and its ROUTINE subset keep the same source-row ordinals;
            # the following diagnostic population has a disjoint RNG namespace.
            ordinal_offset += pq.ParquetFile(dataset.directory/'id_map.parquet').metadata.num_rows
    finally:
        for m, was_training in states:
            m.train(was_training)
    return result
