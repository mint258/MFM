"""Private V3 all11 amendment after independently accepted case18 source evidence."""
import argparse
import copy
import inspect
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import traceback
import unittest
from workflows.expansion.alpha_runtime_v1.profile import admit as profile_admit
from workflows.expansion.alpha_runtime_v1.guard import Guard
from workflows.expansion.coconut_alpha_cached735_v1 import support as S
from workflows.expansion.molnet_case18_native_evidence_v1.reads import Reads
from workflows.expansion.molnet_case18_native_evidence_v1 import reads as read_module,parse as parse_module
from workflows.expansion.coconut735_recovery_v1 import consumer as C
from .logic import CASE,COMP,KEY,need,parent,authority,amend,accounting_header,accounting_readback

SCOPE='molnet_case18_index_amendment_v1'
PRODUCER='ALPHA_ALL11_CASE18_EXISTING_COMPOSITION_INDEX_AMENDMENT_V1'


def admission(plan,proof,pp,sp):
    actual=profile_admit(plan,minimum_workers=16)
    need(plan['schema']=='ALPHA_MOLNET_CASE18_INDEX_AMENDMENT_PLAN_V1'
         and plan['scope_key']==proof['request']['scope_key']==SCOPE
         and proof['request']['producer_plan_reference']==S.pin(pp)
         and plan['execution_argv']==proof['request']['execution_argv']
         and plan['execution_argv'][-4:]==sys.argv[-4:]==['--plan',str(pp),'--startup-proof',str(sp)]
         and proof['endpoint']==plan['endpoint']=='218.192.171.238:22'
         and proof['uid']==plan['uid']==os.getuid()==1264
         and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
         and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'EXACT_NEW_ALPHA_AMENDMENT_JOB_SCOPE')
    refs=proof['request']['source_references']
    code=[*Path(__file__).parent.glob('*.py'),Path(S.__file__),Path(read_module.__file__),Path(parse_module.__file__),
          Path(inspect.getsourcefile(C.index_header)),Path(inspect.getsourcefile(C.identity_keys))]
    for path in code:need(S.pin(path) in refs and S.pin(path) in plan['code_references'],'EXACT_UNCHANGED_V3_AND_NEW_SOURCE_PINS')
    for ref in plan['code_references']:S.read(ref,2<<20)
    budget=S.load(plan['reviewed_storage_budget_reference'])
    need(budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and budget['reviewer']=='root'
         and budget['endpoint']=='218.192.171.238:22' and budget['uid']==1264
         and budget['quota_root']=='/gfshome/alpha'
         and plan['output_scope_root']=='/gfshome/alpha/pubchem_expansion_20261103/bulk'
         and plan['output_cap_bytes']==budget['scope_total_caps_bytes']['bulk']
         and plan['other_future_reserved_bytes']==budget['other_future_reserved_bytes_for_each_scope']['bulk']
         and plan['minimum_free_bytes']==budget['minimum_free_after_all_future_bytes'],'ACTUAL_REVIEWED_STORAGE_BUDGET')
    return actual


def accounting(r,ref,job):
    account=r.json(ref);header=accounting_header(account)
    witness=accounting_readback(account,r.read(header['raw_reference']),job)
    return account,witness


def source_authority(r,plan):
    r.json(plan['reviewed_storage_budget_reference'])
    review=r.json(plan['root_source_acceptance_reference'])
    old_ref=review['original_index_root_acceptance_reference'];old=r.json(old_ref)
    need(plan['old_index_root_acceptance_reference']==old_ref,'EXACT_DECLARED_OLD187_ROOT_AUTHORITY')
    native=r.json(review['native_evidence_receipt_reference'])
    account,native_accounting=accounting(r,review['native_evidence_actual_accounting_reference'],native['profile_admission']['job_id'])
    policy=r.json(review['source_policy_reference'])
    expected=authority(review,policy,native,account,old,old_ref)
    old_account,original_accounting=accounting(r,old['actual_accounting_reference'],'1885187')
    need(old['actual_parent']==parent(old_account,'1885187'),
         'ACTUAL_ORIGINAL187_C0_PRESERVED')
    original=C.index_header(r.json(old['index_receipt']))
    need(original['database']==old['closed_database'] and original['source_manifest_reference']==old['source_manifest_reference']
         and original['source_replica_readback']==old['source_replica_readback']
         and original['actual_constraint_rule_counts']=={'coconut':0,'moleculenet':2},'EXACT_187_COMPLETE_V3_BASE')
    consumed=r.json(old['source_replica_readback'])
    need(len(consumed['files'])==old['native_full_SHA_consumption_entries']==577
         and all(x['whole_SHA256_verified'] is True and x['actual_uid']==1264 for x in consumed['files']),
         '577_OLD_COMPLETE_SOURCE_READS_INHERITED_NOT_NEW_READS')
    manifest=r.json(original['source_manifest_reference'])
    rules=[json.loads(line) for line in r.read(review['original_rule_reference']).splitlines()]
    need({x['rule_id'] for x in rules}=={'case:00',CASE} and len(rules)==2
         and [x for x in rules if x['rule_id']==CASE]==[expected],'EXACT_WHOLE_OLD_MOLNET_RULE_FILE_AND_CASE18')
    tests=r.json(native['source_tests_reference'])
    need(tests['tests']==4 and tests['failures']==tests['errors']==0,'ACTUAL_NATIVE_FOUR_SOURCE_FIXTURES')
    reads=r.json(native['actual_source_reads_reference'])
    need(len(reads['files'])==review['actual_source_read_entries']==28
         and all(x['whole_SHA256_verified'] is True and x['actual_uid']==1264 for x in reads['files'])
         and review['root_fresh_same_node_all28_frames_verified'] is True,'REVIEWED_NATIVE28_FULL_READS_HONESTLY_INHERITED')
    observation=r.json(native['evidence_reference'])
    need(observation['status']=='EVIDENCE_ONLY_PENDING_C0_AND_ROOT_SOURCE_REVIEW'
         and observation['original1PTS_graph_UNKNOWN_retained'] is True
         and observation['source_correspondence_adopted'] is False
         and observation['terminal_correspondence_adopted'] is False
         and observation['graph_or_full_keys_created']==0 and observation['missing_atoms_inferred']==0,
         'DIAGNOSTIC_DID_NOT_PRETEND_ADOPTION_OR_GRAPH_RECOVERY')
    r.json(original['original_function_object_proof'])
    matched=[x for x in consumed['files'] if {k:x['replica_reference'][k] for k in ('path','bytes','sha256')}
             =={k:review['original_rule_reference'][k] for k in ('path','bytes','sha256')}]
    need(len(matched)==1 and matched[0]['source_reference']['path'].startswith('/share/home/zixiao/')
         and matched[0]['actual_uid']==1264,'ORIGINAL_MAIN_RULE_LOGICAL_ORIGIN_AND_ALPHA_REPLICA_RETAINED')
    return review,old,original,manifest,expected,dict(native_evidence=native_accounting,original187=original_accounting)


def produce(plan,proof,actual,guard,out):
    r=Reads(plan,guard.check);review,old,base,manifest,expected,accounting_adapters=source_authority(r,plan)
    target=out/'excluded_identities_v3.sqlite'
    need(not target.exists(),'FRESH_PRIVATE_DATABASE_NO_OVERWRITE')
    fd=os.open(target,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd)
    db=sqlite3.connect(target);db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA journal_mode=DELETE')
    try:
        with r.held(base['database'],lock_database=True) as (take,path,source):
            invariants=amend(source,db,expected,guard.check)
        db.close();db=None
        # Second independent output FD SHA/frame readback; never hash an open DB.
        output_reference=S.pin(target)
        with target.open('rb') as f:
            import hashlib
            before=os.fstat(f.fileno());h=hashlib.sha256();size=0
            for block in iter(lambda:f.read(8<<20),b''):
                h.update(block);size+=len(block);guard.check()
            need(S.frame(before)==S.frame(os.fstat(f.fileno()))==S.frame(target.stat())
                 and h.hexdigest()==output_reference['sha256'] and size==output_reference['bytes'],
                 'SECOND_CLOSED_NEW_DATABASE_WHOLE_FD_SHA_AND_FRAME_READBACK')
        need(all(not Path(str(target)+s).exists() for s in ('-wal','-shm','-journal')),'CLOSED_PRIVATE_DATABASE_NO_SIDECARS')
    finally:
        if db is not None:db.close()
    proof_ref=S.save(out/'private_database_invariants.json',invariants)
    source_manifest=S.save(out/'all11_source_manifest_case18_amendment.json',dict(
        schema='ALL11_CASE18_EXISTING_COMPOSITION_SOURCE_MANIFEST_AMENDMENT_V1',
        status='SOURCE_COVERAGE_AMENDED_PENDING_NEW_PARENT_C0_AND_ROOT_INDEX_ACCEPTANCE',
        original_source_manifest_reference=base['source_manifest_reference'],
        inherited_original_manifest=manifest,inherited_all11_source_counts=old['source_counts'],
        inherited_original_index_receipt_reference=old['index_receipt'],
        inherited_original577_source_replica_readback_reference=old['source_replica_readback'],
        inherited_whole_source_SHA_read_entries=577,original577_bodies_rehashed_by_this_parent=False,
        inherited_native28_evidence_readback_reference=review['source_readback_reference'],
        native28_bodies_rehashed_by_this_parent=False,
        root_source_acceptance_reference=plan['root_source_acceptance_reference'],source_policy_reference=review['source_policy_reference'],
        source_manifest_amendment=dict(only_rule_id=CASE,old_rule_reference=review['original_rule_reference'],
            original_rule=expected,original_rule_kept_in_original_index_and_raw_audit=True,
            replacement_coverage=review['replacement'],existing_MolNet_composition_row_not_newly_created=True,
            private_database_invariants_reference=proof_ref),
        source_rows_or_roles_removed=0,original_all11_source_scope_unchanged=True,
        original_graph_UNKNOWNs_retained=True,ClinTox_case00_unchanged=True,COCONUT_scope_unchanged=True,
        original577_parent='1885187',new_parent_binding=actual,new_parent_C0_pending=True,global_pool_release=False))
    actual_reads=S.save(out/'actual_source_reads.json',dict(schema='ALPHA_CASE18_AMENDMENT_ACTUAL_SOURCE_READS_V1',files=r.records))
    result=copy.deepcopy(base)
    result.update(producer_schema=PRODUCER,database=output_reference,source_manifest_reference=source_manifest,
        producer_parent_binding=actual,profile_admission=actual,
        original_function_object_proof_inherited_from_parent='1885187',
        actual_accounting_format_adapters=accounting_adapters,
        current_unchanged_V3_functions={f.__qualname__:S.pin(inspect.getsourcefile(f)) for f in (C.index_header,C.identity_keys)},
        actual_constraint_rule_counts={'coconut':0,'moleculenet':1},actual_parent_C0_acceptance='PENDING_ROOT_TERMINAL_ACCOUNTING',
        original_index_receipt_reference=old['index_receipt'],root_source_acceptance_reference=plan['root_source_acceptance_reference'],
        root_source_policy_reference=review['source_policy_reference'],private_database_invariants_reference=proof_ref,
        actual_source_reads_reference=actual_reads,source_replica_readback=old['source_replica_readback'],
        source_replica_readback_inherited_from_parent='1885187',inherited_whole_source_SHA_read_entries=577,
        original577_bodies_rehashed_by_this_parent=False,original_all11_source_counts=old['source_counts'],
        source_manifest_amendment_performed=True,global_pool_release=False,filtered_pool_complete=False,
        original_graph_unknowns_retained=True,original_UNKNOWN_resolved=False)
    C.index_header(result)
    need(result['sources']==base['sources'] and result['original_all11_source_counts']==old['source_counts']
         and result['constraint_source_datasets']==base['constraint_source_datasets'], 'ALL11_COUNTS_ROLES_AND_V3_FUNCTION_BYTES_REUSED')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=json.loads(a.plan.read_bytes());proof=json.loads(a.startup_proof.read_bytes())
    actual=admission(plan,proof,a.plan,a.startup_proof);guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False)
        report=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromName(__package__+'.test_source')
        tests=unittest.TextTestRunner(stream=report,verbosity=2).run(suite)
        need(tests.testsRun==4 and tests.wasSuccessful() and not tests.skipped,'FOUR_NATIVE_AMENDMENT_SOURCE_FIXTURES')
        fixture=S.save(out/'source_tests.json',dict(tests=tests.testsRun,failures=len(tests.failures),errors=len(tests.errors),output=report.getvalue()))
        result=produce(plan,proof,actual,guard,out);guard.sample()
        result.update(source_tests=fixture,plan_reference=S.pin(a.plan),startup_proof_reference=S.pin(a.startup_proof),runtime=guard.receipt())
        S.save(out/'receipt.json',result)
    except BaseException as exc:
        if out.is_dir():S.save(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),partials_retained=True))
        raise
    finally:guard.close()


if __name__=='__main__':main()
