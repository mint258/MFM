"""Source/small operational headers only. No SCI body/stat/hash at login."""
import argparse
from pathlib import Path
from . import contracts as C
def build(context_path,output):
    C.q.login();ctx=C.load(context_path);out=C.literal(output);C.need(C.ROOT/'control' in out.parents and not out.exists(),'FRESH_DIAGNOSTIC_METADATA_DIRECTORY');out.mkdir(parents=True,mode=0o700)
    required=('strict_parent','fixed_index_authority_reference','resource_authority_reference','cost_decision_reference','python','node','output_directory','startup_proof_path','final_plan_path')
    missing=[k for k in required if ctx.get(k) is None]
    if missing:return C.write_new(out/'NONEXECUTABLE.json',{'status':'NONEXECUTABLE_MISSING_ACTUAL_ROOT_FIELDS','missing':missing,'SCI_opened_statted_or_hashed':False})
    p={k:ctx[k] for k in required};old=C.q.load_ref(p['strict_parent']['plan']);r=C.q.load_ref(p['strict_parent']['receipt'])
    p.update(schema=C.SCHEMA,producer_key=C.KEY,scope_key=C.KEY,stage=C.STAGE,mode='diagnostic735',pilot=False,kind='analysis',endpoint=C.q.ENDPOINT,uid=C.UID,
      run_root=str(C.ROOT),cpus=16,wall_seconds=C.WALL,output_cap_bytes=C.CAP,memory_policy='SLURM_DEFAULT_UNSPECIFIED',role=old['role'],
      frozen_identity_source_references=old['frozen_identity_source_references'],decontamination_source_reference=old['decontamination_source_reference'],
      unknown_locator_reference=C.triple(r['outputs']['unknown_locators']),root_review_reference=None,metadata_status='NONEXECUTABLE_INDEPENDENT_ROOT_REVIEW_REQUIRED')
    bound,data=C.parents(p);p['data_references']=data
    parent=C.unique([*p['strict_parent'].values(),bound['raw_accounting_reference'],p['fixed_index_authority_reference'],*old['norm_parent'].values(),
      bound['A_plan_reference'],bound['DDL_reference'],*old['parent_evidence_references']])
    sources=C.unique([*(C.pin(C.HERE/n) for n in C.FILES),*old['source_references'],*parent,p['resource_authority_reference'],p['cost_decision_reference'],C.pin(context_path)])
    paths={r['path'] for r in data};C.need(not paths&{r['path'] for r in sources+parent},'ALL_LARGE_OR_SMALL_SCI_ARTIFACTS_REMAIN_DATA')
    p.update(parent_evidence_references=parent,source_references=sources);p['scope_parameters']=C.parameters(p)
    p['execution_argv']=[p['python'],'-B','-m',C.MODULE,'--plan',p['final_plan_path'],'--startup-proof',p['startup_proof_path']]
    C.write_new(out/'plan.DRAFT.json',p)
    template={k:p[k] for k in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references')}
    template.update(schema='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1',status='DRAFT_REQUIRES_INDEPENDENT_ROOT_REVIEW',reviewer=None,
      approved_source_references=sources,actual_closed735_parent_and_fixed_index_reviewed=False,fixed_root_first_CPU_SHA_readonly_index_authorized=False)
    C.write_new(out/'root_review.DRAFT.json',template)
    return C.write_new(out/'draft_receipt.json',{'schema':'COCONUT735_SOURCE_ONLY_METADATA_DRAFT_V1','plan_reference':C.pin(out/'plan.DRAFT.json'),
      'root_review_template_reference':C.pin(out/'root_review.DRAFT.json'),'data_locator_count':len(data),'deferred_fixed_index_SHA_created':False,
      'SCI_DATA_opened_statted_or_hashed':False,'actual_structures_DDL_reference':bound['DDL_reference']})
def finalize(draft,review,output):
    from .adapters import REVIEW_FIELDS
    C.q.login();p=C.load(draft);rr=C.pin(review);r=C.q.load_ref(rr);out=C.literal(output)
    C.need(p['metadata_status']=='NONEXECUTABLE_INDEPENDENT_ROOT_REVIEW_REQUIRED' and str(out)==p['final_plan_path'] and not out.exists(),'EXACT_NEW_FINAL_PLAN_PATH')
    C.need(r['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root'
      and r['actual_closed735_parent_and_fixed_index_reviewed'] is True and r['fixed_root_first_CPU_SHA_readonly_index_authorized'] is True,'ACTUAL_ROOT_BOUND_SCOPE_AND_FIXED_ROOT_READ_AUTHORITY')
    for key in REVIEW_FIELDS:C.need(r[key]==p[key],'EXACT_INDEPENDENT_REVIEW_FIELD:'+key)
    C.need(r['approved_source_references']==p['source_references'],'EXACT_SOURCE_SET')
    p.update(root_review_reference=rr,metadata_status='FINALIZED_ACTUAL_ROOT_REVIEW_BOUND');C.parents(p);out.parent.mkdir(parents=True,exist_ok=True);return C.write_new(out,p)
def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='action',required=True);x=s.add_parser('build');x.add_argument('--context',required=True);x.add_argument('--output',required=True)
    x=s.add_parser('finalize');x.add_argument('--draft',required=True);x.add_argument('--root-review',required=True);x.add_argument('--output',required=True);a=p.parse_args()
    print(build(a.context,a.output) if a.action=='build' else finalize(a.draft,a.root_review,a.output))
if __name__=='__main__':main()
