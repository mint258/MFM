"""Six report-only TRAIN-inner finetunes specified by taskbook v3.

Use the already produced initial X/z cache for TRAIN feature normalization.
No new fixed-encoder pass, test split, early stopping or model selection.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

import torch

from .v2_disk import save_checkpoint, save_metadata_json
from .v2_s_training import s_model
from .v3_dev_evaluation import TaskSpec, task_rows, _prediction, error
from .v3_dev_evaluation_v2 import _pack, REPO
from .v3_dev_membership import GroupedTrainingView
from .v3_dev_readouts import FrozenFeatureProbe
from .v3_latent_evaluation import cached_rows
from .v3_latent_training import TrainingHistory


TASKS = ('exp.LogD', 'exp.Log_HLM_CLint', 'qm9.homo')


def finetune(c, *, store_factory):
    """One actual checkpoint/task run, with both encoder and head updated."""
    from torch_geometric.data import Batch, Data
    from torch_geometric.utils import to_dense_batch
    if c['task_id'] not in TASKS or c['readout'] not in ('R3', 'R2z'):
        raise ValueError('Use exactly the three specified tasks and original/new heads')
    if (c['seed'], c['epochs'], c['batch_size'], c['encoder_lr'], c['head_lr']) != (
            0, 30, 32, 1e-4, 1e-3):
        raise ValueError('Keep the taskbook finetuning recipe')
    checkpoint_path = Path(c['checkpoint'])
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    previous = checkpoint['configuration']
    if previous.get('condition', 'S') != 'P' or checkpoint['clock']['samples_consumed'] != 6_000_000:
        raise ValueError('Finetuning uses only the original/fresh P six-million checkpoints')
    specification = checkpoint.get('architecture', {}).get('backbone', {}).get('v3_latent')
    if c['readout'] == 'R2z':
        if previous.get('stage') != 'T2' or specification is None or specification['kind'] not in ('pma', 'lite_rec'):
            raise ValueError('New readout requires the actual fresh adopted module checkpoint')
    elif specification is not None:
        raise ValueError('Original R3 control must use the original C1 checkpoint')
    feature_root = Path(c['initial_feature_cache'])
    if feature_root.name != checkpoint_path.parent.name + '__' + checkpoint_path.stem:
        raise ValueError('Initial normalization cache must belong to this exact checkpoint')
    panel = json.loads((REPO / 'configs/dev_panel_v2.json').read_text())
    definition = next(item for item in panel['tasks'] if item['task_id'] == c['task_id'])
    task = TaskSpec(**{key: definition[key] for key in (
        'task_id', 'dataset_id', 'field', 'output_level', 'error_metric', 'pooling')})
    store = store_factory(c['store'])
    view = GroupedTrainingView(store, task.dataset_id,
        'official' if task.dataset_id == 'expansionrx' else '0', store.group_map)
    payload = torch.load(feature_root / (task.dataset_id + '.pt'), map_location='cpu', weights_only=True)
    cached = cached_rows(payload)
    train = task_rows(view, cached, task, role='train')
    held = task_rows(view, cached, task, role='train_inner_validation')
    initial_z = {r.molecule_uid: r.z for r in cached}
    direct = c['readout'] == 'R2z'
    features = (torch.stack([initial_z[r.source_member_uid] for r in train]).double()
                if direct else torch.cat([r.h0.double() for r in train]))
    mean, scale = features.mean(0), features.std(0, unbiased=False)
    scale = torch.where(scale > 1e-12, scale, torch.ones_like(scale))
    del features
    targets = torch.cat([r.targets[r.supervision_mask & r.candidate_mask].double() for r in train])
    if not len(targets):
        raise ValueError('No observed TRAIN optimization targets')
    target_mean = float(targets.mean())
    target_scale = float(targets.std(unbiased=False))
    target_scale = target_scale if target_scale > 1e-12 else 1.
    source = {}
    for role in ('train', 'train_inner_validation'):
        for index in view.view(role):
            sample = view.get(index, role=role)
            if sample.geometry_ready:
                source[sample.member_uid] = sample
    torch.manual_seed(0)
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model, _ = s_model(previous['distance_bias'], previous['views'],
        latent='none' if specification is None else specification['kind'],
        latent_config=specification)
    state = checkpoint['model']
    if any(name.startswith('structural.') for name in state):
        state = {name.removeprefix('structural.'): value for name, value in state.items()
                 if name.startswith('structural.')}
    model.load_state_dict(state)
    encoder = model.encoder.cuda()
    torch.manual_seed(0)
    head = FrozenFeatureProbe(train[0].h0.shape[1], readout='R2' if direct else 'R3',
        output_level='graph', n_ref=payload['n_ref'], mean=mean, scale=scale,
        direct_features=direct).cuda()
    optimizer = torch.optim.AdamW([
        dict(params=encoder.parameters(), lr=1e-4),
        dict(params=head.parameters(), lr=1e-3)], betas=(.9, .999),
        weight_decay=.01, eps=1e-8, foreach=False, fused=False)
    output = Path(c['output'])
    output.mkdir(parents=True, exist_ok=False)
    history = TrainingHistory(output, dict(c, selection_use=False, encoder_updated=True,
        source_roles=['train', 'train_inner_validation'], downstream_TEST_read=False))
    rng = torch.Generator(device='cpu').manual_seed(0)
    retained = tuple(r for r in train if bool((r.supervision_mask & r.candidate_mask).any()))

    def predict(rows):
        selected = [source[r.source_member_uid] for r in rows]
        batch = Batch.from_data_list([Data(x=r.x.reshape(-1, 1), pos=r.pos) for r in selected]).cuda()
        h = encoder.encode_atoms(batch)
        padded, mask = to_dense_batch(h, batch.batch)
        z = encoder.latent_module.last_z if direct else None
        return head(padded, mask, z)

    updates, samples, started, success = 0, 0, time.monotonic(), False
    try:
        for epoch in range(30):
            encoder.train()
            head.train()
            order = torch.randperm(len(retained), generator=rng).tolist()
            for start in range(0, len(order), 32):
                rows = tuple(retained[i] for i in order[start:start + 32])
                prediction = predict(rows)
                y = torch.cat([r.targets for r in rows]).cuda().float()
                valid = torch.cat([r.supervision_mask & r.candidate_mask for r in rows]).cuda()
                loss = torch.nn.functional.mse_loss(prediction[valid], (y[valid]-target_mean)/target_scale)
                if not bool(torch.isfinite(loss)):
                    raise FloatingPointError('Nonfinite finetuning loss')
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()
                updates += 1
                samples += len(rows)
                history.log(dict(total=float(loss.detach()), samples=samples, updates=updates,
                    epoch=epoch, lr_encoder=1e-4, lr_head=1e-3,
                    seconds=time.monotonic()-started, gpu_peak_bytes=torch.cuda.max_memory_allocated()))
        encoder.eval()
        head.eval()
        values = []
        with torch.no_grad():
            for start in range(0, len(held), 32):
                values.extend((predict(held[start:start+32])*target_scale+target_mean).cpu().tolist())
        prediction = _prediction(task, held, values)
        save_checkpoint(dict(prediction=_pack(prediction), encoder=encoder.state_dict(),
            head=head.state_dict(), configuration=c, optimizer=optimizer.state_dict(),
            torch_rng=torch.get_rng_state(), cuda_rng=torch.cuda.get_rng_state(),
            shuffle_rng=rng.get_state(), updates=updates, samples=samples,
            target_mean=target_mean, target_scale=target_scale), output / 'final.pt')
        save_metadata_json(dict(status='COMPLETE_REPORT_ONLY', task_id=task.task_id,
            readout=c['readout'], mae=error(prediction), unit=definition['unit'],
            checkpoint=str(checkpoint_path), epochs=30, updates=updates, samples=samples,
            seconds=time.monotonic()-started, selection_use=False, encoder_updated=True,
            initial_feature_normalization='existing_checkpoint_cache_TRAIN_only_fixed_during_finetune',
            normalization_fit_scope='train', n_ref=payload['n_ref'],
            source_roles=['train', 'train_inner_validation'], downstream_TEST_read=False),
            output / 'summary.json')
        success = True
    finally:
        history.close(success)
