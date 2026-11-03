"""Writer-only continuation of the complete merged domain from failed 4525591."""
import csv
import hashlib
import io
import json
import os
import pathlib
import stat
from . import contract as C, resume
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import domain as D, io as I

OLD_JOB = '4525591'
OLD_ROOT = C.OUTPUT / 'day07_parallel_frozen_pilot_v1_provisional'
OLD_STAGE_ROOTS = [str(C.OUTPUT / name / 'permanent_f64_source_groups') for name in
                  ('day06_parallel_frozen_pilot_v1_provisional', 'day07_parallel_frozen_pilot_v1_provisional')]


def prepare(plan, accepted, roots, root, budget):
    ref = plan['writer_only_resume_reference']
    C.need(ref in plan['source_references'] and not plan.get('closed_source_groups_resume_reference'),
           'ONE_WRITER_ONLY_PATH_NO_SOURCE_PROJECTION_RESUME')
    review = C.meta(ref)
    C.need(review['schema'] == 'ROOT_D5_4525591_WRITER_ONLY_RESUME_REVIEW_V1' and
           review['status'] == 'APPROVED_CLOSED_MERGED_DOMAIN_ONLY_NOT_PARENT_C0' and review['reviewer'] == 'root' and
           review['old_parent_job_id'] == OLD_JOB and review['old_output_root'] == str(OLD_ROOT) and
           review['old_domain_locator'] == str(OLD_ROOT / 'domain.sqlite') and
           review['old_domain_expected_bytes'] == 3508211712 and review['CPU_first_old_domain_full_SHA_authorized'] is True and
           review['old_all_source_groups_merged_before_writer'] is True and review['expected_closed_source_groups'] == 113 and
           review['closed_source_group_directories'] == OLD_STAGE_ROOTS and
           review['scientific_rules_or_source_masks_changed'] is False,
           'EXACT_4525591_COMPLETE_MERGED_DOMAIN_WRITER_ONLY_REVIEW')
    names = ('old_plan_reference', 'old_startup_proof_reference', 'old_parent_accounting_reference', 'old_source3_reference',
             'old_shared_configuration_acceptance_reference', 'old_closed_groups_log_reference', 'old_failure_reference')
    C.need(all(review[k] in plan['source_references'] for k in names), 'ALL_OLD_WRITER_FAILURE_LINEAGE_SMALL_REFS_DECLARED')
    old, proof, account, gate, shared = (C.meta(review[k]) for k in names[:5])
    C.need(old['output_directory'] == str(OLD_ROOT) and proof['uid'] == 1278 and str(proof['job_id']) == OLD_JOB and
           proof['request']['scope_key'] == C.KEY and proof['request']['cpus'] == 16 and
           proof['request']['execution_argv'] == [C.PY, '-B', '-m', C.MODULE, '--plan', review['old_plan_reference']['path'],
               '--startup-proof', review['old_startup_proof_reference']['path']], 'ACTUAL_4525591_PLAN_AND_PROOF')
    for key in ('pilot_acceptance_reference', 'D5_delivery_reference', 'shared_D3_plan_reference',
                'D1_design_policy_reference', 'D1_five_layer_reference', 'actual_geometry_manifest_reference',
                'codec_source_references', 'order_capability'):
        C.need(old[key] == plan[key], 'SAME_FROZEN_WRITER_ONLY_INPUT:' + key)
    C.need(all(gate[k] == v for k, v in dict(tests_run=3, failures=0, errors=0, skips=0,
           expected_failures=0, unexpected_successes=0).items()), 'ACTUAL_OLD_WRITER_PARENT_SOURCE3_PASS')
    raw_ref = account['raw_sacct_reference']
    C.need(C.Q.pin(raw_ref['path']) == raw_ref, 'REAL_WRITER_FAILED_RAW_ACCOUNTING_SHA')
    rows = [r for r in csv.DictReader(io.StringIO(C.Q.read_small(raw_ref['path']).decode()), delimiter='|')
            if r.get('JobIDRaw') == OLD_JOB]
    C.need(account['schema'] == 'DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['query_returncode'] == 0 and
           account['endpoint'] == '202.38.247.57:22' and account['uid'] == 1278 and len(rows) == 1 and
           rows[0]['State'].split()[0] == 'FAILED' and rows[0]['ExitCode'] == '3:0' and rows[0]['UID'] == '1278' and
           rows[0]['AllocCPUS'] == '16' and rows[0]['NodeList'] == proof['node'], 'ACTUAL_4525591_FAILED3_NOT_PARENT_C0')
    failure = C.meta(review['old_failure_reference'])
    C.need(failure['error'] == "KeyError('native_projection')" and 'write_batch' in failure['traceback'] and
           'granular_store.py' in failure['traceback'], 'EXACT_OLD_FORMAT_FAILURE_NOT_PARTIAL_SOURCE_FAILURE')
    log_ref = review['old_closed_groups_log_reference']
    C.need(pathlib.Path(log_ref['path']) == OLD_ROOT / 'closed_groups.jsonl', 'EXACT_113_GROUP_LOG_LOCATION')
    raw = C.Q.read_small(log_ref['path'])
    C.need(len(raw) == log_ref['bytes'] and hashlib.sha256(raw).hexdigest() == log_ref['sha256'], 'CLOSED113_LOG_CURRENT_CPU_SHA')
    results = [json.loads(line) for line in raw.decode().splitlines() if line]
    C.need(len(results) == len({r['key'] for r in results}) == 113, 'ALL113_UNIQUE_CLOSED_SOURCE_GROUP_RESULTS')
    for result in results:
        path = pathlib.Path(result['reference']['path'])
        C.need(result['all_handles_closed'] is True and result['new_QM_UFF_calls'] == 0 and
               str(path.parent) in OLD_STAGE_ROOTS and path.name == result['key'] + '.sqlite',
               'ONLY_EXACT_LOGGED_CLOSED113_GROUPS_NO_UNFINISHED_STORES')
    source = pathlib.Path(review['old_domain_locator'])
    C.need(not any(p.is_symlink() for p in (source, *source.parents)) and
           not any(pathlib.Path(str(source) + suffix).exists() for suffix in ('-journal', '-wal', '-shm')),
           'CLOSED_OLD_DOMAIN_REGULAR_LITERAL_WITHOUT_ACTIVE_JOURNAL')
    before = I.identity(source)
    C.need(before[2] == review['old_domain_expected_bytes'], 'EXACT_CLOSED_DOMAIN_OBSERVED_SIZE')
    target = root / 'domain.sqlite'
    digest = hashlib.sha256()
    with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as src, target.open('xb') as dst:
        frame = os.fstat(src.fileno())
        C.need(stat.S_ISREG(frame.st_mode) and frame.st_uid == 1278 and frame.st_nlink == 1 and
               [frame.st_dev, frame.st_ino, frame.st_size, frame.st_mtime_ns, frame.st_ctime_ns] == before,
               'CURRENT_CPU_OWN_SOURCE_DOMAIN_EXACT_FD')
        while True:
            budget.check()
            block = src.read(8 << 20)
            if not block:
                break
            digest.update(block)
            dst.write(block)
        dst.flush()
        os.fsync(dst.fileno())
        frame = os.fstat(src.fileno())
        C.need([frame.st_dev, frame.st_ino, frame.st_size, frame.st_mtime_ns, frame.st_ctime_ns] == before == I.identity(source),
               'CLOSED_SOURCE_DOMAIN_STABLE_DURING_COMPLETE_CPU_SHA_COPY')
    origin = dict(path=str(source), bytes=before[2], sha256=digest.hexdigest())
    copied = I.pin(target)
    C.need(copied['bytes'] == origin['bytes'] and copied['sha256'] == origin['sha256'], 'NEW_MUTABLE_DOMAIN_EXACT_FULL_BYTE_COPY')
    db = I.connect(target)
    C.need({r[0] for r in db.execute('SELECT name FROM sqlite_master WHERE type="table"')} >=
           {'molecules', 'geometries', 'orders', 'excluded', 'native_bases', 'wanted_rids', 'pieces', 'closed_groups', 'exported', 'stores'},
           'EXACT_MERGED_DOMAIN_TABLES_NOT_A_STORE_OR_PARTIAL_SOURCE_GROUP')
    actual = {r['key']: json.loads(r['ref']) for r in db.execute('SELECT key,ref FROM closed_groups')}
    operational_counts = {name: db.execute('SELECT count(*) FROM ' + name).fetchone()[0]
                          for name in ('molecules', 'native_bases', 'wanted_rids', 'pieces', 'closed_groups')}
    operational_counts['geometries_selected'] = db.execute('SELECT count(*) FROM geometries WHERE selected=1').fetchone()[0]
    C.need(actual == {r['key']: r for r in results} and operational_counts['pieces'] ==
           sum(r['pieces'] for r in results), 'ALL113_GROUP_RESULTS_EXACTLY_MERGED_IN_COPIED_DOMAIN')
    geometry = D.read(accepted['component_references']['geometry_reference'], roots)
    binding = D.register(geometry['cell_binding_reference'], roots)
    I.require(binding)
    locators = ('old_selected_diagnostic_geometry_ids_locator', 'old_diagnostic_molecule_ids_locator')
    expected = ('selected_diagnostic_geometry_ids.parquet', 'actual_seen_diagnostic_molecule_ids.parquet')
    tables = []
    for key, name in zip(locators, expected):
        path = pathlib.Path(review[key])
        C.need(path == OLD_ROOT / name, 'EXACT_PREVIOUS_CLOSED_DIAGNOSTIC_SELECTION_TABLE')
        reference = I.pin(path)
        I.add(reference, str(OLD_ROOT))
        I.require(reference)
        tables.append(reference)
    mids = db.execute('SELECT count(DISTINCT mid) FROM molecules').fetchone()[0]
    count = db.execute('SELECT count(*) FROM geometries WHERE selected=1').fetchone()[0]
    bases = db.execute('SELECT count(*) FROM geometries WHERE selected=1 AND parent IS NULL AND aux=0').fetchone()[0]
    C.need(db.execute("SELECT count(*) FROM molecules WHERE role!='TRAIN'").fetchone()[0] == 0 and count > 0 and bases == 2 * mids,
           'SAME_CLOSED_HELD_TRAIN_DOMAIN_AND_TWO_SOURCE_BASES')
    selection = dict(closed_D4_geometry_origin_reference=binding, global_D5_diagnostic_MIDs=20000,
        frozen_D3_selected_TRAIN_MIDs=50000, actual_D3_seen_TRAIN_MIDs=None,
        actual_D3_seen_status='FROZEN_ROSTER_AWAITING_INDEPENDENT_D3_PAYLOAD_CLOSURE',
        actual_seen_D5_intersection_MIDs=mids, global_D5_MIDs_outside_actual_seen_TRAIN=20000-mids,
        selected_diagnostic_geometry_ids_reference=tables[0], actual_seen_diagnostic_molecule_ids_reference=tables[1],
        selected_geometries=count, selected_bases=bases, selected_child_input_views=count-bases)
    return db, geometry, binding, selection, dict(review=review, reference=ref, results=results, shared=shared,
        old_domain_origin_reference=origin, exact_initial_mutable_copy_reference=copied,
        operational_counts=operational_counts)


def validate_and_reset(state, groups, configurations, db, root, budget):
    C.need({resume.group_key(g) for g in groups} == {r['key'] for r in state['results']} and len(groups) == 113,
           'ALL_CURRENT_LOGICAL_GROUP_KEYS_EQUAL_COMPLETE_OLD113')
    old = state['shared']
    C.need(old['schema'] == 'D5_ACTUAL_EARLY_CLOSED_D3_CONFIGURATION_ACCEPTANCE_V1' and
           old['actual_configuration_references'] == configurations and old['all_current_CPU_file_hashes_verified'] is True and
           old['new_rho_fit'] is False, 'SAME_COMPLETE_ACTUAL_D4_D5_SHARED_CONFIGURATIONS_BEFORE_WRITER')
    budget.check(force=True)
    db.execute('DELETE FROM exported')
    db.execute('DELETE FROM stores')
    db.execute('DROP TABLE IF EXISTS partitions')
    db.commit()
    for result in state['results']:
        I.append(root / 'closed_groups.jsonl', result)
    I.save(root / 'writer_only_domain_resume_acceptance.json', dict(
        schema='D5_ACTUAL_4525591_WRITER_ONLY_DOMAIN_ACCEPTANCE_V1',
        status='CPU_WHOLE_SHA_EXACT_MUTABLE_COPY_RESET_UNFINISHED_WRITER_ONLY_NOT_OLD_PARENT_C0',
        root_review_reference=state['reference'], old_parent_job_id=OLD_JOB,
        old_domain_origin_reference=state['old_domain_origin_reference'],
        initial_mutable_copy_reference=state['exact_initial_mutable_copy_reference'],
        operational_counts=state['operational_counts'], source_domain_bytes=state['old_domain_origin_reference']['bytes'],
        sum_logged_pieces=sum(r['pieces'] for r in state['results']),
        sum_closed_group_reference_bytes=sum(r['reference']['bytes'] for r in state['results']),
        all_closed_source_groups=113, current_logical_group_keys_equal=True,
        source_projection_rerun=False, old_unfinished_stores_adopted=False,
        original_geometry_native_indices_pieces_and_closed_groups_preserved=True, new_QM_UFF_calls=0))
