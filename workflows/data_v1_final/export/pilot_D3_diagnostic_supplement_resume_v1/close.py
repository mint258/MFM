"""Root small-metadata wrapper only after the supplement's real external C0."""
import argparse
import pathlib
from . import contract as C
from workflows.data_v1_final.export.common_day_parent_v1 import parent as A


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=pathlib.Path, required=True)
    parser.add_argument('--accounting', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    rr, ar = C.Q.pin(args.receipt), C.Q.pin(args.accounting)
    receipt = C.meta(rr)
    C.need(receipt['schema'] == 'D3_DIAGNOSTIC_SUPPLEMENT_PARENT_RECEIPT_V1' and
           receipt['status'] == 'DIAGNOSTIC_SUPPLEMENT_CLOSED_PENDING_ACTUAL_C0_ROOT_WRAPPER' and
           receipt['role'] == C.ROLE and receipt['new_QM_UFF_calls'] == 0 and
           receipt['training_excluded'] is True and receipt['scientific_masks_unchanged'] is True and
           receipt['same_D4_statistics_no_refit'] is True and receipt['all_handles_closed'] is True,
           'ACTUAL_COMPLETE_DIAGNOSTIC_PARENT_RECEIPT_NOT_SOURCE_PLAN')
    proof = C.meta(receipt['startup_proof_reference'])
    plan = C.meta(receipt['plan_reference'])
    C.need(proof['request']['scope_key'] == C.KEY and proof['request']['execution_argv'] ==
           [C.PY, '-B', '-m', C.MODULE, '--plan', receipt['plan_reference']['path'],
            '--startup-proof', receipt['startup_proof_reference']['path']] and
           str(proof['job_id']) == receipt['actual_parent_job_id'] and proof['uid'] == 1278 and
           pathlib.Path(rr['path']).parent == pathlib.Path(plan['output_directory']), 'TRUE_SINGLE_SUPPLEMENT_PARENT')
    account, raw = A.account(ar, receipt['actual_parent_job_id'], receipt['node'], 16)
    C.parents(plan)
    value = dict(receipt, schema='ACTUAL_D3_DIAGNOSTIC_SUPPLEMENT_V1',
                 status='ACTUAL_C0_DIAGNOSTIC_SUPPLEMENT_NOT_TRAINING_OR_FINAL_COMMON',
                 actual_parent_accounting_reference=ar,
                 actual_parent={'manifest': rr, 'proof': receipt['startup_proof_reference'], 'accounting': ar, 'raw': raw},
                 actual_parent_endpoint='202.38.247.57:22', actual_parent_uid=1278,
                 role_source='ACTUAL_D3_EXPORTED_TRAIN_MIDS_INTERSECT_FORMAL_D5_HELD_TARGETS',
                 actual_root_C0_wrapper=True)
    C.need(C.ROOT / 'control' in args.output.parents and not args.output.exists(), 'NEW_ROOT_SMALL_METADATA_WRAPPER')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    C.Q.write_new(args.output, value)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
