"""Replay genuine closed ordinary catalogs; never rerun an existing result."""
import csv
import io
import pathlib
import stat
from workflows.data_v1_final.conformers.postprocess_day_v1 import contract as C, statistics

PRIOR_KEY = 'ordinary_postprocess_resume_v1'
PRIOR_MODULE = 'workflows.data_v1_final.conformers.' + PRIOR_KEY + '.run'
TERMINAL = {'COMPLETED', 'FAILED', 'TIMEOUT', 'CANCELLED', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED'}
INPUTS = ('original_config_reference', 'closed_common_manifest_reference', 'closed_common_accounting_reference',
          'pm7_preparation_plan_reference', 'cache_plan_reference', 'pm7_owner_entry')


class Replay:
    def __init__(self):
        self.rows = {}
        self.done = set()
        self.complete = set()
        self.unknown = []
        self.interrupted = {}
        self.summary = {'source_parent_job_id': None, 'reused_closed_molecules': 0,
                        'PM7_or_RMSD_recomputed_for_reused_molecules': False}


def restore(ctx, collector, descriptors, value=None):
    value = ctx.plan.get('closed_ordinary_resume') if value is None else value
    result = Replay()
    if value is None:
        return result
    import pyarrow.parquet as pq
    jid = str(value['actual_parent_job_id'])
    C.need(jid == '4525890', 'ONLY_ACTUAL_PRIOR_ORDINARY_4525890')
    old = ctx.read(value['plan_reference'])
    proof = ctx.read(value['startup_proof_reference'])
    req = proof['request']
    account = ctx.read(value['accounting_reference'])
    C.need(account['query_returncode'] == 0 and account['uid'] == 1278 and
           account['endpoint'] == '202.38.247.57:22', 'REAL_PRIOR_NATIVE_ACCOUNTING_REQUIRED')
    raw = ctx.require(account['raw_sacct_reference']).read_text(encoding='utf-8')
    native = [r for r in csv.DictReader(io.StringIO(raw), delimiter='|') if r['JobIDRaw'] == jid]
    C.need(len(native) == 1 and native[0]['State'].split()[0] in TERMINAL and native[0]['UID'] == '1278'
           and native[0]['AllocCPUS'] == '16' and native[0]['NodeList'] == old['node'],
           'PRIOR_REALLY_TERMINAL_UID16CPU_NODE_NO_C0_INVENTION')
    root = pathlib.Path(old['output_directory'])
    C.need(str(proof['job_id']) == jid and proof['uid'] == 1278 and req['scope_key'] == PRIOR_KEY
           and req['cpus'] == 16 and req['node'] == old['node'] and req['execution_argv'] ==
           [C.PY, '-B', '-m', PRIOR_MODULE, '--plan', value['plan_reference']['path'],
            '--root-preflight', value['startup_proof_reference']['path'], '--output', str(root)],
           'EXACT_ORIGINAL_PRIOR_PLAN_PROOF_ARGV_OWNER')
    C.need(all(old[k] == ctx.plan[k] for k in INPUTS), 'SAME_ORIGINAL_POPULATION_HOF_COMMON_AND_SOURCE_COMPONENTS')
    old_sources = {r['path']: C.F.triple(r) for r in req['source_references']}
    for ref in ctx.plan['source_references']:
        if '/conformers/postprocess_day_v1/' in ref['path']:
            C.need(old_sources.get(ref['path']) == C.F.triple(ref), 'UNCHANGED_ORIGINAL_SCIENCE_SOURCE_BYTES')
    checkpoints = {}
    for ref in value['checkpoint_references']:
        C.need(pathlib.Path(ref['path']).parent == root / 'checkpoints', 'EXACT_OLD_CHECKPOINT_ROOT')
        item = ctx.read(ref)
        cursor = item['cursor']
        ordinal = cursor['descriptor_ordinal']
        C.need(type(ordinal) is int and 0 <= ordinal < len(descriptors)
               and ordinal not in checkpoints and str(item['actual_parent_job_id']) == jid
               and cursor['descriptor'] == descriptors[ordinal], 'GENUINE_ORIGINAL_DESCRIPTOR_CHECKPOINT')
        checkpoints[ordinal] = cursor
    C.need(sorted(checkpoints) == list(range(len(checkpoints))), 'CONTINUOUS_PRIOR_DESCRIPTOR_PREFIX')
    incomplete = [n for n, c in checkpoints.items() if not c['descriptor_complete']]
    C.need(not incomplete or incomplete == [max(checkpoints)], 'ONLY_FINAL_PRIOR_DESCRIPTOR_MAY_BE_PARTIAL')
    catalog_by_index = {}
    for ref in value['catalog_part_references']:
        path = pathlib.Path(ref['path'])
        C.need(path.parent == root / 'catalog_parts' and path.suffix == '.parquet'
               and path.stem.isdecimal(), 'EXACT_OLD_CLOSED_CATALOG_ROOT')
        ordinal = int(path.stem)
        C.need(ordinal in checkpoints and ordinal not in catalog_by_index, 'ONE_CATALOG_PER_RECORDED_DESCRIPTOR')
        catalog_by_index[ordinal] = ref
    packet_paths = set()
    for ordinal in sorted(checkpoints):
        cursor = checkpoints[ordinal]
        rows = []
        if cursor['attempted_current_parent']:
            C.need(ordinal in catalog_by_index, 'EVERY_COMPLETED_RESULT_HAS_POSITIVE_CLOSED_CATALOG')
            for batch in pq.ParquetFile(ctx.require(catalog_by_index[ordinal])).iter_batches(batch_size=1024):
                rows.extend(batch.to_pylist())
        C.need(len(rows) == cursor['attempted_current_parent'], 'ORIGINAL_ATTEMPT_AND_CATALOG_COUNT_AGREE')
        if cursor['descriptor_complete']:
            C.need(len(rows) == descriptors[ordinal]['molecules'], 'COMPLETE_ORIGINAL_DESCRIPTOR_COUNT')
            result.complete.add(ordinal)
        for row in rows:
            ctx.check()
            mid = row['molecule_id']
            C.need(mid not in result.done and str(row['runtime']['job_id']) == jid and
                   row['runtime']['uid'] == 1278 and row['runtime']['node'] == old['node'], 'ORIGINAL_UNIQUE_CLOSED_WORKER_OWNER')
            claim_ref = row['claim_reference']
            claim = ctx.read(claim_ref)
            key = claim['key']
            ref = row['packet_reference']
            C.need(claim['schema'] == 'ORDINARY_READONLY_CONTINUATION_CLAIM_V1'
                   and pathlib.Path(claim_ref['path']) == root / 'claims' / (key + '.json')
                   and pathlib.Path(ref['path']) == root / 'molecules' / (key + '.json.gz')
                   and claim['job_id'] == jid and claim['uid'] == 1278 and claim['node'] == old['node']
                   and claim['molecule_id'] == mid and claim['output_directory'] == str(root)
                   and claim['plan_reference'] == value['plan_reference']
                   and claim['closed_common_component_reference'] == ctx.plan['closed_common_manifest_reference']
                   and claim['Native_once_written'] is False and claim['new_UFF_or_QM'] is False,
                   'ORIGINAL_CLOSED_CLAIM_SOURCE_AND_OUTPUT_BINDING')
            packet = statistics.packet(ctx, ref)
            start = ctx.read(packet['worker_start_reference'])
            C.need(packet['molecule_id'] == mid and packet['runtime'] == row['runtime']
                   and packet['status'] == row['status'] and packet['claim_reference'] == claim_ref
                   and packet['common'] == claim['ordinary_D7'] and packet['new_UFF_calls'] == packet['new_QM_calls'] == 0
                   and packet['production_once_written'] is False and start['claim_reference'] == claim_ref
                   and start['molecule_id'] == mid and start['job_id'] == jid and start['uid'] == 1278
                   and start['node'] == old['node'] and start['pid'] == row['runtime']['pid'],
                   'ORIGINAL_PACKET_START_RUNTIME_AND_NO_NATIVE_REEXECUTION')
            cache = packet.get('cache')
            if cache is not None:
                C.need(C.F.sha_value(cache['source_records']) == claim['original_records_SHA']
                       and C.F.sha_value(cache['hof_by_record']) == claim['canonical_HOF_SHA'],
                       'EXACT_ORIGINAL_SOURCE_RECORDS_AND_CANONICAL_HOF')
            # Rebuild only derived statistics/orders through the unchanged method.
            # The original packet reader above binds provenance; add retains its
            # original readback. Neither path invokes PM7/RMSD/geometry orders.
            collector.add(ref, mid, claim['ordinary_D7'])
            if row['status'] == 'READONLY_MOLECULE_UNKNOWN':
                result.unknown.append(dict(molecule_id=mid, packet_reference=ref, source_parent_job_id=jid))
            else:
                C.need(row['status'] == 'DURABLE_READONLY_MOLECULE_RESULT', 'ORIGINAL_CLOSED_RESULT_STATUS')
            result.done.add(mid)
            packet_paths.add(pathlib.Path(ref['path']))
        result.rows[ordinal] = rows
    adoption_reference = value.get('orphan_adoption_reference')
    if adoption_reference is not None:
        adoption_path = pathlib.Path(adoption_reference['path'])
        C.need(C.ROOT / 'control' in adoption_path.parents and root not in adoption_path.parents,
               'NEW_CONTROL_ADOPTION_NOT_A_REWRITTEN_OLD_ARTIFACT')
        adoption = ctx.read(adoption_reference, 32 << 20)
        C.need(adoption['schema'] == 'ORDINARY_CLOSED_ORPHAN_ADOPTION_V1'
               and adoption['source_parent_job_id'] == jid
               and adoption['prior_plan_reference'] == value['plan_reference']
               and adoption['prior_startup_proof_reference'] == value['startup_proof_reference']
               and adoption['actual_parent_accounting'] == native[0]
               and adoption['frozen_roster_reference'] == C.meta(ctx.plan['cache_plan_reference'])['whole_molecule_roster']
               and adoption['original_catalog_part_references'] == value['catalog_part_references']
               and adoption['original_checkpoint_references'] == value['checkpoint_references']
               and adoption['original_receipt_reference'] == value.get('receipt_reference')
               and adoption['original_failure_reference'] == value.get('failure_reference')
               and adoption['old_output_or_checkpoint_rewritten'] is False
               and adoption['new_UFF_calls'] == adoption['new_QM_calls'] == 0,
               'ACTUAL_SAME_TERMINAL_SOURCE_ORPHAN_ADOPTION_NOT_OLD_CHECKPOINT')
        for item in adoption['closed_orphans']:
            ordinal, row = item['descriptor_ordinal'], item['catalog_row']
            C.need(type(ordinal) is int and 0 <= ordinal < len(descriptors)
                   and item['descriptor'] == descriptors[ordinal]
                   and row['molecule_id'] not in result.done, 'UNIQUE_REAL_ORPHAN_DESCRIPTOR_MEMBER')
            packet, claim = check_closed_row(ctx, value, row)
            collector.add(row['packet_reference'], row['molecule_id'], claim['ordinary_D7'])
            result.rows.setdefault(ordinal, []).append(row)
            result.done.add(row['molecule_id'])
            packet_paths.add(pathlib.Path(row['packet_reference']['path']))
            if packet['status'] == 'READONLY_MOLECULE_UNKNOWN':
                result.unknown.append(dict(molecule_id=row['molecule_id'], packet_reference=row['packet_reference'],
                                           source_parent_job_id=jid, original_status=packet['status']))
        for item in adoption['resource_interrupted_readonly']:
            C.need(item['status'] == 'RESOURCE_INTERRUPTED_READONLY' and item['molecule_id'] not in result.done
                   and item['molecule_id'] not in result.interrupted
                   and item['descriptor'] == descriptors[item['descriptor_ordinal']],
                   'ONE_UNCLOSED_READONLY_ATTEMPT_NOT_A_SCIENTIFIC_RETRY')
            claim = check_claim(ctx, value, item['claim_reference'])
            C.need(claim['molecule_id'] == item['molecule_id'], 'INTERRUPTED_CLAIM_MEMBER')
            result.interrupted[item['molecule_id']] = dict(item, original_claim=claim)
        result.unknown.extend(adoption['original_unknowns'])
        for item in adoption['unresolved_existing_outputs']:
            result.unknown.append(item)
            packet_paths.add(pathlib.Path(item['path']))
    # Every old output is either a genuine catalog/adopted packet or an explicit
    # preserved UNKNOWN. A missing packet is never silently counted completed.
    for path in (root / 'molecules').iterdir():
        info = path.lstat()
        C.need(stat.S_ISREG(info.st_mode) and info.st_uid == 1278 and not path.is_symlink()
               and path in packet_paths, 'UNCATALOGED_PRIOR_OUTPUT_REQUIRES_ADOPTION_NO_RECOMPUTATION')
    if value.get('receipt_reference'):
        receipt = ctx.read(value['receipt_reference'], 32 << 20)
        C.need(str(receipt['job_id']) == jid and receipt['plan_reference'] == value['plan_reference'], 'SAME_PRIOR_RECEIPT')
        if adoption_reference is None:
            result.unknown.extend(receipt.get('unknown', []))
    if result.unknown:
        ctx.stop = ctx.stop or 'REUSED_ORIGINAL_SOURCE_OR_SCIENTIFIC_UNKNOWN_HOLD'
    result.summary = dict(source_parent_job_id=jid, actual_parent_accounting=native[0],
                          prior_plan_reference=value['plan_reference'],
                          prior_startup_proof_reference=value['startup_proof_reference'],
                          prior_catalog_part_references=value['catalog_part_references'],
                          prior_checkpoint_references=value['checkpoint_references'],
                          orphan_adoption_reference=adoption_reference,
                          resource_interrupted_readonly_molecules=len(result.interrupted),
                          reused_closed_molecules=len(result.done), prior_unknown_evidence_entries=len(result.unknown),
                          PM7_or_RMSD_recomputed_for_reused_molecules=False,
                          old_input_bytes_granted_new_output_quota_credit=False)
    return result


def inspect_parent(ctx, value):
    """Closed metadata only; no requested or invented terminal state."""
    identity = tuple((value[k]['path'], value[k]['bytes'], value[k]['sha256'])
                     for k in ('plan_reference', 'startup_proof_reference', 'accounting_reference'))
    cached = getattr(ctx, '_ordinary_prior_inspection', None)
    if cached is not None and cached[0] == identity:
        return cached[1]
    jid = str(value['actual_parent_job_id'])
    C.need(jid == '4525890', 'ONLY_ORIGINAL_ORDINARY_PARENT')
    old = ctx.read(value['plan_reference'])
    proof = ctx.read(value['startup_proof_reference'])
    account = ctx.read(value['accounting_reference'])
    C.need(account['query_returncode'] == 0 and account['uid'] == 1278
           and account['endpoint'] == '202.38.247.57:22', 'REAL_NATIVE_CLOSED_ACCOUNTING')
    raw = ctx.require(account['raw_sacct_reference']).read_text(encoding='utf-8')
    rows = [r for r in csv.DictReader(io.StringIO(raw), delimiter='|') if r['JobIDRaw'] == jid]
    C.need(len(rows) == 1 and rows[0]['State'].split()[0] in TERMINAL and rows[0]['UID'] == '1278'
           and rows[0]['AllocCPUS'] == '16' and rows[0]['NodeList'] == old['node'], 'ACTUAL_TERMINAL_SOURCE_NOT_RUNNING')
    root = pathlib.Path(old['output_directory'])
    req = proof['request']
    C.need(str(proof['job_id']) == jid and proof['uid'] == 1278 and req['scope_key'] == PRIOR_KEY
           and req['execution_argv'] == [C.PY, '-B', '-m', PRIOR_MODULE, '--plan', value['plan_reference']['path'],
               '--root-preflight', value['startup_proof_reference']['path'], '--output', str(root)]
           and all(old[k] == ctx.plan[k] for k in INPUTS), 'ORIGINAL_PROOF_ARGV_AND_SAME_FROZEN_INPUTS')
    ctx._ordinary_prior_proof = proof
    ctx._ordinary_prior_inspection = identity, (old, root, rows[0])
    return ctx._ordinary_prior_inspection[1]


def check_claim(ctx, value, reference):
    old, root, native = inspect_parent(ctx, value)
    claim = ctx.read(reference)
    C.need(claim['schema'] == 'ORDINARY_READONLY_CONTINUATION_CLAIM_V1'
           and pathlib.Path(reference['path']) == root / 'claims' / (claim['key'] + '.json')
           and claim['job_id'] == str(value['actual_parent_job_id']) and claim['uid'] == 1278
           and claim['node'] == old['node'] and claim['output_directory'] == str(root)
           and claim['plan_reference'] == value['plan_reference']
           and claim['closed_common_component_reference'] == ctx.plan['closed_common_manifest_reference']
           and claim['Native_once_written'] is False and claim['new_UFF_or_QM'] is False,
           'ORIGINAL_READONLY_CLAIM_AND_FROZEN_COMMON_SOURCE')
    return claim


def check_closed_row(ctx, value, row):
    old, root, native = inspect_parent(ctx, value)
    claim_ref = row['claim_reference']
    claim = check_claim(ctx, value, claim_ref)
    ref = row['packet_reference']
    C.need(pathlib.Path(ref['path']) == root / 'molecules' / (claim['key'] + '.json.gz'), 'EXACT_ORIGINAL_PACKET_LEAF')
    packet = statistics.packet(ctx, ref)
    start = ctx.read(packet['worker_start_reference'])
    C.need(packet['molecule_id'] == claim['molecule_id'] == row['molecule_id']
           and packet['runtime'] == row['runtime'] and packet['claim_reference'] == claim_ref
           and str(packet['runtime']['job_id']) == str(value['actual_parent_job_id'])
           and packet['runtime']['uid'] == 1278 and packet['runtime']['node'] == old['node']
           and packet['status'] == row['status'] and packet['common'] == claim['ordinary_D7']
           and packet['new_UFF_calls'] == packet['new_QM_calls'] == 0 and packet['production_once_written'] is False
           and start['claim_reference'] == claim_ref and start['molecule_id'] == claim['molecule_id']
           and start['job_id'] == claim['job_id'] and start['uid'] == 1278 and start['node'] == old['node']
           and start['pid'] == packet['runtime']['pid'] and start['boot_id'] == ctx._ordinary_prior_proof['boot_id'],
           'EXACT_ORIGINAL_CLOSED_PACKET_CLAIM_START_RUNTIME')
    cache = packet.get('cache')
    if cache is not None:
        C.need(C.F.sha_value(cache['source_records']) == claim['original_records_SHA']
               and C.F.sha_value(cache['hof_by_record']) == claim['canonical_HOF_SHA'], 'ORIGINAL_RECORD_AND_HOF_HASHES')
    C.need(packet['status'] in ('DURABLE_READONLY_MOLECULE_RESULT', 'READONLY_MOLECULE_UNKNOWN'), 'ORIGINAL_RESULT_OR_PRESERVED_UNKNOWN')
    return packet, claim


def interrupted_claim(result, task, d7):
    item = result.interrupted.get(task['meta']['molecule_id'])
    if item is None:
        return None
    claim = item['original_claim']
    C.need(claim['cache_key'] == task['cache_key'] and claim['ordinary_D7'] == (d7 is not None)
           and claim['original_records_SHA'] == C.F.sha_value(task['records'])
           and claim['canonical_HOF_SHA'] == C.F.sha_value(task['hof']),
           'RESOURCE_INTERRUPTED_READONLY_CAN_ONLY_CONTINUE_IDENTICAL_FROZEN_INPUTS')
    return item['claim_reference']


def boundary_stop(ctx):
    """A request consumed only after this new runner drains a descriptor."""
    path = ctx.out / 'stop_after_descriptor.json'
    if not path.exists():
        return False
    info = path.lstat()
    C.need(stat.S_ISREG(info.st_mode) and info.st_uid == 1278 and info.st_nlink == 1
           and info.st_size <= 65536 and not path.is_symlink(), 'OWN_SMALL_DESCRIPTOR_STOP_REQUEST')
    import json
    value = json.loads(path.read_text(encoding='utf-8'))
    C.need(str(value['job_id']) == ctx.job_id and value['stop_after_current_descriptor'] is True,
           'EXACT_THIS_PARENT_DESCRIPTOR_DRAIN_REQUEST')
    ctx.stop = ctx.stop or 'REQUESTED_DESCRIPTOR_BOUNDARY_DRAIN'
    return True
