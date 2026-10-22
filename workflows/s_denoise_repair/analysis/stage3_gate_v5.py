"""Stage-3 measurements and strict guide gates. Does not submit training."""
from __future__ import annotations
import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
GUIDE_SHA = '240b7b8132603517a7640662a5ea75e67371d5633e8a3c723ab148174c0b8fa3'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Missing or nonfinite scientific measurement')
    if positive and value <= 0:
        raise ValueError('Expected positive scientific measurement')
    return float(value)


def estimate_cost(result, curve, elapsed, estimator):
    rate = finite(result['training_records_per_second'], positive=True)
    records = {int(row['evaluation_records']) for row in curve}
    if len(records) != 1 or records != {18486} or len(curve) != 9:
        raise ValueError('Expected all nine common FULL2000 evaluations')
    if [row['optimizer_update'] for row in curve] != list(range(0, 4001, 500)):
        raise ValueError('Unmatched evaluation endpoints')
    validation = sum(finite(row['evaluation_wall_seconds'], positive=True) for row in curve)
    training = finite(result['training_seconds_including_loader'], positive=True)
    all_saves = finite(result['checkpoint_all_save_readback_seconds'])
    single_save = finite(result['checkpoint_save_readback_seconds'], positive=True)
    if elapsed + 1 < training + validation + all_saves:
        raise ValueError('Parent allocation shorter than its measured components')
    startup_close = max(0.0, elapsed - training - validation - all_saves)
    train = estimator['train_records'] / rate
    val = (estimator['FULL_plus_routine_validation_events_per_epoch_upper_reference']
           * (estimator['FULL_records'] + estimator['routine_records']) / 18486 * validation / len(curve))
    saves = estimator['checkpoint_save_readback_events_per_epoch_reference'] * single_save
    segments = math.ceil((train + val) / estimator['usable_training_segment_seconds'])
    return dict(estimated_GPU_hours=(train + val + saves + segments * startup_close) / 3600,
                estimated_train_seconds=train, estimated_validation_seconds=val,
                estimated_checkpoint_seconds=saves, measured_startup_close_seconds=startup_close,
                estimated_segments=segments, actual_D3_parent_elapsed_seconds=elapsed,
                GPU_model=result['runtime']['gpu_model'], records_per_second=rate,
                peak_allocated_bytes=result['gpu_peak_allocated_bytes'],
                peak_reserved_bytes=result['gpu_peak_reserved_bytes'])


def denoise_fraction(result):
    rows = result['final_gradient_rows']
    if len(rows) != 20 or [row['optimizer_update'] for row in rows] != list(range(3980, 4000)):
        raise ValueError('Expected exact final20 TRAIN gradient observations')
    values = []
    for row in rows:
        d = row['diagnostics']
        if set(d['norms']) != {'element', 'denoise_eps_mse', 'bond_order'}:
            raise ValueError('Expected three shared-backbone tasks')
        fractions = d['fractions_of_sum_of_norms']
        if abs(sum(finite(v) for v in fractions.values()) - 1) > 1e-5:
            raise ValueError('Invalid gradient fraction normalization')
        values.append(finite(fractions['denoise_eps_mse']))
    return math.fsum(values) / len(values)


def judge(seeds, lookup_subset):
    lookup_subset = finite(lookup_subset, positive=True)
    measurements = []
    for seed in [0, 1]:
        item = seeds[seed]
        multi, single, baseline = item['multitask'], item['denoise_only'], item['A0']
        rmse = finite(multi['final']['local_rmse_A'], positive=True)
        single_rmse = finite(single['final']['local_rmse_A'], positive=True)
        fraction = denoise_fraction(multi)
        interference = float(abs(Decimal(str(single_rmse)) - Decimal(str(rmse))) / Decimal(str(rmse)))
        element_delta = finite(multi['final']['masked_element_accuracy']) - finite(baseline['final']['masked_element_accuracy'])
        bond_delta = finite(multi['final']['bond_order_accuracy']) - finite(baseline['final']['bond_order_accuracy'])
        cost = finite(item['cost']['estimated_GPU_hours'], positive=True)
        measurements.append(dict(seed=seed, local_rmse_A=rmse, lookup_FULL2000_RMSE_A=lookup_subset,
            below_historical_0_042_A=rmse < .042, gradient_fraction=fraction,
            A5_local_rmse_A=single_rmse, interference_relative_gap=interference,
            masked_element_accuracy_delta_vs_matched_A0=element_delta,
            bond_accuracy_delta_vs_matched_A0=bond_delta, **item['cost']))
    gates = dict(denoising=all(m['local_rmse_A'] < lookup_subset for m in measurements),
                 gradient=all(m['gradient_fraction'] >= .10 for m in measurements),
                 interference=all(m['interference_relative_gap'] <= .10 for m in measurements),
                 other_tasks=all(m['masked_element_accuracy_delta_vs_matched_A0'] >= 0 and m['bond_accuracy_delta_vs_matched_A0'] >= 0 for m in measurements),
                 cost=all(m['estimated_GPU_hours'] <= 15 for m in measurements))
    return dict(status='ALL_STAGE3_GATES_PASS' if all(gates.values()) else 'STAGE3_GATES_NOT_ALL_PASSED',
                gates=gates, measurements=measurements, formal_training_authorized_by_gate=all(gates.values()))


def query_parents(job_ids, snapshot):
    snapshot=Path(snapshot)
    if not snapshot.is_absolute() or not snapshot.is_relative_to(ROOT/'control/accounting_snapshots'):
        raise ValueError('Actual parent snapshot outside task')
    document=json.loads(snapshot.read_text())
    if (document['status']!='ACTUAL_SONMI_SACCT_SNAPSHOT' or document['host'].split('.')[0]!='sonmi'
            or document['uid']!=1278 or document['columns']!=['State','ExitCode','ElapsedRaw','AllocCPUS']):
        raise ValueError('Unverified actual accounting origin')
    raw={r[0]:r[1:] for r in (line.split('|') for line in document['raw_stdout'].splitlines()) if r[0] in job_ids}
    rows=document['rows']
    for job in job_ids:
        if job not in rows or raw.get(job)!=rows[job] or rows[job][:2]!=['COMPLETED','0:0']:
            raise ValueError('Scientific parent not actually COMPLETED/0: '+job)
        if len(rows[job])!=4 or int(rows[job][2])<0 or int(rows[job][3])<1:
            raise ValueError('Invalid actual allocation metrics')
    return {job:rows[job] for job in job_ids}


def read_ref(ref, inputs):
    pointer = json.loads(ref.read_text())
    path = Path(pointer['path'])
    if ROOT not in path.parents or sha(path) != pointer['sha256']:
        raise ValueError('Invalid result reference: ' + str(ref))
    inputs.append(dict(path=str(path), sha256=sha(path)))
    return json.loads(path.read_text()), path


def lookup_provenance(closure_path, lookup, lookup_path):
    closure_path=Path(closure_path)
    if not closure_path.is_absolute() or not closure_path.is_relative_to(ROOT/'configs'):
        raise ValueError('Lookup closure outside this task')
    closure=json.loads(closure_path.read_text())
    if (closure['status']!='ACTUAL_FULL_TRAIN_LOOKUP_REFIT_CLOSED' or closure['guide_sha256']!=GUIDE_SHA
        or closure['TRAIN_records']!=11104772 or closure['metrics']!=lookup['metrics']):
        raise ValueError('Lookup result and actual closure differ')
    result_ref=closure['result_reference']
    if result_ref['path']!=str(lookup_path) or result_ref['sha256']!=sha(lookup_path):
        raise ValueError('Lookup closure points to another result')
    snapshot_ref=closure['actual_parent_snapshot']
    if sha(snapshot_ref['path'])!=snapshot_ref['sha256']:
        raise ValueError('Lookup accounting snapshot changed')
    job=str(closure['job_id'])
    if not job.isdecimal():raise ValueError('Invalid lookup parent')
    actual=query_parents({job},snapshot_ref['path'])
    if actual[job]!=closure['actual_parent']:
        raise ValueError('Lookup parent projection differs')
    evidence=[dict(path=str(closure_path),sha256=sha(closure_path)),snapshot_ref]
    for item in closure['canonical_recipe_sources']+closure['output_references']:
        if sha(item['path'])!=item['sha256']:
            raise ValueError('Pinned lookup recipe or result changed')
        evidence.append(item)
    return job,evidence


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', required=True)
    parser.add_argument('--source-binding',type=Path,default=ROOT/'configs/D3_source_binding_v4.json')
    parser.add_argument('--lookup-closure',type=Path,default=ROOT/'configs/lookup_refit_closure_v1.json')
    parser.add_argument('--baseline-phase', default='d3_local_blocks_v1',
                        help='Phase ledger containing the original matched A0 seeds')
    parser.add_argument('--parent-snapshot', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    return parser.parse_args(argv)


def main():
    args = parse_args()
    if sha(ROOT / 'user_repair_guide.md') != GUIDE_SHA:
        raise ValueError('Guide changed')
    if (ROOT / 'GUIDE_STOP.json').exists():
        raise ValueError('Guide stop marker exists')
    control = ROOT / 'control' / args.phase
    status = json.loads((control / 'status.json').read_text())
    if status['status'] != 'D3_PHASE_COMPLETE_AWAITING_SCIENTIFIC_GATE':
        raise ValueError('D3 phase incomplete')
    selection = json.loads((control / 'LR_selection.json').read_text())
    selected = selection['selected']
    jobs = json.loads((control / 'jobs.json').read_text())
    baseline_jobs=json.loads((ROOT/'control'/args.baseline_phase/'jobs.json').read_text())
    for seed in [0,1]:
        key='A0_seed'+str(seed)
        if key not in jobs:jobs[key]=baseline_jobs[key]
    tasks = json.loads((control / 'tasks.json').read_text())
    a5 = next(name for name, seed in tasks if name not in selection['scores'] and name not in ['A0', 'A1'])
    required = sorted(set([selected, a5, 'A0']))
    inputs = []
    lookup, lookup_path = read_ref(ROOT / 'reports/lookup_latest.json', inputs)
    if lookup['status'] != 'NEW_TRAIN_LOOKUP_REFIT_AND_FULL_EVALUATION_COMPLETE' or lookup['TRAIN_records'] != 11104772 or lookup['validation_values_used_for_fit']:
        raise ValueError('Invalid new-population TRAIN-only lookup refit')
    if lookup['metrics']['full']['records'] != 127082 or lookup['metrics']['D3_FULL2000']['records'] != 18486:
        raise ValueError('Lookup validation coverage differs')
    lookup_job,lookup_evidence=lookup_provenance(args.lookup_closure,lookup,lookup_path)
    inputs.extend(lookup_evidence)
    binding = json.loads(args.source_binding.read_text())
    test_jobs = {item['job_id'] for item in binding['C6_actual_job_closure'].values()}
    parent_rows = query_parents({entry['job_id'] for entry in jobs.values()} | test_jobs | {lookup_job},args.parent_snapshot)
    inputs.append(dict(path=str(args.parent_snapshot),sha256=sha(args.parent_snapshot)))
    estimator_path = ROOT / 'configs/cost_estimator_v2.json'
    estimator = json.loads(estimator_path.read_text())
    results, paths = {}, {}
    for name in required:
        for seed in [0, 1]:
            key = name + '_seed' + str(seed)
            result, path = read_ref(ROOT / 'reports' / (key + '_latest.json'), inputs)
            entry = jobs[key]
            if result['status'] != 'D3_CONDITION_COMPLETE' or result['optimizer_updates'] != 4000:
                raise ValueError('Partial condition: ' + key)
            if result['condition'] != name or result['seed'] != seed or result['runtime']['job_id'] != entry['job_id']:
                raise ValueError('Condition identity mismatch: ' + key)
            if sha(entry['configuration']) != entry['configuration_sha256'] or result['configuration_sha256'] != entry['configuration_sha256']:
                raise ValueError('Configuration mismatch: ' + key)
            results[key], paths[key] = result, path
    seeds = {}
    for seed in [0, 1]:
        key = selected + '_seed' + str(seed)
        result = results[key]
        curve_path = paths[key].with_name('curve.json')
        inputs.append(dict(path=str(curve_path), sha256=sha(curve_path)))
        cost = estimate_cost(result, json.loads(curve_path.read_text()), int(parent_rows[jobs[key]['job_id']][2]), estimator)
        baseline = results['A0_seed' + str(seed)]
        same_hardware = result['runtime']['gpu_model'] == baseline['runtime']['gpu_model']
        cost.update(A0_GPU_model=baseline['runtime']['gpu_model'], hardware_matched_to_A0=same_hardware,
                    throughput_fraction_vs_matched_A0=result['training_records_per_second'] / baseline['training_records_per_second'] if same_hardware else None,
                    peak_allocated_delta_bytes_vs_matched_A0=result['gpu_peak_allocated_bytes'] - baseline['gpu_peak_allocated_bytes'] if same_hardware else None,
                    peak_reserved_delta_bytes_vs_matched_A0=result['gpu_peak_reserved_bytes'] - baseline['gpu_peak_reserved_bytes'] if same_hardware else None)
        seeds[seed] = dict(multitask=result, denoise_only=results[a5 + '_seed' + str(seed)], A0=baseline, cost=cost)
    report = judge(seeds, lookup['metrics']['D3_FULL2000']['lookup_rmse_A'])
    report.update(selected=selected, A5=a5, phase=args.phase, scientific_inputs=inputs, actual_parents=parent_rows,
                  lookup_FULL_RMSE_A=lookup['metrics']['full']['lookup_rmse_A'], historical_reference_A=.042,
                  cost_estimator=dict(path=str(estimator_path), sha256=sha(estimator_path)),
                  guide_sha256=GUIDE_SHA, source_binding=dict(path=str(args.source_binding), sha256=sha(args.source_binding)),
                  scientific_scope='D3 only; no claim of full-epoch training or downstream convergence')
    binding = json.loads(args.source_binding.read_text())
    for item in binding['files']:
        if sha(item['path']) != item['sha256']:
            raise ValueError('Frozen active source changed')
    if ROOT not in args.output.parents:
        raise ValueError('Output outside task')
    with args.output.open('x') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=report['status'], selected=selected, gates=report['gates']), ensure_ascii=False))


if __name__ == '__main__':
    main()
