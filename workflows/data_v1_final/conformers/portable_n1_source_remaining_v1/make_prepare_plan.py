"""Root small metadata constructor over actual resources/base PYTHONPATH; no SCI."""
import argparse,json,pathlib,sys
from . import contract as C,metadata as M


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('resources','base-freeze-plan','legacy-disabled','control-directory','output-directory'):p.add_argument('--'+name,type=pathlib.Path,required=True)
    p.add_argument('--wall-seconds',type=int,default=3600);p.add_argument('--root-reason',required=True)
    p.add_argument('--root-approve-zero-UFF-export-and-foreign-assignment',action='store_true');a=p.parse_args()
    C.need(a.root_approve_zero_UFF_export_and_foreign_assignment and a.root_reason.strip(),'EXPLICIT_ROOT_METADATA_EXPORT_SCOPE')
    resources_ref=C.ref(a.resources,2<<20);resources=C.load(resources_ref);base_ref=C.ref(a.base_freeze_plan,2<<20);base=C.load(base_ref)
    C.need(resources['cpus']==16 and resources['node'] in ('compute-0-'+str(n) for n in (2,*range(8,20)))
        and 1800<=a.wall_seconds<=14400 and a.wall_seconds==resources['wall_seconds']
        and resources['output_cap_bytes']==16<<30,'REAL16_CPU_BOUNDED_IO_EXPORT_NOT_SCI_DAY')
    legacy_ref=C.ref(a.legacy_disabled,2<<20);legacy=C.load(legacy_ref)
    C.need(legacy['reviewer']=='root' and legacy['all_N1_generation_parents_terminal']is True and legacy['legacy_N1_generation_disabled']is True
        and legacy['all_existing_claims_preserved_no_retry']is True,'ROOT_ACTUAL_LEGACY_DISABLE_AUTHORITY')
    latest=C.load_path(C.MAIN/'control/root_current_all_future_ledger_v1.json');future_ref=latest['review_reference'];future=C.load(future_ref)
    C.need(future['reviewer']=='root' and future['status']=='APPROVED' and future['total_future_reserved_bytes']==latest['total_future_reserved_bytes']
        and future['total_future_reserved_bytes']>=16<<30,'IMMUTABLE_LATEST_ALL_FUTURE_REVIEW_INCLUDES_EXPORT')
    directory=C.MAIN/'artifacts/conformers/n1_pprime2_source_full_v1/prepared_v1'
    prepared_ref=C.ref(directory/'prepared.json',2<<20);prepared=C.load(prepared_ref)
    pilot_ref=prepared['science_cost_review_reference'];pilot=C.load(pilot_ref)
    account_ref=C.ref(C.MAIN/'control/n1_source_full_prepare_actual_accounting_v1.json',2<<20);account=C.load(account_ref)
    provider_ref=resources['quota_provider_review_reference'];identity_ref=resources['quota_provider_identity_reference']
    C.load(provider_ref);C.load(identity_ref)
    data=[*base.get('data_references',[]),prepared['source_task_roster']]
    sources=[*base['source_references'],base_ref,resources_ref,legacy_ref,future_ref,prepared_ref,pilot_ref,account_ref,account['raw_sacct_reference'],provider_ref,identity_ref]
    here=pathlib.Path(__file__).absolute().parent;sources.extend(C.ref(x,2<<20) for x in sorted(here.glob('*.py')))
    repo=C.MAIN/'repository';old=repo/'workflows/data_v1_final/conformers/n1_pprime2_source_full_v1'
    sources.extend(C.ref(old/name,2<<20) for name in ('__init__.py','core.py','contract.py'))
    sources.extend([prepared['source_population_authority'],prepared['catalog']])
    # Top DATA locators are inherited from the closed old authority, not hashed
    # or opened by this metadata constructor. Task/base/LMDB descendants are
    # independently verified in the allocated CPU exporter.
    authority=C.load(prepared['source_population_authority']);data.extend(authority['source_inputs'])
    def unique(rows):
        found={}
        for row in rows:
            r=C.triple(row);C.need(r['path']not in found or found[r['path']]==r,'CONFLICTING_ROOT_PIN');found[r['path']]=r
        return [found[k] for k in sorted(found)]
    sources=unique(sources);data=unique(data)
    for r in sources:C.verify(r,2<<20)
    control=C.literal(a.control_directory);out=C.literal(a.output_directory)
    C.need(C.MAIN/'control' in control.parents and not control.exists() and C.MAIN/'artifacts/conformers' in out.parents and not out.exists(),'NEW_OWN_PLAN_AND_EXPORT_CHILDREN')
    control.mkdir(parents=True);path=control/'plan.json';proof=control/'proof.json';script=control/'parent.sbatch'
    endpoint={'id':'alpha','address':'218.192.171.238:22','uid':1264,'root':str(C.ALPHA),'memory_policy':'SLURM_DEFAULT_UNSPECIFIED'}
    shards=[{'shard_id':'alpha'+str(n),'endpoint':endpoint,'cpus':n,'node':node,'wall_seconds':86400,'stop_dispatch_before_wall_seconds':900,
        'output_cap_bytes':16<<30,'output_directory':str(C.ALPHA/'outputs/portable_n1_source_remaining_v1'/control.name/('alpha'+str(n)))}
        for n,node in ((64,'compute-0-1'),(16,'sonmi1'))]
    python=base['python_executable'];pythonpath=':'.join(dict.fromkeys([str(here.parent),*base['pythonpath'].split(':')]))
    plan={'schema':'N1_ZERO_UFF_SOURCE_REMAINDER_EXPORT_PLAN_V1','role':'freeze',
        'endpoint':{'id':'main','address':'202.38.247.57:22','uid':1278,'root':str(C.MAIN),'memory_policy':'SLURM_DEFAULT_UNSPECIFIED'},
        'cpus':16,'node':resources['node'],'wall_seconds':a.wall_seconds,'stop_dispatch_before_wall_seconds':min(600,a.wall_seconds//5),
        'output_cap_bytes':16<<30,'metadata_cap_bytes':8<<30,'output_directory':str(out),'control_directory':str(control),
        'startup_proof_path':str(proof),'script_path':str(script),'python_executable':python,'pythonpath':pythonpath,'workdir':str(repo),
        'execution_argv':[python,'-B','-m','portable_n1_source_remaining_v1.prepare','--plan',str(path),'--startup-proof',str(proof)],
        'job_name':'dv1_n1_source_remaining_export_v1','source_references':sources,'data_references':data,
        'quota_provider_review_reference':provider_ref,'quota_provider_identity_reference':identity_ref,
        'total_future_reserved_bytes':future['total_future_reserved_bytes'],'all_future_reservations_reference':future_ref,
        'prepared_reference':prepared_ref,'pilot_review_reference':pilot_ref,'prepare_accounting_reference':account_ref,
        'legacy_disabled_reference':legacy_ref,'shards':shards}
    review={'schema':'ROOT_DISJOINT_REMAINING_REVIEW_V4','status':'APPROVED','reviewer':'root','plan_body_sha256':C.value_sha(plan),
        'no_retry_or_claim_reset':True,'no_scientific_recipe_change':True,'root_reason':a.root_reason,
        'only_zero_UFF_export_and_explicit_foreign_assignment_reservations_authorized':True,'new_SCI_generation_authorized':False,
        'old_formal_full_source_job_authorized_by_this_review':pilot['formal_full_source_job_authorized_by_this_review']}
    plan['root_review_reference']=C.save(control/'root_review.json',review);plan_ref=C.save(path,plan);script_ref=M.script(path,script)
    print(json.dumps({'status':'PREPARED_NOT_SUBMITTED_UFF0','plan_reference':plan_ref,'script_reference':script_ref,
        'science_run_requires_actual_assignment_and_separate_exact_finite_review':True}))
    return 0


if __name__=='__main__':raise SystemExit(main())
