#!/usr/bin/env python3
"""Verify the pinned real B3 checkpoint using only two synthetic CPU molecules.

This is a checkpoint-format/source/H0 smoke, not a downstream evaluation or
GPU-capacity measurement. The root coordinator supplies an owned Slurm CPU
allocation, immutable code/reference bindings, and a fresh external output.
No downstream store, labels, prior evaluation results, or optimizer is opened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
import traceback


ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / 'current'))


def write_new_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def measured_file(reference):
    path = Path(reference['path'])
    if path.is_symlink() or not path.is_file() or path.stat().st_size != reference['bytes']:
        raise ValueError('The pinned historical weights must be the exact ordinary source file')
    digest = hashlib.sha256(); measured = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block); measured += len(block)
    result = {'path': str(path), 'sha256': digest.hexdigest(), 'bytes': measured}
    if result['sha256'] != reference['sha256'] or measured != reference['bytes']:
        raise ValueError('The actual historical checkpoint bytes differ from the pinned receipt')
    return result


def synthetic_geometries():
    import torch
    from phychem_mfm.phase1.v3_dev_panel import NativeGeometry
    return (NativeGeometry('synthetic_B3_smoke', 'synthetic:0', 0,
        torch.tensor([[5], [0], [0]], dtype=torch.long),
        torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]], dtype=torch.float32),
        torch.tensor([2, 0, 1], dtype=torch.long)),
        NativeGeometry('synthetic_B3_smoke', 'synthetic:1', 1,
        torch.tensor([[7], [0]], dtype=torch.long),
        torch.tensor([[0., 0., 0.], [0., 0., 1.]], dtype=torch.float32),
        torch.tensor([1, 0], dtype=torch.long)))


def execute(*, reference_path, reference_sha256, code_sha, output_root):
    # This entry point is intentionally restricted to a fresh coordinator-owned
    # CPU allocation. It never selects a GPU, launches a job or resumes training.
    if (os.getuid() != 1278 or not os.environ.get('SLURM_JOB_ID')
            or int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) < 16):
        raise RuntimeError('The root coordinator must provide an owned Slurm allocation with at least 16 CPUs')
    if not re.fullmatch(r'[0-9a-f]{40}', code_sha) or not re.fullmatch(r'[0-9a-f]{64}', reference_sha256):
        raise ValueError('Full actual code and pinned physical reference SHA values are required')
    output = Path(output_root).absolute()
    if output.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Smoke outputs, checkpoints and H0 cache must stay outside the source repository')
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = {'schema': 'model_v3_real_B3_synthetic_H0_smoke_v1', 'status': 'FAILED',
        'actual_code_sha': code_sha, 'reference': {'path': str(reference_path), 'sha256': reference_sha256},
        'node': socket.gethostname(), 'job_id': os.environ['SLURM_JOB_ID'], 'device': 'cpu',
        'allocated_cpus': int(os.environ['SLURM_CPUS_PER_TASK']), 'threads': 16,
        'scientific_scope': 'real source weights, synthetic input only; no downstream evaluation',
        'downstream_target_records_read': 0, 'downstream_evaluation_result_files_opened': 0,
        'checkpoint_pretraining_validation_scores_used': 0,
        'checkpoint_envelope_note': 'The source weights-only loader deserializes the complete checkpoint envelope; '
            'pretraining validation history is not inspected, scored, compared or used.',
        'real_GPU_capacity_measured': False, 'training_updates': 0}
    try:
        from phychem_mfm.phase1.v3_dev_store import bound_json
        from phychem_mfm.phase1.v3_dev_panel import FrozenH0Cache, canonical
        from phychem_mfm.phase1.v3_encoder_bridge import load_encoder_pair, source_model_configuration
        from phychem_mfm.phase1.v3_h0_runtime import physical_source_binding
        reference = bound_json(reference_path, reference_sha256)
        if reference.get('schema') != 'model_v3_historical_b3_reference_v1':
            raise ValueError('The explicit frozen B3 physical reference is required')
        report['smoke_implementation'] = physical_source_binding(__file__)
        report['loading_source_files'] = {relative: physical_source_binding(ROOT / relative)
            for relative in ('current/phychem_mfm/factory.py',
                'current/phychem_mfm/phase1/v3_encoder_bridge.py',
                'current/phychem_mfm/phase1/v3_dev_store.py',
                'current/phychem_mfm/phase1/v3_dev_panel.py',
                'current/phychem_mfm/phase1/v3_h0_runtime.py',
                'current/phychem_mfm/phase1/v3_h0_packing.py',
                'workflows/sprime_s/scripts/s_model_memory_v1.py')}
        checkpoint = measured_file(reference['checkpoint'])
        report['actual_checkpoint_measurement'] = checkpoint
        config_ref = reference['configuration']
        configuration = bound_json(config_ref['path'], config_ref['sha256'])
        model_config = source_model_configuration(configuration)
        if configuration.get('seed') != 0:
            raise ValueError('This smoke is specifically the pinned original B3_seed0 source')
        import torch
        torch.set_num_threads(16)
        pair = load_encoder_pair(checkpoint, config_ref, architecture_sha256=canonical(model_config),
            pretraining_seed=0, random_seed=20261025, reference_kind='historical_sanity_only',
            historical_reference={'path': str(reference_path), 'sha256': reference_sha256}, expected_state_key='model')
        if pair.candidate.latent_dim != 384 or pair.random_reference.latent_dim != 384:
            raise ValueError('A historical 384-dimensional candidate and matching random reference are required')
        report['encoder_pair'] = pair.provenance
        report['source_model_configuration'] = pair.model_configuration
        report['historical_builder'] = pair.candidate.s_memory_implementation
        if pair.candidate.s_memory_implementation != pair.random_reference.s_memory_implementation:
            raise ValueError('Historical candidate/random builders differ')
        geometry = synthetic_geometries()
        membership_sha = canonical([[r.dataset_id, r.member_index, r.molecule_uid] for r in geometry])
        cache = FrozenH0Cache(output / 'h0_cache', repository_root=ROOT)
        metadata, values = {}, {}
        for label, encoder in (('candidate', pair.candidate), ('random_reference', pair.random_reference)):
            rows, bound = cache.get_or_compute(encoder, geometry, architecture_sha256=canonical(model_config),
                membership_sha256=membership_sha, max_graphs=2, max_native_atoms=5,
                max_padded_pairs=18, atom_bucket_width=16, device='cpu', execution_source={
                    'actual_code_sha': code_sha, 'loader_implementation': pair.provenance['loader_implementation'],
                    'reference_sha256': reference_sha256, 'smoke_implementation': report['smoke_implementation'],
                    'weights_origin': checkpoint if label == 'candidate' else {'initialization_seed': 20261025}})
            if ([r.member_index for r in rows] != [0, 1] or [list(r.h0.shape) for r in rows] != [[3, 384], [2, 384]]
                    or any(not torch.equal(row.source_atom_ids, original.source_atom_ids)
                           for row, original in zip(rows, geometry))):
                raise ValueError('Synthetic source membership or native atom/H0 correspondence differs')
            metadata[label] = bound
            values[label] = torch.cat([r.h0 for r in rows])
        candidate, random = metadata['candidate']['binding'], metadata['random_reference']['binding']
        if any(candidate[key] != random[key] for key in (
                'architecture_sha256', 'membership_sha256', 'geometry_sha256', 'dimension',
                'packing_plan_sha256', 'effective_runtime_sha256')):
            raise ValueError('Paired H0 source/geometry/packing/runtime bindings differ')
        if torch.equal(values['candidate'], values['random_reference']):
            raise ValueError('The independently sourced candidate/random H0 values unexpectedly coincide')
        if (physical_source_binding(__file__) != report['smoke_implementation'] or any(
                physical_source_binding(ROOT / relative) != source
                for relative, source in report['loading_source_files'].items())):
            raise RuntimeError('The physical loading/source implementation changed during this smoke')
        report.update(status='PASS', H0_shapes={'candidate': [5, 384], 'random_reference': [5, 384]},
            native_molecules=2, native_atoms=5, native_source_atom_order_preserved=True,
            loading_source_files_unchanged=True, caches=metadata, cuda_initialized=bool(torch.cuda.is_initialized()))
        if report['cuda_initialized']:
            raise RuntimeError('This CPU-only smoke unexpectedly initialized CUDA')
    except BaseException as exc:
        report.update(status='FAILED', exception_type=type(exc).__name__, exception=str(exc),
                      exception_chain=traceback.format_exc())
        raise
    finally:
        report['elapsed_seconds'] = time.monotonic()-started
        write_new_json(output / 'smoke_result.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path,
        default=ROOT / 'configs/model_v3/historical_B3_H0_reference_v1.json')
    parser.add_argument('--reference-sha256', required=True)
    parser.add_argument('--code-sha', required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    report = execute(reference_path=args.reference, reference_sha256=args.reference_sha256,
        code_sha=args.code_sha, output_root=args.output_root)
    print(json.dumps({key: report[key] for key in ('status', 'H0_shapes', 'elapsed_seconds',
        'downstream_target_records_read', 'downstream_evaluation_result_files_opened')}))


if __name__ == '__main__':
    main()
