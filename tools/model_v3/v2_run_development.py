"""Dispatch existing taskbook-v2 programs from an explicit experiment JSON."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


BASE = Path('/lfshome/zixiao/model_v31_20261105')
NATIVE_ARGUMENTS = ('index_path', 'output', 'distance_bias', 'views', 'seed',
    'samples', 'batch_size', 'lr', 'schedule', 'clip', 'workers', 'microbatch_size', 'resume')
REGISTRY = Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/model_output_budget.json')


def require_registered_output(output, registry):
    path = Path(output).resolve()
    if registry.get('schema') != 'MODEL_OUTPUT_BUDGET_V1':
        raise ValueError('The global model output registry is required')
    roots = [Path(name).resolve() for name in registry['roots']]
    if not any(root.parent == BASE and path.is_relative_to(root) for root in roots):
        raise ValueError('Register the experiment root in the existing global forecast before launching')


def command(mode, configuration, configuration_path, *, python=sys.executable):
    output = Path(configuration['output'])
    if not output.is_absolute() or output == BASE or not output.resolve().is_relative_to(BASE):
        raise ValueError('Use an owned experiment output below the shared model root')
    prefix = [python, '-B', '-u']
    if mode == 'latent':
        return prefix + ['tools/model_v3/v3_train_latent.py', '--configuration', str(configuration_path)]
    if mode == 'v31':
        if not configuration.get('root'):
            raise ValueError('Bind the published data root before launching a trial')
        return prefix + ['tools/model_v3/v2_train_v31.py', '--configuration', str(configuration_path)]
    if mode == 'native_s':
        if set(configuration) - set(NATIVE_ARGUMENTS) or not configuration.get('index_path'):
            raise ValueError('Use only the existing native S CLI arguments and original D5 index')
        argv = prefix + ['tools/model_v3/v2_train_s.py']
        for name in NATIVE_ARGUMENTS:
            if name in configuration and configuration[name] is not None:
                argv += ['--' + name.replace('_', '-'), str(configuration[name])]
        return argv
    if mode == 'dev':
        if set(configuration) - {'checkpoint', 'output', 'validation_index','panel','reference_only','cache_root'} or not configuration.get('checkpoint'):
            raise ValueError('Use the existing development panel inputs')
        argv = prefix + ['tools/model_v3/v2_evaluate_s.py', '--checkpoint',
            str(configuration['checkpoint']), '--output', str(output)]
        if configuration.get('validation_index'):
            argv += ['--validation-index', str(configuration['validation_index'])]
        if configuration.get('panel'):
            argv += ['--panel',str(configuration['panel'])]
        if configuration.get('reference_only'):
            argv += ['--reference-only']
        if configuration.get('cache_root'):
            argv += ['--cache-root',str(configuration['cache_root'])]
        return argv
    if mode == 'validation':
        names = ('checkpoint', 'output', 'unseen_root', 'train_root', 'unseen_split',
                 'unseen_subset', 'train_subset', 'batch_size')
        if set(configuration) - set(names) or not configuration.get('checkpoint'):
            raise ValueError('Use the existing paired validation inputs')
        if configuration.get('unseen_split', 'FULL') != 'FULL':
            raise ValueError('Use FULL or its ROUTINE subset, never downstream TEST')
        argv = prefix + ['tools/model_v3/v2_validate_v31.py']
        for name in names:
            if name in configuration and configuration[name] is not None:
                argv += ['--' + name.replace('_', '-'), str(configuration[name])]
        return argv
    raise ValueError('Unknown existing development program')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('v31', 'native_s', 'dev', 'validation', 'latent'), required=True)
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--show-output', action='store_true')
    args = parser.parse_args()
    configuration = json.loads(Path(args.configuration).read_text())
    argv = command(args.mode, configuration, args.configuration)
    require_registered_output(configuration['output'], json.loads(REGISTRY.read_text()))
    if args.show_output:
        print(configuration['output'])
        return 0
    return subprocess.run(argv, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
