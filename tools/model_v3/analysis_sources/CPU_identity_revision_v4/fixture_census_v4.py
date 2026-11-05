"""Original test-only lstat census, with an explicit new-source policy receipt."""
import hashlib
import os
from pathlib import Path
import stat

RUNS = Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025')

def fixture_output_bytes(root, *, output, fixtures):
    root = Path(root).absolute()
    if root != output:
        raise ValueError('The fixture adapter cannot measure arbitrary outputs')
    for attempt in range(3):
        try:
            if not root.exists():
                return 0
            total,entries,seen = 0,0,set()
            stack = [root]
            while stack:
                path = stack.pop()
                info = path.lstat()
                entries += 1
                if entries > 50000 or info.st_uid != os.getuid():
                    raise ValueError('Test output inventory exceeded its owner/entry bounds')
                key = info.st_dev,info.st_ino
                if key in seen:
                    continue
                seen.add(key)
                relative = path.relative_to(root)
                if stat.S_ISLNK(info.st_mode):
                    if not relative.parts or relative.parts[0] not in fixtures:
                        raise ValueError('Only declared pytest fixture subtrees may contain test symlinks')
                    # A link is negative-test data, never a traversal root.
                    total += info.st_size
                elif stat.S_ISDIR(info.st_mode):
                    total += info.st_size
                    with os.scandir(path) as children:
                        stack.extend(Path(child.path) for child in children)
                elif stat.S_ISREG(info.st_mode):
                    total += info.st_size
                elif (stat.S_ISFIFO(info.st_mode) or stat.S_ISSOCK(info.st_mode)) and relative.parts and relative.parts[0] in fixtures:
                    # Negative filesystem fixtures are measured, never opened.
                    total += info.st_size
                else:
                    raise ValueError('Unexpected non-file test output object')
            return total
        except FileNotFoundError:
            if attempt == 2:
                raise


def fixture_policy(output, record, pins_path, pins_sha):
    output = Path(output).absolute()
    job = os.environ['SLURM_JOB_ID']
    scope = os.environ.get('MODEL_V3_CPU_TEST_SCOPE', 'units')
    if scope == 'regression':
        prefix = os.environ.get('MODEL_V3_CPU_TEST_OUTPUT_PREFIX', 'c2_postmerge_tests')
        if prefix not in ('c2_postmerge_tests', 'integration_tests', 'premerge_tests'):
            raise ValueError('Known original output prefix required')
        expected_name = prefix + '_' + job
        fixtures = {'tmp_' + str(index) for index in range(4)}
        request_sha = os.environ['MODEL_V3_EXECUTION_SHA']
    elif scope == 'units':
        from identity_revision_v4 import read_json
        request_sha = os.environ['MODEL_V3_UNITS_REQUEST_SHA']
        request = read_json(Path(os.environ['MODEL_V3_UNITS_REQUEST']), request_sha)
        fixtures = {row['name'] + '_tmp' for row in request['tasks']}
        expected_name = 'frozen_units_' + job
    else:
        raise ValueError('Explicit known CPU test scope required')
    if output != RUNS / expected_name:
        raise ValueError('Exact original job-owned test output required')
    policy = dict(schema='model_v3_unit_fixture_census_revision_v4', output=str(output),
                  request_identity_kind='Git_commit' if scope == 'regression' else 'raw_request_sha256',
                  request_sha256=request_sha, declared_fixture_subtrees=sorted(fixtures),
                  census_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  source_pins=dict(path=str(pins_path), sha256=pins_sha),
                  production_census_modified=False, private_storage_census_modified=False,
                  semantics='Original owned lstat inventory; links never traversed; same2GiB/50000entry/RSS/wall bounds')
    return lambda root: fixture_output_bytes(root, output=output, fixtures=fixtures), policy