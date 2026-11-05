"""Resume transport of already compacted, once-validated v3.1 outputs only."""
import argparse
import collections
import concurrent.futures
import json
import pathlib
import subprocess
import time

from .run import load, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--finalize-only', action='store_true',
                        help='Publish metadata from recorded successful transfers; no data reads or copies')
    args = parser.parse_args()
    plan = load(args.plan)
    root = pathlib.Path(plan['output_root'])
    started = time.monotonic()
    manifests = {role: load(root / ('v31_pilot_' + role) / 'manifest.json')
                 for role in ('TRAIN', 'VAL')}
    # Reuse the actual final check results. Never open an LMDB or rerun QA here.
    numerical = manifests['TRAIN']['numeric_check']
    assert numerical == manifests['VAL']['numeric_check']
    assert numerical['status'] == 'COMPLETE' and numerical['pm7_samples'] == 1000
    schema = load(root / 'schema.json')
    arrays = schema['array_definitions']
    arrays['3']['codebook'] = {'1': 'single', '2': 'double', '3': 'triple', '4': 'aromatic'}
    arrays['5']['codebook'] = schema['role_codebook']
    arrays['6']['source_axis'] = ['pm7', 'uff_sprime']
    for ident in ('7', '9', '10'):
        arrays[ident]['index_semantics'] = 'Zero-based P conformer_index in this molecule; original published order'
    for ident in ('8', '11', '12'):
        arrays[ident]['index_semantics'] = 'Zero-based U conformer_index in this molecule; original published order'
    for ident, kind in [('13', 'P'), ('14', 'U')]:
        arrays[ident].update(index_semantics=kind + ' conformer_index', codebook={
            '0': 'ordinary training-eligible subject to original policy',
            '1': 'D5 holdout; exclude this base and its actual child targets from training'})
    for ident in ('21', '22'):
        arrays[ident].update(unit='angstrom', atom_axis='M.Z order')
    arrays['31'].update(index_base=0, ref_array_id=26,
                        order='Original retained r73 entry order including duplicates')
    arrays['32'].update(columns=['basis_i', 'basis_j', 'optional_channel'],
                        codebook='r73_channel_codebook', absent_code=0)
    arrays['33']['codebook'] = {'0': 'not provided', '1': False, '2': True}
    schema['array_axis_descriptions_published_by_root'] = True
    save(root / 'schema.json', schema)

    def transfer(node):
        subprocess.run(['ssh', '-n', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', node,
                        'test "$(id -u)" = 1278 && mkdir -p ' + plan['node_destination_root']], check=True)
        # rsync --protect-args sends its remote arguments over stdin; ssh -n breaks it.
        subprocess.run(['rsync', '-a', '--sparse', '--protect-args', '-e',
                        'ssh -o BatchMode=yes -o ConnectTimeout=15', str(root) + '/',
                        node + ':' + plan['node_destination_root'] + '/'], check=True)
        return dict(node=node, directory=plan['node_destination_root'], status='RSYNC_SPARSE_COMPLETED')

    remaining = list(plan['gpu_nodes'])
    completed = []
    if args.finalize_only:
        completed = load(plan['progress_path'])['completed']
        assert {x['node'] for x in completed} == set(plan['gpu_nodes'])
        assert all(x['status'] == 'RSYNC_SPARSE_COMPLETED' for x in completed)
        remaining = []
    while remaining:
        deferred = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            pending = {pool.submit(transfer, node): node for node in remaining}
            for future in concurrent.futures.as_completed(pending):
                node = pending[future]
                try:
                    completed.append(future.result())
                    error = None
                except subprocess.CalledProcessError as exc:
                    deferred.append(node)
                    error = str(exc)
                save(plan['progress_path'], dict(phase='COPY', completed=completed,
                    node=node, error=error, remaining=[n for n in plan['gpu_nodes']
                    if n not in {x['node'] for x in completed}]))
        remaining = deferred
        if remaining:
            time.sleep(60)
    counts = collections.Counter()
    sizes = collections.Counter()
    for manifest in manifests.values():
        counts.update(manifest['records'])
        sizes.update(manifest['record_key_value_bytes'])
    logical = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    allocated = int(subprocess.check_output(['du', '-s', '-B1', str(root)], text=True).split()[0])
    # Native accounting is collected on the login host, not compute-local localhost:6819.
    original_elapsed = plan['original_export_elapsed_seconds']
    distribution_seconds = (plan['distribution_elapsed_seconds'] if args.finalize_only
                            else time.monotonic() - started)
    save(plan['progress_path'], dict(status='D3_V31_EXPORTED_VALIDATED_AND_DISTRIBUTED',
        shared_root=str(root), roles={r: m['molecule_count'] for r, m in manifests.items()},
        P_records=counts['P'], U_records=counts['U'], logical_bytes=logical, du_bytes=allocated,
        export_seconds=manifests['TRAIN']['export_seconds'],
        total_seconds=original_elapsed + distribution_seconds,
        distribution_seconds=distribution_seconds,
        administrative_metadata_recovery=args.finalize_only,
        original_export_job='4525960', original_export_terminal='CANCELLED_AFTER_FINAL_CHECK_DURING_TRANSPORT_ONLY',
        mean_record_bytes={k: sizes[k] / counts[k] for k in ('M', 'P', 'U')},
        numerical=numerical, topology_differences=manifests['TRAIN']['topology_difference_count'],
        transfers=sorted(completed, key=lambda x: x['node']), old_v30_preserved=True,
        Model_payload_ACK=False, D6=False))


if __name__ == '__main__':
    main()
