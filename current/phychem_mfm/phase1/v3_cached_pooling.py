"""T0-2: four fixed atom statistics from the already produced target-free H0."""
from dataclasses import replace
import json
import os
from pathlib import Path
import time

import numpy as np
import torch

from .v2_disk import save_metadata_json
from .v3_dev_membership import GroupedTrainingView
from .v3_dev_evaluation import (TaskSpec, task_rows, ridge_probe, mlp_pooled_probe,
                               compare_panel, error)
from .v3_dev_evaluation_v2 import (_cached_rows, _save_once, _pack, _unpack,
                                   ProbeHistory, DATASETS)


def four_statistics(rows, n_ref):
    result = []
    for row in rows:
        h = row.h0
        feature = torch.cat((h.mean(0), h.sum(0) / n_ref, h.max(0).values,
                             h.std(0, unbiased=False)))
        result.append(replace(row, graph_features=feature))
    return tuple(result)


def evaluate_cached_pooling(c, *, store_factory):
    """One production, no encoder invocation or new data split."""
    from .v3_latent_training import TrainingHistory
    from .v3_dev_evaluation_v2 import REPO
    output = Path(c['output'])
    output.mkdir(parents=True, exist_ok=False)
    save_metadata_json(c, output / 'configuration.json')
    store = store_factory(c['store'])
    views = {dataset: GroupedTrainingView(store, dataset,
        'official' if dataset == 'expansionrx' else '0', store.group_map) for dataset in DATASETS}
    panel = json.loads((REPO / 'configs/dev_panel_v2.json').read_text())
    tasks = [TaskSpec(**{k: item[k] for k in
        ('task_id', 'dataset_id', 'field', 'output_level', 'error_metric', 'pooling')})
        for item in panel['tasks']]
    threads = max(1, min(16, int(os.environ.get('SLURM_CPUS_PER_TASK', '16'))))
    torch.set_num_threads(threads)
    tracker = TrainingHistory(output, dict(c, selection_use=False, torch_threads=threads))
    history = ProbeHistory(tracker.stream, tracker.run)
    completed, started = False, time.monotonic()
    packets, files = {}, {}
    try:
        for label in ('reference', 'S', 'P'):
            packets[label], files[label] = {'R1': {}, 'R2': {}}, {}
            destination = output / label
            for dataset in DATASETS:
                if dataset == 'cyp_isoform':
                    continue  # Atom readouts are unchanged: reuse their existing results below.
                payload = torch.load(Path(c['cache_directories'][label]) / (dataset + '.pt'),
                                     map_location='cpu', weights_only=True)
                cached = _cached_rows(payload)
                for task in (t for t in tasks if t.dataset_id == dataset):
                    train = four_statistics(task_rows(views[dataset], cached, task, role='train'), payload['n_ref'])
                    validation = four_statistics(task_rows(views[dataset], cached, task,
                        role='train_inner_validation'), payload['n_ref'])
                    for name in ('R1', 'R2'):
                        history.cell = label + '/' + task.task_id + '/' + name
                        if name == 'R1':
                            prediction, detail = ridge_probe(train, validation, task)
                        else:
                            prediction, detail = mlp_pooled_probe(train, validation, task,
                                n_ref=payload['n_ref'], seed=0, device=c.get('device', 'cpu'), tracker=history)
                        path = destination / 'probes' / (task.task_id.replace('.', '_') + '__' + name + '.pt')
                        _save_once(dict(prediction=_pack(prediction), detail=detail), path)
                        packets[label][name][task.task_id] = prediction
                        files[label][task.task_id + '/' + name] = str(path)
                        history.log({'readout/native_error': error(prediction)}, step=detail.get('updates', 0), commit=True)
            save_metadata_json(dict(files=files[label], selection_use=False,
                representation='mean|sum/N_ref|max|population_std', checkpoint=c['checkpoints'].get(label)),
                destination / 'predictions.json')
        rows = []
        for label in ('S', 'P'):
            manifest = json.loads(Path(c['existing_v2_predictions'][label]).read_text())
            ref = json.loads(Path(c['existing_v2_predictions']['reference']).read_text())
            for task in (t for t in tasks if t.output_level == 'atom'):
                key = task.task_id + '/R2'
                packets[label]['R2'][task.task_id] = _unpack(torch.load(manifest['files'][key],
                    map_location='cpu', weights_only=True)['prediction'])
                if task.task_id not in packets['reference']['R2']:
                    packets['reference']['R2'][task.task_id] = _unpack(torch.load(ref['files'][key],
                        map_location='cpu', weights_only=True)['prediction'])
            summaries = {}
            for name in ('R1', 'R2'):
                summary = compare_panel(packets[label][name], packets['reference'][name],
                    architecture_sha256='C1-0:three:four_statistics',
                    reference_architecture_sha256='C1-0:three:four_statistics')
                if name == 'R1':
                    legacy = json.loads(Path(c['legacy_summaries'][label]).read_text())
                    atom = {key: value for key, value in legacy['tasks'].items()
                            if key.startswith('cyp.') and key.endswith('/ridge')}
                    if len(atom) != 2:
                        raise ValueError('Both original SoM ridge cells must be reused')
                    summary['unchanged_atom_cells'] = atom
                    summary['nine_task_mean'] = float(np.mean(
                        [value['normalized_improvement'] for value in summary['tasks'].values()] +
                        [value['normalized_improvement'] for value in atom.values()]))
                    summary['bootstrap_scope'] = 'seven graph tasks only; old two atom cells reused without retraining'
                else:
                    summary['nine_task_mean'] = summary['mean_normalized_improvement']
                    summary['bootstrap_scope'] = 'all nine tasks; original R2 SoM predictions reused'
                summary['selection_use'] = False
                save_metadata_json(summary, output / (label + '_' + name + '_summary.json'))
                summaries[name] = summary
            rows.append(dict(condition=label, R1=summaries['R1']['nine_task_mean'],
                             R2=summaries['R2']['nine_task_mean']))
        save_metadata_json(dict(status='T0_2_FOUR_STATISTICS_COMPLETE', rows=rows,
            selection_use=False, source_roles=['train', 'train_inner_validation'], downstream_TEST_read=False,
            seconds=time.monotonic()-started), output / 'summary.json')
        completed = True
    finally:
        tracker.close(completed)
