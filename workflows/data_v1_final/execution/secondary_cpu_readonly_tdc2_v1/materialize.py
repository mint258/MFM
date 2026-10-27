"""Small-metadata relocation, independent Root source review, draft and finalize."""
import argparse,copy
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_tdc_exact2_composition_v1 import contracts as C
from secondary_moleculenet_csv6_identity_v1 import contracts as CSV
from secondary_coconut_identity_norm_profile_v1 import contracts as B
from . import adapters as A


def relocation(request_path,output):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_TDC_EXACT2_EVIDENCE_RELOCATION_V1' and v['requested_by']=='root',
        'ROOT_SUPPLIED_ACTUAL_MAIN_TRIPLES_AND_ALPHA_LOCATORS')
    rows=v['metadata_aliases'];Q.need(len(rows)==len(C.META_KEYS) and {r['key'] for r in rows}==set(C.META_KEYS),'EXACT15_METADATA_COPIES')
    copies=[]
    for r in rows:
        origin=C.metadata_origin(r['key'],r['origin_reference']);path=Q.literal(r['target_path'])
        Q.need(Q.ROOT/'control' in path.parents or Q.ROOT/'metadata' in path.parents,'ONLY_ALPHA_SMALL_METADATA_COPY_DIRECTORY')
        target=Q.ref(path)
        Q.need((origin['bytes'],origin['sha256'])==(target['bytes'],target['sha256']),'ACTUAL_ALPHA_SMALL_COPY_EQUALS_MAIN_ORIGINAL_BYTES')
        copies.append({'key':r['key'],'origin_reference':origin,'target_reference':target})
    copies=sorted(copies,key=lambda x:C.META_KEYS.index(x['key']));d=Q.load_ref(copies[0]['target_reference'])
    identity=Q.load_ref(next(r['target_reference'] for r in copies if r['key']=='identity'))
    originals=[*d['selected_original_event_DATA_references'],identity['input_reference']]
    Q.need([r['key'] for r in v['data_aliases']]==['source_events','result_events','archive'],'ONLY_EXISTING_TWO_EVENTS_AND_OFFICIAL_ZIP')
    aliases=[]
    for r,old in zip(v['data_aliases'],originals):
        Q.need(C.triple(r['origin_reference'],main=True)==old,'UPSTREAM_PRODUCER_BODY_PIN_NOT_A_NEW_LOGIN_HASH')
        target=Q.literal(r['target_path']);s=target.lstat();Q.need(target.is_file() and not target.is_symlink() and s.st_uid==1264 and s.st_size==old['bytes'],
            'SIZE_ONLY_ALPHA_COPY_OBSERVATION_NO_BODY_READ_OR_SHA')
        aliases.append({'key':r['key'],'origin_reference':old,'target_reference':{'path':str(target),'bytes':old['bytes'],'sha256':old['sha256']},
            'target_current_SHA_verification':'PENDING_THIS_JOB_CPU_AFTER_FIXTURES','login_observation':'LSTAT_SIZE_ONLY'})
    return Q.write_new(output,{'schema':'TDC_EXACT2_MAIN_TO_ALPHA_EVIDENCE_RELOCATION_V1','origin_endpoint':C.MAIN_ENDPOINT,'origin_uid':1278,
        'target_endpoint':Q.ENDPOINT,'target_uid':1264,'metadata_copies':copies,'data_aliases':aliases,
        'scientific_body_SHA_verified_on_login':False,'policy_or_scientific_acceptance':False,'Root_request_reference':Q.ref(request_path)})


def source_template(manifest_path,output):
    mr=Q.ref(manifest_path);m=Q.load_ref(mr);refs=[Q.ref(A.HERE/n) for n in A.FILES];old=Q.ref(A.V13)
    Q.need(m['schema']=='SB4_SOURCE_ONLY_BUNDLE_MANIFEST_V1','EXACT_SOURCE_BUNDLE_MANIFEST')
    for ref in refs:
        rows=[r for r in m['entries'] if r.get('alpha_target_path')==ref['path']]
        Q.need(len(rows)==1 and (rows[0]['bytes'],rows[0]['sha256'])==(ref['bytes'],ref['sha256']),'ACTUAL_ALL_THREE_INSTALLED_ADAPTER_BYTES')
    Q.need((old['bytes'],old['sha256'])==(refs[0]['bytes'],refs[0]['sha256']),'CONTROLLER_BYTE_IDENTICAL_TO_V13')
    return Q.write_new(output,{'schema':'ROOT_SECONDARY_TDC2_THIN_SOURCE_REVIEW_V1','status':'PENDING_INDEPENDENT_ROOT_SOURCE_REVIEW','reviewer':None,
        'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'source_manifest_reference':mr,'source_references':refs,
        'controller_reference':refs[0],'v13_controller_reference':old,'only_TDC_exact2_atoms_only_protocol':True,'new_queue_algorithm':False})


def draft(request_path,out):
    v=Q.load(request_path);Q.need(v['schema']=='ROOT_REQUESTED_ALPHA_TDC_EXACT2_ATOMS_ONLY_EVIDENCE_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','ROOT_REQUEST_NOT_POLICY_OR_SCOPE_APPROVAL')
    sr=A.source_review(v['adapter_source_review_reference']);base=Q.source_review(v['base_controller_review_reference']['path'])
    Q.authority(v['resource_authority_reference']['path']);Q.need(Q.literal(v['storage_review_reference']['path'])==A.STORAGE_SCOPE,'EXACT_CURRENT_SCOPE7')
    Q.verify(v['storage_review_reference']);Q.need(v['node'] in Q.NODES,'ACTUAL_ALPHA_NODE')
    out=Q.literal(out);science=Q.literal(v['output_directory']);proof=Q.literal(v['startup_proof_path'])
    Q.need(Q.ROOT/'control' in out.parents and not out.exists() and Q.ROOT/'artifacts' in science.parents and not science.exists() and not proof.exists(),'NEW_METADATA_OUTPUT_AND_PROOF')
    m=Q.load_ref(v['main_relocation_reference']);parents=C.unique([r['target_reference'] for r in m['metadata_copies']]);data=[r['target_reference'] for r in m['data_aliases']]
    frozen={k:Q.ref(Q.ROOT/'code'/r[0]) for k,r in B.FROZEN.items()}
    csv=v['frozen_csv_source_references']
    sources=C.unique([*(Q.ref(C.HERE/n) for n in C.FILES),*(Q.ref(A.HERE/n) for n in A.FILES),*(Q.ref(CSV.HERE/n) for n in CSV.FILES),
        *(Q.ref(Q.ROOT/'code/secondary_coconut_identity_norm_profile_v1'/n) for n in ('__init__.py','contracts.py','runtime.py','run.py')),
        *(r['target_locator'] for r in base['sources']),*parents,*frozen.values(),
        *(Q.ref(Q.ROOT/'code'/p) for p in ('workflows/expansion/__init__.py','workflows/expansion/identity_v2/__init__.py',
            'workflows/expansion/identity_v2/readers_v2.py','workflows/expansion/tdc_zip44_identity_main_v1/__init__.py',
            'workflows/expansion/secondary_missing11_identity_format_probe_v1/__init__.py')),
        *(r['target_reference'] for r in csv.values()),v['main_relocation_reference'],v['adapter_source_review_reference'],sr['source_manifest_reference'],sr['v13_controller_reference'],
        v['base_controller_review_reference'],v['resource_authority_reference'],v['cost_decision_reference'],v['storage_review_reference'],Q.ref(request_path)])
    paths={r['path'] for r in data}
    for r in data:C.triple(r)
    for r in sources:Q.need(r['path'] not in paths,'DATA_NOT_READ_AS_METADATA');Q.verify(r)
    python=v['python'];Q.need(Path(python).is_absolute(),'ABSOLUTE_ACTUAL_ALPHA_PYTHON')
    final=out/'plan.json'
    plan={'schema':C.PLAN,'producer_key':C.KEY,'scope_key':C.KEY,'stage':C.STAGE,'mode':'evidence','kind':'analysis','pilot':False,'performance_profile':False,
        'scope_parameters':C.PARAMETERS,'scope_mode':C.SCOPE,'endpoint':Q.ENDPOINT,'uid':1264,'run_root':str(Q.ROOT),'node':v['node'],'cpus':16,'memory_policy':Q.POLICY,
        'wall_seconds':C.WALL,'output_cap_bytes':C.CAP,'python':python,'output_directory':str(science),'startup_proof_path':str(proof),'root_review_reference':None,
        'execution_argv':[python,'-B','-m',C.MODULE,'--plan',str(final),'--startup-proof',str(proof)],'source_references':sources,'data_references':data,
        'parent_evidence_references':parents,'main_relocation_reference':v['main_relocation_reference'],'frozen_identity_source_references':frozen,'frozen_csv_source_references':csv,
        **{k:v[k] for k in ('resource_authority_reference','cost_decision_reference','adapter_source_review_reference')}}
    C.inputs(plan);out.mkdir(parents=True,mode=0o700);candidate=Q.write_new(out/'plan.candidate.json',plan)
    template={'schema':'EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1','status':'PENDING_INDEPENDENT_ROOT_SCOPE_REVIEW','reviewer':None,
        **{k:copy.deepcopy(plan[k]) for k in C.REVIEW_FIELDS},'approved_source_references':sources,
        'new_SMILES_atoms_only_evidence_seam_reviewed':True,'automatic_policy_acceptance':False,'full_or_pool_release':False}
    return Q.write_new(out/'draft_receipt.json',{'schema':'ALPHA_TDC_EXACT2_ATOMS_ONLY_METADATA_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_SCOPE_APPROVAL',
        'plan_candidate_reference':candidate,'scope_template_reference':Q.write_new(out/'scope_review.template.json',template),'final_plan_path':str(final),
        'base_controller_review_reference':v['base_controller_review_reference'],'storage_review_reference':v['storage_review_reference'],
        'scientific_bodies_opened_or_hashed':False,'future_body_pin_or_PASS_or_job_created':False})


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='ALPHA_TDC_EXACT2_ATOMS_ONLY_METADATA_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_SCOPE_APPROVAL','EXACT_PENDING_DRAFT')
    rr=Q.ref(review_path);r=Q.load_ref(rr);t=Q.load_ref(d['scope_template_reference'])
    Q.need(rr!=d['scope_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root','ROOT_ALONE_APPROVES_EXACT_EVIDENCE_SCOPE')
    for k,x in t.items():
        if k not in ('status','reviewer'):Q.need(r[k]==x,'ROOT_EXACT_REVIEW_FIELD:'+k)
    p=Q.load_ref(d['plan_candidate_reference']);Q.need(p['root_review_reference'] is None,'UNMODIFIED_DRAFT');p['root_review_reference']=rr
    for ref in [*p['source_references'],*p['parent_evidence_references']]:Q.verify(ref)
    C.inputs(p);ref=Q.write_new(d['final_plan_path'],p);A.readonly(ref['path'],None,p['node'],C.WALL)
    return Q.write_new(Path(draft_path).parent/'finalize_receipt.json',{'schema':'ALPHA_TDC_EXACT2_ATOMS_ONLY_METADATA_FINALIZED_V1','plan_reference':ref,
        'root_scope_review_reference':rr,'base_controller_review_reference':d['base_controller_review_reference'],'storage_review_reference':d['storage_review_reference'],
        'scientific_bodies_opened_or_hashed':False,'sbatch_or_observe_called':False,'policy_or_pool_release':False,
        'next_API':'existing controller.prepare -> submit_held -> observe; Root only'})


def main():
    Q.login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('relocation');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('source-template');a.add_argument('--source-manifest',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True);a=p.parse_args()
    if a.action=='relocation':v=relocation(a.request,a.output)
    elif a.action=='source-template':v=source_template(a.source_manifest,a.output)
    elif a.action=='draft':v=draft(a.request,a.output)
    else:v=finalize(a.draft,a.root_review)
    print(v)


if __name__=='__main__':main()
