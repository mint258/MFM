"""Post-C0 external seal; writes only exact configuration references, no DATA IO."""
import argparse,json,os
from pathlib import Path
from . import contract as C

def actual_family(candidate,proof,account,raw):
    c=C.meta(candidate);p=C.meta(proof);a=C.meta(account);req=p['request'];jid=str(p['job_id'])
    C.need(c['schema']==C.CANDIDATE and c['status']=='COMPLETE_EXACT_FINAL_CANDIDATE_REQUIRES_ACTUAL_PARENT_C0_AND_ROOT_SEAL'
      and c['current_actual_parent_job_id']==jid and c['current_startup_proof_reference']==proof
      and c['current_parent_C0_claimed'] is False,'EXACT_CURRENT_FAMILY_CANDIDATE_NOT_INDEPENDENT_C0')
    C.need(req['scope_key']=='family_export_day_v1' and req['cpus']==16 and req['wall_seconds']==86400
      and C.meta(p['request_reference'])==req,'REAL_ORIGINAL_GENERIC_FAMILY16_REQUEST')
    C.need(a['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and a['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
      and a['endpoint']=='202.38.247.57:22' and a['uid']==1278 and a['query_returncode']==0 and a['raw_sacct_reference']==raw,
      'REAL_MAIN_FINAL_PARENT_RAW_ACCOUNTING')
    rows=[r for r in a['parents'] if str(r['job_id'])==jid]
    C.need(len(rows)==1 and rows[0]['state']=='COMPLETED' and rows[0]['exit_code']=='0:0' and rows[0]['alloc_cpus']==16,'ACTUAL_PARENT_C0_NOT_PENDING_TIMEOUT_OR_CHILD_ALIAS')
    lines=C.A.pin_bytes(raw,C.Q.read_small).decode('utf-8-sig').splitlines();head=lines[0].split('|')
    rr=[dict(zip(head,line.split('|'))) for line in lines[1:] if line.split('|')[0]==jid]
    C.need(len(rr)==1 and rr[0]['UID']=='1278' and rr[0]['State']=='COMPLETED' and rr[0]['ExitCode']=='0:0'
      and rr[0]['AllocCPUS']=='16','ACTUAL_EXACT_RAW_PARENT_ROW')
    C.need(Path(req['scope_parameters']['output_directory']) in Path(candidate['path']).parents,'CANDIDATE_IN_THIS_ACTUAL_PARENT_OUTPUT')
    return c,p

def candidate(path,proof,account,raw,output):
    refs={k:C.Q.pin(v) for k,v in {'candidate':path,'startup_proof':proof,'accounting':account,'raw':raw}.items()}
    c,p=actual_family(*(refs[k] for k in ('candidate','startup_proof','accounting','raw')))
    value={'schema':'FINAL_LABEL_POST_C0_ROOT_REVIEW_CANDIDATE_V1','status':'PENDING_INDEPENDENT_ROOT_FINAL_REVIEW',
      'actual_parent_references':refs,'release_id':c['release_id'],'release_scope':c['release_scope'],
      'exact_outputs':{k:c[k] for k in ('registry_reference','mapping_reference','normalization_reference','mask_release_reference','size_rho_reference')},
      'joint_policy_reference':c['joint_policy_reference'],'root_reviewed_directive_reference':c['root_reviewed_directive_reference'],
      'required_full_Model_actual_acceptance_reference':None,'reviewer':None,'publish':False,'scientific_DATA_read_or_hashed_on_login':False}
    return C.Q.write_new(Path(output),value)

def publish(review_path,output_directory):
    review_ref=C.Q.pin(review_path);review=C.meta(review_ref)
    C.need(review['schema']=='ROOT_FINAL_LABEL_PUBLICATION_REVIEW_V1' and review['status']=='APPROVED_EXACT_ACTUAL_C0_RELEASE'
      and review['reviewer']=='root','INDEPENDENT_ACTUAL_ROOT_PUBLICATION_REVIEW')
    before=C.meta(review['candidate_reference']);refs=before['actual_parent_references']
    c,p=actual_family(*(refs[k] for k in ('candidate','startup_proof','accounting','raw')))
    C.need(review['exact_outputs']==before['exact_outputs']=={k:c[k] for k in before['exact_outputs']}
      and review['joint_policy_reference']==c['joint_policy_reference'],'EXACT_CANDIDATE_OUTPUTS_AND_JOINT_POLICY_NO_REPLACEMENT')
    policy=C.meta(c['joint_policy_reference']);C.need(policy['status']=='JOINTLY_FROZEN' and policy['actual_final_Model_ack_not_conditional'] is True,
      'STILL_REAL_FINAL_JOINT_POLICY')
    full=c['release_scope']=='FULL_V1'
    if full:
        C.need(c['Pprime_complete'] is True and review['model_actual_acceptance_reference'],'FULL_V1_NEEDS_REAL_PPRIME_AND_REAL_MODEL_RUNTIME')
        m=C.meta(review['model_actual_acceptance_reference'])
        C.need(m['schema']=='ROOT_MODEL_ACTUAL_NATIVE_CONSUMER_ACCEPTANCE_V1' and m['status']=='ACTUAL_REQUIRED_NATIVE_MODEL_CHECKS_ACCEPTED'
          and m['release_candidate_reference']==refs['candidate'] and m['all_required_model_checks_passed'] is True
          and m['actual_runtime_evidence_references'],'REAL_MODEL_NATIVE_CONSUMPTION_NOT_SYNTHETIC_ONLY_OR_CONDITIONAL_REVIEW')
        for r in m['actual_runtime_evidence_references']:C.A.pin_bytes(r,C.Q.read_small)
    out=Path(output_directory).absolute();allowed=C.REPO/'configs/data_v1/releases'
    C.need(out==allowed/c['release_id'] and not out.exists() and not any(q.is_symlink() for q in (out,*out.parents)),
      'FRESH_VERSIONED_ALLOWED_CONFIG_PATH_NO_OVERWRITE_DRAFT_OR_RUNNING_SOURCE')
    out.mkdir(parents=True,mode=0o700);outputs={}
    labels={'label_registry_v3.json':'registry_reference','physical_target_mapping_v3.json':'mapping_reference',
      'normalization_v1.json':'normalization_reference','validity_masks_v1.json':'mask_release_reference','size_families_v1.json':'size_rho_reference'}
    for filename,key in labels.items():
        outputs[key]=C.Q.write_new(out/filename,{'schema':'FINAL_LABEL_CONFIGURATION_REFERENCE_V1','status':'FROZEN_FULL_V1' if full else 'FROZEN_BOUNDED_DIAGNOSTIC_P_D_SCOPE',
          'configuration_kind':key,'configuration_reference':c[key],'release_scope':c['release_scope'],
          'actual_parent_references':refs,'joint_policy_reference':c['joint_policy_reference'],'root_publication_review_reference':review_ref,
          'data_body_not_read_or_rehashed_on_login':True})
    release={'schema':C.RELEASE,'status':'FULL_V1_FROZEN' if full else 'BOUNDED_DIAGNOSTIC_P_D_RELEASE_NOT_FULL_V1',
      'release_id':c['release_id'],'release_scope':c['release_scope'],'configurations':outputs,
      **{k:c[k] for k in labels.values()},'candidate_reference':refs['candidate'],'actual_parent_references':refs,
      'joint_policy_reference':c['joint_policy_reference'],'root_publication_review_reference':review_ref,
      'model_actual_acceptance_reference':review.get('model_actual_acceptance_reference'),
      'D2_published':True,'D4_P_D_published':True,'D4_published':full,'independent_Pprime_published':full,
      'all_writes_within_guide_six_directories':True,'old_draft_and_all_raw_values_and_masks_preserved':True,
      'final_consumer_release':True,'training_ready':full}
    return C.Q.write_new(out/'release.json',release)

def main():
    C.Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('validate');a.add_argument('--directive',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('candidate')
    for n in ('candidate','startup-proof','accounting','raw','output'):a.add_argument('--'+n,required=True)
    a=s.add_parser('publish');a.add_argument('--root-review',required=True);a.add_argument('--output-directory',required=True)
    a=p.parse_args()
    if a.action=='validate':
        result=C.validate_directive(C.meta(C.Q.pin(a.directive)))
        value=C.Q.write_new(Path(a.output),{k:result[k] for k in ('status','missing','source_references','data_references','current_parent_C0_required_for_candidate')})
    elif a.action=='candidate':value=candidate(a.candidate,a.startup_proof,a.accounting,a.raw,a.output)
    else:value=publish(a.root_review,a.output_directory)
    print(value)
if __name__=='__main__':main()
