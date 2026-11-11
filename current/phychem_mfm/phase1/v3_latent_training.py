"""Taskbook-v3 continuations; native S records and the original sample recipe."""
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
    if stage not in ('T0', 'T1') or arm not in (t0 if stage == 'T0' else t1):
        raise ValueError('Use a specified T0/T1 arm')
    if c['seed'] != 0 or c['batch_size'] != 32:
        raise ValueError('The latent experiment uses seed0 and effective B32')
    kind = (t0 if stage == 'T0' else t1)[arm]
    specification = dict(c['latent_spec'], kind=kind)
    specification['write_back'] = stage != 'T0' and kind in ('lite', 'lite_rec')
    specification['reconstruction'] = (kind == 'lite_rec' or
        (stage == 'T0' and arm == 'T0-3' and c['condition'] == 'S'))
    expected = (500_000, 3e-4) if stage == 'T0' else (1_500_000, 1e-4)
    if (c['samples'], c['lr']) != expected or c['clip'] != 1.:
        raise ValueError('Keep the taskbook stage budget, learning rate and clipping')
    return kind, specification


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
    def __init__(self, output, configuration):
        import wandb
        root = output / 'offline_wandb' / os.environ.get('SLURM_JOB_ID', str(os.getpid()))
        root.mkdir(parents=True, exist_ok=False)
        for suffix in ('cache', 'config', 'data'):
            path = root / suffix
            path.mkdir()
            os.environ['WANDB_' + suffix.upper() + '_DIR'] = str(path)
        self.run = wandb.init(project='MFM-model-v3', name=output.name, mode='offline',
            dir=str(root), config=configuration,
            settings=wandb.Settings(x_stats_sampling_interval=30))
        if self.run is None or self.run.disabled:
            raise RuntimeError('A genuine offline W&B SDK execution is required')
        self.root, self.output = root, output
        self.stream = (root / 'training_history.jsonl').open('x', buffering=1)
        self.window = []
        self.next_boundary = 100_000

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
    checkpoint = torch.load(c['initialize_from'], map_location='cpu', weights_only=True)
    previous = checkpoint['configuration']
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
    # Reinitialize optimizer/stage clocks; preserve the paired source draw/RNG state.
    rng = np.random.default_rng()
    rng.bit_generator.state = checkpoint['rng']
    torch.set_rng_state(checkpoint['torch_rng'])
    torch.cuda.set_rng_state(checkpoint['cuda_rng'])
    base_samples = checkpoint['clock']['samples_consumed']
    base_updates = checkpoint['clock']['optimizer_updates']
    if base_samples != 6_000_000:
        raise ValueError('Start every paired arm from the same6M checkpoint')
    clock = SampleClock(c['samples'])
    view_config = StructuralViewConfig(seed=c['seed'])
    builder = build_two_structural_views if c['views'] == 'two' else build_structural_views
    gradients, started, success = [], time.monotonic(), False
    try:
        with (output / 'losses.csv').open('x', buffering=1) as log:
            writer = csv.DictWriter(log, fieldnames=('samples', 'updates', 'total', 'S', 'rec',
                'preclip_norm', 'lr', 'seconds', 'cumulative_samples', 'gpu_peak_bytes'))
            writer.writeheader()
            while clock.samples_consumed < c['samples']:
                count = clock.max_next_samples(32)
                selected = index.draw(rng, count)
                records = list(pool.map(_read_native, selected, chunksize=1))
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
    raise ValueError('P molecular-vector routing awaits the user; no fields may be changed')
