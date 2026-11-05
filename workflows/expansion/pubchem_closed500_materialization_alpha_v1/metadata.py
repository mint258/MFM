"""Only existing small metadata/Source reads on Alpha login; no DATA or submit."""
import argparse
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from . import contract as C
def draft(request_path,out):
    Q.login();r=Q.load(request_path);Q.need(r['schema']=='ROOT_REQUESTED_CLOSED500_MATERIALIZATION_V1' and r['requested_by']=='root','ROOT_REQUEST')
    out=Q.literal(out);Q.need(not out.exists() and out.is_relative_to(Q.ROOT/'control'),'NEW_CONTROL_DIRECTORY')
    c,fragments,old=C.inputs()
    p={'schema':'ALPHA_CLOSED500_MATERIALIZATION_PLAN_V1','status':'PENDING_ROOT_EXACT_REVIEW','endpoint':Q.ENDPOINT,'uid':1264,
      'mode':'closed500_materialization','node':r['node'],'cpus':r['cpus'],'wall_seconds':r['wall_seconds'],
      'output_cap_bytes':r['output_cap_bytes'],'output_directory':r['output_directory'],'job_name':r['job_name'],
      'python':str(Q.ROOT/'chemprop_compatible_v2/bin/python'),'software_budget_bytes':64<<30,'rss_stop_bytes':56<<30,
      'coverage_reference':C.COVERAGE,'fragments':fragments,'fragment_count':502,'source_rows':C.N,'expected_counts':C.COUNTS,
      'science':old['science'],'intent_path':str(C.INTENT),'no_chemistry_no_filter_no_release':True,
      'storage_scope_review_reference':r['storage_scope_review_reference'],'cost_gate_reference':r['cost_gate_reference'],
      'new_source_references':C.sources(),'source_references':C.merge(C.sources(),old['source_references'],
       [Q.ref(request_path),C.COVERAGE,c['frozen_manifest_reference'],c['new_tail_actual_C0_closure_reference'],
        Q.load_ref(c['new_tail_actual_C0_closure_reference'])['producer_receipt_reference'],r['storage_scope_review_reference'],r['cost_gate_reference']]),
      'plan_path':str(out/'plan.json'),'startup_proof_path':str(out/'proof.json')}
    p['execution_argv']=[p['python'],'-B','-m',C.MODULE,'--plan',p['plan_path'],'--startup-proof',p['startup_proof_path']]
    C.validate(dict(p,status='READY'));Q.need(not C.INTENT.exists() and not Path(p['output_directory']).exists(),'NO_PRIOR_INTENT_OR_OUTPUT_RETRY')
    out.mkdir(parents=True,mode=0o700);ref=Q.write_new(out/'candidate.json',p)
    return Q.write_new(out/'review.template.json',{'schema':'ROOT_EXACT_CLOSED500_IO_REVIEW_V1','status':'PENDING','reviewer':None,
      'candidate_reference':ref,'original_SQL_minimum_CID_alias_semantics':True,'no_chemistry_no_decontamination_no_release':True})
def finalize(candidate_path,review_path):
    Q.login();p=Q.load(candidate_path);p.update(status='READY',candidate_reference=Q.ref(candidate_path),root_review_reference=Q.ref(review_path))
    C.validate(p);C.review(p);Q.need(not C.INTENT.exists() and not Path(p['output_directory']).exists(),'NO_PRIOR_IO_INTENT_OR_OUTPUT')
    return Q.write_new(p['plan_path'],p)
def close(receipt_path,account_path,out):
    Q.login();r=Q.load(receipt_path);a=Q.load(account_path);p=a['actual_parent'];Q.verify(a['raw_sacct_reference'])
    Q.need(r['schema']=='ALPHA_CLOSED500_UNFILTERED_MATERIALIZATION_RECEIPT_V1' and r['status']=='MATERIALIZED_UNFILTERED_NO_RELEASE'
      and r['source_rows']==C.N and r['counts']==C.COUNTS and r['fragment_count']==502
      and p['JobIDRaw']==r['job_id'] and p['UID']=='1264' and p['State']=='COMPLETED' and p['ExitCode']=='0:0'
      and int(p['AllocCPUS'])==r['cpus'] and p['NodeList']==r['node'] and a['query_returncode']==0
      and a['allocated_core_seconds']==int(p['ElapsedRaw'])*r['cpus'],'REAL_MATERIALIZATION_C0_ONLY')
    return Q.write_new(out,{'schema':'ROOT_ACTUAL_CLOSED500_UNFILTERED_MATERIALIZATION_CLOSURE_V1',
      'status':'ACTUAL_PARENT_C0_UNFILTERED_NO_RELEASE','receipt_reference':Q.ref(receipt_path),'accounting_reference':Q.ref(account_path),
      'coverage_reference':C.COVERAGE,'database':r['database'],'input_fragment_manifest_reference':r['input_fragment_manifest_reference'],
      'source_rows':C.N,'counts':C.COUNTS,'decontamination_or_ranked_or_training_release':False})
def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('finalize');a.add_argument('--candidate',required=True);a.add_argument('--root-review',required=True)
    a=s.add_parser('close');a.add_argument('--receipt',required=True);a.add_argument('--accounting',required=True);a.add_argument('--output',required=True)
    a=p.parse_args();r=draft(a.request,a.output) if a.action=='draft' else finalize(a.candidate,a.root_review) if a.action=='finalize' else close(a.receipt,a.accounting,a.output)
    print(Q.canonical(r).decode())
if __name__=='__main__':main()
