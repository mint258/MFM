"""Selected-architecture S/P/D/SDP development and exact sample-clock segments.

The legacy engine is retained. Latent paths evaluate a complete effective batch
so reconstruction teacher variance is the registered global batch statistic.
"""
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import csv
import json
import multiprocessing
from pathlib import Path
import time

import numpy as np
import torch

from .v2_disk import save_checkpoint
from .v2_s_training import s_model, sample_lr_ratio, structural_observation_counts
from .v31_experiments import (_init_reader, _read_choice, accumulated_backward,
    observation_weights, segment_stop_samples)
from .v31_loader import MFM4Dataset, collate_samples, encode_samples
from .v31_prefetch import ordered_sample_batches
from .v31_training import V31PDModel
from .v3_losses import V3LossResult
from .v3_structural import build_structural_views, StructuralViewConfig, combine_structural_loss
from .v3_architecture_views import build_two_structural_views
from .v3_training import SampleClock
from .v3_latent_training import TrainingHistory, reconstruction_from_clean
from ..training.losses import LossWeights


@contextmanager
def tracked_execution(output, configuration, initial_samples):
    history = TrainingHistory(output, configuration, initial_samples=initial_samples)
    success = False
    try:
        yield history
        success = True
    finally:
        history.close(success)


def train_selected(configuration):
    import pyarrow.parquet as pq
    c = dict(condition='SDP', distance_bias='C1-0', views='three', head_form='H1',
        pooling='registry', source='PM7', order='fixed_random', k=None, seed=0,
        samples=6_000_000, run_until_samples=None, batch_size=32, microbatch_size=4, workers=14,
        lr=3e-4, schedule='cosine', clip=1., mean_labels=False,
        families=None, fixed_full_condition=False, expected_molecules=240_000,
        latent='none', latent_spec=None, arm='selected', stage='SELECTED')
    unknown = set(configuration) - (set(c) | {'root', 'training_view', 'normalizations',
        'subset_path', 'output', 'resume', 'stage', 'candidate', 'code_tag'})
    if unknown:
        raise ValueError('Unknown experiment configuration keys: ' + ', '.join(sorted(unknown)))
    c.update(configuration)
    if c['latent'] not in ('none', 'pma', 'lite_rec'):
        raise ValueError('Use only the actual adopted architecture or original none')
    if c['latent'] != 'none' and c['microbatch_size'] != c['batch_size']:
        raise ValueError('Use a complete effective batch for the registered reconstruction variance')
    stop_samples = segment_stop_samples(c)
    groups = tuple(g for g in ('S', 'D', 'P') if g in c['condition'])
    if c['condition'] not in ('S', 'P', 'D', 'SDP'):
        raise ValueError('Use an explicit S/P/D/SDP scientific condition')
    if c['views'] not in ('two', 'three') or c['schedule'] not in ('cosine', 'wsd'):
        raise ValueError('Use explicit two/three views and cosine/wsd schedule')
    pd_groups = tuple(g for g in groups if g != 'S')
    if not 0 < c['microbatch_size'] <= c['batch_size']:
        raise ValueError('Microbatch size must be between one and the effective batch size')
    dataset_configuration = dict(root=c['root'], source=c['source'], order=c['order'], k=c['k'])
    dataset_configuration['pprime'] = c['source'] == 'UFF' and 'P' in groups
    dataset_configuration['geometry_only'] = not pd_groups
    if pd_groups:
        view = json.loads(Path(c['training_view']).read_text())
        if view.get('status') != 'FROZEN_BEFORE_STAGE5_PD':
            raise ValueError('Frozen data-line training view required')
        dataset_configuration.update(training_view=view,
            normalizations=json.loads(Path(c['normalizations']).read_text()))
    dataset = MFM4Dataset(**dataset_configuration)
    if c.get('subset_path'):
        mids = pq.read_table(c['subset_path'], columns=['molecule_id']).column(0).to_pylist()
        indices = dataset.indices_from_ids(mids)
        dataset.indices, dataset._index_set = indices, set(map(int, indices))
    if len(dataset) != c['expected_molecules']:
        raise ValueError('Actual TRAIN population differs from the experiment configuration')
    output = Path(c['output'])
    output.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(c['seed'])
    torch.manual_seed(c['seed'])
    torch.set_num_threads(1)
    structural, architecture = s_model(c['distance_bias'], c['views'], latent=c['latent'],
        latent_config=c['latent_spec'] if c['latent'] != 'none' else None)
    modules = dict(structural=structural)
    pd = V31PDModel(structural.encoder, dataset.view, forms=c['head_form'], pooling=c['pooling']) if pd_groups else None
    module = getattr(structural.encoder, 'latent_module', None)
    if pd is not None:
        if module is not None and module.has_z:
            pd.heads.enable_latent_scalar_routes(module.representation_dim, seed=c['seed'])
        modules['pd'] = pd
    model = torch.nn.ModuleDict(modules).cuda().train()
    parameters = list(model.parameters())
    fields = tuple(f.name for f in pd.registry.enabled(pd_groups)
                   if c['families'] is None or f.family in c['families']) if pd is not None else ()
    field_groups = {f.name: f.group for f in structural.registry.fields if 'S' in groups}
    if pd is not None:
        physical_fields = {pd.selections[name][0] for name in fields}
        field_groups.update({f.name: f.group for f in pd.head_registry.fields if f.name in physical_fields})
    full_denominators = None
    if c['fixed_full_condition']:
        full_denominators = {g: (3 if g == 'S' else sum(f.group == g for f in pd.head_registry.fields)) for g in groups}
    optimizer = torch.optim.AdamW(parameters, lr=c['lr'], betas=(.9, .95))
    clock = SampleClock(c['samples'])
    view_configuration = StructuralViewConfig(seed=c['seed'])
    builder = build_two_structural_views if c['views'] == 'two' else build_structural_views
    gradients, elapsed_prior, peak_prior = [], 0., 0
    if c.get('resume'):
        checkpoint = torch.load(c['resume'], map_location='cpu', weights_only=True)
        previous = checkpoint['configuration']
        ignored = {'output', 'resume', 'microbatch_size', 'workers', 'run_until_samples'}
        if {k:v for k,v in previous.items() if k not in ignored} != {k:v for k,v in c.items() if k not in ignored}:
            raise ValueError('Scientific resume configuration differs')
        model.load_state_dict(checkpoint['model'])
        optimizer.load_state_dict(checkpoint['optimizer'])
        clock.load_state_dict(checkpoint['clock'])
        rng.bit_generator.state = checkpoint['rng']
        torch.set_rng_state(checkpoint['torch_rng'])
        torch.cuda.set_rng_state(checkpoint['cuda_rng'])
        gradients = checkpoint['preclip_norms']
        elapsed_prior = checkpoint['elapsed_seconds']
        peak_prior = checkpoint.get('gpu_peak_bytes')
        stop_samples = segment_stop_samples(c, clock.samples_consumed)
    (output/'configuration.json').write_text(json.dumps(c, indent=2) + '\n')
    (output/'architecture.json').write_text(json.dumps(architecture, indent=2) + '\n')
    initial_samples, initial_updates = clock.samples_consumed, clock.optimizer_updates
    (output/'execution.json').write_text(json.dumps(dict(microbatch_size=c['microbatch_size'],
        effective_batch_size=c['batch_size'], prefetched_batches=1, initial_samples=initial_samples,
        initial_updates=initial_updates, elapsed_seconds_prior=elapsed_prior), indent=2) + '\n')

    def pd_counts(samples):
        return {} if pd is None else pd.field_counts(samples, groups=pd_groups, fields=fields)

    def peak_gpu_bytes():
        # Old checkpoints without a prior peak cannot establish a full-run peak.
        return None if peak_prior is None else max(peak_prior, torch.cuda.max_memory_allocated())

    def evaluate_chunk(chunk, *, count_only=False):
        samples, ordinals = chunk
        s_loss, prediction = None, None
        clean = collate_samples(samples)
        clean_features = clean_z = projected = clean_batch = None
        if 'S' in groups:
            views = builder(clean, ordinals=ordinals, config=view_configuration)
            if count_only:
                return {**pd_counts(samples), **structural_observation_counts(structural, views)}
            views = views.to('cuda')
            prediction = structural.forward_pretrain(views, enabled_groups=('S',))
            s_loss = structural.compute_loss(prediction, views, {}, {}, enabled_groups=('S',),
                weights=LossWeights(), exposure_step=clock.optimizer_updates)
            clean_features, clean_batch = prediction.clean_h0, clean.to('cuda')
            if module is not None:
                clean_z = module.last_z[views.clean_graph_rows]
                if getattr(module, 'decoder', None) is not None:
                    projected = module.last_projected_latent[views.clean_graph_rows]
        if count_only:
            return {**pd_counts(samples), **({} if s_loss is None else s_loss.counts)}
        if module is not None and prediction is None:
            clean_batch, clean_features = encode_samples(samples, structural.encoder, device='cuda')
            clean_z, projected = module.last_z, module.last_projected_latent
        if pd is not None:
            predictions = pd.predict(samples, groups=pd_groups, fields=fields,
                clean_features=clean_features, clean_batch=clean_batch, clean_z=clean_z)
            loss = pd.loss(predictions, samples, groups=pd_groups, fields=fields)
        else:
            loss = V3LossResult(torch.zeros((), device='cuda'), {}, {}, {}, {}, ())
        loss = loss if s_loss is None else combine_structural_loss(loss, s_loss.fields, s_loss.counts, enabled_groups=groups)
        if module is None:
            return loss
        rec = loss.total.new_zeros(())
        if getattr(module, 'decoder', None) is not None:
            rec = reconstruction_from_clean(module, projected, clean_batch, clean_features)
        return loss, rec

    started = time.monotonic()
    reader = dict(dataset=dataset_configuration, mean_labels=c['mean_labels'])
    with tracked_execution(output, c, initial_samples) as history, ProcessPoolExecutor(c['workers'], mp_context=multiprocessing.get_context('spawn'),
            initializer=_init_reader, initargs=(reader,)) as pool, (output/'losses.csv').open('w', buffering=1) as log:
        writer = csv.DictWriter(log, fieldnames=['samples','updates','total','S','D','P','rec','preclip_norm','lr','seconds','gpu_peak_bytes'])
        writer.writeheader()
        for samples, consumed_rng in ordered_sample_batches(pool, _read_choice, dataset,
                clock, rng, c['batch_size'], stop_samples):
            count = len(samples)
            chunks = [(samples[start:start+c['microbatch_size']], tuple(range(clock.samples_consumed+start,
                       clock.samples_consumed+min(start+c['microbatch_size'], count))))
                      for start in range(0, count, c['microbatch_size'])]
            lr = c['lr'] * sample_lr_ratio(clock.samples_consumed, c['samples'], c['schedule'])
            for group in optimizer.param_groups:
                group['lr'] = lr
            optimizer.zero_grad(set_to_none=True)
            rec = torch.zeros((), device='cuda')
            if module is None:
                loss = accumulated_backward(chunks, evaluate_chunk,
                    lambda chunk: evaluate_chunk(chunk, count_only=True) if 'S' in groups else pd_counts(chunk[0]),
                    field_groups, groups, fixed_denominators=full_denominators)
                total = loss.total
            else:
                loss, rec = evaluate_chunk((samples, tuple(range(clock.samples_consumed, clock.samples_consumed+count))))
                weights = observation_weights(loss.counts, field_groups, groups, full_denominators)
                base = sum((loss.fields[name]*weight for name, weight in weights.items()), rec.new_zeros(()))
                total = base + c['latent_spec']['reconstruction_weight']*rec
                total.backward()
            norm = torch.nn.utils.clip_grad_norm_(parameters, c['clip'], error_if_nonfinite=True)
            optimizer.step()
            clock.advance(count)
            rng.bit_generator.state = consumed_rng
            gradients.append(float(norm))
            row = dict(samples=clock.samples_consumed, updates=clock.optimizer_updates,
                total=float(total), rec=float(rec), gpu_peak_bytes=torch.cuda.max_memory_allocated(),
                preclip_norm=float(norm), lr=lr, seconds=elapsed_prior+time.monotonic()-started,
                **{g: float(loss.groups[g]) if g in loss.groups else None for g in ('S','D','P')})
            writer.writerow(row)
            history.log(row)
            milestone = clock.samples_consumed in clock.milestones or clock.samples_consumed == c['samples']
            if milestone or clock.optimizer_updates % 1000 == 0:
                payload = dict(model=model.state_dict(), optimizer=optimizer.state_dict(), configuration=c, architecture=architecture,
                    clock=clock.state_dict(), rng=rng.bit_generator.state, torch_rng=torch.get_rng_state(),
                    cuda_rng=torch.cuda.get_rng_state(), preclip_norms=gradients,
                    elapsed_seconds=elapsed_prior+time.monotonic()-started, gpu_peak_bytes=peak_gpu_bytes())
                if milestone:
                    save_checkpoint(payload, output/f'samples_{clock.samples_consumed}.pt')
                else:
                    save_checkpoint(payload, output/'recovery_next.pt')
                    (output/'recovery_next.pt').replace(output/'recovery.pt')
            if clock.optimizer_updates % 100 == 0:
                print(json.dumps(row), flush=True)
    status = ('TRAINING_COMPLETE_DEV_EVALUATION_PENDING' if clock.samples_consumed == c['samples']
              else 'SEGMENT_COMPLETE_DEV_EVALUATION_PENDING')
    actual_seconds = time.monotonic()-started
    summary = dict(status=status, sample_budget=c['samples'], samples=clock.samples_consumed,
        updates=clock.optimizer_updates, seconds=elapsed_prior+actual_seconds,
        actual_samples=clock.samples_consumed-initial_samples,
        actual_updates=clock.optimizer_updates-initial_updates, actual_seconds=actual_seconds,
        gpu_peak_bytes=peak_gpu_bytes(), process_gpu_peak_bytes=torch.cuda.max_memory_allocated(),
        preclip_gradient_p99=float(np.quantile(gradients, .99)))
    (output/'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    dataset.close()
    return summary
