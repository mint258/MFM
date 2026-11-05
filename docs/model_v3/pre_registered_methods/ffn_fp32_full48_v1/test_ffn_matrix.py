"""Original complete48 and original absolute1e-5; all terminal arrays precede gate."""
import hashlib
import json
import os
from pathlib import Path
import traceback
import pytest
import torch
from ffn_adapter import MODE,PROJECTION_MODE,GEOMETRY_MODE,FFN_MODE,load_equation,ffn_composition,durable_file,FIXTURE_SHA256

EQUATION = load_equation()

def save(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,sort_keys=True,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    durable_file(path)

def parameter_authority(spec):
    path = Path(os.environ['MODEL_V3_CENTERED_CAPTURE_MANIFEST'])
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == os.environ['MODEL_V3_CENTERED_CAPTURE_MANIFEST_SHA']
    capture = json.loads(raw)
    assert capture['status'] == 'CAPTURE_COMPLETE' and capture['job_id'] == '4521492'
    rows = [row for row in capture['cases'] if row['case_id'] == spec.identity]
    assert len(rows) == 1
    ref = rows[0]['capture_case'];raw = Path(ref['path']).read_bytes()
    assert len(raw) == ref['bytes'] and hashlib.sha256(raw).hexdigest() == ref['sha256']
    case = json.loads(raw)
    return case['original_measurement']['weight_summary']['all_named_parameter_sha256']

@pytest.mark.parametrize('spec',EQUATION.CASE_SPECS,ids=lambda case:case.identity)
def test_original_complete48_geometry_FP32_absolute_1e_minus5(spec,tmp_path):
    assert os.environ['MODEL_V3_NUMERIC_TEST_DEVICE'] == 'cuda:0'
    assert os.environ['MODEL_V3_NUMERIC_TEST_MODE'] == 'compensated_fp32_v1'
    assert os.environ['MODEL_V3_CENTERED_ATTENTION_MODE'] == MODE
    assert os.environ['MODEL_V3_PROJECTION_MODE'] == PROJECTION_MODE
    assert os.environ['MODEL_V3_GEOMETRY_MODE'] == GEOMETRY_MODE
    assert os.environ['MODEL_V3_FFN_PROJECTION_MODE'] == FFN_MODE
    assert torch.cuda.is_available() and torch.cuda.device_count() == 1
    assert EQUATION.ABSOLUTE_TOLERANCE == 1e-5 and EQUATION.RELATIVE_TOLERANCE == 0
    try:
        original = parameter_authority(spec)
        with ffn_composition(EQUATION,original) as construction:
            measured = EQUATION.measure_case(spec,device='cuda:0',threads=1,terminal_output_directory=tmp_path)
        assert len(construction) == 1
        artifact = measured['actual_terminal_output_artifact'];durable_file(artifact['path'])
        save(tmp_path/(spec.identity+'__numeric_case.json'),{
            'schema':'model_v3_ffn_FP32_complete48_case_v1','numeric_mode':'compensated_fp32_v1',
            'attention_aggregation_mode':MODE,'attention_projection_mode':PROJECTION_MODE,'geometry_mode':GEOMETRY_MODE,'ffn_projection_mode':FFN_MODE,'construction':construction[0],
            'original_fixture_source_sha256':FIXTURE_SHA256,'trained_or_selected_model':False,
            'all_FP32_fixed_FFN_projection_candidate':True,'scientific_adoption':False,'measured':measured})
    except Exception as error:
        partial = tmp_path/(spec.identity+'__terminals.npz')
        if partial.is_file():durable_file(partial)
        save(tmp_path/(spec.identity+'__exception.json'),{'case_id':spec.identity,
            'attention_aggregation_mode':MODE,'exception':type(error).__name__,'message':str(error),
            'traceback':traceback.format_exc(),'passed':False,'complete_measurement_not_fabricated':True})
        raise
    ports = construction[0]['projection_ports']
    expected_ports = [(layer,kind) for _ in range(4) for layer in range(6) for kind in ('qkv','out')]
    assert [(row['layer'],row['projection']) for row in ports] == expected_ports
    assert all(row['all_observed_projection_floating_ports_CUDA_FP32'] and
               row['original_helper_called_once_and_original_result_returned'] for row in ports)
    geometry_ports = construction[0]['geometry_ports']
    expected_geometry = [('dense_layer',layer,True) for _ in range(4) for layer in range(6)] if spec.distance_bias == 'C1-0' else [('shared_pair_encoder',None,False)]*4
    assert [(row['caller'],row['layer'],row['squared']) for row in geometry_ports] == expected_geometry
    assert all(row['all_observed_geometry_floating_ports_CUDA_FP32'] and
               row['original_helper_called_once_and_original_result_returned'] for row in geometry_ports)
    assert construction[0]['all_six_geometry_modes'] == [GEOMETRY_MODE]*6
    ffn_ports = construction[0]['ffn_ports']
    assert [(row['layer'],row['projection']) for row in ffn_ports] == [
        (layer,kind) for _ in range(4) for layer in range(6) for kind in ('in','out')]
    assert all(row['all_observed_FFN_floating_ports_CUDA_FP32'] and
               row['original_helper_called_once_and_original_result_returned'] for row in ffn_ports)
    assert construction[0]['all_six_FFN_modes'] == [FFN_MODE]*6
    assert sum(row['actual_K64_linear_calls'] for row in ffn_ports) == (1152 if spec.views == 'two' else 1728)
    assert len(artifact['arrays']) == 52 and artifact['numeric_bytes'] <= 320*1024
    raw = Path(artifact['path']).read_bytes()
    assert len(raw) <= 512*1024 and hashlib.sha256(raw).hexdigest() == artifact['sha256']
    assert len(measured['measurements']) == 3 and all(len(row['fields']) == 13 for row in measured['measurements'])
    assert measured['encoder_forward_shapes'] == [[88 if spec.views == 'two' else 132,512]]*4
    configuration = measured['encoder_configuration']
    assert configuration['backbone_config']['attention_aggregation_mode'] == MODE
    assert configuration['backbone_config']['attention_projection_mode'] == PROJECTION_MODE
    assert configuration['backbone_config']['geometry_mode'] == GEOMETRY_MODE
    assert configuration['backbone_config']['ffn_projection_mode'] == FFN_MODE
    assert configuration['backbone_config']['numeric_mode'] == configuration['head_config']['numeric_mode'] == 'compensated_fp32_v1'
    EQUATION.assert_case_passed(measured)  # Same original gate; all artifacts are already durable.
