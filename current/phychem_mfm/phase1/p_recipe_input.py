"""Ordered P batches prepared by CPU readers, with the original draw order."""
from copy import deepcopy
from collections import deque
from types import SimpleNamespace

import numpy as np
import torch

from .p_recipe_data import PRecipeDataset
from .v31_loader import collate_samples
from .v31_grouped_loss import prepare_v31_targets
from .v31_training import V31PDModel


class PreparedSamples(list):
    def __init__(self, samples, prepared):
        super().__init__(samples)
        self.prepared = prepared


def reader_metadata(model, fields, *, sync_free=False, async_transfer=False):
    return SimpleNamespace(registry=model.registry, head_by_name=model.head_by_name,
        selections=model.selections, definitions=model.definitions,
        view=SimpleNamespace(normalizations=model.view.normalizations),
        routes=model.routes, fields=fields, grouped_fields=model.grouped_fields,
        sync_free=sync_free, async_transfer=async_transfer, allow_onsite_fields=model.heads.allow_onsite_fields,
        _require_vector_normalization=V31PDModel._require_vector_normalization)


def init_prepared_reader(configuration, mean_labels, metadata, validation_configuration):
    global DATA, MEAN, META, VALIDATION_CONFIGURATION, VALIDATION
    torch.set_num_threads(1)
    DATA = PRecipeDataset(**configuration)
    MEAN, META = mean_labels, metadata
    VALIDATION_CONFIGURATION, VALIDATION = validation_configuration, None


def prepare_samples(samples, metadata, *, retain_samples=True):
    prepared = dict(clean_batch=collate_samples(samples))
    targets, affines, names = prepare_v31_targets(metadata, samples, ('P',), metadata.fields)
    prepared['loss_targets'] = dict(values=torch.cat([target.values.flatten() for target in targets.values()]),
        valid=torch.cat([target.valid for target in targets.values()]),
        layout=[(name,tuple(target.values.shape)) for name,target in targets.items()],affines=affines,names=names)
    pairs, pair_rows, observed, indices, scatter = {}, {}, {}, {}, {}
    shapes = {n: (sum(len(s['targets'][n].raw) for s in samples), samples[0]['targets'][n].raw.shape[-1])
              for n in metadata.fields}
    for route in sorted(set(metadata.routes[metadata.selections[n][0]] for n in metadata.fields)):
        names = [n for n in metadata.fields if metadata.routes[metadata.selections[n][0]] == route]
        selected = list(range(len(samples))) if route == 21 else [i for i, sample in enumerate(samples)
            if any(sample['targets'][n].valid.any() for n in names)]
        indices[route] = selected
        if not selected:
            continue
        working = [samples[i] for i in selected]
        if len(selected)!=len(samples):
            for name in names:
                lengths = [len(s['targets'][name].raw) for s in samples]
                offsets = np.r_[0, np.cumsum(lengths)]
                scatter[name] = torch.as_tensor(np.concatenate([np.arange(offsets[i], offsets[i+1]) for i in selected]))
        if route == 22:
            for sample in working:
                if sample['pos_perturbed'] is None or not np.isfinite(sample['pos_perturbed']).all():
                    raise ValueError('Observed perturbed label lacks its actual source geometry')
            source = [{**s, 'pos': s['pos_perturbed']} for s in working]
            prepared['perturbed_batch'] = collate_samples(source)
            batch = prepared['perturbed_batch']
        else:
            batch = prepared['clean_batch']
        physical = {}
        for name in names:
            head = metadata.selections[name][0]
            physical.setdefault(head, []).append(name)
            if metadata.head_by_name[head].level != 'pair':
                continue
            masks = [s['targets'][name].valid.any(-1) for s in working]
            pairs[head] = torch.cat([torch.as_tensor(s['targets'][name].pair_index[mask].T.copy(),
                dtype=torch.long)+batch.ptr[i] for i, (s, mask) in enumerate(zip(working, masks))], 1)
            mask = np.concatenate(masks)
            pair_rows[head] = (torch.as_tensor(np.flatnonzero(mask)), len(mask))
        observed[route] = {head for head, columns in physical.items() if any(
            np.concatenate([s['targets'][n].valid for n in columns], -1).all(-1).any() for s in working)}
    prepared.update(pairs=pairs, pair_rows=pair_rows, observed=observed, route_indices=indices,
                    shapes=shapes, scatter_rows=scatter)
    if getattr(metadata, 'sync_free', False):
        from ..model.perf_sync import prepare_layout
        for name in ('clean_batch', 'perturbed_batch'):
            if name in prepared:
                prepare_layout(prepared[name])
        for head, index in pairs.items():
            route = metadata.routes[head]
            batch = prepared['perturbed_batch' if route == 22 else 'clean_batch']
            if index.dtype != torch.long or index.ndim != 2 or index.shape[0] != 2:
                raise ValueError('Native pair index shape/domain differs')
            if not bool(((index >= 0) & (index < len(batch.batch))).all()):
                raise ValueError('Native pair index outside atom domain')
            if not bool((batch.batch[index[0]] == batch.batch[index[1]]).all()):
                raise ValueError('Pairs cross molecule boundaries')
            if head not in metadata.allow_onsite_fields and not bool((index[0] != index[1]).all()):
                raise ValueError('Onsite rows lack source permission')
    if getattr(metadata, 'async_transfer', False):
        from .perf_sync_transfer import share_tensors
        prepared = share_tensors(prepared)
    identities = [dict(molecule_index=s['molecule_index'],conformer_index=s['conformer_index']) for s in samples]
    return PreparedSamples(samples if retain_samples else identities, prepared)


def unpack_targets(packed):
    from .v3_contract import FieldTarget
    targets, value_cursor, valid_cursor = {}, 0, 0
    for name, (rows,width) in packed['layout']:
        targets[name] = FieldTarget(packed['values'][value_cursor:value_cursor+rows*width].view(rows,width),
                                   packed['valid'][valid_cursor:valid_cursor+rows])
        value_cursor += rows*width
        valid_cursor += rows
    return targets, packed['affines'], packed['names']


def draw_prepared_choices(state, count):
    rng = np.random.default_rng()
    rng.bit_generator.state = state
    choices = []
    for _ in range(count):
        molecule = int(rng.choice(DATA.indices))
        conformer = int(rng.choice(DATA.choices(molecule)))
        choices.append((molecule,conformer))
    return choices, deepcopy(rng.bit_generator.state)


def read_prepared_choices(choices):
    samples = []
    for molecule,conformer in choices:
        sample = DATA.read(molecule, conformer)
        if MEAN:
            sample['targets'] = DATA.molecule_mean(molecule)
        samples.append(sample)
    return prepare_samples(samples, META, retain_samples=not META.grouped_fields)


def read_prepared_validation(molecules):
    global VALIDATION
    if VALIDATION is None:
        VALIDATION = PRecipeDataset(**VALIDATION_CONFIGURATION)
    return prepare_samples([VALIDATION.read(m, int(VALIDATION.choices(m)[0])) for m in molecules], META)


def ordered_prepared_batches(pool, clock, rng, batch_size, stop_samples):
    planned = deepcopy(clock)
    planned_state = deepcopy(rng.bit_generator.state)
    pending = deque()

    def submit():
        nonlocal planned_state
        count = min(planned.max_next_samples(batch_size), stop_samples-planned.samples_consumed)
        if count <= 0:
            return
        choices, planned_state = pool.submit(draw_prepared_choices, planned_state, count).result()
        planned.advance(count)
        pending.append((pool.submit(read_prepared_choices, choices), planned_state))

    for _ in range(4):
        submit()
    while pending:
        future, state = pending.popleft()
        samples = future.result()
        submit()
        yield samples, state
