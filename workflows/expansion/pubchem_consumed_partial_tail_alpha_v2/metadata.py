"""Alpha login: small metadata only, no scientific DATA opens or submissions."""
import argparse,copy
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from . import contract as C

def old_accounts(ref):
    a=Q.load_ref(ref)
    Q.need(a['endpoint']==Q.ENDPOINT and a['uid']==1264,'ACTUAL_OLD_ALPHA_ENDPOINT_ACCOUNT')
    rows={p['job_id']:p for p in a['parents']}
    for spec in C.TAILS:
        p=rows[spec['parent']]
        Q.need(p['state']=='FAILED' and p['exit_code']=='3:0' and p['alloc_cpus']==32 and p['node']==spec['node']
          and p['elapsed_raw_seconds']>0,'RETAIN_BOTH_REAL_OLD_FAILED3_PARENTS_AND_COSTS')
    Q.verify(a['raw_sacct_reference'])
    return a

def draft(request_path,out):
    Q.login();r=Q.load(request_path)
    Q.need(r['schema']=='ROOT_REQUESTED_PUBCHEM_CONSUMED_TAIL_V1' and r['requested_by']=='root','EXACT_ROOT_TAIL_REQUEST')
    out=Q.literal(out);Q.need(out.is_relative_to(Q.ROOT/'control') and not out.exists(),'NEW_CONTROL_DIRECTORY')
    account=old_accounts(r['old_accounting_reference']);parents=[];science=None;sources=[]
    for spec in C.TAILS:
        cp,p=C.checkpoint(spec)
        if science is None:science=p['science']
        Q.need(p['science']==science,'SAME_ORIGINAL_FROZEN_SCIENCE_BOTH_PARENTS')
        receipt_path=Path(spec['checkpoint_reference']['path']).parent.parent/'receipt.json'
        receipt_ref=Q.ref(receipt_path);receipt=Q.load_ref(receipt_ref)
        Q.need(receipt['job_id']==spec['parent'] and receipt['partial_descriptors']==[{'index':spec['index'],'reference':spec['checkpoint_reference']}]
          and receipt['runtime_budget']['first_stop_reason']=='WALL_RESERVE_STOP_NEW_TASKS_NATURAL_DRAIN','ACTUAL_NATURALLY_DRAINED_PARTIAL')
        parents.extend([spec['checkpoint_reference'],cp['original_claim_reference'],cp['actual_parent_plan_reference'],receipt_ref,receipt['startup_proof_reference']])
        sources=C.merge(sources,p['source_references'])
    plan={'schema':'ALPHA_CONSUMED_PARTIAL_TAIL_PLAN_V1','status':'PENDING_ROOT_EXACT_REVIEW','endpoint':Q.ENDPOINT,'uid':1264,
      'mode':'consumed_partial_tail','node':r['node'],'cpus':r['cpus'],'wall_seconds':r['wall_seconds'],
      'output_cap_bytes':r['output_cap_bytes'],'output_directory':r['output_directory'],'job_name':r['job_name'],
      'python':str(Q.ROOT/'chemprop_compatible_v2/bin/python'),'software_budget_bytes':64<<30,'rss_stop_bytes':56<<30,
      'tail_specs':copy.deepcopy(list(C.TAILS)),'tail_rows':150638,'science':science,'intent_path':str(C.INTENT),
      'old_accounting_reference':r['old_accounting_reference'],'original_parent_references':C.merge(parents,[r['old_accounting_reference']]),
      'storage_scope_review_reference':r['storage_scope_review_reference'],'cost_gate_reference':r['cost_gate_reference'],'new_source_references':C.sources(),
      'source_references':C.merge(sources,C.sources(),parents,[Q.ref(request_path),r['old_accounting_reference'],r['storage_scope_review_reference'],r['cost_gate_reference']]),'pool_release':False,'old_results_modified':False,
      'plan_path':str(out/'plan.json'),'startup_proof_path':str(out/'proof.json'),
      'cost_reference':{'full500_uniform_phase_core_seconds':17552317,'observed260_related_parent_core_seconds':15878560,
       'scope':'RELATED_PRODUCTION_AND_FAILED_PARENTS_NOT_WHOLE_LINE_LEDGER','environment_fixture_costs_not_all_included':True,'display_reference_rounded_actual_admission_in_cost_gate_reference':True}}
    plan['execution_argv']=[plan['python'],'-B','-m',C.MODULE,'--plan',plan['plan_path'],'--startup-proof',plan['startup_proof_path']]
    check=dict(plan,status='READY');C.validate(check);Q.verify(plan['storage_scope_review_reference'])
    Q.need(not Path(plan['output_directory']).exists() and not C.INTENT.exists(),'NO_OLD_OUTPUT_OR_TAIL_INTENT_RETRY')
    out.mkdir(mode=0o700);candidate=Q.write_new(out/'candidate.json',plan)
    return Q.write_new(out/'review.template.json',{'schema':'ROOT_REVIEWED_EXACT_PUBCHEM_TAIL_PLAN_V1',
      'status':'PENDING','reviewer':None,'candidate_reference':candidate,'old_claims_and_failures_unchanged':True,'only_exact_unread_suffixes':True})
def finalize(candidate_path,review_path):
    Q.login();candidate_ref=Q.ref(candidate_path);p=Q.load_ref(candidate_ref);r=Q.load(review_path)
    Q.need(r['candidate_reference']==candidate_ref and r['status']=='APPROVED' and r['reviewer']=='root','INDEPENDENT_APPROVED_EXACT_CANDIDATE')
    p.update(status='READY',candidate_reference=candidate_ref,root_review_reference=Q.ref(review_path));C.validate(p);C.review(p)
    Q.need(not C.INTENT.exists() and not Path(p['output_directory']).exists(),'FRESH_NOT_ALREADY_CONSUMED_TAILS')
    return Q.write_new(p['plan_path'],p)
def close(receipt_path,account_path,out):
    Q.login();ref=Q.ref(receipt_path);r=Q.load_ref(ref);a=Q.load(account_path);p=a['actual_parent'];Q.verify(a['raw_sacct_reference'])
    Q.need(r['status']=='TWO_LOGICAL_DESCRIPTORS_CPU_CLOSED_ACCOUNTING_PENDING'
      and p['JobIDRaw']==r['job_id'] and p['UID']=='1264' and p['State']=='COMPLETED' and p['ExitCode']=='0:0'
      and int(p['AllocCPUS'])==r['cpus'] and p['NodeList']==r['node']
      and a['query_returncode']==0 and a['endpoint']==Q.ENDPOINT and a['uid']==1264
      and a['allocated_core_seconds']==int(p['ElapsedRaw'])*r['cpus'],'REAL_NEW_PARENT_C0_REQUIRED_NOT_FUTURE_C0')
    for row in r['logical_descriptors']:
        meta=Q.load_ref(row)
        Q.need(meta['logical_rows']==250000 and meta['old_partial_parent_state']=='FAILED'
          and meta['old_partial_parent_exit']=='3:0' and meta['source_row_conservation'] is True,'CPU_LOGICAL_FRAGMENT_CLOSURE')
    return Q.write_new(out,{'schema':'PUBCHEM_ORIGINAL363_412_LOGICAL_CLOSURE_V1','status':'ACTUAL_NEW_PARENT_C0_TWO_ORIGINAL_DESCRIPTORS_CLOSED',
      'producer_receipt_reference':ref,'new_accounting_reference':Q.ref(account_path),'old_accounting_reference':r['old_accounting_reference'],
      'logical_descriptors':r['logical_descriptors'],'old_claims_partial_FAILED_and_costs_unchanged':True,'pool_release':False})
def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('finalize');a.add_argument('--candidate',required=True);a.add_argument('--root-review',required=True)
    a=s.add_parser('close');a.add_argument('--receipt',required=True);a.add_argument('--accounting',required=True);a.add_argument('--output',required=True)
    a=p.parse_args()
    result=draft(a.request,a.output) if a.action=='draft' else finalize(a.candidate,a.root_review) if a.action=='finalize' else close(a.receipt,a.accounting,a.output)
    print(Q.canonical(result).decode())
if __name__=='__main__':main()
