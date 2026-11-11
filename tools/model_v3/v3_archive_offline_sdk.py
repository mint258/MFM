"""Archive actual closed v3 SDKs with the existing protected tar producer."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket

from v2_archive_wandb import pack_closed_runs, actual_capacity_check, BASE, PROJECT


def sdk_roots(manifest, jobs):
    if not jobs or len(set(jobs)) != len(jobs) or any(type(j) is not int or j <= 0 for j in jobs):
        raise ValueError('Select distinct actual positive Slurm IDs')
    base = Path(manifest['tracking_root']).resolve()
    if base != BASE or manifest.get('schema') != 'MODEL_V3_CLOSED_SDK_INPUTS_V1':
        raise ValueError('Use the actual model-window SDK input manifest')
    roots = []
    for job in jobs:
        rows = [r for r in manifest['runs'] if r['job'] == job]
        if len(rows) != 1 or not rows[0]['sdk_directories']:
            raise ValueError('Every actual job must occur once and have real SDK directories')
        for record in rows[0]['sdk_directories']:
            root = Path(record['path'])
            if (root.name != str(job) or root.is_symlink() or
                    not root.resolve().is_relative_to(base) or not root.is_dir()):
                raise ValueError('Use an owned ordinary model SDK directory')
            name = record['marker']
            if name not in ('sdk_finished.json', 'tracking.json', 'status.json'):
                raise ValueError('Use the original SDK completion marker')
            marker = root / name
            state = json.loads(marker.read_text())
            closed = (state.get('sdk_finished') is True or state.get('native_sdk_finished') is True
                      if name == 'sdk_finished.json' else state.get('finished') is True)
            if not closed or (name != 'sdk_finished.json' and state.get('job') != job):
                raise ValueError('The actual SDK session is not closed')
            roots.append(root)
    if len(set(map(str, roots))) != len(roots):
        raise ValueError('An SDK directory must be archived only once in a bundle')
    return base, roots


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True)
    args = parser.parse_args()
    if os.getuid() != 1278 or socket.gethostname().split('.')[0] != 'compute-0-20':
        raise ValueError('Compression belongs to the existing CPU development node')
    c = json.loads(Path(args.configuration).read_text())
    manifest = json.loads(Path(c['sources_manifest']).read_text())
    spec = importlib.util.spec_from_file_location('existing_model_output_registry',
        PROJECT / 'MFM_model_v3/tools/model_v3/v2_run_development.py')
    registry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(registry)
    budget = json.loads(registry.REGISTRY.read_text())
    registry.require_registered_output(c['output'], budget)
    for row in manifest['runs']:
        for directory in row['sdk_directories']:
            registry.require_registered_output(directory['path'], budget)
    base, roots = sdk_roots(manifest, c['jobs'])
    capacity = actual_capacity_check(Path(c['output']))
    from v3_sdk_system_report import export_system_reports
    reports = export_system_reports(roots, c['jobs'], Path(c['output']), capacity)
    result = pack_closed_runs(manifest, c['jobs'], Path(c['output']), c['name'],
        capacity_check=capacity, root_resolver=lambda _manifest, _jobs: (base, roots + [reports]),
        archive_prefix='MODEL_V3_OFFLINE_SDK')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}), flush=True)


if __name__ == '__main__':
    main()

