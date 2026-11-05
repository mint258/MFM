"""Only fixed projection config and transparent actual-helper dtype/call coverage."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys

MODE = 'centered_fp32_v1'
PROJECTION_MODE = 'blocked_k64_compensated_fp32_v1'
ROOT = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_projection_fp32_candidate_v1')
FIXTURE_SOURCE = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_composed_equivariance_runtime_v3/current/phychem_mfm/phase1/v3_composed_equivariance.py')
FIXTURE_SHA256 = '0c49debe901ee5db79a71fcbc8541d426231c5090eb9740b84649e867d8df0e8'

def need(value, message):
    if not value:
        raise ValueError(message)

def load_equation():
    import phychem_mfm
    need(Path(phychem_mfm.__file__).resolve() == (ROOT/'current/phychem_mfm/__init__.py').resolve(),
         'Only the independent projection candidate namespace may execute')
    raw = FIXTURE_SOURCE.read_bytes()
    need(len(raw) <= 64<<10 and hashlib.sha256(raw).hexdigest() == FIXTURE_SHA256,
         'Original complete48 physical fixture differs')
    name = 'phychem_mfm.phase1._projection_original_complete48_v1'
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
def projection_composition(equation, original_parameter_sha256):
    import torch
    from torch.overrides import TorchFunctionMode
    from phychem_mfm.model import attention as dense_module
    from phychem_mfm.model import v3_architecture as pair_module
    from phychem_mfm.model import v3_attention_projection as implementation
    from phychem_mfm.model.v3_numeric_stability import numeric_mode, COMPENSATED
    old_encoder, old_bank, old_composition = equation.build_source_s_architecture_model, equation.V3HeadBank, equation.build_composition
    old_dense, old_pair = dense_module.attention_projection, pair_module.attention_projection
    need(old_dense is old_pair is implementation.attention_projection,
         'The actual published helper must serve both coupled attention classes')
    receipts, ports, modules = [], [], {}

    class ProjectionDtypes(TorchFunctionMode):
        """Only active during one original projection helper call; no data copies."""
        def __init__(self):
            super().__init__()
            self.floating_operands = self.floating_results = 0
            self.functions = {}
        def inspect(self, value, *, result):
            if isinstance(value, torch.Tensor):
                if value.dtype.is_floating_point or value.dtype.is_complex:
                    need(value.dtype == torch.float32 and value.device.type == 'cuda',
                         'Actual projection floating arithmetic must remain CUDA FP32')
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
        audit = ProjectionDtypes()
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

    def encoder(configuration, *args, **kwargs):
        value = deepcopy(configuration)
        need('numeric_stability' not in value
             and 'attention_aggregation_mode' not in value['backbone']
             and 'attention_projection_mode' not in value['backbone'],
             'Original fixture unexpectedly predeclares an arithmetic candidate')
        value['numeric_stability'] = {'mode':COMPENSATED}
        value['backbone']['attention_aggregation_mode'] = MODE
        value['backbone']['attention_projection_mode'] = PROJECTION_MODE
        model = old_encoder(value, *args, **kwargs)
        implementation.require_projection_backbone(model.backbone, expected_mode=PROJECTION_MODE)
        need(numeric_mode(model) == COMPENSATED
             and model.config_dict()['backbone_config']['attention_aggregation_mode'] == MODE
             and model.config_dict()['backbone_config']['attention_projection_mode'] == PROJECTION_MODE,
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
        receipt = {'case_id':spec.identity, 'attention_aggregation_mode':MODE,
            'attention_projection_mode':PROJECTION_MODE,
            'all_six_aggregation_modes':[layer.attn.attention_aggregation_mode for layer in model.encoder.backbone.layers],
            'all_six_projection_modes':[layer.attn.attention_projection_mode for layer in model.encoder.backbone.layers],
            'original_parameter_sha256':original_parameter_sha256,
            'actual_parameter_sha256':summary['all_named_parameter_sha256'],
            'parameter_count':summary['parameters'], 'numeric_mode':COMPENSATED,
            'projection_ports':ports, 'projection_spy_scope':'One actual projection helper at a time, never the whole model',
            'dtype_scope':'Observed PyTorch operands/results, not hardware accumulator proof',
            'new_parameters_or_initializer':False, 'FP64_core_or_encoder':False,
            'NativeRuntimeDense_or_bf16_covered':False}
        receipts.append(receipt)
        return model, registry

    equation.build_source_s_architecture_model, equation.V3HeadBank, equation.build_composition = encoder, bank, composition
    dense_module.attention_projection = pair_module.attention_projection = spy
    try:
        yield receipts
    finally:
        equation.build_source_s_architecture_model, equation.V3HeadBank, equation.build_composition = old_encoder, old_bank, old_composition
        dense_module.attention_projection, pair_module.attention_projection = old_dense, old_pair

def durable_file(path):
    with Path(path).open('rb') as stream:
        os.fsync(stream.fileno())
    descriptor = os.open(str(Path(path).parent), os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
