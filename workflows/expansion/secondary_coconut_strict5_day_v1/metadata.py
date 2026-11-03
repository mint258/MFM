"""Login: SOURCE/small headers only; no identity DATA body or new DATA hash."""
import argparse,json,os
from pathlib import Path
from . import contracts as C
from .io import triple

def unique(refs):
    out={}
    for r in refs:
        C.need(r['path'] not in out or out[r['path']]==r,'CONFLICTING_PRODUCER_REFERENCE');out[r['path']]=r
    return list(out.values())

def build(context,output):
    C.q.login();ctx=C.load(context);out=C.literal(output);C.need(not out.exists() and C.ROOT/'control' in out.parents,'FRESH_SMALL_STRICT5_METADATA');out.mkdir(parents=True,mode=0o700)
    pp=ctx['norm_parent'];r=C.q.load_ref(pp['receipt']);old=C.q.load_ref(pp['plan']);native=C.q.load_ref(pp['A_receipt']);outputs=C.q.load_ref(pp['outputs'])
    lookup={x['path']:triple(x) for x in outputs};parts=[lookup[x['Parquet_path']] for x in r['closed_parts']]
    properties=[triple(x) for x in native['physical_output_references'] if x['path'].endswith('/properties.raw_identity.parquet')]
    C.need(len(parts)==46 and len(properties)==1,'EXACT_CLOSED_NORM46_AND_NATIVE_FORMULA1');data=parts+properties
    p={k:ctx[k] for k in ('python','node','output_cap_bytes','output_directory','startup_proof_path','role')}
    C.need(p['role']=='ALL_SOURCE_NATIVE_SPLIT_UNKNOWN','NO_INVENTED_NATIVE_TRAIN_TEST_ROLE')
    p.update(root_review_reference=None,metadata_status='NONEXECUTABLE_ROOT_REVIEW_DRAFT',final_plan_path=ctx['final_plan_path'])
    p.update(schema=C.SCHEMA,producer_key=C.KEY,scope_key=C.KEY,stage=C.STAGE,mode='full',pilot=False,kind='analysis',
      endpoint=C.q.ENDPOINT,uid=1264,run_root=str(C.ROOT),cpus=16,wall_seconds=86400,memory_policy='SLURM_DEFAULT_UNSPECIFIED',
      norm_parent=pp,frozen_identity_source_references=old['frozen_identity_source_references'],
      resource_authority_reference=ctx['resource_authority_reference'],cost_decision_reference=ctx['cost_decision_reference'],
      decontamination_source_reference=C.pin(C.HERE/'frozen/decontamination.py'),data_references=data)
    expected=C.load(C.HERE/'frozen_sources.json')['decontamination_current_Main_source']
    actual=C.pin(C.HERE/'frozen/decontamination.py')
    C.need(actual==p['decontamination_source_reference'] and (actual['bytes'],actual['sha256'])==(expected['bytes'],expected['sha256']),
        'EXACT_ACTUALLY_INSTALLED_STRICT5_SOURCE_ASSET_NOT_ASSUMED_ALPHA_COPY')
    parent=unique([*pp.values(),*old['parent_evidence_references'],*old['source_references'],r['accepted_profile'],r['A_full_receipt']])
    source=unique([*(C.pin(C.HERE/n) for n in C.FILES),*old['source_references'],p['decontamination_source_reference'],
      p['resource_authority_reference'],p['cost_decision_reference'],C.pin(context)])
    denied={x['path'] for x in data};C.need(not denied&{x['path'] for x in source+parent},'ALL47_IDENTITY_BODIES_ARE_DATA_NOT_SMALL_SOURCE')
    p.update(parent_evidence_references=parent,source_references=source);p['scope_parameters']=C.parameters(p)
    p['execution_argv']=[p['python'],'-B','-m',C.MODULE,'--plan',p['final_plan_path'],'--startup-proof',p['startup_proof_path']]
    C.norm_parent(p);C.write_new(out/'plan.DRAFT.json',p)
    review={k:p[k] for k in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds',
      'output_cap_bytes','execution_argv','data_references','parent_evidence_references')}
    review.update(schema='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1',status='DRAFT_REQUIRES_ROOT_REVIEW',reviewer=None,
      approved_source_references=source,actual_norm_parent_and_unknowns_reviewed=False,all_physical_rows_including_no_key_authorized=False)
    C.write_new(out/'root_review.DRAFT.json',review)
    C.write_new(out/'draft_receipt.json',{'schema':'COCONUT_STRICT5_SMALL_METADATA_DRAFT_V1','plan_reference':C.pin(out/'plan.DRAFT.json'),
      'root_review_template_reference':C.pin(out/'root_review.DRAFT.json'),'DATA_locator_count':47,'identity_DATA_bodies_opened_or_hashed':False,
      'producer_parent_job_id':'1884790','Alpha_strict5_asset_actual_installed_Source_verified':actual,'no_submission_or_Root_approval_claimed':True})

def finalize(draft_path,review_path,output):
    from .adapters import REVIEW_FIELDS
    C.q.login();p=C.load(draft_path);ref=C.pin(review_path);review=C.q.load_ref(ref);target=C.literal(output)
    C.need(p['metadata_status']=='NONEXECUTABLE_ROOT_REVIEW_DRAFT' and str(target)==p['final_plan_path'] and not target.exists(),
        'FRESH_EXACT_PREDECLARED_FINAL_PLAN_PATH_NOT_FUTURE_HASH')
    C.need(review['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review['status']=='APPROVED_FOR_EXACT_STAGE'
      and review['reviewer']=='root' and review['actual_norm_parent_and_unknowns_reviewed'] is True
      and review['all_physical_rows_including_no_key_authorized'] is True,'ACTUAL_INDEPENDENT_ROOT_SCOPE_REVIEW')
    for key in REVIEW_FIELDS:C.need(review[key]==p[key],'EXACT_REVIEWED_FINAL_SCOPE:'+key)
    C.need(review['approved_source_references']==p['source_references'],'EXACT_REVIEWED_CODE_SOURCE_SET')
    p.update(root_review_reference=ref,metadata_status='FINALIZED_ACTUAL_ROOT_REVIEW_BOUND');C.norm_parent(p)
    target.parent.mkdir(parents=True,exist_ok=True);return C.write_new(target,p)

def candidate(receipt_ref,account_ref,output):
    """Only an actual C0 can produce a candidate; never update Root config."""
    r=C.q.load_ref(receipt_ref);account=C.q.load_ref(account_ref);plan=C.q.load_ref(r['plan_reference']);proof=C.q.load_ref(r['startup_proof_reference'])
    from secondary_coconut_identity_norm_full_v1.contracts import account as original_account
    original_account(account_ref,r['job_id'],r['node'],[account_ref,account['raw_sacct_reference']])
    C.need(r['schema']=='COCONUT_STRICT5_DAY_RECEIPT_V1' and r['complete_physical_source'] is True and r['READY_candidate'] is True
      and r['status']=='FULL_STRICT5_CONSERVATIVE_COVERAGE_REQUIRES_ROOT_REVIEW' and proof['job_id']==r['job_id']
      and proof['plan_reference']==r['plan_reference'] and proof['scope_key']==C.KEY,'ACTUAL_COMPLETE_STRICT5_C0_NOT_PARTIAL_OR_PENDING')
    coverage=C.q.load_ref(r['coverage_reference']);C.need(coverage['all_splits'] is True and coverage['unresolved_without_identity_or_composition']==0
      and coverage['observed_physical_rows_by_table']==C.COUNTS and coverage['original_consumer_all_identity_rows_readback']==coverage['expected_identity_records'],
      'WHOLE_NATIVE_COVERAGE_AND_ORIGINAL_STRICT5_READBACK_NO_UNKNOWN_WAIVER')
    value={'dataset':'coconut','status':'ALPHA_READY_CANDIDATE_REQUIRES_ROOT_ALIAS_REVIEW','version':'COCONUT_NORM1884790_'+plan['norm_parent']['receipt']['sha256'],
      'required_roles':[plan['role']],'required_subdatasets':['molecules','entries'],'identities':coverage['identities'],
      'coverage_evidence':r['coverage_reference'],'raw_artifacts':coverage['raw_artifacts'],
      'actual_closure':{'receipt':receipt_ref,'proof':r['startup_proof_reference'],'accounting':account_ref,'raw':account['raw_sacct_reference']},
      'source_norm_parent':plan['norm_parent'],'no_Main_path_or_transferred_byte_equivalence_claimed':True,'Root_config_modified':False}
    return C.write_new(C.literal(output),value)

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    b=sub.add_parser('build');b.add_argument('--context',required=True);b.add_argument('--output',required=True)
    f=sub.add_parser('finalize');f.add_argument('--draft',required=True);f.add_argument('--root-review',required=True);f.add_argument('--output',required=True)
    k=sub.add_parser('candidate');k.add_argument('--receipt',required=True);k.add_argument('--account',required=True);k.add_argument('--output',required=True)
    a=p.parse_args()
    if a.action=='build':return build(a.context,a.output)
    if a.action=='finalize':return finalize(a.draft,a.root_review,a.output)
    return candidate(C.pin(a.receipt),C.pin(a.account),a.output)
if __name__=='__main__':main()
