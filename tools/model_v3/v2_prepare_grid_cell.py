"""Prepare/submit one preregistered cell after real model/recipe freezing.

This stdlib-only launcher may run on the development login host; training is
always submitted to Slurm. It never creates frozen winners or a value of B*.
"""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess


CROSS = {(120_000, k) for k in (1, 2, 5, None)} | {(m, 1) for m in (240_000, 600_000, 1_126_937)}
OUTER = {(1_126_937, 2), (1_126_937, 5)}


def required_cells():
    return {('S', m, k) for m,k in CROSS | OUTER} | {('P', m, k) for m,k in CROSS | OUTER} | {
        ('D', m, k) for m,k in CROSS} | {('Sprime', 120_000, k) for k in (1, None)}


def make_configuration(model, recipe, *, condition, molecules, k, order, seed,
                       root, subset, training_view, normalizations, output, shared_k_star=None):
    if model.get('status') != 'FROZEN' or recipe.get('status') != 'FROZEN':
        raise ValueError('Actual frozen model and recipe files are required')
    architecture = model['architecture']
    if (architecture['layers'], architecture['dim']) != (6, 512):
        raise ValueError('This taskbook does not contain model-size comparisons')
    if architecture['backbone_activation_checkpointing'] or architecture['head_activation_checkpointing']:
        raise ValueError('Use the adopted backbone/HeadOff settings')
    if (recipe['optimizer'] != 'AdamW' or recipe['betas'] != [.9,.95]
            or recipe['warmup_fraction'] != .02 or recipe.get('wsd_decay_fraction', .2) != .2
            or recipe.get('weight_decay', .01) != .01):
        raise ValueError('Frozen recipe differs from the implemented taskbook recipe')
    if type(recipe['sample_budget']) is not int or recipe['sample_budget'] <= 0:
        raise ValueError('An actual frozen sample budget B* is required')
    if (condition, molecules, k) not in required_cells():
        comparison_k = None if shared_k_star == 'all' else shared_k_star
        if not (condition in ('Sprime', 'Pprime') and molecules == 120_000 and k == comparison_k
                and shared_k_star in (1, 2, 5, 'all')):
            raise ValueError('Cell is outside the preregistered grid or actual shared-k* comparison')
    if order != 'fixed_random' and (molecules, k) != (120_000, 1):
        raise ValueError('Ordering comparison is at M120000, k1')
    if seed not in (0, 1):
        raise ValueError('Use the two preregistered seed IDs')
    source = 'UFF' if condition in ('Sprime', 'Pprime') else 'PM7'
    actual_condition = {'Sprime':'S', 'Pprime':'P'}.get(condition, condition)
    if actual_condition != 'S' and (not training_view or not normalizations):
        raise ValueError('Explicit frozen training view and source-specific D4 mapping required')
    return dict(root=str(root), subset_path=str(subset), output=str(output), stage='performance',
        code_tag=model['code_tag'], candidate=condition, condition=actual_condition,
        distance_bias=architecture['distance_bias'], views=architecture['views'],
        head_form=architecture['head_form'], pooling=architecture['pooling'],
        training_view=training_view, normalizations=normalizations, source=source,
        order=order, k=k, seed=seed, expected_molecules=molecules,
        samples=recipe['sample_budget'], batch_size=recipe['batch_size'], lr=recipe['lr'],
        schedule=recipe['schedule'], clip=recipe['clip'])


def slurm_script(configuration_path, output, *, node, gpu_uuid, python, repo):
    if not re.fullmatch(r'compute-0-\d+', node) or not re.fullmatch(r'GPU-[0-9a-fA-F-]+', gpu_uuid):
        raise ValueError('Explicit development compute node and GPU UUID required')
    q = shlex.quote
    dispatcher = repo / 'tools/model_v3/v2_run_development.sbatch'
    return '\n'.join(['#!/bin/bash', '#SBATCH --job-name=model-v3-grid-cell', '#SBATCH --partition=all',
        '#SBATCH --nodelist=' + node, '#SBATCH --nodes=1', '#SBATCH --ntasks=1',
        '#SBATCH --cpus-per-task=16', '#SBATCH --output=' + str(output) + '.log',
        'set -euo pipefail', 'cd ' + q(str(repo)),
        'exec /bin/bash ' + q(str(dispatcher)) + ' v31 ' + q(str(configuration_path))
        + ' ' + q(gpu_uuid) + ' ' + q(python), ''])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('model-config','recipe-config','root','subset','output','node','gpu-uuid','python'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--condition', choices=['S','P','D','Sprime','Pprime'], required=True)
    parser.add_argument('--molecules', type=int, required=True)
    parser.add_argument('--k', choices=['1','2','5','all'], required=True)
    parser.add_argument('--order', choices=['fixed_random','energy','diversity'], default='fixed_random')
    parser.add_argument('--seed', type=int, choices=[0,1], default=0)
    parser.add_argument('--training-view')
    parser.add_argument('--normalizations')
    parser.add_argument('--shared-k-star', choices=['1','2','5','all'])
    parser.add_argument('--submit', action='store_true')
    args = parser.parse_args()
    k = None if args.k == 'all' else int(args.k)
    shared = None if args.shared_k_star is None else 'all' if args.shared_k_star == 'all' else int(args.shared_k_star)
    config = make_configuration(json.loads(Path(args.model_config).read_text()),
        json.loads(Path(args.recipe_config).read_text()), condition=args.condition,
        molecules=args.molecules, k=k, order=args.order, seed=args.seed, root=args.root,
        subset=args.subset, training_view=args.training_view, normalizations=args.normalizations,
        output=args.output, shared_k_star=shared)
    output = Path(args.output).absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    configuration_path = Path(str(output) + '.input.json')
    script = Path(str(output) + '.sbatch')
    repo = Path(__file__).absolute().parents[2]
    body = slurm_script(configuration_path, output, node=args.node, gpu_uuid=args.gpu_uuid,
                        python=args.python, repo=repo)
    with configuration_path.open('x') as file:
        file.write(json.dumps(config, indent=2) + '\n')
    with script.open('x') as file:
        file.write(body)
    if args.submit:
        subprocess.run(['sbatch', str(script)], check=True)
    else:
        print(shlex.join(['sbatch', str(script)]))


if __name__ == '__main__':
    main()
