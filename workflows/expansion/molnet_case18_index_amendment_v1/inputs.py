"""Only bounded metadata input bindings; no old database body scan or submission."""
import argparse
from pathlib import Path
from workflows.expansion.coconut_alpha_cached735_v1 import support as S
from workflows.expansion.molnet_case18_native_evidence_v1.reads import key,triple
from .logic import accounting_header


def collect(source_ref,budget_ref):
    review=S.load(source_ref);old_ref=review['original_index_root_acceptance_reference'];old=S.load(old_ref)
    native=S.load(review['native_evidence_receipt_reference']);index=S.load(old['index_receipt'])
    refs=[source_ref,budget_ref,old_ref,review['native_evidence_receipt_reference'],review['native_evidence_actual_accounting_reference'],
        review['source_policy_reference'],review['original_rule_reference'],old['actual_accounting_reference'],old['index_receipt'],
        old['source_replica_readback'],index['source_manifest_reference'],index['database'],index['original_function_object_proof'],
        native['source_tests_reference'],native['actual_source_reads_reference'],native['evidence_reference']]
    for account in (S.load(review['native_evidence_actual_accounting_reference']),S.load(old['actual_accounting_reference'])):
        refs.append(accounting_header(account)['raw_reference'])
    unique={key(r):triple(r) for r in refs}
    S.need(all(r['path'].startswith('/gfshome/alpha/') for r in unique.values()),'ACTUAL_ALPHA_REFERENCES_NOT_MAIN_UID_ALIAS')
    return dict(schema='ALPHA_MOLNET_CASE18_INDEX_AMENDMENT_INPUT_FIELDS_V1',
        root_source_acceptance_reference=source_ref,old_index_root_acceptance_reference=old_ref,
        reviewed_storage_budget_reference=budget_ref,
        input_bindings=[dict(source_reference=r,replica_reference=r,origin_endpoint='218.192.171.238:22',origin_uid=1264)
                        for r in unique.values()],runtime_proof_code_refs_and_output_pending_root=True,no_job_submitted=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root-source-acceptance',type=Path,required=True)
    p.add_argument('--future-budget-review',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();S.save(a.output,collect(S.pin(a.root_source_acceptance),S.pin(a.future_budget_review)))


if __name__=='__main__':main()
