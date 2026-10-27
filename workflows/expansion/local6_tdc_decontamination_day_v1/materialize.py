"""Original generic-scope metadata API; actual C0 then separate READY adoption."""
import argparse,copy
from pathlib import Path
from workflows.expansion.marcel_kraken_decontamination_main_v1.materialize import approved
from . import contract as C
Q=C.Q

def fresh(path,kind):
    p=Path(path);C.need(p.is_absolute() and C.ROOT/kind in p.parents and '..' not in p.parts and not p.exists()
        and not any(v.is_symlink() for v in (p,*p.parents)),'FRESH_OWN_'+kind.upper());return p

def draft(path,out):
    from . import io as original_IO_context,projection as original_projection_context,local as local_context,tdc as tdc_context,supplement as supplementary_context
    r=Q.load(path);C.need(r['schema']=='ROOT_REQUESTED_LOCAL6_TDC_DECONTAMINATION_DAY_V1' and r['status']=='REQUESTED_FOR_REVIEW'
        and r['requested_by']=='root','ACTUAL_ROOT_REQUEST_NOT_AUTHORED_APPROVAL')
    authority,data,parents=C.derive(r)
    keys=('local_receipt_reference','tdc_receipt_reference','tdc2_policy_reference','local_accounting_reference','tdc_accounting_reference',
        'resource_authority_reference','cost_decision_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference',
        'native_git_assets_manifest_reference','native_git_wrapper_reference','physical_manifest_reference','physical_accounting_reference')
    plan={k:r[k] for k in keys};resources=[r[k] for k in keys[5:10]]
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(r['resource_authority_reference'],read_small=Q.read_small)
    C.Day.carveout(C.meta(r['root_carveout_review_reference']),{'scope_key':C.KEY,'node':'compute-0-14',
        'resource_authority_reference':r['resource_authority_reference'],'estimated_peak_output_bytes':C.CAP})
    sources=C.unique([*(Q.pin(p) for p in C.sources()),*parents,*resources,Q.pin(path)],source=True)
    C.need(not {v['path'] for v in sources}&{v['path'] for v in data},'SOURCE_METADATA_AND406_DATA_DISJOINT')
    plan.update(schema='LOCAL6_TDC_DECONTAMINATION_DAY_PLAN_V1',scope_parameters=C.PARAMETERS,authority=authority,data_references=data,
        source_references=sources,wall_seconds=C.WALL,output_cap_bytes=C.CAP,output_directory=str(fresh(r['output_directory'],'artifacts')))
    out=fresh(out,'control');out.mkdir(parents=True,mode=0o700);pr=Q.write_new(out/'plan.json',plan);sources=C.unique([*sources,pr],source=True)
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':C.WALL,
        'estimated_peak_output_bytes':C.CAP,'source_status_stage':'CLOSED_LOCAL6_TDC_ALL_SOURCE_STRICT_IDENTITY_EXPORT',
        'execution_argv':[C.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**copy.deepcopy(fields),
        'scope_mode':'BOUNDED_METADATA_PREPARATION','resource_authority_reference':r['resource_authority_reference'],'stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':data,
        'closed_local6_all44_and_exact2_conservative_identity_only_authorized':True,'original_SOURCE_roles_are_not_wholeMID_training_roles':True,
        'original_repository_checker_and_six_software_DATA_authorized':True,
        'exact_407_closed_physical_C0_embedded_triples_discovered_on_CPU_only_authorized':True,
        'global_pool_release_authorized':False}
    tr=Q.write_new(out/'root_review.template.json',template)
    return Q.write_new(out/'draft_receipt.json',{'schema':'LOCAL6_TDC_EXPORT_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'template_reference':tr,'stage_fields':fields,'source_references':sources,'data_references':data,
        'resource_authority_reference':r['resource_authority_reference'],'scientific_DATA_opened_or_hashed':False})

def finalize(path,review_path):
    d=Q.load(path);C.need(d['schema']=='LOCAL6_TDC_EXPORT_DRAFT_V1','EXACT_THIS_METADATA_DRAFT');rr=approved(d['template_reference'],review_path)
    plan=C.meta(d['plan_reference']);a,data,_=C.derive(plan);C.need(a==plan['authority'] and data==d['data_references'],'SAME_CLOSED_PRODUCER_LOCATORS')
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'CURRENT_SOURCE_AND_SMALL_PARENT_BYTES')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':C.CAP,'source_references':d['source_references'],'data_references':data,
        'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(path).parent/'stage_spec.json',spec)

def actual(receipt_path,accounting_path):
    ref=Q.pin(receipt_path);b=C.meta(ref);ar=Q.pin(accounting_path);raw=C.account(ar,b['job_id'],'compute-0-14')
    C.need(b['schema']=='LOCAL6_TDC_DECONTAMINATION_DAY_RECEIPT_V1' and b['status']=='PRIMARY7_STRICT_IDENTITIES_COMPLETE_PENDING_ROOT_ADOPTION'
        and b['uid']==1278 and b['node']=='compute-0-14' and b['new_graph_RDKit_fullkey_UFF_QM_calls']==0
        and b['READY_or_global_manifest_modified'] is False and b['pool_or_training_release'] is False,'ACTUAL_COMPLETE_SEVEN_CANDIDATES_NOT_SELF_READY')
    plan=C.meta(b['plan_reference']);proof=C.meta(b['startup_proof_reference']);req=proof['request'];gate=C.meta(b['source3_reference'])
    C.need(str(proof['job_id'])==str(b['job_id']) and proof['uid']==1278 and req['scope_key']==C.KEY and req['scope_parameters']==C.PARAMETERS
        and req['node']=='compute-0-14' and req['cpus']==16 and req['wall_seconds']==C.WALL and req['data_references']==plan['data_references']
        and req['kind']=='analysis' and req['pilot'] is False and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and proof['execution_admission_granted'] is True and req['execution_argv']==[C.PY,'-B','-m',C.MODULE,'--plan',b['plan_reference']['path'],'--startup-proof',b['startup_proof_reference']['path']]
        and req['stage_output_cap_bytes']==req['estimated_peak_output_bytes']==C.CAP and b['plan_reference'] in req['source_references']
        and gate['tests_run']==3 and gate['before_DATA_and_resource_monitor'] is True
        and all(gate[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'TRUE_PARENT_SCOPE_SOURCE3_AND_PROOF')
    C.derive(plan);sources=b['primary7_candidates'];C.need(len(sources)==7 and {s['dataset'] for s in sources}==set(C.PRIMARY)|{'tdc_admet'}
        and sum(s['identities']['rows'] for s in sources)==11469344,'ACTUAL_PRIMARY7_COUNTS_NOT_MOLNET_FULL')
    check=C.meta(b['repository_check_actual_reference']);physical=C.meta(b['physical_D1_review_reference'])
    C.need(check['status']=='PASS' and check['returncode']==0 and check['scientific_DATA_read'] is False
        and physical['schema']=='LOCAL7_PARENT_RETAINED_PHYSICAL_D1_FACTS_V1' and physical['native_records']==384
        and physical['gradient_calls']==100 and physical['all407_embedded_refs_whole_SHA_sameFD_verified'] is True
        and physical['Root_physical_PASS_2000_full_or_D1_signed'] is False,'SOURCE_CHECK_AND_READONLY_PHYSICAL_FACTS_NOT_SCIENTIFIC_SIGNOFF')
    for s in sources:
        coverage=C.meta(s['coverage_evidence']);C.need(s['status']=='PENDING_ROOT_ACTUAL_C0_ADOPTION' and coverage['dataset']==s['dataset']
            and coverage['all_splits'] is True and coverage['unresolved_without_identity_or_composition']==0
            and coverage['identities']==s['identities'] and coverage['expected_identity_records']==s['identities']['rows']
            and coverage['readback']['rows']==s['identities']['rows'] and coverage['readback']['all_rows_reparsed_with_original_identity_keys'] is True,
            'ALL_SEVEN_ORIGINAL_CONSUMER_COVERAGES')
    return b,C.unique([ref,ar,raw,b['plan_reference'],b['startup_proof_reference'],b['source3_reference'],b['resource_reference'],
        b['repository_check_actual_reference'],b['physical_D1_review_reference'],req['scope']['review']],source=True)

def acceptance_draft(receipt,accounting,out):
    b,parents=actual(receipt,accounting);out=fresh(out,'control');out.mkdir(parents=True,mode=0o700)
    template={'schema':'ROOT_LOCAL6_TDC_STRICT7_ACCEPTANCE_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'actual_receipt_reference':Q.pin(receipt),'actual_accounting_reference':Q.pin(accounting),'parent_evidence_references':parents,
        'all_primary7_counts_raw_lineage_and_original_roles_reviewed':True,'two_TDC_graph_UNKNOWN_preserved_composition_only_reviewed':True,
        'dataset_READY_candidates_authorized_after_actual_C0':True,'global_pool_release_authorized':False}
    tr=Q.write_new(out/'acceptance.template.json',template)
    return Q.write_new(out/'acceptance_draft.json',{'schema':'LOCAL6_TDC_STRICT7_ACCEPTANCE_DRAFT_V1','template_reference':tr,
        'actual_receipt_reference':Q.pin(receipt),'actual_accounting_reference':Q.pin(accounting)})

def acceptance_finalize(path,review):
    d=Q.load(path);C.need(d['schema']=='LOCAL6_TDC_STRICT7_ACCEPTANCE_DRAFT_V1','EXACT_ACTUAL_ACCEPTANCE_DRAFT');rr=approved(d['template_reference'],review)
    b,_=actual(d['actual_receipt_reference']['path'],d['actual_accounting_reference']['path'])
    C.need(Q.pin(d['actual_receipt_reference']['path'])==d['actual_receipt_reference'] and Q.pin(d['actual_accounting_reference']['path'])==d['actual_accounting_reference'],'SAME_ACTUAL_C0_NOT_FUTURE_PIN')
    sources=[{**s,'status':'READY','actual_CPU_receipt_reference':d['actual_receipt_reference'],'actual_CPU_accounting_reference':d['actual_accounting_reference'],
        'independent_Root_acceptance_reference':rr,'global_pool_release':False} for s in b['primary7_candidates']]
    return Q.write_new(Path(path).parent/'primary7_READY_source_candidates.json',{'schema':'LOCAL6_TDC_SEPARATELY_ACCEPTED_READY_CANDIDATES_V1',
        'sources':sources,'existing_global_manifest_modified':False,'Molnet17_or_pool_release':False})

def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    a=s.add_parser('acceptance-draft');a.add_argument('--receipt',type=Path,required=True);a.add_argument('--accounting',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('acceptance-finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    a=p.parse_args()
    print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review) if a.action=='finalize' else
        acceptance_draft(a.receipt,a.accounting,a.output) if a.action=='acceptance-draft' else acceptance_finalize(a.draft,a.root_review))
if __name__=='__main__':main()
