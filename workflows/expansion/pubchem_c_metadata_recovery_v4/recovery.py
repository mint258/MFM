"""Only metadata locator capacity changes; old production authority stays intact."""
import argparse,ast,csv,io,re,time
from pathlib import Path,PurePosixPath
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_continuation_alpha_v3 import contracts as A
HERE=Q.ROOT/'code/pubchem_c_metadata_recovery_v4'
QUEUE=Q.ROOT/'code/secondary_cpu_readonly_pubchem_metadata_recovery_v4'
FILES=('__init__.py','controller.py','recovery.py','test_recovery.py','fixture_cpu.py','README.md')
QUEUE_FILES=('__init__.py','adapters.py','controller.py')
REVIEW='ROOT_REVIEWED_PUBCHEM_METADATA_RECOVERY_V4'
SOURCE3='ROOT_REVIEWED_PUBCHEM_METADATA_RECOVERY_SOURCE3_V4'
STATE=Q.ROOT/'control/secondary_cpu_queue/pubchem_C_continuation52_v3'
EXPECTED={i:str(1884859+i-52) for i in range(52,58)}
EDITS=(
 ('HERE=A.CONTROLLER;CONTROL=',"HERE=Q.ROOT/'code/pubchem_c_metadata_recovery_v4';CONTROL="),
 ("def data_locator(value):\n    Q.normalized(value);Q.literal(value['path']);DENIED.add(value['path'])",
  'def data_locator(value):\n    from .recovery import register_data_locator\n    register_data_locator(value,DENIED)'),
 ('    root,grant,frozen,partition,initial,initial_attempts,base=context(args.root_range_review);state_dir=Q.literal(args.state_directory)',
  '    from .recovery import require_recovery_review\n    require_recovery_review(args)\n    root,grant,frozen,partition,initial,initial_attempts,base=context(args.root_range_review);state_dir=Q.literal(args.state_directory)'),
 ("for name in ('root-range-review','state-directory'","for name in ('metadata-recovery-review','root-range-review','state-directory'"))


def sources():return [*[Q.ref(HERE/n) for n in FILES],*[Q.ref(QUEUE/n) for n in QUEUE_FILES]]


def locator_shape(value):
    Q.need(type(value) is dict and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>0
      and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']) is not None
      and type(value['path']) is str and not any(c in value['path'] for c in ('\0','\r','\n')),'EXACT_POSITIVE_PRODUCER_DATA_LOCATOR')
    p=PurePosixPath(value['path'])
    Q.need(p.is_absolute() and '..' not in p.parts and PurePosixPath(str(Q.ROOT/'artifacts')) in p.parents
      and str(p)==value['path'],'ONLY_LITERAL_ALPHA_ARTIFACT_DATA_LOCATOR')
    return value


def register_data_locator(value,denied):
    locator_shape(value);Q.literal(value['path']);denied.add(value['path'])


def inverse():
    old=Q.read_small(A.CONTROLLER/'controller.py');new=Q.read_small(HERE/'controller.py');expected=old
    for before,after in EDITS:
        a,b=before.encode(),after.encode();Q.need(expected.count(a)==1,'ONE_DECLARED_FORWARD_METADATA_EDIT');expected=expected.replace(a,b)
    Q.need(expected==new,'ONLY_HERE_DATA_LOCATOR_AND_REVIEW_GATE_DELTAS')
    restored=new
    for before,after in reversed(EDITS):
        a,b=before.encode(),after.encode();Q.need(restored.count(b)==1,'ONE_DECLARED_INVERSE_METADATA_EDIT');restored=restored.replace(b,a)
    Q.need(restored==old and ast.dump(ast.parse(restored),include_attributes=False)==ast.dump(ast.parse(old),include_attributes=False),
      'EXACT_OLD_CONTROLLER_BYTES_AND_FULL_AST_INVERSE')
    from . import controller as N
    from pubchem_c_finite500_continuation_v3 import state as S
    Q.need(N.S is S,'DIRECT_UNCHANGED_OLD_STATE_OBJECT')
    oldtree=ast.parse(old);newtree=ast.parse(new)
    oldf={n.name:ast.dump(n,include_attributes=False) for n in oldtree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    newf={n.name:ast.dump(n,include_attributes=False) for n in newtree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    Q.need(set(oldf)==set(newf) and all(oldf[n]==newf[n] for n in oldf if n not in ('data_locator','run','main')),
      'ALL_OTHER_ORIGINAL_METHODS_FULL_AST_IDENTICAL')
    from secondary_cpu_readonly_pubchem_cont_v1 import controller as V
    Q.need(Q.read_small(Path(V.__file__))==Q.read_small(QUEUE/'controller.py'),'QUEUE_ALGORITHM_BYTES_IDENTICAL_LOCAL_ADAPTER_ONLY')
    return {'status':'EXACT_METADATA_LOCATOR_RECOVERY_BYTES_AND_AST_INVERSE','declared_delta_groups':3,'text_edits':4,
      'unchanged_function_names':sorted(n for n in oldf if n not in ('data_locator','run','main')),
      'old_state_object_is_same':True,'old_A_sources_unchanged':True,'science_or_producer_body_modified':False,
      'generic_queue_algorithm_bytes_identical':True,'new_root_review_required_before_run':True}


def same_binding(review,root,grant,binding,state):
    Q.need(review['original_root_range_review_reference']==grant==binding['root_range_review_reference']
      and review['original_state_directory']==str(state)==str(STATE)
      and review['original_deadline_unix_seconds']==root['deadline_unix_seconds']==binding['deadline_unix_seconds']
      and review['original_authorized_unix_seconds']==root['authorized_unix_seconds'],
      'SAME_OLD_GRANT_STATE_AND_ABSOLUTE_DEADLINE_NO_RENEWAL')
    Q.need(review['source_references_for_future_children']==root['source_references']
      and review['future_children_use_old13_approved_template'] is True and review['new_scientific_attempt_for52_57'] is False,
      'NO_NEW_PRODUCTION_AUTHORITY_OR_REPEAT_COMPLETED_SCIENCE')
    for key in ('no_automatic_retry','no_automatic_renewal','no_signals_or_cancel'):
        Q.need(review[key] is root[key] is True,'ORIGINAL_FINITE_INVARIANT:'+key)
    Q.need(root['max_nonterminal_C_parents']==6 and root['reserved_non_C_cpus']==16 and root['controller_metadata_cap_bytes']==16<<20,
      'ORIGINAL6C_SPARE16_AND16MIB_METADATA')


def source3_evidence(receipt_ref,account_ref):
    from . import fixture_cpu as F
    receipt=Q.load_ref(receipt_ref);account=Q.load_ref(account_ref);p=account['actual_parent']
    Q.need(receipt['schema']=='PUBCHEM_METADATA_RECOVERY_SOURCE3_CPU_RECEIPT_V4'
      and receipt['status']=='PASS_PENDING_REAL_TERMINAL_ACCOUNTING' and A.pure_counts(receipt,3)
      and receipt['scientific_body_reads']==0 and receipt['Budget_constructed'] is receipt['ProcessPool_started'] is receipt['ordinal_claim_written'] is False
      and receipt['source_inverse_proof']['status']=='EXACT_METADATA_LOCATOR_RECOVERY_BYTES_AND_AST_INVERSE'
      and receipt['source_references']==sources(),'ACTUAL_NEW3_SOURCE_TESTS_AND_INVERSE_NOT_OLD_STATE5')
    proof=Q.load_ref(receipt['startup_proof_reference']);plan=Q.load_ref(receipt['plan_reference']);F.validate_metadata(plan)
    Q.need(proof['schema']==F.PROOF and proof['scope_key']==F.KEY and proof['plan_reference']==receipt['plan_reference']
      and proof['root_review_reference']==plan['root_review_reference'] and proof['request']['execution_argv']==plan['execution_argv']
      and str(proof['job_id'])==str(receipt['actual_runtime']['job_id'])==p['JobIDRaw'], 'ACTUAL_SOURCE3_PLAN_PROOF_RECEIPT_PARENT_CHAIN')
    runtime=receipt['actual_runtime']
    Q.need(account['schema']=='SECONDARY_CPU_ACTUAL_ACCOUNTING_EVIDENCE_V1' and account['endpoint']==runtime['endpoint']==Q.ENDPOINT
      and account['uid']==runtime['uid']==1264 and account['query_returncode']==0 and account['actual_terminal'] is True
      and p['UID']=='1264' and p['State']=='COMPLETED' and p['ExitCode']=='0:0' and p['AllocCPUS']=='16'
      and p['Partition']=='cpu' and p['NodeList']==runtime['node']==proof['node'] and proof['uid']==1264 and proof['endpoint']==Q.ENDPOINT and p['NodeList'] in Q.NODES
      and runtime['cpus']==16 and account['allocated_core_seconds_observed']==int(p['ElapsedRaw'])*16,
      'REAL_ALPHA_SOURCE3_C0_NOT_MAIN_OR_FUTURE_PASS')
    from pubchem_c_finite500_queue_v2 import controller as L
    L.actual_raw(account['raw_sacct_reference'],p)
    return {'receipt_reference':receipt_ref,'accounting_reference':account_ref,'raw_reference':account['raw_sacct_reference'],
      'actual_parent':p,'allocated_core_seconds_observed':account['allocated_core_seconds_observed']}


def existing_parents(refs,grant):
    from . import controller as N
    rows={}
    for ref in refs:
        value,p=N.account_row(ref,Q.load_ref(ref)['actual_parent']['JobIDRaw']);jid=p['JobIDRaw']
        index=next((i for i,j in EXPECTED.items() if j==jid),None)
        Q.need(index is not None and index not in rows and p['State']=='COMPLETED' and p['ExitCode']=='0:0','EXACT_SIX_ACTUAL52_57_C0_PARENTS')
        rr=value['queue_request_reference'];request=Q.load_ref(rr);folder=Path(rr['path']).parent;sub=Q.load(folder/'submission.json')
        plan=Q.load_ref(request['adapter']['producer_plan_reference'])
        Q.need(sub['job_id']==jid and sub['sbatch_returncode']==0 and sub['queue_request_reference']==rr
          and request['scope_key']==A.KEY and plan['shard_index']==index and plan['continuation_range_review_reference']==grant,
          'EXISTING_ACTUAL_REGISTERED_SCIENCE_ONLY_NO_RESUBMISSION')
        rows[index]={'shard_index':index,'job_id':jid,'accounting_reference':ref,'queue_request_reference':rr,
          'submission_reference':Q.ref(folder/'submission.json'),'plan_reference':request['adapter']['producer_plan_reference']}
    Q.need(set(rows)==set(EXPECTED),'ALL_SIX_EXISTING_REGISTERED_PARENTS_REQUIRED');return [rows[i] for i in sorted(rows)]


def context_binding(context,grant,binding,failure):
    Q.need(context['schema']=='ROOT_ACTUAL_PUBCHEM_SIX_C0_METADATA_RECOVERY_CONTEXT_V1'
      and context['endpoint']==Q.ENDPOINT and context['uid']==1264 and context['scientific_reruns_authorized'] is False
      and context['scientific_body_reads_or_hashes_by_this_helper']==0
      and context['original_root_range_review_reference']==grant and context['original_state_binding_reference']==binding
      and context['failure_event_reference']==failure and context['original_state_directory']==str(STATE),
      'ACTUAL_ROOT_SIX_TERMINAL_CONTEXT_AND_ORIGINAL_BINDING')
    rows=context['six_actual_C0_parents']
    Q.need(len(rows)==6 and {r['job_id'] for r in rows}==set(EXPECTED.values())
      and context['six_parent_core_seconds']==sum(r['allocated_core_seconds_observed'] for r in rows)==157024,
      'SIX_EXISTING_C0_COSTS_RETAINED_NOT_SCIENCE_RETRY')

def require_recovery_review(args):
    Q.need(args.metadata_recovery_review,'EXPLICIT_NEW_METADATA_RECOVERY_REVIEW')
    ref=Q.ref(args.metadata_recovery_review);review=Q.load_ref(ref);grant=Q.ref(args.root_range_review);root=A.range_review(grant)
    Q.need(review['schema']==REVIEW and review['status']=='ROOT_APPROVED' and review['reviewer']=='root'
      and review['endpoint']==Q.ENDPOINT and review['uid']==1264 and review['reason'].strip(),'ROOT_ONLY_NEW_METADATA_RECOVERY_REVIEW')
    binding=Q.load_ref(review['original_state_binding_reference']);state=Q.literal(args.state_directory)
    Q.need(review['original_state_binding_reference']==Q.ref(state/'binding.json'),'EXACT_IMMUTABLE_ORIGINAL_STATE_BINDING')
    same_binding(review,root,grant,binding,state)
    Q.need(review['metadata_recovery_source_references']==sources(),'EXACT_CURRENT_NEW9_METADATA_SOURCES')
    for r in review['metadata_recovery_source_references']:Q.verify(r)
    failure=Q.load_ref(review['original_failure_event_reference'])
    Q.need(Path(review['original_failure_event_reference']['path']).parent==state
      and failure['status']=='HOLD_EXCEPTION_NO_RETRY_NO_RENEWAL_NO_SIGNALS'
      and 'EXACT_SMALL_REFERENCE_REQUIRED' in failure['traceback'] and 'data_locator' in failure['traceback'],
      'ACTUAL_PRESERVED_V3_LOCATOR_FAILURE_EVENT')
    context=Q.load_ref(review['actual_six_C0_context_reference'])
    context_binding(context,grant,review['original_state_binding_reference'],review['original_failure_event_reference'])
    Q.need(review['original_controller_launch_reference']==context['original_controller_launch_reference'],'ORIGINAL_LAUNCH_REFERENCE_RETAINED')
    Q.verify(review['original_controller_launch_reference'])
    actual=source3_evidence(review['source3_receipt_reference'],review['source3_accounting_reference'])
    Q.need(actual==review['source3_actual_evidence'],'SOURCE3_REVIEW_BINDS_REAL_TERMINAL_NOT_PREDICTED_PASS')
    Q.need(existing_parents([r['accounting_reference'] for r in review['existing52_57_actual_parents']],grant)
      ==review['existing52_57_actual_parents'],'SAME_SIX_ACTUAL_C0_PARENTS_TO_ADOPT')
    inverse();return review


def candidate(a):
    Q.login();grant=Q.ref(a.root_range_review);root=A.range_review(grant);state=Q.literal(a.state_directory)
    Q.need(state==STATE,'ONLY_ORIGINAL_V3_STATE_DIRECTORY');bindingref=Q.ref(state/'binding.json');binding=Q.load_ref(bindingref)
    fixture=source3_evidence(Q.ref(a.source3_receipt),Q.ref(a.source3_accounting))
    contextref=Q.ref(a.actual_context);context=Q.load_ref(contextref)
    context_binding(context,grant,bindingref,Q.ref(a.failure_event))
    parents=existing_parents([r['accounting_reference'] for r in context['six_actual_C0_parents']],grant)
    failure_ref=Q.ref(a.failure_event);failure=Q.load_ref(failure_ref)
    Q.need(Path(failure_ref['path']).parent==state and failure['status']=='HOLD_EXCEPTION_NO_RETRY_NO_RENEWAL_NO_SIGNALS'
      and 'EXACT_SMALL_REFERENCE_REQUIRED' in failure['traceback'] and 'data_locator' in failure['traceback'],'ACTUAL_OLD_V3_FAILURE_REQUIRED')
    review={'schema':REVIEW,'status':'ROOT_REVIEW_REQUIRED','reviewer':'UNSIGNED','reason':None,'endpoint':Q.ENDPOINT,'uid':1264,
      'metadata_recovery_source_references':sources(),'original_root_range_review_reference':grant,
      'original_state_directory':str(state),'original_state_binding_reference':bindingref,
      'original_authorized_unix_seconds':root['authorized_unix_seconds'],'original_deadline_unix_seconds':root['deadline_unix_seconds'],
      'source_references_for_future_children':root['source_references'],'future_children_use_old13_approved_template':True,
      'new_scientific_attempt_for52_57':False,'no_automatic_retry':True,'no_automatic_renewal':True,'no_signals_or_cancel':True,
      'source3_receipt_reference':fixture['receipt_reference'],'source3_accounting_reference':fixture['accounting_reference'],
      'source3_actual_evidence':fixture,'existing52_57_actual_parents':parents,'original_failure_event_reference':failure_ref,
      'actual_six_C0_context_reference':contextref,'original_controller_launch_reference':context['original_controller_launch_reference'],
      'approval_created_by_helper':False,'source_inverse_proof':inverse()}
    same_binding(review,root,grant,binding,state)
    output=Q.literal(a.output);Q.need(Q.ROOT/'control' in output.parents and not output.exists(),'NEW_UNSIGNED_METADATA_REVIEW_ONLY')
    Q.write_new(output,review)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('root-range-review','state-directory','source3-receipt','source3-accounting','failure-event','actual-context','output'):p.add_argument('--'+n,type=Path,required=True)
    candidate(p.parse_args())

if __name__=='__main__':main()