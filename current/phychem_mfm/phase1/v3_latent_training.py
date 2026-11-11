"""Taskbook-v3 paired continuations and genuine fresh S/P confirmations."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import csv
import json
import multiprocessing
import os
from pathlib import Path
import time

import numpy as np
import torch

from .v2_disk import save_checkpoint, save_metadata_json
from .v2_s_training import (GroupedSIndex, _worker_init, _read_native, s_model,
                            sample_lr_ratio)
from .v3_training import SampleClock


def latent_configuration(c):
    """Allow only the arms and scientific clocks explicitly present in v3."""
    stage, arm = c['stage'], c['arm']
    t0 = {'T0-3': 'pma', 'T0-4': 'lite_rec'}
    t1 = {'A0': 'none', 'A1': 'pma', 'A2': 'lite', 'A3': 'lite_rec', 'A4': 'dense_addon'}
    allowed = t0 if stage == 'T0' else (t1 if stage == 'T1' else {'A1': 'pma', 'A3': 'lite_rec'})
    if stage not in ('T0', 'T1', 'T2') or arm not in allowed:
        raise ValueError('Use a specified T0/T1 arm or adopted T2 A1/A3')
    if stage == 'T2' and c.get('adopted_option') != allowed[arm]:
        raise ValueError('Fresh confirmation requires the actual provisional adoption')
    if c['seed'] != 0 or c['batch_size'] != 32:
        raise ValueError('The latent experiment uses seed0 and effective B32')
    kind = allowed[arm]
    specification = dict(c['latent_spec'], kind=kind)
    specification['write_back'] = stage != 'T0' and kind in ('lite', 'lite_rec')
    specification['reconstruction'] = (kind == 'lite_rec' or
        (stage == 'T0' and arm == 'T0-3' and c['condition'] == 'S'))
    expected = {'T0': (500_000, 3e-4), 'T1': (1_500_000, 1e-4),
                'T2': (6_000_000, 3e-4)}[stage]
    if (c['samples'], c['lr']) != expected or c['clip'] != 1.:
        raise ValueError('Keep the taskbook stage budget, learning rate and clipping')
    pair = (specification.get('reconstruction_weight', .1), specification.get('k', 8))
    if pair not in ((.1, 8), (.3, 8), (.1, 16)) or (pair != (.1, 8) and kind != 'lite_rec'):
        raise ValueError('Only the default and two taskbook lambda/k settings are allowed')
    return kind, specification


def initialization_source(c):
    """Fresh training reads recipe metadata only, never original model/RNG weights."""
    if c['stage'] == 'T2':
        if c.get('initialize_from') is not None or c.get('resume') is not None:
            raise ValueError('Fresh confirmation cannot inherit a checkpoint or sample clock')
        previous = json.loads(Path(c['recipe_from']).read_text())
        for name in ('distance_bias', 'views', 'seed', 'samples', 'batch_size', 'lr', 'clip'):
            if previous[name] != c[name]:
                raise ValueError('Fresh confirmation must retain the original C1 recipe: ' + name)
        if previous['schedule'] != 'cosine':
            raise ValueError('Keep the original C1 cosine schedule')
        return None, previous
    checkpoint = torch.load(c['initialize_from'], map_location='cpu', weights_only=True)
    return checkpoint, checkpoint['configuration']


def source_rng(checkpoint, seed):
    rng = np.random.default_rng(seed)
    if checkpoint is None:
        return rng, 0, 0
    rng.bit_generator.state = checkpoint['rng']
    torch.set_rng_state(checkpoint['torch_rng'])
    torch.cuda.set_rng_state(checkpoint['cuda_rng'])
    base = checkpoint['clock']['samples_consumed']
    if base != 6_000_000:
        raise ValueError('Paired continuation requires the original6M sample clock')
    return rng, base, checkpoint['clock']['optimizer_updates']


def load_initial_weights(model, checkpoint):
    """Load the existing body/heads; only the expressly new latent may be absent."""
    result = model.load_state_dict(checkpoint['model'], strict=False)
    if result.unexpected_keys or any(not name.startswith('encoder.latent_module.')
                                    for name in result.missing_keys):
        raise ValueError('Continuation must retain every existing body/head weight')


def reconstruction_from_clean(module, projected, batch, teacher):
    from torch_geometric.utils import to_dense_batch
    target, mask = to_dense_batch(teacher, batch.batch)
    pos, _ = to_dense_batch(batch.pos, batch.batch)
    elements = batch.x[:, 0] if batch.x.ndim == 2 else batch.x
    elements, _ = to_dense_batch(elements, batch.batch)
    return module.reconstruction_loss(projected, elements, pos, mask, target)


class TrainingHistory:
    """One real offline SDK execution, raw losses, fixed means and native stats."""
    def __init__(self, output, configuration, *, initial_samples=0):
        import wandb
        root = output / 'offline_wandb' / os.environ.get('SLURM_JOB_ID', str(os.getpid()))
        root.mkdir(parents=True, exist_ok=False)
        for suffix in ('cache', 'config', 'data'):
            path = root / suffix
            path.mkdir()
            os.environ['WANDB_' + suffix.upper() + '_DIR'] = str(path)
        repo = Path(__file__).absolute().parents[3]
        revision = (repo / '.git/HEAD').read_text().strip()
        if revision.startswith('ref: '):
            revision = (repo / '.git' / revision[5:]).read_text().strip()
        recorded = dict(configuration, source_revision=revision,
            slurm_job_id=os.environ.get('SLURM_JOB_ID'),
            node=os.environ.get('SLURMD_NODENAME'), visible_gpu=os.environ.get('CUDA_VISIBLE_DEVICES'))
        devices = [torch.cuda.current_device()] if torch.cuda.is_initialized() else []
        with torch.random.fork_rng(devices=devices):
            self.run = wandb.init(project='MFM-model-v3', name=output.name, mode='offline',
                dir=str(root), config=recorded,
                settings=wandb.Settings(x_stats_sampling_interval=30))
        if self.run is None or self.run.disabled:
            raise RuntimeError('A genuine offline W&B SDK execution is required')
        self.root, self.output = root, output
        self.stream = (root / 'training_history.jsonl').open('x', buffering=1)
        self.window = []
        self.next_boundary = (initial_samples // 100_000 + 1) * 100_000

    def log(self, row):
        self.window.append(row['total'])
        payload = dict(row)
        if len(self.window) == 1000:
            payload['loss_mean_1000_updates'] = sum(self.window) / 1000
            self.window.clear()
        self.stream.write(json.dumps(payload) + '\n')
        self.run.log(payload, step=row['updates'])
        if row['samples'] >= self.next_boundary:
            directory = self.root / 'snapshots'
            directory.mkdir(exist_ok=True)
            while row['samples'] >= self.next_boundary:
                path = directory / (str(self.next_boundary) + '.json')
                save_metadata_json(dict(boundary_samples=self.next_boundary, metrics=payload,
                    output=str(self.output), wandb_run_id=self.run.id,
                    synchronization='OFFLINE_UNSYNCED'), path)
                self.run.save(str(path), base_path=str(self.root), policy='now')
                self.next_boundary += 100_000

    def close(self, success):
        self.stream.close()
        self.run.finish(exit_code=0 if success else 1)
        save_metadata_json(dict(sdk_finished=True, success=success), self.root / 'sdk_finished.json')


def train_native_s(c):
    """The real first run is wiring acceptance; there is no model smoke run."""
    import pyarrow.parquet as pq
    from torch_geometric.data import Batch
    from .v3_structural import build_structural_views, StructuralViewConfig
    from .v3_architecture_views import build_two_structural_views
    from ..training.losses import LossWeights
    kind, specification = latent_configuration(c)
    checkpoint, previous = initialization_source(c)
    if (previous['distance_bias'], previous['views'], previous['samples'], previous['batch_size']) != (
            c['distance_bias'], c['views'], 6_000_000, 32):
        raise ValueError('Continue the selected original C1 six-million S checkpoint')
    index = GroupedSIndex(pq.read_table(c['index_path']))
    if index.molecules != 240_000 or str(c['index_path']) != previous['D5_index']:
        raise ValueError('Keep the exact original native240k S source')
    output = Path(c['output'])
    output.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(c['seed'])
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model, architecture = s_model(c['distance_bias'], c['views'], latent=kind,
                                  latent_config=specification if kind != 'none' else None)
    if checkpoint is not None:
        load_initial_weights(model, checkpoint)
    if c['stage'] == 'T0':
        for name, parameter in model.named_parameters():
            parameter.requires_grad_(name.startswith('encoder.latent_module.'))
    parameters = [p for p in model.parameters() if p.requires_grad]
    counts = dict(total_parameters=sum(p.numel() for p in model.parameters()),
                  trainable_parameters=sum(p.numel() for p in parameters))
    module = getattr(model.encoder, 'latent_module', None)
    if module is not None and hasattr(module, 'parameter_match'):
        counts['dense_module_matching'] = module.parameter_match
    save_metadata_json(c, output / 'configuration.json')
    save_metadata_json(architecture, output / 'architecture.json')
    save_metadata_json(counts, output / 'parameter_counts.json')
    history = TrainingHistory(output, c)
    repo = Path(__file__).absolute().parents[3]
    pool = ProcessPoolExecutor(max_workers=c['workers'],
        mp_context=multiprocessing.get_context('spawn'), initializer=_worker_init, initargs=(str(repo),))
    model = model.cuda().train()
    optimizer = torch.optim.AdamW(parameters, lr=c['lr'], betas=(.9, .95))
    # T0/T1 inherit only source draw/RNG; T2 starts its real sample/update clock at zero.
    rng, base_samples, base_updates = source_rng(checkpoint, c['seed'])
    clock = SampleClock(c['samples'])
    view_config = StructuralViewConfig(seed=c['seed'])
    builder = build_two_structural_views if c['views'] == 'two' else build_structural_views
    gradients, started, success = [], time.monotonic(), False
    try:
        with (output / 'losses.csv').open('x', buffering=1) as log:
            writer = csv.DictWriter(log, fieldnames=('samples', 'updates', 'total', 'S', 'rec',
                'preclip_norm', 'lr', 'seconds', 'cumulative_samples', 'gpu_peak_bytes'))
            writer.writeheader()
            from .v31_prefetch import ordered_sample_batches
            for records, consumed_rng in ordered_sample_batches(pool, _read_native, index,
                    clock, rng, 32, c['samples'], draw=index.draw):
                count = len(records)
                clean = Batch.from_data_list(records)
                optimizer.zero_grad(set_to_none=True)
                structural = torch.zeros((), device='cuda')
                rec = structural
                if c['stage'] == 'T0':
                    clean = clean.to('cuda')
                    h0 = model.encoder.encode_atoms(clean)
                    projected = module.last_projected_latent
                else:
                    ordinals = tuple(range(base_samples + clock.samples_consumed,
                                           base_samples + clock.samples_consumed + count))
                    views = builder(clean, ordinals=ordinals, config=view_config).to('cuda')
                    prediction = model.forward_pretrain(views, enabled_groups=('S',))
                    loss = model.compute_loss(prediction, views, {}, {}, enabled_groups=('S',),
                        weights=LossWeights(), exposure_step=base_updates + clock.optimizer_updates)
                    structural = loss.total
                    h0 = prediction.clean_h0
                    projected = (None if module is None or getattr(module, 'decoder', None) is None else
                                 module.last_projected_latent[views.clean_graph_rows])
                    clean = clean.to('cuda')
                if module is not None and getattr(module, 'decoder', None) is not None:
                    rec = reconstruction_from_clean(module, projected, clean, h0)
                total = rec if c['stage'] == 'T0' else structural + specification['reconstruction_weight'] * rec
                lr = c['lr'] * sample_lr_ratio(clock.samples_consumed, c['samples'], 'cosine')
                for group in optimizer.param_groups:
                    group['lr'] = lr
                total.backward()
                norm = torch.nn.utils.clip_grad_norm_(parameters, 1., error_if_nonfinite=True)
                optimizer.step()
                clock.advance(count)
                rng.bit_generator.state = consumed_rng
                gradients.append(float(norm))
                row = dict(samples=clock.samples_consumed, updates=clock.optimizer_updates,
                    total=float(total), S=float(structural), rec=float(rec), preclip_norm=float(norm),
                    lr=lr, seconds=time.monotonic()-started,
                    cumulative_samples=base_samples+clock.samples_consumed,
                    gpu_peak_bytes=torch.cuda.max_memory_allocated())
                writer.writerow(row)
                history.log(row)
                if clock.optimizer_updates % 100 == 0:
                    print(json.dumps(row), flush=True)
                if (clock.samples_consumed in clock.milestones or clock.samples_consumed == c['samples']
                        or clock.optimizer_updates % 1000 == 0):
                    payload = dict(model=model.state_dict(), optimizer=optimizer.state_dict(),
                        configuration=c, architecture=architecture, clock=clock.state_dict(),
                        original_samples=base_samples, rng=rng.bit_generator.state,
                        torch_rng=torch.get_rng_state(), cuda_rng=torch.cuda.get_rng_state())
                    milestone = clock.samples_consumed in clock.milestones or clock.samples_consumed == c['samples']
                    path = output / (f'samples_{clock.samples_consumed}.pt' if milestone else 'recovery_next.pt')
                    save_checkpoint(payload, path)
                    if not milestone:
                        path.replace(output / 'recovery.pt')
            save_metadata_json(dict(status='TRAINING_COMPLETE_DEV_EVALUATION_PENDING',
                samples=clock.samples_consumed, updates=clock.optimizer_updates,
                cumulative_samples=base_samples+clock.samples_consumed,
                seconds=time.monotonic()-started, gpu_peak_bytes=torch.cuda.max_memory_allocated(),
                preclip_gradient_p99=float(np.quantile(gradients, .99)), **counts), output / 'summary.json')
            success = True
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
        history.close(success)


def train_latent(configuration):
    if configuration['condition'] == 'S':
        return train_native_s(configuration)
    if configuration['condition'] == 'P':
        return train_native_p(configuration)
    raise ValueError('The specified latent experiment uses only S/P')


def _pd_model(c, previous, view, checkpoint, kind, specification):
    from .v31_training import V31PDModel
    structural, architecture = s_model(c['distance_bias'], c['views'], latent=kind,
        latent_config=specification if kind != 'none' else None)
    pd = V31PDModel(structural.encoder, view, forms=previous['head_form'], pooling=previous['pooling'])
    model = torch.nn.ModuleDict(dict(structural=structural, pd=pd))
    if checkpoint is not None:
        result = model.load_state_dict(checkpoint['model'], strict=False)
        allowed = ('structural.encoder.latent_module.', 'pd.encoder.latent_module.')
        if result.unexpected_keys or any(not key.startswith(allowed) for key in result.missing_keys):
            raise ValueError('Retain every original P/structural checkpoint weight')
    if c['stage'] == 'T0':
        for parameter in model.parameters():
            parameter.requires_grad_(False)
    module = getattr(structural.encoder, 'latent_module', None)
    if module is not None:
        for parameter in module.parameters():
            parameter.requires_grad_(True)
        if module.has_z:
            # User2026-11-11: scalars usez; molecular vectors retain original equivariant heads.
            pd.heads.enable_latent_scalar_routes(module.representation_dim, seed=0)
    return model, structural, pd, architecture


def train_native_p(c):
    """Preserve the original MFM4 P recipe, D4, fields and physical geometries."""
    import pyarrow.parquet as pq
    from .v31_loader import MFM4Dataset, encode_samples
    from .v31_experiments import _init_reader, _read_choice
    from .v31_prefetch import ordered_sample_batches
    kind, specification = latent_configuration(c)
    checkpoint, previous = initialization_source(c)
    if (previous['condition'], previous['distance_bias'], previous['views'], previous['seed'],
            previous['samples'], previous['batch_size']) != ('P', c['distance_bias'], c['views'], 0, 6_000_000, 32):
        raise ValueError('Continue the selected original C1 six-million P checkpoint')
    if previous['fixed_full_condition'] or previous['families'] is not None:
        raise ValueError('The paired C1 P run retains its original full enabled P recipe')
    view = json.loads(Path(previous['training_view']).read_text())
    if view.get('status') != 'FROZEN_BEFORE_STAGE5_PD':
        raise ValueError('Use the existing frozen data-line view')
    dataset_configuration = dict(root=previous['root'], source=previous['source'],
        order=previous['order'], k=previous['k'], training_view=view,
        normalizations=json.loads(Path(previous['normalizations']).read_text()), pprime=False,
        geometry_only=False)
    dataset = MFM4Dataset(**dataset_configuration)
    mids = pq.read_table(previous['subset_path'], columns=['molecule_id']).column(0).to_pylist()
    dataset.indices = dataset.indices_from_ids(mids)
    dataset._index_set = set(map(int, dataset.indices))
    if len(dataset) != 240_000:
        raise ValueError('Keep the original P240k subset')
    output = Path(c['output'])
    output.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(0)
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model, structural, pd, architecture = _pd_model(c, previous, dataset.view,
        checkpoint, kind, specification)
    if kind == 'dense_addon':
        # Count complete condition models, including the replaced scalar heads;
        # derive the dense width algebraically, never by a performance search.
        with torch.random.fork_rng(devices=[]):
            reference_spec = dict(specification, kind='lite_rec', write_back=True, reconstruction=True,
                                  k=8, reconstruction_weight=.1)
            reference, _, _, _ = _pd_model(c, previous, dataset.view, None, 'lite_rec', reference_spec)
            target = sum(p.numel() for p in reference.parameters())
            del reference
        from ..model.v3_latent import DenseResidual
        from dataclasses import replace, asdict
        module = structural.encoder.latent_module
        base = sum(p.numel() for p in model.parameters()) - sum(p.numel() for p in module.parameters())
        width = max(8, round(((target-base-4096)/2050)/8)*8)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(0)
            module.layers = torch.nn.ModuleList([DenseResidual(width), DenseResidual(width)])
        module.spec = replace(module.spec, dense_hidden_dim=width)
        architecture['backbone']['v3_latent'] = asdict(module.spec)
        structural.encoder.v3_latent_spec = asdict(module.spec)
        structural.encoder.backbone_config['v3_latent'] = asdict(module.spec)
        actual = sum(p.numel() for p in model.parameters())
        if abs(actual-target)/target > .05:
            raise ValueError('Whole P model must match lite_rec within5% parameters')
        module.parameter_match = dict(scope='whole_P_condition_model', reference=target,
            actual=actual, relative_error=abs(actual-target)/target, hidden_dim=width)
    parameters = [p for p in model.parameters() if p.requires_grad]
    counts = dict(total_parameters=sum(p.numel() for p in model.parameters()),
                  trainable_parameters=sum(p.numel() for p in parameters))
    module = getattr(structural.encoder, 'latent_module', None)
    if module is not None and hasattr(module, 'parameter_match'):
        counts['dense_matching'] = module.parameter_match
    fields = tuple(f.name for f in pd.registry.enabled(('P',))
                   if c['stage'] != 'T0' or f.level == 'graph')
    save_metadata_json(dict(c, inherited_P_recipe=previous, enabled_fields=list(fields)),
                       output / 'configuration.json')
    save_metadata_json(architecture, output / 'architecture.json')
    save_metadata_json(counts, output / 'parameter_counts.json')
    history = TrainingHistory(output, dict(c, inherited_P_recipe=previous))
    reader = dict(dataset=dataset_configuration, mean_labels=previous['mean_labels'])
    pool = ProcessPoolExecutor(max_workers=c['workers'], mp_context=multiprocessing.get_context('spawn'),
                               initializer=_init_reader, initargs=(reader,))
    model = model.cuda().train()
    optimizer = torch.optim.AdamW(parameters, lr=c['lr'], betas=(.9, .95))
    rng, base_samples, _ = source_rng(checkpoint, c['seed'])
    clock = SampleClock(c['samples'])
    gradients, started, success = [], time.monotonic(), False
    try:
        with (output / 'losses.csv').open('x', buffering=1) as log:
            writer = csv.DictWriter(log, fieldnames=('samples', 'updates', 'total', 'P', 'rec',
                'preclip_norm', 'lr', 'seconds', 'cumulative_samples', 'gpu_peak_bytes'))
            writer.writeheader()
            for samples, consumed_rng in ordered_sample_batches(pool, _read_choice, dataset,
                    clock, rng, 32, c['samples']):
                optimizer.zero_grad(set_to_none=True)
                batch, h0 = encode_samples(samples, structural.encoder, device='cuda')
                clean_z = None if module is None else module.last_z
                projected = None if module is None else module.last_projected_latent
                prediction = pd.predict(samples, groups=('P',), fields=fields,
                    clean_features=h0, clean_batch=batch, clean_z=clean_z)
                loss = pd.loss(prediction, samples, groups=('P',), fields=fields)
                rec = loss.total.new_zeros(())
                if module is not None and getattr(module, 'decoder', None) is not None:
                    rec = reconstruction_from_clean(module, projected, batch, h0)
                total = loss.total + specification['reconstruction_weight'] * rec
                lr = c['lr'] * sample_lr_ratio(clock.samples_consumed, c['samples'], 'cosine')
                for group in optimizer.param_groups:
                    group['lr'] = lr
                total.backward()
                norm = torch.nn.utils.clip_grad_norm_(parameters, 1., error_if_nonfinite=True)
                optimizer.step()
                clock.advance(len(samples))
                rng.bit_generator.state = consumed_rng
                gradients.append(float(norm))
                row = dict(samples=clock.samples_consumed, updates=clock.optimizer_updates,
                    total=float(total), P=float(loss.total), rec=float(rec), preclip_norm=float(norm),
                    lr=lr, seconds=time.monotonic()-started,
                    cumulative_samples=base_samples+clock.samples_consumed,
                    gpu_peak_bytes=torch.cuda.max_memory_allocated())
                writer.writerow(row)
                history.log(row)
                if clock.optimizer_updates % 100 == 0:
                    print(json.dumps(row), flush=True)
                if (clock.samples_consumed in clock.milestones or clock.samples_consumed == c['samples']
                        or clock.optimizer_updates % 1000 == 0):
                    payload = dict(model=model.state_dict(), optimizer=optimizer.state_dict(),
                        configuration=dict(c, inherited_P_recipe=previous), architecture=architecture,
                        clock=clock.state_dict(), original_samples=base_samples,
                        rng=consumed_rng, torch_rng=torch.get_rng_state(), cuda_rng=torch.cuda.get_rng_state())
                    milestone = clock.samples_consumed in clock.milestones or clock.samples_consumed == c['samples']
                    path = output / (f'samples_{clock.samples_consumed}.pt' if milestone else 'recovery_next.pt')
                    save_checkpoint(payload, path)
                    if not milestone:
                        path.replace(output / 'recovery.pt')
            save_metadata_json(dict(status='TRAINING_COMPLETE_DEV_EVALUATION_PENDING',
                samples=clock.samples_consumed, updates=clock.optimizer_updates,
                cumulative_samples=base_samples+clock.samples_consumed,
                seconds=time.monotonic()-started, gpu_peak_bytes=torch.cuda.max_memory_allocated(),
                preclip_gradient_p99=float(np.quantile(gradients, .99)), **counts), output / 'summary.json')
            success = True
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
        dataset.close()
        history.close(success)
