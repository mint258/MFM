"""Formal P-prime boundaries. This module never submits jobs or relaxes a gate."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import sys
import time

PARENT = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(PARENT))
import common as IO
from close_pilot import assess


def q(value):
    return "'" + str(value).replace("'", "''") + "'"


def load(path):
    c = json.loads(Path(path).read_text())
    expected = {'schema': 'DATA_V1_PPRIME_FORMAL_COMMON_V1', 'workers': 16,
                'formal_memory_gib': 64, 'wall_seconds': 7200,
                'batch_molecules': 512, 'conformers_per_molecule': 2,
                'order_seed': 20261025, 'minimum_success_rate': .995,
                'maximum_allocated_core_seconds_per_conformer': 11.7}
    if any(c[k] != v for k, v in expected.items()):
        raise ValueError('FORMAL_SCOPE_RESOURCE_OR_PILOT_GATE_CHANGED')
    for pin in c['parent_source_pins']:
        IO.require_pin(pin)
        if IO.digest(PARENT / Path(pin['path']).name) != pin['sha256']:
            raise ValueError('ACTUALLY_IMPORTED_PARENT_SOURCE_DIFFERS')
    IO.require_pin(c['pilot_config'])
    sys.path.insert(0,str(PARENT/'retention_v1'))
    from retention_policy_v1 import load as load_retention
    raw,_=load_retention(IO.require_pin(c['raw_policy']))
    if raw['pilot_config']!=c['pilot_config']:
        raise ValueError('FORMAL_AND_RETENTION_PILOT_AUTHORITIES_DIFFER')
    return c, IO.load_config(c['pilot_config']['path'])


def runtime(c, preflight, config_path, science=False):
    observed = IO.runtime(16, prepare=not science)
    saved = json.loads(Path(preflight).read_text())
    r = saved['request']
    if science and (r['kind'] != 'qm' or r.get('pilot') is not False or
                    r['cpus'] != 16 or r['memory_gib'] != 64 or
                    r['wall_seconds'] > 7200 or r.get('memory_basis')):
        raise ValueError('FORMAL_QM_REQUIRES_ORDINARY_16CPU64G_MAX2H_NO_PILOT_EXCEPTION')
    IO.require_preflight(preflight, config_path, c)
    return observed


def refs(value, keys):
    present = [k for k in keys if k in value]
    if len(present) != 1 or not isinstance(value[present[0]], list):
        raise ValueError('UNAMBIGUOUS_FROZEN_TABLE_REFERENCES_REQUIRED:' + str(keys))
    rows = value[present[0]]
    if not rows:
        raise ValueError('EMPTY_FROZEN_TABLE_MANIFEST')
    for pin in rows:
        IO.require_pin(pin)
    return rows


def paths_sql(pins):
    return '[' + ','.join(q(p['path']) for p in pins) + ']'


def frozen_authorities(common_pin, order_pin, map_pin):
    common = json.loads(IO.require_pin(common_pin).read_text())
    orders = json.loads(IO.require_pin(order_pin).read_text())
    mapping = json.loads(IO.require_pin(map_pin).read_text())
    for item, status in ((common, 'COMMON_POPULATION_V1_FROZEN'),
                         (orders, 'CONFORMER_ORDER_V1_FROZEN'),
                         (mapping, 'CANONICAL_GEOMETRY_MAP_V1_FROZEN')):
        if item.get('status') != status:
            raise ValueError('ACTUAL_FROZEN_COMMON_ORDERS_AND_GEOMETRY_MAP_REQUIRED')
    # Explicit common and order hashes, never infer membership from a native trace.
    if orders.get('common_manifest_sha256') != common_pin['sha256'] or mapping.get('common_manifest_sha256') != common_pin['sha256']:
        raise ValueError('COMMON_LINEAGE_NOT_BOUND_BY_ORDER_AND_GEOMETRY_MANIFESTS')
    bound = mapping.get('order_manifest', mapping.get('order_manifest_reference'))
    if bound != order_pin:
        raise ValueError('CANONICAL_MAP_MUST_BIND_EXACT_FROZEN_ORDER_MANIFEST')
    if orders.get('seed', orders.get('order_seed')) != 20261025:
        raise ValueError('FROZEN_RANDOM_ORDER_SEED_CHANGED')
    return common, refs(common, ('membership_tables',)), refs(orders, ('order_tables', 'tables')), refs(mapping, ('map_tables',))


def pilot_review(path, pilot_config):
    """Recompute gates from raw parent sacct and pinned real pilot result."""
    decision = json.loads(Path(path).read_text())
    if decision.get('schema') != 'PPRIME_REAL_PILOT_ROOT_REVIEW_V1' or decision.get('status') != 'APPROVED':
        raise ValueError('REAL_2000_PILOT_ROOT_REVIEW_REQUIRED')
    result = json.loads(IO.require_pin(decision['result']).read_text())
    IO.require_pin(decision['raw_parent_sacct'])
    if result['config'] != IO.reference(pilot_config):
        raise ValueError('PILOT_REVIEW_CONFIGURATION_CHANGED')
    rows = list(csv.DictReader(Path(decision['raw_parent_sacct']['path']).read_text().splitlines(), delimiter='|'))
    gates = assess(result, rows, IO.load_config(pilot_config))
    if not all(gates['gates'].values()) or gates['allocated_core_seconds_per_requested_conformer'] <= 0:
        raise ValueError('REAL_PILOT_FAIL_STOP_NO_FORMAL_RUN')
    if not decision.get('failure_categories_reviewed') or not decision.get('all_2000_elapsed_times_reviewed'):
        raise ValueError('ROOT_MUST_REVIEW_ALL_RECORD_TIMINGS_AND_SCIENTIFIC_FAILURES')
    for pin in result['family_parquets']:
        IO.require_pin(pin)
    times=result.get('all_2000_elapsed_seconds',[])
    if len(times)!=2000 or len({r['record_id'] for r in times})!=2000 or any(not isinstance(r['elapsed_seconds'],(int,float)) or not math.isfinite(r['elapsed_seconds']) or r['elapsed_seconds']<0 for r in times):
        raise ValueError('ALL2000_ACTUAL_FINITE_CONFORMER_ELAPSED_TIMES_REQUIRED')
    import pyarrow.parquet as pq
    qpins=[p for p in result['family_parquets'] if p.get('family')=='QC']
    if len(qpins)!=1:raise ValueError('ONE_ACTUAL_PILOT_QC_FAMILY_REQUIRED')
    quality=pq.read_table(qpins[0]['path']).to_pylist()
    if len(quality)!=2000 or {r['record_id'] for r in quality}!={r['record_id'] for r in times}:
        raise ValueError('ACTUAL_PILOT_QC_AND_TIMING_RECORD_SETS_DIFFER')
    successes=0
    for row in quality:
        statuses=json.loads(row['task_statuses_json'])
        if len(statuses)!=12 or {r['calc_type'] for r in statuses}!=set(IO.TASKS):
            raise ValueError('ALL2000_ACTUAL_QC_RECORDS_NEED_TWELVE_TASK_STATUSES')
        complete=all(r['status']=='SUCCESS' for r in statuses)
        if complete!=row['all_twelve_tasks_success']:
            raise ValueError('PILOT_QC_SUCCESS_FLAG_MISMATCH')
        successes+=complete
    if result['record_success_rate']!=successes/2000 or successes/2000<.995:
        raise ValueError('REAL_QC_SUCCESS_RATE_FAILS_99_5_PERCENT_GATE')
    IO.require_pin(result['prepared'])
    IO.require_pin(result['reproduction_manifest'])
    return decision, result, gates


def task_key(mid, atom_sha, coordinate_sha, protocol_sha, perturb_record_id):
    # WP5 perturbation seed includes record_id. It is part of the scientific
    # input identity; two IDs with identical clean xyz need different noisy tasks.
    return hashlib.sha256(IO.canonical(['pprime-twelve-once-v1', mid, atom_sha, coordinate_sha,
                                      protocol_sha, perturb_record_id])).hexdigest()


def ledger_file(c, key):
    if len(key) != 64 or any(ch not in '0123456789abcdef' for ch in key):
        raise ValueError('INVALID_ONCE_KEY')
    root = Path(c['attempt_ledger_root'])
    parent = Path(c['external_output_root'])
    if parent not in root.parents or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('ATTEMPT_LEDGER_OUTSIDE_OWN_FORMAL_ROOT')
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    return root / (key + '.json')


def begin(c, pair, evidence):
    path = ledger_file(c, pair['once_key'])
    row = {'schema': 'PPRIME_TWELVE_ONCE_ATTEMPT_V1', 'status': 'STARTED_OUTCOME_NOT_YET_CLOSED',
           'key': pair['once_key'], 'record_id': pair['record_id'],
           'canonical_geometry_id': pair['canonical_geometry_id'],
           'job_id': os.environ['SLURM_JOB_ID'], 'node': socket.gethostname(),
           'uid': os.getuid(), 'pid': os.getpid(), 'started_epoch': time.time(),
           'evidence': evidence}
    # Any existing STARTED/SUCCESS/FAILED/unknown consumes this key. Never overwrite/retry.
    IO.write_json(path, row)
    return IO.reference(path)


def require_budget(estimate, decision):
    cap = decision.get('approved_total_core_hours_cap')
    if not isinstance(cap, (int, float)) or not math.isfinite(cap) or not math.isfinite(estimate) or estimate < 0 or cap < estimate:
        raise ValueError('FINITE_ADEQUATE_ROOT_BUDGET_CAP_REQUIRED')
    if estimate > 500 and decision.get('approved_over_500_core_hours') is not True:
        raise ValueError('OVER500_CORE_HOURS_REQUIRES_EXPLICIT_ROOT_REVIEW')


def formal_review(path, plan_path, c):
    decision = json.loads(Path(path).read_text())
    if decision.get('schema') != 'PPRIME_FORMAL_ROOT_REVIEW_V1' or decision.get('status') != 'APPROVED':
        raise ValueError('EXPLICIT_ROOT_FORMAL_REVIEW_REQUIRED')
    plan = json.loads(Path(plan_path).read_text())
    if decision.get('plan') != IO.reference(plan_path):
        raise ValueError('FORMAL_REVIEW_PLAN_SHA_MISMATCH')
    for name in ('common_manifest', 'order_manifest', 'geometry_manifest', 'pilot_review'):
        if decision[name] != plan[name]:
            raise ValueError('FORMAL_REVIEW_AUTHORITY_MISMATCH:' + name)
        IO.require_pin(decision[name])
    IO.require_pin(decision['pilot_import'])
    pilot_review(decision['pilot_review']['path'], c['pilot_config']['path'])
    require_budget(plan['estimated_allocation_core_hours'], decision)
    scope = decision.get('approved_scope')
    if scope not in {'ALL_COMMON', 'BASELINE_READY_COMMON_SUBSET'}:
        raise ValueError('EXPLICIT_BASELINE_OR_FULL_COMMON_SCOPE_REQUIRED')
    if plan['pending_two_real_geometries'] and scope == 'ALL_COMMON':
        raise ValueError('N1_UNRESOLVED_FULL_COMMON_NOT_AUTHORIZABLE')
    if decision.get('n1_expanded_view_approved'):
        raise ValueError('N1_EXTENSION_NOT_IMPLEMENTED_OR_ACCEPTED_BY_BASELINE_VALIDATOR')
    return decision, plan
