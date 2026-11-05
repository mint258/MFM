"""Root requested bounded full inventory metadata; never reads five DATA bodies."""
import argparse,copy
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_moleculenet_native4_full_v1 import contracts as C
from secondary_moleculenet_csv6_identity_v1 import contracts as CSV
from . import adapters as A


def source_template(manifest_path,output):
    mr=Q.ref(manifest_path);m=Q.load_ref(mr);refs=[Q.ref(A.HERE/n) for n in A.FILES];old=Q.ref(A.V13)
    Q.need(m['schema']=='SB4_SOURCE_ONLY_BUNDLE_MANIFEST_V1','ACTUAL_SOURCE_BUNDLE_MANIFEST')
    for r in refs:
        rows=[v for v in m['entries'] if v.get('alpha_target_path')==r['path']]
        Q.need(len(rows)==1 and (rows[0]['bytes'],rows[0]['sha256'])==(r['bytes'],r['sha256']),'INSTALLED_THREE_THIN_FILES_MATCH_MANIFEST')
    Q.need((old['bytes'],old['sha256'])==(refs[0]['bytes'],refs[0]['sha256']),'V13_CONTROLLER_BYTE_IDENTITY')
    return Q.write_new(output,{'schema':'ROOT_SECONDARY_NATIVE4_FULL_THIN_SOURCE_REVIEW_V1','status':'PENDING_INDEPENDENT_ROOT_SOURCE_REVIEW','reviewer':None,
        'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'source_manifest_reference':mr,'source_references':refs,
        'controller_reference':refs[0],'v13_controller_reference':old,'only_native4_full_physical_inventory_protocol':True,'new_queue_algorithm':False})


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_ALPHA_NATIVE4_FULL_PHYSICAL_INVENTORY_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','ROOT_REQUEST_IS_NOT_SCIENTIFIC_ACCEPTANCE_OR_FINAL_SCOPE_APPROVAL')
    source_review=A.source_review(v['adapter_source_review_reference']);base=Q.source_review(v['base_controller_review_reference']['path'])
    Q.authority(v['resource_authority_reference']['path']);Q.verify(v['storage_review_reference']);Q.need(Q.literal(v['storage_review_reference']['path'])==A.STORAGE_SCOPE,'ONLY_CURRENT_SCOPE7')
    out=Q.literal(out);science=Q.literal(v['output_directory']);proof=Q.literal(v['startup_proof_path'])
    Q.need(Q.ROOT/'control' in out.parents and not out.exists() and Q.ROOT/'artifacts' in science.parents and not science.exists() and not proof.exists()
        and v['node'] in Q.NODES,'NEW_ALPHA_METADATA_OUTPUT_PROOF_AND_AUTHORIZED_NODE')
    rr=C.small(v['native_profile_receipt_reference'],True);ar=C.small(v['native_profile_accounting_reference']);r=Q.load_ref(rr);account=Q.load_ref(ar)
    au=v['accepted_audit_receipt_reference'];Q.need(Q.ROOT/'artifacts' in Q.literal(au['path']).parents and Path(au['path']).name=='receipt.json' and 0<au['bytes']<=2<<20,'ONLY_ACTUAL_SMALL_AUDIT_RECEIPT')
    aa=C.small(v['accepted_audit_accounting_reference']);audit=Q.load_ref(au);audit_account=Q.load_ref(aa)
    refs=[r['plan_reference'],r['startup_proof_reference'],account['raw_sacct_reference'],audit['plan_reference'],audit['startup_proof_reference'],audit_account['raw_sacct_reference']]
    for ref in refs:C.small(ref)
    op=Q.load_ref(r['plan_reference']);ap=Q.load_ref(audit['plan_reference']);parents=C.unique([rr,ar,au,aa,*refs]);data=C.body_refs(r);c=C.census(r)
    paths={ref['path'] for ref in data};Q.need(len(paths)==5,'FIVE_ONLY_PRODUCER_BODY_LOCATORS')
    sources=C.unique([*op['source_references'],*ap['source_references'],*(Q.ref(C.HERE/n) for n in C.FILES),*(Q.ref(A.HERE/n) for n in A.FILES),
        *(Q.ref(CSV.HERE/n) for n in CSV.FILES),*(v['target_locator'] for v in base['sources']),*parents,
        v['adapter_source_review_reference'],source_review['source_manifest_reference'],source_review['v13_controller_reference'],v['base_controller_review_reference'],
        v['resource_authority_reference'],v['cost_decision_reference'],v['storage_review_reference'],Q.ref(request_path)])
    for ref in sources:Q.need(ref['path'] not in paths,'FIVE_BODIES_NOT_LOGIN_SOURCE_METADATA');Q.verify(ref)
    python=v['python'];Q.need(Path(python).is_absolute(),'ACTUAL_ALPHA_ABSOLUTE_PYTHON');final=out/'plan.json'
    plan={'schema':C.PLAN,'producer_key':C.KEY,'scope_key':C.KEY,'stage':C.STAGE,'mode':'full','kind':'analysis','pilot':False,'performance_profile':False,
        'scope_parameters':C.parameters(c),'source_census':c,'scope_mode':C.SCOPE,'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'node':v['node'],
        'cpus':16,'memory_policy':Q.POLICY,'wall_seconds':C.WALL,'output_cap_bytes':C.CAP,'python':python,'output_directory':str(science),'startup_proof_path':str(proof),
        'root_review_reference':None,'execution_argv':[python,'-B','-m',C.MODULE,'--plan',str(final),'--startup-proof',str(proof)],
        'source_references':sources,'data_references':data,'parent_evidence_references':parents,'frozen_identity_source_references':op['frozen_identity_source_references'],
        **{k:v[k] for k in ('native_profile_receipt_reference','native_profile_accounting_reference','accepted_audit_receipt_reference','accepted_audit_accounting_reference',
            'resource_authority_reference','cost_decision_reference','adapter_source_review_reference')}}
    plan['population_once_path']=str(Q.ROOT/'control/native4_full_once_v1'/('population_'+C.fingerprint(plan)+'.json'))
    Q.need(not Path(plan['population_once_path']).exists(),'PRIOR_FULL_POPULATION_ATTEMPT_HOLD_NO_AUTO_RETRY');C.inputs(plan)
    out.mkdir(parents=True,mode=0o700);candidate=Q.write_new(out/'plan.candidate.json',plan)
    template={'schema':'EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1','status':'PENDING_INDEPENDENT_ROOT_SCOPE_REVIEW','reviewer':None,
        **{k:copy.deepcopy(plan[k]) for k in C.REVIEW_FIELDS},'approved_source_references':sources,
        'all39633_physical_SDF_full_inventory_old3195_reuse_reviewed':True,'old_UNKNOWNs_and_component_ID_gaps_preserved':True,
        'automatic_policy_acceptance':False,'full_or_pool_release':False,'population_once_path':plan['population_once_path'],
        'cost_reference677_is_whole_parent_not_pure_key_or_worst_bound':True,'whole4GiB_includes_science_subcap_and8MiB_admin':True}
    return Q.write_new(out/'draft_receipt.json',{'schema':'ALPHA_NATIVE4_FULL_PHYSICAL_INVENTORY_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_SCOPE_APPROVAL',
        'plan_candidate_reference':candidate,'scope_template_reference':Q.write_new(out/'scope_review.template.json',template),'final_plan_path':str(final),
        'base_controller_review_reference':v['base_controller_review_reference'],'storage_review_reference':v['storage_review_reference'],
        'five_DATA_bodies_opened_or_hashed':False,'future_JOB_PASS_or_body_SHA_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='ALPHA_NATIVE4_FULL_PHYSICAL_INVENTORY_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_SCOPE_APPROVAL','PENDING_EXACT_DRAFT')
    rr=Q.ref(review_path);r=Q.load_ref(rr);t=Q.load_ref(d['scope_template_reference'])
    Q.need(rr!=d['scope_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','INDEPENDENT_ROOT_APPROVAL_ONLY')
    for k,value in t.items():
        if k not in ('status','reviewer'):Q.need(r[k]==value,'EXACT_ROOT_REVIEW_FIELD:'+k)
    p=Q.load_ref(d['plan_candidate_reference']);Q.need(p['root_review_reference'] is None,'UNMODIFIED_DRAFT');p['root_review_reference']=rr
    for ref in [*p['source_references'],*p['parent_evidence_references']]:Q.verify(ref)
    C.inputs(p);ref=Q.write_new(d['final_plan_path'],p);A.readonly(ref['path'],None,p['node'],C.WALL)
    return Q.write_new(Path(draft_path).parent/'finalize_receipt.json',{'schema':'ALPHA_NATIVE4_FULL_PHYSICAL_INVENTORY_FINALIZED_V1','plan_reference':ref,
        'root_scope_review_reference':rr,'base_controller_review_reference':d['base_controller_review_reference'],'storage_review_reference':d['storage_review_reference'],
        'DATA_bodies_opened_or_hashed':False,'sbatch_or_observe_called':False,'scientific_or_pool_acceptance':False,'next_API':'existing controller submit/observe/account by Root'})


def main():
    Q.login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('source-template');a.add_argument('--source-manifest',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True);a=p.parse_args()
    if a.action=='source-template':value=source_template(a.source_manifest,a.output)
    elif a.action=='draft':value=draft(a.request,a.output)
    else:value=finalize(a.draft,a.root_review)
    print(value)


if __name__=='__main__':main()
