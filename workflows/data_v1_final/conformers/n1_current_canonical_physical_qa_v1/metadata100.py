"""Root metadata over the existing gate/ready/proof flow; no submission or DATA read."""
import argparse,copy,json,pathlib
import main100_runtime as A
from portable_n1_source_remaining_v1 import metadata as OLD,contract as C

ROOT=A.ROOT
IMPORT_CONTROL=ROOT/'control/n1_foreign_return_import_20261030_v1/cpu2_import_original4407_v1'
IMPORT_ACCOUNT=ROOT/'control/n1_foreign_return_import_20261030_v1/actual_4525249_C0.json'
PROOF100=A.private(OLD.startup_proof,C=A.CONTRACT100)


def unique(rows):
    result={}
    for item in rows:
        ref=C.triple(item)
        C.need(ref['path'] not in result or result[ref['path']]==ref,'EXACT_REFERENCE_PER_PATH')
        result[ref['path']]=ref
    return list(result.values())


def prepare(base_path,control,future_key):
    # Root supplies the current scientific input closure. No import/result/
    # assignments/prepared/Parquet DATA body is opened or hashed on login.
    p=copy.deepcopy(C.load_path(base_path));control=C.literal(control)
    C.need(ROOT/'control' in control.parents and not control.exists(),'NEW_METADATA_CONTROL_NO_OVERWRITE')
    control.mkdir(parents=True,mode=0o700)
    name=p['job_name'];plan_path=ROOT/'control/requests'/(name+'.plan.json')
    proof_path=ROOT/'control/queue_startup'/(name+'.json')
    p.update(node='compute-0-18',cpus=16,wall_seconds=14400,stop_dispatch_before_wall_seconds=900,
        output_cap_bytes=A.CAP,resource_binding=A.RESOURCE_BINDING,account_quota_floor_bytes=A.FLOOR,
        current_all_future_ledger_path=str(A.FUTURE),future_ledger_entry_key=future_key,
        quota_provider_review_reference=C.ref(A.PROVIDER,2<<20),quota_provider_identity_reference=C.ref(A.IDENTITY,2<<20),
        control_directory=str(control),startup_proof_path=str(proof_path),script_path=str(control/'parent.sbatch'),
        workdir=str(ROOT/'repository'),python_executable='/share/home/zixiao/.conda/envs/chemprop/bin/python',
        identity_scope=A.CURRENT.SCOPED.SCOPE,
        import_plan_reference=C.ref(IMPORT_CONTROL/'plan.json',2<<20),
        import_startup_proof_reference=C.ref(IMPORT_CONTROL/'proof.json',2<<20),
        import_accounting_reference=C.ref(IMPORT_ACCOUNT,2<<20),root_review_reference=None)
    C.need(p['role']=='physical_qa' and p['endpoint']['id']=='main' and p['endpoint']['uid']==1278,'MAIN_PHYSICAL_QA_PLAN')
    # The actual Root-bound small plan already carries producer-derived refs.
    # Preserve them verbatim; do not hash/open prepared, catalog or assignments.
    for key,path,size in (
        ('source_prepared_reference',ROOT/'artifacts/conformers/n1_pprime2_source_full_v1/prepared_v1/prepared.json',14188),
        ('catalog_reference',ROOT/'repository/workflows/data_v1_final/conformers/n1_pprime2_source_full_v1/frozen_sources.json',16294)):
        C.need(p.get(key) is not None,'ACTUAL_ROOT_BOUND_INPUT_REQUIRED:'+key)
        ref=C.triple(p[key]);C.need(ref['path']==str(path) and ref['bytes']==size,'EXACT_ORIGINAL_POSITIVE_LOCATOR:'+key)
    for key in ('source_return_reference','physical_identity_authority_reference'):
        C.need(p.get(key) is not None,'ROOT_MUST_BIND_ACTUAL_CURRENT_SCOPE_REFERENCE:'+key);C.triple(p[key])
    p['pythonpath']=':'.join([str(A.HERE),str(A.SCOPED_SOURCE),str(ROOT/'repository/workflows/data_v1_final/conformers'),
        str(ROOT/'repository'),'/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'])
    p['execution_argv']=[p['python_executable'],'-B',str(A.HERE/'main100_runtime.py'),
        '--plan',str(plan_path),'--startup-proof',str(proof_path)]
    policy=C.load_path(A.FLOOR_POINTER);p['quota_floor_policy_reference']=policy['policy_reference']
    # Preserve reviewed source/DATA classification. Explicit source collectors
    # only hash Python/README and the named pure controls, never scientific DATA.
    provider=C.load(p['quota_provider_review_reference'])
    sources=[*p['source_references'],*A.source_references(),
        p['import_plan_reference'],p['import_startup_proof_reference'],p['import_accounting_reference'],
        p['physical_identity_authority_reference'],p['quota_floor_policy_reference'],
        p['quota_provider_review_reference'],p['quota_provider_identity_reference'],
        *provider['provider_source_references'],*provider['evidence_references'],provider['marker_reference']]
    if provider.get('count_correction_authority_reference'):sources.append(provider['count_correction_authority_reference'])
    p['source_references']=unique(sources)
    p['data_references']=unique([*p['data_references'],p['source_return_reference'],p['source_prepared_reference'],p['catalog_reference']])
    p['total_future_reserved_bytes']=A.live_future(p)
    A.resource_plan(p)
    C.need(not plan_path.exists() and not proof_path.exists(),'NO_OLD_CANONICAL_PLAN_OR_PROOF_OVERWRITE')
    ref=C.save(plan_path,p)
    review=OLD.review_template(plan_path,control/'root_review.template.json')
    return dict(status='ROOT_METADATA_PREPARED_NOT_ADMITTED_OR_SUBMITTED',plan_reference=ref,root_review_template_reference=review,
        next='Root signs original ROOT_DISJOINT_REMAINING_REVIEW_V4 and binds its positive ref into this fresh plan, then script action',
        existing_gate_module='portable_n1_source_remaining_v1.gate',current_live_future_bytes=p['total_future_reserved_bytes'],
        output_cap_bytes=A.CAP,account_floor_bytes=A.FLOOR,free_credit_bytes=0)


def startup(plan_path,ready_path,observations_path,out):
    p=C.load_path(plan_path);A.resource_plan(p)
    observed=C.load_path(observations_path);ready=C.load_path(ready_path)
    C.need(observed['account_free_bytes']-A.live_future(p,ready)>=A.FLOOR,'ACTUAL_ROOT_OBSERVATION_MINUS_LIVE_V2_FUTURE_PLUS100GB')
    # The intermediate proof never occupies the gate's real admission path.
    draft=pathlib.Path(p['control_directory'])/'proof.not_released.json'
    PROOF100(plan_path,ready_path,observations_path,draft)
    proof=C.load_path(draft);name=p['job_name']
    request_path=ROOT/'control/requests'/(name+'.json')
    C.need(pathlib.Path(out)==pathlib.Path(p['startup_proof_path'])
        and pathlib.Path(plan_path)==ROOT/'control/requests'/(name+'.plan.json'),'CANONICAL_CURRENT_REQUEST_PLAN_PROOF')
    proof['request_reference']=C.save(request_path,proof['request'])
    return C.save(out,proof)


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='action',required=True)
    q=commands.add_parser('prepare')
    for name in ('base-plan','control','future-key'):q.add_argument('--'+name,required=True)
    q=commands.add_parser('script');q.add_argument('--plan',required=True);q.add_argument('--output',required=True)
    q=commands.add_parser('startup-proof')
    for name in ('plan','ready','observations','output'):q.add_argument('--'+name,required=True)
    a=parser.parse_args()
    value=(prepare(a.base_plan,a.control,a.future_key) if a.action=='prepare'
        else startup(a.plan,a.ready,a.observations,a.output) if a.action=='startup-proof'
        else OLD.script(a.plan,a.output))
    print(json.dumps(value,ensure_ascii=False))

if __name__=='__main__':main()