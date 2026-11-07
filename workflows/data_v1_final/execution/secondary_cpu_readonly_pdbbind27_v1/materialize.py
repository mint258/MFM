"""Small metadata only: source template -> independent Root source approval -> draft/finalize."""
import argparse,copy
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pdbbind_index27_extract_v1 import contracts as C
from secondary_moleculenet_csv6_identity_v1 import contracts as CSV
from . import adapters as A


def source_template(manifest_path,output):
    mr=Q.ref(manifest_path);m=Q.load_ref(mr);refs=[Q.ref(A.HERE/n) for n in A.FILES];old=Q.ref(A.V13)
    Q.need(m['schema']=='SB4_SOURCE_ONLY_BUNDLE_MANIFEST_V1','EXACT_SOURCE_BUNDLE_MANIFEST')
    for ref in [*refs,*(Q.ref(C.HERE/n) for n in C.FILES)]:
        rows=[r for r in m['entries'] if r.get('alpha_target_path')==ref['path']]
        Q.need(len(rows)==1 and (rows[0]['bytes'],rows[0]['sha256'])==(ref['bytes'],ref['sha256']),'ALL10_ACTUAL_INSTALLED_SOURCE_BYTES')
    Q.need((old['bytes'],old['sha256'])==(refs[0]['bytes'],refs[0]['sha256']),'UNCHANGED_V13_CONTROLLER_BYTES')
    return Q.write_new(output,{'schema':'ROOT_SECONDARY_PDBBIND27_THIN_SOURCE_REVIEW_V1','status':'PENDING_INDEPENDENT_ROOT_SOURCE_REVIEW','reviewer':None,
        'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'source_manifest_reference':mr,'source_references':refs,
        'controller_reference':refs[0],'v13_controller_reference':old,'only_original27_identity_opaque_index_protocol':True,'new_queue_algorithm':False})


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_ALPHA_PDBBIND_GENERAL27_INDEX_EVIDENCE_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','ROOT_REQUEST_NOT_IDENTITY_ACCEPTANCE_OR_SCOPE_APPROVAL')
    sr=A.source_review(v['adapter_source_review_reference']);base=Q.source_review(v['base_controller_review_reference']['path'])
    Q.authority(v['resource_authority_reference']['path']);Q.need(Q.literal(v['storage_review_reference']['path'])==A.STORAGE_SCOPE,'EXACT_SCOPE7');Q.verify(v['storage_review_reference'])
    Q.need(v['node'] in Q.NODES,'REAL_ALPHA_NODE_FROM_ALLOWLIST');out=Q.literal(out);science=Q.literal(v['output_directory']);proof=Q.literal(v['startup_proof_path'])
    Q.need(Q.ROOT/'control' in out.parents and not out.exists() and Q.ROOT/'artifacts' in science.parents and not science.exists() and not proof.exists(),'NEW_METADATA_OUTPUT_AND_PROOF')
    d=C.discover(v);parents=d['parents'];inherited=[]
    for old_plan in (d['full_plan'],d['profile_plan'],d['format_plan'],d['acquisition_plan']):inherited.extend(old_plan['source_references'])
    sources=C.unique([*(Q.ref(C.HERE/n) for n in C.FILES),*(Q.ref(A.HERE/n) for n in A.FILES),*(Q.ref(CSV.HERE/n) for n in CSV.FILES),
        *inherited,*(r['target_locator'] for r in base['sources']),*parents,v['adapter_source_review_reference'],sr['source_manifest_reference'],sr['v13_controller_reference'],
        v['base_controller_review_reference'],v['resource_authority_reference'],v['cost_decision_reference'],v['storage_review_reference'],Q.ref(request_path)])
    body_paths={r['path'] for r in d['data']}
    for ref in sources:Q.need(ref['path'] not in body_paths,'ORIGINAL_BODY_IS_DATA_NEVER_SMALL_SOURCE');Q.verify(ref)
    python=v['python'];Q.need(Path(python).is_absolute(),'ACTUAL_ABSOLUTE_ALPHA_PYTHON');final=out/'plan.json'
    plan={'schema':C.PLAN,'producer_key':C.KEY,'scope_key':C.KEY,'stage':C.STAGE,'mode':'evidence','kind':'analysis','pilot':False,'performance_profile':False,
        'scope_parameters':C.PARAMETERS,'scope_mode':C.SCOPE,'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'node':v['node'],'cpus':16,'memory_policy':Q.POLICY,
        'wall_seconds':C.WALL,'output_cap_bytes':C.CAP,'python':python,'output_directory':str(science),'startup_proof_path':str(proof),'root_review_reference':None,
        'execution_argv':[python,'-B','-m',C.MODULE,'--plan',str(final),'--startup-proof',str(proof)],'source_references':sources,'data_references':d['data'],
        'parent_evidence_references':parents,**{k:v[k] for k in ('full_inventory_receipt_reference','full_inventory_accounting_reference',
            'resource_authority_reference','cost_decision_reference','adapter_source_review_reference')}}
    C.inputs(plan);out.mkdir(parents=True,mode=0o700);candidate=Q.write_new(out/'plan.candidate.json',plan)
    template={'schema':'EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1','status':'PENDING_INDEPENDENT_ROOT_SCOPE_REVIEW','reviewer':None,
        **{k:copy.deepcopy(plan[k]) for k in C.REVIEW_FIELDS},'approved_source_references':sources,
        'only_original27_identity_and_opaque_index_evidence':True,'automatic_policy_acceptance':False,'full_or_pool_release':False}
    return Q.write_new(out/'draft_receipt.json',{'schema':'ALPHA_PDBBIND27_INDEX_EVIDENCE_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_SCOPE_APPROVAL',
        'plan_candidate_reference':candidate,'scope_template_reference':Q.write_new(out/'scope_review.template.json',template),'final_plan_path':str(final),
        'base_controller_review_reference':v['base_controller_review_reference'],'storage_review_reference':v['storage_review_reference'],
        'scientific_bodies_opened_or_hashed':False,'future_DATA_pin_PASS_or_job_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='ALPHA_PDBBIND27_INDEX_EVIDENCE_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_SCOPE_APPROVAL','EXACT_PENDING_DRAFT')
    rr=Q.ref(review_path);r=Q.load_ref(rr);t=Q.load_ref(d['scope_template_reference'])
    Q.need(rr!=d['scope_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','ROOT_ALONE_APPROVES_EXACT_OPAQUE_INDEX_SCOPE')
    for k,x in t.items():
        if k not in ('status','reviewer'):Q.need(r[k]==x,'EXACT_ROOT_REVIEW_FIELD:'+k)
    p=Q.load_ref(d['plan_candidate_reference']);Q.need(p['root_review_reference'] is None,'UNMODIFIED_DRAFT');p['root_review_reference']=rr
    for ref in [*p['source_references'],*p['parent_evidence_references']]:Q.verify(ref)
    C.inputs(p);ref=Q.write_new(d['final_plan_path'],p);A.readonly(ref['path'],None,p['node'],C.WALL)
    return Q.write_new(Path(draft_path).parent/'finalize_receipt.json',{'schema':'ALPHA_PDBBIND27_INDEX_EVIDENCE_FINALIZED_V1','plan_reference':ref,
        'root_scope_review_reference':rr,'base_controller_review_reference':d['base_controller_review_reference'],'storage_review_reference':d['storage_review_reference'],
        'scientific_bodies_opened_or_hashed':False,'sbatch_or_observe_called':False,'identity_or_pool_acceptance':False,
        'next_API':'existing controller.prepare -> submit_held -> observe; Root only'})


def main():
    Q.login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('source-template');a.add_argument('--source-manifest',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True);a=p.parse_args()
    if a.action=='source-template':v=source_template(a.source_manifest,a.output)
    elif a.action=='draft':v=draft(a.request,a.output)
    else:v=finalize(a.draft,a.root_review)
    print(v)


if __name__=='__main__':main()
