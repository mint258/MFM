"""C4 v3 decision + nonblocking diagnostics of saved uncompensated FP32 arrays."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import time
import zipfile

N = Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026')
FIELDS = {
    'PD/p_extensive': ('scalar', 'graph'), 'PD/p_intensive': ('scalar', 'graph'),
    'PD/d_intensive': ('scalar', 'graph'), 'PD/d_binary': ('scalar', 'graph'),
    'PD/d_atom': ('scalar', 'clean_atom'), 'PD/p_pair': ('scalar', 'clean_bond'),
    'PD/p_gradient': ('vector', 'clean_atom'), 'PD/p_dipole': ('vector', 'graph'),
    'PD/p_dipole_magnitude': ('scalar', 'graph'), 'S/noise': ('vector', 'physical_atom'),
    'S/coordinate': ('coordinate', 'physical_atom'), 'S/element_logits': ('scalar', 'physical_atom'),
    'S/clean_bond_logits': ('scalar', 'clean_bond')}
TRANSFORMS = ('general_rotation', 'translation_only', 'other_rotation_and_translation')
MOLECULES = ('water_like_3', 'ethanol_like_9', 'decane_like_32_not_optimized')
MAX_OUTPUT = 128 << 20


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def read_json(path, expected=None):
    p = Path(path)
    need(p.is_absolute() and p.suffix == '.json' and not p.is_symlink()
         and p.stat().st_size <= 2 << 20, 'Bounded ordinary JSON metadata required')
    raw = p.read_bytes()
    if expected:
        need(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'],
             'Metadata binding differs: ' + str(p))
    return json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite metadata')))


def bound(ref):
    return read_json(ref['path'], ref)


def budget_action(prior_seconds, consecutive_failures):
    known = (type(prior_seconds) in (int, float) and math.isfinite(prior_seconds)
             and prior_seconds >= 0 and type(consecutive_failures) is int and consecutive_failures >= 0)
    if not known:
        return {'action': 'UNRESOLVED_CONSERVATIVE_OLD_PATH_CONTINUE', 'reason': 'BUDGET_STATE_UNAVAILABLE',
                'FP32_report_permitted': False}
    stop = prior_seconds >= 4 * 3600 or consecutive_failures >= 2
    return {'action': 'UNRESOLVED_CONSERVATIVE_OLD_PATH_CONTINUE' if stop else 'ONE_BOUNDED_SAVED_ARRAY_REPORT',
            'reason': 'FOUR_HOURS_OR_TWO_CONSECUTIVE_FAILURES' if stop else 'WITHIN_EXPLICIT_OPERATIONAL_BUDGET',
            'prior_diagnostic_seconds': prior_seconds, 'consecutive_failures': consecutive_failures,
            'FP32_report_permitted': not stop}


def c4_decision(request, prior_seconds=None, consecutive_failures=None):
    """Stdlib metadata consumer; FP32/log/fixture/SHA issues never reinstate HOLD."""
    snapshot = request['effective_C4_snapshot']
    need(snapshot == {'status': 'PASS', 'authority': 'USER_EXPLICIT_V3',
        'hard_FP64_relative_error_max': 1e-9, 'existing_job': '4524734', 'passed': 48,
        'total': 48, 'FP32_diagnostic_only': True, 'old_runs_rerun': False},
        'Actual user-v3/4734 decision snapshot required')
    issues = []
    evidence = {'effective_authorization_current_read': False, 'existing_FP64_summary_current_read': False}
    try:
        authority = bound(request['effective_authorization'])
        need(authority['schema'] == 'model_line_user_v3_effective_authorization_v1'
             and authority['C4'] == snapshot, 'Current effective authority differs')
        evidence['effective_authorization_current_read'] = True
    except Exception as error:
        issues.append({'scope': 'authorization_metadata_read', 'type': type(error).__name__, 'reason': str(error)})
    try:
        result = bound(request['FP64_summary'])
        complete = bound(request['FP64_COMPLETE'])
        sup = bound(request['FP64_supervisor'])
        need(result['schema'] == 'model_v3_equivariance_v2_FP64_math_v1'
             and str(result['job_id']) == '4524734' and result['status'] == 'PASS' and result['passed'] is True
             and result['relative_tolerance'] == 1e-9 and result['absolute_epsilon'] == 0
             and result['zero_reference_requires_exact_zero_delta'] is True
             and result['counts'] == {'FP32_encoder_forwards': 0, 'cases': 48,
                 'complete_FP64_encoder_forwards': 192, 'errors': 0, 'mathematical_failures': 0, 'passed': 48}
             and complete['summary'] == request['FP64_summary']
             and str(sup['job_id']) == '4524734' and sup['status'] == 'COMPLETED'
             and sup['exit_code'] == 0 and sup['first_failure'] is None and sup['remaining'] == [],
             'Existing4734 mathematical-result/terminal metadata differs')
        evidence['existing_FP64_summary_current_read'] = True
    except Exception as error:
        issues.append({'scope': 'existing_FP64_evidence_read', 'type': type(error).__name__, 'reason': str(error)})
    return {'schema': 'C4_user_v3_decision_v1', 'C4': 'PASS',
        'authority': 'USER_EXPLICIT_V3_AND_ALREADY_COMPLETED_4524734_48_OF48',
        'rule_document': request['rule_document'], 'existing_FP64_summary': request['FP64_summary'],
        'existing_effective_snapshot': snapshot, 'hard_gate': 'FP64 relative error <=1e-9 only',
        'FP32_is_acceptance_gate': False, 'FP32_diagnostic_status': 'NOT_RUN',
        'evidence_current_read': evidence, 'metadata_issues_recorded_nonblocking': issues,
        'old_C4_HOLD_superseded_by_user_v3': True, 'old_v1_v2_preserved_not_rerun': True,
        'compensation': 'STOPPED_NOT_ADOPTED', 'r674': 'LOSS_DISABLED_HEAD_RETAINED_NO_EXTRA_TASK',
        'budget': budget_action(prior_seconds, consecutive_failures),
        'scientific_DECISION_RULES_changed': False, 'TRAIN_only_no_TEST': True,
        'FP32_diagnostic_failure_or_unavailable_does_not_change_C4': True}


def diagnostic_values(actual, reference, *, kind, train_std=None):
    """Pure report math. No tolerance, epsilon or PASS/FAIL returned."""
    import numpy as np
    a = np.asarray(actual, dtype=np.float64)
    y = np.asarray(reference, dtype=np.float64)
    need(a.shape == y.shape and a.size > 0, 'Corresponding nonempty molecular field required')
    finite = np.isfinite(a) & np.isfinite(y)
    nonfinite = int((~finite).sum())
    if kind in ('vector', 'tensor', 'coordinate'):
        if nonfinite:
            return [], {'nonfinite_components': nonfinite, 'undefined_denominator': 0,
                        'unavailable_TRAIN_std': 0, 'norm_delta': None, 'norm_y': None}
        numerator = float(np.linalg.norm((a-y).reshape(-1)))
        denominator = float(np.linalg.norm(y.reshape(-1)))
        if denominator == 0 or not math.isfinite(numerator) or not math.isfinite(denominator):
            return [], {'nonfinite_components': nonfinite, 'undefined_denominator': 1,
                        'unavailable_TRAIN_std': 0, 'norm_delta': numerator if math.isfinite(numerator) else None,
                        'norm_y': denominator if math.isfinite(denominator) else None}
        ratio = numerator / denominator
        return ([ratio] if math.isfinite(ratio) else []), {
            'nonfinite_components': nonfinite + int(not math.isfinite(ratio)), 'undefined_denominator': 0,
            'unavailable_TRAIN_std': 0, 'norm_delta': numerator, 'norm_y': denominator}
    need(kind == 'scalar', 'Only explicit scalar/vector/tensor diagnostic kinds')
    if train_std is None:
        return [], {'nonfinite_components': nonfinite, 'undefined_denominator': 0,
                    'unavailable_TRAIN_std': int(a.size), 'norm_delta': None, 'norm_y': None}
    need(type(train_std) in (int, float) and math.isfinite(train_std) and train_std >= 0,
         'Only an actual finite nonnegative field TRAIN standard deviation may be supplied')
    den = np.abs(y) + train_std
    defined = finite & (den != 0)
    values = np.abs(a[defined]-y[defined]) / den[defined]
    good = np.isfinite(values)
    return values[good].tolist(), {'nonfinite_components': nonfinite + int((~good).sum()),
        'undefined_denominator': int((finite & (den == 0)).sum()), 'unavailable_TRAIN_std': 0,
        'norm_delta': None, 'norm_y': None}


def statistics(values):
    import numpy as np
    if not values:
        return {'defined_values': 0, 'p50': None, 'p99': None, 'max': None}
    x = np.asarray(values, dtype=np.float64)
    need(bool(np.isfinite(x).all()), 'Only defined finite diagnostic values enter quantiles')
    return {'defined_values': len(values), 'p50': float(np.quantile(x, .50, method='linear')),
            'p99': float(np.quantile(x, .99, method='linear')), 'max': float(x.max())}


def archives(raw):
    import numpy as np
    p = Path(raw['path'])
    need(p.is_absolute() and not p.is_symlink() and p.stat().st_uid == 1278 and p.stat().st_nlink == 1
         and p.stat().st_size == raw['bytes'] <= 512 << 10, 'Original bounded owned saved NPZ required')
    before = p.stat()
    need(hashlib.sha256(p.read_bytes()).hexdigest() == raw['sha256'], 'Saved archive binding differs')
    with zipfile.ZipFile(p) as archive:
        entries = archive.infolist()
        need(len(entries) == 52 and all(e.filename.endswith('.npy') and '/' not in e.filename
             and e.file_size <= 2 << 20 for e in entries) and sum(e.file_size for e in entries) <= 2 << 20,
             'Original complete bounded numeric archive required')
    with np.load(p, allow_pickle=False) as archive:
        values = {key: archive[key] for key in archive.files}
    after = p.stat()
    need((before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns),
         'Saved archive changed during diagnostic')
    return values


def row_counts(field, measurement):
    counts = measurement['fixture_native_atoms']
    need(counts == [3, 9, 32], 'Original three-molecule fixture required')
    views = {'two': 2, 'three': 3}[measurement['case']['views']]
    need(measurement['domain']['physical_graph_counts'] == [n for n in counts for _ in range(views)],
         'Original physical-view ordering differs')
    scope = FIELDS[field][1]
    return {'graph': [1, 1, 1], 'clean_atom': counts,
            'clean_bond': [2, 8, 31], 'physical_atom': [n*views for n in counts]}[scope]


def fp32_report(request, output, deadline):
    import numpy as np
    old = bound(request['saved_array_request'])
    entries = [r for r in old['cohorts'] if r['name'] == 'baseline_original1160']
    need(len(entries) == 1 and entries[0]['kind'] == 'fp32_terminals'
         and entries[0]['compensation_history'] is False and entries[0]['job_id'] == '4521160',
         'Only existing uncompensated baseline1160, no compensation history')
    need(request['TRAIN_std_bindings'] is None,
         'Real TRAIN std interface is unavailable; no invented Data statistics schema accepted')
    entry = entries[0]
    expected = set(old['expected_case_ids'])
    need(len(expected) == 48 and len(entry['case_json_paths']) == 48, 'Original complete48 case list required')
    seen = set(); rows = []; grouped = {}; counts = {}
    for path in entry['case_json_paths']:
        need(time.monotonic() < deadline, 'Diagnostic time budget reached; conservative old path continues')
        record = read_json(path); m = record
        for key in entry['measurement_path']:
            m = m[key]
        cid = m['case_id']; need(cid in expected and cid not in seen, 'Exact unique saved baseline case required'); seen.add(cid)
        raw = m['actual_terminal_output_artifact']
        need(raw['contains_native_data'] is False and raw['contains_parameter_weights'] is False,
             'Only saved synthetic terminal outputs')
        values = archives(raw)
        names = {p+'__'+f.replace('/', '__') for p in ('original', 'transform0', 'transform1', 'transform2') for f in FIELDS}
        need(set(values) == set(raw['arrays']) == names and m['complete_terminal_count'] == 13
             and len(m['measurements']) == 3, 'Original52 terminal/13field/3transform coverage differs')
        need(all(a.dtype == np.float32 and a.ndim == 2 and list(a.shape) == raw['arrays'][k]['shape']
                 and raw['arrays'][k]['dtype'] == 'float32' for k, a in values.items())
             and sum(a.nbytes for a in values.values()) <= 320 << 10, 'Original trueF32 shape/header limits differ')
        for ti, transform_record in enumerate(m['measurements']):
            transform = transform_record['transform']
            need(transform['name'] == TRANSFORMS[ti] and transform['row_vector_rule'] == 'x @ R + t', 'Original transform convention differs')
            rotation = np.asarray(transform['rotation_float64'], dtype=np.float64)
            shift = np.asarray(transform['translation_A'], dtype=np.float64)
            fields = {f['field']: f for f in transform_record['fields']}
            need(set(fields) == set(FIELDS), 'All saved fields required')
            for field, (kind, scope) in FIELDS.items():
                base = values['original__'+field.replace('/', '__')].astype(np.float64)
                actual = values['transform'+str(ti)+'__'+field.replace('/', '__')].astype(np.float64)
                law = 'invariant' if kind == 'scalar' else ('coordinate' if kind == 'coordinate' else 'vector')
                need(fields[field]['law'] == law, 'Original field law differs')
                reference = base if law == 'invariant' else base @ rotation
                if law == 'coordinate':
                    reference = reference + shift
                partitions = row_counts(field, m); need(sum(partitions) == actual.shape[0], 'Field molecule partition differs')
                offset = 0
                for molecule, size in enumerate(partitions):
                    block = slice(offset, offset+size); offset += size
                    vals, diagnostic = diagnostic_values(actual[block], reference[block], kind=kind, train_std=None)
                    key = (transform['name'], field)
                    grouped.setdefault(key, []).extend(vals)
                    group_counts = counts.setdefault(key, {'molecule_fields': 0, 'nonfinite_components': 0,
                        'undefined_denominator': 0, 'unavailable_TRAIN_std': 0})
                    group_counts['molecule_fields'] += 1
                    for label in ('nonfinite_components', 'undefined_denominator', 'unavailable_TRAIN_std'):
                        group_counts[label] += diagnostic[label]
                    rows.append({'case_id': cid, 'distance_bias': m['case']['distance_bias'], 'views': m['case']['views'],
                        'head_policy': m['case']['head_policy'], 'weight_seed': m['case']['weight_seed'],
                        'molecule_index': molecule, 'fixture_molecule': MOLECULES[molecule],
                        'transform': transform['name'], 'field': field, 'kind': kind, 'unit': fields[field]['unit'],
                        'diagnostic_definition': 'abs(delta)/(abs(y)+field_TRAIN_std)' if kind == 'scalar' else 'norm(delta)/norm(y)',
                        'scalar_TRAIN_std': None, 'rows_in_molecule_field': size, **statistics(vals), **diagnostic})
    need(seen == expected and len(rows) == 48*3*13*3, 'Full saved molecular-field diagnostic coverage required')
    summary_rows = []
    for key in sorted(grouped):
        summary_rows.append({'transform': key[0], 'field': key[1], **statistics(grouped[key]), **counts[key]})
    for name, table in (('fp32_per_molecule_field.csv', rows), ('fp32_field_summary.csv', summary_rows)):
        with (output/name).open('x', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(table[0])); writer.writeheader(); writer.writerows(table)
    return {'status': 'SAVED_BASELINE_FP32_DIAGNOSTICS_REPORTED', 'baseline_job': '4521160', 'cases': 48,
        'molecule_field_rows': len(rows), 'field_transform_summaries': summary_rows,
        'TRAIN_std': 'UNAVAILABLE_NO_REAL_BOUND_TRAIN_FIELD_STATISTICS', 'FP32_acceptance_verdict': None,
        'compensation_or_model_forward_run': False, 'reference': 'Original base and original saved R64/t64 field law; no new forward/input transform',
        'zero_or_nonfinite_denominators': 'Reported separately and excluded from defined quantiles; no epsilon/scale floor',
        'scalar_population': 'Scalar entries inside each molecule field; no real TRAIN std available so ratios unavailable',
        'vector_population': 'One Frobenius/L2 ratio per original fixture molecule/field, concatenating its original physical views'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--decision-only', action='store_true')
    parser.add_argument('--prior-diagnostic-seconds', type=float)
    parser.add_argument('--consecutive-failures', type=int)
    args = parser.parse_args(); request = read_json(args.request)
    need(request['schema'] == 'C4_user_v3_saved_baseline_diagnostic_request_v1', 'Explicit v3 request required')
    need(args.output.is_absolute() and args.output.is_relative_to(N) and not args.output.exists(), 'Fresh owned output required')
    args.output.mkdir(); started = time.monotonic()
    decision = c4_decision(request, args.prior_diagnostic_seconds, args.consecutive_failures)
    (args.output/'C4_DECISION.json').write_bytes(encoded(decision))
    diagnostics = {'status': 'NOT_RUN_NONBLOCKING', 'reason': 'DECISION_ONLY_OR_DIAGNOSTIC_BUDGET_STOP'}
    if not args.decision_only and decision['budget']['FP32_report_permitted']:
        try:
            need(os.environ.get('SLURM_JOB_ID', '').isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) >= 16
                 and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'Actual CPU>=16 with CUDA hidden required before array open')
            node = socket.gethostname().split('.')[0]
            need(node == os.environ.get('MODEL_V3_EXPECTED_NODE') and re.fullmatch(r'compute-0-(?:2|[89]|1[0-9])', node),
                 'Actual Root-admitted CPU node required')
            need(re.search(r'(?:job[_/-])'+re.escape(os.environ['SLURM_JOB_ID'])+r'(?:/|\n|$)', Path('/proc/self/cgroup').read_text()),
                 'Actual owned CPU job cgroup required')
            deadline = started + min(780, 4*3600-args.prior_diagnostic_seconds)
            diagnostics = fp32_report(request, args.output, deadline)
        except Exception as error:
            diagnostics = {'status': 'UNRESOLVED_CONSERVATIVE_OLD_PATH_CONTINUE', 'type': type(error).__name__,
                'reason': str(error), 'C4_blocked': False, 'no_retry_or_new_candidate_started': True}
    decision['FP32_diagnostic_status'] = diagnostics['status']
    decision['diagnostic_wall_seconds'] = time.monotonic()-started
    (args.output/'C4_DECISION.json').write_bytes(encoded(decision))
    summary = {'schema': 'C4_v3_saved_FP32_report_v1', 'C4': 'PASS', 'decision': decision, 'diagnostics': diagnostics,
        'FP32_PASS_FAIL_issued': False, 'new_forward_or_fit_or_bootstrap': False,
        'old_v1_v2_or_compensation_sources_changed': False, 'r674': 'LOSS_DISABLED_HEAD_RETAINED_NO_EXTRA_TASK',
        'scientific_DECISION_RULES_changed': False, 'TRAIN_only_no_TEST': True}
    raw = encoded(summary)
    need(sum(p.stat().st_size for p in args.output.iterdir())+len(raw) <= MAX_OUTPUT, 'Report output cap exceeded')
    (args.output/'summary.json').write_bytes(raw)
    print(json.dumps({'C4': 'PASS', 'FP32_diagnostic_status': diagnostics['status'], 'output': str(args.output)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
