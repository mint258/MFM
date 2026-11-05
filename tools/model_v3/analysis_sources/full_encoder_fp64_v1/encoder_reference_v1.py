"""Analysis-only FP64 forward adapters preserving the canonical six-layer H0.

No production module is edited. Only a strict independent encoder copy receives
these forwards and explicit legacy numeric metadata. There is no new initializer.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import math
from types import MethodType
import torch
from torch_geometric.utils import to_dense_batch
from phychem_mfm.model.common import ensure_batch_attr


def require(ok, message):
    if not ok:
        raise ValueError(message)


def tensor_header(value):
    value = value.detach().cpu().contiguous()
    return {'dtype': str(value.dtype), 'shape': list(value.shape),
            'bytes': value.numel()*value.element_size(),
            'sha256': hashlib.sha256(value.numpy().tobytes()).hexdigest()}


def _same_state(left, right):
    require(set(left) == set(right), 'Strict complete state key membership differs')
    for key, original in left.items():
        other = right[key]
        if isinstance(original, torch.Tensor):
            require(isinstance(other, torch.Tensor) and tensor_header(original) == tensor_header(other),
                    'Strict copied tensor state differs: '+key)
        else:
            require(type(original) is type(other) and original == other, 'Copied extra-state differs: '+key)


def gaussian_reference_forward(self, pos, elements, mask):
    require(pos.ndim == 3 and pos.size(-1) == 3 and pos.dtype == self.centers.dtype
        and pos.dtype in (torch.float32, torch.float64) and elements.dtype == torch.long
        and mask.dtype == torch.bool and elements.shape == mask.shape == pos.shape[:2],
        'Reference geometry dtype/shape differs')
    require(all(parameter.dtype == pos.dtype for parameter in self.parameters()),
            'Mixed-precision Gaussian reference parameters')
    # The same legacy real-valued formula, without production's forced .float().
    distances = torch.cdist(pos, pos, compute_mode='donot_use_mm_for_euclid_dist')
    transformed = distances.unsqueeze(-1)
    if self.pair_scale is not None:
        pair_type = elements[:, :, None]*self.n_atom_types + elements[:, None, :]
        transformed = self.pair_scale(pair_type)*transformed + self.pair_shift(pair_type)
    widths = torch.nn.functional.softplus(self.raw_widths)+1e-5
    standardized = (transformed-self.centers)/widths
    rbf = torch.exp(-0.5*standardized.square())/(math.sqrt(2*math.pi)*widths)
    features = self.project(rbf)
    pair_valid = mask[:, :, None] & mask[:, None, :]
    envelope = pair_valid.to(features.dtype)
    if self.options.cutoff is not None:
        radius = float(self.options.cutoff)
        cutoff = torch.where(distances < radius,
            0.5*(1.+torch.cos(math.pi*distances/radius)), torch.zeros_like(distances))
        envelope = envelope*cutoff.to(features.dtype)
    return features*envelope.unsqueeze(-1), distances


def backbone_reference_forward(self, data):
    require(type(self).__name__ in ('RealCoordTransformerBackbone', 'SharedPairBackbone'),
            'Only actual declared backbone classes supported')
    require(data.pos.dtype == self.atom_emb.weight.dtype and data.pos.dtype in (torch.float32, torch.float64),
            'No implicit position cast allowed in reference')
    require(not self.training and not self.activation_checkpointing,
            'Actual eval/no-checkpoint reference required')
    batch = ensure_batch_attr(data)
    raw = data.x[:, 0] if data.x.ndim == 2 else data.x
    elements = raw.long().clamp(min=0, max=self.n_atom_types-1)
    embedded, mask = to_dense_batch(self.atom_emb(elements), batch, fill_value=0.)
    pos, _ = to_dense_batch(data.pos, batch, fill_value=0.)
    if type(self).__name__ == 'SharedPairBackbone':
        dense_elements, _ = to_dense_batch(elements, batch, fill_value=0)
        pairs, distances = self.pair_encoder(pos, dense_elements, mask)
        require(pairs.dtype == distances.dtype == embedded.dtype, 'Gaussian reference downcast')
        for layer in self.layers:
            embedded = layer(embedded, pairs, distances, mask)
    else:
        for layer in self.layers:
            embedded = layer(embedded, pos, mask)
    return (self.out_norm(embedded)*mask.unsqueeze(-1).to(embedded.dtype))[mask]


def install_analysis_forwards(backbone):
    require(type(backbone).__name__ in ('RealCoordTransformerBackbone', 'SharedPairBackbone'),
            'Unsupported analysis backbone')
    require(all(type(layer).__name__ in ('RealCoordTransformerLayer', 'SharedPairTransformerLayer')
                for layer in backbone.layers), 'Unsupported optimized/replaced layer')
    expected_attention = 'SharedPairAttention' if type(backbone).__name__ == 'SharedPairBackbone' else 'DenseGeoSelfAttention'
    require(all(type(layer.attn).__name__ == expected_attention for layer in backbone.layers),
            'Unsupported optimized attention reference path')
    for layer in backbone.layers:
        require(not layer.attn.use_radius_mask, 'Actual fixed matrix has global attention')
    if type(backbone).__name__ == 'SharedPairBackbone':
        require(backbone.options.cutoff is None, 'Actual fixed matrix has no Gaussian cutoff')
        require(type(backbone.pair_encoder).__name__ == 'SharedGaussianPairEncoder', 'Unknown pair encoder')
        require('forward' not in backbone.pair_encoder.__dict__, 'Unexpected existing Gaussian forward override')
        backbone.pair_encoder.forward = MethodType(gaussian_reference_forward, backbone.pair_encoder)
    else:
        require(all(type(layer.attn.dist_mlp).__name__ == 'TiledDistanceMLP' for layer in backbone.layers),
                'Actual C1-0 production tiled control required')
    require('forward' not in backbone.__dict__, 'Unexpected existing backbone forward override')
    backbone.forward = MethodType(backbone_reference_forward, backbone)


def strict_fp64_encoder_copy(encoder):
    """Strict state copy first; explicit analysis-mode/dtype mapping only afterward."""
    original = encoder.state_dict()
    clone = deepcopy(encoder)
    result = clone.load_state_dict(original, strict=True)
    require(not result.missing_keys and not result.unexpected_keys, 'Strict encoder state load failed')
    _same_state(original, clone.state_dict())
    for module in clone.modules():
        # apply_numeric_mode(..., legacy) is a no-op in frozen source.
        if hasattr(module, 'numeric_mode'):
            require(module.numeric_mode == 'compensated_fp32_v1', 'Unexpected original numeric mode')
            module.numeric_mode = 'legacy'
    clone.double().eval()
    promoted = clone.state_dict()
    mapping = {}
    for key, value in original.items():
        other = promoted[key]
        if not isinstance(value, torch.Tensor):
            # C1 get_extra_state legitimately exposes the declared shadow mode;
            # the original extra-state was checked exactly BEFORE this mapping.
            mapping[key] = {'original': deepcopy(value), 'analysis_after_mapping': deepcopy(other)}
            continue
        if value.is_floating_point():
            require(value.dtype == torch.float32 and other.dtype == torch.float64
                    and tensor_header(value) == tensor_header(other.to(torch.float32)),
                    'FP32 to FP64 state promotion was not lossless: '+key)
        else:
            require(tensor_header(value) == tensor_header(other), 'Nonfloat state changed: '+key)
        mapping[key] = {'original': tensor_header(value), 'analysis': tensor_header(other)}
    require(all(not hasattr(module, 'numeric_mode') or module.numeric_mode == 'legacy'
                for module in clone.modules()), 'Compensated F32 guard remains active in reference')
    install_analysis_forwards(clone.backbone)
    return clone, mapping


def close_analysis_forwards(backbone):
    """Remove analysis-only bound-method overrides before releasing the copy."""
    if 'forward' in backbone.__dict__:
        del backbone.forward
    if hasattr(backbone, 'pair_encoder') and 'forward' in backbone.pair_encoder.__dict__:
        del backbone.pair_encoder.forward


def geometry_policy(encoder):
    backbone = encoder.backbone
    attention = [{'layer': index, 'class': type(layer.attn).__name__,
                  'use_radius_mask': layer.attn.use_radius_mask, 'declared_radius': layer.attn.radius}
                 for index, layer in enumerate(backbone.layers)]
    pair = getattr(backbone, 'pair_encoder', None)
    cutoff = pair.options.cutoff if pair is not None else None
    require(all(row['use_radius_mask'] is False for row in attention) and cutoff is None,
            'Actual enabled geometry policy differs from global fixed matrix')
    return {'attention': attention, 'effective_attention_radius': None,
            'Gaussian_encoder_present': pair is not None, 'active_Gaussian_cutoff': cutoff,
            'Gaussian_center_range_is_cutoff': False, 'S_geometry_and_pair_head_FP64_covered': False}

class StageReferences:
    """Retain references only; read/copy after the complete original call returns."""
    def __init__(self, backbone):
        self.pending = {}
        self.pending_masks = {}
        self.input = None
        self.handles = [backbone.register_forward_pre_hook(self._before)]
        stages = [('embedding', backbone.atom_emb)]
        stages += [('layer%d' % index, layer) for index, layer in enumerate(backbone.layers)]
        stages += [('out_norm', backbone.out_norm), ('packed_H0', backbone)]
        self.names = [name for name, _ in stages]
        for name, module in stages:
            def after(module, inputs, output, name=name):
                require(name not in self.pending and isinstance(output, torch.Tensor), 'Stage capture coverage differs')
                self.pending[name] = output
                if name.startswith('layer'):
                    require(isinstance(inputs[-1], torch.Tensor), 'Actual layer input mask missing')
                    self.pending_masks[name] = inputs[-1]
            self.handles.append(module.register_forward_hook(after))

    def _before(self, module, inputs):
        require(self.input is None and len(inputs) == 1, 'Overlapping encoder capture')
        self.input = inputs[0]

    def take(self, clean_rows):
        require(set(self.pending) == set(self.names) and self.input is not None, 'Incomplete stage coverage')
        data = self.input.clone().cpu()
        _, mask = to_dense_batch(data.batch, data.batch, fill_value=0)
        count = len(data.pos)
        rows = clean_rows.detach().cpu()
        require(set(self.pending_masks) == {'layer%d' % i for i in range(6)}, 'Six actual layer masks required')
        actual_masks = {name: value.detach().cpu() for name, value in self.pending_masks.items()}
        require(all(value.dtype == torch.bool and tensor_header(value) == tensor_header(mask)
                    for value in actual_masks.values()), 'Actual layer masks differ from physical batch layout')
        stages = {}
        for name in self.names:
            value = self.pending[name].detach().cpu().contiguous()
            if value.ndim == 3:
                require(tuple(value.shape[:2]) == tuple(mask.shape), 'Dense stage shape/mask differs')
                value = value[mask]
            require(value.ndim == 2 and value.shape == (count, 512), 'Actual packed 512 stage shape differs')
            require(value.dtype in (torch.float32, torch.float64) and value.isfinite().all(), 'Nonfinite or hidden mixed stage dtype')
            stages[name] = value.clone()
        self.pending.clear(); self.pending_masks.clear(); self.input = None
        require(torch.equal(stages['out_norm'], stages['packed_H0']), 'Canonical final H0 location differs')
        return {'input': data, 'clean_rows': rows, 'stages': stages,
                'actual_layer_mask': tensor_header(actual_masks['layer0'])}

    def close(self):
        for handle in self.handles:
            handle.remove()
        self.handles.clear()
        self.pending.clear(); self.pending_masks.clear(); self.input = None

def inline_reference_selfcheck(old_head):
    """Tiny GPU formula/device controls, not additional six-layer scientific cases."""
    from torch import nn
    from torch_geometric.data import Data
    from phychem_mfm.model.backbone import RealCoordTransformerBackbone
    from phychem_mfm.model.v3_architecture import ArchitectureOptions, SharedPairBackbone, SOURCE_S_MEMORY_SHA256
    from phychem_mfm.phase1.v3_contract import FieldSpec, LabelRegistry
    from phychem_mfm.model.v3_heads import V3HeadBank
    # Reuse the original source-bound tiled class, no substitute control builder.
    memory = SOURCE_S_MEMORY_SHA256
    import importlib.util
    from pathlib import Path
    import sys
    source = Path(__file__).absolute().parents[3]/'MFM_model_v3_numeric_stability_v1/workflows/sprime_s/scripts/s_model_memory_v1.py'
    # __file__ here is in runs/date/package: parents[3] is the project root.
    require(source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == memory,
            'Tiny parity requires the exact original tiled module')
    spec = importlib.util.spec_from_file_location('precision_tiny_original_tiled', source)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    data = Data(x=torch.tensor([0, 1, 2]), batch=torch.tensor([0, 0, 1]),
                pos=torch.tensor([[0., 0., 0.], [1., .25, .5], [.2, -.1, .7]], dtype=torch.float32)).to('cuda:0')
    parity = []
    for kind in ('C1-0', 'C1-a', 'C1-b'):
        with torch.random.fork_rng(devices=[]):
            torch.random.default_generator.manual_seed(64123)
            original = RealCoordTransformerBackbone(4, 4, layers=1, heads=1, ff_mult=2, dropout=0.)
            original.layers[0].attn.dist_mlp = module.TiledDistanceMLP(original.layers[0].attn.dist_mlp)
            if kind != 'C1-0':
                original = SharedPairBackbone(original, ArchitectureOptions(distance_bias=kind, pair_dim=4, pair_hidden_dim=4))
        original.eval().to('cuda:0')
        copied = deepcopy(original); _same_state(original.state_dict(), copied.state_dict())
        install_analysis_forwards(copied)
        a, b = original(data), copied(data)
        require(tensor_header(a) == tensor_header(b), 'Tiny legacy FP32 forward parity differs: '+kind)
        class TinyEncoder(nn.Module):
            def __init__(self, backbone):
                super().__init__(); self.backbone = backbone
            def encode_atoms(self, value):
                return self.backbone(value)
        reference, _ = strict_fp64_encoder_copy(TinyEncoder(original))
        promoted = data.clone(); promoted.pos = promoted.pos.double()
        r1, r2 = reference.encode_atoms(promoted), reference.encode_atoms(promoted)
        require(r1.dtype == torch.float64 and r1.isfinite().all()
                and tensor_header(r1) == tensor_header(r2), 'Tiny actual-input reference dtype/replay failed')
        parity.append({'kind': kind, 'tiny_legacy_FP32_bitwise_parity': True,
                       'tiny_FP64_dtype_and_replay': True, 'shape': list(r1.shape)})
        close_analysis_forwards(copied)
        close_analysis_forwards(reference.backbone)
    head_rows = []
    for form, pooling in (('H1', 'sum'), ('H1', 'learned'), ('H2', 'sum'), ('H3', 'sum')):
        registry = LabelRegistry((FieldSpec('p_extensive', 'P', 'oracle', 'graph', pooling=pooling),
            FieldSpec('p_dipole', 'P', 'oracle', 'graph', representation='vector'),
            FieldSpec('p_dipole_magnitude', 'P', 'oracle', 'graph', representation='magnitude')),
            'fixed_h0_precision_device_oracle', 'f'*64)
        with torch.random.fork_rng(devices=[]):
            torch.random.default_generator.manual_seed(641)
            bank = V3HeadBank(registry, dim=4, hidden_dim=4, forms=form, numeric_mode='compensated_fp32_v1').eval()
        with torch.no_grad():
            for mixer in bank.pooling_mixers.values(): mixer.logits.copy_(torch.tensor([-.7, .4]))
        features = torch.tensor([[1., .5, -.25, .75], [.25, -.5, .75, 1.], [1., 1., .5, -.5], [-.5, .25, 1., .5]])
        positions = torch.tensor([[0., 0., 0.], [1., .5, 0.], [0., .5, .5], [.5, 0., 1.]])
        batch = torch.tensor([0, 0, 1, 1])
        cpu = old_head.functional64(bank, features, positions, batch)
        bank.to('cuda:0')
        gpu = old_head.functional64(bank, features.to('cuda:0'), positions.to('cuda:0'), batch.to('cuda:0'))
        error = max(float((cpu[key]-gpu[key].cpu()).abs().max()) for key in cpu)
        require(error <= 1e-10 and float(gpu['p_dipole'].abs().max()) > 0,
                'Unchanged functional64 CPU/CUDA small-tensor parity failed')
        head_rows.append({'form': form, 'pooling': pooling, 'maxabs_CPU_GPU_FP64': error})
    return {'scope': 'INLINE_TINY_DEVICE_FORMULA_ORACLES_ONLY_NOT_FULL512_SCIENTIFIC_CASES',
            'backbone_parity': parity, 'unchanged_functional64_device_parity': head_rows,
            'completed_tiny_dim4_one_layer_encoder_forwards': len(parity)*4,
            'completed_functional64_small_CPU_bank_calls': len(head_rows),
            'completed_functional64_small_CUDA_bank_calls': len(head_rows),
            'scientific_seed_or_initializer_changed': False}
