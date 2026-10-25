"""Immutable references and explicit resource boundaries for the P-prime pilot."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import time
import re
from datetime import datetime

sys.dont_write_bytecode = True
TASKS = ('pm7_B', 'pm7_water', 'pm7_octanol', 'pm7_cation', 'pm7_anion',
         'xtb_singlepoint', 'xtb_vipea', 'xtb_vfukui', 'xtb_ALPB_water',
         'xtb_ALPB_octanol', 'xtb_fod', 'xtb_perturbed_gradient')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def reference(path):
    path = Path(path).absolute()
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}


def require_pin(pin, full_hash=True):
    path = Path(pin['path'])
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError('ABSOLUTE_REGULAR_PIN_REQUIRED:' + str(path))
    if 'bytes' in pin and path.stat().st_size != pin['bytes']:
        raise ValueError('PIN_SIZE_CHANGED:' + str(path))
    if full_hash and digest(path) != pin['sha256']:
        raise ValueError('PIN_SHA_CHANGED:' + str(path))
    return path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def staging_bytes(value):
    """Portable JSON staging preserves exceptional float bits without pickle/NaN tokens."""
    import math
    def convert(v):
        if isinstance(v, float) and not math.isfinite(v):
            return {'__pprime_nonfinite_float64__': struct.pack('<d', v).hex()}
        if isinstance(v, dict):
            return {str(k): convert(x) for k, x in v.items()}
        if isinstance(v, (tuple, list)):
            return [convert(x) for x in v]
        return v
    return canonical(convert(value))


def read_staging(line):
    def hook(v):
        if set(v) == {'__pprime_nonfinite_float64__'}:
            return struct.unpack('<d', bytes.fromhex(v['__pprime_nonfinite_float64__']))[0]
        return v
    return json.loads(line, object_hook=hook)


def write_json(path, value):
    path = Path(path)
    payload = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                         allow_nan=False).encode('utf-8') + b'\n'
    with path.open('xb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return reference(path)


def stable_key(seed, molecule_id, source, conformer_id):
    # Byte-identical to SB-2 selection.stable_key; a test protects this contract.
    text = f'data-v1-conformer-order:{seed}:{molecule_id}:{source}:{conformer_id}'
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def ordered_two(rows, mid, seed=20261025):
    ids = [r['sprime_conf_idx'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('DUPLICATE_SPRIME_CONFORMER_ID')
    if any(r['status'] != 'SUCCESS' or r['converged'] is not True for r in rows):
        raise ValueError('NONUSABLE_SPRIME_CONFORMER')
    if len(rows) < 2:
        raise ValueError('TWO_DISTINCT_UFF_CONFORMERS_REQUIRED')
    return sorted(rows, key=lambda r: (stable_key(seed, mid, 'uff_sprime',
                                                r['sprime_conf_idx']),
                                       str(r['sprime_conf_idx'])))[:2]


def runtime(workers=16, prepare=False):
    node = socket.gethostname().split('.')[0]
    allowed = {'compute-0-20'} if prepare else {f'compute-0-{n}' for n in range(14, 20)}
    allocated = int(os.environ.get('SLURM_CPUS_PER_TASK', '0'))
    if not os.environ.get('SLURM_JOB_ID') or node not in allowed:
        raise RuntimeError('OWN_SLURM_ALLOCATION_AND_APPROVED_NODE_REQUIRED')
    if allocated < 16 or workers != 16 or workers > allocated:
        raise RuntimeError('SIXTEEN_ALLOCATED_AND_EFFECTIVE_WORKERS_REQUIRED')
    return {'job_id': os.environ['SLURM_JOB_ID'], 'node': node,
            'allocated_cpus': allocated, 'workers': workers}


def load_config(path):
    c = json.loads(Path(path).read_text(encoding='utf-8'))
    if c['schema'] != 'DATA_V1_PPRIME_PILOT_V1':
        raise ValueError('UNKNOWN_PPRIME_CONFIGURATION')
    expected = {'molecules': 1000, 'conformers_per_molecule': 2, 'order_seed': 20261025,
                'workers': 16, 'minimum_success_rate': 0.995,
                'maximum_allocated_core_seconds_per_conformer': 11.7}
    if any(c[k] != v for k, v in expected.items()):
        raise ValueError('PILOT_SCOPE_OR_GATE_CHANGED')
    for pin in c['small_authority_pins']:
        require_pin(pin)
    return c


def require_preflight(path, config_path, config):
    """Consume the existing Root submitter intent/receipt; no additional approval flow."""
    receipt = json.loads(Path(path).read_text())
    request = receipt['request']
    if reference(config_path) not in request['source_references']:
        raise ValueError('ROOT_PREFLIGHT_CONFIG_SHA_MISMATCH')
    age = time.time() - datetime.fromisoformat(receipt['observed_at']).timestamp()
    if not 0 <= age <= 3600:
        raise ValueError('ROOT_PREFLIGHT_OLDER_THAN_ONE_HOUR')
    if request['node'] != socket.gethostname().split('.')[0]:
        raise ValueError('ROOT_PREFLIGHT_NODE_MISMATCH')
    if not isinstance(receipt['existing_jobs_all_users'], list):
        raise ValueError('ALL_USERS_MEMORY_CHECK_REQUIRED')
    memory = re.search(r'(?:^|\s)RealMemory=(\d+)(?:\s|$)', receipt['node_metadata'])
    if memory is None or receipt['committed_memory_mib'] + request['memory_gib'] * 1024 > .85 * int(memory[1]):
        raise ValueError('NODE_DECLARED_MEMORY_EXCEEDS_85_PERCENT')
    if request['estimated_peak_output_bytes'] < config['max_output_bytes']:
        raise ValueError('ROOT_OUTPUT_ESTIMATE_SMALLER_THAN_PILOT_CAP')
    if receipt['account_free_bytes'] - config['max_output_bytes'] < config['quota_reserve_bytes']:
        raise ValueError('QUOTA_REMAINING_WOULD_FALL_BELOW_200_GB')
    return reference(path)


def load_engine(config):
    contract = json.loads(require_pin(config['legacy_contract']).read_text())
    protocol = json.loads(require_pin(contract['protocol']).read_text())
    if tuple(t['name'] for t in protocol['tasks']) != TASKS:
        raise ValueError('EXACT_TWELVE_TASK_RECIPE_REQUIRED')
    if protocol['perturb_sigma_A'] != 0.1 or protocol['seed'] != 20261010:
        raise ValueError('PERTURBATION_RECIPE_CHANGED')
    names = {'wp5_engine_v3.py', 'wp5_parser_v2.py', 'wp5_parquet_v2.py',
             'wp5_archive_v5.py', 'wp5_archive_v4.py', 'wp5_scf_metadata_v2.py',
             'wp5_registry_coverage_v2.py'}
    selected = {Path(p['path']).name: p for p in contract['sources']
                if Path(p['path']).name in names}
    if set(selected) != names:
        raise ValueError('LEGACY_ENGINE_DEPENDENCIES_NOT_PINNED')
    for pin in selected.values():
        require_pin(pin)
    for pin in protocol['frozen_dependencies'].values():
        require_pin(pin)
    require_pin(contract['registry'])
    engine_path = Path(selected['wp5_engine_v3.py']['path'])
    # Import only; never execute the old runner, queue, submitter or main function.
    sys.path.insert(0, str(engine_path.parent))
    spec = importlib.util.spec_from_file_location('_pprime_wp5_engine_v3', engine_path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine, contract, protocol


def new_output(path, config):
    root, path = Path(config['external_output_root']), Path(path)
    if not path.is_absolute() or root not in path.parents:
        raise ValueError('NEW_EXTERNAL_OUTPUT_CHILD_REQUIRED')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('OUTPUT_SYMLINK_REJECTED')
    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    return path


def output_guard(root, config, reserve=0):
    total = 0
    for path in [Path(root), *Path(root).rglob('*')]:
        info = path.lstat()
        if info.st_uid != os.getuid() or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise RuntimeError('OUTPUT_OWNERSHIP_OR_TYPE_CHANGED')
        total += info.st_size
    if total + reserve > config['max_output_bytes']:
        raise RuntimeError('PPRIME_OUTPUT_CAP_EXCEEDED')
    return total
