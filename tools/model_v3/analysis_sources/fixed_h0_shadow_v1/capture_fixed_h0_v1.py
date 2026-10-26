#!/usr/bin/env python3
"""Fresh all48 same-forward bank-input capture, never1435-H0 or model acceptance."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback

from shadow_common import (HERE, FIELDS, INPUT_CAP, STATE_BYTES, InputBudget, bound, load_file,
    metadata_selfcheck, ref, require, save_plain, source_snapshot, state_arrays,
    tensor_state_identity, verify_publication)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--admit-only', action='store_true')
    args = parser.parse_args()
    request = bound({**ref(args.request), 'sha256': args.request_sha256})
    require(request['schema'] == 'model_v3_fixed_h0_capture_request_v1' and request['expected_case_count'] == 48,
            'Explicit complete48 capture request required')
    require(os.environ.get('MODEL_V3_NUMERIC_GPU_REQUEST_SHA') == args.request_sha256
        and os.environ.get('MODEL_V3_EXPECTED_NODE') == request['node'] == socket.gethostname().split('.')[0]
        and os.environ.get('CUDA_VISIBLE_DEVICES') == request['gpu_uuid']
        and os.environ.get('SLURM_JOB_ID', '').isdigit(), 'Actual assigned GPU capture required')
    sources = source_snapshot(request, os.environ['MODEL_V3_NUMERIC_GPU_LAUNCH_PINS_SHA'])
    if args.admit_only:
        leaf = request['UUID_admission_source']; require(ref(leaf['path']) == leaf, 'Fixed CUDA admission source differs')
        module = load_file(leaf['path'], 'fixed_h0_original_CUuuid_admission')
        save_plain(args.output_root/'CUDA_UUID_ADMISSION.json', module.admit_runtime({
            'device': 'cuda:0', 'expected_node': request['node'], 'gpu_uuid': request['gpu_uuid']}))
        return 0
    out = args.output_root.absolute(); require(not out.exists(), 'Fresh capture scope required'); out.mkdir()
    budget = InputBudget(); budget.json(out/'sources_before.json', sources)
    budget.json(out/'PUBLIC_GIT_IDENTITY.json', {'files': verify_publication(request), 'selfcheck': metadata_selfcheck()})
    rows, failure, after = [], None, None
    actual_encoder_returns = [0]
    try:
        subprocess.run([sys.executable, '-B', str(Path(__file__).absolute()), '--request', str(args.request),
            '--request-sha256', args.request_sha256, '--output-root', str(out), '--admit-only'], check=True)
        budget.adopt(out/'CUDA_UUID_ADMISSION.json')
        import numpy as np
        import torch
        root = Path(request['repository'])
        require(os.environ.get('PYTHONPATH', '').split(':')[0] == str(root/'current'), 'Single candidate package required')
        adapter_path = root/'validation/model_v3_numeric_stability_v1/candidate_composed_adapter.py'
        adapter = load_file(adapter_path, 'fixed_h0_registered_composition_adapter')
        equation = adapter.load_equation()
        from shadow_common import load_npz
        probe = budget.npz(out/'TYPED_IO_SELFCHECK.npz', {'x': np.array([[1., -2., 3.]], dtype=np.float32),
            'i': np.array([0], dtype=np.int64)})
        decoded = load_npz(probe)
        require(decoded['x'].tobytes() == np.array([[1., -2., 3.]], dtype=np.float32).tobytes(), 'Typed NPZ roundtrip oracle')
        bad = {**probe, 'arrays': {key: dict(header) for key, header in probe['arrays'].items()}}
        bad['arrays']['x']['sha256'] = '0'*64
        try: load_npz(bad)
        except ValueError: rejected = True
        else: rejected = False
        require(rejected, 'Typed NPZ corrupt-value metadata must be rejected')
        budget.json(out/'TYPED_IO_SELFCHECK.json', {'packed': probe, 'roundtrip': True,
            'allow_pickle': False, 'corrupt_value_rejected': rejected})
        from shadow_terminals_v1 import tiny_selfcheck
        budget.json(out/'INLINE_HEAD_MATH_SELFCHECK.json', tiny_selfcheck())
        require([s.identity for s in equation.CASE_SPECS] == request['expected_case_ids'], 'Original canonical48 order required')
        expected_state_total = 12*sum(STATE_BYTES.values())
        require(expected_state_total == 55838784 and expected_state_total+48*4*44*512*4 < INPUT_CAP,
                'Preregistered state+H0 raw budget arithmetic differs')
        for ordinal, case in enumerate(equation.CASE_SPECS):
            directory = out/('case_%02d' % ordinal); directory.mkdir()
            holder, handles = {}, []
            original_build = equation.build_composition
            def build(spec):
                model, registry = original_build(spec)
                bank = model.pd_heads
                arrays, names, extras = state_arrays(bank)
                actual_bytes = sum(value.nbytes for value in arrays.values())
                require(actual_bytes == STATE_BYTES[spec.head_policy], 'Actual bank tensor size differs: '+str(actual_bytes)+' vs '+str(STATE_BYTES[spec.head_policy]))
                holder.update(model=model, bank=bank, arrays=arrays, names=names, extras=extras,
                    identity=tensor_state_identity(arrays, names, extras), calls=[], pending=None,
                    full_weight_sha=equation.weight_summary(model)['all_named_parameter_sha256'],
                    registry=asdict(bank.registry), forms=dict(bank.forms))
                def before(module, inputs, kwargs):
                    require(holder['pending'] is None and len(inputs) == 3, 'One bank call per full forward required')
                    # Only Python references; no clone/cast/copy/device operation.
                    holder['pending'] = (inputs, kwargs, None)
                def after_head(module, inputs, kwargs, output):
                    require(holder['pending'] is not None, 'Bank input observation missing')
                    holder['pending'] = (inputs, kwargs, output)
                    # Returning None preserves the exact original output object.
                def encoder_return(module, inputs, output):
                    actual_encoder_returns[0] += 1
                handles.append(model.encoder.backbone.register_forward_hook(encoder_return))
                handles.append(bank.register_forward_pre_hook(before, with_kwargs=True))
                handles.append(bank.register_forward_hook(after_head, with_kwargs=True))
                original_forward = model.forward_pretrain
                had_override = 'forward_pretrain' in model.__dict__
                previous_override = model.__dict__.get('forward_pretrain')
                holder.update(original_forward=original_forward, had_override=had_override, previous_override=previous_override)
                def forward(*args_, **kwargs_):
                    result = original_forward(*args_, **kwargs_)
                    inputs, kwargs, outputs = holder['pending']
                    require(outputs is result.pd_predictions and inputs[0] is not None, 'Same-forward actual bank outputs required')
                    call = len(holder['calls']); require(call < 4, 'Exactly four original forwards/case')
                    h, batch, pos = inputs
                    require(h.dtype == pos.dtype == torch.float32 and batch.dtype == torch.int64
                        and tuple(h.shape) == (44, 512) and tuple(pos.shape) == (44, 3) and tuple(batch.shape) == (44,),
                        'Actual clean bank input shape/dtype differs')
                    require(not kwargs.get('prediction_offsets'), 'Unregistered prediction offset')
                    entries = {'H0': h, 'batch': batch, 'pos': pos}
                    entries.update({'out_'+key: value for key, value in outputs.items()})
                    entries.update({'pair_'+key: value for key, value in (kwargs.get('pair_indices') or {}).items()})
                    keys = {}
                    # All copies occur only AFTER the entire original forward returned.
                    for name, value in entries.items():
                        key = 'call%d_%s' % (call, name); keys[name] = key
                        holder['arrays'][key] = value.detach().cpu().contiguous().numpy().copy()
                    holder['calls'].append({'keys': keys, 'enabled_groups': list(kwargs['enabled_groups']),
                        'enabled_fields': list(kwargs['enabled_fields']), 'output_names': list(outputs)})
                    holder['pending'] = None
                    return result
                model.forward_pretrain = forward
                return model, registry
            measured = None
            try:
                with adapter.composition_mode(equation, 'compensated_fp32_v1'):
                    equation.build_composition = build
                    measured = equation.measure_case(case, device='cuda:0', threads=1, terminal_output_directory=directory)
                require(len(holder['calls']) == 4 and measured['encoder_forward_shapes'] ==
                    [[88 if case.views == 'two' else 132, 512]]*4, 'Complete original four encoder forwards required')
                require(equation.weight_summary(holder['model'])['all_named_parameter_sha256'] == holder['full_weight_sha'],
                        'Full model parameters changed')
                current, names, extras = state_arrays(holder['bank'])
                require(names == holder['names'] and tensor_state_identity(current, names, extras) == holder['identity'],
                        'Bank state changed before/after capture')
                terminal = measured['actual_terminal_output_artifact']; budget.adopt(terminal['path'])
                require(ref(terminal['path']) == {k: terminal[k] for k in ('path', 'bytes', 'sha256')}, 'Same-forward terminal artifact drift')
                with np.load(terminal['path'], allow_pickle=False) as original:
                    require(len(original.files) == 52 and set(original.files) == set(terminal['arrays']),
                            'Original complete52 control identities required')
                    for name, header in terminal['arrays'].items():
                        value = original[name]
                        require(value.dtype == np.float32 and str(value.dtype) == header['dtype']
                            and list(value.shape) == header['shape'] and np.isfinite(value).all(),
                            'Original full52 control dtype/shape/finiteness differs')
                    for index, call in enumerate(holder['calls']):
                        prefix = 'original' if index == 0 else 'transform%d' % (index-1)
                        for field in call['output_names']:
                            a = holder['arrays'][call['keys']['out_'+field]]; b = original[prefix+'__PD__'+field]
                            require(a.dtype == b.dtype == np.float32 and a.shape == b.shape and a.tobytes() == b.tobytes(),
                                    'Same-forward hook output differs from untouched original terminal')
                require(measured['domain']['domain_pass'] and all(t['vector_edges_unchanged'] for t in measured['measurements']),
                        'Registered capture geometry/edge controls changed')
                for transform in measured['measurements']:
                    for field in transform['fields']:
                        require(field['finite'] and (not field['nonzero_required'] or field['actual_nonzero_rows'] > 0),
                                'Finite/nonzero same-forward controls required')
                packed = budget.npz(directory/'BANK_INPUT_STATE.npz', holder['arrays'])
                value = {'schema': 'model_v3_fixed_h0_capture_case_v1', 'case_id': case.identity, 'case': asdict(case),
                    'packed': packed, 'state_names': holder['names'], 'state_extra': holder['extras'],
                    'bank_state_identity': holder['identity'], 'state_tensor_bytes': STATE_BYTES[case.head_policy],
                    'registry': holder['registry'], 'forms': holder['forms'],
                    'bank_constructor': {'dim': 512, 'hidden_dim': 64, 'vector_radius': 5., 'vector_rbf_count': 32,
                                         'numeric_mode': 'compensated_fp32_v1', 'pair_chunk_size': 8192},
                    'calls': holder['calls'], 'transforms': [x['transform'] for x in measured['measurements']],
                    'same_forward_control': True, 'original_measurement': measured,
                    'lineage': 'fresh_capture_not_1435_H0', 'hook_semantics': 'retain refs; copy after original full forward; return original object'}
                case_ref = budget.json(directory/'CAPTURE_CASE.json', value)
                rows.append({'case_id': case.identity, 'capture_case': case_ref, 'physics_passed': measured['passed']})
            finally:
                equation.build_composition = original_build
                for handle in handles: handle.remove()
                if 'model' in holder and 'had_override' in holder:
                    if holder['had_override']: holder['model'].forward_pretrain = holder['previous_override']
                    else: del holder['model'].forward_pretrain
        require([r['case_id'] for r in rows] == request['expected_case_ids'], 'No subset capture accepted')
    except BaseException as error:
        failure = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
    finally:
        try:
            after = {path: ref(path) for path in sources}
            budget.json(out/'sources_after.json', after); require(after == sources, 'Capture source changed')
        except BaseException as error:
            failure = {'earlier': failure, 'source_after': str(error)}
        complete = failure is None and len(rows) == 48 and actual_encoder_returns[0] == 192
        manifest = {'schema': 'model_v3_fixed_h0_capture_manifest_v1', 'status': 'CAPTURE_COMPLETE' if complete else 'FAILED',
            'job_id': os.environ['SLURM_JOB_ID'], 'request': ref(args.request), 'source_pins': ref(HERE/'source_pins_v1.json'),
            'lineage': 'fresh_capture_not_1435_H0', 'cases': rows, 'failure': failure,
            'input_bytes_before_manifest': budget.used, 'input_limit_bytes': INPUT_CAP,
            'physics_case_passed': sum(r['physics_passed'] for r in rows), 'physics_adoption': False,
            'encoder_forwards': actual_encoder_returns[0], 'completed_case_encoder_forwards': 4*len(rows),
            'source_before_after_equal': after == sources}
        manifest_ref = budget.json(out/'CAPTURE_MANIFEST.json', manifest)
        if complete: budget.json(out/'CAPTURE_COMPLETE.json', {'schema': 'model_v3_fixed_h0_capture_complete_v1',
            'manifest': manifest_ref, 'input_files_bytes_before_complete': budget.used})
    return 0 if complete else 1


if __name__ == '__main__':
    raise SystemExit(main())
