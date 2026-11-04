"""Root-only prior224 plan helpers; only pure controls are read/hashed here."""
import argparse,copy,json,pathlib,sys
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
SCOPED=ROOT/'repository/workflows/data_v1_final/conformers/n1_current_canonical_physical_qa_v1'
sys.path.insert(0,str(SCOPED))
import main100_runtime as R,metadata100 as M,scoped_identity as ID
from portable_n1_source_remaining_v1 import contract as C,metadata as OLD
HERE=pathlib.Path(__file__).absolute().parent
JOBS={'4521418','4521476','4521479','4521481'}


def authority_template(base_path,out):
    value=copy.deepcopy(C.load_path(base_path));registry_ref=C.ref(ID.CURRENT_REGISTRY,2<<20);registry=C.load(registry_ref)
    C.need(registry['schema']=='N1_CURRENT_CANONICAL_EXTRA_REGISTRY_V1' and registry['status']=='CLOSED_CURRENT_CANONICAL_SCOPE'
        and registry['identity_scope']==ID.SCOPE and registry['current_registered_extra_count']>=4400,
        'LATEST_NONEMPTY_CURRENT_REGISTRY_NOT_OLD_EMPTY_BASE')
    members=registry['members'];C.need(any(str(m['actual_parent_job_id'])=='4525894' and m['accepted_extra_count']==4400 for m in members),
        'ACTUAL_4400_PHYSICAL_QA_REGISTRATION_RETAINED')
    value.update(status='PENDING_ROOT_CURRENT_CANONICAL_SCOPE_REVIEW',reviewer=None,current_registry_reference=registry_ref,
        current_registered_extra_table_bindings=members,
        registered_extra_identity_tables=[C.triple(m['registered_identity_table_reference']) for m in members])
    source=C.load_path(HERE/'inputs.candidate.json')
    previous={str(p['job_id']):p for p in value['closed_source_parents']}
    for job in JOBS:previous[job]=dict(job_id=job,accounting_reference=source['actual_accounting_reference'],requires_C0=True)
    value['closed_source_parents']=list(previous.values())
    value['coverage_evidence_references']=M.unique([*[r for r in value['coverage_evidence_references'] if r['path']!=registry_ref['path']],registry_ref,source['actual_accounting_reference']])
    value['new_reader_scope']='FOUR_PRIOR_MAIN_ORIGINS_NOT_AN_ALPHA_IMPORT_OR_GLOBAL_HISTORY_RELEASE'
    return C.save(out,value)


def prepare(base_path,authority_path,control,future_key):
    plan=copy.deepcopy(C.load_path(base_path));authority_ref=C.ref(authority_path,2<<20);authority=C.load(authority_ref)
    C.need(authority['status']=='APPROVED_CURRENT_CANONICAL_SCOPE' and authority['reviewer']=='root'
        and authority['identity_scope']==ID.SCOPE and authority['current_registry_reference']==C.ref(ID.CURRENT_REGISTRY,2<<20)
        and authority['current_registered_extra_table_bindings'],'ACTUAL_ROOT_LATEST_NONEMPTY_ID_AUTHORITY')
    control=C.literal(control);C.need(ROOT/'control' in control.parents and not control.exists(),'NEW_PRIOR224_CONTROL_DIRECTORY')
    control.mkdir(parents=True,mode=0o700)
    name='dv1_q_n1_prior224_current_canonical_20261105_v1'
    plan_path=ROOT/'control/requests'/(name+'.plan.json');proof_path=ROOT/'control/queue_startup'/(name+'.json')
    out=ID.OUTPUT/'prior224_current_v1'
    old_authority_path=plan['physical_identity_authority_reference']['path']
    plan.update(schema='N1_PRIOR_MAIN224_CURRENT_PHYSICAL_QA_PLAN_V1',job_name=name,role='physical_qa',
        node='compute-0-18',cpus=16,wall_seconds=14400,stop_dispatch_before_wall_seconds=900,output_cap_bytes=R.CAP,
        output_directory=str(out),control_directory=str(control),script_path=str(control/'parent.sbatch'),
        startup_proof_path=str(proof_path),root_review_reference=None,identity_scope=ID.SCOPE,
        physical_identity_authority_reference=authority_ref,prior_Main224_inputs_reference=C.ref(HERE/'inputs.candidate.json',2<<20),
        future_ledger_entry_key=future_key,resource_binding=R.RESOURCE_BINDING,account_quota_floor_bytes=R.FLOOR,
        current_all_future_ledger_path=str(R.FUTURE),quota_provider_review_reference=C.ref(R.PROVIDER,2<<20),
        quota_provider_identity_reference=C.ref(R.IDENTITY,2<<20))
    plan['pythonpath']=':'.join([str(HERE),str(SCOPED),str(ROOT/'repository/workflows/data_v1_final/conformers'),
        str(ROOT/'repository'),'/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'])
    plan['execution_argv']=[plan['python_executable'],'-B',str(HERE/'run_prior224.py'),'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    own=[C.ref(HERE/n,2<<20) for n in ('run_prior224.py','prior224_worker.py','metadata.py','README.md','inputs.candidate.json')]
    changed={r['path'] for r in [*R.source_references(),*own,authority['current_registry_reference'],authority_ref]}
    changed.add(old_authority_path)
    source=[r for r in plan['source_references'] if r['path'] not in changed]
    source.extend([*R.source_references(),*own,authority_ref,authority['current_registry_reference']])
    header=C.load(plan['prior_Main224_inputs_reference']);data=[]
    for entry in header['history']['registered_generation_roots']:
        source.extend(entry[k] for k in ('request_reference','submission_reference','startup_proof_reference'))
        request=C.load(entry['request_reference']);data.extend(request['data_references'])
        if entry['producer_receipt_reference'] is not None:data.append(entry['producer_receipt_reference'])
    source.extend([header['actual32_review_reference'],header['actual_accounting_reference'],header['actual_raw_sacct_reference']])
    data.extend([*authority['ordinary_physical_map_tables'],*authority['historical_attempted_physical_id_tables'],
        *authority['registered_extra_identity_tables'],*(m['accepted_extra_index_reference'] for m in authority['current_registered_extra_table_bindings']),
        plan['source_prepared_reference'],plan['catalog_reference']])
    plan['source_references']=M.unique(source);plan['data_references']=M.unique(data)
    plan['total_future_reserved_bytes']=R.live_future(plan);R.resource_plan(plan)
    C.need(not plan_path.exists() and not proof_path.exists() and not out.exists(),'NO_OLD_PLAN_PROOF_OR_OUTPUT_OVERWRITE')
    reference=C.save(plan_path,plan);review=OLD.review_template(plan_path,control/'root_review.template.json')
    return dict(status='SOURCE_METADATA_PREPARED_NOT_SUBMITTED',plan_reference=reference,root_review_template_reference=review,
        output_directory=str(out),prior_tasks=224,old_parent_ids=sorted(JOBS),new_UFF_QM_calls=0,
        next='Root signs original plan review; use existing metadata100 script/startup-proof and samePID gate')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('authority-template');p.add_argument('--base-authority',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('prepare')
    for name in ('base-plan','physical-authority','control','future-key'):p.add_argument('--'+name,required=True)
    a=parser.parse_args()
    result=(authority_template(a.base_authority,a.output) if a.action=='authority-template'
        else prepare(a.base_plan,a.physical_authority,a.control,a.future_key))
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()