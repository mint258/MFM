"""Metadata-only actual196/183/200 input collector; no scientific-body reads."""
import argparse
import hashlib
import json
from pathlib import Path
from ..alpha_runtime_v1 import common as Q

N = 1196122
VERSION = 'alpha-original502-generic3642-recovery-v1'
ORIGINAL_NAMES = ('engine.py', 'cache.py', 'workers.py', 'run.py', 'test_exact.py', 'profile_reference.py')


def read(ref):
    Q.need(ref['bytes'] <= 2 << 20, 'Small actual authority metadata only')
    return Q.load(Q.verify(ref))


def triple(ref): return {k: ref[k] for k in ('path', 'bytes', 'sha256')}


def closed(review, job):
    p = review['actual_parent']; account = read(review['actual_accounting_reference'])
    Q.need(review['reviewer'] == 'root' and p['State'] == 'COMPLETED' and p['ExitCode'] == '0:0'
        and str(p['JobIDRaw']) == job and str(p['UID']) == '1264' and p['endpoint'] == account['endpoint'] == Q.ENDPOINT
        and p in account['actual_parents'], 'Actual Alpha closed source parent/accounting required')
    Q.verify(account['raw_sacct_reference'])


def collect(profile_review_ref, reference_review_ref, baseline_review_ref):
    a, r, b = (read(x) for x in (profile_review_ref, reference_review_ref, baseline_review_ref))
    Q.need(a['schema'] == 'ROOT_ALPHA_FULL_COMMON_CACHE_PROFILE_ACTUAL_ACCEPTANCE_V1'
        and a['status'] == 'ACCEPTED_NONRELEASING_FIXED64_OPERATIONAL_PROFILE'
        and a['reference_molecules'] == N and a['measured_queries'] == 64 and a['measured_workers'] == 16,
        'Actual full-reference profile200 acceptance required')
    Q.need(r['schema'] == 'ROOT_ALPHA_FULL_COMMON_EXACT_REFERENCE_PACK_ACTUAL_ACCEPTANCE_V1'
        and r['status'] == 'APPROVED_COMPLETE_COMMON_EXACT_REFERENCE_PACK' and r['reference_molecules'] == N
        and r['original_119_recovered_members_included'] is True, 'Complete repaired Common196 accepted pack required')
    Q.need(b['schema'] == 'ROOT_ACTUAL_ALPHA_CORRECTED_BASELINE1M_V1'
        and b['status'] == 'ACCEPTED_COMPLETE_CORRECTED_PREDECON_FIXED_1M'
        and b['sample_molecules'] == 1000000 and b['population_version'] == VERSION,
        'Actual complete corrected183 baseline, never old1M/subset required')
    for review, job in ((a, '1885200'), (r, '1885196'), (b, '1885183')): closed(review, job)
    Q.need(a['reference_actual_review_reference'] == reference_review_ref
        and a['baseline_actual_review_reference'] == baseline_review_ref
        and a['reference_manifest_reference'] == r['reference_manifest_reference']
        and a['baseline_receipt_reference'] == b['producer_receipt_reference'], 'Same actual source authority graph')
    receipt = read(a['producer_receipt_reference']); plan = read(receipt['resource_plan']); startup = read(receipt['startup_proof'])
    Q.need(receipt['schema'] == 'ALPHA_EXACT_FULL_COMMON_CACHE_PROFILE_RECEIPT_V1'
        and receipt['job_id'] == str(startup['job_id']) == '1885200' and receipt['uid'] == startup['uid'] == 1264
        and receipt['reference_molecules'] == N and receipt['measured_queries'] == 64
        and plan['schema'] == 'ALPHA_FULL_COMMON_EXACT_CACHE_PROFILE_PLAN_V1' and plan['query_count'] == 64
        and plan['reference_role'] == 'before' and plan['workers'] == 16
        and startup['request']['producer_plan_reference'] == receipt['resource_plan']
        and startup['request']['execution_argv'] == plan['execution_argv']
        and receipt['reference_manifest'] == plan['reference_manifest'] == r['reference_manifest_reference']
        and receipt['baseline_receipt'] == plan['baseline_receipt'] == b['producer_receipt_reference']
        and receipt['measurements'] == a['measurements_reference'], 'Actual historical receipt/plan/startup bindings')
    measurements = read(a['measurements_reference'])
    Q.need(measurements['schema'] == 'ALPHA_EXACT_FULL_COMMON_CACHE_PROFILE_DATA_V1'
        and len(measurements['results']) == 64 and [x['query_ordinal'] for x in measurements['results']] == list(range(64))
        and len(measurements['workers']) == 16 and len({x['worker_pid'] for x in measurements['workers']}) == 16
        and all(x['reference_decode_calls'] == N for x in measurements['workers']), 'All64 historical rows and16 complete reference workers')
    prior_tests = read(r['original_math9_and_metadata3_tests_reference'])
    Q.need(prior_tests['before_DATA'] is True and prior_tests['tests'] == 12
        and prior_tests['errors'] == prior_tests['failures'] == prior_tests['skips'] == 0, 'Actual prior accepted native suite metadata')
    math_lines = [line for line in prior_tests['transcript'].splitlines() if '(workflows.expansion.exact_nn_cached_v1.test_exact.' in line]
    Q.need(len(math_lines) == 9 and all(line.endswith(' ... ok') for line in math_lines), 'Actual prior original math9 source execution evidence')
    manifest = read(r['reference_manifest_reference']); baseline = read(b['producer_receipt_reference'])
    Q.need(manifest['schema'] == 'expansion_exact_ecfp4_reference_v1' and manifest['status'] == 'COMPLETE'
        and manifest['molecules'] == N and manifest['targets_present'] is False
        and manifest['fingerprints']['bytes'] == N * 256 and manifest['keys']['bytes'] == N * 28
        and {tuple(triple(manifest[k]).values()) for k in ('fingerprints','keys','counts')}
            == {tuple(triple(x).values()) for x in r['packed_artifact_references']}, 'Root accepted complete physical pack metadata')
    common = read(manifest['input_manifest'])
    Q.need(common['common_molecules'] == N and common['current_HOLD_molecules'] == 0
        and common['final_Root_graph_review_reference'] == r['Common_actual_review_reference'], 'Full accepted Common, no partial HOLD subset')
    Q.need(baseline['schema'] == 'EXPANSION_PUBCHEM_PREDECON_BASELINE_V1' and baseline['status'] == 'COMPLETE'
        and baseline['projection']['rows'] == baseline['sample_molecules'] == 1000000
        and baseline['sample_ordinal_start'] == 0 and baseline['projection_order'] == 'sample_ordinal_ASC'
        and baseline['population_version'] == VERSION and baseline['sample_seed'] == 20261025
        and baseline['sample_hash_domain'] == 'PubChem-baseline-uniform', 'Full frozen current1M baseline order/seed/version')
    source_refs = {}
    for name in ORIGINAL_NAMES:
        refs = [x for x in plan['code_references'] if x['path'].endswith('/exact_nn_cached_v1/' + name)]
        Q.need(refs and len({(x['bytes'], x['sha256']) for x in refs}) == 1
            and all(x in startup['request']['source_references'] for x in refs), 'Unambiguous historical original source bodies: ' + name)
        for ref in refs: Q.verify(ref)
        source_refs[name] = refs
    Q.need(receipt['source'] in source_refs['profile_reference.py'], 'Historical profile implementation source bound')
    return dict(schema='ALPHA_POPCOUNT_NATIVE_VALIDATION_INPUTS_V1', status='METADATA_BOUND_NO_NEW_BUILD_OR_COMPUTE',
        profile_review_reference=profile_review_ref, reference_review_reference=reference_review_ref,
        baseline_review_reference=baseline_review_ref, historical_receipt_reference=a['producer_receipt_reference'],
        historical_plan_reference=receipt['resource_plan'], historical_startup_reference=receipt['startup_proof'],
        historical_measurements_reference=a['measurements_reference'], reference_manifest_reference=r['reference_manifest_reference'],
        baseline_receipt_reference=b['producer_receipt_reference'], original_source_references=source_refs,
        historical_native_math9_reference=r['original_math9_and_metadata3_tests_reference'],
        historical_identity_sha256=receipt['query_identity_sha256'], reference_molecules=N, query_prefix_rows=64,
        baseline_rows=1000000, full_1M_NN_or_pool_or_training_release=False)


def validate_bound(value):
    expected = collect(value['profile_review_reference'], value['reference_review_reference'], value['baseline_review_reference'])
    Q.need(value == expected, 'Collected actual inputs changed; no substituted authority/source hashes')
    return read(value['historical_measurements_reference']), read(value['historical_receipt_reference'])


def historical_queries(rows, data, receipt):
    Q.need(len(rows) == 64 and [x[0] for x in rows] == list(range(64)), 'Exactly historical prefix0..63, no missing sample')
    expected = {x['query_ordinal']: x for x in data['results']}; digest = hashlib.sha256()
    Q.need(len(expected) == 64 and set(expected) == set(range(64)), 'All historical64 fingerprint bindings required')
    for ordinal, row, raw in rows:
        Q.need(hashlib.sha256(raw).hexdigest() == expected[ordinal]['fingerprint_sha256'], 'Actual200 per-query fingerprint SHA differs')
        digest.update(json.dumps([ordinal,row['cid'],row['full_key'],raw.hex()],separators=(',',':')).encode() + b'\n')
    Q.need(digest.hexdigest() == receipt['query_identity_sha256'], 'Historical full ordered query identity digest differs')
    return digest.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('profile-review','reference-review','baseline-review','output'): p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args(); result = collect(*(Q.reference(x) for x in (a.profile_review,a.reference_review,a.baseline_review)))
    print(json.dumps(Q.write(a.output,result),sort_keys=True))


if __name__ == '__main__': main()
