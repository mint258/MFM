"""Only configuration injection around the unchanged original complete48 fixture."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys

MODE = 'centered_fp32_v1'
ROOT = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_attention_centering_v1')
FIXTURE_SOURCE = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_composed_equivariance_runtime_v3/current/phychem_mfm/phase1/v3_composed_equivariance.py')
FIXTURE_SHA256 = '0c49debe901ee5db79a71fcbc8541d426231c5090eb9740b84649e867d8df0e8'

def need(value,message):
    if not value:
        raise ValueError(message)

def load_equation():
    import phychem_mfm
    need(Path(phychem_mfm.__file__).resolve() == (ROOT/'current/phychem_mfm/__init__.py').resolve(),
         'Only the independent candidate worktree may execute; never reporting/model-v3')
    raw = FIXTURE_SOURCE.read_bytes()
    need(len(raw) <= 64<<10 and hashlib.sha256(raw).hexdigest() == FIXTURE_SHA256,
         'Original full48 cohort/physics source differs')
    name = 'phychem_mfm.phase1._centered_attention_original_complete48_v1'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name,FIXTURE_SOURCE)
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    return sys.modules[name]

@contextmanager
def centered_composition(equation,original_parameter_sha256):
    from phychem_mfm.model.v3_numeric_stability import numeric_mode,COMPENSATED
    old_encoder,old_bank,old_composition = equation.build_source_s_architecture_model,equation.V3HeadBank,equation.build_composition
    receipts = []
    def encoder(configuration,*args,**kwargs):
        value = deepcopy(configuration)
        need('numeric_stability' not in value and 'attention_aggregation_mode' not in value['backbone'],
             'Original fixture unexpectedly already declares a numeric/aggregation option')
        value['numeric_stability'] = {'mode':COMPENSATED}
        value['backbone']['attention_aggregation_mode'] = MODE
        model = old_encoder(value,*args,**kwargs)
        need(numeric_mode(model) == COMPENSATED,'Existing COMPENSATED encoder must remain enabled')
        layers = model.backbone.layers
        need(len(layers) == 6 and all(layer.attn.attention_aggregation_mode == MODE for layer in layers),
             'All six actual coupled attention modules must use the candidate; no legacy fallback')
        need(all(type(layer.attn).__name__ in ('DenseGeoSelfAttention','SharedPairAttention') for layer in layers),
             'Only the two declared coupled classes may execute')
        need(model.config_dict()['backbone_config']['attention_aggregation_mode'] == MODE,
             'Actual model config must bind aggregation mode')
        return model
    def bank(*args,**kwargs):
        need('numeric_mode' not in kwargs,'Original head mode unexpectedly predeclared')
        kwargs['numeric_mode'] = COMPENSATED
        value = old_bank(*args,**kwargs)
        need(numeric_mode(value) == COMPENSATED,'Head/reducer COMPENSATED mode must remain unchanged')
        return value
    def composition(spec):
        model,registry = old_composition(spec)
        summary = equation.weight_summary(model)
        need(summary['all_named_parameter_sha256'] == original_parameter_sha256,
             'Original1492 seed/complete parameter identity differs')
        import torch
        need(all(p.dtype == torch.float32 and p.device.type == 'cpu' for p in model.parameters()),
             'Original complete CPU FP32 initialization required')
        need(numeric_mode(model.encoder) == numeric_mode(model.pd_heads) == COMPENSATED,
             'Global numeric/head modes changed')
        receipt = {'case_id':spec.identity,'attention_aggregation_mode':MODE,
            'all_six_layer_modes':[layer.attn.attention_aggregation_mode for layer in model.encoder.backbone.layers],
            'original_parameter_sha256':original_parameter_sha256,'actual_parameter_sha256':summary['all_named_parameter_sha256'],
            'parameter_count':summary['parameters'],'ordinary_FP32':True,'new_parameters_or_initializer':False,
            'numeric_mode':COMPENSATED,'NativeRuntimeDense_or_bf16_covered':False}
        receipts.append(receipt)
        return model,registry
    equation.build_source_s_architecture_model,equation.V3HeadBank,equation.build_composition = encoder,bank,composition
    try:
        yield receipts
    finally:
        equation.build_source_s_architecture_model,equation.V3HeadBank,equation.build_composition = old_encoder,old_bank,old_composition

def durable_file(path):
    with Path(path).open('rb') as stream:
        os.fsync(stream.fileno())
    descriptor = os.open(str(Path(path).parent),os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
