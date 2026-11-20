"""Reuse P's frozen probes, placing the CPU ridge fit on CPU nodes.

One GPU feature production serves both readouts. R3 stays on the GPU; R1 uses
the same saved H and original ridge_probe on CPU8..19, before original scoring.
"""
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import time

import torch

from phychem_mfm.phase1.p_recipe_handoff import publish_checkpoint
from runtime import CONTROL, REPO, write


def existing_evaluation():
    spec = importlib.util.spec_from_file_location('s_existing_evaluate', REPO/'tools/p_recipe/evaluate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context(e):
    panel = json.loads((REPO/'configs/dev_panel_v3.json').read_text())
    tasks = [replace(e.TaskSpec(**{key: item[key] for key in
        ('task_id', 'dataset_id', 'field', 'output_level', 'error_metric', 'pooling')}), pooling='mean')
        for item in panel['tasks']]
    return tasks


def views(e, store_path):
    store = e.TrainOnlyPackedStore(store_path, verify_digests=False)
    return {name: e.GroupedTrainingView(store, name, 'official' if name == 'expansionrx' else '0', store.group_map)
            for name in ('expansionrx', 'cyp_isoform', 'qm9')}


def ensure_features(e, c, dataset, view):
    target = e.feature_path(c, dataset)
    if target.is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    pending = target.with_name(target.name+'.writing.'+str(os.getpid())+'.'+str(time.time_ns()))
    temporary = dict(c, features={dataset: str(pending)}, persist_features=True)
    e.produce_missing_features(temporary, dataset, view)
    # A failed producer leaves its partial for diagnosis; readers only see a
    # closed final name after its successful serialization.
    pending.replace(target)
    return target


def configuration(c, samples):
    output = Path(c['output'])/('readout' if samples == c['samples'] else 'readout_'+str(samples))
    return dict(c, samples=samples, output=str(output), layer=6,
        checkpoint=str(Path(c['output'])/('samples_'+str(samples)+'.pt')),
        features=str(CONTROL/'scratch/readout_features'/c['run']/str(samples)),
        store=c['evaluation_store'], persist_features=True)


def gpu(c):
    output = Path(c['output'])
    output.mkdir(parents=True, exist_ok=True)
    if (output/'predictions.json').is_file():
        return
    e = existing_evaluation()
    tasks = context(e)
    datasets = views(e, c['store'])
    history = e.History(output/'probe_history.jsonl')
    torch.set_num_threads(16)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    files, details, label_stds = {}, {}, {}
    for dataset, view in datasets.items():
        path = ensure_features(e, c, dataset, view)
        payload = torch.load(path, map_location='cpu', weights_only=True)
        cached = e.cached_rows(payload)
        for task in (task for task in tasks if task.dataset_id == dataset):
            rows = e.atomization_rows if task.task_id == e.ATOMIZATION_TASK_ID else e.task_rows
            train = rows(view, cached, task, role='train')
            validation = rows(view, cached, task, role='train_inner_validation')
            labels = torch.cat([row.targets[row.supervision_mask & row.candidate_mask].double() for row in train])
            label_stds[task.task_id] = float(labels.std(unbiased=False))
            key = task.task_id+'/R3'
            destination = output/(task.task_id.replace('.', '_')+'__R3.pt')
            if not destination.is_file():
                history.cell = key
                prediction, detail = e.run_probe(train, validation, task, readout='R3',
                    n_ref=payload['n_ref'], seed=0, device='cuda', tracker=history,
                    relative_std_floor=True, internal_epoch_selection=True)
                publish_checkpoint(dict(prediction=e._pack(prediction), detail=detail), destination)
            result = torch.load(destination, map_location='cpu', weights_only=True)
            files[key] = str(destination)
            details[key] = {name: value for name, value in result['detail'].items() if name != 'state_dict'}
            print(json.dumps(dict(run=c['run'], cell=key, error=e.error(e._unpack(result['prediction'])))), flush=True)
    write(output/'predictions.json', dict(run=c['run'], files=files, details=details,
        label_stds=label_stds, stage=c['stage'], round=c['round'], arm=c['arm'], samples=c['samples'],
        protocol='p_recipe', source_roles=['train', 'train_inner_validation'],
        features=c['features'], store=c['store'], readout_backends=dict(R3='cuda', R1='CPU_PENDING')))


def finish_cpu_ridge(c, samples, *, settings=None):
    """Called only by the admitted CPU statistics worker, never on GPU hosts."""
    settings = configuration(c, samples) if settings is None else settings
    output = Path(settings['output'])
    manifest = json.loads((output/'predictions.json').read_text())
    if manifest.get('readout_backends', {}).get('R1') == 'cpu':
        return
    e = existing_evaluation()
    datasets = views(e, settings['store'])
    torch.set_num_threads(1)
    for dataset, view in datasets.items():
        payload = torch.load(e.feature_path(settings, dataset), map_location='cpu', weights_only=True)
        cached = e.cached_rows(payload)
        for task in (task for task in context(e) if task.dataset_id == dataset):
            rows = e.atomization_rows if task.task_id == e.ATOMIZATION_TASK_ID else e.task_rows
            train = rows(view, cached, task, role='train')
            validation = rows(view, cached, task, role='train_inner_validation')
            key = task.task_id+'/R1'
            destination = output/(task.task_id.replace('.', '_')+'__R1.pt')
            if not destination.is_file():
                prediction, detail = e.ridge_probe(train, validation, task, relative_std_floor=True)
                publish_checkpoint(dict(prediction=e._pack(prediction), detail=detail), destination)
            result = torch.load(destination, map_location='cpu', weights_only=True)
            manifest['files'][key] = str(destination)
            manifest['details'][key] = {name: value for name, value in result['detail'].items() if name != 'state_dict'}
            print(json.dumps(dict(run=c['run'], cell=key, error=e.error(e._unpack(result['prediction'])))), flush=True)
    manifest['readout_backends']['R1'] = 'cpu'
    write(output/'predictions.json', manifest)


def release_closed_feature_cache(c):
    """Dispose only this producer's reconstructible, closed scratch H files.

    The caller has completed both readouts and their original bootstrap. Raw
    predictions, checkpoints, metadata and failed partials are all retained.
    """
    owned = CONTROL.resolve()
    raw_base = CONTROL/'scratch/readout_features'
    base = raw_base.resolve()
    if (not base.is_relative_to(owned) or raw_base.is_symlink()
            or (CONTROL/'scratch').is_symlink()):
        raise ValueError('Feature cache base escaped S scratch')
    run = base/c['run']
    if run.parent.resolve() != base or run.is_symlink():
        raise ValueError('Feature cache run must be directly inside S scratch')
    removed, released = 0, 0
    for samples in c['evaluation_samples']:
        directory = run/str(samples)
        if directory.is_symlink() or directory.parent.resolve() != run.resolve():
            raise ValueError('Feature cache directory escaped its registered run')
        for dataset in ('expansionrx', 'cyp_isoform', 'qm9'):
            path = directory/(dataset+'.pt')
            if path.is_symlink() or path.parent.resolve() != directory.resolve():
                raise ValueError('Feature cache path escaped S scratch')
            if path.is_file():
                observed = path.stat()
                if observed.st_uid != os.getuid():
                    raise ValueError('Closed H scratch file belongs to another UID')
                size = observed.st_size
                path.unlink()
                removed += 1
                released += size
    return dict(status='CLOSED_H_SCRATCH_RELEASED_AFTER_R1_R3_AND_BOOTSTRAP',
                files=removed, bytes=released, failed_partials_preserved=True)
