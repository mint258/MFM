#!/usr/bin/env python3
"""Same actual1492 inputs: strict FP32 replay then independent FP64 H0 analysis.

SOURCE ONLY. Neither this reference nor its raw-scale errors adopt an architecture.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback

HERE = Path(__file__).absolute().parent
B = Path('/share/home/zixiao/descriptor_analysis')
OLD_HEAD = B/'runs/model_v3_20261026/numeric_fixed_h0_shadow_v3_source'
# Original published helpers, exact unchanged functional64 arithmetic.
sys.path.insert(0, str(OLD_HEAD))
import shadow_common as common
if Path(common.__file__).absolute() != OLD_HEAD/'shadow_common.py':
    raise ValueError('Original published head helper namespace differs')
require, ref, bound, save = common.require, common.ref, common.bound, common.save_plain
verify_publication, metadata_selfcheck = common.verify_publication, common.metadata_selfcheck


def load_file(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sources(request, pins_sha):
    pins = bound({**ref(HERE/'source_pins_v1.json'), 'sha256': pins_sha})
    require(pins['schema'] == 'model_v3_full_encoder_precision_launch_source_pins_v1'
        and pins['role'] == 'FULL_ENCODER_FP64_ACTUAL_INPUT_ANALYSIS_ONLY', 'Independent analysis snapshot required')
    rows = {leaf['path']: leaf for leaf in request['source_refs']+pins['files']+pins['protected_dependencies']}
    rows[str(HERE/'source_pins_v1.json')] = ref(HERE/'source_pins_v1.json')
    for leaf in rows.values():
        require(ref(leaf['path']) == leaf, 'Source inventory drift: '+leaf['path'])
    common.verify_publication(request)
    return pins, rows


def compare_saved(actual, expected, name):
    from encoder_reference_v1 import tensor_header
    a, e = tensor_header(actual), tensor_header(expected)
    return {'name': name, 'actual': a, 'original1492': e, 'bitwise_equal': a == e}


def promotion_input(data, device):
    import torch
    value = data.clone().to(device)
    for key, tensor in value:
        if isinstance(tensor, torch.Tensor) and tensor.is_floating_point():
            require(tensor.dtype == torch.float32, 'Only actual FP32 floating input may be promoted')
            value[key] = tensor.to(torch.float64)
    return value


def max_record(value):
    import torch
    value = value.detach().cpu().double()
    flat = int(value.abs().argmax()); width = value.shape[-1]
    return {'maxabs': float(value.abs().max()), 'argmax': [flat//width, flat%width],
            'signed_value': float(value.reshape(-1)[flat]),
            'components_gt_1e_5': int((value.abs() > 1e-5).sum())}


def stage_analysis(fp32, fp64):
    result = []
    for transform in range(3):
        for name in fp32[0]['stages']:
            for scope in ('all_packed_physical_views', 'clean44_bank_rows'):
                a0, at = fp32[0]['stages'][name], fp32[transform+1]['stages'][name]
                b0, bt = fp64[0]['stages'][name], fp64[transform+1]['stages'][name]
                if scope == 'clean44_bank_rows':
                    a0, at = a0[fp32[0]['clean_rows']], at[fp32[transform+1]['clean_rows']]
                    b0, bt = b0[fp64[0]['clean_rows']], bt[fp64[transform+1]['clean_rows']]
                require(a0.dtype == at.dtype == __import__('torch').float32
                    and b0.dtype == bt.dtype == __import__('torch').float64, 'Stage is not true declared dtype')
                d32, d64 = at.double()-a0.double(), bt-b0
                residual = d32-d64
                flat = int(d32.abs().argmax()); width = d32.shape[1]
                result.append({'transform_index': transform, 'stage': name, 'scope': scope,
                    'shape': list(d32.shape), 'FP32_actual_input_drift': max_record(d32),
                    'FP64_actual_input_drift': max_record(d64), 'FP32_minus_FP64_drift': max_record(residual),
                    'at_same_FP32_drift_argmax': {'row': flat//width, 'channel': flat%width,
                        'FP32': float(d32.reshape(-1)[flat]), 'FP64': float(d64.reshape(-1)[flat]),
                        'FP32_minus_FP64': float(residual.reshape(-1)[flat])},
                    'closure_maxabs': float((d32-d64-residual).abs().max())})
    require(all(row['closure_maxabs'] <= 1e-10 for row in result), 'Precision drift closure differs')
    return result


def raw_state_headers(module):
    from encoder_reference_v1 import tensor_header
    import torch
    return {name: tensor_header(value) if isinstance(value, torch.Tensor) else value
            for name, value in module.state_dict().items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--admit-only', action='store_true')
    args = parser.parse_args()
    request = bound({**ref(args.request), 'sha256': args.request_sha256})
    require(os.environ.get('MODEL_V3_NUMERIC_GPU_REQUEST_SHA') == args.request_sha256
        and os.environ.get('MODEL_V3_EXPECTED_NODE') == request['node'] == socket.gethostname().split('.')[0]
        and os.environ.get('CUDA_VISIBLE_DEVICES') == request['gpu_uuid']
        and os.environ.get('SLURM_JOB_ID', '').isdigit(), 'Actual source-bound GPU allocation required')
    pins, before = sources(request, os.environ['MODEL_V3_NUMERIC_GPU_LAUNCH_PINS_SHA'])
    if args.admit_only:
        leaf = request['UUID_admission_source']
        require(ref(leaf['path']) == leaf, 'Original CUuuid admission source differs')
        admission = load_file(leaf['path'], 'full_encoder_original_UUID_admission')
        save(args.output_root/'CUDA_UUID_ADMISSION.json', admission.admit_runtime({
            'device': 'cuda:0', 'gpu_uuid': request['gpu_uuid'], 'expected_node': request['node']}))
        return 0
    protocol = bound(pins['analysis_protocol'])
    require(protocol['schema'] == 'model_v3_full_encoder_precision_analysis_protocol_v1'
        and protocol['only_actual_FP32_input_promoted'] is True and not protocol['ideal_coordinate_counterfactual']
        and protocol['expected_FP32_encoder_forwards'] == protocol['expected_FP64_encoder_forwards'] == 192,
        'Fixed actual-input-only protocol required')
    complete = bound(protocol['capture_complete']); capture = bound(complete['manifest'])
    require(capture['schema'] == 'model_v3_fixed_h0_capture_manifest_v1' and capture['status'] == 'CAPTURE_COMPLETE'
        and capture['source_before_after_equal'] and capture['failure'] is None
        and capture['job_id'] == '4521492' and capture['completed_case_encoder_forwards'] == capture['encoder_forwards'] == 192
        and capture['source_pins'] == protocol['capture_producer_source_pins']
        and [row['case_id'] for row in capture['cases']] == request['expected_case_ids'], 'Complete actual1492 source lineage required')
    supervisor = bound(protocol['capture_supervisor'])
    require(supervisor['job_id'] == '4521492' and supervisor['status'] == 'COMPLETED'
        and supervisor['exit_code'] == 0 and supervisor['first_failure'] is None
        and supervisor['remaining_recorded_processes_before_retirement'] == []
        and supervisor['private_storage_cleanup_errors'] == []
        and supervisor['gpu_uuid'] == request['gpu_uuid']
        and supervisor['supervisor_source_sha256'] == request['supervisor_source']['sha256']
        and supervisor['foreign_gpu_processes_signalled'] is False, 'Closed successful fixed capture required')
    require(capture['request']['sha256'] == args.request_sha256
        and bound(capture['request']) == request, 'Original capture scientific request differs')
    producer = bound(protocol['capture_producer_source_pins'])
    require(producer['operational_revision'] == 2, 'Actual immutable v2 capture producer required')
    expected_capture_command = [request['GPU_python'], '-u', '-B',
        str(Path(protocol['capture_producer_source_pins']['path']).parent/'capture_fixed_h0_v1.py'),
        '--request', capture['request']['path'], '--request-sha256', capture['request']['sha256'],
        '--output-root', str(Path(protocol['capture_complete']['path']).parent)]
    require(supervisor['command'] == expected_capture_command, 'Actual supervised capture command differs')
    accounting = load_file(OLD_HEAD/'cpu_metadata_v3.py', 'encoder_original_accounting_adapter')
    accounting_validation = accounting.validate_capture_accounting(bound(protocol['capture_accounting']), '4521492')
    input_root = Path(protocol['capture_complete']['path']).parent
    input_files = [path for path in input_root.rglob('*') if path.is_file()]
    require(all(not path.is_symlink() for path in input_files)
        and sum(path.stat().st_size for path in input_files) <= 128*1024**2, 'Original input scope exceeds128MiB')
    require(not args.output_root.exists(), 'Fresh precision analysis output required')
    args.output_root.mkdir(); save(args.output_root/'sources_before.json', before)
    counts = {'FP32_full_encoder_returns': 0, 'FP64_full_encoder_returns': 0}
    scientific_head_calls = [0]
    result, failure = None, None
    try:
        subprocess.run([sys.executable, '-B', str(Path(__file__).absolute()), '--request', str(args.request),
            '--request-sha256', args.request_sha256, '--output-root', str(args.output_root), '--admit-only'], check=True)
        import torch
        from encoder_reference_v1 import StageReferences, strict_fp64_encoder_copy, tensor_header, inline_reference_selfcheck, close_analysis_forwards, geometry_policy
        old_head = load_file(OLD_HEAD/'shadow_terminals_v1.py', 'original_public_functional64_head')
        adapter_leaf = next(leaf for leaf in request['source_refs'] if leaf['path'].endswith('/candidate_composed_adapter.py'))
        adapter = load_file(adapter_leaf['path'], 'encoder_precision_original_candidate_adapter')
        equation = adapter.load_equation()
        require([spec.identity for spec in equation.CASE_SPECS] == request['expected_case_ids'], 'Canonical complete48 required')
        # Retain only input/stage CPU tensors across this first global gate;
        # never retain48 model copies or persist encoder weights.
        replay = {}
        with equation.numerical_policy(threads=1), torch.inference_mode(), torch.autocast(device_type='cuda', enabled=False):
            for ordinal, (spec, leaf) in enumerate(zip(equation.CASE_SPECS, capture['cases'])):
                case, old_bank, original_calls = old_head.decode_case(leaf)
                holder, handles = {}, []
                original_builder = equation.build_composition
                def build(actual_spec):
                    model, registry = original_builder(actual_spec)
                    require(equation.weight_summary(model)['all_named_parameter_sha256']
                        == case['original_measurement']['weight_summary']['all_named_parameter_sha256'],
                        'Original1492 complete parameter identity differs')
                    actual_arrays, names, extras = common.state_arrays(model.pd_heads)
                    require(common.tensor_state_identity(actual_arrays, names, extras) == case['bank_state_identity'],
                            'Original1492 typed bank state differs')
                    recorder = StageReferences(model.encoder.backbone)
                    original_forward = model.forward_pretrain
                    holder.update(model=model, recorder=recorder, calls=[], original_forward=original_forward,
                        had_override='forward_pretrain' in model.__dict__)
                    def count(module, inputs, output): counts['FP32_full_encoder_returns'] += 1
                    handles.append(model.encoder.backbone.register_forward_hook(count))
                    def bank_before(module, inputs, kwargs): holder['bank_input'] = inputs
                    handles.append(model.pd_heads.register_forward_pre_hook(bank_before, with_kwargs=True))
                    def forward(*positional, **keywords):
                        output = original_forward(*positional, **keywords)
                        observed = recorder.take(positional[0].clean_atom_rows)
                        h, batch, pos = holder.pop('bank_input')
                        index = len(holder['calls']); require(index < 4, 'Unexpected additional model forward')
                        original_h, original_pos, original_batch, _ = original_calls[index]
                        comparisons = [compare_saved(h, original_h, 'actual_bank_H0'),
                            compare_saved(pos, original_pos, 'actual_bank_pos'), compare_saved(batch, original_batch, 'actual_bank_batch'),
                            compare_saved(observed['stages']['packed_H0'][observed['clean_rows']], original_h, 'canonical_clean_H0')]
                        save(args.output_root/('replay_case%02d_role%d.json' % (ordinal, index)), {
                            'case_id': spec.identity, 'role': index, 'comparisons': comparisons,
                            'stage_dtypes': {k: str(v.dtype) for k, v in observed['stages'].items()},
                            'input_pos': tensor_header(observed['input'].pos),
                            'actual_layer_mask': observed['actual_layer_mask'], 'actual_geometry_policy': geometry_policy(model.encoder)})
                        require(all(row['bitwise_equal'] for row in comparisons), 'REPLAY_MISMATCH against actual1492')
                        require(all(v.dtype == torch.float32 for v in observed['stages'].values()), 'Original path stage was not FP32')
                        holder['calls'].append(observed)
                        return output
                    model.forward_pretrain = forward
                    return model, registry
                try:
                    with adapter.composition_mode(equation, 'compensated_fp32_v1'):
                        equation.build_composition = build
                        measured = equation.measure_case(spec, device='cuda:0', threads=1)
                    save(args.output_root/('replay_case%02d.json' % ordinal), measured)
                    require(measured['encoder_configuration'] == case['original_measurement']['encoder_configuration']
                        and measured['registry_sha256'] == case['original_measurement']['registry_sha256']
                        and measured['case'] == case['case'], 'Actual1492 model config/registry/case differs')
                    require(len(holder['calls']) == 4, 'Four exact original roles required')
                    expected_nodes = 88 if spec.views == 'two' else 132
                    require(measured['encoder_forward_shapes'] == case['original_measurement']['encoder_forward_shapes']
                        == [[expected_nodes, 512]]*4
                        and all(len(call['input'].pos) == expected_nodes for call in holder['calls']),
                        'Original full physical views/packed shape differs')
                    require(equation.weight_summary(holder['model'])['all_named_parameter_sha256']
                        == case['original_measurement']['weight_summary']['all_named_parameter_sha256'], 'Replay changed parameters')
                    require(measured['fixture_geometry_sha256'] == case['original_measurement']['fixture_geometry_sha256']
                        and measured['original_physical_geometry_sha256'] == case['original_measurement']['original_physical_geometry_sha256']
                        and measured['original_view_identity_sha256'] == case['original_measurement']['original_view_identity_sha256'],
                        'Original full-view input fixture/discrete/geometry identity differs')
                    replay[spec.identity] = holder['calls']
                finally:
                    equation.build_composition = original_builder
                    for handle in handles: handle.remove()
                    if 'recorder' in holder: holder['recorder'].close()
                    if 'model' in holder:
                        if holder['had_override']: holder['model'].forward_pretrain = holder['original_forward']
                        else: del holder['model'].forward_pretrain
                    holder.clear()
            require(len(replay) == 48 and counts['FP32_full_encoder_returns'] == 192, 'Entire192 replay gate required BEFORE FP64')
            save(args.output_root/'FP32_REPLAY_GATE.json', {'status': 'ALL48_192_ROLES_BITWISE_MATCH_ACTUAL1492',
                'counts': dict(counts), 'source_capture': protocol['capture_complete'],
                'FP64_started_before_complete_replay_gate': False})
            small_controls = inline_reference_selfcheck(old_head)
            save(args.output_root/'INLINE_DEVICE_SELFCHECK.json', small_controls)
            case_results = []
            for ordinal, (spec, leaf) in enumerate(zip(equation.CASE_SPECS, capture['cases'])):
                case, old_bank, original_calls = old_head.decode_case(leaf)
                with adapter.composition_mode(equation, 'compensated_fp32_v1'):
                    original, _ = equation.build_composition(spec)
                original.to('cuda:0')
                original_sha = equation.weight_summary(original)['all_named_parameter_sha256']
                require(original_sha == case['original_measurement']['weight_summary']['all_named_parameter_sha256'],
                        'Second source reconstruction parameters differ')
                state_before = raw_state_headers(original)
                reference, mapping = strict_fp64_encoder_copy(original.encoder)
                reference.to('cuda:0')
                reference_before = raw_state_headers(reference)
                recorder = StageReferences(reference.backbone)
                handle = reference.backbone.register_forward_hook(
                    lambda module, inputs, output: counts.__setitem__('FP64_full_encoder_returns', counts['FP64_full_encoder_returns']+1))
                refs, terminals, clean_values, clean_headers = [], [], {}, {}
                try:
                    for role, stored in enumerate(replay[spec.identity]):
                        data = promotion_input(stored['input'], 'cuda:0')
                        require(len(data.pos) == (88 if spec.views == 'two' else 132)
                            and data.batch.dtype == torch.int64, 'F64 must retain full original physical batch')
                        packed = reference.encode_atoms(data)
                        require(packed.dtype == torch.float64 and packed.shape == stored['stages']['packed_H0'].shape
                            and packed.isfinite().all() and float(packed.abs().max()) > 0,
                                'Reference final packed H0 dtype/shape differs')
                        captured = recorder.take(stored['clean_rows']); refs.append(captured)
                        clean = packed.index_select(0, stored['clean_rows'].to('cuda:0'))
                        require(clean.shape == (44, 512), 'Canonical reference clean H0 shape differs')
                        _, original_pos, original_batch, _ = original_calls[role]
                        predicted = old_head.functional64(original.pd_heads, clean,
                            original_pos.to('cuda:0'), original_batch.to('cuda:0'))
                        scientific_head_calls[0] += 1
                        require(all(value.dtype == torch.float64 and value.isfinite().all() and float(value.abs().max()) > 0 for value in predicted.values()),
                                'Functional reference head is not finite FP64')
                        terminals.append(predicted)
                        clean_values['role%d_clean_H0' % role] = clean.detach().cpu().numpy()
                        clean_headers['role%d_clean_H0' % role] = tensor_header(clean)
                    observations = []
                    for index, transform in enumerate(case['transforms']):
                        rotation = torch.tensor(transform['rotation_float64'], dtype=torch.float64, device='cuda:0')
                        for field in common.FIELDS:
                            vector = field == 'p_dipole'
                            actual_d = old_head.linear_transform(original_calls[0][3][field].to('cuda:0').double(), rotation, vector)
                            actual_d = original_calls[index+1][3][field].to('cuda:0').double()-actual_d
                            reference_d = terminals[index+1][field]-old_head.linear_transform(terminals[0][field], rotation, vector)
                            flat = int(actual_d.abs().argmax()); width = actual_d.shape[1]
                            observations.append({'field': field, 'transform': transform['name'],
                                'R64_orthogonality_maxabs': transform['orthogonality_maxabs'],
                                'GPU_FP32_with_FP64_L': max_record(actual_d), 'full_encoder_functional_head_FP64_D': max_record(reference_d),
                                'FP32_minus_FP64_D': max_record(actual_d-reference_d),
                                'at_same_original_GPU_argmax': {'row': flat//width, 'component': flat%width,
                                    'GPU_FP32_with_FP64_L': float(actual_d.reshape(-1)[flat]),
                                    'FP64': float(reference_d.reshape(-1)[flat]),
                                    'FP32_minus_FP64': float((actual_d-reference_d).reshape(-1)[flat])},
                                'not_original_FP32_physics_acceptance': True})
                    import numpy as np
                    h0_path = args.output_root/('reference_case%02d_H0.npz' % ordinal)
                    with h0_path.open('xb') as stream:
                        np.savez(stream, **clean_values); stream.flush(); os.fsync(stream.fileno())
                    with np.load(h0_path, allow_pickle=False) as archive:
                        require(set(archive.files) == set(clean_headers), 'Typed reference H0 output keys differ')
                        for key in archive.files:
                            value = archive[key]
                            require(value.dtype == np.float64 and value.shape == (44, 512)
                                and hashlib.sha256(value.tobytes()).hexdigest() == clean_headers[key]['sha256'],
                                'Typed allow_pickleFalse output roundtrip failed')
                    require(raw_state_headers(original) == state_before and raw_state_headers(reference) == reference_before,
                            'Original or reference state changed')
                    row = {'case_id': spec.identity, 'stage_metrics': stage_analysis(replay[spec.identity], refs),
                        'terminal_observations': observations, 'FP64_clean_H0': {'file': ref(h0_path), 'arrays': clean_headers},
                        'original_parameter_sha256': original_sha, 'lossless_state_mapping': mapping,
                        'original_actual_geometry_policy': geometry_policy(original.encoder),
                        'reference_actual_geometry_policy': geometry_policy(reference),
                        'reference_actual_layer_masks': [role['actual_layer_mask'] for role in refs],
                        'historical1492_encoder_buffer_rawSHA_saved': False,
                        'buffer_evidence_scope': 'current_replayed_original_to_shadow_lossless; old_named_parameters_SHA_and_all192_H0_gate; not_old_independent_buffer_SHA',
                        'S_geometry_or_pair_head_FP64_validated': False,
                        'actual_input_only': True, 'ideal_or_polar_coordinate_counterfactual': False,
                        'reference_physical_input_nodes_per_role': [len(role['input'].pos) for role in refs],
                        'reference_encoder_input_was_clean44_only': False, 'canonical_PD_nodes_per_role': 44}
                    path = args.output_root/('reference_case%02d.json' % ordinal); save(path, row)
                    case_results.append({'case_id': spec.identity, 'result': ref(path)})
                finally:
                    handle.remove(); recorder.close(); close_analysis_forwards(reference.backbone)
                del reference, original, refs, terminals, clean_values
            require(counts == {'FP32_full_encoder_returns': 192, 'FP64_full_encoder_returns': 192}
                and scientific_head_calls[0] == 192, 'Actual384 model/192scientific head call count differs')
            result = {'schema': 'model_v3_full_encoder_precision_analysis_result_v1', 'status': 'ANALYSIS_COMPLETE',
                'scope': 'ACTUAL1492_INPUT_PRECISION_ANALYSIS_ONLY', 'cases': case_results, 'case_count': 48,
                'counts': counts, 'capture_complete': protocol['capture_complete'], 'protocol': pins['analysis_protocol'],
                'functional64_scientific_bank_calls': scientific_head_calls[0],
                'functional64_scientific_field_outputs': scientific_head_calls[0]*3,
                'tiny_device_controls': small_controls,
                'accounting_validation': accounting_validation, 'original_physics_passed': 10, 'original_physics_failed': 38,
                'reference_remaining_drift_is_not_proved_coordinate_quantization_only': True,
                'FP32_error_lower_bound_proved': False, 'scientific_adoption': False}
            save(args.output_root/'ANALYSIS_RESULT.json', result)
    except BaseException as error:
        failure = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
    finally:
        after = {path: ref(path) for path in before}; save(args.output_root/'sources_after.json', after)
        stable = after == before
        summary = {'schema': 'model_v3_full_encoder_precision_analysis_closure_v1',
            'status': 'ANALYSIS_COMPLETE' if result is not None and failure is None and stable else 'FAILED',
            'counts': counts, 'failure': failure, 'sources_before_after_equal': stable,
            'functional64_scientific_bank_calls': scientific_head_calls[0],
            'result': ref(args.output_root/'ANALYSIS_RESULT.json') if result is not None else None,
            'original1492_not_replaced': True, 'scientific_adoption': False}
        save(args.output_root/('COMPLETE.json' if summary['status'] == 'ANALYSIS_COMPLETE' else 'FAILED.json'), summary)
    return 0 if failure is None and result is not None and stable else 1


if __name__ == '__main__':
    raise SystemExit(main())
