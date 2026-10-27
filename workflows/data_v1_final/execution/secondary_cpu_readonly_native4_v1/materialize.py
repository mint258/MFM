"""Alpha small-metadata source template, plan draft, then independent finalize."""
import argparse,copy
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_moleculenet_native4_identity_v1 import contracts as C
from secondary_moleculenet_csv6_identity_v1 import contracts as CSV
from . import adapters as A


def source_template(manifest_path,output):
    manifest_ref=Q.ref(manifest_path);manifest=Q.load_ref(manifest_ref);refs=[Q.ref(A.HERE/n) for n in A.FILES];old=Q.ref(A.V13)
    Q.need(manifest['schema']=='SB4_SOURCE_ONLY_BUNDLE_MANIFEST_V1','EXACT_SOURCE_ONLY_INSTALLATION_MANIFEST')
    for ref in refs:
        matches=[r for r in manifest['entries'] if r.get('alpha_target_path')==ref['path']]
        Q.need(len(matches)==1 and (matches[0]['bytes'],matches[0]['sha256'])==(ref['bytes'],ref['sha256']),'ACTUAL_TARGET_EQUALS_DECLARED_SOURCE_BUNDLE_BYTES')
    Q.need((old['bytes'],old['sha256'])==(refs[0]['bytes'],refs[0]['sha256']),'UNMODIFIED_V13_CONTROLLER_SOURCE_BYTES')
    return Q.write_new(output,{'schema':'ROOT_SECONDARY_NATIVE4_THIN_SOURCE_REVIEW_V1','status':'PENDING_INDEPENDENT_ROOT_SOURCE_REVIEW','reviewer':None,
        'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'source_manifest_reference':manifest_ref,'source_references':refs,
        'controller_reference':refs[0],'v13_controller_reference':old,'only_native4_profile_protocol':True,'new_queue_algorithm':False})


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_ALPHA_NATIVE4_PROFILE_V1' and v['status']=='REQUESTED_FOR_REVIEW' and v['requested_by']=='root','ROOT_REQUEST_NOT_SCOPE_APPROVAL')
    source_review=A.source_review(v['adapter_source_review_reference']);base=Q.source_review(v['base_controller_review_reference']['path'])
    Q.authority(v['resource_authority_reference']['path']);Q.need(Q.literal(v['storage_review_reference']['path'])==A.STORAGE_SCOPE,'ONLY_CURRENT_SCOPE7')
    Q.verify(v['storage_review_reference']);Q.need(v['node'] in Q.NODES,'ACTUAL_AUTHORIZED_ALPHA_NODE')
    out=Q.literal(out);science=Q.literal(v['output_directory']);proof=Q.literal(v['startup_proof_path'])
    Q.need(Q.ROOT/'control' in out.parents and not out.exists() and Q.ROOT/'artifacts' in science.parents and not science.exists() and not proof.exists(),'FRESH_METADATA_SCIENCE_AND_PROOF_PATHS')
    a=Q.load(C.HERE/'authority792.json');fmt_plan=Q.load_ref(a['format_plan_reference']);fmt_proof=Q.load_ref(a['format_proof_reference'])
    kernel=Q.load_ref(v['kernel_profile_receipt_reference']);kp=Q.load_ref(kernel['plan']);ks=Q.load_ref(kernel['startup_proof'])
    fa=Q.load_ref(v['format_accounting_reference']);ka=Q.load_ref(v['kernel_profile_accounting_reference'])
    parents=A.unique([*(a[k] for k in ('format_receipt_reference','format_plan_reference','format_proof_reference','format_fixture_reference')),
        v['format_accounting_reference'],fa['raw_sacct_reference'],v['kernel_profile_receipt_reference'],v['kernel_profile_accounting_reference'],ka['raw_sacct_reference'],kernel['plan'],kernel['startup_proof']])
    data=[s['payload_reference'] for s in a['sources']]+[s['inventory_reference'] for s in a['sources']]
    sources=A.unique([*fmt_plan['source_references'],*kp['source_references'],*(Q.ref(C.HERE/n) for n in C.FILES),*(Q.ref(A.HERE/n) for n in A.FILES),
        *(Q.ref(CSV.HERE/n) for n in CSV.FILES),*(r['target_locator'] for r in base['sources']),*parents,
        *(s['format_report_reference'] for s in a['sources']),v['adapter_source_review_reference'],source_review['source_manifest_reference'],source_review['v13_controller_reference'],
        v['base_controller_review_reference'],v['resource_authority_reference'],v['cost_decision_reference'],v['storage_review_reference'],Q.ref(request_path)])
    paths={r['path'] for r in data}
    for ref in data:A.body_locator(ref)
    for ref in sources:Q.need(ref['path'] not in paths,'DATA_NOT_LOGIN_METADATA');Q.verify(ref)
    final_path=out/'plan.json';python=v.get('python',kp['python']);Q.need(Path(python).is_absolute(),'EXACT_ABSOLUTE_ALPHA_PYTHON')
    plan={'schema':C.PLAN,'producer_key':C.KEY,'scope_key':C.KEY,'stage':C.STAGE,'mode':'profile','kind':'analysis','pilot':True,'performance_profile':True,
        'scope_parameters':C.PARAMETERS,'scope_mode':C.SCOPE,'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'node':v['node'],'cpus':16,'memory_policy':Q.POLICY,
        'wall_seconds':14400,'output_cap_bytes':C.CAP,'python':python,'output_directory':str(science),'startup_proof_path':str(proof),'root_review_reference':None,
        'execution_argv':[python,'-B','-m',C.MODULE,'--plan',str(final_path),'--startup-proof',str(proof)],'source_references':sources,'data_references':data,
        'parent_evidence_references':parents,'format_authority_reference':Q.ref(C.HERE/'authority792.json'),
        'frozen_identity_source_references':kp['frozen_identity_source_references'],
        **{k:v[k] for k in ('resource_authority_reference','cost_decision_reference','format_accounting_reference','kernel_profile_receipt_reference','kernel_profile_accounting_reference','adapter_source_review_reference')}}
    A.parents(plan);out.mkdir(parents=True,mode=0o700)
    candidate=Q.write_new(out/'plan.candidate.json',plan)
    fields={k:copy.deepcopy(plan[k]) for k in A.REVIEW_FIELDS}
    template={'schema':'EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1','status':'PENDING_INDEPENDENT_ROOT_SCOPE_REVIEW','reviewer':None,**fields,
        'approved_source_references':sources,'source_only_PDB_seam_and_MOL2_unknowns_reviewed':True,'full_or_pool_release':False}
    review_ref=Q.write_new(out/'scope_review.template.json',template)
    return Q.write_new(out/'draft_receipt.json',{'schema':'ALPHA_NATIVE4_PROFILE_METADATA_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_SCOPE_APPROVAL',
        'plan_candidate_reference':candidate,'scope_template_reference':review_ref,'final_plan_path':str(final_path),
        'base_controller_review_reference':v['base_controller_review_reference'],'storage_review_reference':v['storage_review_reference'],
        'scientific_bodies_opened_or_hashed':False,'submission_or_future_body_pin_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='ALPHA_NATIVE4_PROFILE_METADATA_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_SCOPE_APPROVAL','EXACT_PENDING_DRAFT')
    rr=Q.ref(review_path);review=Q.load_ref(rr);template=Q.load_ref(d['scope_template_reference'])
    Q.need(rr!=d['scope_template_reference'] and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','ROOT_ALONE_APPROVES_SCOPE')
    for key,value in template.items():
        if key not in ('status','reviewer'):Q.need(review[key]==value,'EXACT_REVIEW_FIELD:'+key)
    plan=Q.load_ref(d['plan_candidate_reference']);Q.need(plan['root_review_reference'] is None,'ORIGINAL_UNAPPROVED_CANDIDATE')
    plan['root_review_reference']=rr
    for ref in [*plan['source_references'],*plan['parent_evidence_references']]:Q.verify(ref)
    A.parents(plan);ref=Q.write_new(d['final_plan_path'],plan);A.readonly(ref['path'],None,plan['node'],14400)
    return Q.write_new(Path(draft_path).parent/'finalize_receipt.json',{'schema':'ALPHA_NATIVE4_PROFILE_METADATA_FINALIZED_V1','plan_reference':ref,
        'root_scope_review_reference':rr,'base_controller_review_reference':d['base_controller_review_reference'],'storage_review_reference':d['storage_review_reference'],
        'scientific_bodies_opened_or_hashed':False,'sbatch_or_observe_called':False,
        'next_existing_API':'controller.prepare -> controller.submit_held -> controller.observe; Root invocation only'})


def main():
    Q.login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('source-template');a.add_argument('--source-manifest',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    a=p.parse_args()
    if a.action=='source-template':value=source_template(a.source_manifest,a.output)
    elif a.action=='draft':value=draft(a.request,a.output)
    else:value=finalize(a.draft,a.root_review)
    print(value)


if __name__=='__main__':main()
