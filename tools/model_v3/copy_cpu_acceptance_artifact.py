"""Archive the closed failed acceptance once; never execute training or comparison."""
import json
from pathlib import Path
from cpu_bottleneck_step1 import REPO, SCRATCH, capacity


def main():
    capacity()
    source = SCRATCH / 'equivalence_4530319/acceptance.json'
    target = REPO / 'results/model_v3_perf_20261112/equivalence_4530319.json'
    raw = source.read_bytes()
    result = json.loads(raw)
    assert result['status'] == 'FAIL' and result['steps'] == 200
    assert result['parameter_relative_l2'] > 1e-5
    if target.exists():
        assert target.read_bytes() == raw
    else:
        capacity()
        with target.open('xb') as file:
            file.write(raw)
    print(target, len(raw), result['status'])


if __name__ == '__main__':
    main()
