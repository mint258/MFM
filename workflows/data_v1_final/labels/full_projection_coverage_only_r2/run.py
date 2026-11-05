"""Closed producer evidence plus first base-Z read; local index, Lustre catalog."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat

from workflows.data_v1_final.labels.normalization_compact_day_v1 import io as OLD_IO
from workflows.data_v1_final.labels.normalization_compact_day_v1 import lineage as L, closed_projection_reuse as A
from workflows.data_v1_final.execution.cpu_account100_queue_v1.runtime import require_startup
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity, ref

from . import catalog as P

KEY = 'full_projection_coverage_only_v1'
MODULE = 'workflows.data_v1_final.labels.full_projection_coverage_only_r2.run'
HERE = Path(__file__).resolve().parent
RUN = Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
MIB, GIB = 1 << 20, 1 << 30


def need(value, message):
    if not value:
        raise ValueError(message)


def scope(plan):
    return dict(purpose='FULL_CLOSED_TYPED_PROJECTION_COVERAGE_ONLY_NO_COMMON_FIT',
                failed_closed_projection_reuse_reference=plan['failed_closed_projection_reuse_reference'],
                requested_cpus=plan['requested_cpus'], node=plan['node'],
                control_directory=plan['control_directory'], output_directory=plan['output_directory'],
                local_workspace_directory=plan['local_workspace_directory'],
                resource_binding=plan['resource_binding'],
                source_records=11231854, source_molecules=1220466, task_slots=14, fields=146,
                coverage_implementation='CLOSED_PRODUCER_EVIDENCE_AND_FIRST_BASE_READ',
                original_full_numeric_coverage_executed=False, label_typed_values_reopened=False,
                producer_closed_window_evidence_reused=True, statistics_performed=False,
                original_WP5_or_LMDB_reprojection=False, typed_parts_copied=False,
                new_UFF_calls=0, new_QM_calls=0, final_Common_or_D4=False)


def fresh(path, parent, direct=False):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and not path.exists()
         and (path.parent == parent if direct else parent in path.parents)
         and not any(p.is_symlink() for p in (path, *path.parents)), 'FRESH_LITERAL_OWN_OUTPUT:' + str(path))
    path.mkdir(parents=True, mode=0o700)
    need(path.stat().st_uid == 1278, 'ACTUAL_OWN_OUTPUT_UID1278')
    return path


def save(path, value):
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    with Path(path).open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    return ref(path)


def publish_catalog(source, destination, budget):
    """SQLite's storage-only VACUUM INTO; no row/column transformation or copy of cache parts."""
    need(not destination.exists(), 'FRESH_FINAL_CATALOG')
    partial = destination.with_suffix('.sqlite.partial')
    need(not partial.exists(), 'FRESH_VACUUM_TARGET')
    connection = sqlite3.connect(str(source))
    try:
        def progress():
            budget.check()
            return 0
        connection.set_progress_handler(progress, 10000)
        connection.execute('VACUUM INTO ?', (str(partial),))
    finally:
        connection.close()
    budget.check()
    info = partial.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == 1278 and info.st_nlink == 1
         and not partial.is_symlink(), 'CLOSED_OWN_VACUUM_OUTPUT')
    # Hash this formal output while its FD and inode frame remain fixed.
    # No old input or typed cache part is copied or repinned here.
    digest = hashlib.sha256()
    with partial.open('rb') as stream:
        before = os.fstat(stream.fileno())
        for block in iter(lambda: stream.read(MIB), b''):
            budget.check(); digest.update(block)
        after = os.fstat(stream.fileno())
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) == tuple(identity(partial)),
             'VACUUM_OUTPUT_FD_FRAME_STABLE')
        os.fsync(stream.fileno())
    os.replace(partial, destination)
    directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return dict(path=str(destination), bytes=info.st_size, sha256=digest.hexdigest())


def execute(plan, proof, plan_reference, proof_reference, budget):
    """Callable logic entry; budget is Root's real generic100 new-KEY binding."""
    control = Path(plan['control_directory'])
    need(control.is_absolute() and RUN / 'control' in control.parents and control.is_dir()
         and control.stat().st_uid == 1278 and not any(p.is_symlink() for p in (control, *control.parents)),
         'ACTUAL_OWN_MAIN_CONTROL_DIRECTORY')
    # resource_runtime alone creates this fresh private directory and marker.
    local = Path(budget.local_workspace_directory)
    need(local == Path(plan['local_workspace_directory']) and local.parent == Path('/dev/shm')
         and local.is_dir() and local.stat().st_uid == 1278 and not local.is_symlink(),
         'ACTUAL_RESOURCE_CREATED_PRIVATE_LOCAL_WORKSPACE')
    # SQLite spill files belong to the same observed 32GiB private workspace.
    # Keep 512MiB outside the derived SQLite page ceiling for its journal and
    # metadata; no unobserved system-/tmp spill is allowed.
    os.environ['SQLITE_TMPDIR'] = str(local)
    os.environ['TMPDIR'] = str(local)
    output = fresh(plan['output_directory'], Path('/lfshome/zixiao'))
    budget.check()
    # These functions validate the original closed FAILED/C0/timeout history.
    # They do not instantiate the obsolete day resource Budget or admit scope.
    authority, old_plan, cfg = A.authority(plan['failed_closed_projection_reuse_reference'])
    need(plan['prior_hash_stage_reference'] == old_plan['prior_hash_stage_reference']
         and plan['failed_prefix_recovery_reference'] == old_plan['failed_prefix_recovery_reference'],
         'KEEP_ORIGINAL_FAILED_AND_HASH_STAGE_ANCESTRY')
    need(cfg['mode'] == 'full' and cfg['codec_schema'] == 'COMPACT_TYPED_BINARY_JSON_V3', 'ORIGINAL_FULL_TYPED_V3_ONLY')
    # Local workspace is only a new derived index, never a fake closed authority.
    L.bind(proof, plan_reference, local, cfg)
    registered = []
    for reference in authority['closed_projection_references']:
        budget.check()
        manifest = OLD_IO.load(OLD_IO.require(reference))
        A.projection_header(manifest, cfg)
        registered.append(L.register(reference, prior_root=old_plan['output_directory']))
    need(registered == cfg['batch_history'][3:], 'EXACT_ORIGINAL_FIVE_ORDERED_CLOSED_COMPONENTS')
    cfg = copy.deepcopy(cfg)
    cfg.update(whole_output_cap_bytes=plan['resource_binding']['local_workspace_cap_bytes'],
               config_path=str(output / 'coverage_config.json'))
    config_reference = save(cfg['config_path'], cfg)
    workspace = local / 'coverage'; workspace.mkdir(mode=0o700)
    gate = authority['actual_parent']['day_fixture_gate']
    coverage = P.execute(cfg, proof, workspace, gate, budget)
    need(coverage['schema'] == P.SCHEMA and coverage['status'] == P.STATUS
         and coverage['producer_closed_window_evidence_reused'] is True
         and coverage['independent_numeric_replay_performed'] is False
         and coverage['label_typed_values_reopened'] is False
         and coverage['errors'] == coverage['quality_hold_fields'] == [],
         'ACTUAL_PRODUCER_EVIDENCE_COVERAGE_NOT_INDEPENDENT_LABEL_REPLAY')
    budget.check()
    final_catalog = publish_catalog(workspace / 'numeric_catalog.sqlite', output / 'numeric_catalog.sqlite', budget)
    coverage.update(parts_catalog=final_catalog, base_index=final_catalog, config=config_reference)
    coverage_reference = save(output / 'manifest.json', coverage)
    budget.check()
    receipt = dict(schema='FULL_PROJECTION_PRODUCER_EVIDENCE_COVERAGE_PARENT_RECEIPT_V1',
                   status='PRODUCER_EVIDENCE_COVERAGE_CLOSED_PENDING_ACTUAL_PARENT_ACCOUNTING',
                   job_id=str(proof['job_id']), uid=1278, node=proof['request']['node'], actual_cpus=proof['request']['cpus'],
                   plan_reference=plan_reference, startup_proof_reference=proof_reference,
                   coverage_reference=coverage_reference, parts_catalog=final_catalog,
                   closed_projection_reuse_authority=plan['failed_closed_projection_reuse_reference'],
                   preserved_old_parent_job_id=authority['old_job_id'], preserved_old_parent_state=authority['old_parent_state'],
                   closed_projection_references=authority['closed_projection_references'],
                   original_fixture_gate_reference=gate, fixture_scope='HISTORICAL_ORIGINAL_SOURCE6_NOT_REEXECUTED',
                   typed_parts_copied=False, original_WP5_or_LMDB_reprojected=False, coverage_base_index_rebuilt=True,
                   producer_closed_window_evidence_reused=True, original_full_numeric_coverage_executed=False,
                   independent_numeric_replay_performed=False, label_typed_values_reopened=False,
                   input_whole_file_hashes_recomputed=False, base_Z_first_read_performed=True,
                   storage_only_VACUUM_INTO=True, statistics_performed=False, normalization_completed=False,
                   final_Common_D4=False, new_UFF_calls=0, new_QM_calls=0, Model_ACK=False,
                   resource=budget.report())
    save(control / 'receipt.json', receipt)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True); parser.add_argument('--startup-proof', required=True)
    args = parser.parse_args()
    plan_reference, proof_reference = ref(args.plan), ref(args.startup_proof)
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    need(plan['schema'] == 'FULL_PROJECTION_COVERAGE_ONLY_PLAN_V1' and plan['scope_key'] == KEY
         and plan['scope_parameters'] == scope(plan) and plan['requested_cpus'] == 16,
         'EXACT_NEW_COVERAGE_SCOPE_NOT_PPRIME_OR_OLD_DAY')
    binding = plan['resource_binding']
    need(binding['schema'] == 'ROOT_BOUND_FULL_PROJECTION_COVERAGE_RESOURCE_V1'
         and binding['status'] == 'ROOT_BOUND_REAL_STORAGE_ADMISSION'
         and 0 < binding['output_forecast_bytes'] <= 32 * GIB
         and 512 * MIB < binding['local_workspace_cap_bytes'] <= 32 * GIB,
         'ACTUAL_NEW_SCOPE_STORAGE_BINDING_NOT_A_RESOURCE_FORECAST_ACCEPTANCE')
    argv = [A.C.A.PY, '-B', '-m', MODULE, '--plan', args.plan, '--startup-proof', args.startup_proof]
    proof = require_startup(args.startup_proof, expected_scope_key=KEY,
                            expected_scope_parameters=plan['scope_parameters'], expected_kind='analysis',
                            expected_source=Path(__file__), expected_execution_argv=argv,
                            required_references=[plan_reference, *plan['source_references']])
    need(proof['request']['cpus'] == 16 and proof['request']['node'] == plan['node']
         and {r['path']: r for r in proof['request']['data_references']} ==
             {r['path']: r for r in plan['data_references']}, 'REAL_CPU16_NODE_AND_EXACT_DATA_BINDING')
    # Root supplies the separately source-pinned NEW-KEY resource_runtime.
    # No Pprime scope resource module or old finite/day Budget is invoked.
    from . import resource_runtime
    budget = resource_runtime.start(plan, proof, plan_reference=plan_reference, proof_reference=proof_reference)
    complete = False
    try:
        result = execute(plan, proof, plan_reference, proof_reference, budget)
        complete = result == 0
        return result
    except BaseException as error:
        save(Path(plan['control_directory']) / 'failure.json',
             dict(schema='FULL_PROJECTION_PRODUCER_EVIDENCE_COVERAGE_FAILURE_V1', error=repr(error),
                  job_id=str(proof['job_id']), new_UFF_calls=0, new_QM_calls=0,
                  original_cache_unchanged=True, full_coverage_claimed=False, resource=budget.report()))
        raise
    finally:
        budget.finish()
        if complete:
            budget.cleanup_local_workspace()


if __name__ == '__main__':
    raise SystemExit(main())
