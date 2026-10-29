"""Saved-metadata-only 10k/20k Native development-panel tables and figures."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re

PROJECT = Path('/share/home/zixiao/descriptor_analysis')
N = PROJECT / 'runs/model_v3_20261026'
MAX_JSON = 2 << 20
MAX_INPUT = 16 << 20
MAX_OUTPUT = 64 << 20
READOUTS = ('ridge', 'linear64_relu')
DATASETS = ('cyp_isoform', 'expansionrx', 'qm9')
TASKS = ('exp.LogD', 'exp.Log_HLM_CLint', 'exp.LogS', 'cyp.3A4', 'cyp.2D6',
         'qm9.U0', 'qm9.homo', 'qm9.lumo', 'qm9.alpha')
PREREG = '39cf4929299cd227a3c361183a4b26c8b1405900'
MANIFEST_KEYS = {'atoms', 'molecules', 'binding', 'packing_plan', 'targets_cached', 'tensor_sha256'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    # Exact original v3_dev_panel cache-key encoding: no added newline.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def ci(value):
    need(type(value) is list and len(value) == 2 and all(finite(x) for x in value)
         and value[0] <= value[1], 'Invalid saved confidence interval')
    return value


class Metadata:
    def __init__(self):
        self.refs = {}
        self.total = 0

    def read(self, ref):
        need(type(ref) is dict and {'path', 'sha256'} <= set(ref), 'Bound metadata rawref required')
        path = Path(ref['path'])
        need(path.is_absolute() and path.suffix == '.json' and path.is_relative_to(PROJECT),
             'Only owned project JSON metadata may be read')
        need(not path.is_symlink() and path.is_file(), 'Metadata file must be ordinary')
        size = path.stat().st_size
        need(size <= MAX_JSON and ('bytes' not in ref or ref['bytes'] == size), 'Metadata size differs')
        if str(path) not in self.refs:
            need(self.total + size <= MAX_INPUT, 'Metadata input limit exceeded')
        raw = path.read_bytes()
        actual = {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        need(actual['sha256'] == ref['sha256'], 'Metadata SHA differs: ' + str(path))
        if str(path) not in self.refs:
            self.total += len(raw)
        self.refs[str(path)] = actual
        return json.loads(raw)

    def after(self):
        for path, ref in self.refs.items():
            p = Path(path)
            need(not p.is_symlink() and p.stat().st_size == ref['bytes']
                 and hashlib.sha256(p.read_bytes()).hexdigest() == ref['sha256'],
                 'Input metadata changed during report: ' + path)
        return list(self.refs.values())


def rows_from_summaries(result, panel):
    # Narrow reuse of make_primary512_report.validate_panel's saved scalar projection.
    # Its old source_training_checkpoint_v1 admission is replaced by the actual Native Root closure.
    summaries = result['summaries']
    need(set(summaries) == {'primary_18_cells', *READOUTS}, 'Three original summaries required')
    cells = {task + '@' + readout for task in TASKS for readout in READOUTS}
    definitions = {task['task_id']: task for task in panel['tasks']}
    rows = []
    for name, summary in summaries.items():
        expected = cells if name == 'primary_18_cells' else {task + '@' + name for task in TASKS}
        need(summary['complete'] is True and set(summary['tasks']) == expected,
             'Complete original task/readout population required')
        need(summary['architecture_sha256'] == result['architecture_sha256']
             and summary['bootstrap_samples'] == summary['bootstrap_defined'] == 1000
             and summary['bootstrap_unit'] == 'molecule'
             and summary['bootstrap_seed'] == panel['uncertainty']['seed'], 'Saved bootstrap differs')
        ci(summary['bootstrap_ci'])
        scores = []
        for cell, item in sorted(summary['tasks'].items()):
            need(all(finite(item[key]) for key in ('error', 'reference_error', 'normalized_improvement')),
                 'Nonfinite saved task scalar')
            need(item['error'] >= 0 and item['reference_error'] > 0
                 and item['bootstrap_defined'] == 1000, 'Unavailable original task result')
            score = (item['reference_error'] - item['error']) / item['reference_error']
            need(math.isclose(score, item['normalized_improvement'], rel_tol=1e-12, abs_tol=1e-12),
                 'Original normalized-improvement identity differs')
            scores.append(score)
            task, readout = cell.split('@')
            need(summaries[readout]['tasks'][cell] == item, 'Primary/separate readout cell differs')
            if name == 'primary_18_cells':
                interval = ci(item['bootstrap_ci'])
                need(all(type(item[k]) is int and item[k] > 0
                         for k in ('observed_labels', 'observed_molecules')), 'Missing observed population')
                rows.append({'task_id': task, 'readout': readout,
                    'error_metric': definitions[task]['error_metric'], 'unit': definitions[task]['unit'],
                    'candidate_error': item['error'], 'random_reference_error': item['reference_error'],
                    'normalized_improvement': item['normalized_improvement'],
                    'ci95_low': interval[0], 'ci95_high': interval[1], 'bootstrap_samples': 1000,
                    'observed_labels': item['observed_labels'], 'observed_molecules': item['observed_molecules']})
        need(math.isclose(sum(scores) / len(scores), summary['mean_normalized_improvement'],
                          rel_tol=1e-12, abs_tol=1e-12), 'Equal-weight mean differs')
    return rows


def read_point(meta, point):
    updates = point['optimizer_updates']
    need(type(updates) is int and updates in (10000, 20000), 'Only actual two endpoints are in scope')
    root = meta.read(point['Root_closure'])
    need(root['schema'] == 'model_v3_Native_S' + str(updates) + '_panel_GPU_Root_metadata_closure_v1'
         and root['status'] == 'ACTUAL_GPU_C0_NATIVE' + str(updates)
             + '_FULL9_18CELL_H0_SOURCE_RESOURCE_CLOSED_SDK_PENDING', 'Actual completed Native Root closure required')
    need(root['Native_endpoint']['optimizer_updates'] == updates
         and root['Native_endpoint']['seed'] == 0 and root['Native_endpoint']['precision'] == 'fp32',
         'Wrong Native endpoint')
    need(root['D5_or_B_acceptance'] is False and root['pretraining_seed_SD_claimed'] is False,
         'Unexpected authority scope')
    result = meta.read(root['result'])
    request = meta.read(root['request'])
    panel = meta.read(request['panel'])
    need(result['schema'] == 'model_v3_dev_evaluation_result_v1' and result['status'] == 'COMPLETED'
         and result['job_id'] == root['job_id']
         and result['request_sha256'] == root['request']['sha256'], 'Result/Root/request differs')
    need(result['panel_sha256'] == request['panel']['sha256']
         and result['preregistration_sha'] == request['preregistration_sha'] == PREREG,
         'Frozen panel/preregistration differs')
    need(len(panel['tasks']) == 9 and {t['task_id'] for t in panel['tasks']} == set(TASKS)
         and set(panel['readouts']) == {*READOUTS, 'pooling_note'}, 'Original nine-task/two-readout definition differs')
    uncertainty = panel['uncertainty']
    need(uncertainty['bootstrap_samples'] == 1000 and uncertainty['confidence'] == .95
         and uncertainty['paired'] is True
         and uncertainty['same_draw_across_tasks_and_readouts_within_dataset'] is True,
         'Original bootstrap method differs')
    need(panel['readouts']['linear64_relu']['epochs'] == 20
         and panel['readouts']['linear64_relu']['batch_graphs'] == 32, 'Readout recipe differs')
    pair = result['encoder_pair']
    need(pair['checkpoint_schema'] == 'model_v3_native_S_immutable_checkpoint'
         and pair['H0_dimension'] == 512 and pair['pretraining_seed'] == result['pretraining_seed'] == 0
         and pair['random_reference_seed'] == result['random_reference_initialization_seed'] == 20261025
         and result['readout_seed'] == panel['readouts']['linear64_relu']['seed'] == 0
         and pair['architecture_sha256'] == result['architecture_sha256'] == request['architecture_sha256'],
         'H0/architecture/seed identity differs')
    need(pair['checkpoint'] == request['checkpoint']
         and pair['original_configuration'] == request['model_configuration'], 'Checkpoint/configuration differs')
    caches = result['h0_caches']
    need(set(caches) == {label + '/' + dataset for label in ('candidate', 'reference') for dataset in DATASETS},
         'Exactly six original caches required')
    populations = {}
    for dataset in DATASETS:
        left, right = (caches[label + '/' + dataset] for label in ('candidate', 'reference'))
        for key in ('architecture_sha256', 'membership_sha256', 'geometry_sha256', 'dimension',
                    'packing_budget_sha256', 'packing_plan_sha256', 'effective_runtime_sha256'):
            need(left['binding'][key] == right['binding'][key], 'Candidate/reference cache binding differs')
        for key in ('atoms', 'molecules', 'unavailable_geometry_records'):
            need(left[key] == right[key], 'Candidate/reference geometry population differs')
        closed = root['panel']['matched_caches']
        for label, cache in (('candidate', left), ('reference', right)):
            binding = cache['binding']
            key = label + '/' + dataset
            need(cache['cache_key'] == digest(binding), 'Original H0 cache-key rule differs')
            need(Path(cache['manifest']) == Path(request['cache_root']) / cache['cache_key'] / 'manifest.json',
                 'Original cache manifest path differs')
            manifest_ref = closed[key]['manifest']
            need(manifest_ref['path'] == cache['manifest'], 'Root manifest binding differs')
            manifest = meta.read(manifest_ref)
            need(set(manifest) == MANIFEST_KEYS and all(manifest[k] == cache[k] for k in MANIFEST_KEYS),
                 'Six manifest/result fields differ')
            need(binding['dimension'] == 512 and cache['targets_cached'] is False
                 and binding['architecture_sha256'] == result['architecture_sha256']
                 and binding['membership_sha256'] == result['membership_sha256'][dataset]
                 and binding['packing_plan_sha256'] == result['h0_packing_plan_sha256'][dataset]
                 and binding['packing_budget_sha256'] == result['h0_packing_budget_sha256']
                 and binding['effective_runtime_sha256'] == result['h0_effective_runtime_sha256'],
                 'H0 cache/result identity differs')
            expected_encoder = pair['checkpoint_encoder_state_sha256'] if label == 'candidate' else pair['random_encoder_state_sha256']
            need(binding['encoder_sha256'] == expected_encoder, 'Encoder state binding differs')
            need(closed[key]['cache_key'] == cache['cache_key']
                 and closed[key]['producer_tensor_sha256'] == cache['tensor_sha256'], 'Root producer H0 identity differs')
        populations[dataset] = {'molecules': left['molecules'], 'atoms': left['atoms'],
            'unavailable_geometry_records': left['unavailable_geometry_records'],
            'geometry_sha256': left['binding']['geometry_sha256'],
            'membership_sha256': left['binding']['membership_sha256'],
            'packing_plan_sha256': left['binding']['packing_plan_sha256'],
            'record_order_sha256': left['packing_plan']['record_order_sha256']}
    rows = rows_from_summaries(result, panel)
    for row in rows:
        row.update(optimizer_updates=updates, samples_consumed=root['Native_endpoint']['samples_consumed'],
                   pretraining_seed=0, pretraining_precision='fp32', evaluation_job_id=root['job_id'])
        for label in ('candidate', 'reference'):
            detail = result['probe_details'][label + '/' + row['task_id'] + '@' + row['readout']]
            need(detail['normalization_fit_scope'] == 'train', 'Readout normalization scope differs')
            if row['readout'] == 'ridge':
                need(detail['fit_scope'] == 'train' and detail['validation_role'] == 'train_inner_validation',
                     'Original TRAIN/inner-validation scope differs')
            else:
                need(detail['encoder_updated'] is False and detail['epochs'] == 20 and detail['batch_graphs'] == 32,
                     'Original frozen encoder/readout recipe differs')
    return {'root': root, 'result': result, 'request': request, 'panel': panel,
            'rows': rows, 'populations': populations}


def compare(left, right):
    a, b = left['result'], right['result']
    for key in ('code_sha', 'data_version', 'architecture_sha256', 'panel_sha256', 'preregistration_sha',
                'pretraining_seed', 'readout_seed', 'random_reference_initialization_seed', 'membership_sha256',
                'training_store_sha256', 'h0_effective_runtime_sha256', 'h0_packing_budget_sha256', 'h0_packing_plan_sha256'):
        need(a[key] == b[key], 'Cross-endpoint comparison identity differs: ' + key)
    need(left['panel'] == right['panel'] and left['populations'] == right['populations'],
         'Frozen panel or effective geometry population differs across endpoints')
    need(a['encoder_pair']['random_encoder_state_sha256'] == b['encoder_pair']['random_encoder_state_sha256'],
         'Matched random initialization differs')
    ma = {(r['task_id'], r['readout']): r for r in left['rows']}
    mb = {(r['task_id'], r['readout']): r for r in right['rows']}
    deltas = []
    for key, x in ma.items():
        y = mb[key]
        need(all(x[k] == y[k] for k in ('unit', 'error_metric', 'observed_labels', 'observed_molecules')),
             'Task metric or observed population differs across endpoints')
        # These are descriptive differences of saved estimates. No delta CI is inferred.
        deltas.append({'task_id': key[0], 'readout': key[1], 'error_metric': x['error_metric'], 'unit': x['unit'],
            'error_10000': x['candidate_error'], 'error_20000': y['candidate_error'],
            'error_delta_20000_minus_10000': y['candidate_error'] - x['candidate_error'],
            'normalized_improvement_10000': x['normalized_improvement'],
            'normalized_improvement_20000': y['normalized_improvement'],
            'normalized_improvement_delta': y['normalized_improvement'] - x['normalized_improvement'],
            'random_reference_error_10000': x['random_reference_error'],
            'random_reference_error_20000': y['random_reference_error'], 'delta_CI_available': False,
            'observed_labels': x['observed_labels'], 'observed_molecules': x['observed_molecules']})
    return deltas


def write_csv(path, rows):
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plots(output, rows, panel):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import ScalarFormatter
    styles = {'ridge': ('#1764ab', 'o'), 'linear64_relu': ('#d36500', 's')}
    definitions = {t['task_id']: t for t in panel['tasks']}
    for mode in ('raw_error', 'normalized_improvement'):
        fig, axes = plt.subplots(3, 3, figsize=(12, 9), constrained_layout=False)
        for ax, task in zip(axes.flat, TASKS):
            for readout in READOUTS:
                group = sorted((r for r in rows if r['task_id'] == task and r['readout'] == readout),
                               key=lambda r: r['optimizer_updates'])
                x = [r['optimizer_updates'] for r in group]
                color, marker = styles[readout]
                if mode == 'raw_error':
                    y = [r['candidate_error'] for r in group]
                else:
                    y = [r['normalized_improvement'] for r in group]
                    # Stored intervals may not contain the point estimate; do not coerce yerr >= 0.
                    ax.vlines(x, [r['ci95_low'] for r in group], [r['ci95_high'] for r in group],
                              color=color, linewidth=1.2, alpha=.7)
                ax.plot(x, y, marker=marker, color=color, label=readout, linewidth=1.4, markersize=4)
            ax.set_title(task, fontsize=10)
            ax.set_xticks([10000, 20000], ['10k', '20k'])
            ax.set_xlim(8500, 21500)
            ax.set_xlabel('Native optimizer updates; seed 0 FP32', fontsize=8)
            if mode == 'raw_error':
                ax.set_ylabel(definitions[task]['error_metric'] + ' [' + definitions[task]['unit'] + ']', fontsize=8)
                formatter = ScalarFormatter(useOffset=False)
                formatter.set_powerlimits((-3, 3))
                ax.yaxis.set_major_formatter(formatter)
            else:
                ax.set_ylabel('Improvement vs matched random', fontsize=8)
                ax.axhline(0, color='0.55', linewidth=.7)
            ax.tick_params(labelsize=8)
            ax.grid(alpha=.2)
        handles, labels = axes.flat[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.5, .01), ncol=2, frameon=False)
        subtitle = ('Saved candidate errors; lower is better. No raw-error CI was saved.' if mode == 'raw_error'
                    else 'Saved endpoint estimates and original paired-molecule 95% CIs (1000 draws). No CI for endpoint change.')
        fig.suptitle('Native S, seed 0 FP32: 10k to 20k development panel\n' + subtitle, fontsize=11)
        fig.tight_layout(rect=(0, .085, 1, .91))
        for suffix in ('png', 'pdf'):
            fig.savefig(output / (mode + '.' + suffix), dpi=180, bbox_inches='tight')
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    need(args.output.is_absolute() and args.output.is_relative_to(N) and not args.output.exists(),
         'Fresh owned N output required')
    args.output.mkdir()
    meta = Metadata()
    try:
        need(args.inputs.is_absolute() and args.inputs.is_relative_to(N) and args.inputs.suffix == '.json'
             and not args.inputs.is_symlink() and args.inputs.stat().st_size <= MAX_JSON,
             'Bound owned input request JSON required')
        own_source = Path(__file__).absolute()
        source_raw = own_source.read_bytes()
        source_ref = {'path': str(own_source), 'bytes': len(source_raw), 'sha256': hashlib.sha256(source_raw).hexdigest()}
        raw = args.inputs.read_bytes()
        need(len(raw) <= MAX_JSON, 'Input request too large')
        inputs_ref = {'path': str(args.inputs.absolute()), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        inputs = meta.read(inputs_ref)
        need(inputs['schema'] == 'native_S10k20k_saved_panel_report_inputs_v1'
             and [p['optimizer_updates'] for p in inputs['points']] == [10000, 20000], 'Report request scope differs')
        points = [read_point(meta, p) for p in inputs['points']]
        deltas = compare(*points)
        rows = points[0]['rows'] + points[1]['rows']
        need(len(rows) == 36 and len(deltas) == 18, 'Complete 2 x 9 x 2 cells required')
        aggregate = []
        for point in points:
            for name, item in point['result']['summaries'].items():
                aggregate.append({'optimizer_updates': point['root']['Native_endpoint']['optimizer_updates'],
                    'summary': name, 'cells': len(item['tasks']),
                    'mean_normalized_improvement': item['mean_normalized_improvement'],
                    'ci95_low': item['bootstrap_ci'][0], 'ci95_high': item['bootstrap_ci'][1], 'bootstrap_samples': 1000})
        write_csv(args.output / 'task_metrics.csv', rows)
        write_csv(args.output / 'task_changes.csv', deltas)
        write_csv(args.output / 'aggregate_metrics.csv', aggregate)
        plots(args.output, rows, points[0]['panel'])
        refs = meta.after()
        need(own_source.read_bytes() == source_raw, 'Report driver changed during execution')
        output_files = []
        for path in sorted(args.output.iterdir()):
            need(path.is_file() and not path.is_symlink(), 'Unexpected report output entry')
            raw = path.read_bytes()
            output_files.append({'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        need(sum(r['bytes'] for r in output_files) < MAX_OUTPUT, 'Report output limit exceeded')
        reference_differences = [r['task_id'] + '@' + r['readout'] for r in deltas
            if r['random_reference_error_10000'] != r['random_reference_error_20000']]
        summary = {'schema': 'native_S10k20k_saved_panel_report_v1', 'status': 'SAVED_36_CELLS_REPORTED_NO_REFIT',
            'input_metadata_refs_before_and_after_equal': refs, 'input_bytes': meta.total,
            'report_driver_before_after_equal': source_ref,
            'output_files': output_files, 'task_metrics': rows, 'task_changes': deltas, 'aggregate_metrics': aggregate,
            'geometry_population': points[0]['populations'], 'bootstrap_intervals': 'Copied original endpoint 1000-draw paired-molecule 95% intervals; no new draws',
            'matched_random_encoder_state_sha256': points[0]['result']['encoder_pair']['random_encoder_state_sha256'],
            'reference_error_differences_between_saved_evaluations': reference_differences,
            'extra_zero_update_random_anchor_added': False, 'delta_confidence_interval_claimed': False,
            'interpretation': 'Two descriptive development endpoints only; one pretraining seed FP32, not formal D5/B*/bf16/seed-SD acceptance',
            'model_or_readout_fit_or_bootstrap_or_tensor_payload_opened': False,
            'SDK_or_step_or_resource_journal_opened': False, 'input_limit_bytes': MAX_INPUT,
            'output_limit_bytes': MAX_OUTPUT, 'scientific_acceptance': False}
        encoded = (json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
        need(sum(r['bytes'] for r in output_files) + len(encoded) <= MAX_OUTPUT, 'Summary exceeds report output limit')
        (args.output / 'summary.json').write_bytes(encoded)
        print(json.dumps({'status': summary['status'], 'output': str(args.output), 'rows': len(rows), 'deltas': len(deltas)}))
    except Exception as exc:
        failure = {'status': 'REPORT_FAILED', 'type': type(exc).__name__, 'reason': str(exc),
                   'model_or_SDK_payload_opened': False}
        (args.output / 'FAILURE.json').write_text(json.dumps(failure, indent=2) + '\n', encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
