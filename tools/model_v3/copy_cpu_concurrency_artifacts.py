"""Copy only completed phase summaries; never replay training measurements."""
import argparse
import json
from pathlib import Path

from cpu_bottleneck_step1 import REPO, SCRATCH, capacity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', required=True, type=int)
    args = parser.parse_args()
    root = SCRATCH / f'concurrency_{args.job}'
    output = REPO / 'results/model_v3_perf_20261112' / root.name
    sources = sorted(root.glob('*/summary.json'))
    if (root/'summary.json').is_file():
        sources.append(root/'summary.json')
    for source in sources:
        data = source.read_bytes()
        value = json.loads(data)
        if source.parent != root and 'samples_per_second' not in value:
            raise ValueError('Phase summary lacks completed throughput measurements')
        target = output / source.relative_to(root)
        if target.exists():
            if target.read_bytes() != data:
                raise ValueError('A previously closed summary changed; preserve both sources for review')
            continue
        capacity()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as file:
            file.write(data)
        print(source.relative_to(root), len(data), flush=True)


if __name__ == '__main__':
    main()
