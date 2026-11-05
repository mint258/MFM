"""Offline frame audit from retained source outputs, without rerunning QM."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).absolute().parent.parent))
from common import read_staging, reference, require_pin, write_json
from math_v1 import (AU_DIPOLE_TO_DEBYE, covariance, force_relation, mechanical_diagnostics,
                    output_frame, tensor_checks, tensor_covariance, tensor_translation)
from prepare_v1 import load_audit


def compare_stored(stored, raw, atol=1e-12):
    import numpy as np
    if stored is None or raw is None:
        return {'pass': False, 'status': 'STORED_OR_RAW_FIELD_UNAVAILABLE'}
    a, b = np.asarray(stored, float), np.asarray(raw, float)
    if a.size != b.size:
        return {'pass': False, 'status': 'STORED_RAW_SHAPE_MISMATCH'}
    a = a.reshape(b.shape)
    return {'pass': bool(np.isfinite(a).all() and np.all(np.abs(a-b) <= atol)),
            'max_abs_stored_raw_difference': float(np.max(np.abs(a-b)))}


def measurement(record, config):
    case = record['case']
    obs, parsed = record.get('independent_raw_readback', {}), record.get('parsed_wp5_result', {})
    values = parsed.get('values', {})
    result = {'case_id': case['case_id'], 'QM_scope_status': parsed.get('scope_status'),
              'postcall_inputs_match_prepared': all(p['matches_prepared_bytes'] for p in record.get('actual_postcall_input_references', [])),
              'coordinates': {'status': 'OWN_SOURCE_OUTPUT_COORDINATES_UNAVAILABLE', 'supports_input_axes': False},
              'vectors': {}, 'quadrupole': None, 'stored_raw_checks': {}}
    if case['calc_type'] == 'pm7_B':
        aux = obs.get('mopac_aux', {})
        coordinates = aux.get('ATOM_X_OPT:ANGSTROMS')
        elements = aux.get('ATOM_EL', {}).get('values')
        if coordinates is not None:
            result['coordinates'] = output_frame(case['actual_rendered_coordinates_A'], coordinates['values'],
                                                  config['coordinate_atol_A']['mopac'])
            result['coordinates']['source_artifact'] = 'input.aux:ATOM_X_OPT:ANGSTROMS'
            result['coordinates']['atom_order_matches'] = (elements is not None and
                [v.capitalize() for v in elements] == case['symbols'])
            result['coordinates']['supports_input_axes'] &= result['coordinates']['atom_order_matches']
        for key, name in [('DIP_VEC:DEBYE', 'pm7_dipole_Debye'),
                          ('GRADIENTS:KCAL/MOL/ANGSTROM', 'pm7_gradient_kcal_mol_A')]:
            if key in aux:
                result['vectors'][name] = aux[key]
                stored = values.get('dipole_Debye' if key.startswith('DIP') else 'gradient_kcal_mol_A')
                result['stored_raw_checks'][name] = compare_stored(stored, aux[key]['values'])
    else:
        dip = obs.get('xtb_dipole')
        if dip:
            result['vectors']['xtb_dipole_Debye'] = {'values': dip['dipole_Debye'],
                'rounding_halfwidth': dip['rounding_halfwidth_Debye']}
            result['dipole_au'] = dip['raw_atomic_units']
            result['dipole_epsilon_au'] = [e/AU_DIPOLE_TO_DEBYE for e in dip['rounding_halfwidth_Debye']]
            # WP5 intentionally drops dipoles from the perturbed-gradient target scope.
            if case['calc_type'] == 'xtb_singlepoint':
                result['stored_raw_checks']['xtb_dipole_Debye'] = compare_stored(values.get('dipole_Debye'), dip['dipole_Debye'])
        gradient = obs.get('xtb_gradient')
        if gradient:
            hypotheses = {name: output_frame(case['actual_rendered_coordinates_A'], coords,
                          config['coordinate_atol_A']['xtb']) for name, coords in
                          gradient['coordinate_conversion_hypotheses_A'].items()}
            matching = [name for name, value in hypotheses.items() if value['supports_input_axes']]
            selected = matching[0] if matching else 'WP5_parser_0.529177210903'
            result['coordinates'] = dict(hypotheses[selected],
                coordinate_conversion_selected=selected, coordinate_conversion_hypotheses=hypotheses,
                conversion_note='predeclared implementation constants checked separately; frozen force/label conversion not changed')
            result['coordinates']['source_artifact'] = 'gradient:$grad coordinates (Bohr -> Angstrom)'
            result['coordinates']['atom_order_matches'] = gradient['symbols'] == case['symbols']
            result['vectors']['xtb_gradient_Eh_bohr'] = {'values': gradient['gradient_Eh_bohr'],
                'rounding_halfwidth': gradient['gradient_rounding_halfwidth_Eh_bohr']}
            result['stored_raw_checks']['xtb_gradient_Eh_bohr'] = compare_stored(values.get('gradient_Eh_bohr'), gradient['gradient_Eh_bohr'])
            result['force_relation'] = force_relation(gradient['gradient_Eh_bohr'], values.get('forces_eV_A'))
            result['mechanical_diagnostics'] = mechanical_diagnostics(gradient['coordinates_A'], gradient['gradient_Eh_bohr'])
        q = obs.get('xtb_quadrupole')
        if q:
            result['quadrupole'] = q
            result['quadrupole_checks'] = tensor_checks(q['six_components_au'], q['rounding_halfwidth_au'])
            if case['calc_type'] == 'xtb_singlepoint':
                result['stored_raw_checks']['r674_quadrupole_six'] = compare_stored(values.get('molecular_quadrupole_traceless_au'), q['six_components_au'])
    return result


def evaluate(records, config):
    import numpy as np
    groups = {}
    measured = {}
    for record in records:
        case = record.get('case')
        if case is None:
            continue
        key = (case['molecule_id'], case['geometry_source'], case['condition'])
        groups.setdefault(key, {})[case['arm']] = record
        measured[case['case_id']] = measurement(record, config)
    comparisons, contradictions, incomplete = [], [], []
    for key, arms in sorted(groups.items()):
        if key[2].endswith('origin_translation'):
            continue
        result = {'molecule_id': key[0], 'geometry_source': key[1], 'condition': key[2],
                  'vector_covariance': {}, 'quadrupole_covariance': None}
        if set(arms) != {'base', 'rotated'}:
            incomplete.append({'group': list(key), 'reason': 'CONTROL_ARM_MISSING'})
            continue
        base, rotated = (measured[arms[arm]['case']['case_id']] for arm in ('base', 'rotated'))
        if base['QM_scope_status'] != 'SUCCESS' or rotated['QM_scope_status'] != 'SUCCESS':
            incomplete.append({'group': list(key), 'reason': 'QM_TASK_NOT_SUCCESS'})
            comparisons.append(result)
            continue
        for field in sorted(set(base['vectors']) & set(rotated['vectors'])):
            b, r = base['vectors'][field], rotated['vectors'][field]
            check = covariance(b['values'], r['values'], b['rounding_halfwidth'],
                               r['rounding_halfwidth'], config['vector_tolerances'][field])
            result['vector_covariance'][field] = check
            if not check['within_numeric_allowance']:
                contradictions.append({'group': list(key), 'field': field, 'reason': 'VECTOR_NOT_COVARIANT'})
            elif not check['sufficient_signal']:
                incomplete.append({'group': list(key), 'field': field, 'reason': 'INSUFFICIENT_SIGNAL'})
        if not result['vector_covariance']:
            incomplete.append({'group': list(key), 'reason': 'SOURCE_VECTORS_UNAVAILABLE'})
        if base['quadrupole'] and rotated['quadrupole']:
            b, r = base['quadrupole'], rotated['quadrupole']
            check = tensor_covariance(b['six_components_au'], r['six_components_au'],
                                      b['rounding_halfwidth_au'], r['rounding_halfwidth_au'], config['tensor_tolerance'])
            result['quadrupole_covariance'] = check
            if not check['within_numeric_allowance']:
                contradictions.append({'group': list(key), 'field': 'r674', 'reason': 'TENSOR_NOT_R_Q_RT'})
        comparisons.append(result)
    companions, origins = [], []
    for mid, geom in sorted({(key[0], key[1]) for key in groups}):
        grad = groups.get((mid, geom, 'xtb_perturbed_gradient'), {})
        sp = groups.get((mid, geom, 'xtb_singlepoint_noisy_companion'), {})
        for arm in ('base', 'rotated'):
            if arm not in grad or arm not in sp:
                incomplete.append({'molecule_id': mid, 'geometry': geom, 'arm': arm, 'reason': 'COINCIDENT_GRADIENT_SP_CONTROL_MISSING'})
                continue
            g, s = grad[arm], sp[arm]
            gm, sm = measured[g['case']['case_id']], measured[s['case']['case_id']]
            same = bool(np.max(np.abs(np.asarray(g['case']['actual_rendered_coordinates_A'])-
                                      np.asarray(s['case']['actual_rendered_coordinates_A']))) <= config['rendered_coordinate_atol_A'])
            gd, sd = gm.get('dipole_au'), sm.get('dipole_au')
            dipole_match = compare_stored(gd, sd, config['same_geometry_dipole_atol_au'])
            check = {'molecule_id': mid, 'geometry_source': geom, 'arm': arm,
                     'exact_same_input_geometry': same, 'gradient_output_coordinates': gm['coordinates'],
                     'SP_gradient_raw_dipole_agreement': dipole_match,
                     'SP_coordinate_evidence': 'same-input gradient companion; SP has no independent coordinate block'}
            companions.append(check)
            if not same or not gm['coordinates']['supports_input_axes'] or not dipole_match['pass']:
                contradictions.append({'molecule_id': mid, 'geometry': geom, 'arm': arm, 'reason': 'COINCIDENT_GEOMETRY_FRAME_OR_DIPOLE_MISMATCH'})
        original = groups.get((mid, geom, 'xtb_singlepoint'), {}).get('base')
        translated = groups.get((mid, geom, 'xtb_singlepoint_origin_translation'), {}).get('translated')
        if original and translated:
            bm, tm = measured[original['case']['case_id']], measured[translated['case']['case_id']]
            bq, tq = bm.get('quadrupole'), tm.get('quadrupole')
            if bq and tq and bm.get('dipole_au'):
                check = tensor_translation(bq['six_components_au'], tq['six_components_au'],
                    bm['dipole_au'], translated['case']['translation_A'], bq['rounding_halfwidth_au'],
                    tq['rounding_halfwidth_au'], bm['dipole_epsilon_au'], config['tensor_tolerance'], total_charge=0.)
                origins.append({'molecule_id': mid, 'geometry_source': geom, **check})
                if not check['pass']:
                    contradictions.append({'molecule_id': mid, 'geometry': geom, 'field': 'r674', 'reason': 'ORIGIN_TRANSLATION_RULE_FAILED'})
            else:
                incomplete.append({'molecule_id': mid, 'geometry': geom, 'reason': 'ORIGIN_CONTROL_MULTIPOLES_UNAVAILABLE'})
    for case_id, value in measured.items():
        for field, check in value['stored_raw_checks'].items():
            if not check['pass']:
                contradictions.append({'case_id': case_id, 'field': field, 'reason': 'STORED_FIELD_DIFFERS_FROM_SOURCE_RAW'})
        if 'force_relation' in value and not value['force_relation']['pass']:
            contradictions.append({'case_id': case_id, 'reason': 'FORCE_IS_NOT_NEGATIVE_CONVERTED_GRADIENT'})
        if value.get('quadrupole_checks', {}).get('trace_within_rounding') is False:
            contradictions.append({'case_id': case_id, 'field': 'r674', 'reason': 'TRACE_EXCEEDS_PRINTED_ROUNDING_BOUND'})
        if value['coordinates']['status'] != 'OWN_SOURCE_OUTPUT_COORDINATES_UNAVAILABLE' and not value['coordinates']['supports_input_axes']:
            contradictions.append({'case_id': case_id, 'reason': 'OUTPUT_COORDINATE_REORIENTATION_OR_ORDER_CHANGE'})
    return {'status': 'ACTUAL_FRAME_CONTRADICTION_REPORT_ROOT' if contradictions else
                     'INCOMPLETE_FRAME_EVIDENCE' if incomplete else 'INPUT_FRAME_SUPPORTED_ON_TESTED_CONTROLS_WITH_LIMITS',
            'measurements': measured, 'rotation_comparisons': comparisons, 'same_geometry_SP_gradient_controls': companions,
            'quadrupole_origin_controls': origins, 'contradictions': contradictions, 'incomplete': incomplete,
            'production_membership': False, 'all_corpus_vector_frames_verified': False,
            'scope': 'PM7 B dipole/gradient; xTB GFN2 SP dipole/quadrupole and perturbed gradient/force, only these source controls',
            'limitations': ['SP lacks its own output-coordinate block: coincident gradient controls are explicit corroboration',
                'Six quadrupole components imply symmetric encoding; yx/zx/zy are not independent observations',
                'No numerical finite-difference derivative test; torque is diagnostic only',
                'PM7 ions/solvent vector fields and untested molecules are not certified by this control set']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    config = load_audit(args.config)
    closed = json.loads((args.run/'run_closed.json').read_text())
    records = []
    for pin in closed['results']:
        path = require_pin(pin)
        records.append(read_staging(path.read_bytes()))
    report = evaluate(records, config)
    report.update(run=reference(args.run/'run_closed.json'), config=reference(args.config),
                  execution_errors=closed['execution_errors'], all_workers_joined=closed['all_workers_joined'])
    if closed['execution_errors'] or not closed['all_workers_joined']:
        report['status'] = 'EXECUTION_INCOMPLETE_NO_FRAME_ACCEPTANCE'
    write_json(args.output, report)


if __name__ == '__main__':
    main()
