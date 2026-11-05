#!/usr/bin/env python3
"""Offline endpoints only. Never build/forward a model or change the FP32 gate."""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import sys
import zipfile

HERE = Path(__file__).absolute().parent
B = Path('/share/home/zixiao/descriptor_analysis')
COMMON = B/'runs/model_v3_20261026/H0_interface_quantization_CPU_v1_source/counterfactual_common.py'
INPUT_CAP = 128*1024**2
REPLAY_BOUND = 1e-10
TOL = 1e-5
ROLE_NAMES = ('original', 'transform0', 'transform1', 'transform2')

def need(ok, text):
    if not ok:
        raise ValueError(text)

def bootstrap_ref(path):
    path = Path(path).absolute()
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid()
         and before.st_size <= 2*1024**2, 'Ordinary bounded bootstrap source/metadata required')
    raw = path.read_bytes()
    after = path.lstat()
    keys = ('st_dev','st_ino','st_size','st_mtime_ns','st_uid','st_nlink')
    need(all(getattr(before,k) == getattr(after,k) for k in keys), 'Bootstrap changed')
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def load_file(path, name):
    need(name not in sys.modules, 'Dedicated analysis module namespace already occupied')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def ordered_f32(value, np):
    bits = value.view(np.uint32).astype(np.int64)
    magnitude = bits & 0x7fffffff
    # Both signed zeros have one rank; adjacent finite lattice values differ1.
    return np.where((bits & 0x80000000) != 0, 0x80000000-magnitude, 0x80000000+magnitude)

def replay_control(saved, replay, expected, actual, bound):
    differences = []
    exact = ('field','unit','law','count','components','absolute_tolerance','relative_tolerance',
             'finite','nonzero_required','nonzero_norm_floor','reference_nonzero_rows',
             'actual_nonzero_rows','passed')
    for name in exact:
        if saved[name] != replay[name]:
            differences.append('exact:'+name)
    for name in ('maxabs','reference_max_row_norm','actual_max_row_norm'):
        if saved[name] is None or replay[name] is None or abs(saved[name]-replay[name]) > bound:
            differences.append('scalar:'+name)
    index = (saved['argmax']['row'], saved['argmax']['component'])
    if abs(float(actual[index])-saved['argmax']['actual']) > bound:
        differences.append('saved_argmax_actual')
    if abs(float(expected[index])-saved['argmax']['expected']) > bound:
        differences.append('saved_argmax_expected')
    return differences, index

def lattice_record(actual, expected, old_index, np):
    nearest = expected.astype(np.float32)
    need(np.isfinite(nearest).all(), 'Finite closest-F32 target required')
    with np.errstate(over='ignore'):
        lower = np.nextafter(nearest, np.float32(-np.inf)).astype(np.float64)
        upper = np.nextafter(nearest, np.float32(np.inf)).astype(np.float64)
    q = nearest.astype(np.float64)
    gap = np.abs(q-expected)
    need(bool((gap <= np.abs(lower-expected)).all() and (gap <= np.abs(upper-expected)).all()),
         'Nearest-F32 conversion was not closest among adjacent lattice values')
    a = actual.astype(np.float64)
    signed_ulp = ordered_f32(actual, np)-ordered_f32(nearest, np)
    ulps = np.abs(signed_ulp)
    impossible = gap > TOL
    max_index = tuple(int(i) for i in np.unravel_index(int(gap.argmax()), gap.shape))
    levels = (0,1,2,4,8,16,32,64,128,256,512,1024)
    histogram, previous = [], -1
    for edge in levels:
        histogram.append({'ULP_interval':[previous+1,edge],
                          'components':int(((ulps > previous) & (ulps <= edge)).sum())})
        previous = edge
    histogram.append({'ULP_interval':[previous+1,None],'components':int((ulps > previous).sum())})
    def point(index):
        plus, minus = upper[index]-q[index], q[index]-lower[index]
        return {'index':list(index),'actual_FP32':float(a[index]),'original_expected_FP64':float(expected[index]),
                'nearest_FP32':float(q[index]),'actual_minus_expected':float(a[index]-expected[index]),
                'nearest_minus_expected':float(q[index]-expected[index]),
                'actual_minus_nearest':float(a[index]-q[index]),
                'actual_to_nearest_signed_ULP':int(signed_ulp[index]),
                'nearest_spacing_plus':float(plus) if np.isfinite(plus) else None,
                'nearest_spacing_minus':float(minus) if np.isfinite(minus) else None}
    closure = (a-expected)-((a-q)+(q-expected))
    return {'population_components':int(a.size),
            'actual_abs_min':float(np.abs(a).min()),'actual_abs_max':float(np.abs(a).max()),
            'expected_abs_max':float(np.abs(expected).max()),
            'nearest_F32_gap_maxabs':float(gap.max()),
            'nearest_F32_unattainable_components_gt_original_1e_5':int(impossible.sum()),
            'all_unattainable_row_components':np.argwhere(impossible).tolist(),
            'actual_to_nearest_abs_ULP_max':int(ulps.max()),
            'actual_to_nearest_ULP_histogram':histogram,
            'at_original_saved_argmax':point(old_index),
            'at_largest_nearest_F32_gap':point(max_index),
            'signed_endpoint_decomposition_FP64_closure_maxabs':float(np.abs(closure).max()),
            'scope':'Conditional on this saved original terminal and its recorded expected transform only'}

def load_terminals(artifact, budget, np):
    leaf = {k:artifact[k] for k in ('path','bytes','sha256')}
    need(leaf['bytes'] <= 512*1024 and artifact['numeric_bytes'] <= 320*1024
         and len(artifact['arrays']) == 52 and artifact['contains_parameter_weights'] is False
         and artifact['contains_native_data'] is False, 'Original terminal-only limits required')
    budget.add(leaf, payload=True)
    headers = artifact['arrays']
    need(sum(int(np.prod(h['shape']))*4 for h in headers.values()) == artifact['numeric_bytes'],
         'Typed terminal numeric bytes differ')
    with zipfile.ZipFile(leaf['path']) as archive:
        entries = archive.infolist()
        need(len(entries) == 52 and len({e.filename for e in entries}) == 52
             and {e.filename for e in entries} == {k+'.npy' for k in headers},
             'Exact nonduplicated terminal ZIP entries required')
        for entry in entries:
            header = headers[entry.filename[:-4]]
            need(entry.file_size <= int(np.prod(header['shape']))*4+16384,
                 'Bounded terminal NPY member required')
    with np.load(leaf['path'], allow_pickle=False) as archive:
        need(len(archive.files) == 52 and set(archive.files) == set(headers), 'All52 terminal keys required')
        values = {}
        for name, header in headers.items():
            value = archive[name]
            need(value.dtype == np.float32 and header['dtype'] == 'float32'
                 and value.ndim == 2 and list(value.shape) == header['shape']
                 and value.size > 0 and np.isfinite(value).all(), 'Finite typed F32 terminal matrix required')
            values[name] = value.copy()
    return leaf, values

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--inputs-sha256', required=True)
    parser.add_argument('--source-pins-sha256', required=True)
    parser.add_argument('--expected-node', choices=['compute-0-'+str(i) for i in (2,*range(8,20))], required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    a = parser.parse_args()
    need(os.getuid() == 1278 and os.environ.get('SLURM_JOB_ID','').isdigit()
         and int(os.environ.get('SLURM_CPUS_PER_TASK','0')) == 16
         and os.environ.get('CUDA_VISIBLE_DEVICES') == ''
         and socket.gethostname().split('.')[0] == a.expected_node, 'Actual owned16CPU allocation required')
    pins_ref = bootstrap_ref(HERE/'source_pins.json')
    input_ref = bootstrap_ref(a.inputs)
    need(pins_ref['sha256'] == a.source_pins_sha256 and input_ref['sha256'] == a.inputs_sha256,
         'Exact new inputs/pins required')
    pins = json.loads(Path(pins_ref['path']).read_bytes())
    need(pins['schema'] == 'model_v3_projection_4550_terminal_offline_CPU_source_v1'
         and pins['inputs'] == input_ref, 'Exact frozen offline-analysis input required')
    deps = json.loads((HERE/'dependencies.json').read_bytes())
    for leaf in pins['files']:
        need(bootstrap_ref(leaf['path']) == {k:leaf[k] for k in ('path','bytes','sha256')}, 'Package source changed')
    need(bootstrap_ref(COMMON) == deps['common_IO'], 'Original stdlib I/O source changed')
    common = load_file(COMMON, '_projection4550_frozen_IO')
    budget = common.Budget()
    inputs = budget.json(input_ref)
    budget.add(pins_ref)
    for leaf in pins['files']:
        budget.add({k:leaf[k] for k in ('path','bytes','sha256')})
    for name in ('common_IO','projection_adapter','original_fixture','existing_CPU_supervisor','original_CPU_template'):
        budget.add(deps[name])
    for leaf in deps['existing_CPU_helpers']:
        budget.add(leaf)
    need(inputs['schema'] == 'model_v3_projection_4550_terminal_offline_CPU_inputs_v1'
         and inputs['scalar_replay_bound'] == REPLAY_BOUND
         and inputs['original_absolute_tolerance'] == TOL and inputs['original_relative_tolerance'] == 0
         and inputs['input_cap_bytes'] == INPUT_CAP, 'Fixed diagnostic policy required')
    result = budget.json(inputs['actual_GPU_result'])
    need(result['status'] == 'PHYSICAL_CRITERION_FAIL' and result['failure'] is None
         and result['counts'] == {'tests':48,'failures':36,'errors':0,'skipped':0}
         and result['local_commit'] == inputs['code_sha']
         and result['source_before_after_equal'] is True, 'Original failed source scope differs')
    adapter = load_file(deps['projection_adapter']['path'], '_projection4550_original_adapter')
    equation = adapter.load_equation()
    need(bootstrap_ref(adapter.FIXTURE_SOURCE) == deps['original_fixture'], 'Original comparator source differs')
    need([c['case_id'] for c in inputs['cases']] == [s.identity for s in equation.CASE_SPECS],
         'Original full48 order/population required')
    import numpy as np
    import torch
    need(not torch.cuda.is_initialized(), 'CPU analysis must not initialize CUDA')
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    need(not a.output_root.exists() and not a.output_root.is_symlink(), 'Fresh analysis output required')
    a.output_root.mkdir(parents=True)
    records, errors, cases, unmatched, blocked_records, blocked_components = 0, [], [], 0, 0, 0
    csv_path = a.output_root/'all_1872_field_transform_records.csv'
    columns = ('case_id','distance_bias','views','head_policy','weight_seed','transform','field','law','unit',
               'rows','components','original_passed','scalar_replay_matched','original_maxabs',
               'nearest_F32_gap_maxabs','unattainable_components','actual_abs_max','actual_to_nearest_ULP_max',
               'original_argmax_signed_tuple_json')
    with csv_path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader()
        for number, selected in enumerate(inputs['cases']):
            identity, local_rows = selected['case_id'], []
            try:
                captured = budget.json(selected['case_json'])
                measured = captured['measured']
                need(measured['case_id'] == identity and measured['case'] == selected['case_spec']
                     and measured['complete_terminal_count'] == 13 and len(measured['measurements']) == 3
                     and measured['passed'] == selected['original_physics_passed'], 'Original case identity differs')
                need(captured['construction']['original_parameter_sha256'] ==
                     captured['construction']['actual_parameter_sha256'] ==
                     measured['weight_summary']['all_named_parameter_sha256'] == selected['original_parameter_sha256'],
                     'Saved parameter identity differs')
                artifact = measured['actual_terminal_output_artifact']
                need({k:artifact[k] for k in ('path','bytes','sha256')} == selected['terminal_npz'],
                     'Selected terminal rawref differs')
                leaf, arrays = load_terminals(artifact, budget, np)
                field_names = [f['field'] for f in measured['measurements'][0]['fields']]
                need(len(field_names) == len(set(field_names)) == 13
                     and set(arrays) == {role+'__'+field.replace('/','__') for role in ROLE_NAMES for field in field_names},
                     'Complete original thirteen-field/four-role keys required')
                for tnum, movement in enumerate(measured['measurements']):
                    document = movement['transform']
                    need(document['row_vector_rule'] == 'x @ R + t'
                         and [f['field'] for f in movement['fields']] == field_names, 'Original transform/field order differs')
                    transform = equation.RigidTransform(document['name'],
                        torch.tensor(document['rotation_float64'], dtype=torch.float64),
                        torch.tensor(document['translation_A'], dtype=torch.float64))
                    for saved in movement['fields']:
                        field, suffix = saved['field'], saved['field'].replace('/','__')
                        original, actual = arrays['original__'+suffix], arrays['transform'+str(tnum)+'__'+suffix]
                        reference_tensor, actual_tensor = torch.from_numpy(original), torch.from_numpy(actual)
                        expected_tensor = equation.transform_expected(reference_tensor, transform, saved['law'])
                        replay = equation.field_measurement(field, actual_tensor, expected_tensor,
                            law=saved['law'], unit=saved['unit'], require_nonzero=saved['nonzero_required'],
                            reference=reference_tensor)
                        expected = expected_tensor.numpy()
                        failures, old_index = replay_control(saved, replay, expected, actual, REPLAY_BOUND)
                        nearest = lattice_record(actual, expected, old_index, np)
                        need(nearest['signed_endpoint_decomposition_FP64_closure_maxabs'] <= REPLAY_BOUND,
                             'Endpoint decomposition arithmetic control differs')
                        record = {'case_id':identity,'case':selected['case_spec'],'transform':document,
                                  'saved_measurement':saved,'replayed_measurement':replay,
                                  'scalar_replay_disagreements':failures,'nearest_F32':nearest,
                                  'input_pushforward_evidence_reused':movement['view_proof'],
                                  'saved_vector_edges_unchanged':movement['vector_edges_unchanged']}
                        local_rows.append(record); records += 1; unmatched += bool(failures)
                        impossible = nearest['nearest_F32_unattainable_components_gt_original_1e_5']
                        blocked_records += impossible > 0; blocked_components += impossible
                        writer.writerow({'case_id':identity,**selected['case_spec'],'transform':document['name'],
                            'field':field,'law':saved['law'],'unit':saved['unit'],'rows':saved['count'],
                            'components':saved['components'],'original_passed':saved['passed'],
                            'scalar_replay_matched':not failures,'original_maxabs':saved['maxabs'],
                            'nearest_F32_gap_maxabs':nearest['nearest_F32_gap_maxabs'],
                            'unattainable_components':impossible,'actual_abs_max':nearest['actual_abs_max'],
                            'actual_to_nearest_ULP_max':nearest['actual_to_nearest_abs_ULP_max'],
                            'original_argmax_signed_tuple_json':json.dumps(nearest['at_original_saved_argmax'],sort_keys=True)})
                need(common.reference(leaf['path'],524288) == leaf, 'Terminal archive changed while read')
                case_result = {'schema':'projection4550_saved_terminal_case_analysis_v1',
                    'case_id':identity,'original_physics_passed':measured['passed'],
                    'actual_archive':leaf,'all39_records':local_rows,'new_encoder_or_head_calls':0}
            except Exception as exc:
                errors.append({'case_id':identity,'type':type(exc).__name__,'message':str(exc)[:1024]})
                case_result = {'schema':'projection4550_saved_terminal_case_analysis_v1',
                    'case_id':identity,'analysis_error':errors[-1],'partial_records':local_rows,
                    'original_physics_passed':selected['original_physics_passed']}
            cases.append(common.write_new(a.output_root/('case_%02d.json'%number),case_result))
        stream.flush(); os.fsync(stream.fileno())
    for entry in budget.identities.values():
        path, size, mtime, sha = entry
        need(common.reference(path,8*1024**2) == {'path':path,'bytes':size,'sha256':sha}
             and Path(path).stat().st_mtime_ns == mtime, 'Input/source changed after analysis')
    need(not torch.cuda.is_initialized(), 'CPU-only analysis initialized CUDA')
    complete = not errors and unmatched == 0 and len(cases) == 48 and records == 1872
    summary = {'schema':'projection4550_saved_terminal_analysis_result_v1',
        'status':'COMPLETE_PENDING_ACTUAL_CPU_OUTER_C0' if complete else 'HOLD_ANALYSIS_NOT_CLOSED',
        'purpose':inputs['purpose'],'job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname(),
        'original_GPU_physics_counts_preserved':result['counts'],'original_passed_cases':12,
        'cases':cases,'field_transform_records':records,'scalar_replay_mismatched_records':unmatched,
        'errors':errors,'nearest_F32_unattainable_field_transform_records':blocked_records,
        'nearest_F32_unattainable_components':blocked_components,
        'representability_scope':'Only these saved original terminals and their original recorded expected transforms',
        'cannot_separate_encoder_head_or_input_rounding_causes':True,
        'no_universal_FP32_floor_claim':True,'new_model_or_encoder_or_head_calls':0,
        'input_unique_bytes':budget.total,'source_pins':pins_ref,'inputs':input_ref,
        'CSV':common.reference(csv_path,64*1024**2),
        'runtime':{'logical_python':sys.executable,'torch':str(torch.__version__),'numpy':str(np.__version__),
                   'torch_threads':torch.get_num_threads(),'torch_interop_threads':torch.get_num_interop_threads(),
                   'CUDA_initialized':torch.cuda.is_initialized()},
        'scientific_adoption':False,'original_4550_physics_verdict_changed':False}
    common.write_new(a.output_root/'RESULT.json',summary)
    print(json.dumps({'status':summary['status'],'records':records,'cases':len(cases),
                      'scalar_replay_mismatches':unmatched,'analysis_errors':len(errors)},sort_keys=True))
    return 0 if complete else 1

if __name__ == '__main__':
    raise SystemExit(main())
