"""Small actual terminal metadata only; all old SQLite/parts SHA are CPU-deferred."""
import argparse,copy,types
from pathlib import Path
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import metadata as FAST
from workflows.data_v1_final.labels.existing_sprime_native_pilot_resume_v2 import metadata as NATIVE
P=C.P
def source_paths():
    return list(dict.fromkeys([*FAST.source_paths(),*(C.HERE/n for n in C.FILES),
      C.REPO/'workflows/data_v1_final/execution/finite_quota_observation_guard_v2.py']))
def draft(request_path,out):
    FAST.login();r=C.meta(P.pin(request_path))
    C.need(r['schema']=='ROOT_REQUESTED_FAST55K_C0_PARTIAL_CACHE_RESUME_V1' and r['requested_by']=='root','ROOT_RESUME_REQUEST')
    seed={'resume_origin_review_reference':r['resume_origin_review_reference']};_,old,_=C.resume_authority(seed);p=copy.deepcopy(old)
    p.update(schema='EXISTING_SPRIME_FAST55K_RESUME_PLAN_V1',status='ROOT_REVIEW_REQUIRED',reviewer=None,
      resume_origin_review_reference=r['resume_origin_review_reference'],node=r['node'],output_directory=r['output_directory'],
      whole_output_cap_bytes=r['whole_output_cap_bytes'],statistics_cap_bytes=r['whole_output_cap_bytes'],
      quota_provider_review_reference=r['quota_provider_review_reference'],quota_provider_identity_reference=r['quota_provider_identity_reference'],
      root_carveout_review_reference=r['root_carveout_review_reference'],cache_transitive_output_origins=[],accepted_prior_output_roots=[])
    provider=C.meta(p['quota_provider_review_reference']);carve=C.meta(p['root_carveout_review_reference'])
    source=[*old['source_references'],P.pin(request_path),r['resume_origin_review_reference'],
      p['quota_provider_review_reference'],p['quota_provider_identity_reference'],p['root_carveout_review_reference'],
      *(P.pin(x)for x in source_paths()),*r.get('source_references',[])]
    for key in ('provider_source_references','evidence_references'):source.extend(provider.get(key,[]))
    source.extend(carve.get('accounting_basis_references',[]))
    for key in ('marker_reference','probe_reference','count_correction_authority_reference'):
        if provider.get(key) is not None:source.append(provider[key])
    registration=C.meta(p['resume_origin_review_reference'])['parent_registration'];source.extend(registration.values())
    p['actual_parent_evidence_references']=C.unique([*old['actual_parent_evidence_references'],*registration.values()])
    p['source_references']=C.unique(source);p['data_references']=C.unique([*old['data_references'],*r.get('data_references',[])])
    p['scope_parameters']=C.scope(p);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    return P.write(out/'plan_candidate.json',p)
def stage(plan_path,out,scope_review=None):
    # The existing generic16/no_mem metadata stage protocol; no new controller.
    old=NATIVE.stage;namespace=dict(old.__globals__,C=C)
    f=types.FunctionType(old.__code__,namespace,old.__name__,old.__defaults__,old.__closure__);f.__kwdefaults__=old.__kwdefaults__
    return f(plan_path,out,scope_review)
def close(registration_path,out):
    FAST.login();r=C.meta(P.pin(registration_path));account=C.meta(r['accounting_reference']);receipt=C.meta(r['receipt_reference'])
    request=C.meta(r['request_reference']);sub=C.meta(r['submission_reference']);proof=C.meta(r['proof_reference']);jid=str(sub['job_id'])
    C.need(request==sub['request']==proof['request'] and request['scope_key']==C.KEY and str(proof['job_id'])==str(receipt['job_id'])==jid
      and account['query_returncode']==0 and account['raw_sacct_reference']==r['raw_reference'],'ACTUAL_NEW_PARENT_CHAIN')
    raw,pin=P.small(r['raw_reference']['path']);C.need(pin==r['raw_reference'],'REAL_ACTUAL_RAW_ACCOUNT')
    import csv,io
    rows=[x for x in csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter='|')if x['JobIDRaw']==jid]
    C.need(len(rows)==1 and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0'
      and rows[0]['UID']=='1278' and int(rows[0]['AllocCPUS'])==16 and receipt['held']is False and receipt['errors']==[],'REAL_C0_NOT_FUTURE_STATUS')
    complete=receipt['status']=='PROVISIONAL55K_FAST_TYPED_NATIVE_RANDOM_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL'
    C.need(complete or receipt['status']=='DAY_DURABLE_PARTIAL_PENDING_EXPLICIT_ROOT_CONTINUATION','ORIGINAL_FINITE_PHASE_STATUS')
    C.need(not complete or receipt['independent_numeric_replay_equal']is True and len(receipt['numeric_repetitions'])==2
      and receipt['r674_report_reference']is not None,'REAL_TWO_INDEPENDENT_TRAIN_REPLAYS_AND_D4_REPORT')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    return P.write(out/'root_limited_acceptance_candidate.json',{'schema':'ROOT_FAST55K_RESUME_LIMITED_COMPONENT_ACCEPTANCE_V1',
      'status':'ROOT_REVIEW_REQUIRED','reviewer':None,'registration_reference':P.pin(registration_path),'complete_55k_components':complete,
      'actual_parent':{'manifest':r['receipt_reference'],'proof':r['proof_reference'],'accounting':r['accounting_reference'],'raw':r['raw_reference']},
      'component_references':{k:receipt[k]for k in ('prefix_reference','coverage_reference','geometry_reference','population_reference','eligibility_reference',
       'typed_reader_config_reference','numeric_repetitions','r674_report_reference','schema_only_header_reference')},
      'old4525232_C0_partial_history_unchanged':True,'full_Common_D2_D3_D4_D5_D6_release':False,'future_D3_explicit_consumer_required':True})
def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('stage');a.add_argument('--plan',required=True);a.add_argument('--output',required=True);a.add_argument('--scope-review')
    a=s.add_parser('close');a.add_argument('--registration',required=True);a.add_argument('--output',required=True)
    a=p.parse_args();print(draft(a.request,a.output)if a.action=='draft'else stage(a.plan,a.output,a.scope_review)if a.action=='stage'else close(a.registration,a.output))
if __name__=='__main__':main()
