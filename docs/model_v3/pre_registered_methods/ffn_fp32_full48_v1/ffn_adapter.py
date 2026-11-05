"""Fixed geometry base plus one FFN affine mode; transparent actual-helper coverage."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys

MODE = 'centered_fp32_v1'
PROJECTION_MODE = 'blocked_k64_compensated_fp32_v1'
GEOMETRY_MODE = 'residual_expansion_fp32_v1'
FFN_MODE = 'blocked_k64_compensated_fp32_v1'
ROOT = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_ffn_fp32_candidate_v1')
FIXTURE_SOURCE = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_composed_equivariance_runtime_v3/current/phychem_mfm/phase1/v3_composed_equivariance.py')
FIXTURE_SHA256 = '0c49debe901ee5db79a71fcbc8541d426231c5090eb9740b84649e867d8df0e8'

def need(value, message):
    if not value:
        raise ValueError(message)

def load_equation():
    import phychem_mfm
    need(Path(phychem_mfm.__file__).resolve() == (ROOT/'current/phychem_mfm/__init__.py').resolve(),
         'Only the independent FFN candidate namespace may execute')
    raw = FIXTURE_SOURCE.read_bytes()
    need(len(raw) <= 64<<10 and hashlib.sha256(raw).hexdigest() == FIXTURE_SHA256,
         'Original complete48 physical fixture differs')
    name = 'phychem_mfm.phase1._ffn_original_complete48_v1'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, FIXTURE_SOURCE)
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    return sys.modules[name]

@contextmanager
def ffn_composition(equation, original_parameter_sha256):
    import torch
    from torch.overrides import TorchFunctionMode
    from phychem_mfm.model import attention as dense_module
    from phychem_mfm.model import v3_architecture as pair_module
    from phychem_mfm.model import v3_attention_projection as implementation
    from phychem_mfm.model import v3_geometry_fp32 as geometry
    from phychem_mfm.model import v3_ffn_projection as ffn_implementation
    from phychem_mfm.model.v3_numeric_stability import numeric_mode, COMPENSATED
    old_encoder, old_bank, old_composition = equation.build_source_s_architecture_model, equation.V3HeadBank, equation.build_composition
    old_dense, old_pair = dense_module.attention_projection, pair_module.attention_projection
    need(old_dense is old_pair is implementation.attention_projection,
         'The actual published helper must serve both coupled attention classes')
    old_dense_geometry, old_pair_geometry = dense_module.residual_pairwise_distance_fp32, pair_module.residual_pairwise_distance_fp32
    need(old_dense_geometry is old_pair_geometry is geometry.residual_pairwise_distance_fp32,
         'Both actual encoder distance callers must use the frozen raw-coordinate helper')
    old_ffn = dense_module.ffn_projection
    need(old_ffn is ffn_implementation.ffn_projection,
         'The one original DenseFFN imported alias must serve C1-0/a/b')
    receipts, ports, modules, geometry_ports, geometry_modules = [], [], {}, [], {}
    ffn_ports, ffn_modules = [], {}

    class ActualHelperDtypes(TorchFunctionMode):
        """Only one original projection or geometry helper call; no data copies."""
        def __init__(self):
            super().__init__()
            self.floating_operands = self.floating_results = 0
            self.functions = {}
        def inspect(self, value, *, result):
            if isinstance(value, torch.Tensor):
                if value.dtype.is_floating_point or value.dtype.is_complex:
                    need(value.dtype == torch.float32 and value.device.type == 'cuda',
                         'Actual controlled helper floating tensors must remain CUDA FP32')
                    if result: self.floating_results += 1
                    else: self.floating_operands += 1
            elif isinstance(value, (tuple, list)):
                for item in value: self.inspect(item, result=result)
            elif isinstance(value, dict):
                for item in value.values(): self.inspect(item, result=result)
        def __torch_function__(self, func, types, args=(), kwargs=None):
            kwargs = {} if kwargs is None else kwargs
            self.inspect(args, result=False); self.inspect(kwargs, result=False)
            result = func(*args, **kwargs)
            name = getattr(func, '__name__', str(func))
            self.functions[name] = self.functions.get(name, 0)+1
            self.inspect(result, result=True)
            return result

    def spy(module, linear, values):
        need(id(module) in modules, 'Projection outside the declared six-layer model')
        layer = modules[id(module)]
        kind = 'qkv' if linear is module.qkv else 'out' if linear is module.proj else None
        need(kind is not None and module.attention_projection_mode == PROJECTION_MODE
             and module.attention_aggregation_mode == MODE, 'Wrong actual projection/mode')
        audit = ActualHelperDtypes()
        with audit:
            result = old_dense(module, linear, values)
        rows = values.numel()//values.shape[-1]
        expected_leaves = 8*((rows+127)//128)
        need(audit.functions.get('linear', 0) == expected_leaves
             and audit.floating_operands > 0 and audit.floating_results > 0,
             'The fixed K64/row128 projection leaf coverage differs')
        ports.append({'layer':layer, 'projection':kind, 'input_shape':list(values.shape),
            'output_shape':list(result.shape), 'input_dtype':str(values.dtype),
            'weight_dtype':str(linear.weight.dtype),
            'bias_dtype':None if linear.bias is None else str(linear.bias.dtype),
            'output_dtype':str(result.dtype), 'dense_rows':rows,
            'actual_K64_linear_calls':audit.functions['linear'],
            'floating_operands_checked':audit.floating_operands,
            'floating_results_checked':audit.floating_results,
            'all_observed_projection_floating_ports_CUDA_FP32':True,
            'original_helper_called_once_and_original_result_returned':True})
        return result

    def ffn_spy(module, linear, values):
        need(id(module) in ffn_modules, 'FFN projection outside the declared six-layer model')
        layer = ffn_modules[id(module)]
        kind = 'in' if linear is module.net[0] else 'out' if linear is module.net[3] else None
        need(kind is not None and module.ffn_projection_mode == FFN_MODE,
             'Wrong actual FFN affine/mode')
        audit = ActualHelperDtypes()
        with audit:
            result = old_ffn(module, linear, values)
        rows = values.numel()//values.shape[-1]
        expected_leaves = (values.shape[-1]//64)*((rows+127)//128)
        need(audit.functions.get('linear', 0) == expected_leaves
             and audit.floating_operands > 0 and audit.floating_results > 0,
             'Actual fixed FFN K64/row128 leaf coverage differs')
        ffn_ports.append({'layer':layer, 'projection':kind, 'input_shape':list(values.shape),
            'output_shape':list(result.shape), 'input_dtype':str(values.dtype),
            'weight_dtype':str(linear.weight.dtype), 'bias_dtype':str(linear.bias.dtype),
            'output_dtype':str(result.dtype), 'dense_rows':rows,
            'actual_K64_linear_calls':audit.functions['linear'],
            'floating_operands_checked':audit.floating_operands,
            'floating_results_checked':audit.floating_results,
            'all_observed_FFN_floating_ports_CUDA_FP32':True,
            'original_helper_called_once_and_original_result_returned':True,
            'hardware_accumulator_proof':False})
        return result

    def geometry_call(caller, left, right, *, squared, original, expected_kind):
        need(id(caller) in geometry_modules, 'Undeclared encoder geometry caller')
        kind, layer = geometry_modules[id(caller)]
        need(kind == expected_kind and caller.geometry_mode == GEOMETRY_MODE,
             'Actual caller geometry mode/class binding differs')
        need(type(squared) is bool and squared == (kind == 'dense_layer')
             and left is right and left.ndim == 3 and left.shape[-1] == 3,
             'Original dense squared/shared norm raw self-pair geometry required')
        audit = ActualHelperDtypes()
        with audit:
            result = original(left, right, squared=squared)
        need(result.shape == (left.shape[0], left.shape[1], left.shape[1])
             and result.dtype == torch.float32 and audit.floating_operands > 0
             and audit.floating_results > 0, 'Actual geometry shape/FP32 coverage differs')
        geometry_ports.append({'caller':kind, 'layer':layer, 'squared':squared,
            'input_shape':list(left.shape), 'output_shape':list(result.shape),
            'input_dtype':str(left.dtype), 'output_dtype':str(result.dtype),
            'floating_operands_checked':audit.floating_operands,
            'floating_results_checked':audit.floating_results,
            'all_observed_geometry_floating_ports_CUDA_FP32':True,
            'original_helper_called_once_and_original_result_returned':True,
            'hardware_accumulator_proof':False})
        return result

    def dense_geometry(left, right, *, squared=False):
        return geometry_call(sys._getframe(1).f_locals.get('self'), left, right,
            squared=squared, original=old_dense_geometry, expected_kind='dense_layer')

    def shared_geometry(left, right, *, squared=False):
        return geometry_call(sys._getframe(1).f_locals.get('self'), left, right,
            squared=squared, original=old_pair_geometry, expected_kind='shared_pair_encoder')

    def encoder(configuration, *args, **kwargs):
        value = deepcopy(configuration)
        need('numeric_stability' not in value
             and 'attention_aggregation_mode' not in value['backbone']
             and 'attention_projection_mode' not in value['backbone']
             and 'geometry_mode' not in value['backbone']
             and 'ffn_projection_mode' not in value['backbone'],
             'Original fixture unexpectedly predeclares an arithmetic candidate')
        value['numeric_stability'] = {'mode':COMPENSATED}
        value['backbone']['attention_aggregation_mode'] = MODE
        value['backbone']['attention_projection_mode'] = PROJECTION_MODE
        value['backbone']['geometry_mode'] = GEOMETRY_MODE
        value['backbone']['ffn_projection_mode'] = FFN_MODE
        model = old_encoder(value, *args, **kwargs)
        implementation.require_projection_backbone(model.backbone, expected_mode=PROJECTION_MODE)
        geometry.require_geometry_binding(model.backbone, expected_mode=GEOMETRY_MODE)
        ffn_implementation.require_ffn_backbone(model.backbone, expected_mode=FFN_MODE)
        need(numeric_mode(model) == COMPENSATED
             and model.config_dict()['backbone_config']['attention_aggregation_mode'] == MODE
             and model.config_dict()['backbone_config']['attention_projection_mode'] == PROJECTION_MODE
             and model.config_dict()['backbone_config']['geometry_mode'] == GEOMETRY_MODE
             and model.config_dict()['backbone_config']['ffn_projection_mode'] == FFN_MODE,
             'Actual model configuration/mode differs')
        return model

    def bank(*args, **kwargs):
        need('numeric_mode' not in kwargs, 'Original head mode unexpectedly predeclared')
        kwargs['numeric_mode'] = COMPENSATED
        value = old_bank(*args, **kwargs)
        need(numeric_mode(value) == COMPENSATED, 'Original compensated heads/reductions must remain')
        return value

    def composition(spec):
        model, registry = old_composition(spec)
        summary = equation.weight_summary(model)
        need(summary['all_named_parameter_sha256'] == original_parameter_sha256,
             'Original1492 complete seeded parameters differ')
        need(all(p.dtype == torch.float32 and p.device.type == 'cpu' for p in model.parameters())
             and all(not b.dtype.is_floating_point or b.dtype == torch.float32 for b in model.buffers()),
             'Original CPU FP32 parameters/buffers required')
        need(numeric_mode(model.encoder) == numeric_mode(model.pd_heads) == COMPENSATED,
             'Head or global numeric mode changed')
        for index, layer in enumerate(model.encoder.backbone.layers):
            modules[id(layer.attn)] = index
            ffn_modules[id(layer.ffn)] = index
            geometry_modules[id(layer.attn)] = ('dense_layer', index)
        if hasattr(model.encoder.backbone, 'pair_encoder'):
            geometry_modules[id(model.encoder.backbone.pair_encoder)] = ('shared_pair_encoder', None)
        receipt = {'case_id':spec.identity, 'attention_aggregation_mode':MODE,
            'attention_projection_mode':PROJECTION_MODE, 'geometry_mode':GEOMETRY_MODE,
            'ffn_projection_mode':FFN_MODE,
            'all_six_FFN_modes':[layer.ffn.ffn_projection_mode for layer in model.encoder.backbone.layers],
            'ffn_ports':ffn_ports, 'ffn_spy_scope':'One actual FFN affine helper call only; original result object returned',
            'all_six_geometry_modes':[layer.attn.geometry_mode for layer in model.encoder.backbone.layers],
            'all_six_aggregation_modes':[layer.attn.attention_aggregation_mode for layer in model.encoder.backbone.layers],
            'all_six_projection_modes':[layer.attn.attention_projection_mode for layer in model.encoder.backbone.layers],
            'original_parameter_sha256':original_parameter_sha256,
            'actual_parameter_sha256':summary['all_named_parameter_sha256'],
            'parameter_count':summary['parameters'], 'numeric_mode':COMPENSATED,
            'geometry_ports':geometry_ports, 'geometry_spy_scope':'One original raw-coordinate helper per call; no encoder replay or changed return',
            'geometry_backward_scope':'Inline independent tiny controls only; full48 remains inference',
            'head_geometry_pooling_and_parameters_unchanged':True,
            'projection_ports':ports, 'projection_spy_scope':'One actual projection helper at a time, never the whole model',
            'dtype_scope':'Observed PyTorch operands/results, not hardware accumulator proof',
            'new_parameters_or_initializer':False, 'FP64_core_or_encoder':False,
            'NativeRuntimeDense_or_bf16_covered':False}
        receipts.append(receipt)
        return model, registry

    equation.build_source_s_architecture_model, equation.V3HeadBank, equation.build_composition = encoder, bank, composition
    dense_module.attention_projection = pair_module.attention_projection = spy
    dense_module.ffn_projection = ffn_spy
    dense_module.residual_pairwise_distance_fp32 = dense_geometry
    pair_module.residual_pairwise_distance_fp32 = shared_geometry
    try:
        yield receipts
    finally:
        equation.build_source_s_architecture_model, equation.V3HeadBank, equation.build_composition = old_encoder, old_bank, old_composition
        dense_module.attention_projection, pair_module.attention_projection = old_dense, old_pair
        dense_module.ffn_projection = old_ffn
        dense_module.residual_pairwise_distance_fp32, pair_module.residual_pairwise_distance_fp32 = old_dense_geometry, old_pair_geometry

def durable_file(path):
    with Path(path).open('rb') as stream:
        os.fsync(stream.fileno())
    descriptor = os.open(str(Path(path).parent), os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
