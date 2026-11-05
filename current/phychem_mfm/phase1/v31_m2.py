"""The two taskbook-v2 real-data acceptance runs; no auxiliary smoke suite."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import time
import numpy as np
import torch

from .v2_disk import save_checkpoint

from .v31_loader import MFM4Dataset, collate_samples
from .v31_training import V31PDModel


class FieldMoments:
    def __init__(self):
        self.rows = {}

    def add(self, name, prediction, target):
        p, y = np.asarray(prediction, dtype=np.float64), np.asarray(target, dtype=np.float64)
        valid = ~np.isnan(y)
        if not np.isfinite(p[valid]).all():
            raise FloatingPointError('Nonfinite observed prediction: ' + name)
        row = self.rows.setdefault(name, {key: np.zeros(y.shape[-1], dtype=np.float64)
            for key in ('n', 'mean', 'm2', 'sse', 'sae')})
        n = valid.sum(0)
        mean = np.divide(np.where(valid, y, 0.).sum(0), n, out=np.zeros(y.shape[-1]), where=n > 0)
        centered = np.where(valid, y - mean, 0.)
        combined = row['n'] + n
        delta = mean - row['mean']
        row['m2'] += (centered ** 2).sum(0) + np.divide(delta ** 2 * row['n'] * n,
            combined, out=np.zeros_like(combined), where=combined > 0)
        row['mean'] += np.divide(delta * n, combined, out=np.zeros_like(combined), where=combined > 0)
        error = np.where(valid, p - y, 0.)
        row['n'] = combined
        row['sse'] += (error ** 2).sum(0)
        row['sae'] += np.abs(error).sum(0)

    def results(self):
        rows = []
        for name, x in self.rows.items():
            sst = float(x['m2'].sum())
            count = int(x['n'].sum())
            score = 1. - float(x['sse'].sum()) / sst if sst > 0. else None
            rows.append(dict(field=name, valid_components=count, R2=score,
                MAE=float(x['sae'].sum()) / count if count else None,
                passed=score is not None and score >= .95))
        return rows


@torch.no_grad()
def overfit_metrics(model, samples, batch_size):
    model.eval()
    moments = FieldMoments()
    for start in range(0, len(samples), batch_size):
        batch = samples[start:start + batch_size]
        predictions = model.original_predictions(model.predict(batch), batch)
        for name, value in predictions.items():
            moments.add(name, value.detach().cpu().numpy(),
                        np.concatenate([s['targets'][name].raw for s in batch]))
    model.train()
    return moments.results()


def save_metrics(path, rows):
    with Path(path).open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['field', 'valid_components', 'R2', 'MAE', 'passed'])
        writer.writeheader()
        writer.writerows(rows)


def run_m2(*, root, training_view, normalizations, output, mode,
           overfit_updates=10_000, batch_size=8, seed=0, lr=3e-4):
    """Use exactly 1,000 overfit molecules, then one 2,000-step SDP run.

    The overfit optimizer updates all enabled heads and the shared backbone;
    every training-view field receives its own original-unit R²/MAE result.
    """
    from .v2_s_training import s_model
    from .v3_structural import build_structural_views, StructuralViewConfig
    from ..training.losses import LossWeights
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    view = json.loads(Path(training_view).read_text())
    if view.get('status') != 'FROZEN_BEFORE_STAGE5_PD':
        raise ValueError('Use the formally frozen data-line training view')
    norms = json.loads(Path(normalizations).read_text())
    dataset = MFM4Dataset(root, training_view=view, normalizations=norms)
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    structural, configuration = s_model('C1-0', 'three')
    pd = V31PDModel(structural.encoder, dataset.view)
    structural, pd = structural.cuda().train(), pd.cuda().train()
    # Shared encoder parameters appear once in the optimizer.
    combined = torch.nn.ModuleDict(dict(structural=structural, pd=pd))
    parameters = list(combined.parameters())
    optimizer = torch.optim.AdamW(parameters, lr=lr, betas=(.9, .95))
    recipe = dict(mode=mode, root=str(root), training_view=str(training_view),
        normalizations=str(normalizations), seed=seed, lr=lr, betas=[.9, .95],
        clip=1., batch_size=batch_size, model=configuration,
        enabled_training_view_columns=len(pd.registry.fields), physical_loss_fields=len(pd.head_registry.fields),
        overfit_molecules=1000 if mode == 'overfit' else None,
        updates=overfit_updates if mode == 'overfit' else 2000)
    (output/'configuration.json').write_text(json.dumps(recipe, indent=2) + '\n')
    fixed = None
    if mode == 'overfit':
        indices = rng.choice(dataset.indices, 1000, replace=False)
        fixed = [dataset.read(int(i), int(dataset.choices(int(i))[0])) for i in indices]
    elif mode != 'sdp':
        raise ValueError('M2 mode must be overfit or sdp')
    started = time.monotonic()
    history, metrics = [], None
    field_names = tuple(f.name for f in pd.registry.fields)
    with (output/'losses.csv').open('w', buffering=1) as file:
        writer = csv.DictWriter(file, fieldnames=['updates', 'samples', 'total', 'S', 'D', 'P',
                                                  'preclip_norm', 'seconds'])
        writer.writeheader()
        for step in range(1, recipe['updates'] + 1):
            samples = ([fixed[int(i)] for i in rng.integers(1000, size=batch_size)] if fixed is not None else
                       [dataset.sample(rng) for _ in range(batch_size)])
            optimizer.zero_grad(set_to_none=True)
            s_loss = None
            if mode == 'sdp':
                clean = collate_samples(samples)
                views = build_structural_views(clean, ordinals=tuple(range((step-1)*batch_size,
                    step*batch_size)), config=StructuralViewConfig(seed=seed)).to('cuda')
                s_prediction = structural.forward_pretrain(views, enabled_groups=('S',))
                s_loss = structural.compute_loss(s_prediction, views, {}, {}, enabled_groups=('S',),
                    weights=LossWeights(), exposure_step=step-1)
                prediction = pd.predict(samples, clean_features=s_prediction.clean_h0,
                                        clean_batch=clean.to('cuda'))
            else:
                prediction = pd.predict(samples)
            loss = pd.loss(prediction, samples)
            total = loss.total if s_loss is None else torch.stack([
                s_loss.groups['S'], loss.groups['D'], loss.groups['P']]).mean()
            total.backward()
            norm = torch.nn.utils.clip_grad_norm_(parameters, 1.)
            optimizer.step()
            row = dict(updates=step, samples=step*batch_size, total=float(total.detach()),
                S=None if s_loss is None else float(s_loss.groups['S'].detach()),
                D=float(loss.groups['D'].detach()), P=float(loss.groups['P'].detach()),
                preclip_norm=float(norm), seconds=time.monotonic()-started)
            writer.writerow(row)
            history.append(row)
            if mode == 'overfit' and (step % 500 == 0 or step == recipe['updates']):
                metrics = overfit_metrics(pd, fixed, batch_size)
                if set(row['field'] for row in metrics) != set(field_names):
                    raise ValueError('A frozen enabled field is absent from the actual overfit result')
                save_metrics(output/'per_head_metrics.csv', metrics)
                passed = sum(row['passed'] for row in metrics)
                print(f'overfit updates={step} fields_R2_ge_0.95={passed}/{len(metrics)}', flush=True)
                if passed == len(metrics):
                    break
            elif step % 100 == 0:
                print(json.dumps(row), flush=True)
    summary = dict(recipe, actual_updates=step, actual_samples=step*batch_size,
        seconds=time.monotonic()-started, gpu_peak_bytes=torch.cuda.max_memory_allocated())
    if mode == 'overfit':
        summary.update(status='OVERFIT_REPORTED', enabled_fields=len(field_names),
            failed_fields=[row for row in metrics if not row['passed']],
            all_fields_passed=all(row['passed'] for row in metrics))
    else:
        trend = {group: dict(first100=float(np.mean([row[group] for row in history[:100]])),
                            last100=float(np.mean([row[group] for row in history[-100:]])))
                 for group in ('S', 'D', 'P')}
        for value in trend.values():
            value['decreasing'] = value['last100'] < value['first100']
        summary.update(status='SDP_2000_STEPS_REPORTED', group_trend=trend,
                       all_groups_decreasing=all(v['decreasing'] for v in trend.values()))
    save_checkpoint(dict(model=combined.state_dict(), optimizer=optimizer.state_dict(),
        configuration=recipe, updates=step, rng=rng.bit_generator.state,
        torch_rng=torch.get_rng_state(), cuda_rng=torch.cuda.get_rng_state()), output/'final.pt')
    (output/'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    dataset.close()
    return summary
