#!/usr/bin/env python3
"""Read-only full-matrix layer/head attribution; no model fix or adoption."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
import traceback

import numpy as np
import torch
from torch import nn
import torch.nn.functional as functional

sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
B = Path('/share/home/zixiao/descriptor_analysis')
DESIGN = B/'runs/model_v3_20261026/eq_layer_head_diagnostic_v1'
LEGACY_PATH = B/'runs/model_v3_20261026/eq_diagnostic_v1/diagnose_aggregation.py'
LEGACY_SHA = 'b3bf90764e4799258b1115d16f8567c06d14dd8bcc67efdc0306ccd32d77dee0'
PLAN_SHA = '5f7c8022870789eaaea847493079d71fb1d5bfba0eebd0009078a1bf4a2ebef6'
ATTRIBUTION_SHA = '6b24cb45e70803c5bdd22f147a0ece278fd02aac0b191c557adcebe4702ad4d1'
OUTPUT_CAP = 64*1024**2
WALL_CAP = 600
TARGET_FIELDS = ('p_extensive', 'p_dipole', 'p_dipole_magnitude')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def assert_unchanged_weights(equation, model, expected, message):
    # measure_case creates parameters in inference mode; preserve that mode
    # while invoking the exact original finite/hash validation.
    with torch.inference_mode():
        require(equation.weight_summary(model) == expected, message)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def legacy():
    require(sha(LEGACY_PATH.read_bytes()) == LEGACY_SHA, 'Frozen attribution support source changed')
    specification = importlib.util.spec_from_file_location('frozen_eq_attribution_support_v1', LEGACY_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def tensor_digest(value):
    value = value.detach().cpu().contiguous()
    header = json.dumps({'dtype': str(value.dtype), 'shape': list(value.shape)}, sort_keys=True).encode()
    return sha(header+b'\0'+value.numpy().tobytes())


def compare(actual, expected):
    require(actual.shape == expected.shape and actual.numel() > 0, 'Corresponding nonempty diagnostic arrays required')
    a, e = actual.detach().cpu().double(), expected.detach().cpu().double()
    require(bool(torch.isfinite(a).all() and torch.isfinite(e).all()), 'Nonfinite diagnostic reference')
    difference = a-e
    index = int(difference.abs().reshape(-1).argmax())
    coordinate = [int(item) for item in np.unravel_index(index, tuple(a.shape))]
    return {'shape': list(a.shape), 'count': a.numel(), 'maxabs': float(difference.abs().max()),
        'mean_squared_error': float(difference.square().mean()), 'argmax': coordinate,
        'actual': float(a.reshape(-1)[index]), 'expected': float(e.reshape(-1)[index]),
        'signed_error_at_argmax': float(difference.reshape(-1)[index]),
        'actual_dtype': str(actual.dtype), 'expected_dtype': str(expected.dtype),
        'actual_sha256': tensor_digest(actual), 'expected_sha256': tensor_digest(expected)}


def pool64(h, batch, graphs, mode):
    require(h.dtype == torch.float64 and mode in ('sum', 'mean'), 'Declared FP64 pool reference required')
    value = h.new_zeros((graphs, h.shape[-1])).index_add(0, batch, h)
    if mode == 'mean':
        value = value/torch.bincount(batch, minlength=graphs).double()[:, None]
    return value


def shadow_mlp(module, value):
    """Functional same-weight FP64 reference; never casts the real model."""
    require(value.dtype == torch.float64, 'FP64 reference input required')
    if isinstance(module, nn.Linear):
        bias = None if module.bias is None else module.bias.detach().double()
        return functional.linear(value, module.weight.detach().double(), bias)
    if type(module) is nn.SiLU:
        return functional.silu(value)
    if type(module) is nn.Sequential:
        for child in module:
            value = shadow_mlp(child, value)
        return value
    raise ValueError('Unknown module in declared shadow: '+type(module).__qualname__)


def shadow_head(bank, field, h, pos, batch):
    h, pos = h.double(), pos.double()
    graphs = int(batch.max())+1
    key = bank.keys[field.name]
    head = bank.field_heads[key]
    if field.representation in ('vector', 'magnitude'):
        require(type(head).__name__ == '_DipoleHead', 'Expected actual graph dipole source')
        q = shadow_mlp(head.charges, h)
        center = pool64(pos, batch, graphs, 'mean')
        relative = pos-center[batch]
        terms = q*relative
        vector = terms.new_zeros((graphs, 3)).index_add(0, batch, terms)
        return (vector.norm(dim=-1, keepdim=True) if head.magnitude else vector), {
            'charges': q, 'center': center, 'relative': relative, 'terms': terms, 'vector': vector}
    require(field.level == 'graph' and field.representation == 'scalar', 'Only declared failing graph families are replayed')
    if field.pooling == 'learned':
        mixer = bank.pooling_mixers[key]
        probability = mixer.logits.detach().double().softmax(0)
        pooled = (torch.stack((pool64(h, batch, graphs, 'sum'), pool64(h, batch, graphs, 'mean')), 1)
            *probability[None, :, None]).sum(1)
    else:
        pooled = pool64(h, batch, graphs, field.pooling)
    feature = pooled
    if bank.forms[field.name] == 'H2':
        feature = shadow_mlp(bank.group_projectors[field.group], feature)
    return shadow_mlp(head, feature), {'pool': pooled, 'feature': feature}


def transform_value(value, rotation, law):
    require(law in ('invariant', 'vector'), 'Explicit head output law required')
    value = value.double()
    return value@rotation.double() if law == 'vector' else value


def four_way(y00, y10, y01, y11, rotation, law):
    total = y11.double()-transform_value(y00, rotation, law)
    feature = transform_value(y10.double()-y00.double(), rotation, law)
    coordinate = y01.double()-transform_value(y00, rotation, law)
    interaction = total-feature-coordinate
    closure = total-(feature+coordinate+interaction)
    require(float(closure.abs().max()) <= 1e-12*max(1., float(total.abs().max())), 'FP64 bookkeeping identity failed')
    return {name: {**compare(value, torch.zeros_like(value)), 'values': value.tolist()} for name, value in (
        ('total', total), ('H0_effect', feature), ('coordinate_effect', coordinate),
        ('interaction', interaction), ('bookkeeping_residual', closure))}


def tensor_parts(value):
    if isinstance(value, torch.Tensor):
        return {'': value}
    if isinstance(value, (tuple, list)):
        require(all(isinstance(item, torch.Tensor) for item in value), 'Unknown nested trace output')
        return {'.'+str(i): item for i, item in enumerate(value)}
    raise ValueError('Unknown trace return type')


class ReadOnlyCapture:
    """Forward hooks copy values and always return None."""
    def __init__(self):
        self.handles = []
        self.values = {}
        self.phase = -1

    def record(self, name, value):
        require(self.phase in range(4), 'Exactly four original encoder phases required')
        for suffix, item in tensor_parts(value).items():
            require(item.dtype == torch.float32, 'Actual trace tensor must remain FP32')
            key = name+suffix
            self.values.setdefault(key, {}).setdefault(self.phase, []).append(item.detach().cpu().clone())

    def watch(self, name, module, *, before=False, first=False):
        if before:
            def hook(unused, inputs):
                self.record(name, inputs[0])
                return None
            handle = module.register_forward_pre_hook(hook)
        else:
            def hook(unused, inputs, output):
                self.record(name, output[0] if first else output)
                return None
            handle = module.register_forward_hook(hook)
        self.handles.append(handle)

    def close(self):
        for handle in self.handles:
            handle.remove()
        self.handles.clear()

class CompositionTrace(ReadOnlyCapture):
    def __init__(self, model, registry):
        super().__init__()
        self.model, self.registry = model, registry
        self.physical, self.bank_inputs, self.bank_outputs = {}, {}, {}
        backbone = model.encoder.backbone
        require(len(backbone.layers) == 6 and backbone.dim == 512, 'Actual6x512 required')
        def start(unused, inputs):
            self.phase += 1
            require(self.phase < 4, 'Unexpected extra encoder pass')
            data = inputs[0]
            self.physical[self.phase] = {name: getattr(data, name).detach().cpu().clone()
                for name in ('pos', 'target_pos', 'batch')}
            return None
        self.handles.append(backbone.register_forward_pre_hook(start))
        self.watch('embedding', backbone.atom_emb)
        for number, layer in enumerate(backbone.layers):
            prefix = 'layer.'+str(number)
            for name in ('norm1', 'norm2', 'ffn'):
                self.watch(prefix+'.'+name, getattr(layer, name))
            self.watch(prefix+'.attn', layer.attn, first=not hasattr(backbone, 'pair_encoder'))
            self.watch(prefix+'.output', layer)
            if hasattr(backbone, 'pair_encoder'):
                self.watch(prefix+'.pair_projection', layer.attn.pair_projection)
            else:
                self.watch(prefix+'.distance_input', layer.attn.dist_mlp, before=True)
                self.watch(prefix+'.distance_output', layer.attn.dist_mlp)
        if hasattr(backbone, 'pair_encoder'):
            self.watch('pair', backbone.pair_encoder)
        self.watch('out_norm.input', backbone.out_norm, before=True)
        self.watch('out_norm.output', backbone.out_norm)
        bank = model.pd_heads
        def bank_before(unused, inputs):
            require(self.phase not in self.bank_inputs, 'One PD call per full encoder pass required')
            self.bank_inputs[self.phase] = tuple(value.detach().cpu().clone() for value in inputs[:3])
            return None
        def bank_after(unused, inputs, output):
            self.bank_outputs[self.phase] = {name: value.detach().cpu().clone() for name, value in output.items()}
            return None
        self.handles.extend((bank.register_forward_pre_hook(bank_before), bank.register_forward_hook(bank_after)))
        for field in bank.registry.fields:
            if field.level != 'graph':
                continue
            key = bank.keys[field.name]
            for name, module in bank.field_heads[key].named_modules():
                if isinstance(module, nn.Linear) or type(module) is nn.SiLU:
                    self.watch('PD/'+field.name+'/'+(name or 'linear'), module)
            if key in bank.pooling_mixers:
                self.watch('PD/'+field.name+'/mixer', bank.pooling_mixers[key])
        for group, projector in bank.group_projectors.items():
            for name, module in projector.named_modules():
                if isinstance(module, nn.Linear) or type(module) is nn.SiLU:
                    self.watch('PD/projector_'+group+'/'+name, module)

    def complete(self):
        require(self.phase == 3 and set(self.bank_inputs) == set(self.bank_outputs) == set(range(4)), 'Missing complete encoder/head phase')
        for phases in self.values.values():
            require(set(phases) == set(range(4)) and len({len(items) for items in phases.values()}) == 1,
                'Trace module membership/call count changed by transform')


def select_graph(value, batch, graph, *, dense):
    count = int((batch == graph).sum())
    graphs = int(batch.max())+1
    if value.shape[0] == len(batch):
        return value[batch == graph]
    require(value.shape[0] == graphs, 'Unknown graph trace leading dimension')
    selected = value[graph]
    if dense:
        require(value.ndim >= 3, 'Dense trace has no atom axis')
        width = int(torch.bincount(batch).max())
        selected = selected[:count]
        if value.ndim >= 3 and value.shape[2] == width:
            selected = selected[:, :count]
    return selected


def layer_summaries(trace, transforms):
    trace.complete()
    result = []
    for phase, transform in enumerate(transforms, 1):
        rows = []
        for name, phases in trace.values.items():
            pd = name.startswith('PD/')
            batch = trace.bank_inputs[0][1] if pd else trace.physical[0]['batch']
            for call, (before, after) in enumerate(zip(phases[0], phases[phase])):
                for graph in range(int(batch.max())+1):
                    dense = not pd and before.shape[0] != len(batch) and before.ndim >= 3
                    a = select_graph(after, batch, graph, dense=dense)
                    b = select_graph(before, batch, graph, dense=dense)
                    if name.startswith('PD/pool/width3/'):
                        b = b.double()@transform.rotation+transform.translation
                    rows.append({'module': name, 'call': call, 'graph': graph,
                        'law': 'coordinate' if name.startswith('PD/pool/width3/') else 'invariant',
                        'valid_atom_count': int((batch == graph).sum()), **compare(a, b)})
        result.append({'transform': transform.name, 'stages': rows})
    return result


def input_and_distance_summaries(trace, transforms):
    result = []
    distance_names = (['pair.1'] if 'pair.1' in trace.values else
        ['layer.'+str(i)+'.distance_input' for i in range(6)])
    for phase, transform in enumerate(transforms, 1):
        original, moved = trace.physical[0], trace.physical[phase]
        batch = original['batch']
        require(torch.equal(batch, moved['batch']), 'Physical graph order changed')
        graphs = []
        for graph in range(int(batch.max())+1):
            rows = batch == graph
            p0, p1 = original['pos'][rows].double(), moved['pos'][rows].double()
            t0, t1 = original['target_pos'][rows].double(), moved['target_pos'][rows].double()
            exact0 = (p0[:, None]-p0[None, :]).square().sum(-1)
            exact1 = (p1[:, None]-p1[None, :]).square().sum(-1)
            distances = []
            for name in distance_names:
                d0 = select_graph(trace.values[name][0][0], batch, graph, dense=True).double()
                d1 = select_graph(trace.values[name][phase][0], batch, graph, dense=True).double()
                squared = name != 'pair.1'
                if squared:
                    d0, d1 = d0.squeeze(-1), d1.squeeze(-1)
                e0, e1 = (exact0, exact1) if squared else (exact0.sqrt(), exact1.sqrt())
                arithmetic_change = (d1-e1)-(d0-e0)
                distances.append({'module': name, 'unit': 'Angstrom_squared' if squared else 'Angstrom',
                    'input_rounding_effect': compare(e1, e0),
                    'original_arithmetic_residual': compare(d0, e0),
                    'moved_arithmetic_residual': compare(d1, e1),
                    'arithmetic_residual_change': compare(arithmetic_change, torch.zeros_like(arithmetic_change)),
                    'bookkeeping_residual': compare((d1-d0)-((e1-e0)+arithmetic_change), torch.zeros_like(d0))})
            graphs.append({'graph': graph, 'atoms': int(rows.sum()),
                'input_cast_residual_A': compare(p1, p0@transform.rotation+transform.translation),
                'noise_pushforward_residual_A': compare(p1-t1, (p0-t0)@transform.rotation), 'distances': distances})
        result.append({'transform': transform.name, 'physical_graphs': graphs})
    return result


def fp32_dipole_parts(head, h, pos, batch, pool):
    graphs = int(batch.max())+1
    q = head.charges(h.float())
    center = pool(pos.float(), batch, graphs, 'mean')
    relative = pos.float()-center[batch]
    terms = q*relative
    vector = pos.float().new_zeros((graphs, 3)).index_add(0, batch, terms)
    output = vector.norm(dim=-1, keepdim=True) if head.magnitude else vector
    return output, {'charges': q, 'center': center, 'relative': relative, 'terms': terms, 'vector': vector}


def moment_summaries(parts, batch):
    result = []
    for graph in range(int(batch.max())+1):
        rows = batch == graph
        terms = parts['terms'][rows].double()
        vector = parts['vector'][graph].double()
        absolute_sum = terms.abs().sum(0)
        denominator = vector.abs()
        result.append({'graph': graph, 'charges': compare(parts['charges'][rows], torch.zeros_like(parts['charges'][rows])),
            'charge_mean': float(parts['charges'][rows].double().mean()),
            'charge_sum': float(parts['charges'][rows].double().sum()),
            'charge_population_std': float(parts['charges'][rows].double().std(unbiased=False)),
            'center': parts['center'][graph].double().tolist(),
            'centered_coordinate_sum': parts['relative'][rows].double().sum(0).tolist(),
            'sum_absolute_moment_terms': absolute_sum.tolist(), 'actual_vector': vector.tolist(),
            'cancellation_ratios': [float(a/b) if b != 0 else None for a, b in zip(absolute_sum, denominator)]})
    return result


def replay_heads(trace, transforms, heads):
    bank = trace.model.pd_heads
    h0, batch, p0 = trace.bank_inputs[0]
    result = []
    for phase, transform in enumerate(transforms, 1):
        h1, moved_batch, p1 = trace.bank_inputs[phase]
        require(torch.equal(batch, moved_batch), 'Clean head graph identities changed')
        fields = []
        for name in TARGET_FIELDS:
            field = bank.registry.by_name()[name]
            law = 'vector' if field.representation == 'vector' else 'invariant'
            values, references, details32, details64 = {}, {}, {}, {}
            for code, h, pos in (('00', h0, p0), ('10', h1, p0), ('01', h0, p1), ('11', h1, p1)):
                value = bank(h, batch, pos, enabled_groups=(field.group,), enabled_fields=(name,))[name]
                require(value.dtype == torch.float32, 'Actual replay must remain FP32')
                values[code] = value
                references[code], details64[code] = shadow_head(bank, field, h, pos, batch)
                if field.representation in ('vector', 'magnitude'):
                    literal, parts = fp32_dipole_parts(bank.field_heads[bank.keys[name]], h, pos, batch, heads._pool)
                    require(torch.equal(literal, value), 'Magnitude/vector reconstruction differs from actual own head')
                    details32[code] = moment_summaries(parts, batch)
                else:
                    key = bank.keys[name]
                    pool = bank.pooling_mixers[key](h, batch, 3) if field.pooling == 'learned' else heads._pool(h, batch, 3, field.pooling)
                    details32[code] = {'pool_rounding': compare(pool, details64[code]['pool'])}
            require(torch.equal(values['00'], trace.bank_outputs[0][name])
                    and torch.equal(values['11'], trace.bank_outputs[phase][name]), 'Head replay changed full-batch original output')
            row = {'field': name, 'law': law, 'unit': field.unit,
                'actual_FP32_cross_decomposition': four_way(values['00'], values['10'], values['01'], values['11'], transform.rotation, law),
                'FP64_shadow_cross_decomposition_NOT_acceptance': four_way(references['00'], references['10'], references['01'], references['11'], transform.rotation, law),
                'FP32_minus_same_weight_FP64_shadow': {code: compare(values[code], references[code]) for code in values},
                'original_FP32_intermediates': details32,
                'actual_FP32_cross_values': {code: value.double().tolist() for code, value in values.items()},
                'FP64_shadow_cross_values_NOT_acceptance': {code: value.tolist() for code, value in references.items()}}
            if field.representation in ('vector', 'magnitude'):
                q0, q1 = details64['00']['charges'], details64['10']['charges']
                r0, r1 = details64['00']['relative'], details64['01']['relative']
                dr = r1-r0@transform.rotation
                feature = pool64((q1-q0)*r0, batch, 3, 'sum')@transform.rotation
                coordinate = pool64(q0*dr, batch, 3, 'sum')
                interaction = pool64((q1-q0)*dr, batch, 3, 'sum')
                total = details64['11']['vector']-details64['00']['vector']@transform.rotation
                row['own_charge_vector_FP64_bilinear_identity'] = {name: compare(value, torch.zeros_like(value))
                    for name, value in (('q_change', feature), ('position_change', coordinate), ('interaction', interaction),
                        ('closure', total-feature-coordinate-interaction))}
            elif bank.forms[name] == 'H1':
                head = bank.field_heads[bank.keys[name]]
                require(isinstance(head, nn.Linear), 'H1 must remain a literal affine head')
                difference = details64['11']['pool']-details64['00']['pool']
                analytic = functional.linear(difference, head.weight.detach().double(), None)
                row['H1_exact_linear_pool_delta_reference'] = compare(
                    references['11']-references['00'], analytic)
            fields.append(row)
        result.append({'transform': transform.name, 'fields': fields,
            'clean_H0_by_graph': [{'graph': graph, **compare(h1[batch == graph], h0[batch == graph])}
                for graph in range(int(batch.max())+1)]})
    return result

@contextmanager
def capture_composition(equation, heads):
    """Only attach read-only hooks and a transparent original-pool wrapper."""
    original_builder, original_pool = equation.build_composition, heads._pool
    holder = {}
    def builder(spec):
        require('trace' not in holder, 'One actual composition per measured case')
        model, registry = original_builder(spec)
        holder['trace'] = CompositionTrace(model, registry)
        return model, registry
    def captured_pool(h, batch, graphs, mode):
        result = original_pool(h, batch, graphs, mode)
        trace = holder.get('trace')
        if trace is not None:
            name = 'PD/pool/width'+str(h.shape[-1])+'/'+mode
            trace.record(name+'.input', h)
            trace.record(name+'.output', result)
        return result
    equation.build_composition, heads._pool = builder, captured_pool
    try:
        yield holder
    finally:
        trace = holder.get('trace')
        if trace is not None:
            trace.close()
        equation.build_composition, heads._pool = original_builder, original_pool
        require(equation.build_composition is original_builder and heads._pool is original_pool,
            'Original factory/pool callable identities were not restored')


def ensure_terminal_equality(first, second):
    """Read only new control/replay archives; no old baseline NPZ is read."""
    require(first != second, 'Independent fresh control and replay artifacts required')
    for path in (first, second):
        require(Path(path).is_file() and not Path(path).is_symlink(), 'Ordinary fresh terminal archive required')
    with np.load(first, allow_pickle=False) as a, np.load(second, allow_pickle=False) as b:
        require(set(a.files) == set(b.files) and len(a.files) == 52, 'Complete4x13 terminal membership required')
        for name in a.files:
            x, y = a[name], b[name]
            require(x.dtype == y.dtype == np.float32 and x.ndim == y.ndim == 2 and x.shape == y.shape,
                'Corresponding original-unit FP32 terminal arrays required')
            require(x.tobytes() == y.tobytes(), 'Hook changed raw terminal: '+name)
    return {'archive_arrays': 52, 'all_original_and_three_transformed_terminals_bitwise_equal': True}


def complete_membership(actual, expected):
    require(len(actual) == len(expected) == 48 and len(set(actual)) == 48 and actual == expected,
        'Exact ordered complete48 cases required; missing/duplicate/reordered membership')


def save_trace(path, value):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))+'\n').encode()
    require(len(raw) <= 8*1024**2, 'Bounded in-memory trace JSON required')
    compressed = gzip.compress(raw, mtime=0)
    require(len(compressed) <= 512*1024, 'Per-case compressed trace512KiB cap exceeded')
    require(not path.exists() and not path.is_symlink(), 'Never overwrite a diagnostic trace')
    with path.open('xb') as stream:
        stream.write(compressed)
        stream.flush()
        os.fsync(stream.fileno())
    return {'path': str(path), 'bytes': len(compressed), 'sha256': sha(compressed),
        'encoding': 'gzip_json_utf8', 'uncompressed_bytes': len(raw), 'uncompressed_sha256': sha(raw)}


def source_files(support, equation, repository):
    sources = support.source_files(equation, repository)
    for path in (LEGACY_PATH, DESIGN/'PLAN.md', DESIGN/'protocol_draft_v1.json', DESIGN/'source_pins_v1.json',
            HERE/'instrument_layer_heads.py', HERE/'test_layer_head_attribution.py',
            HERE/'README.md', HERE/'execution_protocol_v1.json'):
        reference = support.binding(path)
        sources[reference['path']] = {'bytes': reference['bytes'], 'sha256': reference['sha256']}
    return sources


def make_request(repository, aggregate, node):
    support = legacy()
    require(sha((DESIGN/'PLAN.md').read_bytes()) == PLAN_SHA, 'Root-reviewed design changed')
    design = support.bound_json(support.binding(DESIGN/'protocol_draft_v1.json'))
    attribution = support.bound_json(design['closed_aggregate'])
    require(design['closed_aggregate']['sha256'] == ATTRIBUTION_SHA and attribution['original_exact_replay'] is True
        and attribution['all336_cases_complete'] is True and attribution['all13104_measurements_included'] is True,
        'Actual closed attribution report must bind the reviewed follow-up')
    base = support.make_request(repository, aggregate, node)
    equation, _ = support.import_equation(repository)
    implementation = support.bound_json(support.binding(HERE/'execution_protocol_v1.json'))
    require(implementation['schema'] == 'model_v3_C4_layer_head_execution_protocol_v1'
        and implementation['reviewed_PLAN_sha256'] == PLAN_SHA and implementation['full_encoder_forwards'] == 384
        and implementation['child_output_cap_bytes'] == OUTPUT_CAP and implementation['absolute_tolerance'] == 1e-5
        and implementation['relative_tolerance'] == 0, 'Declared implementation/method protocol differs')
    sources = source_files(support, equation, repository)
    return {'schema': 'model_v3_C4_layer_head_request_v1', 'status': 'FROZEN_NOT_EXECUTED_DIAGNOSTIC_ONLY',
        'equation_repository': str(Path(repository).absolute()), 'baseline_aggregate': base['baseline_aggregate'],
        'closed_prior_attribution': design['closed_aggregate'], 'design_PLAN': support.binding(DESIGN/'PLAN.md'),
        'execution_protocol': support.binding(HERE/'execution_protocol_v1.json'), 'expected_node': node,
        'cases': base['cases'], 'equation_protocol_sha256': base['equation_protocol_sha256'],
        'source_files': sources, 'source_inventory_sha256': equation.canonical_hash(sources),
        'Torch_and_BLAS_threads': 1, 'device': 'cpu', 'full_encoder_forwards': 384,
        'child_output_cap_bytes': OUTPUT_CAP, 'child_wall_seconds': WALL_CAP,
        'old_NPZ_reads': 0, 'native_data_or_labels_or_checkpoints': 0,
        'scientific_selection_or_adoption': False, 'is_FP32_acceptance_evidence': False,
        'Root_CPU_test_and_public_source_binding_required_before_run': True}


def admit_CPU(request):
    node = request['expected_node']
    require(re.fullmatch(r'compute-0-(?:2|[89]|1[0-9])', node)
        and socket.gethostname().split('.')[0] == node == os.environ.get('SLURMD_NODENAME', node)
        and os.environ.get('SLURM_JOB_ID', '').isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) >= 16
        and os.environ.get('CUDA_VISIBLE_DEVICES') in ('', '-1'), 'Actual owned CPU Slurm node/allocation required')


def run(request, request_ref, output):
    admit_CPU(request)
    require(not output.exists() and output.parent.is_dir(), 'Fresh external output required')
    require(not output.absolute().is_relative_to(HERE) and not output.absolute().is_relative_to(DESIGN)
        and not output.absolute().is_relative_to(Path(request['equation_repository'])), 'Output cannot modify frozen source')
    support = legacy()
    equation, heads = support.import_equation(request['equation_repository'])
    before = source_files(support, equation, request['equation_repository'])
    require(before == request['source_files'], 'Frozen source drift before run')
    aggregate = support.bound_json(request['baseline_aggregate'])
    baseline = {item['case_id']: item for item in aggregate['source_cases']}
    expected = [case.identity for case in equation.CASE_SPECS]
    complete_membership(request['cases'], expected)
    output.mkdir(mode=0o700)
    control_dir, hooked_dir = output/'unhooked', output/'hooked'
    control_dir.mkdir(mode=0o700)
    hooked_dir.mkdir(mode=0o700)
    support.save(output/'INPUT_BINDING.json', {'schema': 'model_v3_C4_layer_head_input_binding_v1',
        'request': request_ref, 'job_id': os.environ['SLURM_JOB_ID'], 'old_NPZ_reads': 0,
        'scientific_selection_or_adoption': False, 'is_FP32_acceptance_evidence': False})
    start = time.perf_counter()
    controls, records = {}, []
    failure = None
    def budget():
        require(time.perf_counter()-start <= WALL_CAP, 'Declared600s diagnostic wall exceeded')
        require(support.bytes_used(output) <= OUTPUT_CAP, 'Declared64MiB total child output cap exceeded')
    try:
        for spec in equation.CASE_SPECS:
            budget()
            old = support.bound_json(baseline[spec.identity])
            measured = equation.measure_case(spec, device='cpu', threads=1, terminal_output_directory=control_dir)
            support.unchanged_case_identity(measured, old)
            require(support.replay_measurements(measured, old), 'Unhooked original baseline JSON replay differs')
            path = control_dir/(spec.identity+'.json')
            support.save(path, measured)
            controls[spec.identity] = measured
            budget()
            print(json.dumps({'phase': 'unhooked', 'case': spec.identity, 'exact_baseline_replay': True}), flush=True)
        complete_membership(list(controls), expected)
        for spec in equation.CASE_SPECS:
            budget()
            old = support.bound_json(baseline[spec.identity])
            with capture_composition(equation, heads) as holder:
                measured = equation.measure_case(spec, device='cpu', threads=1, terminal_output_directory=hooked_dir)
            trace = holder['trace']
            trace.complete()
            assert_unchanged_weights(equation, trace.model, measured['weight_summary'], 'Hooks changed model parameters')
            support.unchanged_case_identity(measured, old)
            require(support.replay_measurements(measured, old), 'Hooked original baseline JSON replay differs')
            equality = ensure_terminal_equality(controls[spec.identity]['actual_terminal_output_artifact']['path'],
                measured['actual_terminal_output_artifact']['path'])
            transforms = equation.transforms()
            with equation.numerical_policy(threads=1), torch.inference_mode(), torch.autocast(device_type='cpu', enabled=False):
                layer_rows = layer_summaries(trace, transforms)
                geometry_rows = input_and_distance_summaries(trace, transforms)
                head_rows = replay_heads(trace, transforms, heads)
            assert_unchanged_weights(equation, trace.model, measured['weight_summary'], 'Head/shadow replay changed model parameters')
            detail = {'schema': 'model_v3_C4_layer_head_trace_v1', 'case_id': spec.identity,
                'weight_summary': measured['weight_summary'], 'fixture_geometry_sha256': measured['fixture_geometry_sha256'],
                'original_view_identity_sha256': measured['original_view_identity_sha256'],
                'layers': layer_rows, 'input_and_distance': geometry_rows, 'head_cross_replay': head_rows,
                'all_trace_hooks_removed': not trace.handles, 'original_factory_and_pool_restored': True,
                'is_FP32_acceptance_evidence': False}
            trace_ref = save_trace(hooked_dir/(spec.identity+'__TRACE.json.gz'), detail)
            path = hooked_dir/(spec.identity+'.json')
            support.save(path, {'schema': 'model_v3_C4_layer_head_case_v1', 'status': 'COMPLETE_DIAGNOSTIC_ONLY',
                'case_id': spec.identity, 'bitwise_terminal_control': equality, 'original_baseline_JSON_replay': True,
                'unhooked': support.binding(control_dir/(spec.identity+'.json')), 'trace': trace_ref,
                'hooked_measurement': measured, 'scientific_selection_or_adoption': False,
                'is_FP32_acceptance_evidence': False})
            records.append({'case_id': spec.identity, 'case_result': support.binding(path), 'completed': True})
            del trace, holder
            budget()
            print(json.dumps({'phase': 'hooked_attribution', 'case': spec.identity, 'bitwise_control': True}), flush=True)
    except Exception as error:
        failure = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc(),
            'last_requested_case': spec.identity if 'spec' in locals() else None}
        support.save(output/'FAILED.json', failure)
    after = source_files(support, equation, request['equation_repository'])
    closed = failure is None and len(controls) == len(records) == 48 and before == after
    if closed:
        complete_membership([record['case_id'] for record in records], expected)
    result = {'schema': 'model_v3_C4_layer_head_result_v1',
        'status': 'COMPLETE_DIAGNOSTIC_ONLY_NO_ADOPTION' if closed else 'INCOMPLETE_OR_REPLAY_FAILURE',
        'job_id': os.environ['SLURM_JOB_ID'], 'request': request_ref, 'case_results': records,
        'unhooked_complete_cases': len(controls), 'hooked_complete_cases': len(records),
        'original_FP32_case_pass_count_NOT_adoption': sum(value['passed'] for value in controls.values()),
        'completed_and_controlled_encoder_forwards': 4*(len(controls)+len(records)),
        'actual_full_encoder_forwards_if_closed': 384 if closed else None, 'source_before_after_identical': before == after,
        'wall_seconds': time.perf_counter()-start, 'failure': failure, 'old_NPZ_reads': 0,
        'all_data_synthetic': True, 'is_FP32_acceptance_evidence': False, 'scientific_selection_or_adoption': False}
    support.save(output/'DIAGNOSTIC_RESULT.json', result)
    require(support.bytes_used(output) <= OUTPUT_CAP, 'Declared64MiB child output cap exceeded at closure')
    if closed:
        completion = {'schema': 'model_v3_C4_layer_head_complete_v1',
            'result': support.binding(output/'DIAGNOSTIC_RESULT.json'), 'cases': 48, 'full_encoder_forwards': 384,
            'all_terminals_bitwise_controlled': True, 'source_before_after_identical': True,
            'status': 'DIAGNOSTIC_ONLY_NO_ADOPTION'}
        completion_bytes = (json.dumps(completion, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)+'\n').encode()
        require(support.bytes_used(output)+len(completion_bytes) <= OUTPUT_CAP, 'Completion would exceed64MiB; no marker written')
        support.save(output/'COMPLETE.json', completion)
        require(support.bytes_used(output) <= OUTPUT_CAP, 'Declared64MiB cap exceeded by complete receipt')
    return 0 if closed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('prepare-request')
    prepare.add_argument('--eq-repository', type=Path, required=True)
    prepare.add_argument('--aggregate', type=Path, default=B/'runs/model_v3_20261026/eq_diagnostic_v1/baseline_aggregate.json')
    prepare.add_argument('--expected-node', required=True)
    prepare.add_argument('--output', type=Path, required=True)
    execute = sub.add_parser('run')
    execute.add_argument('--request', type=Path, required=True)
    execute.add_argument('--request-sha256', required=True)
    execute.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    support = legacy()
    if args.action == 'prepare-request':
        support.save(args.output, make_request(args.eq_repository, args.aggregate, args.expected_node))
        print(json.dumps(support.binding(args.output)))
        return 0
    reference = support.binding(args.request)
    require(reference['sha256'] == args.request_sha256, 'Request rawSHA differs')
    request = support.bound_json(reference)
    require(request == make_request(request['equation_repository'], request['baseline_aggregate']['path'], request['expected_node']),
        'Exact source/design/input/execution request differs')
    return run(request, reference, args.output_root)


if __name__ == '__main__':
    raise SystemExit(main())
