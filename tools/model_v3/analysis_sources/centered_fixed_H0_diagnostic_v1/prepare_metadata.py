#!/usr/bin/env python3
"""Root-only metadata assembly. No Torch/NumPy import, NPZ open, network or sbatch."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat

B = Path('/share/home/zixiao/descriptor_analysis')
N = B/'runs/model_v3_20261026'
HERE = Path(__file__).absolute().parent
E2E = N/'attention_centered_e2e_v1_source'
OLD2 = N/'numeric_fixed_h0_shadow_v2_source'
OLD3 = N/'numeric_fixed_h0_shadow_v3_source'

# Input identity is frozen in DRAFT_DEPENDENCIES.json by raw-byte machine hashes.
# Root may assemble after review; actual GPU execution requires publication of the final request/source.
def need(value, message):
    if not value:
        raise ValueError(message)

def reference(path):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 2*1024**2,
         'Bounded ordinary source/JSON required')
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def bound(leaf):
    need(reference(leaf['path']) == leaf, 'Original metadata changed: '+leaf['path'])
    return json.loads(Path(leaf['path']).read_bytes())

def write_new(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    need(len(raw) <= 2*1024**2, 'New metadata exceeds2MiB')
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    return reference(path)

def assemble():
    need(not (HERE/'execution_request_v1.json').exists() and not (HERE/'source_pins_v1.json').exists(),
         'Never overwrite an assembled request or consumed pins')
    deps = json.loads((HERE/'DRAFT_DEPENDENCIES.json').read_bytes())
    need(deps['status'] == 'DRAFT_SOURCE_ONLY_NOT_EXECUTED', 'Draft dependency identity differs')
    for leaf in deps['files']:
        need(reference(leaf['path']) == leaf, 'Actual dependency source changed')
    source_inventory = json.loads((HERE/'DRAFT_SOURCE_INVENTORY.json').read_bytes())
    for leaf in source_inventory['files']:
        need(reference(leaf['path']) == leaf, 'Reviewed draft source changed')
    base = bound(deps['centered_execution_request'])
    closure = bound(deps['actual1776_Root_closure'])
    need(base['local_commit'] == 'cf8ce66d97cd518ebf279b40ee20294919bb95e1'
         and base['public_commit'] == 'f8417157dc23326d1beca8e19e4725755d9f13c6'
         and base['exact_shared_tree'] == '2389ab046ee23f2ba92fcb61179d853dfdee8357'
         and base['expected_case_count'] == 48 and len(base['expected_case_ids']) == 48,
         'Actual tested centered candidate identity differs')
    need(closure['schema'] == 'model_v3_centered_complete48_Root_metadata_closure_v1'
         and closure['status'] == 'ACTUAL_COMPLETE48_SCIENTIFIC_GATE_FAIL_RETAINED_NOT_ADOPTED'
         and closure['actual_sacct'] == '4521776|zixiao|FAILED|1:0|42|16|compute-0-21'
         and closure['passed_cases'] == 21 and closure['failed_cases'] == 27
         and closure['source_before_after_equal'] and len(closure['case_refs']) == 48,
         'Original failed1776 closure must remain explicit and unchanged')
    old_manifest = bound(base['original_capture_manifest'])
    need(old_manifest['job_id'] == '4521492' and old_manifest['status'] == 'CAPTURE_COMPLETE'
         and old_manifest['source_before_after_equal'] and len(old_manifest['cases']) == 48,
         'Original1492 parameter metadata authority differs')
    expected = base['expected_case_ids']
    need([row['case_id'] for row in old_manifest['cases']] == expected, 'Original1492 full48 order differs')
    parameters, old_cases, external, stats = {}, [], {}, []
    proof_sources = [deps['actual1776_Root_closure'], deps['centered_execution_request'], base['original_capture_manifest']]
    for identity, old_leaf, new_ref in zip(expected, old_manifest['cases'], closure['case_refs']):
        old = bound(old_leaf['capture_case'])
        actual = bound(new_ref)
        measured = actual['measured']
        need(old['case_id'] == measured['case_id'] == identity and old['case'] == measured['case']
             and actual['attention_aggregation_mode'] == 'centered_fp32_v1'
             and actual['numeric_mode'] == 'compensated_fp32_v1'
             and measured['weight_summary']['all_named_parameter_sha256'] ==
                 old['original_measurement']['weight_summary']['all_named_parameter_sha256'],
             'Full48 original case/seed/parameter identity differs')
        terminal = measured['actual_terminal_output_artifact']
        path = Path(terminal['path'])
        need(path.suffix == '.npz' and not path.is_symlink() and path.is_file(), 'Ordinary1776 terminal stat required')
        st = path.stat()
        need(stat.S_ISREG(st.st_mode) and st.st_size == terminal['bytes'] and st.st_nlink == 1,
             'Original1776 terminal stat differs; this is NOT a payload hash check')
        need(len(terminal['arrays']) == 52 and measured['complete_terminal_count'] == 13
             and measured['domain']['domain_pass'], 'Complete original52/domain required')
        parameters[identity] = old['original_measurement']['weight_summary']['all_named_parameter_sha256']
        external[identity] = new_ref
        old_cases.append(old_leaf['capture_case'])
        proof_sources += [old_leaf['capture_case'], new_ref]
        stats.append({'case_id': identity, 'artifact_ref_from_original_metadata': {k:terminal[k] for k in ('path','bytes','sha256')},
            'device': st.st_dev, 'inode': st.st_ino, 'bytes': st.st_size, 'mtime_ns': st.st_mtime_ns,
            'payload_opened_or_hashed_by_prepare': False})
    need(len(external) == len(parameters) == 48 and sum(row['bytes'] for row in stats) <= 128*1024**2,
         'Bounded complete external terminal input required')
    request = deepcopy(base)
    request.update(schema='model_v3_centered_fixed_H0_capture_GPU_request_v1',
        executable=str(HERE/'capture_centered_H0.py'),
        original1492_parameter_sha256=parameters, original1492_case_refs=old_cases,
        external1776_case_refs=external, actual1776_Root_closure=deps['actual1776_Root_closure'],
        external1776_terminal_stat_observations=stats,
        centered_adapter=reference(E2E/'centered_adapter.py'),
        centered_tiny_controls=reference(E2E/'tiny_candidate_controls.py'),
        scientific_acceptance=False, purpose='FRESH_CENTERED_H0_DIAGNOSTIC_NOT_CANDIDATE_ACCEPTANCE',
        fresh_H0_lineage='new_job_not_1776_hidden_H0_not_old1492_H0',
        encoder_forwards=192, full_FP64_encoder_forwards=0,
        physics_failure_does_not_stop_remaining_cases=True,
        external_terminal_replay_failure_blocks_CPU_attribution=True)
    source_values = base['source_refs']+deps['files']+proof_sources
    source_map = {leaf['path']: leaf for leaf in source_values}
    need(all(source_map[leaf['path']] == leaf for leaf in source_values), 'Conflicting source identity')
    request['source_refs'] = list(source_map.values())
    request_ref = write_new(HERE/'execution_request_v1.json', request)
    own = [reference(path) for path in sorted(HERE.iterdir()) if path.is_file()
           and path.name not in ('source_pins_v1.json',)]
    pins = {'schema': 'model_v3_centered_fixed_H0_capture_GPU_launch_source_pins_v1',
        'status': 'ROOT_ASSEMBLED_SOURCE_BOUND_NOT_EVIDENCE_OF_EXECUTION_OR_PUBLICATION',
        'files': own, 'protected_dependencies': deps['files']+deps['inherited_protected_dependencies'], 'execution_request': request_ref,
        'original_capture_source': deps['original_capture_source'],
        'original1503_functional_source': deps['original1503_functional_source'],
        'same48_tolerance': {'absolute': 1e-5, 'relative': 0},
        'new_capture_job_id': None, 'CPU_analysis_completed': False, 'scientific_adoption': False}
    pins_ref = write_new(HERE/'source_pins_v1.json', pins)
    return {'status':'ASSEMBLED_METADATA_ONLY_NO_SUBMISSION', 'request':request_ref, 'source_pins':pins_ref,
            'NPZ_payload_read':False, 'SDK_read':False, 'new_job_C0_claimed':False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assemble', action='store_true', required=True)
    p.parse_args()
    print(json.dumps(assemble(), sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())