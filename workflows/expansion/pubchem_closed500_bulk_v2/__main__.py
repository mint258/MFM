"""Root-managed prepare/project/merge/run CLI; cluster scheduling stays external."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from .common import canonical, load, need, reference, write_new
from .plan import load_coverage, validate_plan


def actual_compute(workers):
    import socket
    need(socket.gethostname().startswith('compute-') or bool(os.environ.get('SLURM_JOB_ID')), 'Run scientific-data projection/SQL on an actual compute node')
    available = len(os.sched_getaffinity(0))
    declared = int(os.environ.get('SLURM_CPUS_PER_TASK', available))
    need(workers <= min(available, declared), 'Workers exceed actual allowed CPU allocation/affinity')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--coverage', required=True)
    prepare.add_argument('--output', required=True)
    prepare.add_argument('--plan', required=True)
    prepare.add_argument('--workers', type=int, required=True)
    prepare.add_argument('--batch-rows', type=int, default=8192)
    prepare.add_argument('--output-cap-bytes', type=int, required=True)
    prepare.add_argument('--minimum-free-bytes', type=int, required=True)
    prepare.add_argument('--other-future-reserved-bytes', type=int, required=True)
    prepare.add_argument('--duckdb-memory-bytes', type=int, required=True)
    for action in ('project', 'merge', 'run'):
        command = sub.add_parser(action)
        command.add_argument('--plan', required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        ref = reference(args.coverage)
        plan = {'schema': 'PUBCHEM_CLOSED500_BULK_PLAN_V2', 'coverage_reference': ref, 'fragments': load_coverage(ref), 'output_directory': str(Path(args.output).absolute()), 'workers': args.workers, 'batch_rows': args.batch_rows, 'output_cap_bytes': args.output_cap_bytes, 'minimum_free_bytes': args.minimum_free_bytes, 'other_future_reserved_bytes': args.other_future_reserved_bytes, 'duckdb_memory_bytes': args.duckdb_memory_bytes, 'arbitrary_wall_clock_or_retry_count_stop': False, 'scientific_functions_invoked': False}
        validate_plan(plan)
        print(canonical(write_new(args.plan, plan)).decode())
        return
    plan = validate_plan(load(args.plan))
    actual_compute(plan['workers'])
    root = Path(plan['output_directory'])
    if args.action in ('project', 'run'):
        from .project import project
        project(args.plan)
    if args.action in ('merge', 'run'):
        from .merge import materialize
        materialize(root / 'projection_manifest.json', root / 'unfiltered_pool', plan['workers'], plan['duckdb_memory_bytes'], plan, inputs_verified=args.action == 'run')


if __name__ == '__main__':
    main()
