"""Fill the registered9M curve from closed primaries and existing VAL columns."""
import csv
import io
import json
from pathlib import Path

from cpu_execution_20261126 import execution_fields, native_record
from e1_reporting_20261126 import original_p_algebra
from storage_20261122 import CONTROL as C, REPO as R, ROOT, write

RUNS = ('S_B0_s0_9M', 'S_final_s0_9M')
read = lambda path: json.loads(Path(path).read_text())


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['svg.fonttype'] = 'none'
    figure, axes = plt.subplots(2, 1, figsize=(7.2, 6.4), sharex=True, constrained_layout=True)
    for run, label, color in zip(RUNS, ('S-B0', 'S-final'), ('#276fbf', '#c65d21')):
        series = sorted((row for row in rows if row['source_run']==run and row['R3_mean']!=''),
            key=lambda row:int(row['samples']))
        x = [int(row['samples'])/1000000 for row in series]
        for axis, key in zip(axes, ('R1', 'R3')):
            axis.plot(x, [float(row[key+'_mean']) for row in series], 'o-', color=color, label=label)
            axis.fill_between(x, [float(row[key+'_ci_lower']) for row in series],
                [float(row[key+'_ci_upper']) for row in series], color=color, alpha=.13)
            axis.set_ylabel(key+' normalized improvement')
            axis.grid(alpha=.2)
    axes[0].legend(frameon=False)
    axes[0].set_title('Original 9M cosine trajectories: frozen layer 6')
    axes[-1].set_xlabel('Training samples (millions)')
    axes[-1].set_xticks(range(1,10))
    directory = R/'results/s_recipe/figures'
    directory.mkdir(parents=True, exist_ok=True)
    figure.savefig(directory/'budget_frozen_curve.svg')
    figure.savefig(C/'budget_frozen_curve_20261127.png', dpi=160)
    plt.close(figure)
    figure, axes = plt.subplots(3, 1, figsize=(7.2, 7.5), sharex=True, constrained_layout=True)
    for axis, family in zip(axes, ('s_bond', 's_element', 's_noise')):
        for run, label, color in zip(RUNS, ('S-B0', 'S-final'), ('#276fbf', '#c65d21')):
            series = sorted((row for row in rows if row['source_run']==run and row['VAL_loss_'+family]!=''),
                key=lambda row:int(row['samples']))
            if not series: continue
            axis.plot([int(row['samples'])/1000000 for row in series],
                [float(row['VAL_loss_'+family]) for row in series], '.-', color=color, label=label)
        axis.set_ylabel(family+' VAL loss')
        axis.grid(alpha=.2)
    axes[0].legend(frameon=False)
    axes[0].set_title('Existing fixed-VAL records, transcribed once')
    axes[-1].set_xlabel('Training samples (millions)')
    figure.savefig(directory/'budget_VAL_curve.svg')
    figure.savefig(C/'budget_VAL_curve_20261127.png', dpi=160)
    plt.close(figure)


def collect():
    marker = C/'budget_readout_delivery_20261127_COMPLETE.json'
    if marker.exists():
        return read(marker)
    phases = {}
    for run in RUNS:
        for samples in range(1000000, 9000000, 1000000):
            output = C/'training'/run/('readout_'+str(samples))
            phase = read(output/'snapshot_statistics_status.json')
            parent_path = Path(phase['native_record'])
            parent = read(parent_path)
            command = read(parent_path.with_name('command_exit.json'))
            gpu = read(output/'snapshot_gpu_status.json')
            close = read(C/(gpu['resource_handle']+'_resource_close.json'))
            if (phase.get('status') != 'COMPLETE' or not phase.get('owned_descendants_exited')
                    or phase.get('run') != run or phase.get('samples') != samples
                    or parent.get('status') != 'COMPLETE' or parent.get('exit_code') != 0
                    or command.get('exit_code') != 0 or not parent.get('owned_descendants_exited')
                    or not parent.get('observer_joined') or close.get('status') != 'OWN_RESOURCES_CLOSED'
                    or close.get('exit_code') != 0 or close.get('run') != run or close.get('samples') != samples):
                raise ValueError('All16 actual original-trajectory readouts must be closed first')
            phases[(run, samples)] = dict(phase=phase, parent=parent, gpu_close=close)
    # First and only reporting consumption of these original scores. All draws
    # are retained producer results; compare_frozen performs subtraction only.
    scores = {(run, samples): read(C/'training'/run/('readout_'+str(samples))/'scores.json')
        for run, samples in phases}
    algebra = original_p_algebra(ROOT/'MFM_p_recipe')
    points = []
    fields = ('complete', 'mean_normalized_improvement', 'bootstrap_ci',
        'bootstrap_samples', 'bootstrap_defined', 'bootstrap_unit', 'bootstrap_seed', 'included_tasks')
    for (run, samples), score in scores.items():
        for key in ('R1', 'R3'):
            value = score[key]
            if not value.get('complete') or value['bootstrap_samples'] != 1000 or value['bootstrap_defined'] != 1000:
                raise ValueError('Original seven-task primaries must contain1000 defined draws')
        point = dict(run=run, samples=samples, source_training_budget=9000000,
            independent_budget=False, descriptive_only=True, layer=6,
            readouts={key:{field:score[key][field] for field in fields if field in score[key]}
                for key in ('R1', 'R3')}, execution=phases[(run, samples)])
        if run == RUNS[1]:
            point['paired_vs_B0_same_9M_trajectory_boundary'] = {
                key:algebra.compare_frozen(score, scores[(RUNS[0], samples)], key)['decision']
                for key in ('R1', 'R3')}
            # This is a descriptive contrast, without a recipe decision.
            for value in point['paired_vs_B0_same_9M_trajectory_boundary'].values():
                value.pop('verdict', None)
        points.append(point)
    value = dict(status='COMPLETE_ORIGINAL9M_PREFIX_READOUT_DELIVERY', points=points,
        reporting_execution=execution_fields(), original_score_files_consumed=16,
        new_fits=0, new_bootstrap_draws=0, original_VAL_files_reopened=0,
        endpoint9M='Already delivered original endpoints reused from budget_curve.csv',
        interpretation='Within-run cosine trajectory trends; no independent-budget or screening3M comparison')
    write(R/'results/s_recipe/budget_readout_delivery_20261127.json', value)
    write(marker, value)
    return value


def run():
    native_record()
    delivery = collect()
    destination = R/'results/s_recipe/budget_curve.csv'
    with destination.open(newline='') as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames)
        rows = list(reader)
    if (len(rows) != 36 or {(r['source_run'], int(r['samples'])) for r in rows}
            != {(run, samples) for run in RUNS for samples in range(500000, 9000001, 500000)}):
        raise ValueError('Preserve the existing two complete eighteen-point VAL series')
    originals = {(r['source_run'], r['samples']):{k:v for k,v in r.items() if k.startswith('VAL_')} for r in rows}
    points = {(p['run'], p['samples']):p for p in delivery['points']}
    for name in ('fullFT_ensemble_mean', 'fullFT_ci_estimand'):
        if name not in fields: fields.append(name)
    completed_ft = []
    for row in rows:
        point = points.get((row['source_run'], int(row['samples'])))
        if point:
            row.update(readout_run=point['run'], readout_complete=True,
                readout_status='COMPLETE_ORIGINAL9M_TRAJECTORY')
            for key in ('R1', 'R3'):
                value = point['readouts'][key]
                row[key+'_mean'] = value['mean_normalized_improvement']
                row[key+'_ci_lower'], row[key+'_ci_upper'] = value['bootstrap_ci']
                pair = point.get('paired_vs_B0_same_9M_trajectory_boundary', {}).get(key)
                if pair:
                    for field in ('delta', 'ci_lower', 'ci_upper'):
                        row[key+'_S_final_minus_S_B0_'+field] = pair[field]
        if row['fullFT_point']:
            path = R/'results/s_recipe/full_finetune'/(row['fullFT_point']+'.json')
            if path.exists():
                ft = read(path)
                if ft.get('status') != 'COMPLETE_FULLFT_POINT':
                    raise ValueError('Exact complete fullFT point delivery required')
                value = ft['aggregate']
                row.update(fullFT_status='COMPLETE_DESCRIPTIVE',
                    fullFT_mean=value['scratch_improvement_seed_mean'],
                    fullFT_ensemble_mean=value['ensemble_scratch_improvement'],
                    fullFT_ci_lower=value['ensemble_ci'][0], fullFT_ci_upper=value['ensemble_ci'][1],
                    fullFT_ci_estimand=value['ensemble_ci_estimand'])
                completed_ft.append(row['fullFT_point'])
    if originals != {(r['source_run'], r['samples']):{k:v for k,v in r.items() if k.startswith('VAL_')} for r in rows}:
        raise ValueError('Original transcribed VAL columns changed')
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    temporary = destination.with_suffix('.csv.next')
    temporary.write_text(stream.getvalue())
    temporary.replace(destination)
    plot(rows)
    status = dict(status='READOUTS_COMPLETE_FULLFT_COMPLETE' if len(completed_ft)==5 else
        'READOUTS_COMPLETE_FULLFT_PENDING', reporting_execution=execution_fields(),
        rows=36, completed_readout_points=18, completed_fullFT_points=completed_ft,
        required_fullFT_points=5, original_VAL_files_reopened=0, new_fits=0, new_bootstrap_draws=0)
    write(R/'results/s_recipe/budget_curve_status.json', status)
    print(json.dumps(status), flush=True)
    return 0
