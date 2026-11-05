"""Small terminal-parent metadata and existing generic16CPU submission protocol."""
import argparse,copy,types
from pathlib import Path
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v3 import metadata as OLD
P=C.P

def source_paths():return list(dict.fromkeys([*OLD.source_paths(),*(C.HERE/n for n in C.FILES)]))

def draft(request_path,out):
    OLD.FAST.login();r=C.meta(P.pin(request_path))
    C.need(r['schema']=='ROOT_REQUESTED_FAST55K_C0_PARTIAL_CACHE_RESUME_V1'and r['requested_by']=='root','ROOT_CLOSED_PHASE_REQUEST')
    seed={'resume_origin_review_reference':r['resume_origin_review_reference'],'closed_phase_review_reference':r['closed_phase_review_reference']}
    _,old,_=C.resume_authority(seed);phase,_,_,receipt=C.phase_authority(seed);p=copy.deepcopy(old)
    p.update(schema='EXISTING_SPRIME_FAST55K_RESUME_PLAN_V1',status='ROOT_REVIEW_REQUIRED',reviewer=None,
      resume_origin_review_reference=r['resume_origin_review_reference'],closed_phase_review_reference=r['closed_phase_review_reference'],
      node=r['node'],output_directory=r['output_directory'],whole_output_cap_bytes=r['whole_output_cap_bytes'],statistics_cap_bytes=r['whole_output_cap_bytes'],
      quota_provider_review_reference=r['quota_provider_review_reference'],quota_provider_identity_reference=r['quota_provider_identity_reference'],
      root_carveout_review_reference=r['root_carveout_review_reference'],cache_transitive_output_origins=[],accepted_prior_output_roots=[])
    provider=C.meta(p['quota_provider_review_reference']);carve=C.meta(p['root_carveout_review_reference'])
    source=[*old['source_references'],P.pin(request_path),r['resume_origin_review_reference'],r['closed_phase_review_reference'],
      p['quota_provider_review_reference'],p['quota_provider_identity_reference'],p['root_carveout_review_reference'],
      *(P.pin(x)for x in source_paths()),*r.get('source_references',[])]
    for key in ('provider_source_references','evidence_references'):source.extend(provider.get(key,[]))
    source.extend(carve.get('accounting_basis_references',[]))
    for key in ('marker_reference','probe_reference','count_correction_authority_reference'):
        if provider.get(key)is not None:source.append(provider[key])
    registration=C.meta(p['resume_origin_review_reference'])['parent_registration'];source.extend(registration.values());source.extend(phase['parent_registration'].values())
    p['actual_parent_evidence_references']=C.unique([*old['actual_parent_evidence_references'],*registration.values(),*phase['parent_registration'].values()])
    p['source_references']=C.unique(source);p['data_references']=C.unique([*old['data_references'],receipt['coverage_reference'],*r.get('data_references',[])])
    p['scope_parameters']=C.scope(p);out=Path(out);out.mkdir(parents=True,exist_ok=True);return P.write(out/'plan_candidate.json',p)

def stage(plan_path,out,scope_review=None):
    f=OLD.NATIVE.stage;g=dict(f.__globals__,C=C)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(plan_path,out,scope_review)

def close(registration_path,out):
    f=OLD.close;g=dict(f.__globals__,C=C)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(registration_path,out)

def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('stage');a.add_argument('--plan',required=True);a.add_argument('--output',required=True);a.add_argument('--scope-review')
    a=s.add_parser('close');a.add_argument('--registration',required=True);a.add_argument('--output',required=True)
    a=p.parse_args();print(draft(a.request,a.output)if a.action=='draft'else stage(a.plan,a.output,a.scope_review)if a.action=='stage'else close(a.registration,a.output))
if __name__=='__main__':main()
