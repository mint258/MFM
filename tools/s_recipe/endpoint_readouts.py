"""Endpoint-only descriptive layer curves using the original encoder/probes."""
import argparse
import json
import os
from pathlib import Path
import socket

import torch

import readouts
from representations import registered
from runtime import CONTROL, capacity, write


def settings(c, layer):
    base = readouts.configuration(c, 3000000)
    if layer == 6:
        return base  # Reuse the formal H0 predictions, without refitting.
    return dict(base, layer=layer,
                output=str(Path(c['output'])/'diagnostic_readouts'/('layer_'+str(layer))),
                features=str(CONTROL/'scratch/readout_features'/c['run']/'endpoint_layers'/str(layer)))


def layer_payload(payload, chunks):
    """Keep the original source/MID ordering; replace only the captured H."""
    h = torch.cat(chunks)
    records, offset = [], 0
    for row in payload['records']:
        count = len(row['h0'])
        records.append(dict(row, h0=h[offset:offset+count]))
        offset += count
    if offset != len(h):
        raise ValueError('Captured layer atom count differs from the producer records')
    return dict(payload, records=records)


def predefined_terminal(c, samples):
    """Only the two endpoints known before recipe selection get early caches."""
    return (samples == c['samples'] == 3000000 and c['seed'] == 0
            and c['arm'] in ('S-B0', 'S-G1'))


def features(c, dataset, view, e):
    import phychem_mfm.phase1.v2_s_training as training
    from phychem_mfm.phase1.p_recipe_handoff import publish_checkpoint
    paths = {layer: e.feature_path(settings(c, layer), dataset) for layer in range(1, 7)}
    summary = Path(c['output'])/'summary.json'
    formal_closed = (summary.is_file()
                     and json.loads(summary.read_text())['status'] == 'COMPLETE'
                     and (Path(settings(c, 6)['output'])/'scores.json').is_file())
    required = range(1, 6) if formal_closed else range(1, 7)
    if all(paths[layer].is_file() for layer in required):
        return
    original_factory = training.s_model
    captured = {layer: [] for layer in range(1, 6)}
    encoders = []

    def factory(*args, **kwargs):
        model, auxiliary = original_factory(*args, **kwargs)
        original_encode = model.encoder.encode_atoms

        def encode(batch, **unused):
            final, intermediate = original_encode(batch, return_intermediates=True)
            for layer in captured:
                captured[layer].append(intermediate[layer-1].detach().cpu().float())
            return final

        model.encoder.encode_atoms = encode
        encoders.append(model.encoder)
        return model, auxiliary

    # The original producer owns model construction, batching, source IDs and
    # canonical final H0. Capture intermediate returns within that same forward.
    # This worker does not run another encoder/probe thread; always restore the
    # factory, including when its own feature producer raises.
    capacity()
    temporary = dict(settings(c, 6), persist_features=False,
                     features={dataset: str(paths[1])+'.in_memory_producer'})
    training.s_model = factory
    try:
        payload = e.produce_missing_features(temporary, dataset, view)
    finally:
        training.s_model = original_factory
        for encoder in encoders:
            del encoder.encode_atoms  # Restore its class method; break the capture closure.
        encoders.clear()
    for layer in required:
        path = paths[layer]
        if path.is_file():
            continue
        capacity()
        path.parent.mkdir(parents=True, exist_ok=True)
        publish_checkpoint(payload if layer == 6 else layer_payload(payload, captured[layer]), path)


def capture(c):
    """Capture all registered layers in the original formal H0 forward."""
    if registered(c) != [1, 2, 3, 4, 5, 6]:
        raise ValueError('Endpoint layer curves require the frozen1..6 scope')
    e = readouts.existing_evaluation()
    for dataset, view in readouts.views(e, c['evaluation_store']).items():
        features(c, dataset, view, e)


def gpu(c):
    node = socket.gethostname().split('.')[0]
    if node not in {'compute-0-'+str(i) for i in (*range(8), 20, 22)}:
        raise ValueError('Endpoint readouts require an admitted GPU node')
    if node not in ('compute-0-20', 'compute-0-22') and not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('Small-group endpoint readouts require Slurm')
    capture(c)
    for layer in range(1, 7):
        readouts.gpu(settings(c, layer))
    result = dict(status='GPU_DIAGNOSTIC_READOUTS_COMPLETE_WAITING_CPU',
                  descriptive_only=True, formal_decision_layer=6)
    write(Path(c['output'])/'diagnostic_readouts/gpu_summary.json', result)
    return result


def cpu(c):
    from s_statistics import cpu_only
    cpu_only()
    registered(c)
    e = readouts.existing_evaluation()
    scores = {}
    for layer in range(1, 7):
        setting = settings(c, layer)
        output = Path(setting['output'])
        destination = output/'scores.json'
        if not destination.is_file():
            if layer == 6:
                raise ValueError('Wait for the original formal layer6 statistics;do not refit')
            readouts.finish_cpu_ridge(c, 3000000, settings=setting)
            e.score(output/'predictions.json', c['reference_manifest'],
                    Path(c['output'])/'diagnostic_readouts/scores.csv')
        scores[str(layer)] = json.loads(destination.read_text())
    result = dict(status='COMPLETE', descriptive_only=True, layers=scores,
                  formal_decision_layer=6, layer_selection=False)
    write(Path(c['output'])/'diagnostic_readouts/summary.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--configuration', type=Path, required=True)
    p.add_argument('--mode', choices=('gpu', 'cpu'), required=True)
    args = p.parse_args()
    c = json.loads(args.configuration.read_text())
    print(json.dumps(gpu(c) if args.mode == 'gpu' else cpu(c)), flush=True)
