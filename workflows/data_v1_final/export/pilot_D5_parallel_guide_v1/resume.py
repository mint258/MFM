"""One explicit continuation: closed source groups from failed parent 4525590."""
import csv
import hashlib
import io
import json
import pathlib
from . import contract as C
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import io as I

OLD_JOB = '4525590'
OLD_ROOT = C.OUTPUT / 'day06_parallel_frozen_pilot_v1_provisional'


def group_key(group):
    return hashlib.sha256(json.dumps(group, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load(plan, groups, configurations, root, budget):
    reference = plan.get('closed_source_groups_resume_reference')
    if reference is None:
        return []
    C.need(reference in plan['source_references'], 'EXPLICIT_ROOT_CLOSED_GROUP_REVIEW_IN_SOURCE_CLOSURE')
    review = C.meta(reference)
    C.need(review['schema'] == 'ROOT_D5_4525590_CLOSED_SOURCE_GROUP_REUSE_REVIEW_V1' and
           review['status'] == 'APPROVED_CLOSED_SOURCE_GROUPS_ONLY_NOT_PARENT_C0' and review['reviewer'] == 'root' and
           review['old_parent_job_id'] == OLD_JOB and review['old_output_root'] == str(OLD_ROOT) and
           review['old_source_groups_directory'] == str(OLD_ROOT / 'permanent_f64_source_groups') and
           review['expected_closed_source_groups'] == 101 and review['old_all_source_merges_deferred'] is True and
           review['scientific_rules_or_source_masks_changed'] is False,
           'ONLY_REVIEWED_4525590_DEFERRED_MERGE_101_CLOSED_GROUPS')
    names = ('old_plan_reference', 'old_startup_proof_reference', 'old_parent_accounting_reference',
             'old_source3_reference', 'old_shared_configuration_acceptance_reference', 'old_closed_groups_log_reference')
    C.need(all(review[k] in plan['source_references'] for k in names), 'ALL_ACTUAL_OLD_PARENT_METADATA_DECLARED')
    old, proof, account, gate, shared = (C.meta(review[k]) for k in names[:-1])
    C.need(old['output_directory'] == str(OLD_ROOT) and proof['uid'] == 1278 and str(proof['job_id']) == OLD_JOB and
           proof['request']['scope_key'] == C.KEY and proof['request']['cpus'] == 16 and
           proof['request']['execution_argv'] == [C.PY, '-B', '-m', C.MODULE, '--plan',
               review['old_plan_reference']['path'], '--startup-proof', review['old_startup_proof_reference']['path']],
           'ACTUAL_FAILED_4525590_PLAN_PROOF_NOT_4525589_RACE_OUTPUT')
    for key in ('pilot_acceptance_reference', 'D5_delivery_reference', 'shared_D3_plan_reference',
                'D1_design_policy_reference', 'D1_five_layer_reference', 'actual_geometry_manifest_reference',
                'codec_source_references', 'order_capability'):
        C.need(old[key] == plan[key], 'UNCHANGED_FROZEN_CLOSED_GROUP_SOURCE_IDENTITY:' + key)
    C.need(all(gate[k] == v for k, v in dict(tests_run=3, failures=0, errors=0, skips=0,
           expected_failures=0, unexpected_successes=0).items()), 'ACTUAL_OLD_SOURCE3_PASS')
    C.need(shared['schema'] == 'D5_ACTUAL_EARLY_CLOSED_D3_CONFIGURATION_ACCEPTANCE_V1' and
           shared['actual_configuration_references'] == configurations and shared['all_current_CPU_file_hashes_verified'] is True and
           shared['new_rho_fit'] is False, 'SAME_ACTUAL_SHARED_CONFIGURATION_NOT_OLD_GUESSED_FAMILY')
    raw_ref = account['raw_sacct_reference']
    C.need(C.Q.pin(raw_ref['path']) == raw_ref, 'ACTUAL_FAILED_4525590_RAW_ACCOUNTING_PIN')
    rows = [r for r in csv.DictReader(io.StringIO(C.Q.read_small(raw_ref['path']).decode()), delimiter='|')
            if r.get('JobIDRaw') == OLD_JOB]
    C.need(account['schema'] == 'DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['query_returncode'] == 0 and
           account['endpoint'] == '202.38.247.57:22' and account['uid'] == 1278 and len(rows) == 1 and
           rows[0]['State'].split()[0] == 'FAILED' and rows[0]['ExitCode'] == '3:0' and
           rows[0]['UID'] == '1278' and rows[0]['AllocCPUS'] == '16' and rows[0]['NodeList'] == proof['node'],
           'REAL_EXTERNAL_FAILED3_4525590_NO_PARENT_C0_PROMOTION')
    parents = [p for p in account['parents'] if p['job_id'] == OLD_JOB]
    C.need(len(parents) == 1 and parents[0]['state'] == 'FAILED' and parents[0]['exit_code'] == '3:0' and
           parents[0]['alloc_cpus'] == 16 and parents[0]['node'] == proof['node'] and
           parents[0]['elapsed_raw_seconds'] == int(rows[0]['ElapsedRaw']), 'FAILED_ACCOUNTING_ROW_MATCHES_RAW')
    log_ref = review['old_closed_groups_log_reference']
    C.need(pathlib.Path(log_ref['path']) == OLD_ROOT / 'closed_groups.jsonl', 'ONLY_ACTUAL_4525590_CLOSED_LOG')
    raw = C.Q.read_small(log_ref['path'])
    C.need(len(raw) == log_ref['bytes'] and hashlib.sha256(raw).hexdigest() == log_ref['sha256'], 'CLOSED_LOG_CURRENT_CPU_FULL_SHA')
    results = [json.loads(line) for line in raw.decode().splitlines() if line]
    C.need(len(results) == 101 and len({r['key'] for r in results}) == 101, 'EXACT101_UNIQUE_CLOSED_GROUP_RECORDS')
    current = {group_key(g): g for g in groups}
    C.need(len(current) == len(groups), 'CURRENT_LOGICAL_SOURCE_GROUP_KEYS_UNIQUE')
    for result in results:
        budget.check()
        ref = result['reference']
        C.need(result['key'] in current and result['all_handles_closed'] is True and result['new_QM_UFF_calls'] == 0 and
               type(result['pieces']) is int and result['pieces'] >= 0 and
               pathlib.Path(ref['path']) == OLD_ROOT / 'permanent_f64_source_groups' / (result['key'] + '.sqlite') and
               ref in plan['data_references'], 'EXACT_CLOSED_SOURCE_STAGE_AND_CURRENT_LOGICAL_GROUP_NOT_UNKNOWN_PARTIAL')
        I.add(ref, str(OLD_ROOT))
        I.require(ref)  # First actual full FD/SHA check is on this admitted CPU.
    I.save(root / 'closed_source_group_resume_acceptance.json', dict(
        schema='D5_ACTUAL_4525590_CLOSED_SOURCE_GROUP_RESUME_ACCEPTANCE_V1',
        status='CURRENT_CPU_HASHED_CLOSED_GROUPS_ONLY_NOT_OLD_PARENT_C0',
        root_review_reference=reference, old_parent_job_id=OLD_JOB, closed_source_groups=101,
        same_actual_D4_D5_and_shared_configurations=True, original_source3_and_source_readback_unchanged=True,
        unknown_or_unlogged_partial_groups_adopted=0, source_QM_UFF_calls=0))
    return results
