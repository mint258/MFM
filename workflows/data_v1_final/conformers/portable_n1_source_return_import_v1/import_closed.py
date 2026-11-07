"""Actual Main CPU import of the original Alpha return; no optimizer or release."""
import argparse
import collections
import concurrent.futures as cf
import csv
import importlib
import io
import json
import pathlib

from portable_n1_source_remaining_v1 import contract as C, runtime as R, io as I
from .paths import ReturnPaths, ALPHA_OUTPUT, ALPHA_CLAIMS, ROOT


def assignments(manifest, pair, budget):
    C.need(manifest['schema'] == 'N1_SOURCE_FINITE_REMAINING_ASSIGNMENTS_V1' and
           manifest['status'] == 'FROZEN_AWAITING_ROOT_EXACT_FINITE_SCIENCE_REVIEW' and
           pair['schema'] == 'ROOT_ACTUAL_N1_ALPHA_EXACT_PAIR_SUBMITTED_V1' and
           pair['exact_finite_molecules'] == manifest['remaining_frozen'] == 4407 and
           pair['new_QM_calls'] == 0 and pair['all_old_claims_preserved'] is True,
           'ORIGINAL_EXACT4407_FROZEN_ASSIGNMENT_AND_ACTUAL_PAIR')
    by, shards, owners = {}, {}, {}
    for shard in manifest['shards']:
        sid = shard['shard_id']
        C.need(sid not in shards, 'UNIQUE_ORIGINAL_SHARD')
        shards[sid] = set()
        for member in C.load(shard['members_reference'], C.ADMIN):
            budget.check()
            key = member['task_key']
            C.need(key not in by and member['shard_id'] == sid and
                   member['endpoint_id'] == 'alpha' and
                   key == C.task_key(member['molecule_id']) and
                   member['seed'] == C.proposed_seed(member['molecule_id']),
                   'EXACT_UNIQUE_FROZEN_MEMBER_AND_ORIGINAL_SEED')
            reserved = member['original_Main_assignment_claim_reference']
            C.need(C.ref(C.MAIN_LEDGER / (key + '.json')) == reserved,
                   'ORIGINAL_MAIN_ASSIGNMENT_RESERVATION_UNCHANGED')
            owner = C.load(reserved)
            C.need(owner['schema'] == 'N1_FOREIGN_ASSIGNMENT_RESERVED_V1' and
                   owner['task_key'] == key and owner['molecule_id'] == member['molecule_id'] and
                   owner['seed'] == member['seed'] and owner['shard_id'] == sid and
                   owner['owner_endpoint'] == shard['endpoint'] and
                   str(owner['actual_Main_export_job_id']) == str(manifest['actual_export_job_id']) and
                   owner['scientific_attempt_started'] is False and owner['automatic_retry'] is False,
                   'TRUE_FOREIGN_ASSIGNMENT_NOT_FAKE_MAIN_NATIVE_START')
            by[key], owners[key] = member, owner
            shards[sid].add(key)
        C.need(len(shards[sid]) == shard['molecules'] and
               C.value_sha(sorted(shards[sid])) == shard['task_keys_sha256'],
               'COMPLETE_ORIGINAL_SHARD_MEMBER_KEYS')
    parents = {p['shard_id']: p for p in pair['parents']}
    C.need(len(pair['parents']) == len(parents) == 2 and set(parents) == set(shards) and
           len(by) == manifest['remaining_frozen'] and
           set(str(p['job_id']) for p in parents.values()) == {'1885108', '1885109'},
           'ONLY_ACTUAL_ORIGINAL_TWO_PARENTS_AND_ALL4407_KEYS')
    for shard in manifest['shards']:
        p = parents[shard['shard_id']]
        C.need(p['uid'] == 1264 and p['endpoint'] == '218.192.171.238:22' and
               p['cpus'] == shard['cpus'] and p['node'] == shard['node'] and
               p['molecules'] == shard['molecules'], 'ACTUAL_PAIR_MATCHES_FROZEN_RESOURCE_AND_SHARD')
    return by, shards, owners, parents


def terminal(entry, receipt, parent, target):
    jid = str(receipt['actual_parent_job_id'])
    account = C.load(target(entry['actual_accounting_reference']))
    raw = C.verify(target(account['raw_sacct_reference']), 2 << 20).read_text()
    C.need(account['endpoint'] == '218.192.171.238:22' and account['uid'] == 1264 and
           account['query_returncode'] == 0, 'REAL_FOREIGN_ACCOUNTING_ENDPOINT_UID')
    found = [r for r in csv.DictReader(io.StringIO(raw), delimiter='|') if r['JobIDRaw'] == jid]
    C.need(len(found) == 1 and found[0]['UID'] == '1264' and
           found[0]['State'].split()[0] in C.TERMINAL and
           int(found[0]['AllocCPUS']) == receipt['cpus'] == parent['cpus'] and
           found[0]['NodeList'] == receipt['node'] == parent['node'],
           'ACTUAL_FOREIGN_TERMINAL_PARENT_NOT_FAKE_MAIN_JOB')
    return {'job_id': jid, 'endpoint': '218.192.171.238:22', 'actual': found[0],
            'allocated_core_seconds': int(found[0]['AllocCPUS']) * int(found[0]['ElapsedRaw']),
            'receipt_origin_reference': entry['receipt_reference'],
            'actual_Main_receipt_copy_reference': target(entry['receipt_reference']),
            'actual_accounting_reference': entry['actual_accounting_reference'],
            'native_receipt_resource_failure': receipt['resource_report']['failure'],
            'native_receipt_stop_new': receipt['resource_report']['stop_new_native']}


def read_result(result, member, owner, receipt, target, geometry, budget):
    budget.check()
    key, jid = member['task_key'], str(receipt['actual_parent_job_id'])
    task = C.load(owner['original_task_reference'], 8 << 20)
    C.need(C.value_sha(task) == member['task_sha256'], 'ORIGINAL_EXACT_TASK_SHA')
    origin = ALPHA_OUTPUT / receipt['shard_id'] / 'tasks' / key
    C.need(result['packet_reference']['path'] == str(origin / 'packet.json.gz') and
           result['worker_start_reference']['path'] == str(origin / 'worker_start.json') and
           result['native_claim_reference']['path'] == str(ALPHA_CLAIMS / (key + '.json')),
           'RESULT_LEAVES_BELONG_TO_EXACT_ORIGINAL_TASK_AND_NATIVE_LEDGER')
    packet = I.packet(target(result['packet_reference']), task, receipt['endpoint'], jid, geometry)
    start = C.load(target(result['worker_start_reference']))
    native = C.load(target(result['native_claim_reference']))
    reserved = member['original_Main_assignment_claim_reference']
    C.need(start['runtime'] == result['runtime'] == packet['runtime'] and
           start['task_key'] == native['task_key'] == result['task_key'] == key and
           native['actual_parent_job_id'] == jid and native['uid'] == 1264 and
           native['original_Main_assignment_claim_reference'] == reserved and
           native['assignment_manifest_reference'] == start['assignment_manifest_reference'] ==
           receipt['assignment_manifest_reference'] and
           start['native_claim_reference'] == result['native_claim_reference'] and
           start['original_Main_assignment_claim_reference'] == reserved and
           start['task_sha256'] == native['task_sha256'] == member['task_sha256'],
           'ACTUAL_FOREIGN_START_CLAIM_PACKET_OWNER_AND_SOURCE')
    return {'task_key': key, 'molecule_id': member['molecule_id'], 'seed': member['seed'],
            'original_task_reference': owner['original_task_reference'],
            'original_Main_assignment_claim_reference': reserved,
            'native_claim_origin_reference': result['native_claim_reference'],
            'native_start_origin_reference': result['worker_start_reference'],
            'native_packet_origin_reference': result['packet_reference'],
            'actual_Main_packet_copy_reference': target(result['packet_reference']),
            'native_endpoint': receipt['endpoint'], 'native_parent_job_id': jid,
            'summary': packet['summary'], 'source_supplement_present': packet['supplement'] is not None,
            'all_F64_event_and_real_second_SHA_readback': True, 'new_SCI_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=pathlib.Path)
    parser.add_argument('--startup-proof', required=True, type=pathlib.Path)
    args = parser.parse_args()
    plan, proof = R.admit(args.plan, args.startup_proof, 'import')
    C.need(plan['schema'] == 'N1_SOURCE_RETURN_IMPORT_PLAN_V1' and
           plan['endpoint']['id'] == 'main' and plan['cpus'] == 16,
           'ACTUAL_MAIN16_CPU_ORIGINAL_RETURN_IMPORT_ONLY')
    out = C.literal(plan['output_directory'])
    C.need(ROOT in out.parents and not out.exists(), 'NEW_OWN_IMPORT_OUTPUT')
    manifest = C.load(plan['assignment_manifest_reference'])
    pair = C.load(plan['actual_submitted_pair_reference'])
    target = ReturnPaths(plan, manifest)
    C.need(not any(pathlib.Path(p) == out or pathlib.Path(p) in out.parents
                   for p in target.prefixes.values()), 'IMPORT_OUTPUT_OUTSIDE_ALL_READONLY_COPY_TREES')
    out.mkdir(parents=True)
    budget = R.Budget(plan, proof, out)
    budget.check()
    by, shards, owners, parents = assignments(manifest, pair, budget)
    geometry = importlib.import_module('workflows.data_v1_final.conformers.common').geometry_sha
    rows, states, closed, observed_shards = [], [], [], set()
    for entry in plan['closed_native_parents']:
        budget.check()
        receipt = C.load(target(entry['receipt_reference']), C.ADMIN)
        sid = receipt['shard_id']
        C.need(sid in parents and sid not in observed_shards, 'EACH_ORIGINAL_NATIVE_SHARD_ACCOUNTED_ONCE')
        observed_shards.add(sid)
        parent = parents[sid]
        C.need(entry['receipt_reference']['path'] == str(ALPHA_OUTPUT / sid / 'receipt.json') and
               receipt['schema'] == 'N1_FOREIGN_FINITE_SHARD_RECEIPT_V1' and
               str(receipt['actual_parent_job_id']) == str(parent['job_id']) and
               receipt['run_plan_reference'] == parent['plan_reference'] and
               receipt['startup_proof_reference'] == parent['startup_proof_reference'] and
               receipt['assignment_manifest_reference'] == plan['assignment_manifest_reference'] and
               receipt['endpoint'] == next(s['endpoint'] for s in manifest['shards'] if s['shard_id'] == sid) and
               receipt['all_started_native_tasks_drained'] is True and
               receipt['signals_sent'] is False and receipt['automatic_retry'] is False and
               receipt['new_QM_calls'] == 0 and receipt['ordinary_N_changed'] is False and
               receipt['common_or_physical_map_release'] is False,
               'TRUE_ORIGINAL_DRAINED_FINITE_RECEIPT_AND_PAIR_NOT_NEW_PRODUCER')
        closed.append(terminal(entry, receipt, parent, target))
        groups = {'RETURNED_NATIVE_PACKET': set(), 'STARTED_OR_DISPATCH_UNKNOWN_NO_RETRY': set(),
                  'UNSTARTED_PRESERVED_NO_RETRY': set(), 'ALREADY_CONSUMED_NATIVE_CLAIM_NO_RETRY': set()}
        details = {}
        for label, values in ((list(groups)[1], receipt['errors']),
                              (list(groups)[2], receipt['unstarted_keys']),
                              (list(groups)[3], receipt['already_consumed_native_claims'])):
            for original in values:
                key = original if type(original) is str else original['task_key']
                C.need(key in shards[sid] and key not in groups[label], 'UNIQUE_ORIGINAL_RECEIPT_STATE_KEY')
                groups[label].add(key)
                details[key] = original
                if label == 'ALREADY_CONSUMED_NATIVE_CLAIM_NO_RETRY':
                    C.need(original['claim_reference']['path'] == str(ALPHA_CLAIMS / (key + '.json')),
                           'CONSUMED_CLAIM_FROM_ORIGINAL_NATIVE_LEDGER')
                    C.need(C.load(target(original['claim_reference']))['task_key'] == key,
                           'PRESERVED_ACTUAL_CONSUMED_NATIVE_CLAIM')
        with cf.ThreadPoolExecutor(max_workers=16) as pool:
            pending = set()
            def settle(done):
                for future in done:
                    row = future.result()
                    rows.append(row)
            indices = set()
            for index in receipt['result_index_references']:
                C.need(pathlib.PurePosixPath(index['path']).parent ==
                       pathlib.PurePosixPath(str(ALPHA_OUTPUT / sid / 'result_indices')) and
                       index['path'] not in indices, 'EXACT_UNIQUE_ORIGINAL_RESULT_INDEX_PREFIX')
                indices.add(index['path'])
                with C.verify(target(index), check=budget.check).open() as stream:
                    for line in stream:
                        budget.check()
                        result = json.loads(line)
                        key = result['task_key']
                        C.need(key in shards[sid] and key not in groups['RETURNED_NATIVE_PACKET'],
                               'NO_DUPLICATE_OR_OTHER_SHARD_NATIVE_RESULT')
                        groups['RETURNED_NATIVE_PACKET'].add(key)
                        pending.add(pool.submit(read_result, result, by[key], owners[key], receipt, target, geometry, budget))
                        if len(pending) >= 16:
                            done, pending = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
                            settle(done)
            settle(pending)
        flat = [key for group in groups.values() for key in group]
        C.need(len(flat) == len(set(flat)) and set(flat) == shards[sid],
               'COMPLETE_DISJOINT_RETURNED_UNKNOWN_UNSTARTED_CONSUMED_PARTITION')
        for label, keys in groups.items():
            for key in sorted(keys):
                states.append({'task_key': key, 'molecule_id': by[key]['molecule_id'],
                               'shard_id': sid, 'status': label,
                               'receipt_origin_reference': entry['receipt_reference'],
                               'original_receipt_state': details.get(key),
                               'original_Main_assignment_claim_reference': by[key]['original_Main_assignment_claim_reference'],
                               'automatic_retry': False, 'physical_geometry_accepted': False})
    C.need(observed_shards == set(shards) and len(states) == len(by) and
           len({r['task_key'] for r in rows}) == len(rows), 'WHOLE_ORIGINAL4407_PARTITION_NOT_SCIENTIFIC_SUCCESS')
    rows.sort(key=lambda r: r['task_key'])
    states.sort(key=lambda r: r['task_key'])
    index = budget.write(out / 'foreign_N1_closed_result_index.jsonl', b''.join(C.canonical(r) + b'\n' for r in rows))
    outcomes = budget.write(out / 'all4407_return_states.jsonl', b''.join(C.canonical(r) + b'\n' for r in states))
    budget.write(out / 'import.json', C.canonical({
        'schema': 'N1_SOURCE_RETURN_IMPORT_V1', 'status': 'CLOSED_SOURCE_RETURN_IMPORTED_NO_PHYSICAL_OR_COMMON_RELEASE',
        'assignment_manifest_reference': plan['assignment_manifest_reference'],
        'actual_submitted_pair_reference': plan['actual_submitted_pair_reference'],
        'source_prefix_mappings': plan['source_prefix_mappings'], 'result_index_reference': index,
        'all4407_states_reference': outcomes, 'frozen_molecules': len(by), 'returned_packets': len(rows),
        'state_counts': dict(collections.Counter(r['status'] for r in states)),
        'returned_packet_summary_status_counts': dict(collections.Counter(r['summary']['status'] for r in rows)),
        'returned_packets_with_source_supplement': sum(r['source_supplement_present'] for r in rows),
        'preexport_consumed_keys_preserved_without_reclassification': manifest['consumed_existing_keys'],
        'actual_native_parents': closed, 'new_SCI_calls': 0, 'canonical_Main_assignment_claims_rewritten': False,
        'UNKNOWN_and_unstarted_not_retried': True, 'scientific_all_success_claimed': False,
        'physical_mapping_and_independent_stereo_QA': 'PENDING_SEPARATE_READONLY_CONNECTOR',
        'common_or_extra_physical_id_release': False, 'resource_report': budget.report()}) + b'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
