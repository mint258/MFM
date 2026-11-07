"""Closed D3/D4/D5 only; no future receipt, role invention or second D3 release."""
import pathlib
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import contract as O, io as I
from workflows.data_v1_final.export.common_day_parent_v1 import parent as A

Q, ROOT, REPO, PY, need, meta, reference = O.Q, O.ROOT, O.REPO, O.PY, O.need, O.meta, O.reference
KEY = 'pilot_D3_diagnostic_supplement_census_v3'
STORE_NAMESPACE = 'pilot_D3_diagnostic_supplement_v1'  # Unchanged wire/consumer format, not producer identity.
MODULE = 'workflows.data_v1_final.export.' + KEY + '.run'
HERE = REPO / 'workflows/data_v1_final/export' / KEY
OUTPUT = ROOT / 'artifacts/labels/source_status_v1' / KEY
ROLE = 'TRAIN_UNSEEN_CONFORMATION'
FILES = ('__init__.py', 'contract.py', 'domain.py', 'source.py', 'verify.py', 'run.py', 'close.py', 'README.md')


def parameters(plan):
    return {'domain': 'ACTUAL_D3_SEEN_TRAIN_INTERSECT_FORMAL_D5_HELD_TARGETS', 'sample_role': ROLE,
            'workers': 16, 'pending': 32, 'wall_seconds': 86400,
            'whole_output_cap_bytes': plan['whole_output_cap_bytes'], 'fields': 146,
            'source_roundtrip': 'ALL_IF_LESS_THAN10000_ELSE_ORIGINAL_DETERMINISTIC10000',
            'source_masks_unchanged': True, 'training_excluded': True, 'new_QM_UFF_calls': 0,
            'r674': 'ORIGINAL_VALUES_MASKS_LOSS_OFF', 'r73': 'ORIGINAL_ORDERED_NATIVE_RECORDS',
            'permanent_F64_and_original_once_F32': True, 'full_Common_D6_Model_ACK': False}


def parents(plan):
    d3, norm, d5 = (meta(plan[k]) for k in ('D3_export_reference', 'D4_normalization_reference', 'D5_delivery_reference'))
    need(d3['schema'] == 'DATA_V1_PILOT_D3_FORMAL_EXPORT_DELIVERY_V1' and
         norm['schema'] == 'DATA_V1_PILOT_D4_FORMAL_NORMALIZATION_DELIVERY_V1' and
         d5['schema'] == 'DATA_V1_D5_PROVISIONAL_DELIVERY_V1' and
         d3['version'] == norm['version'] == d5['version'] == 'v1-pilot-provisional' and
         d3['status'] == norm['status'] == d5['status'] == 'DELIVERED_PROVISIONAL_SCOPE_NOT_FINAL_COMMON',
         'ACTUAL_FORMAL_PROVISIONAL_D3_D4_D5_REQUIRED')
    receipt = meta(d3['actual_D3_receipt_reference'])
    proof = meta(receipt['startup_proof_reference'])
    prior = meta(receipt['plan_reference'])
    need(receipt['schema'] == 'BOUNDED_PILOT_FAMILY_D3_RECEIPT_V1' and receipt['errors'] == [] and
         receipt['source_roundtrip_records'] == 10000 and receipt['pilot_counts'] == {'TRAIN': 50000, 'VAL': 5000} and
         receipt['all_Family_SQLite_Sidecar_and_spawn_reader_handles_closed'] is True and
         proof['request']['scope_key'] == O.KEY and proof['request']['execution_argv'][3] == O.MODULE and
         proof['request']['cpus'] == 16 and proof['uid'] == 1278 and
         str(proof['job_id']) == str(receipt['job_id']) == d3['actual_D3_parent_job_id'],
         'EXACT_RESUME_FAST55K_D3_C0_CLOSED_HANDLES_SOURCE_QA_NOT_OLD_PARTIAL_ALIAS')
    A.account(d3['actual_parent_accounting_reference'], receipt['job_id'], proof['node'], 16)
    need(norm['actual_D3_receipt_reference'] == d3['actual_D3_receipt_reference'] and
         norm['actual_D4_acceptance_reference'] == receipt['pilot_acceptance_reference'] == plan['pilot_acceptance_reference'] and
         norm['fit_role'] == 'TRAIN' and norm['fit_pilot_molecules'] == 50000 and norm['VAL_used_for_fitting'] is False,
         'EXACT_SAME_ACTUAL_D4_STATISTICS_NO_REFIT_OR_DIAGNOSTIC_FIT')
    accepted = meta(receipt['pilot_acceptance_reference'])
    components = accepted['component_references']
    need(norm['statistics_reference'] == components['numeric_repetitions'][0] and
         norm['independent_equal_replay_reference'] == components['numeric_repetitions'][1] and
         norm['r674_report_reference'] == components['r674_report_reference'] and
         norm['population_reference'] == components['population_reference'] and
         prior['bounded_export_review_reference'] == plan['bounded_export_review_reference'] and
         accepted['actual_parent']['manifest'] == plan['pilot_parent_manifest_reference'],
         'SAME_FROZEN_D3_CONFIGURATION_AND_FAST55K_READER_CHAIN')
    d4_receipt = meta(accepted['actual_parent']['manifest'])
    old = meta(d4_receipt['plan_reference'])
    A.account(accepted['actual_parent']['accounting'], d4_receipt['job_id'], meta(accepted['actual_parent']['proof'])['node'], 16)
    d5_acceptance = meta(d5['actual_acceptance_reference'])
    chain = d5_acceptance['actual_parent']
    d5_receipt, d5_proof = meta(chain['manifest']), meta(chain['proof'])
    A.account(chain['accounting'], d5_receipt['job_id'], d5_proof['node'], 16)
    need(d5_acceptance['schema'] == 'ROOT_ACCEPTED_BOUNDED_OLD_COMPLETE_D5_COMPONENTS_V1' and
         d5_acceptance['status'] == 'ACTUAL_C0_OLD_COMPLETE_D5_COMPONENTS_ACCEPTED_NOT_FINAL_COMMON' and
         str(d5_receipt['job_id']) == str(d5_proof['job_id']) == '4525184' and d5_proof['uid'] == 1278 and
         d5['components']['diagnostic_TRAIN_molecules'] == 20000,
         'ORIGINAL_ACTUAL_D5_20K_TARGETS_NOT_A_NEW_SELECTION')
    need(pathlib.Path(prior['output_directory']).parent == O.OUTPUT and
         plan['closed_D3_domain_locator'] == str(pathlib.Path(prior['output_directory']) / 'domain.sqlite') and
         plan['first_CPU_closed_domain_SHA_and_finite_projection_authorized'] is True,
         'ONLY_REAL_C0_D3_DOMAIN_NO_LOGIN_DATA_HASH_OR_FUTURE_REFERENCE')
    return d3, norm, d5, receipt, prior, accepted, old


def guard(plan_path, proof_path, plan):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    proof = require_startup(proof_path, expected_kind='analysis', expected_scope_key=KEY,
        expected_scope_parameters=parameters(plan), expected_execution_argv=[PY, '-B', '-m', MODULE,
        '--plan', str(plan_path), '--startup-proof', str(proof_path)], expected_source=HERE / 'run.py',
        required_references=[Q.pin(plan_path), *plan['source_references']])
    I.resource_admission(proof['request'], plan)
    return proof


def sources():
    return O.unique([*O.sources(), *(Q.pin(HERE / name) for name in FILES)])
