"""Registered pure-S training, wrapping existing model, loss and checkpoint APIs.

The launcher must establish the taskbook GPU-start condition and actual resource
admission before calling this module. Importing it starts no computation.
"""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import csv
import json
import multiprocessing
from pathlib import Path
import random
import time

import numpy as np
import torch

from phychem_mfm.phase1.p_recipe_clip import GroupClipCalibration
from phychem_mfm.phase1.p_recipe_handoff import publish_checkpoint, read_request, finish_handoff
from phychem_mfm.phase1.v2_s_training import s_model, sample_lr_ratio
from phychem_mfm.phase1.v31_loader import collate_samples
from phychem_mfm.phase1.v31_prefetch import ordered_sample_batches
from phychem_mfm.phase1.v3_structural import (build_structural_views, StructuralViewConfig,
                                            structural_raw_losses)
from phychem_mfm.phase1.v3_training import SampleClock, capture_rng_state, restore_rng_state
from phychem_mfm.phase1.v3_latent_training import TrainingHistory
from phychem_mfm.training.losses import LossWeights

from loss import structural_total
from diagnostics import noise_statistics, relative_error
from noise import apply_geometry_noise, multiscale_sigma
from s_data import GeometryDataset, init_reader, paired_choices, read_choice
from checkpoint_binding import validate_resume, baseline_acceptance_required


def train(configuration):
    c = dict(configuration)
    # These checks protect the registered execution contract, not old outputs.
    if c['batch_size'] != 32 or c['microbatch_size'] != 32:
        raise ValueError('S taskbook requires a real B32 without accumulation')
    if c.get('activation_checkpointing', False) or c.get('gradient_accumulation', False):
        raise ValueError('S taskbook disables recomputation and accumulation')
    if c['samples'] not in (3000000, 9000000):
        raise ValueError('Unregistered S training budget')
    torch.set_num_threads(1)
    random.seed(c['seed'])
    np.random.seed(c['seed'])
    torch.manual_seed(c['seed'])
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision('highest')
    rotor_index = c['rotor_index'] if c['noise'] == 'frad' else None
    data = GeometryDataset(c['root'], c['population'], source=c['source'], rotor_index=rotor_index)
    validation = GeometryDataset(c['root'], c['population'], source=c['source'], validation=True,
                                 rotor_index=rotor_index)
    model, architecture = s_model('C1-0', 'three')
    initialization = torch.load(c['initialization'], map_location='cpu', weights_only=True)
    if (initialization['schema'] != 'S_RECIPE_RANDOM_INITIALIZATION_V1'
            or initialization['seed'] != c['seed'] or initialization['training_samples'] != 0):
        raise ValueError('Wrong producer-bound random S initialization')
    model.load_state_dict(initialization['model'])
    torch.set_rng_state(initialization['torch_rng'])
    del initialization
    model = model.cuda().train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=c['lr'], betas=tuple(c['betas']),
                                 weight_decay=c['weight_decay'])
    milestones = tuple(range(500000, c['samples'] + 1, 500000))
    clock = SampleClock(c['samples'], milestones=milestones)
    rng = np.random.default_rng(c['seed'])
    calibration = GroupClipCalibration(c['clip_calibration'], c['samples'])
    views_config = StructuralViewConfig(seed=c['seed'])
    weights = LossWeights()
    output = Path(c['output'])
    output.mkdir(parents=True, exist_ok=bool(c.get('resume')))
    prior_seconds = 0.
    if c.get('resume'):
        checkpoint = torch.load(c['resume'], map_location='cpu', weights_only=True)
        validate_resume(c, checkpoint['configuration'])
        model.load_state_dict(checkpoint['model'])
        optimizer.load_state_dict(checkpoint['optimizer'])
        clock.load_state_dict(checkpoint['clock'])
        rng.bit_generator.state = checkpoint['sampler_rng']
        calibration.load_state_dict(checkpoint['clip_calibration'])
        restore_rng_state(checkpoint['rng_state'])
        prior_seconds = checkpoint['elapsed_seconds']
        if 'baseline_acceptance' in checkpoint['configuration']:
            c['baseline_acceptance'] = checkpoint['configuration']['baseline_acceptance']
    (output/'configuration.json').write_text(json.dumps(c, indent=2)+'\n')
    history = TrainingHistory(output, c, initial_samples=clock.samples_consumed)
    planned_cursor = clock.samples_consumed

    def draw(planned_rng, count):
        nonlocal planned_cursor
        choices = paired_choices(planned_rng, data.rows, c['source'], seed=c['seed'],
                                  start=planned_cursor, count=count)
        planned_cursor += count
        return choices

    def calculate(samples, *, validation_pass=False):
        clean = collate_samples(samples)
        ordinals = tuple(sample['ordinal'] for sample in samples)
        views = build_structural_views(clean, ordinals=ordinals, config=views_config)
        plans = None
        if c['noise'] == 'frad':
            if any('rotors' not in sample for sample in samples):
                raise ValueError('Frad requires source-order precomputed rotor plans')
            plans = [sample['rotors'] for sample in samples]
        views = apply_geometry_noise(views, mode=c['noise'], rotor_plans=plans).to('cuda')
        prediction = model.forward_pretrain(views, enabled_groups=('S',))
        raw, counts = structural_raw_losses(prediction.source_outputs, views, model.registry,
                                            model.structural_binding, weights,
                                            exposure_step=clock.optimizer_updates)
        total = structural_total(raw, counts, disabled=c['disabled'])
        labels = None
        if validation_pass and c['noise'] == 'multiscale':
            labels = ['sigma_'+format(multiscale_sigma(views_config.noise_seed(ordinal)), '.16g')
                      for ordinal in ordinals]
        elif validation_pass and c['noise'] == 'frad':
            labels = [('rotors_0' if not plan else 'rotors_1-3' if len(plan) <= 3 else
                       'rotors_4-7' if len(plan) <= 7 else 'rotors_8+') for plan in plans]
        statistics = (noise_statistics(prediction.source_outputs, views, group_labels=labels)
                      if validation_pass else None)
        if baseline_acceptance_required(c, clock.samples_consumed, validation_pass):
            # The single taskbook baseline acceptance uses this real loader
            # batch and forward, without an extra run or independent reread.
            original = views.batch.to_data_list()
            for i, sample in enumerate(samples):
                expected_x = torch.as_tensor(sample['Z'].astype(np.int64)-1, device='cuda').reshape(-1, 1)
                expected_pos = torch.as_tensor(sample['pos'], dtype=torch.float32, device='cuda')
                for record in original[3*i:3*i+3]:
                    if not torch.equal(record.target_x, expected_x) or not torch.equal(record.target_pos, expected_pos):
                        raise ValueError('Baseline targets differ from source atom order/geometry')
            c['baseline_acceptance'] = dict(source_order=True, targets='element:topo,noise:geom,bond:clean',
                noise_sign='noisy minus clean', noise_loss_denominator='3*(0.1 Angstrom)^2 per atom',
                observed_counts=counts, component_denominator=sum(count>0 for count in counts.values()))
            (output/'configuration.json').write_text(json.dumps(c, indent=2)+'\n')
        return total, raw, counts, statistics

    def validate():
        model.eval()
        sums, counts = {}, {}
        diagnostics = dict(predicted_squared_error=0., zero_squared_error=0., atoms=0)
        groups = {}
        with torch.no_grad():
            for start in range(0, len(validation.rows), 32):
                selected = validation.rows[start:start+32]
                samples = [validation.read((int(row['molecule_index']), int(row[c['source']][0]),
                                             start+i)) for i, row in enumerate(selected)]
                _, raw, observed, statistics = calculate(samples, validation_pass=True)
                for name in diagnostics:
                    diagnostics[name] += statistics[name]
                for label, observed_group in statistics.get('groups', {}).items():
                    group = groups.setdefault(label, dict(predicted_squared_error=0., zero_squared_error=0., atoms=0))
                    for name in group:
                        group[name] += observed_group[name]
                for name, value in raw.items():
                    sums[name] = sums.get(name, 0.) + float(value) * observed[name]
                    counts[name] = counts.get(name, 0) + observed[name]
        model.train()
        result = {name: sums[name]/counts[name] if counts[name] else None for name in sums}
        for label, group in groups.items():
            sigma = float(label.removeprefix('sigma_')) if label.startswith('sigma_') else .1
            group['standardized_denoising_error'] = (group['predicted_squared_error']/(3*sigma**2*group['atoms'])
                                                       if group['atoms'] else None)
            group['relative_to_zero_displacement'] = relative_error(group)
        record = dict(samples=clock.samples_consumed, losses=result, counts=counts,
                 predicted_displacement_error_relative_to_zero=relative_error(diagnostics),
                 displacement_error_sums=diagnostics, descriptive_denoising_groups=groups)
        (output/('VAL_'+str(clock.samples_consumed)+'.json')).write_text(json.dumps(record, indent=2)+'\n')
        history.run.log({'validation/'+k: v for k, v in result.items() if v is not None},
                        step=clock.optimizer_updates)

    started = time.monotonic()
    success = False
    columns = ['samples', 'updates', 'total', 'element', 'noise', 'bond', 'preclip_norm', 'lr', 'seconds']
    try:
        with ProcessPoolExecutor(c['workers'], mp_context=multiprocessing.get_context('spawn'),
                                 initializer=init_reader,
                                 initargs=(c['root'], c['population'], c['source'], rotor_index)) as pool:
            with (output/'losses.csv').open('a' if c.get('resume') else 'w', buffering=1) as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                if stream.tell() == 0:
                    writer.writeheader()
                for samples, sampler_state in ordered_sample_batches(
                        pool, read_choice, data, clock, rng, 32, c['samples'], draw=draw):
                    before = clock.samples_consumed
                    lr = c['lr'] * sample_lr_ratio(before+len(samples), c['samples'], 'cosine')
                    for group in optimizer.param_groups:
                        group['lr'] = lr
                    optimizer.zero_grad(set_to_none=True)
                    total, raw, counts, _ = calculate(samples)
                    total.backward()
                    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), calibration.threshold,
                                                          error_if_nonfinite=True)
                    optimizer.step()
                    clock.advance(len(samples))
                    rng.bit_generator.state = deepcopy(sampler_state)
                    if calibration.observe(float(norm), clock.samples_consumed, samples_before=before):
                        (output/'clip_calibration.json').write_text(json.dumps(calibration.fitted_summary(), indent=2)+'\n')
                    elapsed = prior_seconds+time.monotonic()-started
                    row = dict(samples=clock.samples_consumed, updates=clock.optimizer_updates,
                                         total=float(total.detach()), element=float(raw['s_element'].detach()),
                                         noise=float(raw['s_noise'].detach()), bond=float(raw['s_bond'].detach()),
                                         preclip_norm=float(norm), lr=lr, seconds=elapsed)
                    writer.writerow(row)
                    history.log(row)
                    if clock.optimizer_updates % 1000 == 0:
                        print(json.dumps(dict(samples=clock.samples_consumed, updates=clock.optimizer_updates,
                                              total=float(total.detach()), seconds=elapsed)), flush=True)
                    if clock.optimizer_updates == 1000:
                        (output/'initial_throughput.json').write_text(json.dumps(dict(
                            samples=clock.samples_consumed, seconds=elapsed,
                            samples_per_second=(clock.samples_consumed/elapsed),
                            window='first1000 real optimizer updates; no separate benchmark'))+'\n')
                    if clock.samples_consumed % 500000 == 0:
                        training_rng = capture_rng_state()
                        validate()
                        restore_rng_state(training_rng)
                    handoff = read_request(c) if clock.samples_consumed < c['samples'] else None
                    if clock.samples_consumed % 1000000 == 0 or handoff:
                        checkpoint = output/('samples_'+str(clock.samples_consumed)+'.pt')
                        publish_checkpoint(dict(model=model.state_dict(), optimizer=optimizer.state_dict(),
                            configuration=c, architecture=architecture, clock=clock.state_dict(),
                            sampler_rng=rng.bit_generator.state, rng_state=capture_rng_state(),
                            clip_calibration=calibration.state_dict(),
                            elapsed_seconds=prior_seconds+time.monotonic()-started), checkpoint)
                        if handoff:
                            success = True
                            return finish_handoff(c, handoff, checkpoint, clock.state_dict())
        result = dict(status='TRAINING_COMPLETE_READOUT_PENDING', samples=clock.samples_consumed,
                      updates=clock.optimizer_updates, seconds=prior_seconds+time.monotonic()-started)
        (output/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
        history.run.summary.update(result)
        success = True
        return result
    finally:
        history.close(success)
        data.close()
        validation.close()
