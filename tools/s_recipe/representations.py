"""Taskbook endpoint H extraction and CPU-only descriptive statistics.

Composition functions are the unchanged p-followup5af7d2b7 implementation.
The unresolved layer scope must be explicitly frozen before this entry runs.
"""
import argparse
import json
from pathlib import Path
import resource
import socket
import os

import numpy as np
import torch

import composition_statistics as statistics
from checkpoint_binding import validate_resume
from representation_moments import atom_moments, participation_ratios, mean_participation_ratios
from runtime import CONTROL, REPO, capacity, write
from s_data import GeometryDataset

BASIS = CONTROL.parent/'p_data_information_20261115_v1/normalizations_TRAIN.json'
SOURCE_STATISTICS = '5af7d2b730fd14d4ad2f3a0a0b9c2f32049816ea:tools/p_followup/composition_statistics.py'


def registered(c):
    registration = json.loads((REPO/'configs/s_recipe/preregistration.json').read_text())
    if registration['status'] != 'FROZEN':
        raise ValueError('Endpoint diagnostics wait for the scientific registration freeze')
    layers = registration['diagnostics'].get('representation_layers')
    if not layers or layers != sorted(set(layers)) or not set(layers) <= set(range(1, 7)):
        raise ValueError('Explicit registered representation layers are required; do not infer the unresolved scope')
    if c['seed'] != 0 or c['samples'] != 3000000:
        raise ValueError('Endpoint diagnostics are3M seed0 only')
    if c['arm'] not in ('S-B0', 'S-G1'):
        best = json.loads((REPO/'configs/s_recipe/CURRENT_BEST.json').read_text())
        if best['status'] != 'FROZEN' or best['recipe'] != c['arm']:
            raise ValueError('Only the distinct frozen S-final may add an endpoint diagnosis')
    return layers


def directory(c):
    base = CONTROL/'scratch/representations'
    path = base/c['run']
    if path.parent.resolve() != base.resolve():
        raise ValueError('Diagnostic cache must stay inside its own S scratch run')
    return path


def extract(c):
    layers = registered(c)
    node = socket.gethostname().split('.')[0]
    if node not in {'compute-0-'+str(i) for i in (*range(8), 20, 22)}:
        raise ValueError('Representation extraction requires an admitted GPU compute node')
    if node not in ('compute-0-20', 'compute-0-22') and not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('Small-group GPU extraction requires a real Slurm allocation')
    capacity()
    output = directory(c)
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = Path(c['output'])/'samples_3000000.pt'
    binding = dict(run=c['run'], arm=c['arm'], source=c['source'], checkpoint=str(checkpoint),
                   population=c['population'], layers=layers)
    path = output/'binding.json'
    if path.is_file() and json.loads(path.read_text()) != binding:
        raise ValueError('Existing endpoint extraction belongs to a different condition')
    if (output/'manifest.json').is_file():
        return json.loads((output/'manifest.json').read_text())
    write(path, binding)
    from phychem_mfm.phase1.v2_s_training import s_model
    from phychem_mfm.phase1.v31_loader import collate_samples
    from phychem_mfm.phase1.p_recipe_handoff import publish_checkpoint
    payload = torch.load(checkpoint, map_location='cpu', weights_only=True)
    validate_resume(c, payload['configuration'])
    if payload['clock']['samples_consumed'] != 3000000:
        raise ValueError('The producer checkpoint is not the registered3M endpoint')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision('highest')
    model, _ = s_model('C1-0', 'three')
    model.load_state_dict(payload['model'])
    encoder = model.encoder.cuda().eval()
    del payload
    data = GeometryDataset(c['root'], c['population'], source=c['source'], validation=True)
    if len(data.rows) != 5000:
        raise ValueError('Use the producer-frozen5000 VAL molecules')
    choices, owners, first = [], [], []
    for owner, row in enumerate(data.rows):
        for ordinal, conformer in enumerate(row[c['source']]):
            choices.append((int(row['molecule_index']), int(conformer), len(choices)))
            owners.append(owner)
            first.append(ordinal == 0)
    files = []
    try:
        with torch.no_grad():
            for start in range(0, len(choices), 32):
                target = output/('chunk_'+str(start)+'.pt')
                files.append(str(target))
                if target.is_file():
                    continue
                if start % 1024 == 0:
                    capacity()
                samples = [data.read(choice) for choice in choices[start:start+32]]
                batch = collate_samples(samples, device='cuda')
                final, intermediate = encoder.encode_atoms(batch, return_intermediates=True)
                h = torch.stack([final if layer == 6 else intermediate[layer-1] for layer in layers], dim=1)
                pointers = batch.ptr.cpu().tolist()
                means, atoms, atom_owners, elements = [], [], [], []
                for j, (a, b) in enumerate(zip(pointers, pointers[1:])):
                    # Existing follow-up convention: F64 pooling, F32 cache,
                    # then F64 statistical arithmetic on the CPU worker.
                    means.append(h[a:b].double().mean(dim=0).float().cpu())
                    if first[start+j]:
                        atoms.append(h[a:b].cpu())
                        atom_owners.append(owners[start+j])
                        elements.append(torch.as_tensor(samples[j]['Z'].astype(np.int64)))
                publish_checkpoint(dict(owners=owners[start:start+len(samples)], mean_H=torch.stack(means),
                    first_atom_H=atoms, first_owners=atom_owners, first_Z=elements), target)
                if start % 1024 == 0:
                    print(json.dumps(dict(endpoint=c['run'], extracted=start+len(samples), conformers=len(choices))), flush=True)
    finally:
        data.close()
    result = dict(schema='S_RECIPE_ENDPOINT_H_V1', binding=binding, molecules=5000,
        molecule_ids=[row['molecule_id'] for row in data.rows], conformers=len(choices), chunks=files,
        layer6='after out_norm', intermediate_layers='original post-block outputs',
        PR_and_CEV='first allowed conformer', CVF='all allowed conformers;original>=2 eligibility',
        cache_dtype='float32', pooling_dtype='float64', encoder_forward='one per closed input chunk;no probes')
    write(output/'manifest.json', result)
    return result


def _layer_inputs(manifest, layer_index, basis):
    n = manifest['molecules']
    dimension = 512
    products = np.empty((n, dimension*(dimension+1)//2), np.float64)
    sums = np.empty((n, dimension), np.float64)
    counts = np.empty(n, np.float64)
    x = np.empty((n, len(basis)+2), np.float64)
    seen = np.zeros(n, bool)
    means, owners = [], []
    for index, filename in enumerate(manifest['chunks']):
        packet = torch.load(filename, map_location='cpu', weights_only=True)
        means.append(packet['mean_H'][:, layer_index].double().numpy())
        owners.extend(packet['owners'])
        for owner, h, z in zip(packet['first_owners'], packet['first_atom_H'], packet['first_Z']):
            if seen[owner]:
                raise ValueError('Endpoint producer repeated a first-conformer owner')
            seen[owner] = True
            counts[owner], sums[owner], products[owner] = atom_moments(h[:, layer_index].numpy())
            numbers = z.numpy()
            x[owner] = [int((numbers == element).sum()) for element in basis]+[len(numbers), int((numbers > 1).sum())]
        if index % 32 == 0:
            capacity()
    if not seen.all():
        raise ValueError('Endpoint producer has not closed every fixed VAL molecule')
    return counts, sums, products, x, np.concatenate(means), np.asarray(owners, dtype=np.int64)


def calculate(c):
    from s_statistics import cpu_only
    memory = cpu_only()
    layers = registered(c)
    manifest = json.loads((directory(c)/'manifest.json').read_text())
    expected = dict(run=c['run'], arm=c['arm'], source=c['source'],
                    checkpoint=str(Path(c['output'])/'samples_3000000.pt'), population=c['population'], layers=layers)
    if manifest['binding'] != expected:
        raise ValueError('Endpoint extraction does not match the registered condition/layers')
    norms = json.loads(BASIS.read_text())
    basis = sorted({int(z) for spec in norms.values() for z in (spec.get('element_reference') or {}).get('basis', [])})
    if not basis:
        raise ValueError('Existing composition-reference element basis unavailable; do not refit it')
    weights = np.vstack([np.ones(manifest['molecules']), statistics.bootstrap_weights(manifest['molecules'], 1000)])
    destination = REPO/'results/s_recipe/representations'/c['run']
    destination.mkdir(parents=True, exist_ok=True)
    results = {}
    for index, layer in enumerate(layers):
        target = destination/('layer_'+str(layer)+'.json')
        if target.is_file():
            results[str(layer)] = json.loads(target.read_text())
            continue
        counts, sums, products, x, h, owners = _layer_inputs(manifest, index, basis)
        atom_pr = participation_ratios(weights, counts, sums, products)
        del products, sums, counts
        first = np.flatnonzero(np.r_[True, np.diff(owners) != 0])
        y = h[first]
        if len(y) != manifest['molecules'] or not np.array_equal(owners[first], np.arange(len(y))):
            raise ValueError('Mean H source ordering differs from the frozen MID cohort')
        mean_pr = mean_participation_ratios(weights, y)
        prediction, alphas = statistics.ridge_oof(x, y)
        cev = statistics.cev_values(y, prediction, weights)
        cvf, cvf_res = statistics.cvf_values(h, owners, prediction, weights)
        values = dict(atom_H_PR=atom_pr, mean_H_PR=mean_pr, CEV=cev, CVF=cvf, CVF_res=cvf_res)
        row = dict(layer=layer, molecules=len(y), conformers=len(h),
                   metrics={name: statistics.summary(v) for name, v in values.items()}, selected_alphas=alphas)
        capacity()
        np.savez_compressed(destination/('layer_'+str(layer)+'_bootstrap.npz'), **values)
        write(target, row)
        results[str(layer)] = row
        del h, y, x, prediction
    result = dict(schema='S_RECIPE_ENDPOINT_DIAGNOSTICS_V1', status='COMPLETE', binding=manifest['binding'],
        layers=results, statistics_dtype='float64', bootstrap=dict(draws=1000, seed=20261025, unit='molecule'),
        composition_basis_source=str(BASIS), source_statistics=SOURCE_STATISTICS, descriptive_only=True,
        node=socket.gethostname(), job=os.environ['SLURM_JOB_ID'], memory_at_start=memory,
        peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    write(destination/'summary.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--configuration', type=Path, required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--extract', action='store_true')
    mode.add_argument('--statistics', action='store_true')
    args = p.parse_args()
    c = json.loads(args.configuration.read_text())
    print(json.dumps(extract(c) if args.extract else calculate(c)), flush=True)
