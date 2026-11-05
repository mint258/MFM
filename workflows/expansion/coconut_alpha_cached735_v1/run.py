"""Allocated complete735 cached-representation diagnosis; never an index release."""
import argparse
import collections
import concurrent.futures as cf
import io
import json
import multiprocessing as mp
import os
import sys
import traceback
import unittest
from pathlib import Path
from . import kernel as K, support as S


def admit(plan, proof, plan_path, proof_path):
    from workflows.expansion.alpha_runtime_v1 import profile
    authority = profile.admit(plan, minimum_workers=16)
    req = proof['request']
    S.need(plan['schema'] == 'COCONUT_ALPHA_CACHED735_PLAN_V1'
           and plan['scope_key'] == req['scope_key'] == 'coconut_alpha_cached735_v1'
           and req['producer_plan_reference'] == S.pin(plan_path), 'EXACT_ROOT_DIAGNOSTIC_PLAN')
    argv = req['execution_argv']
    S.need(argv == plan['execution_argv'] and argv[argv.index('--plan') + 1] == str(plan_path)
           and argv[argv.index('--startup-proof') + 1] == str(proof_path)
           and sys.argv[-4:] == ['--plan', str(plan_path), '--startup-proof', str(proof_path)],
           'EXACT_CURRENT_CLI_AND_ROOT_REQUEST')
    S.need(proof['endpoint'] == plan['endpoint'] == '218.192.171.238:22'
           and proof['uid'] == plan['uid'] == os.getuid() == 1264
           and str(proof['job_id']) == os.environ.get('SLURM_JOB_ID')
           and proof['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
           'CURRENT_ALPHA_PARENT_BOOT_AND_UID')
    approved = {r['path']:r for r in req['source_references']}
    for file in Path(__file__).parent.glob('*.py'):
        S.need(approved.get(str(file.absolute())) == S.pin(file), 'EXACT_CURRENT_DIAGNOSTIC_SOURCE')
    for ref in req['source_references']:
        S.read(ref, 2 << 20)
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    return authority


def parent(plan):
    receipt = S.load(plan['native735_receipt_reference'])
    S.need(receipt['schema'] == 'COCONUT_ALPHA_NATIVE735_PRODUCER_V1'
           and receipt['result']['schema'] == 'COCONUT_ALPHA_NATIVE735_DIAGNOSTIC_V1'
           and receipt['result']['status'] == 'ORIGINAL735_NATIVE_FIELDS_OBSERVED_NOT_EXCLUSION_ACCEPTANCE'
           and receipt['result']['DATA']['rows'] == 735
           and receipt['profile_admission']['endpoint'] == '218.192.171.238:22'
           and receipt['profile_admission']['uid'] == 1264
           and receipt['profile_admission']['job_id'] == '1885146'
           and receipt['result']['original_graph_UNKNOWN_retained'] is True
           and receipt['result']['native_formula_or_ID_association_accepted'] is False,
           'ACTUAL_NATIVE735_UNACCEPTED_SOURCE_PRODUCER')
    account = S.load(plan['native735_actual_accounting_reference'])
    parents = account.get('actual_parents', [account.get('actual_parent', {})])
    selected = [p for p in parents if str(p.get('JobIDRaw')) == '1885146']
    S.need(account['endpoint'] == '218.192.171.238:22' and account['uid'] == 1264
           and account['query_returncode'] == 0 and len(selected) == 1
           and selected[0]['State'] == 'COMPLETED' and selected[0]['ExitCode'] == '0:0'
           and str(selected[0]['UID']) == '1264' and selected[0]['User'] == 'alpha',
           'ROOT_ACTUAL_NATIVE735_TERMINAL_C0_NOT_SELF_CLAIMED')
    original_plan = S.load(receipt['plan'])
    S.need(plan['original_source_root'] == original_plan['original_source_root']
           and plan['original_source_references'] == original_plan['original_source_references'],
           'SAME_NATIVE735_ORIGINAL_ALPHA_FROZEN_SOURCES')
    ref = receipt['result']['DATA']
    raw = S.read(ref)  # Machine receipt is the sole DATA SHA authority, never a hand-copied literal.
    S.need(raw.endswith(b'\n'), 'CLOSED_COMPLETE_NATIVE_JSONL')
    records = [json.loads(line) for line in raw.splitlines()]
    S.need(len(records) == ref['rows'] == 735, 'ALL_AND_ONLY_ORIGINAL735_SOURCE_ROWS')
    source_ids = [(r['source']['source_table'], r['source']['copy_block'],
                   r['source']['source_row_ordinal']) for r in records]
    S.need(len(set(source_ids)) == 735, 'EXACT_NO_DUPLICATE_PHYSICAL_SOURCE_ROW')
    return records, ref, receipt


def source_tests(out):
    from .test_source import Source
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Source)
    transcript = io.StringIO()
    tested = unittest.TextTestRunner(stream=transcript, verbosity=2).run(suite)
    ref = S.save(out / 'source_tests.json', dict(tests=tested.testsRun,
        failures=len(tested.failures), errors=len(tested.errors), skips=len(tested.skipped),
        transcript=transcript.getvalue(), before_DATA=True))
    S.need(tested.wasSuccessful() and tested.testsRun == 7 and not tested.skipped,
           'SEVEN_NATIVE_SOURCE_AND_BOUNDARY_FIXTURES_BEFORE_DATA')
    return ref


def execute(plan, out, guard):
    records, data_ref, old_receipt = parent(plan)
    destination = out / 'cached735_complete_representation_observations.DATA.jsonl'
    counts = collections.Counter(); workers = collections.Counter(); pending = collections.deque()
    with destination.open('xb') as target, cf.ProcessPoolExecutor(max_workers=plan['workers'],
            mp_context=mp.get_context('spawn'), initializer=K.initialize, initargs=(plan,)) as pool:
        def collect():
            result = pending.popleft().result(); guard.check()
            S.need(result['original_UNKNOWN_unchanged'] is True and result['strict5_written'] is False,
                   'NO_DIAGNOSTIC_OBSERVATION_PROMOTED')
            target.write(S.canonical(result)); counts['physical_rows'] += 1
            workers[result['worker_pid']] += 1
            for key, value in result['diagnostic_availability'].items():
                counts['row_availability/' + key] += bool(value)
            for key, value in result['literal_comparisons'].items():
                counts['literal_comparison/' + key + '/' + str(value)] += 1
            if result['mixed_CSV_observation'] is not None:
                counts['original_id174178_whole_source_observed'] += 1
            for v in result['variants']:
                counts['variants'] += 1
                counts['variant/' + v['variant_id'] + '/input/' + v['text_reference']['state']] += 1
                atoms = v.get('unsanitized_atom_observation', {})
                keys = v.get('key_observation', {})
                for name, value in [('atom_state', atoms.get('state', 'NOT_CALLED')),
                                    ('key_state', keys.get('state', 'NOT_CALLED'))]:
                    counts['variant/' + v['variant_id'] + '/' + name + '/' + value] += 1
                if atoms.get('positive_known_non_H_atom_lower_bound_observation'):
                    counts['variant_with_positive_known_atom_lower_bound'] += 1
                if atoms.get('query_atom_indices') or atoms.get('dummy_atom_indices') or atoms.get('query_bond_indices'):
                    counts['variant_with_query_or_dummy_evidence'] += 1
                if any(o.get('state') == 'DIAGNOSTIC_EXCEPTION_UNKNOWN_RETAINED' for o in (atoms, keys)):
                    counts['variants_with_diagnostic_exception_UNKNOWN'] += 1
        for ordinal, record in enumerate(records, 1):
            guard.check()
            record['native735_source_record_reference'] = dict(DATA_reference=data_ref,
                                                              record_ordinal_1based=ordinal)
            # Read only the already isolated complete original row, never rescan the38GB SQL.
            S.read(record['opaque_original_row_reference'], 8 << 20)
            pending.append(pool.submit(K.work, record))
            if len(pending) >= 2 * plan['workers']:
                collect()
        while pending:
            collect()
        target.flush(); os.fsync(target.fileno())
    S.need(counts['physical_rows'] == 735 and counts['variants'] == 735 * 11
           and counts['original_id174178_whole_source_observed'] == 1,
           'COMPLETE735_ELEVEN_SOURCE_VARIANTS_EACH_NO_SILENT_DROP')
    guard.check()
    return dict(schema='COCONUT_ALPHA_CACHED735_DIAGNOSTIC_V1',
                status='COMPLETE_CACHED_REPRESENTATION_OBSERVATIONS_NOT_EXCLUSION_ACCEPTANCE',
                DATA=dict(S.pin(destination), rows=735), counts=dict(counts),
                actual_nonempty_worker_rows=dict(workers), native735_DATA_reference=data_ref,
                native735_receipt_reference=plan['native735_receipt_reference'],
                native735_actual_accounting_reference=plan['native735_actual_accounting_reference'],
                original_normalize_source_fields_not_synthetic=True,
                original_graph_UNKNOWN735_retained=True, original_recipe_objects_unchanged=True,
                source_variants_merged_as_identical_graphs=False, native_formula_derived=False,
                lower_bounds_or_full_keys_accepted=False, strict5_rows_written=0,
                all11_ready=False, global_pool_release=False, source_rows_changed=False,
                new_UFF_QM_network_calls=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--startup-proof', type=Path, required=True)
    args = parser.parse_args(); plan = json.loads(args.plan.read_text()); proof = json.loads(args.startup_proof.read_text())
    authority = admit(plan, proof, args.plan, args.startup_proof)
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    guard = Guard(plan); out = Path(plan['output_directory'])
    try:
        guard.check(); out.mkdir(parents=True, exist_ok=False)
        kernel_proof = K.initialize(plan); tests = source_tests(out)
        kernel_ref = S.save(out / 'actual_frozen_kernel_proof.json', kernel_proof)
        result = execute(plan, out, guard)
        S.save(out / 'receipt.json', dict(schema='COCONUT_ALPHA_CACHED735_PRODUCER_V1',
            plan=S.pin(args.plan), startup_proof=S.pin(args.startup_proof), source_tests=tests,
            kernel_proof=kernel_ref, profile_admission=authority, result=result,
            runtime=guard.receipt(), actual_parent_C0_pending_root_readback=True,
            all11_ready=False, global_pool_release=False))
    except BaseException as exc:
        if out.is_dir():
            S.save(out / 'failure.json', dict(error=repr(exc), traceback=traceback.format_exc(),
                original_UNKNOWN_unchanged=True, partials_retained=True, no_exclusion_acceptance=True))
        raise
    finally:
        guard.close()


if __name__ == '__main__':
    main()
