"""Root-managed metadata preparation, allocated reconstruction and collection."""
from __future__ import annotations
import argparse
from pathlib import Path
from .support import canonical, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--inventory-receipt', required=True)
    p.add_argument('--acquisition-receipt', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--plan', required=True)
    p.add_argument('--resources', required=True, help='Root actual working/future/quota resource JSON, not hypothetical constants')
    p.add_argument('--workers', type=int, required=True)
    p.add_argument('--batch-rows', type=int, default=512)
    for action in ('run', 'assemble'):
        command = sub.add_parser(action)
        command.add_argument('--plan', required=True)
        if action == 'run':
            command.add_argument('--indices', help='Comma-separated original descriptor indices; omitted means all500')
    args = parser.parse_args()
    if args.action == 'prepare':
        from .plan import prepare
        result = prepare(args.inventory_receipt, args.acquisition_receipt, args.output, args.plan, workers=args.workers, batch_rows=args.batch_rows, resource_parameters=load(args.resources))
    elif args.action == 'run':
        from .run import run
        result = run(args.plan, None if args.indices is None else [int(x) for x in args.indices.split(',')])
    elif args.action == 'assemble':
        from .run import assemble
        result = assemble(args.plan)
    print(canonical(result).decode(), flush=True)


if __name__ == '__main__':
    main()
