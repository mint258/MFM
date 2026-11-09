"""Prepare only the top-two C1 seed repeats after all six initial dev results."""
import argparse
import importlib.util
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASE = Path('/lfshome/zixiao/model_v31_20261105')
CANDIDATES = ('C1-0', 'C1-a', 'C1-b')
spec = importlib.util.spec_from_file_location('existing_v2_decisions',
    REPO/'current/phychem_mfm/phase1/v2_decisions.py')
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


def rank_initial(rows):
    if len(rows) != 6:
        raise ValueError('All three candidates on S and P are required')
    complete, pending = rules.condition_aggregates(rows, ('S', 'P'))
    if pending or set(complete) != set(CANDIDATES) or any(set(v) != {0} for v in complete.values()):
        raise ValueError('Complete S/P seed0 results are required; no partial ranking')
    scores = {name: complete[name][0] for name in CANDIDATES}
    ranked = sorted(CANDIDATES, key=lambda name: (-scores[name], CANDIDATES.index(name)))
    return dict(status='TOP_TWO_REPEATS_REQUIRED_NOT_FINAL_ARCHITECTURE',
        joint_seed0_scores=scores, selected_top_two=ranked[:2],
        selected_architecture=None, seed_standard_deviation=None)


def initial_result(entry, cells):
    directory = Path(entry['directory'])
    configuration = json.loads((directory/'configuration.json').read_text())
    summary = json.loads((directory/'dev_eval/summary.json').read_text())
    condition, candidate = entry['condition'], entry['candidate']
    if (configuration.get('condition', 'S') != condition
            or configuration['distance_bias'] != candidate or configuration['seed'] != 0
            or configuration['views'] != 'three' or configuration['samples'] != 6_000_000
            or configuration['batch_size'] != 32 or configuration['lr'] != 3e-4
            or configuration['schedule'] != 'cosine' or configuration['clip'] != 1
            or configuration.get('expected_molecules', configuration.get('TRAIN_molecules')) != 240_000):
        raise ValueError('Initial configuration differs from the frozen C1 comparison')
    if (summary.get('complete') is not True or summary.get('consumed_samples') != 6_000_000
            or set(summary['tasks']) != cells
            or any(not math.isfinite(v['normalized_improvement']) for v in summary['tasks'].values())
            or set(summary.get('source_roles', [])) != {'train', 'train_inner_validation'}
            or summary.get('downstream_TEST_read') is not False
            or Path(summary['checkpoint']).resolve() != (directory/'samples_6000000.pt').resolve()
            or not math.isfinite(summary['mean_normalized_improvement'])):
        raise ValueError('Complete original 6M TRAIN development results are required')
    row = dict(candidate=candidate, condition=condition, seed=0,
        score=summary['mean_normalized_improvement'],
        configuration=str(directory/'configuration.json'), dev_summary=str(directory/'dev_eval/summary.json'))
    return row, configuration


def repeat_configuration(condition, candidate, original):
    output = str(BASE/f'M3_{condition}_{candidate}_seed1')
    if condition == 'P':
        return 'v31', dict(original, seed=1, output=output)
    if condition != 'S' or original['betas'] != [.9, .95]:
        raise ValueError('The original native S recipe is required')
    configuration = {name: original[name] for name in
        ('distance_bias', 'views', 'samples', 'batch_size', 'lr', 'schedule', 'clip')}
    configuration.update(index_path=original['D5_index'], output=output, seed=1,
        workers=14, microbatch_size=4)
    return 'native_s', configuration


def prepare(inputs, output):
    panel = json.loads((REPO/'configs/dev_panel_v1.json').read_text())
    cells = {t['task_id']+'/'+readout for t in panel['tasks'] for readout in ('ridge', 'linear64_relu')}
    rows, originals = [], {}
    for entry in inputs['runs']:
        row, configuration = initial_result(entry, cells)
        rows.append(row)
        originals[(row['condition'],row['candidate'])] = configuration
    result = rank_initial(rows)
    result.update(initial_runs=rows, prepared_repeats=[], gpu_jobs_submitted=False)
    output = Path(output)
    pending = []
    for candidate in result['selected_top_two']:
        for condition in ('S', 'P'):
            mode, configuration = repeat_configuration(condition, candidate, originals[(condition,candidate)])
            path = output/f'{condition}_{candidate}_seed1.json'
            pending.append((path,configuration))
            result['prepared_repeats'].append(dict(candidate=candidate,condition=condition,seed=1,
                mode=mode,configuration=str(path),output=configuration['output']))
    pending.append((output/'selection.json',result))
    spec = importlib.util.spec_from_file_location('existing_metadata_writer',
        REPO/'current/phychem_mfm/phase1/v2_disk.py')
    disk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(disk)
    for path, value in pending:
        if path.exists():
            if json.loads(path.read_text()) != value:
                raise ValueError('Existing prepared configuration differs; preserve it')
        else:
            disk.save_metadata_json(value,path)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    result = prepare(json.loads(Path(args.inputs).read_text()),args.output)
    print(json.dumps(result),flush=True)
