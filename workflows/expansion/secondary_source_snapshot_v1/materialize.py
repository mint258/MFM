"""Small Root metadata only: independent source/scope reviews, no asset body/AST/tests."""
import argparse,copy
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from . import contracts as C,adapters as A


def source_template(manifest_path,output):
    mr=Q.ref(manifest_path);m=Q.load_ref(mr);refs=[Q.ref(A.HERE/n) for n in A.FILES];old=Q.ref(A.V13)
    Q.need(m['schema']=='SB1_ALPHA_SOURCE_SNAPSHOT_SOURCE_BUNDLE_V1','EXACT_NEW_SOURCE_BUNDLE_MANIFEST')
    for ref in [*(Q.ref(C.HERE/n) for n in C.FILES)]:
        found=[r for r in m['entries'] if r['alpha_target_path']==ref['path']]
        Q.need(len(found)==1 and (found[0]['bytes'],found[0]['sha256'])==(ref['bytes'],ref['sha256']),'ALL10_ACTUAL_ALPHA_SOURCE_BYTES')
    Q.need((old['bytes'],old['sha256'])==(refs[0]['bytes'],refs[0]['sha256']),'EXACT_V13_CONTROLLER_BYTE_IDENTITY')
    guard_origin=C.ROOT/'code/secondary_native4_key_journal_audit_v1/guard.py'
    text=Q.read_small(guard_origin).decode().replace("plan['mode']=='audit'","plan['mode']=='inventory'").replace('only_existing_native4_journal_zero_parse_audit','only_exact_source_snapshot_checks')
    Q.need(text.encode()==Q.read_small(C.HERE/'guard.py'),'ONLY_DECLARED_GUARD_MODE_AND_REVIEW_FLAG_DELTA')
    return Q.write_new(output,{'schema':'ROOT_SECONDARY_SOURCE_SNAPSHOT_THIN_SOURCE_REVIEW_V1','status':'PENDING_INDEPENDENT_ROOT_SOURCE_REVIEW','reviewer':None,
      'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'source_manifest_reference':mr,'source_references':refs,
      'controller_reference':refs[0],'v13_controller_reference':old,'only_exact_source_snapshot_protocol':True,'new_queue_algorithm':False,
      'guard_origin_reference':Q.ref(guard_origin),'guard_only_literal_delta_verified':True})


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_ALPHA_EXACT_SOURCE_SNAPSHOT_V1' and v['status']=='REQUESTED_FOR_REVIEW'
      and v['requested_by']=='root','ROOT_REQUEST_ONLY_NOT_SCOPE_APPROVAL')
    sr=A.source_review(v['adapter_source_review_reference']);base=Q.source_review(v['base_controller_review_reference']['path'])
    Q.authority(v['resource_authority_reference']['path']);Q.need(Q.literal(v['storage_review_reference']['path'])==A.STORAGE_SCOPE,'EXACT_SCOPE7')
    Q.verify(v['storage_review_reference']);Q.need(v['node'] in Q.NODES,'EXACT_ACTUAL_ALPHA_CPU_NODE')
    out=Q.literal(out);body=Q.literal(v['output_directory']);proof=Q.literal(v['startup_proof_path'])
    Q.need(Q.ROOT/'control' in out.parents and not out.exists() and Q.ROOT/'artifacts' in body.parents and not body.exists() and not proof.exists(),'FRESH_SMALL_METADATA_OUTPUT_AND_PROOF')
    asset_fields=('source_manifest_reference','source_universe_reference','git_manifest_reference','main_export_reference','native_git_transport_reference')
    parents=C.unique([*(v[k] for k in asset_fields),*v['parent_evidence_references']])
    runtime=[Q.ROOT/'code/secondary_moleculenet_csv6_identity_v1'/n for n in ('__init__.py','runtime.py','contracts.py')]
    sources=C.unique([*(Q.ref(C.HERE/n) for n in C.FILES),*(Q.ref(p) for p in runtime),
      *(r['target_locator'] for r in base['sources']),*parents,*v['additional_source_references'],
      v['adapter_source_review_reference'],sr['source_manifest_reference'],sr['v13_controller_reference'],sr['guard_origin_reference'],
      v['base_controller_review_reference'],v['resource_authority_reference'],v['cost_decision_reference'],v['storage_review_reference'],Q.ref(request_path)])
    for r in sources:Q.verify(r)
    python=v['python'];Q.need(Path(python).is_absolute(),'ACTUAL_ABSOLUTE_ALPHA_PYTHON');final=out/'plan.json'
    archives=[v['source_archive_reference'],v['git_archive_reference']]
    Q.need(not set(r['path'] for r in archives).intersection(r['path'] for r in sources),'SOURCE_ASSET_BODIES_NOT_SMALL_LOGIN_SOURCES')
    plan={'schema':C.PLAN,'producer_key':C.KEY,'scope_key':C.KEY,'stage':C.STAGE,'mode':'inventory','kind':'analysis','pilot':False,'performance_profile':False,
      'scope_parameters':C.PARAMETERS,'scope_mode':C.SCOPE,'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'node':v['node'],'cpus':16,'memory_policy':Q.POLICY,
      'wall_seconds':C.WALL,'output_cap_bytes':C.CAP,'python':python,'output_directory':str(body),'startup_proof_path':str(proof),'root_review_reference':None,
      'execution_argv':[python,'-B','-m',C.MODULE,'--plan',str(final),'--startup-proof',str(proof)],'source_references':sources,'data_references':archives,
      'source_code_asset_references':archives,'parent_evidence_references':parents,
      **{k:v[k] for k in (*asset_fields,'source_archive_reference','git_archive_reference','resource_authority_reference','cost_decision_reference','adapter_source_review_reference')}}
    C.inputs(plan);out.mkdir(parents=True,mode=0o700);candidate=Q.write_new(out/'plan.candidate.json',plan)
    template={'schema':'EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1','status':'PENDING_INDEPENDENT_ROOT_SCOPE_REVIEW','reviewer':None,
      **{k:copy.deepcopy(plan[k]) for k in C.REVIEW_FIELDS},'approved_source_references':sources,
      'only_exact_source_snapshot_checks':True,'automatic_policy_acceptance':False,'full_or_pool_release':False}
    return Q.write_new(out/'draft_receipt.json',{'schema':'ALPHA_EXACT_SOURCE_SNAPSHOT_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_SCOPE_APPROVAL',
      'plan_candidate_reference':candidate,'scope_template_reference':Q.write_new(out/'scope_review.template.json',template),'final_plan_path':str(final),
      'base_controller_review_reference':v['base_controller_review_reference'],'storage_review_reference':v['storage_review_reference'],
      'source_asset_bodies_opened_or_hashed':False,'AST_or_tests_or_sbatch_called':False,'future_pin_or_acceptance_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='ALPHA_EXACT_SOURCE_SNAPSHOT_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_SCOPE_APPROVAL','EXACT_PENDING_SOURCE_DRAFT')
    rr=Q.ref(review_path);r=Q.load_ref(rr);t=Q.load_ref(d['scope_template_reference'])
    Q.need(rr!=d['scope_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','ROOT_ALONE_APPROVES_EXACT_SOURCE_SCOPE')
    for k,value in t.items():
        if k not in ('status','reviewer'):Q.need(r[k]==value,'EXACT_REVIEW_FIELD:'+k)
    plan=Q.load_ref(d['plan_candidate_reference']);Q.need(plan['root_review_reference'] is None,'UNCHANGED_UNAPPROVED_CANDIDATE');plan['root_review_reference']=rr
    for ref in [*plan['source_references'],*plan['parent_evidence_references']]:Q.verify(ref)
    C.inputs(plan);pr=Q.write_new(d['final_plan_path'],plan);A.readonly(pr['path'],None,plan['node'],C.WALL)
    return Q.write_new(Path(draft_path).parent/'finalize_receipt.json',{'schema':'ALPHA_EXACT_SOURCE_SNAPSHOT_FINALIZED_V1','plan_reference':pr,
      'root_scope_review_reference':rr,'base_controller_review_reference':d['base_controller_review_reference'],'storage_review_reference':d['storage_review_reference'],
      'source_asset_bodies_opened_or_hashed':False,'AST_tests_or_sbatch_called':False,'Main_or_scientific_acceptance':False,
      'next_API':'original v13 prepare->submit_held->observe via exact-byte thin controller; Root only'})


def main():
    Q.login();p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('source-template');a.add_argument('--source-manifest',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True);a=p.parse_args()
    if a.action=='source-template':v=source_template(a.source_manifest,a.output)
    elif a.action=='draft':v=draft(a.request,a.output)
    else:v=finalize(a.draft,a.root_review)
    print(v)


if __name__=='__main__':main()
