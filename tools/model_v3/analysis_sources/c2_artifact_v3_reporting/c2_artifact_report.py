"""C2 baseline-v2 / loader-v3 aggregate report: true C0 and verified native SDK."""
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path
import time

import c2_artifact_schema as schema
import c2_native_sdk as native

SUCCESS = 'VERIFIED_ANALYSIS_ONLY_NOT_MODEL_SELECTION'


def markdown(report):
    m, zero, verification = report['metrics'], report['derived_zero_baseline'], report['independent_native_SDK']
    fmt = lambda value: 'N/A (P=0)' if value is None else format(value, '.9g')
    lines = ['# C2 baseline v2, artifact loader v3: first fixed PRETRAIN_VAL analysis', '',
        f"Actual current job {report['actual_job_id']}: Slurm C0, fixed CPU supervisor closed, independent native SDK VERIFIED.",
        'Analysis only; no model selection gate or new metric acceptance threshold.', '',
        'Parameter estimation belongs to prior TRAIN diagnostic job 4520559: 8,192 records, 436,120 atoms. '
        'The current job loads that accepted artifact, performs no parameter estimation, reads zero native TRAIN geometries, '
        'and evaluates exactly 1,024 original existing-S PRETRAIN_VAL records. Records are not molecule-uniform samples or a new D-5 split.', '',
        'Target epsilon = y - x (Angstrom displacement); predicted clean coordinates = y - predicted epsilon. '
        'Noisy-distance <5 Angstrom features use 0.1 Angstrom bins; the TRAIN objective has ridge=1e-4. '
        'Unknown bins receive zero correction while every atom/pair remains in its original denominator. '
        'Local pairs are unique upper-triangle clean-distance <2 Angstrom pairs computed from the same predicted clean coordinates.', '',
        '| Original metric | Value | Unit | Original denominator / definition |',
        '|---|---:|---|---|']
    for key, value in m.items():
        definition = report['metric_units_and_denominators'][key]
        lines.append(f"| `{key}` | {fmt(value)} | {definition['unit']} | {definition['denominator']} |")
    lines += ['', '| Original core role / flag / aggregate membership hash | Value |', '|---|---|']
    for key, value in report['core_metric_metadata'].items(): lines.append(f'| `{key}` | `{value}` |')
    lines += ['', '| Display comparison | Fitted artifact | Zero correction (noisy identity) | Unit |',
        '|---|---:|---:|---|']
    for key in ('coordinate_vector_RMSE_A', 'coordinate_component_RMSE_A', 'explicit_sigma_normalized_component_MSE'):
        unit = 'dimensionless' if key.endswith('MSE') else 'Angstrom'
        lines.append(f'| `{key}` | {fmt(m[key])} | {fmt(zero[key])} | {unit} |')
    lines += [f"| `local_pair_RMSE_A` | {fmt(m['local_pair_RMSE_A'])} | {fmt(m['noisy_identity_local_pair_RMSE_A'])} | Angstrom |", '',
        'Zero coordinate vector/component RMSE and sigma-normalized MSE above are algebraically derived from the saved '
        'noisy_identity_vector_MSE_A2; they are not new evaluations. No confidence interval or seed variance is inferred. '
        'The old approximately 0.0413 Angstrom pair-distance result is not a coordinate RMSE comparison.', '',
        '![C2 metrics in separate physical units](metrics.png)', '',
        'Solver and objective diagnostics below are copied from bound prior TRAIN outputs, never recomputed here. '
        'The active/Jacobi explicit augmented LSQR uses damp=0, atol=btol=1e-8, iteration cap=2000, condition limit=1e8, '
        'one BLAS thread and no warm start. KKT has no acceptance threshold.', '',
        '| Prior solver statistic | Value |', '|---|---:|']
    for key, value in report['prior_solver_statistics'].items(): lines.append(f'| `{key}` | `{value}` |')
    lines += ['', '| Prior original-coordinate diagnostic | Value |', '|---|---:|']
    for key, value in report['prior_original_coordinate_diagnostics'].items(): lines.append(f'| `{key}` | `{value}` |')
    lines += ['', f"Prior TRAIN job elapsed: {report['prior_TRAIN_job_elapsed_seconds']} s; current VAL-only allocation: {report['current_job_elapsed_seconds']} s. "
        f"Current process peak RSS: {report['current_job_resources']['process_peak_RSS_bytes']} bytes; recorded inner wall: {report['current_job_resources']['wall_seconds']:.6g} s.", '',
        f"Offline W&B run `{report['run_id']}`: exactly two committed history rows, steps 0/1, {verification['native_records']} total native records, "
        'all public fields/config/final summary exact, clean EOF and native exit0. Expected rows are code-derived from the fixed '
        'logger source plus saved outputs; there is no mirrored history file. Native SDK originals remain unchanged; no online sync is claimed.', '',
        'Original job 4520482 remains FAILED; its original stop code/iteration count is not inferred from the later diagnostic. '
        'Artifact-loader v2 job 4520595 failed before native geometry access; the v3 registration-chain correction preserves the objective/evaluator/logger. '
        'This tool parses bounded model-owned result/closure/plan metadata (including identities already in those files), '
        'then exports only allowlisted aggregates, units, counts and source hashes. It opens no lookup/NPZ/native geometry store and '
        'exports no identities, weights, coordinates or predictions.', '',
        'CSV denoise_rmse means coordinate_component_RMSE_A; code_sha/preregistration_sha identify the publicly adopted artifact runtime protocol. '
        'Its complete executed source inventory is separately byte-bound. Hashes and input/output source manifest are in report.json / REPORT_COMPLETE.json.', '']
    mapping = report['diagnostic_registration_mapping']
    lines += ['## Diagnostic publication mapping', '',
        f"Executed local diagnostic commit: `{mapping['executed_local_protocol_registration']['commit']}`; "
        f"public diagnostic commit: `{mapping['public_registration']['commit']}`. "
        f"Producer-verified common tree: `{mapping['verified_local_tree']}`; protocol raw SHA: `{mapping['verified_protocol_blob_raw_sha256']}`. "
        'This reporter independently matches the complete model-owned prior input/binding/mapping metadata chain. '
        'The pinned v3 producer performed the actual Git blob/method/source/tree checks; the reporter does not re-run Git or infer commit equality.', '']
    return '\n'.join(lines)


def draw(report, output):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    import numpy as np
    m, zero = report['metrics'], report['derived_zero_baseline']
    with plt.rc_context({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False}):
        fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), constrained_layout=True)
        x = np.arange(2); width = .34
        for offset, label, values, color in ((-width/2, 'Fitted artifact', [m['coordinate_vector_RMSE_A'], m['coordinate_component_RMSE_A']], '#2878a1'),
                (width/2, 'Zero correction', [zero['coordinate_vector_RMSE_A'], zero['coordinate_component_RMSE_A']], '#a8afb7')):
            bars = axes[0].bar(x+offset, values, width, label=label, color=color)
            axes[0].bar_label(bars, fmt='%.4g', padding=3, fontsize=8)
        axes[0].set_xticks(x, ['Vector (N)', 'Component (3N)']); axes[0].set_title('Coordinate RMSE')
        axes[0].set_ylabel('RMSE (Angstrom)'); axes[0].legend(fontsize=8)
        for ax, title, unit, values in ((axes[1], 'Sigma-normalized component MSE', 'MSE (dimensionless)',
                [m['explicit_sigma_normalized_component_MSE'], zero['explicit_sigma_normalized_component_MSE']]),
                (axes[2], 'Local pair RMSE', 'RMSE (Angstrom)', [m['local_pair_RMSE_A'], m['noisy_identity_local_pair_RMSE_A']])):
            if any(value is None for value in values): ax.text(.5, .5, 'N/A: no local pairs', ha='center', transform=ax.transAxes)
            else:
                bars = ax.bar(['Fitted', 'Zero'], values, color=['#2878a1', '#a8afb7'], width=.6)
                ax.bar_label(bars, fmt='%.4g', padding=4)
            ax.set_title(title); ax.set_ylabel(unit)
        axes[1].set_xlabel('Denominator: 3N * sigma^2; sigma=0.1 A')
        axes[2].set_xlabel('All unique clean-distance<2 A pairs')
        for ax in axes:
            ax.set_ylim(bottom=0, top=max(ax.get_ylim()[1]*1.15, 1e-8)); ax.grid(axis='y', alpha=.2); ax.set_axisbelow(True)
        fig.suptitle('C2 artifact-origin existing-S PRETRAIN_VAL | analysis only')
        try:
            fig.savefig(output/'metrics.png', dpi=180); fig.savefig(output/'metrics.pdf')
        finally: plt.close(fig)


def render(context, certificate, output, *, deadline=None):
    schema.require(certificate['status'] == 'VERIFIED' and certificate['job_id'] == context['job_id']
        and certificate['run_id'] == context['run_id'] and certificate['metadata_bindings'] == context['sources']
        and certificate['all_public_metrics_config_summary_exact'] is True
        and certificate['native']['native_closed'] is True, 'Matching independent native verification required')
    output = Path(output)
    schema.require(output.is_absolute() and '..' not in output.parts and not output.exists(), 'Fresh absolute report output required')
    for parent in output.parents: schema.require(not parent.is_symlink(), 'Physical output ancestry required')
    output.mkdir(parents=True, exist_ok=False)
    report = dict(context['report']); report['status'] = SUCCESS
    report['independent_native_SDK'] = {'status': 'VERIFIED', 'native_records': certificate['native']['native_packets'],
        'history_rows': 2, 'steps': [0, 1], 'expectation_origin': certificate['expectation_origin'], 'SDK_file': certificate['SDK_file']}
    report['reporting_sources'] = {path.name: schema.file_ref(path) for path in
        (Path(__file__), Path(schema.__file__), Path(native.__file__))}
    (output/'native_verification.json').write_bytes(schema.encoded(certificate))
    draw(report, output)
    (output/'report.json').write_bytes(schema.encoded(report))
    (output/'report.md').write_text(markdown(report), encoding='utf-8')
    buffer = io.StringIO(newline=''); writer = csv.DictWriter(buffer, fieldnames=list(context['csv']), lineterminator='\n')
    writer.writeheader(); writer.writerow(context['csv'])
    (output/'summary.csv').write_text(buffer.getvalue(), encoding='utf-8', newline='')
    refs = [schema.file_ref(output/name, native.LIMITS['max_export_bytes']) for name in
        ('native_verification.json', 'report.json', 'report.md', 'summary.csv', 'metrics.png', 'metrics.pdf')]
    schema.require(sum(item['bytes'] for item in refs) < native.LIMITS['max_export_bytes']-(1 << 20), 'Report output budget exceeded')
    for ref in context['sources'].values(): schema.require(schema.file_ref(ref['path']) == ref, 'Metadata changed while reporting')
    schema.require(deadline is None or time.monotonic() <= deadline, 'Report wall budget exhausted before completion')
    complete = {'schema': 'model_v3_C2_artifact_v3_report_complete_v1', 'status': SUCCESS,
        'files': refs, 'input_bindings': context['sources'], 'SDK_file': certificate['SDK_file'],
        'reader_source': certificate['reader_source'], 'reporting_sources': report['reporting_sources'],
        'identities_weights_coordinates_predictions_exported': False, 'model_selection_gate': False}
    (output/'REPORT_COMPLETE.json').write_bytes(schema.encoded(complete))
    return report


def main(argv=None):
    deadline = time.monotonic()+native.LIMITS['max_wall_seconds']
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True); parser.add_argument('--inputs-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    context = native.load_context(args.inputs, args.inputs_sha256)
    report = render(context, native.verify(context, deadline=deadline), args.output, deadline=deadline)
    print(schema.encoded({'status': report['status'], 'job_id': report['actual_job_id'], 'model_selection_gate': False}).decode(), end='')


if __name__ == '__main__': main()
