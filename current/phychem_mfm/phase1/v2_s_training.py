"""Taskbook-v2 S experiments on the delivered D5 240k identity index.

Reuses the original native transport, structural views, S heads and loss.
No record hashes, extra smoke runs or downstream TEST access are performed.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import importlib.util
import json
import multiprocessing
from pathlib import Path
import pickle
import time

import numpy as np
import torch

from .v2_disk import save_checkpoint


class GroupedSIndex:
    def __init__(self, table):
        self.columns = table.to_pydict()
        mids = np.asarray(self.columns['molecule_id'])
        self.starts = np.r_[0, np.flatnonzero(mids[1:] != mids[:-1]) + 1]
        self.ends = np.r_[self.starts[1:], len(mids)]
        self.molecules = len(self.starts)

    def draw(self, rng, count):
        molecules = rng.integers(self.molecules, size=count)
        rows = [int(rng.integers(self.starts[m], self.ends[m])) for m in molecules]
        return [{name: self.columns[name][r] for name in
                 ('molecule_id', 'record_id', 'source_path', 'real_index', 'total_atoms')}
                for r in rows]


def _worker_init(repo):
    global _transport, _normalizer, _handles
    from .full_corpus_loader import _strict_normalizer
    torch.set_num_threads(1)
    path = Path(repo) / 'reproduction/linked_sources/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py'
    spec = importlib.util.spec_from_file_location('v2_original_native_transport', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _transport = module.transport_native_record
    _normalizer, _handles = _strict_normalizer(), {}


def _read_native(row):
    import lmdb
    path = row['source_path']
    if path not in _handles:
        _handles[path] = lmdb.open(path, subdir=Path(path).is_dir(), readonly=True,
                                   lock=False, readahead=False, create=False)
    with _handles[path].begin() as txn:
        payload = txn.get(f"{row['real_index']:09d}".encode())
    if payload is None:
        raise KeyError((path, row['real_index']))
    record = _transport(pickle.loads(payload), real_index=row['real_index'], normalizer=_normalizer)
    if len(record.x) != row['total_atoms']:
        raise ValueError('Native atom count differs from D5 identity join')
    return structural_record(record)


def structural_record(record):
    """Carry original S inputs only; descriptor '*index' names are not edges.

    Native records contain atom descriptor indices that PyG otherwise guesses
    are graph edges. None of those unused descriptors belongs in S collation.
    """
    from torch_geometric.data import Data
    from ..data.descriptor_schema import (BOND_INDEX_FIELD, BOND_ORDER_FIELD,
                                         BOND_STATUS_FIELD, BOND_FAIL_REASON_FIELD)
    result = Data(x=record.x, pos=record.pos)
    defaults = {BOND_INDEX_FIELD: torch.empty((2, 0), dtype=torch.long),
                BOND_ORDER_FIELD: torch.empty(0, dtype=torch.long),
                BOND_STATUS_FIELD: '', BOND_FAIL_REASON_FIELD: ''}
    for key, default in defaults.items():
        value = getattr(record, key, None)
        setattr(result, key, default if value is None else value)
    return result


def s_model(distance_bias, views):
    # Every real v3.1 entry uses the same existing S precision configuration.
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    from ..model.v3_architecture import build_architecture_model, ArchitectureOptions
    from ..model.v3_multiview import V3MultiViewModel
    from .v3_architecture_views import V3TwoViewModel
    from .v3_contract import FieldSpec, LabelRegistry
    from .v3_structural import StructuralFieldBinding
    configuration = {'architecture': {'preset': 'shared_light'},
        'backbone': {'n_atom_types': 119, 'dim': 512, 'layers': 6, 'heads': 8,
            'ff_mult': 2, 'use_radius_mask': False, 'radius': 8.,
            'distance_bias_projection_bias': False, 'activation_checkpointing': False},
        'head': {'profile': 'phase1', 'geometry_head': 'equivariant_noise'}}
    # Reuse the measured original tiled S builder directly. Its historical
    # public module identity is used by the existing bias-free C validation.
    import sys
    name = 'model_v3_architecture_s_memory_170a7752bad1812d'
    if name not in sys.modules:
        path = Path(__file__).absolute().parents[3] / 'workflows/sprime_s/scripts/s_model_memory_v1.py'
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    encoder = build_architecture_model(configuration, ArchitectureOptions(distance_bias=distance_bias),
        legacy_builder=sys.modules[name].build_memory_bounded_model)
    from ..model.v3_performance import ConfigurableDenoisingHead
    encoder.geometry_head = ConfigurableDenoisingHead(encoder.geometry_head, activation_checkpointing=False)
    fields = (FieldSpec('s_element', 'S', 'structural', 'atom', kind='classification', classes=119,
                        unit='element_class'),
              FieldSpec('s_noise', 'S', 'structural', 'atom', kind='denoise_eps_mse',
                        representation='vector', unit='angstrom'),
              FieldSpec('s_bond', 'S', 'structural', 'pair', kind='classification', classes=5,
                        unit='bond_order_class'))
    # Existing published D5 identity reference; no content digest is recomputed.
    registry = LabelRegistry(fields, 'D5_OLD_COMPLETE_FROZEN_RANDOM_20261029_V1',
        '6026f3267b3c56472dcf1b6239efd4e139e133ea641947d04c2bc70438734a33', 'data_line')
    binding = StructuralFieldBinding('s_element', 's_noise', 's_bond')
    cls = V3TwoViewModel if views == 'two' else V3MultiViewModel
    return cls(encoder, None, registry, binding), configuration


def sample_lr_ratio(consumed, budget, schedule):
    from math import cos, pi
    warmup = int(budget * .02)
    if consumed < warmup:
        return consumed / warmup
    begin = int(budget * .8) if schedule == 'wsd' else warmup
    if consumed < begin:
        return 1.
    progress = (consumed - begin) / (budget - begin)
    return 1. - progress if schedule == 'wsd' else .5 * (1. + cos(pi * progress))


def structural_observation_counts(model, views):
    """Count the original S targets on CPU, without a backbone/head forward.

    Bond selection reuses the original positive-edge selector, including its
    status, endpoint and class rules. The view builder preserves real atoms;
    counts therefore need no padded encoder output or prediction values.
    """
    batch = views.batch
    if batch.x.device.type != 'cpu' or not views.includes_structural:
        raise ValueError('Count original structural CPU views before device transfer')
    encoder, binding = model.encoder, model.structural_binding
    source_types = batch.sample_type_id.reshape(-1)[batch.batch]
    base_graph = views.base_graph_index[batch.batch]
    target = batch.target_x[:, 0]
    legal = (torch.isfinite(target) & target.eq(target.float().floor())
             & target.ge(0) & target.lt(encoder.n_atom_types - 1))
    element = ((source_types.eq(2) | source_types.eq(3)) & legal
        & batch.element_corrupt_mask.reshape(-1).gt(.5)
        & views.graph_eligibility['element'][base_graph])
    noise = ((source_types.eq(1) | source_types.eq(3))
        & torch.isfinite(batch.target_pos).all(-1)
        & views.graph_eligibility['noise'][base_graph])
    bond = encoder._phase1_positive_bond_pairs(batch, batch.batch)
    bond_keep = (views.graph_eligibility['bond'][views.base_graph_index[bond.pair_graph_index]]
        & bond.order_target.ge(0) & bond.order_target.lt(5))
    return {binding.element: int(element.sum()), binding.noise: int(noise.sum()),
            binding.bond: int(bond_keep.sum())}


def train_s(*, index_path, output, distance_bias='C1-0', views='three', seed=0,
            samples=6_000_000, batch_size=32, lr=3e-4, schedule='cosine', clip=1., workers=14,
            resume=None, microbatch_size=None):
    import pyarrow.parquet as pq
    from torch_geometric.data import Batch
    from .v3_structural import build_structural_views, StructuralViewConfig
    from .v3_architecture_views import build_two_structural_views
    from .v3_training import SampleClock
    from ..training.losses import LossWeights
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    index = GroupedSIndex(pq.read_table(index_path))
    if index.molecules != 240_000:
        raise ValueError('Scientific proxy requires the full delivered 240k TRAIN subset')
    rng = np.random.default_rng(seed)
    repo = Path(__file__).absolute().parents[3]
    # Start CPU workers before any CUDA use.
    pool = ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
                               initializer=_worker_init, initargs=(str(repo),))
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model, configuration = s_model(distance_bias, views)
    model = model.cuda().train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, betas=(.9, .95))
    def set_lr(consumed):
        ratio = sample_lr_ratio(consumed, samples, schedule)
        for group in optimizer.param_groups:
            group['lr'] = lr * ratio
    set_lr(0)
    clock = SampleClock(samples)
    config = StructuralViewConfig(seed=seed)
    builder = build_two_structural_views if views == 'two' else build_structural_views
    started = time.monotonic()
    gradients = []
    trial = dict(distance_bias=distance_bias, views=views, seed=seed, samples=samples,
                 batch_size=batch_size, lr=lr, betas=[.9, .95], schedule=schedule, clip=clip,
                 D5_index=str(index_path), model=configuration, TRAIN_molecules=index.molecules)
    if microbatch_size is not None and not 0 < microbatch_size <= batch_size:
        raise ValueError('Microbatch size must be between one and B0')
    if resume is not None:
        checkpoint = torch.load(resume, map_location='cpu', weights_only=True)
        if checkpoint['configuration'] != trial:
            raise ValueError('Resume configuration differs from the original experiment')
        model.load_state_dict(checkpoint['model'])
        optimizer.load_state_dict(checkpoint['optimizer'])
        clock.load_state_dict(checkpoint['clock'])
        rng.bit_generator.state = checkpoint['rng']
        torch.set_rng_state(checkpoint['torch_rng'])
        torch.cuda.set_rng_state(checkpoint['cuda_rng'])
        set_lr(clock.samples_consumed)
    (output / 'configuration.json').write_text(json.dumps(trial, indent=2) + '\n')
    (output / 'execution.json').write_text(json.dumps({'microbatch_size': microbatch_size,
        'effective_batch_size': batch_size, 'field_count_weighted_accumulation': microbatch_size is not None}, indent=2) + '\n')
    try:
        with (output / 'losses.csv').open('w', buffering=1) as log:
            log.write('samples,updates,total,element,noise,bond,preclip_norm,lr,seconds\n')
            while clock.samples_consumed < samples:
                count = clock.max_next_samples(batch_size)
                selected = index.draw(rng, count)
                records = list(pool.map(_read_native, selected, chunksize=1))
                clean = Batch.from_data_list(records)
                ordinals = tuple(range(clock.samples_consumed, clock.samples_consumed + count))
                if microbatch_size is None:
                    view = builder(clean, ordinals=ordinals, config=config).to('cuda')
                optimizer.zero_grad(set_to_none=True)
                if microbatch_size is None:
                    prediction = model.forward_pretrain(view, enabled_groups=('S',))
                    loss = model.compute_loss(prediction, view, {}, {}, enabled_groups=('S',),
                        weights=LossWeights(), exposure_step=clock.optimizer_updates)
                    loss.total.backward()
                else:
                    loss = accumulated_s_backward(model, records, ordinals, builder, config,
                        microbatch_size, clock.optimizer_updates,
                        count_observations=structural_observation_counts)
                norm = torch.nn.utils.clip_grad_norm_(model.parameters(), clip)
                optimizer.step()
                clock.advance(count)
                set_lr(clock.samples_consumed)
                gradients.append(float(norm))
                fields = loss.fields
                log.write(f'{clock.samples_consumed},{clock.optimizer_updates},{float(loss.total)},'
                    f'{float(fields["s_element"])},{float(fields["s_noise"])},'
                    f'{float(fields["s_bond"])},{float(norm)},'
                    f'{optimizer.param_groups[0]["lr"]},{time.monotonic()-started}\n')
                if (clock.samples_consumed in clock.milestones or clock.samples_consumed == samples
                        or clock.optimizer_updates % 1000 == 0):
                    payload = dict(model=model.state_dict(), optimizer=optimizer.state_dict(),
                        configuration=trial, clock=clock.state_dict(), rng=rng.bit_generator.state,
                        torch_rng=torch.get_rng_state(), cuda_rng=torch.cuda.get_rng_state())
                    if clock.samples_consumed in clock.milestones or clock.samples_consumed == samples:
                        save_checkpoint(payload, output / f'samples_{clock.samples_consumed}.pt')
                    else:
                        # Update this run's rolling recovery state; milestone
                        # and historical failed-run artifacts remain separate.
                        save_checkpoint(payload, output / 'recovery_next.pt')
                        (output / 'recovery_next.pt').replace(output / 'recovery.pt')
                if clock.optimizer_updates % 100 == 0:
                    print(f'samples={clock.samples_consumed} loss={float(loss.total):.7f}', flush=True)
        summary = {**trial, 'status': 'TRAINING_COMPLETE_DEV_EVALUATION_PENDING',
            'samples': clock.samples_consumed, 'updates': clock.optimizer_updates,
            'seconds': time.monotonic()-started,
            'preclip_gradient_p99': float(np.quantile(gradients, .99)),
            'gpu_peak_bytes': torch.cuda.max_memory_allocated()}
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def accumulated_s_backward(model, records, ordinals, builder, config, microbatch_size, exposure_step,
                           *, count_observations=None):
    """Exact field-observation means across microbatches, with one B0 update.

    Native training counts masks/positive edges on CPU without a model pass.
    Custom callers may retain the original no-grad count fallback. Restoring
    RNG keeps that fallback's stochastic choices. Views are built once on CPU.
    """
    from torch_geometric.data import Batch
    from .v3_losses import V3LossResult
    from ..training.losses import LossWeights
    views = [builder(Batch.from_data_list(records[start:start + microbatch_size]),
                     ordinals=ordinals[start:start + microbatch_size], config=config)
             for start in range(0, len(records), microbatch_size)]
    device = next(model.parameters()).device
    cpu_rng = torch.get_rng_state()
    cuda_rng = torch.cuda.get_rng_state(device) if device.type == 'cuda' else None
    counts = {}
    with torch.no_grad():
        for source in views:
            if count_observations is not None:
                for name, count in count_observations(model, source).items():
                    counts[name] = counts.get(name, 0) + count
                continue
            view = source.to(device)
            prediction = model.forward_pretrain(view, enabled_groups=('S',))
            loss = model.compute_loss(prediction, view, {}, {}, enabled_groups=('S',),
                weights=LossWeights(), exposure_step=exposure_step)
            for name, count in loss.counts.items():
                counts[name] = counts.get(name, 0) + count
            del prediction, loss, view
    torch.set_rng_state(cpu_rng)
    if cuda_rng is not None:
        torch.cuda.set_rng_state(cuda_rng, device)
    active = sum(n > 0 for n in counts.values())
    values = {name: torch.zeros((), device=device) for name in counts}
    for source in views:
        view = source.to(device)
        prediction = model.forward_pretrain(view, enabled_groups=('S',))
        loss = model.compute_loss(prediction, view, {}, {}, enabled_groups=('S',),
            weights=LossWeights(), exposure_step=exposure_step)
        total = loss.total.new_zeros(())
        for name, value in loss.fields.items():
            if counts[name]:
                weighted = value * (loss.counts[name] / counts[name])
                values[name] += weighted.detach()
                total = total + weighted / active
        total.backward()
        del prediction, loss, total, view
    total = torch.stack([values[name] for name, n in counts.items() if n]).mean()
    return V3LossResult(total, values, {'S': total}, counts, {'S': active}, ('S',))
