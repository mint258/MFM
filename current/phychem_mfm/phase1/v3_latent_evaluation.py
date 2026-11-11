"""Frozen X/z evaluation for the explicitly specified latent experiments."""
from dataclasses import dataclass, replace
import fcntl
import json
import os
from pathlib import Path
import time

import torch

from .v2_s_training import s_model
from .v3_dev_panel import MoleculeH0
from .v3_dev_membership import GroupedTrainingView
from .v3_dev_evaluation import (TaskSpec, task_rows, ridge_probe, mlp_pooled_probe,
                               deep_atom_probe, compare_panel, error)
from .v3_dev_evaluation_v2 import (_save_once, _json, _pack, _unpack, _cached_rows,
                                   ProbeHistory, REPO, BASE, DATASETS)
from .v3_latent_training import TrainingHistory


@dataclass(frozen=True)
class LatentH0(MoleculeH0):
    z: object = None


def encoded_rows(encoder, view, encode):
    module = getattr(encoder, 'latent_module', None)
    if module is None or not module.has_z:
        return encode(encoder, view)
    latent = []
    def capture(backbone, args, output):
        latent.extend(module.last_z.detach().cpu().float().unbind(0))
    handle = encoder.backbone.register_forward_hook(capture)
    try:
        rows = encode(encoder, view)
    finally:
        handle.remove()
    if len(latent) != len(rows):
        raise ValueError('The same encoder pass must supply one z per ordered molecule')
    return [LatentH0(r.molecule_uid, r.member_index, r.h0, r.source_atom_ids, z)
            for r, z in zip(rows, latent)]


def cached_rows(payload):
    return [LatentH0(r['molecule_uid'], r['member_index'], r['h0'], r['source_atom_ids'], r.get('z'))
            for r in payload['records']]


def z_rows(rows, cached):
    values = {r.molecule_uid: r.z for r in cached}
    if any(values[r.source_member_uid] is None for r in rows):
        raise ValueError('Molecular z must come from the same frozen geometry as X')
    return tuple(replace(r, graph_features=values[r.source_member_uid]) for r in rows)


def feature_cache(model, views, encode, destination):
    destination = Path(destination)
    for dataset, view in views.items():
        path = destination / (dataset + '.pt')
        if path.exists():
            continue
        rows = encoded_rows(model.encoder, view, encode)
        optimization = set(view.view('train'))
        sizes = [len(r.h0) for r in rows if r.member_index in optimization]
        payload = dict(n_ref=sum(sizes)/len(sizes), records=[dict(molecule_uid=r.molecule_uid,
            member_index=r.member_index, h0=r.h0, source_atom_ids=r.source_atom_ids,
            z=getattr(r, 'z', None)) for r in rows])
        _save_once(payload, path)


def _probe(name, train, validation, task, n_ref, history, path):
    if path.exists():
        return str(path)
    if name.startswith('R1'):
        prediction, detail = ridge_probe(train, validation, task)
    else:
        probe = deep_atom_probe if name == 'R3' else mlp_pooled_probe
        prediction, detail = probe(train, validation, task, n_ref=n_ref,
            seed=0, device='cuda', tracker=history)
    _save_once(dict(prediction=_pack(prediction), detail=detail), path)
    history.log({'readout/native_error': error(prediction)}, step=detail.get('updates', 0), commit=True)
    return str(path)


def _base_r1(views, tasks, root, history):
    """Materialize missing R1 reference predictions once for NEW paired contrasts.

    The completed C1 R1 scores remain quoted unchanged. Old v1 persisted scores,
    not the per-record predictions needed by the newly requested R1z contrast.
    """
    destination = root / 'base_reference_R1'
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / 'producer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest = destination / 'predictions.json'
        if manifest.exists():
            return json.loads(manifest.read_text())['files']
        files = {}
        for dataset, view in views.items():
            payload = torch.load(BASE / 'h0_cache/random__C1-0__three' / (dataset + '.pt'),
                                 map_location='cpu', weights_only=True)
            cached = _cached_rows(payload)
            for task in (t for t in tasks if t.dataset_id == dataset):
                train = task_rows(view, cached, task, role='train')
                validation = task_rows(view, cached, task, role='train_inner_validation')
                history.cell = 'reference/X/' + task.task_id + '/R1'
                files[task.task_id + '/R1'] = _probe('R1', train, validation, task, payload['n_ref'],
                    history, destination / 'probes' / (task.task_id.replace('.', '_') + '__R1.pt'))
        _json(dict(files=files, purpose='new latent R1/R1z paired predictions; no C1 score replacement'), manifest)
        return files


def _z_reference(spec, config, views, tasks, root, encode, history):
    # Decoder/loss weight do not enter z. Both lite kinds have identical ordered
    # read/self/write and z initializations; write gates are exactly zero.
    profile = ('pma' if spec['kind'] == 'pma' else 'lite') + '_k' + str(spec['k']) + '_write' + str(int(spec['write_back']))
    destination = root / ('reference_z_' + profile)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / 'producer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest = destination / 'predictions.json'
        if manifest.exists():
            return json.loads(manifest.read_text())['files']
        torch.manual_seed(20261025)
        model, _ = s_model(config['distance_bias'], config['views'], latent=spec['kind'], latent_config=spec)
        model = model.cuda().eval()
        cache = destination / 'features'
        feature_cache(model, {d: v for d, v in views.items() if d != 'cyp_isoform'}, encode, cache)
        del model
        torch.cuda.empty_cache()
        files = {}
        for dataset, view in views.items():
            if dataset == 'cyp_isoform':
                continue
            payload = torch.load(cache / (dataset + '.pt'), map_location='cpu', weights_only=True)
            cached = cached_rows(payload)
            for task in (t for t in tasks if t.dataset_id == dataset):
                train = z_rows(task_rows(view, cached, task, role='train'), cached)
                validation = z_rows(task_rows(view, cached, task, role='train_inner_validation'), cached)
                for name in ('R1z', 'R2z'):
                    history.cell = 'reference/' + profile + '/' + task.task_id + '/' + name
                    files[task.task_id + '/' + name] = _probe(name, train, validation, task,
                        payload['n_ref'], history, destination / 'probes' / (task.task_id.replace('.', '_') + '__' + name + '.pt'))
        _json(dict(files=files, z_profile=profile, actual_initialization_spec=spec,
            seed=20261025, S_P_shared=True), manifest)
        return files


def produce(args, checkpoint, *, store_factory, encode):
    config = checkpoint['configuration']
    if config['distance_bias'] != 'C1-0':
        raise ValueError('Latent experiments start from the selected C1-0')
    output, root = Path(args.output), Path(args.cache_root)
    output.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    architecture = checkpoint['architecture']
    spec = architecture['backbone'].get('v3_latent')
    has_z = spec is not None and spec['kind'] in ('pma', 'lite', 'lite_rec')
    _json(dict(checkpoint=str(args.checkpoint), stage=config['stage'], arm=config['arm'],
        condition=config['condition'], panel='v2', cache_root=str(root)), output / 'configuration.json')
    store = store_factory(args.store)
    views = {dataset: GroupedTrainingView(store, dataset,
        'official' if dataset == 'expansionrx' else '0', store.group_map) for dataset in DATASETS}
    panel = json.loads((REPO / 'configs/dev_panel_v2.json').read_text())
    tasks = [TaskSpec(**{k: item[k] for k in
        ('task_id', 'dataset_id', 'field', 'output_level', 'error_metric', 'pooling')}) for item in panel['tasks']]
    history_owner = TrainingHistory(output, dict(checkpoint=str(args.checkpoint), stage=config['stage'],
        condition=config['condition'], arm=config['arm'], panel='v2', pretrained_encoder_frozen=True))
    history = ProbeHistory(history_owner.stream, history_owner.run)
    torch.set_num_threads(16)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    completed, started = False, time.monotonic()
    try:
        references = _base_r1(views, tasks, root, history)
        baseline = json.loads((BASE / 'reference/C1-0/predictions.json').read_text())['files']
        references.update(baseline)
        if has_z:
            references.update(_z_reference(spec, config, views, tasks, root, encode, history))
        cache = root / (Path(args.checkpoint).parent.name + '__' + Path(args.checkpoint).stem)
        if not all((cache / (dataset + '.pt')).exists() for dataset in DATASETS):
            model, _ = s_model(config['distance_bias'], config['views'],
                latent='none' if spec is None else spec['kind'], latent_config=spec)
            state = checkpoint['model']
            if any(key.startswith('structural.') for key in state):
                state = {key.removeprefix('structural.'): value for key, value in state.items()
                         if key.startswith('structural.')}
            model.load_state_dict(state)
            model = model.cuda().eval()
            feature_cache(model, views, encode, cache)
            del model
            torch.cuda.empty_cache()
        files = {}
        for dataset, view in views.items():
            payload = torch.load(cache / (dataset + '.pt'), map_location='cpu', weights_only=True)
            cached = cached_rows(payload)
            for task in (t for t in tasks if t.dataset_id == dataset):
                train = task_rows(view, cached, task, role='train')
                validation = task_rows(view, cached, task, role='train_inner_validation')
                for name in ('R1', 'R2', 'R3') + (('R1z', 'R2z') if has_z else ()):
                    key = task.task_id + '/' + name
                    if task.output_level == 'atom' and name in ('R3', 'R1z', 'R2z'):
                        original = 'R1' if name == 'R1z' else 'R2'
                        files[key] = files[task.task_id + '/' + original]
                        if name.endswith('z'):
                            references[key] = references[task.task_id + '/' + original]
                        continue
                    fit, held = (z_rows(train, cached), z_rows(validation, cached)) if name.endswith('z') else (train, validation)
                    history.cell = config['stage'] + '/' + config['arm'] + '/' + config['condition'] + '/' + key
                    files[key] = _probe(name, fit, held, task, payload['n_ref'], history,
                        output / 'probes' / (task.task_id.replace('.', '_') + '__' + name + '.pt'))
        _json(dict(files=files, reference_files=references, architecture=architecture,
            checkpoint=str(args.checkpoint), condition=config['condition'], stage=config['stage'], arm=config['arm'],
            has_z=has_z, primary='R2z' if has_z else 'R3', source_roles=['train', 'train_inner_validation'],
            downstream_TEST_read=False), output / 'predictions.json')
        completed = True
    finally:
        history_owner.close(completed)
    _json(dict(status='PREDICTIONS_COMPLETE', seconds=time.monotonic()-started), output / 'producer_complete.json')


def score(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'predictions.json').read_text())
    summaries = {}
    for name in ('R1', 'R2', 'R3') + (('R1z', 'R2z') if manifest['has_z'] else ()):
        path = directory / (name + '_summary.json')
        if path.exists():
            summaries[name] = json.loads(path.read_text())
            continue
        actual, reference = {}, {}
        for key, source in manifest['files'].items():
            if not key.endswith('/' + name):
                continue
            task = key.rsplit('/', 1)[0]
            actual[task] = _unpack(torch.load(source, map_location='cpu', weights_only=True)['prediction'])
            reference[task] = _unpack(torch.load(manifest['reference_files'][key],
                map_location='cpu', weights_only=True)['prediction'])
        identity = 'C1-0:matched-initial-encoder-function:' + name
        summary = compare_panel(actual, reference, architecture_sha256=identity,
            reference_architecture_sha256=identity, retain_paired_samples=True, retain_task_samples=True)
        summary.update(readout=name, primary=name == manifest['primary'], downstream_TEST_read=False)
        _json(summary, path)
        summaries[name] = summary
    _json(dict(stage=manifest['stage'], arm=manifest['arm'], condition=manifest['condition'],
        primary=manifest['primary'], means={name: row['mean_normalized_improvement'] for name, row in summaries.items()},
        source_roles=['train', 'train_inner_validation'], downstream_TEST_read=False), directory / 'summary.json')
    return summaries
