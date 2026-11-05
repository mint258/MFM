"""Native metadata producer applying the already observed exact732 user reply."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from workflows.expansion.coconut_alpha_cached735_v1 import support as S
from .assemble import assemble


def native_parent(value,receipt,job):
    import csv,io
    S.need(value['endpoint']=='218.192.171.238:22' and value['uid']==1264
           and value['query_returncode']==0,'ACTUAL_ALPHA_ACCOUNTING_NOT_MAIN')
    raw=value.get('actual_sacct')
    if value.get('raw_sacct_reference'):raw=S.read(value['raw_sacct_reference']).decode()
    rows=list(csv.DictReader(io.StringIO(raw),delimiter='|')) if raw else value.get('actual_parents',[value.get('actual_parent',{})])
    matches=[r for r in rows if str(r.get('JobIDRaw'))==str(job)]
    S.need(len(matches)==1 and matches[0]['State']=='COMPLETED' and matches[0]['ExitCode']=='0:0'
           and str(matches[0]['UID'])=='1264','ACTUAL_SOURCE_PARENT_C0')
    if value.get('receipt'):S.need(value['receipt']==receipt,'ACCOUNTING_EXACT_SOURCE_RECEIPT')
    return matches[0]


def rows(ref):
    raw=S.read(ref);lines=raw.splitlines(keepends=True)
    S.need((not raw or raw.endswith(b'\n')) and len(lines)==ref['rows'],'FULL_CLOSED_JSONL_EOF_CENSUS')
    return [json.loads(line) for line in lines]


def write_rows(path,values):
    with path.open('xb') as stream:
        for value in values:stream.write(S.canonical(value))
        stream.flush();os.fsync(stream.fileno())
    ref=dict(S.pin(path),rows=len(values))
    S.need(rows(ref)==values,'INDEPENDENT_OUTPUT_READBACK')
    return ref


def admit(plan,proof,pp,sp):
    from workflows.expansion.alpha_runtime_v1 import profile
    authority=profile.admit(plan,minimum_workers=16)
    S.need(plan['schema']=='ALPHA_COCONUT735_APPROVED_SCOPE_LEDGER_PLAN_V1'
           and plan['scope_key']==proof['request']['scope_key']=='alpha_coconut735_approved_scope_ledger_v1'
           and proof['request']['producer_plan_reference']==S.pin(pp)
           and proof['request']['execution_argv']==plan['execution_argv']
           and plan['execution_argv'][-4:]==sys.argv[-4:]==['--plan',str(pp),'--startup-proof',str(sp)]
           and proof['endpoint']==plan['endpoint']=='218.192.171.238:22'
           and proof['uid']==plan['uid']==os.getuid()==1264
           and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
           and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
           'EXACT_ALPHA_CURRENT_SCOPE_PLAN_JOB_BOOT_ARGV')
    declared={r['path']:r for r in proof['request']['source_references']}
    for file in [*Path(__file__).parent.glob('*.py'),Path(S.__file__)]:
        S.need(declared.get(str(file.absolute()))==S.pin(file),'EXACT_OWN_SOURCE_BEFORE_PRODUCER')
    for ref in plan['code_references']:S.read(ref,2<<20)
    return authority


def build(plan,guard,out):
    S.need(plan['actual_user_approval_reference']['sha256']=='0aeab0141dcbb198db581b603e3126d9bb04a10428b65e71cde55788e86ff7e9'
           and plan['scope_proposal_reference']['sha256']=='d2c5a886cb16433c9730cf730c523971e808200a26e962479bac9a742ff3cafd',
           'EXACT_ALREADY_APPROVED_PUBLIC44F8_SOURCE_SET_AND_ACTUAL_REPLY')
    from workflows.expansion.coconut_alpha_primary3_exact_v1 import prepare as P
    # Reuse the original complete formula/source-association/identity_keys proof.
    S.need(S.pin(P.__file__) in plan['code_references'],'DECLARED_UNCHANGED_PRIMARY3_SOURCE_REPLAY')
    primary=P.build(plan['primary3_receipt_reference'],plan['primary3_actual_accounting_reference'])
    overlay=primary.pop('proposed_original_strict5_rows')
    pr=S.save(out/'primary3_exact_source_replay.json',primary)
    overlay_ref=write_rows(out/'primary3_exact_composition.strict5.jsonl',overlay)
    native=S.load(plan['native735_receipt_reference'])
    native_parent(S.load(plan['native735_actual_accounting_reference']),plan['native735_receipt_reference'],
                  native['profile_admission']['job_id'])
    S.need(native['schema']=='COCONUT_ALPHA_NATIVE735_PRODUCER_V1'
           and native['profile_admission']['endpoint']==plan['endpoint']
           and native['profile_admission']['uid']==1264,'ACTUAL_ORIGINAL735_NATIVE_SOURCE')
    original_ref=native['result']['DATA'];original=rows(original_ref);guard.check()
    proposal=S.load(plan['scope_proposal_reference']);approval=S.load(plan['actual_user_approval_reference'])
    structural_review=S.load(proposal['actual_structural_review_reference'])
    structural_ref=structural_review['producer_receipt_reference'];audit=S.load(structural_ref)
    native_parent(S.load(plan['structural735_actual_accounting_reference']),structural_ref,audit['profile_admission']['job_id'])
    S.need(audit['schema']=='COCONUT_ALPHA_STRUCTURAL_AUDIT_PRODUCER_V1'
           and audit['result']['DATA']==proposal['structural_DATA_reference']
           and audit['result']['DATA']['rows']==735,'FULL_ACTUAL_SOURCE_AUDIT_NOT_INFERRED_SCOPE')
    evidence=[plan['actual_user_approval_reference'],plan['scope_proposal_reference'],pr,
              plan['primary3_receipt_reference'],plan['primary3_actual_accounting_reference'],
              structural_ref,proposal['actual_structural_review_reference'],plan['structural735_actual_accounting_reference'],audit['result']['DATA']]
    ledger=assemble(original,rows(audit['result']['DATA']),proposal,approval,primary,overlay,evidence)
    guard.check()
    ledger_ref=write_rows(out/'physical_dispositions735.jsonl',ledger)
    # An exact derivative of Root's already durable user reply, not a new reply.
    reply=S.save(out/'actual_prior_user_reply.json',dict(role='user',text=approval['user_answer_verbatim'],
        source_reference=plan['actual_user_approval_reference'],verbatim_derived_from_existing_root_record=True))
    authority=S.save(out/'source_scope_authority.json',dict(schema='ROOT_COCONUT_SOURCE_SCOPE_ACTUAL_APPROVAL_V1',
        status='ACTUAL_USER_APPROVAL_RECORDED',reviewer='root',actual_user_reply_observed=True,
        actual_user_reply_reference=reply,existing_root_user_approval_reference=plan['actual_user_approval_reference'],
        approved_source_ids=proposal['proposed_quarantined_source_ids'],original_records_retained=True,
        original_graph_unknowns_retained=True,audit_receipt_reference=structural_ref,
        audit_actual_accounting_reference=plan['structural735_actual_accounting_reference'],
        adapter_records_existing_approval_only=True,new_user_or_root_scientific_approval_created=False))
    strict_ref=primary['original_strict_receipt_reference'];strict=S.load(strict_ref)
    cov=S.load(strict['coverage_reference'])
    S.need(strict['complete_physical_source'] is True and cov['all_splits'] is True
           and cov['physical_rows']==2939137 and cov['unresolved_without_identity_or_composition']==735
           and cov['covered_roles']==['ALL_SOURCE_NATIVE_SPLIT_UNKNOWN']
           and set(cov['covered_subdatasets'])=={'molecules','entries'}
           and cov['identities']==strict['outputs']['identities']
           and cov['no_status_invalid_or_parsefail_drop'] is True,'ORIGINAL_WHOLE_COCONUT_BASE_NOT_REPLACED')
    # Large old bodies are pinned as inherited inputs. The all11 native index
    # performs their fresh complete FD reads; this narrow stage does not claim it.
    coverage=dict(schema='COCONUT735_ACCEPTED_EXCLUSION_COVERAGE_V1',
        status='SOURCE_LEDGER_CLOSED_PENDING_ACTUAL_C0_ROOT_ADOPTION_AND_COMPLETE_POOL_IMPACT',
        physical_unknown_rows=735,remaining_exclusion_HOLD=0,all_physical_source_rows_retained=True,
        original_graph_identities_repaired=False,source_version='COCONUT_ORIGINAL1885088_PLUS_EXACT732_APPROVAL_V1',
        required_roles=cov['covered_roles'],required_subdatasets=cov['covered_subdatasets'],
        raw_artifacts=cov['raw_artifacts'],identity_parts=[cov['identities'],overlay_ref],
        lower_bounds=write_rows(out/'no_new_lower_bounds.jsonl',[]),physical_dispositions=ledger_ref,
        source_scope_authority_reference=authority,original735_receipt_reference=plan['native735_receipt_reference'],
        original735_DATA_reference=original_ref,
        original735_actual_accounting_reference=plan['native735_actual_accounting_reference'],
        original_strict_receipt_reference=strict_ref,original_base_coverage_reference=strict['coverage_reference'],
        original_base_physical_audit_reference=strict['outputs']['physical_audit'],
        original_base_unknown_locators_reference=strict['outputs']['unknown_locators'],
        original_all_physical_rows=cov['physical_rows'],original_base_identity_rows=cov['identities']['rows'],
        supplemental_exact_composition_rows=3,approved_scope_dispositions=732,
        original735_graph_UNKNOWN_retained=True,new_lower_bound_rules=0,
        unchanged_base_body_full_read_claimed_by_this_narrow_stage=False,
        all11_ready=False,candidate_filtering_or_impact_measured=False,global_pool_release=False)
    return dict(coverage_reference=S.save(out/'coconut735_coverage_candidate.json',coverage),
        ledger_reference=ledger_ref,overlay_reference=overlay_ref,source_scope_authority_reference=authority,
        primary3_replay_reference=pr,physical_unknown_rows=735,original_graph_UNKNOWN_retained=735,
        disposition_counts={'EXACT_COMPOSITION_COVERED':3,'APPROVED_SOURCE_SCOPE_DISPOSITION':732},
        new_chemical_calls=0,new_graph_identities=0,new_lower_bound_rules=0,source_rows_deleted=0,
        all11_ready=False,complete_candidate_pool_impact_pending=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=json.loads(a.plan.read_text());proof=json.loads(a.startup_proof.read_text())
    authority=admit(plan,proof,a.plan,a.startup_proof)
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False)
        import unittest,io
        report=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromName(__package__+'.test_source')
        tests=unittest.TextTestRunner(stream=report,verbosity=2).run(suite)
        S.need(tests.testsRun==2 and tests.wasSuccessful() and not tests.skipped,'TWO_NATIVE_SOURCE_FIXTURES')
        fixture=S.save(out/'source_tests.json',dict(tests=tests.testsRun,failures=len(tests.failures),errors=len(tests.errors),output=report.getvalue()))
        result=build(plan,guard,out);result['source_tests_reference']=fixture;guard.sample()
        S.save(out/'receipt.json',dict(schema='ALPHA_COCONUT735_APPROVED_SCOPE_LEDGER_PRODUCER_V1',
            status='PHYSICAL735_LEDGER_CLOSED_PENDING_ACTUAL_C0_AND_ROOT_ADOPTION',
            plan_reference=S.pin(a.plan),startup_proof_reference=S.pin(a.startup_proof),
            profile_admission=authority,result=result,runtime=guard.receipt(),
            actual_parent_C0_pending_root_readback=True,global_pool_release=False))
    except BaseException as exc:
        if out.is_dir():S.save(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),partials_retained=True))
        raise
    finally:guard.close()


if __name__=='__main__':main()



