"""Same frozen D4/D5 inputs; D3 closed configurations, never D3 payload C0."""
import pathlib
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import contract as O, io as I, local_parent as L
from workflows.data_v1_final.export.common_day_parent_v1 import parent as A

Q, ROOT, REPO, PY, need, meta, reference = O.Q, O.ROOT, O.REPO, O.PY, O.need, O.meta, O.reference
PRODUCER_NAMESPACE = 'pilot_D5_parallel_guide_v1'
KEY = PRODUCER_NAMESPACE.lower()
STORE_NAMESPACE = 'pilot_D3_diagnostic_supplement_v1'
MODULE = 'workflows.data_v1_final.export.' + PRODUCER_NAMESPACE + '.run'
HERE = REPO / 'workflows/data_v1_final/export' / PRODUCER_NAMESPACE
OUTPUT = ROOT / 'artifacts/labels/source_status_v1' / PRODUCER_NAMESPACE
ROLE = 'TRAIN_UNSEEN_CONFORMATION'
FILES = ('__init__.py', 'contract.py', 'domain.py', 'source.py', 'shared.py', 'resource.py', 'resume.py', 'verify.py', 'run.py', 'close.py', 'README.md')


def parameters(plan):
    return dict(domain='FROZEN_D4_PILOT_TRAIN_INTERSECT_FORMAL_D5_HELD_TARGETS', sample_role=ROLE,
        workers=16, pending=32, wall_seconds=86400, whole_output_cap_bytes=plan['whole_output_cap_bytes'],
        fields=146, source_roundtrip='ALL_IF_LESS_THAN10000_ELSE_ORIGINAL_DETERMINISTIC10000',
        source_masks_unchanged=True, training_excluded=True, new_QM_UFF_calls=0,
        r674='ORIGINAL_VALUES_MASKS_LOSS_OFF', r73='ORIGINAL_ORDERED_NATIVE_RECORDS',
        permanent_F64_and_original_once_F32=True, full_Common_D6_Model_ACK=False,
        D3_payload_C0_required=False, shared_configuration='CLOSED_ACTUAL_CPU_HEADER_AND_FOUR_CURRENT_HASHES',
        active_domain_resource_credit='DISABLED_KEEP_FULL_OWN_FUTURE_CAP_NO_MUTABLE_BLOCK_MONOTONICITY',
        worker_rss_soft_cap_bytes=3 << 30,
        closed_source_groups_resume='ROOT_REVIEWED_4525590_101_CLOSED_ONLY' if plan.get('closed_source_groups_resume_reference') else None)


def parents(plan):
    accepted = meta(plan['pilot_acceptance_reference'])
    need(accepted['schema'] == L.SCHEMA, 'ACTUAL_LOCAL_COMPLETE_D4_REQUIRED')
    accepted, receipt, proof, old, bounded, data, refs = L.parents(plan, accepted)
    need(L.component_numeric_scope(plan, accepted['component_references']) is True,
         'EXPLICIT_USER_GUIDE_SINGLE_COMPLETE_PASS')
    d5 = meta(plan['D5_delivery_reference'])
    need(d5['schema'] == 'DATA_V1_D5_PROVISIONAL_DELIVERY_V1' and
         d5['version'] == 'v1-pilot-provisional' and
         d5['status'] == 'DELIVERED_PROVISIONAL_SCOPE_NOT_FINAL_COMMON' and
         d5['components']['diagnostic_TRAIN_molecules'] == 20000,
         'ORIGINAL_GLOBAL_D5_LISTS_NOT_NEW_SAMPLING')
    d5_acceptance = meta(d5['actual_acceptance_reference'])
    chain = d5_acceptance['actual_parent']
    d5_receipt, d5_proof = meta(chain['manifest']), meta(chain['proof'])
    A.account(chain['accounting'], d5_receipt['job_id'], d5_proof['node'], 16)
    need(d5_acceptance['schema'] == 'ROOT_ACCEPTED_BOUNDED_OLD_COMPLETE_D5_COMPONENTS_V1' and
         d5_acceptance['status'] == 'ACTUAL_C0_OLD_COMPLETE_D5_COMPONENTS_ACCEPTED_NOT_FINAL_COMMON' and
         str(d5_receipt['job_id']) == str(d5_proof['job_id']) == '4525184' and d5_proof['uid'] == 1278,
         'REAL_ORIGINAL_5184_D5_20K_CLOSURE')
    d3plan = meta(plan['shared_D3_plan_reference'])
    need(d3plan['schema'] == 'BOUNDED_PILOT_FAMILY_D3_PLAN_V1' and
         d3plan['pilot_acceptance_reference'] == plan['pilot_acceptance_reference'] and
         d3plan['bounded_export_review_reference'] == plan['bounded_export_review_reference'] and
         d3plan['D1_design_policy_reference'] == plan['D1_design_policy_reference'] and
         d3plan['D1_five_layer_reference'] == plan['D1_five_layer_reference'] and
         d3plan['order_capability'] == plan['order_capability'] == O.NATIVE_MODE and
         pathlib.Path(d3plan['output_directory']).parent == O.OUTPUT and
         plan['shared_D3_configuration_locator'] == str(pathlib.Path(d3plan['output_directory']) / 'actual_bounded_configurations') and
         plan['CPU_first_shared_configuration_hash_authorized'] is True,
         'SAME_FROZEN_D4_CONFIGURATION_PARENT_NO_FUTURE_HASH_OR_D3_C0_GATE')
    return accepted, receipt, proof, old, bounded, data, refs, d5, d3plan


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
