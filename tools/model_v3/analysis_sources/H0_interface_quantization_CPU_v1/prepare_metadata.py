#!/usr/bin/env python3
"""Metadata-only assembly after Root review/preregistration; no payload/model open."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from counterfactual_common import HERE, INPUT_CAP, REPLAY_BOUND, Budget, need, read_json, reference, write_new

def assemble():
    need(not (HERE/'inputs_v1.json').exists() and not (HERE/'source_pins_v1.json').exists(), 'Fresh bindings only')
    deps = json.loads((HERE/'DRAFT_DEPENDENCIES.json').read_bytes())
    inventory = json.loads((HERE/'DRAFT_SOURCE_INVENTORY.json').read_bytes())
    for leaf in inventory['files']:
        need(reference(leaf['path']) == leaf, 'Reviewed draft source changed')
    budget = Budget()
    root64 = budget.json(deps['Root1561'])
    root32 = budget.json(deps['Root1838'])
    need(root64['schema'] == 'model_v3_full_encoder_4521561_Root_metadata_closure_v1'
         and root64['status'] == 'ROOT_METADATA_VERIFIED_DIAGNOSTIC_ONLY'
         and root64['job_id'] == '4521561' and root64['roles_bitwise_matched'] == 192
         and root64['individual_bitwise_comparisons'] == 768
         and root64['original_recorded_comparison_truth_verified'] is True,
         'Actual historical1561 replay lineage required')
    need(root32['schema'] == 'model_v3_centered_fixed_H0_capture_Root_metadata_closure_v1'
         and root32['status'] == 'ACTUAL_GPU_C0_FULL48_EXTERNAL52_REPLAY_CLOSED_CPU_DIAGNOSTIC_ALLOWED'
         and root32['case_count'] == 48 and root32['encoder_forwards'] == 192
         and root32['source_before_after_equal'] is True, 'Actual new1838 capture closure required')
    controls = [deps['Root1561'], deps['Root1838'], root64['complete'], root64['FP32_replay_gate'],
        root64['supervisor'], root64['source_manifest'], root32['complete'], root32['supervisor'],
        root32['accounting'], root32['prereg_publication'], deps['Root_selected_input_stat']]
    for leaf in controls:
        budget.json(leaf)
    historical = budget.json(root64['result'])
    centered = budget.json(root32['manifest'])
    old_complete = budget.json(historical['capture_complete'])
    original = budget.json(old_complete['manifest'])
    need(historical['case_count'] == 48 and centered['job_id'] == '4521838'
         and original['job_id'] == '4521492'
         and centered['status'] == original['status'] == 'CAPTURE_COMPLETE', 'Exact input populations required')
    cases, params = [], []
    from counterfactual_common import equal_case, validate_authorities
    validate_authorities(root64,root32,budget)
    for new_leaf, old_leaf, reference_leaf in zip(centered['cases'], original['cases'], historical['cases']):
        new = budget.json(new_leaf['capture_case'])
        old = budget.json(old_leaf['capture_case'])
        saved = budget.json(reference_leaf['result'])
        alignment = equal_case(old, new, saved)
        budget.add(new['packed']['file'], payload=True, hash_payload=False)
        budget.add(saved['FP64_clean_H0']['file'], payload=True, hash_payload=False)
        cases.append({'case_id': new['case_id'], 'centered_capture': new_leaf,
            'original1492_capture': old_leaf['capture_case'], 'historical1561': reference_leaf['result'],
            'alignment': alignment})
        params.append(new['case_id'])
    need(len(cases) == len(set(params)) == 48
         and params == [row['case_id'] for row in original['cases']] == [row['case_id'] for row in historical['cases']],
         'No case/seed/role selection permitted')
    # Bind all declared candidate package Python, including imports made by model.__init__.
    native_request = budget.json(centered['request'])
    prefix = native_request['repository']+'/current/phychem_mfm/'
    package_sources = [leaf for leaf in native_request['source_refs']
                       if leaf['path'].startswith(prefix) and leaf['path'].endswith('.py')]
    need(package_sources, 'Actual candidate package source declarations required')
    sources = {leaf['path']:leaf for leaf in deps['implementation_sources']+package_sources}
    for leaf in sources.values():
        budget.add(leaf)
    result = {'schema':'model_v3_H0_interface_quantization_CPU_inputs_v1',
        'purpose':'HISTORICAL_FIXED_H64_COUNTERFACTUAL_DIAGNOSTIC_ONLY',
        'Root1561':deps['Root1561'], 'Root1838':deps['Root1838'], 'controls':controls,
        'historical_analysis':root64['result'], 'centered_manifest':root32['manifest'],
        'original1492_manifest':old_complete['manifest'], 'historical_capture_complete':historical['capture_complete'],
        'centered_request':centered['request'], 'cases':cases, 'case_ids':params,
        'candidate_repository':native_request['repository'], 'source_refs':list(sources.values()),
        'diagnostic_scalar_replay_absolute_bound':REPLAY_BOUND, 'physical_absolute_threshold':1e-5,
        'physical_relative_threshold':0, 'combined_input_cap_bytes':INPUT_CAP,
        'selected_inputs_stat_bytes_before_new_bindings':budget.total,
        'NPZ_payload_read_or_current_hash_performed_by_prepare':False,
        'FP64_encoder_is_current_centered_hidden_H0':False, 'encoder_forwards':0, 'scientific_adoption':False}
    input_ref = write_new(HERE/'inputs_v1.json', result)
    own = [reference(path) for path in sorted(HERE.iterdir()) if path.is_file() and path.name != 'source_pins_v1.json']
    # Include all new metadata/source in the SAME finite cap; no waiver or reserved zeroes.
    for leaf in own:
        budget.add(leaf)
    pins = {'schema':'model_v3_H0_interface_quantization_CPU_source_pins_v1',
        'status':'SOURCE_BOUND_NO_EXECUTION_OR_NEW_PUBLICATION_CLAIM', 'inputs':input_ref,
        'files':own, 'protected_dependencies':list(sources.values()),
        'input_bytes_before_pins':budget.total, 'combined_input_cap_bytes':INPUT_CAP,
        'original_encoder_reference_algorithm_is_different':True, 'scientific_adoption':False}
    pin_ref = write_new(HERE/'source_pins_v1.json', pins)
    budget.add(pin_ref)
    return {'status':'METADATA_ASSEMBLED_NO_SUBMISSION', 'inputs':input_ref, 'source_pins':pin_ref,
            'combined_selected_stat_bytes':budget.total,'input_cap_bytes':INPUT_CAP,'payload_read':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assemble',action='store_true',required=True)
    parser.parse_args()
    print(json.dumps(assemble(),sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())