"""Original complete48 and original absolute1e-5; all terminal arrays precede gate."""
import hashlib
import json
import os
from pathlib import Path
import traceback
import pytest
import torch
from core64_adapter import MODE,load_equation,centered_composition,durable_file,FIXTURE_SHA256

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
def test_original_complete48_core64_diagnostic_absolute_1e_minus5(spec,tmp_path):
    assert os.environ['MODEL_V3_NUMERIC_TEST_DEVICE'] == 'cuda:0'
    assert os.environ['MODEL_V3_NUMERIC_TEST_MODE'] == 'compensated_fp32_v1'
    assert os.environ['MODEL_V3_CENTERED_ATTENTION_MODE'] == MODE
    assert torch.cuda.is_available() and torch.cuda.device_count() == 1
    assert EQUATION.ABSOLUTE_TOLERANCE == 1e-5 and EQUATION.RELATIVE_TOLERANCE == 0
    try:
        original = parameter_authority(spec)
        with centered_composition(EQUATION,original) as construction:
            measured = EQUATION.measure_case(spec,device='cuda:0',threads=1,terminal_output_directory=tmp_path)
        assert len(construction) == 1
        artifact = measured['actual_terminal_output_artifact'];durable_file(artifact['path'])
        save(tmp_path/(spec.identity+'__numeric_case.json'),{
            'schema':'model_v3_core64_attention_diagnostic_complete48_case_v1','numeric_mode':'compensated_fp32_v1',
            'attention_aggregation_mode':MODE,'construction':construction[0],
            'original_fixture_source_sha256':FIXTURE_SHA256,'trained_or_selected_model':False,
            'mixed_precision_diagnostic_only':True,'formal_FP32_gate_satisfied':False,
            'model_freeze_candidate':False,'measured':measured})
    except Exception as error:
        partial = tmp_path/(spec.identity+'__terminals.npz')
        if partial.is_file():durable_file(partial)
        save(tmp_path/(spec.identity+'__exception.json'),{'case_id':spec.identity,
            'attention_aggregation_mode':MODE,'exception':type(error).__name__,'message':str(error),
            'traceback':traceback.format_exc(),'passed':False,'complete_measurement_not_fabricated':True})
        raise
    assert len(artifact['arrays']) == 52 and artifact['numeric_bytes'] <= 320*1024
    raw = Path(artifact['path']).read_bytes()
    assert len(raw) <= 512*1024 and hashlib.sha256(raw).hexdigest() == artifact['sha256']
    assert len(measured['measurements']) == 3 and all(len(row['fields']) == 13 for row in measured['measurements'])
    assert measured['encoder_forward_shapes'] == [[88 if spec.views == 'two' else 132,512]]*4
    configuration = measured['encoder_configuration']
    assert configuration['backbone_config']['attention_aggregation_mode'] == MODE
    assert configuration['backbone_config']['numeric_mode'] == configuration['head_config']['numeric_mode'] == 'compensated_fp32_v1'
    EQUATION.assert_case_passed(measured)  # Same original gate; all artifacts are already durable.
