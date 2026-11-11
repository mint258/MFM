"""Original native240k S proxy with the selected latent, recipe and exact resume."""
from concurrent.futures import ProcessPoolExecutor
import csv
import multiprocessing
from pathlib import Path
import time

import numpy as np
import torch

from .v2_disk import save_checkpoint, save_metadata_json
from .v2_s_training import (GroupedSIndex, _worker_init, _read_native, s_model,
    sample_lr_ratio, accumulated_s_backward, structural_observation_counts)
from .v3_training import SampleClock
from .v3_latent_training import TrainingHistory, reconstruction_from_clean


def train_selected_native_s(c):
    """The real first run is wiring acceptance; there is no model smoke run."""
    import pyarrow.parquet as pq
    from torch_geometric.data import Batch
    from .v3_structural import build_structural_views, StructuralViewConfig
    from .v3_architecture_views import build_two_structural_views
    from ..training.losses import LossWeights
    kind, specification = c['latent'], c.get('latent_spec')
    if c['condition'] != 'S' or kind not in ('none', 'pma', 'lite_rec'):
        raise ValueError('Use the selected architecture for native proxy S only')
    if c['seed'] != 0 or c['samples'] != 6_000_000 or c['batch_size'] not in (32, 64):
        raise ValueError('Keep the registered proxy seed, budget and effective batches')
    index = GroupedSIndex(pq.read_table(c['index_path']))
    if index.molecules != 240_000:
        raise ValueError('Native proxy S retains the complete original240k source')
    microbatch = c.get('microbatch_size', c['batch_size'])
    if not 0 < microbatch <= c['batch_size'] or (kind != 'none' and microbatch != c['batch_size']):
        raise ValueError('Latent reconstruction requires one complete effective batch')
    output = Path(c['output'])
    output.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(c['seed'])
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model, architecture = s_model(c['distance_bias'], c['views'], latent=kind,
                                  latent_config=specification if kind != 'none' else None)
    parameters = [p for p in model.parameters() if p.requires_grad]
    counts = dict(total_parameters=sum(p.numel() for p in model.parameters()),
                  trainable_parameters=sum(p.numel() for p in parameters))
    module = getattr(model.encoder, 'latent_module', None)
    if module is not None and hasattr(module, 'parameter_match'):
        counts['dense_module_matching'] = module.parameter_match
    save_metadata_json(c, output / 'configuration.json')
    save_metadata_json(architecture, output / 'architecture.json')
    save_metadata_json(counts, output / 'parameter_counts.json')
    repo = Path(__file__).absolute().parents[3]
    pool = ProcessPoolExecutor(max_workers=c['workers'],
        mp_context=multiprocessing.get_context('spawn'), initializer=_worker_init, initargs=(str(repo),))
    model = model.cuda().train()
    optimizer = torch.optim.AdamW(parameters, lr=c['lr'], betas=(.9, .95))
    rng, base_samples, base_updates = np.random.default_rng(c['seed']), 0, 0
    clock = SampleClock(c['samples'])
    view_config = StructuralViewConfig(seed=c['seed'])
    builder = build_two_structural_views if c['views'] == 'two' else build_structural_views
    gradients, elapsed_prior, peak_prior = [], 0., 0
    if c.get('resume'):
        checkpoint = torch.load(c['resume'], map_location='cpu', weights_only=True)
        ignored = {'output', 'resume', 'workers', 'microbatch_size'}
        if {k:v for k,v in checkpoint['configuration'].items() if k not in ignored} != {
                k:v for k,v in c.items() if k not in ignored}:
            raise ValueError('Scientific native S resume configuration differs')
        model.load_state_dict(checkpoint['model'])
        optimizer.load_state_dict(checkpoint['optimizer'])
        clock.load_state_dict(checkpoint['clock'])
        rng.bit_generator.state = checkpoint['rng']
        torch.set_rng_state(checkpoint['torch_rng'])
        torch.cuda.set_rng_state(checkpoint['cuda_rng'])
        gradients = checkpoint['preclip_norms']
        elapsed_prior = checkpoint['elapsed_seconds']
        peak_prior = checkpoint['gpu_peak_bytes']
    initial_samples, initial_updates = clock.samples_consumed, clock.optimizer_updates
    history = TrainingHistory(output, c, initial_samples=initial_samples)
    started, success = time.monotonic(), False
    try:
        with (output / 'losses.csv').open('x', buffering=1) as log:
            writer = csv.DictWriter(log, fieldnames=('samples', 'updates', 'total', 'S', 'rec',
                'preclip_norm', 'lr', 'seconds', 'cumulative_samples', 'gpu_peak_bytes'))
            writer.writeheader()
            while clock.samples_consumed < c['samples']:
                count = clock.max_next_samples(c['batch_size'])
                selected = index.draw(rng, count)
                records = list(pool.map(_read_native, selected, chunksize=1))
                clean = Batch.from_data_list(records)
                optimizer.zero_grad(set_to_none=True)
                structural = torch.zeros((), device='cuda')
                rec = structural
                ordinals = tuple(range(clock.samples_consumed, clock.samples_consumed+count))
                if kind == 'none' and microbatch < count:
                    loss = accumulated_s_backward(model, records, ordinals, builder, view_config,
                        microbatch, clock.optimizer_updates, count_observations=structural_observation_counts)
                    structural = loss.total
                    total = structural
                else:
                    views = builder(clean, ordinals=ordinals, config=view_config).to('cuda')
                    prediction = model.forward_pretrain(views, enabled_groups=('S',))
                    loss = model.compute_loss(prediction, views, {}, {}, enabled_groups=('S',),
                        weights=LossWeights(), exposure_step=clock.optimizer_updates)
                    structural = loss.total
                    if module is not None and getattr(module, 'decoder', None) is not None:
                        projected = module.last_projected_latent[views.clean_graph_rows]
                        rec = reconstruction_from_clean(module, projected, clean.to('cuda'), prediction.clean_h0)
                    total = structural + (0. if specification is None else specification['reconstruction_weight'])*rec
                    total.backward()
                lr = c['lr'] * sample_lr_ratio(clock.samples_consumed, c['samples'], c['schedule'])
                for group in optimizer.param_groups:
                    group['lr'] = lr
                norm = torch.nn.utils.clip_grad_norm_(parameters, c['clip'], error_if_nonfinite=True)
                optimizer.step()
                clock.advance(count)
                gradients.append(float(norm))
                row = dict(samples=clock.samples_consumed, updates=clock.optimizer_updates,
                    total=float(total), S=float(structural), rec=float(rec), preclip_norm=float(norm),
                    lr=lr, seconds=elapsed_prior+time.monotonic()-started,
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
                        preclip_norms=gradients, elapsed_seconds=elapsed_prior+time.monotonic()-started,
                        gpu_peak_bytes=max(peak_prior, torch.cuda.max_memory_allocated()),
                        torch_rng=torch.get_rng_state(), cuda_rng=torch.cuda.get_rng_state())
                    milestone = clock.samples_consumed in clock.milestones or clock.samples_consumed == c['samples']
                    path = output / (f'samples_{clock.samples_consumed}.pt' if milestone else 'recovery_next.pt')
                    save_checkpoint(payload, path)
                    if not milestone:
                        path.replace(output / 'recovery.pt')
            save_metadata_json(dict(status='TRAINING_COMPLETE_DEV_EVALUATION_PENDING',
                samples=clock.samples_consumed, updates=clock.optimizer_updates,
                cumulative_samples=base_samples+clock.samples_consumed,
                seconds=elapsed_prior+time.monotonic()-started, gpu_peak_bytes=max(peak_prior, torch.cuda.max_memory_allocated()),
                actual_samples=clock.samples_consumed-initial_samples,
                actual_updates=clock.optimizer_updates-initial_updates,
                actual_seconds=time.monotonic()-started,
                preclip_gradient_p99=float(np.quantile(gradients, .99)), **counts), output / 'summary.json')
            success = True
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
        history.close(success)

