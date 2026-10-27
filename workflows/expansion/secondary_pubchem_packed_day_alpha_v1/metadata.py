"""Root-only metadata plan builder; no source index/parts/journal body reads."""
import argparse,copy,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import contracts as O,materialize_shards as M
from . import contracts as C

def build(request_path,output):
    req=Q.load(request_path);Q.need(req['schema']=='ROOT_REQUESTED_ALPHA_PUBCHEM_DAY32_PARENT_V1' and req['requested_by']=='root','ROOT_ONE_ACTUAL_PARENT_REQUEST')
    root=C.cutover(req['cutover_review_reference']);token=req['assignment_token'];assignment=root['assignments'][token]
    frozen=Q.load_ref(req['metadata_freeze_receipt_reference']);Q.need(frozen['schema']=='PUBCHEM_C_METADATA_FREEZE_RECEIPT_V1'
      and frozen['status']=='ROOT_REVIEWED_BUDGET_AND500_PARTITION_METADATA_CLOSED_NO_SUBMISSION' and frozen['shards']==500,'ORIGINAL_ACTUAL_FROZEN500')
    bp=Q.load_ref(frozen['b_plan_reference']);a=Q.load_ref(frozen['a_receipt_reference']);b=Q.load_ref(frozen['b_receipt_reference'])
    Q.need(a['job_id']=='1884794' and a['status']=='ALPHA_PHYSICAL500_COMPLETE_NO_CHEMISTRY' and a['inventory']['part_count']==500
      and a['inventory']['records']==O.N and a['inventory']['all500_parts_equal_Main_SHA_rows_bytes'] is True
      and a['inventory']['gzip_EOF_CRC_revalidated'] is True,'ACTUAL_ALPHA_ORIGINAL500_COMPLETE_TRANSITIVE_PART_AUTHORITY')
    Q.need(b['job_id']=='1884795' and b['status']=='ALPHA_UNIFORM10000_EQUIVALENT_PROFILE_COMPLETE'
      and b['comparison']['compared_rows']==10000 and b['comparison']['scientific_mismatches']==0
      and b['frozen_manifest_reference']==bp['frozen_manifest_reference']==a['frozen_manifest_reference']
      and bp['alpha_inventory_receipt_reference']==frozen['a_receipt_reference'],'REAL_EXACT_PROFILE_NOT_NEW32_PERFORMANCE_PROOF')
    from secondary_pubchem_screening_alpha_v1.guard import account
    parents=C.merge(frozen['actual_parent_evidence_references'],bp['parent_evidence_references'],[frozen['a_accounting_reference'],frozen['b_accounting_reference']])
    account(frozen['a_accounting_reference'],'1884794',Q.ENDPOINT,1264,parents);account(frozen['b_accounting_reference'],'1884795',Q.ENDPOINT,1264,parents)
    manifest=M.validate(Q.load_ref(frozen['full_shard_manifest_reference']));Q.need(root['original_full_shard_manifest_reference']==frozen['full_shard_manifest_reference']
      and manifest['profile_receipt_reference']==frozen['b_receipt_reference'] and manifest['profile_output_budget_reference']==frozen['profile_output_budget_reference'],'SAME_ACTUAL_FROZEN_PARTITION_NO_NEW_SELECTION')
    fields=('raw_reference','main_index_reference','main_evidence_references','metadata_relocation_reference','frozen_manifest_reference',
      'alpha_raw_validation_receipt_reference','alpha_raw_validation_accounting_reference','resource_authority_reference','cost_decision_reference',
      'alpha_inventory_receipt_reference','alpha_inventory_accounting_reference','source_references','parent_evidence_references')
    science={k:copy.deepcopy(bp[k]) for k in fields};science.update(mode='full_shard',accepted_profile_receipt_reference=frozen['b_receipt_reference'],
      accepted_profile_accounting_reference=frozen['b_accounting_reference'],full_shard_manifest_reference=frozen['full_shard_manifest_reference'],
      profile_output_budget_reference=frozen['profile_output_budget_reference'],metadata_freeze_receipt_reference=req['metadata_freeze_receipt_reference'])
    out=Q.literal(output);Q.need(C.BASE in out.parents and not out.exists(),'FRESH_METADATA_DIRECTORY')
    target=Q.literal(req['output_directory']);Q.need(Q.ROOT/'artifacts/pubchem_packed_day32_alpha_v1' in target.parents and not target.exists(),'FRESH_DAY_PARENT_OUTPUT')
    tag=req['job_name'];Q.need(type(tag)is str and C.re.fullmatch('dv1_pcday_[A-Za-z0-9_]+',tag),'SAFE_ONE_PARENT_NAME')
    plan_path=out/'plan.json';proof_path=out/'proof.json';python=bp['python']
    refs=C.merge(science['source_references'],parents,C.sources(),[Q.ref(request_path),req['cutover_review_reference'],req['metadata_freeze_receipt_reference'],
      frozen['b_plan_reference'],frozen['a_receipt_reference'],frozen['b_receipt_reference'],frozen['full_shard_manifest_reference'],frozen['profile_output_budget_reference'],
      root['new_actual_alpha32_day_authority_reference'],root['original_grant_reference'],req['storage_scope_review_reference']])
    plan={'schema':C.SCHEMA,'scope_key':C.KEY,'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'cpus':32,'node':assignment['node'],
      'wall_seconds':86400,'memory_policy':Q.POLICY,'mode':'full_shard','python':python,'job_name':tag,'output_directory':str(target),
      'output_cap_bytes':req['output_cap_bytes'],'cutover_review_reference':req['cutover_review_reference'],'assignment_token':token,
      'descriptor_indices':assignment['indices'],'science':science,'source_references':refs,'parent_evidence_references':parents,
      'data_references':[C.data_ref(a['inventory']['source_index'])],'storage_scope_review_reference':req['storage_scope_review_reference'],
      'startup_proof_path':str(proof_path),'execution_argv':[python,'-B','-m',C.MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)],
      'source_or_science_or_claim_history_modified':False,'automatic_epoch_retry_or_submission':False,'full_source_pool_release_authorized':False}
    plan['scope_parameters']=C.parameters(plan);C.validate(plan);out.mkdir(mode=0o700,parents=True)
    candidate=Q.write_new(out/'plan.candidate.json',plan)
    review={'schema':'ROOT_EXACT_ALPHA_PUBCHEM_DAY32_PARENT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
      'candidate_plan_reference':candidate,'exact_scope':plan['scope_parameters'],'new32_actual_proof_required':True,
      'original500_once_chemical_funnel_outputs_and_quality_unchanged':True,'one_true_day_parent_not_per_chunk_Slurm':True}
    rr=Q.write_new(out/'review.template.json',review)
    return Q.write_new(out/'draft.json',{'schema':'ALPHA_PUBCHEM_DAY32_PARENT_DRAFT_V1','candidate_reference':candidate,'review_template_reference':rr,
      'plan_path':str(plan_path),'source_only_no_jobs_or_claims':True,'scientific_DATA_bodies_read_or_hashed':False})

def finalize(draft_path,review_path):
    draft=Q.load(draft_path);template=Q.load_ref(draft['review_template_reference']);review_ref=Q.ref(review_path);review=Q.load_ref(review_ref)
    Q.need(review=={**template,'status':'APPROVED','reviewer':'root'} and review_ref!=draft['review_template_reference'],'ROOT_INDEPENDENT_EXACT_PARENT_REVIEW')
    plan=Q.load_ref(draft['candidate_reference']);plan.update(root_parent_review_reference=review_ref,candidate_plan_reference=draft['candidate_reference'])
    plan['source_references']=C.merge(plan['source_references'],[review_ref,draft['candidate_reference']]);C.validate(plan)
    return Q.write_new(draft['plan_path'],plan)

def main():
    Q.login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',required=True);a.add_argument('--root-review',required=True);a=p.parse_args()
    print(build(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
