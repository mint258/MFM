#!/usr/bin/env python3
"""CPU-only same-capture-H0 arithmetic attribution, not a candidate or1435 replay."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import os
from pathlib import Path
import socket
import traceback

from shadow_common import (HERE, FIELDS, INPUT_CAP, STATE_BYTES, bound, load_npz, metadata_selfcheck,
    ref, require, save_plain, source_snapshot, state_arrays, tensor_state_identity)


def pool64(h, batch, graphs, mode):
    import torch
    result = torch.stack([h[batch == i].sum(0) for i in range(graphs)])
    if mode == 'mean':
        result = result/torch.bincount(batch, minlength=graphs).to(h.dtype)[:, None]
    return result


def linear64(module, value):
    import torch
    require(type(module).__name__ == 'Linear' and module.weight.dtype == torch.float32,
            'Known original FP32 Linear parameter topology required')
    bias = None if module.bias is None else module.bias.to(torch.float64)
    return torch.nn.functional.linear(value, module.weight.to(torch.float64), bias)


def mlp64(module, value, final=True):
    import torch
    require(isinstance(module, torch.nn.Sequential) and len(module) == (3 if final else 2)
        and type(module[1]).__name__ == 'SiLU', 'Only original Linear/SiLU topology supported')
    value = torch.nn.functional.silu(linear64(module[0], value))
    return linear64(module[2], value) if final else value


def functional64(bank, h, pos, batch):
    import torch
    h, pos = h.to(torch.float64), pos.to(torch.float64)
    graphs, results = int(batch.max())+1, {}
    fields = bank.registry.by_name()
    for name in FIELDS:
        field, key = fields[name], bank.keys[name]
        head = bank.field_heads[key]
        if field.representation in ('vector', 'magnitude'):
            require(type(head).__name__ == '_DipoleHead', 'Original graph dipole topology required')
            center = pool64(pos, batch, graphs, 'mean')
            charge = mlp64(head.charges, h)
            vector = pool64(charge*(pos-center[batch]), batch, graphs, 'sum')
            results[name] = torch.linalg.vector_norm(vector, dim=-1, keepdim=True) if head.magnitude else vector
        else:
            require(name == 'p_extensive' and field.level == 'graph', 'Only registered three graph fields')
            if field.pooling == 'learned':
                mixer = bank.pooling_mixers[key]
                require(tuple(mixer.logits.shape) == (2,), 'Original sum/mean mixer required')
                values = torch.stack((pool64(h, batch, graphs, 'sum'), pool64(h, batch, graphs, 'mean')), dim=1)
                feature = (values*mixer.logits.to(torch.float64).softmax(0)[None, :, None]).sum(1)
            else: feature = pool64(h, batch, graphs, field.pooling)
            form = bank.forms[name]
            if form == 'H2': feature = mlp64(bank.group_projectors[field.group], feature, final=False)
            require(form in ('H1', 'H2', 'H3'), 'Original graph form required')
            results[name] = mlp64(head, feature) if form == 'H3' else linear64(head, feature)
    return results


def linear_transform(value, rotation, vector):
    return value@rotation if vector else value


def decomposition(values, rotation, vector):
    f00, ft0, f0t, ftt = values
    baseline = linear_transform(f00, rotation, vector)
    d = ftt-baseline
    h = linear_transform(ft0-f00, rotation, vector)
    g = f0t-baseline
    interaction = ftt-f0t-linear_transform(ft0-f00, rotation, vector)
    closure = float((d-h-g-interaction).abs().max())
    require(closure <= 1e-10, 'Signed four-way closure exceeds fixed1e-10')
    return {'D': d, 'H': h, 'G': g, 'I': interaction}, closure


def tiny_selfcheck():
    import torch
    # Independent scalar extensive oracle and nonzero row-R vector identity.
    h = torch.tensor([[1., 2.], [3., 4.], [5., 6.]], dtype=torch.float64)
    batch = torch.tensor([0, 0, 1])
    require(torch.equal(pool64(h, batch, 2, 'sum'), torch.tensor([[4., 6.], [5., 6.]], dtype=torch.float64)),
            'Independent dense segment oracle failed')
    rotation = torch.tensor([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]], dtype=torch.float64)
    origin = torch.tensor([[.5, -.3, .7]], dtype=torch.float64)
    changed = origin+torch.tensor([[.2, .4, -.1]], dtype=torch.float64)
    parts, residual = decomposition((origin, changed, origin@rotation, changed@rotation), rotation, True)
    require(float(parts['G'].abs().max()) == 0 and float(parts['I'].abs().max()) < 1e-14
        and float(parts['H'].abs().max()) > 0, 'Nonzero vector row convention oracle failed')
    from phychem_mfm.phase1.v3_contract import FieldSpec, LabelRegistry
    from phychem_mfm.model.v3_heads import V3HeadBank
    parity = []
    for form, pooling in (('H1', 'sum'), ('H1', 'learned'), ('H2', 'sum'), ('H3', 'sum')):
        registry = LabelRegistry((FieldSpec('p_extensive', 'P', 'oracle', 'graph', pooling=pooling),
            FieldSpec('p_dipole', 'P', 'oracle', 'graph', representation='vector'),
            FieldSpec('p_dipole_magnitude', 'P', 'oracle', 'graph', representation='magnitude')),
            'fixed_h0_oracle', 'f'*64)
        with torch.random.fork_rng(devices=[]):
            torch.random.default_generator.manual_seed(641)
            bank = V3HeadBank(registry, dim=4, hidden_dim=4, forms=form, numeric_mode='compensated_fp32_v1').eval()
        with torch.no_grad():
            for mixer in bank.pooling_mixers.values(): mixer.logits.copy_(torch.tensor([-.7, .4], dtype=torch.float32))
        features = torch.tensor([[1., .5, -.25, .75], [.25, -.5, .75, 1.], [1., 1., .5, -.5], [-.5, .25, 1., .5]])
        pos = torch.tensor([[0., 0., 0.], [1., .5, 0.], [0., .5, .5], [.5, 0., 1.]])
        batch = torch.tensor([0, 0, 1, 1])
        with torch.inference_mode():
            original = bank(features, batch, pos, enabled_groups=('P',), enabled_fields=FIELDS)
            shadow = functional64(bank, features, pos, batch)
        error = max(float((original[k].to(torch.float64)-shadow[k]).abs().max()) for k in FIELDS)
        require(error <= 2e-6, 'Original-bank/functional64 small-tensor parity failed')
        require(float(original['p_dipole'].abs().max()) > 0, 'Nonzero dipole oracle required')
        parity.append({'form': form, 'pooling': pooling, 'maxabs_FP32_vs_FP64': error})
    return {'dense_segment_oracle': True, 'row_R_four_way': True, 'closure': residual,
            'head_form_small_tensor_parity': parity, 'metadata': metadata_selfcheck()}


def decode_case(leaf):
    import torch
    from phychem_mfm.phase1.v3_contract import FieldSpec, LabelRegistry
    from phychem_mfm.model.v3_heads import V3HeadBank
    case = bound(leaf['capture_case'])
    require(case['schema'] == 'model_v3_fixed_h0_capture_case_v1' and case['lineage'] == 'fresh_capture_not_1435_H0'
        and case['same_forward_control'] and len(case['calls']) == 4 and len(case['transforms']) == 3,
        'Complete new same-forward typed case required')
    arrays = load_npz(case['packed'])
    used = set(case['state_names'].values()) | {key for call in case['calls'] for key in call['keys'].values()}
    require(used == set(arrays), 'No untyped or silently ignored capture arrays permitted')
    require(case['case_id'] == leaf['case_id'], 'Capture case ID/ref mismatch')
    require(tensor_state_identity(arrays, case['state_names'], case['state_extra']) == case['bank_state_identity'],
            'Typed bank state identity differs')
    registry = dict(case['registry']); registry['fields'] = tuple(FieldSpec(**field) for field in registry['fields'])
    registry = LabelRegistry(**registry)
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(0)
        bank = V3HeadBank(registry, forms=case['forms'], **case['bank_constructor']).eval()
    state = {name: torch.from_numpy(arrays[key]) for name, key in case['state_names'].items()}
    state.update(case['state_extra'])
    require(set(state) == set(bank.state_dict()), 'Complete original bank state keys required')
    bank.load_state_dict(state, strict=True)
    require(sum(value.nbytes for name, value in arrays.items() if name in set(case['state_names'].values()))
            == STATE_BYTES[case['case']['head_policy']], 'Actual state bytes differ')
    calls = []
    for call in case['calls']:
        keys = call['keys']
        h, batch, pos = [torch.from_numpy(arrays[keys[name]]) for name in ('H0', 'batch', 'pos')]
        require(h.dtype == pos.dtype == torch.float32 and batch.dtype == torch.int64
            and tuple(h.shape) == (44, 512) and tuple(pos.shape) == (44, 3) and tuple(batch.shape) == (44,)
            and torch.equal(torch.bincount(batch), torch.tensor([3, 9, 32])), 'Actual captured bank input domain differs')
        outputs = {name: torch.from_numpy(arrays[keys['out_'+name]]) for name in FIELDS}
        calls.append((h, pos, batch, outputs))
    require(all(torch.equal(calls[0][2], c[2]) for c in calls), 'Captured graph identities changed')
    return case, bank, calls


def evaluate(payload):
    import torch
    case, bank, calls = payload
    def evaluate32(h, pos, batch):
        return {k: v.to(torch.float64) for k, v in bank(h, batch, pos,
            enabled_groups=('P',), enabled_fields=FIELDS).items()}
    with torch.inference_mode():
        h0, pos0, batch, gpu0 = calls[0]
        f32base, f64base = evaluate32(h0, pos0, batch), functional64(bank, h0, pos0, batch)
        observations = []
        for index, (ht, post, batcht, gput) in enumerate(calls[1:]):
            rotation = torch.tensor(case['transforms'][index]['rotation_float64'], dtype=torch.float64)
            v32 = (f32base, evaluate32(ht, pos0, batch), evaluate32(h0, post, batch), evaluate32(ht, post, batch))
            v64 = (f64base, functional64(bank, ht, pos0, batch), functional64(bank, h0, post, batch), functional64(bank, ht, post, batch))
            for name in FIELDS:
                vector = name == 'p_dipole'
                p32, c32 = decomposition(tuple(v[name] for v in v32), rotation, vector)
                p64, c64 = decomposition(tuple(v[name] for v in v64), rotation, vector)
                gpu_d = gput[name].to(torch.float64)-linear_transform(gpu0[name].to(torch.float64), rotation, vector)
                head_delta = gpu_d-p64['D']
                flat = int(gpu_d.abs().argmax()); columns = gpu_d.shape[1]; row, component = flat//columns, flat%columns
                terms = {**p64, 'GPU_FP32_D': gpu_d, 'head_arithmetic_delta': head_delta, 'CPU_FP32_D': p32['D']}
                require(float((gpu_d-p64['H']-p64['G']-p64['I']-head_delta).abs().max()) <= 1e-10,
                        'GPU = inheritedH0 + geometry + interaction + head arithmetic closure failed')
                if name == 'p_extensive':
                    require(float(p64['G'].abs().max()) == float(p64['I'].abs().max()) == 0,
                            'Scalar position-independence oracle failed')
                observations.append({'field': name, 'transform': case['transforms'][index]['name'],
                    'signed_components': {k: value.tolist() for k, value in terms.items()},
                    'maxabs': {k: float(value.abs().max()) for k, value in terms.items()},
                    'GPU_argmax': {'row': row, 'component': component,
                        'same_component_terms': {k: float(value[row, component]) for k, value in terms.items()}},
                    'CPU_FP32_closure': c32, 'FP64_closure': c64,
                    'CPU_FP32_vs_GPU_moved_maxabs': float((v32[3][name]-gput[name].to(torch.float64)).abs().max()),
                    'not_FP32_acceptance': True})
    require(len(observations) == 9, 'All3 fields/all3 transforms required')
    arrays, names, extras = state_arrays(bank)
    require(tensor_state_identity(arrays, names, extras) == case['bank_state_identity'], 'Bank state changed during shadow')
    return {'case_id': case['case_id'], 'observations': observations, 'bank_state_identity': case['bank_state_identity']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-complete', type=Path, required=True); parser.add_argument('--capture-complete-sha256', required=True)
    parser.add_argument('--capture-supervisor', type=Path, required=True); parser.add_argument('--capture-supervisor-sha256', required=True)
    parser.add_argument('--capture-accounting', type=Path, required=True); parser.add_argument('--capture-accounting-sha256', required=True)
    parser.add_argument('--source-pins-sha256', required=True); parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--expected-node', choices=['compute-0-'+str(i) for i in (2, *range(8, 20))], required=True)
    args = parser.parse_args()
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and socket.gethostname().split('.')[0] == args.expected_node
        and os.environ.get('SLURM_JOB_ID', '').isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) == 16,
        'Actual16CPU-only allocation required')
    complete = bound({**ref(args.capture_complete), 'sha256': args.capture_complete_sha256})
    require(complete['schema'] == 'model_v3_fixed_h0_capture_complete_v1', 'Capture completion type differs')
    capture = bound(complete['manifest'])
    require(capture['schema'] == 'model_v3_fixed_h0_capture_manifest_v1' and capture['status'] == 'CAPTURE_COMPLETE'
        and capture['failure'] is None and capture['source_before_after_equal'] and len(capture['cases']) == 48
        and capture['input_bytes_before_manifest'] <= INPUT_CAP and capture['input_limit_bytes'] == INPUT_CAP
        and capture['encoder_forwards'] == capture['completed_case_encoder_forwards'] == 192
        and capture['lineage'] == 'fresh_capture_not_1435_H0', 'Complete stable new48 capture required')
    supervisor = bound({**ref(args.capture_supervisor), 'sha256': args.capture_supervisor_sha256})
    require(supervisor['job_id'] == capture['job_id'] and supervisor['status'] == 'COMPLETED'
        and supervisor['exit_code'] == 0 and supervisor['first_failure'] is None
        and supervisor['remaining_recorded_processes_before_retirement'] == []
        and supervisor['private_storage_cleanup_errors'] == [], 'Actual capture supervisor must close successfully')
    accounting = bound({**ref(args.capture_accounting), 'sha256': args.capture_accounting_sha256})
    expected_accounting = ['sacct', '-n', '-P', '-j', capture['job_id'], '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS']
    require(accounting['argv'] == expected_accounting and accounting['returncode'] == 0
        and hashlib.sha256(accounting['stdout'].encode()).hexdigest() == accounting['stdout_sha256'], 'Bound Root raw accounting required')
    lines = [x.split('|') for x in accounting['stdout'].splitlines() if x.strip()]
    require(len(lines) == 1 and lines[0][:4] == [capture['job_id'], 'zixiao', 'COMPLETED', '0:0']
        and int(lines[0][4]) >= 0 and lines[0][5] == '16', 'Actual terminalC0 capture accounting required')
    capture_files = [path for path in args.capture_complete.parent.rglob('*') if path.is_file()]
    require(all(not path.is_symlink() for path in capture_files)
        and sum(path.stat().st_size for path in capture_files) <= INPUT_CAP, 'Actual complete input scope exceeds128MiB')
    request = bound(capture['request'])
    require(capture['source_pins'] == ref(HERE/'source_pins_v1.json') and capture['source_pins']['sha256'] == args.source_pins_sha256,
            'Same capture/shadow source version required')
    sources = source_snapshot(request, args.source_pins_sha256)
    require([r['case_id'] for r in capture['cases']] == request['expected_case_ids'], 'All original48 cases required')
    expected_command = [request['GPU_python'], '-u', '-B', str(HERE/'capture_fixed_h0_v1.py'),
        '--request', capture['request']['path'], '--request-sha256', capture['request']['sha256'],
        '--output-root', str(args.capture_complete.parent)]
    require(supervisor['command'] == expected_command, 'Actual supervised capture argv differs')
    require(supervisor['supervisor_source_sha256'] == request['supervisor_source']['sha256']
        and supervisor['gpu_uuid'] == request['gpu_uuid'] and supervisor['foreign_gpu_processes_signalled'] is False,
        'Actual fixed capture supervisor source/GPU scope differs')
    require(not args.output_root.exists(), 'Fresh CPU shadow output required'); args.output_root.mkdir()
    save_plain(args.output_root/'sources_before.json', sources)
    result, failure = None, None
    try:
        import phychem_mfm
        require(Path(phychem_mfm.__file__).resolve() == (Path(request['repository'])/'current/phychem_mfm/__init__.py').resolve(),
                'CPU shadow imported a foreign model namespace')
        import torch
        torch.set_num_threads(4)
        selfcheck = tiny_selfcheck()
        payloads = [decode_case(leaf) for leaf in capture['cases']]
        with ThreadPoolExecutor(max_workers=4) as executor: rows = list(executor.map(evaluate, payloads))
        require([row['case_id'] for row in rows] == request['expected_case_ids'], 'Shadow full48 membership differs')
        result = {'schema': 'model_v3_fixed_h0_terminal_shadow_result_v1', 'status': 'SHADOW_COMPLETE',
            'capture_complete': ref(args.capture_complete), 'capture_supervisor': ref(args.capture_supervisor),
            'capture_accounting': ref(args.capture_accounting), 'lineage': 'fresh_capture_not_1435_H0',
            'cases': rows, 'case_count': 48, 'field_transform_observations': 432,
            'selfcheck': selfcheck, 'physical_FP32_threshold_changed': False, 'scientific_adoption': False}
        save_plain(args.output_root/'SHADOW_RESULT.json', result)
        with (args.output_root/'shadow_summary.csv').open('x', newline='') as stream:
            writer = csv.writer(stream); keys = ('GPU_FP32_D', 'CPU_FP32_D', 'D', 'H', 'G', 'I', 'head_arithmetic_delta')
            writer.writerow(['case_id', 'field', 'transform', *('maxabs_'+k for k in keys)])
            for row in rows:
                for obs in row['observations']: writer.writerow([row['case_id'], obs['field'], obs['transform'], *(obs['maxabs'][k] for k in keys)])
            stream.flush(); os.fsync(stream.fileno())
    except BaseException as error:
        failure = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
    finally:
        after = {path: ref(path) for path in sources}; save_plain(args.output_root/'sources_after.json', after)
        require(after == sources, 'Shadow source changed')
        if failure is not None: save_plain(args.output_root/'FAILED.json', failure)
        elif result is not None: save_plain(args.output_root/'COMPLETE.json', {'schema': 'model_v3_fixed_h0_terminal_shadow_complete_v1',
            'result': ref(args.output_root/'SHADOW_RESULT.json'), 'sources_unchanged': True})
    return 1 if failure else 0


if __name__ == '__main__':
    raise SystemExit(main())
