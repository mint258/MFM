"""Taskbook-v2 S/P/D/SDP experiments on the delivered MFM4 population.

No selection is made here: an experiment configuration fixes its subset,
architecture, recipe and budget. Frozen decisions remain downstream of dev.
"""
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

from .v2_disk import save_checkpoint
from .v31_segment_timing import phase, SegmentTimer

from .v31_loader import MFM4Dataset, collate_samples
from .v31_training import V31PDModel
from .v31_prefetch import ordered_sample_batches
from .v2_s_training import s_model, sample_lr_ratio, structural_observation_counts
from .v3_losses import V3LossResult
from .v3_structural import build_structural_views, StructuralViewConfig, combine_structural_loss
from .v3_architecture_views import build_two_structural_views
from .v3_training import SampleClock
from ..training.losses import LossWeights


def observation_weights(counts, field_groups, groups, fixed_denominators=None):
    """Field/group weights for a complete effective batch, not each microbatch."""
    denominators = ({g: sum(field_groups[n] == g and count > 0 for n, count in counts.items())
                     for g in groups} if fixed_denominators is None else fixed_denominators)
    return {name: 1. / (len(groups) * denominators[field_groups[name]])
            for name, count in counts.items() if count > 0}


def accumulated_backward(chunks, step, count, field_groups, groups, *, fixed_denominators=None,
                         device='cuda'):
    """Reconstruct original per-field observation means before one update."""
    device = torch.device(device)
    cpu_rng = torch.get_rng_state()
    cuda_rng = torch.cuda.get_rng_state(device) if device.type == 'cuda' else None
    totals = {}
    with phase('count'), torch.no_grad():
        for chunk in chunks:
            for name, n in count(chunk).items():
                totals[name] = totals.get(name, 0) + n
    torch.set_rng_state(cpu_rng)
    if cuda_rng is not None:
        torch.cuda.set_rng_state(cuda_rng, device)
    weights = observation_weights(totals, field_groups, groups, fixed_denominators)
    values = {name: torch.zeros((), device=device) for name in totals}
    for chunk in chunks:
        loss = step(chunk)
        with phase('loss'):
            total = loss.total.new_zeros(())
            for name, value in loss.fields.items():
                if totals[name]:
                    weighted = value * (loss.counts[name] / totals[name])
                    values[name] += weighted.detach()
                    total = total + weighted * weights[name]
        if total.requires_grad:
            with phase('backward'):
                total.backward()
    group_values = {group: sum((values[name] * weights.get(name, 0.) * len(groups)
        for name in values if field_groups[name] == group), torch.zeros((), device=device))
        for group in groups}
    total = torch.stack(list(group_values.values())).mean()
    observed = {g: sum(field_groups[n] == g and count > 0 for n, count in totals.items()) for g in groups}
    return V3LossResult(total, values, group_values, totals, observed, tuple(groups))


def _init_reader(configuration):
    global _dataset, _mean_labels
    torch.set_num_threads(1)
    _dataset = MFM4Dataset(**configuration['dataset'])
    _mean_labels = configuration['mean_labels']


def _read_choice(choice):
    molecule, conformer = choice
    sample = _dataset.read(molecule, conformer)
    if _mean_labels:
        sample['targets'] = _dataset.molecule_mean(molecule)
    return sample


def segment_stop_samples(configuration, completed=0):
    """Stop execution at a declared sample checkpoint, retaining the recipe budget."""
    budget = configuration['samples']
    stop = configuration.get('run_until_samples')
    stop = budget if stop is None else stop
    if (type(stop) is not int or not completed < stop <= budget
            or (stop != budget and stop not in SampleClock(budget).milestones)):
        raise ValueError('Execution segment must end at the budget or a later sample milestone')
    return stop


def train_v31(configuration):
    import pyarrow.parquet as pq
    c = dict(condition='SDP', distance_bias='C1-0', views='three', head_form='H1',
        pooling='registry', source='PM7', order='fixed_random', k=None, seed=0,
        samples=6_000_000, run_until_samples=None, batch_size=32, microbatch_size=4, workers=14,
        lr=3e-4, schedule='cosine', clip=1., mean_labels=False,
        families=None, fixed_full_condition=False, expected_molecules=240_000)
    unknown = set(configuration) - (set(c) | {'root', 'training_view', 'normalizations',
        'subset_path', 'output', 'resume', 'stage', 'candidate', 'code_tag'})
    if unknown:
        raise ValueError('Unknown experiment configuration keys: ' + ', '.join(sorted(unknown)))
    c.update(configuration)
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
    structural, architecture = s_model(c['distance_bias'], c['views'])
    modules = dict(structural=structural)
    pd = V31PDModel(structural.encoder, dataset.view, forms=c['head_form'], pooling=c['pooling']) if pd_groups else None
    if pd is not None:
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
        if 'S' in groups:
            views = builder(clean, ordinals=ordinals, config=view_configuration)
            if count_only:
                return {**pd_counts(samples), **structural_observation_counts(structural, views)}
            views = views.to('cuda')
            prediction = structural.forward_pretrain(views, enabled_groups=('S',))
            s_loss = structural.compute_loss(prediction, views, {}, {}, enabled_groups=('S',),
                weights=LossWeights(), exposure_step=clock.optimizer_updates)
        if count_only:
            return {**pd_counts(samples), **({} if s_loss is None else s_loss.counts)}
        if pd is not None:
            predictions = pd.predict(samples, groups=pd_groups, fields=fields,
                clean_features=None if prediction is None else prediction.clean_h0,
                clean_batch=None if prediction is None else clean.to('cuda'))
            loss = pd.loss(predictions, samples, groups=pd_groups, fields=fields)
        else:
            loss = V3LossResult(torch.zeros((), device='cuda'), {}, {}, {}, {}, ())
        return loss if s_loss is None else combine_structural_loss(loss, s_loss.fields, s_loss.counts, enabled_groups=groups)

    timing_directory = os.environ.get('MFM_CPU_PROFILE_DIR')
    timer = SegmentTimer(timing_directory) if timing_directory else None
    measured_steps = int(os.environ.get('MFM_CPU_MEASURE_STEPS', '0'))
    started = time.monotonic()
    reader = dict(dataset=dataset_configuration, mean_labels=c['mean_labels'])
    with ProcessPoolExecutor(c['workers'], mp_context=multiprocessing.get_context('spawn'),
            initializer=_init_reader, initargs=(reader,)) as pool, (output/'losses.csv').open('w', buffering=1) as log:
        writer = csv.DictWriter(log, fieldnames=['samples','updates','total','S','D','P','preclip_norm','lr','seconds'])
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
            loss = accumulated_backward(chunks, evaluate_chunk,
                lambda chunk: evaluate_chunk(chunk, count_only=True) if 'S' in groups else pd_counts(chunk[0]),
                field_groups, groups, fixed_denominators=full_denominators)
            with phase('clip_optimizer'):
                norm = torch.nn.utils.clip_grad_norm_(parameters, c['clip'], error_if_nonfinite=True)
                optimizer.step()
            clock.advance(count)
            rng.bit_generator.state = consumed_rng
            with phase('logging'):
                gradients.append(float(norm))
                row = dict(samples=clock.samples_consumed, updates=clock.optimizer_updates,
                    total=float(loss.total), preclip_norm=float(norm), lr=lr, seconds=elapsed_prior+time.monotonic()-started,
                    **{g: float(loss.groups[g]) if g in loss.groups else None for g in ('S','D','P')})
                writer.writerow(row)
            milestone = clock.samples_consumed in clock.milestones or clock.samples_consumed == c['samples']
            if milestone or clock.optimizer_updates % 1000 == 0:
                with phase('checkpoint'):
                    payload = dict(model=model.state_dict(), optimizer=optimizer.state_dict(), configuration=c,
                        clock=clock.state_dict(), rng=rng.bit_generator.state, torch_rng=torch.get_rng_state(),
                        cuda_rng=torch.cuda.get_rng_state(), preclip_norms=gradients,
                        elapsed_seconds=elapsed_prior+time.monotonic()-started, gpu_peak_bytes=peak_gpu_bytes())
                    if milestone:
                        save_checkpoint(payload, output/f'samples_{clock.samples_consumed}.pt')
                    else:
                        save_checkpoint(payload, output/'recovery_next.pt')
                        (output/'recovery_next.pt').replace(output/'recovery.pt')
            if clock.optimizer_updates % 100 == 0:
                with phase('logging'):
                    print(json.dumps(row), flush=True)
            if timer is not None:
                timer.end_step()
            if measured_steps and clock.optimizer_updates - initial_updates >= measured_steps:
                break
    if timer is not None:
        timer.close()
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
