"""Thin I/O/source adapter. The old capture codecs and CPU math remain frozen."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).absolute().parent
B = Path('/share/home/zixiao/descriptor_analysis')
N = B/'runs/model_v3_20261026'
OLD = N/'numeric_fixed_h0_shadow_v3_source'
CENTERED = N/'attention_centered_e2e_v1_source'

def need(value, message):
    if not value:
        raise ValueError(message)

def load_file(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def metadata_ref(path):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 2*1024**2,
         'Ordinary metadata/source <=2MiB required')
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def read_metadata(leaf):
    need(metadata_ref(leaf['path']) == leaf, 'Metadata raw reference changed')
    return json.loads(Path(leaf['path']).read_bytes())

# No module alias replacement, sys.modules clearing, or alternate model package.
_old_common = sys.modules.get('shadow_common')
if _old_common is None:
    _old_common = load_file(OLD/'shadow_common.py', 'shadow_common')
need(Path(_old_common.__file__).resolve() == (OLD/'shadow_common.py').resolve(),
     'An unrelated shadow_common is already imported')
FIELDS, INPUT_CAP, STATE_BYTES = _old_common.FIELDS, _old_common.INPUT_CAP, _old_common.STATE_BYTES
InputBudget, bound, ref = _old_common.InputBudget, _old_common.bound, _old_common.ref
require, save_plain = _old_common.require, _old_common.save_plain
state_arrays, tensor_state_identity = _old_common.state_arrays, _old_common.tensor_state_identity
load_npz, metadata_selfcheck = _old_common.load_npz, _old_common.metadata_selfcheck

def load_shadow():
    name = '_centered_H0_frozen_1503_functional_heads'
    if name not in sys.modules:
        load_file(OLD/'shadow_terminals_v1.py', name)
    module = sys.modules[name]
    need(Path(module.__file__).resolve() == (OLD/'shadow_terminals_v1.py').resolve(),
         'CPU functional-head implementation differs')
    return module

def verify_publication(request):
    publication = load_file(CENTERED/'centered_publication.py', '_centered_H0_actual_candidate_publication')
    rows = publication.verify_publication(request)
    need(request['local_commit'] == 'cf8ce66d97cd518ebf279b40ee20294919bb95e1'
         and request['public_commit'] == 'f8417157dc23326d1beca8e19e4725755d9f13c6'
         and request['exact_shared_tree'] == '2389ab046ee23f2ba92fcb61179d853dfdee8357',
         'Exact previously tested centered candidate identity required')
    return rows

def source_snapshot(request, pins_sha):
    pins = bound({**ref(HERE/'source_pins_v1.json'), 'sha256': pins_sha})
    need(pins['schema'] == 'model_v3_centered_fixed_H0_capture_GPU_launch_source_pins_v1',
         'Dedicated centered capture source pins required')
    need(request['expected_case_count'] == 48 and len(request['expected_case_ids']) == 48
         and len(set(request['expected_case_ids'])) == 48
         and request['attention_aggregation_mode'] == 'centered_fp32_v1'
         and request['mode'] == 'compensated_fp32_v1'
         and request['absolute_tolerance'] == 1e-5 and request['relative_tolerance'] == 0,
         'Original complete48/FP32/threshold scope differs')
    values = request['source_refs'] + pins['files'] + pins['protected_dependencies']
    sources = {leaf['path']: leaf for leaf in values}
    need(all(sources[leaf['path']] == leaf for leaf in values), 'Conflicting duplicate source references')
    sources[str(HERE/'source_pins_v1.json')] = ref(HERE/'source_pins_v1.json')
    for leaf in sources.values():
        need(ref(leaf['path']) == leaf, 'Capture/functional-head source changed: '+leaf['path'])
    verify_publication(request)
    return sources

def external_terminal_control(request, case_id, measured):
    """Executed only after a new full forward. Never interprets 1776 hidden H0."""
    import numpy as np
    saved = read_metadata(request['external1776_case_refs'][case_id])['measured']
    terminal = measured['actual_terminal_output_artifact']
    need(saved['case_id'] == measured['case_id'] == case_id
         and saved['case'] == measured['case']
         and saved['encoder_configuration'] == measured['encoder_configuration']
         and saved['weight_summary']['all_named_parameter_sha256'] ==
             measured['weight_summary']['all_named_parameter_sha256'] == request['original1492_parameter_sha256'][case_id],
         'Original1776 case/config/parameter identity differs')
    for key in ('registry_sha256', 'fixture_geometry_sha256', 'original_physical_geometry_sha256',
                'original_view_identity_sha256', 'encoder_forward_shapes', 'complete_terminal_count'):
        need(saved[key] == measured[key], 'Original1776 fixture/config metadata differs: '+key)
    expected = saved['actual_terminal_output_artifact']
    need(len(expected['arrays']) == len(terminal['arrays']) == 52
         and set(expected['arrays']) == set(terminal['arrays']), 'Complete external52 identities required')
    need(ref(expected['path']) == {k: expected[k] for k in ('path', 'bytes', 'sha256')},
         'The actual1776 external terminal input changed')
    rows = []
    with np.load(terminal['path'], allow_pickle=False) as actual, np.load(expected['path'], allow_pickle=False) as old:
        need(set(actual.files) == set(old.files) == set(expected['arrays']), 'External52 archive keys differ')
        for key in old.files:
            left, right = actual[key], old[key]
            need(left.dtype == right.dtype == np.float32 and left.shape == right.shape
                 and np.isfinite(left).all() and np.isfinite(right).all(), 'External terminal dtype/shape/nonfinite')
            rows.append({'array': key, 'bitwise_equal': left.tobytes() == right.tobytes()})
    return {'scope': 'EXTERNAL_1776_ALL52_TERMINALS_ONLY_NOT_HIDDEN_H0',
            'reference': {k: expected[k] for k in ('path', 'bytes', 'sha256')},
            'arrays': rows,
            'original1776_physics_passed': saved['passed'], 'new_capture_physics_passed': measured['passed'],
            'physics_pass_matrix_equal': measured['passed'] == saved['passed'],
            'passed': all(row['bitwise_equal'] for row in rows) and measured['passed'] == saved['passed'],
            'new_capture_H0_claimed_equal_to_1776_hidden_H0': False}