"""Alpha Root metadata only, after actual export C0 and exact-key/cost review."""
import argparse,json,pathlib,sys
from . import contract as C,metadata as M
from .source import existing_environment


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('assignments','source-stage','locator-map','environment','legacy-control16-deployment','storage-scope-review','aggregate-future','control-root'):
        p.add_argument('--'+name,type=pathlib.Path,required=True)
    p.add_argument('--root-approve-exact-finite-N1-shards',action='store_true');p.add_argument('--root-over500-ceiling-reviewed',action='store_true')
    p.add_argument('--root-reason',required=True);a=p.parse_args()
    C.need(a.root_approve_exact_finite_N1_shards and a.root_over500_ceiling_reviewed and a.root_reason.strip(),'ROOT_EXACT_FINITE_SCIENCE_AND_OVER500_ALLOCATION_CEILING_REVIEW')
    manifest_ref=C.ref(a.assignments,2<<20);manifest=C.load(manifest_ref);mv=C.load_path(a.locator_map);mapping=mv.get('locator_map',mv)
    origins=[p for p,r in mapping.items() if C.triple(r)==manifest_ref];C.need(len(origins)==1,'ONE_ORIGINAL_MAIN_ASSIGNMENT_REFERENCE')
    origin={**manifest_ref,'path':origins[0]}
    C.need(manifest['schema']=='N1_SOURCE_FINITE_REMAINING_ASSIGNMENTS_V1' and manifest['status']=='FROZEN_AWAITING_ROOT_EXACT_FINITE_SCIENCE_REVIEW'
        and 0<manifest['remaining_frozen']<=4631,'ACTUAL_POSITIVE_FINITE_KEYS_NOT_FULL_SOURCE_PERMISSION')
    source_stage=C.load_path(a.source_stage);environment_ref=C.ref(a.environment,2<<20);environment=C.load(environment_ref)
    legacy_ref=C.ref(a.legacy_control16_deployment,2<<20);legacy,_=existing_environment(environment,legacy_ref)
    storage_ref=C.ref(a.storage_scope_review,2<<20);storage=C.load(storage_ref)
    future_value=C.load_path(a.aggregate_future);future_ref=future_value.get('review_reference',C.ref(a.aggregate_future,2<<20));future=C.load(future_ref)
    C.need(future['reviewer']=='root' and future['status']=='APPROVED' and future['total_future_reserved_bytes']>=32<<30,'ACTUAL_ALPHA_AGGREGATE_FUTURE_INCLUDES_BOTH_FINITE_CAPS')
    if 'review_reference'in future_value:C.need(future_value['total_future_reserved_bytes']==future['total_future_reserved_bytes'],'LATEST_IMMUTABLE_BUDGET')
    sources=[environment_ref,legacy_ref,storage_ref,future_ref,C.ref(a.locator_map,2<<20),C.ref(a.source_stage,2<<20)]
    sources.extend(r['target_locator'] for r in source_stage['copies'])
    sources.extend(r['target_locator'] for r in legacy['science_sources'])
    sources.extend(r['target_locator'] for r in legacy.get('portable_worker_sources',[]))
    sources.extend([legacy['original_recipe_target_locator'],legacy['recipe_target_locator'],legacy['environment_review_target_locator']])
    sources.extend(environment['existing_control16_by_endpoint']['alpha'].values())
    sources.extend(storage['evidence_references']);sources.extend(r['metadata_reference'] for r in storage.get('additional_task_output_reservations',[]))
    package=pathlib.Path(__file__).absolute().parent
    secondary=C.ALPHA/'code/secondary_cpu_queue_v1'
    sources.extend(C.ref(secondary/n,2<<20) for n in ('__init__.py','common.py'))
    unique={}
    for r in sources:C.verify(r,2<<20);C.need(r['path']not in unique or unique[r['path']]==C.triple(r),'CONFLICTING_ACTUAL_NATIVE_SOURCE');unique[r['path']]=C.triple(r)
    source_refs=[unique[k] for k in sorted(unique)];control=C.literal(a.control_root)
    C.need(C.ALPHA/'control'in control.parents and not control.exists(),'FRESH_NATIVE_CONTROL');control.mkdir(parents=True)
    prepared_ref=manifest['source_prepared_reference'];prepared_target=mapping.get(prepared_ref['path'],prepared_ref)
    C.need(prepared_target['sha256']==prepared_ref['sha256'] and prepared_target['bytes']==prepared_ref['bytes'],'EXACT_SOURCE_PREPARED_METADATA_COPY')
    C.load(prepared_target);plans=[]
    for shard in manifest['shards']:
        if not shard['molecules']:continue
        sid=shard['shard_id'];directory=control/sid;directory.mkdir();path=directory/'plan.json';script=directory/'parent.sbatch';proof=directory/'proof.json'
        C.need(shard['endpoint']['id']=='alpha' and shard['cpus']in(16,64) and not C.literal(shard['output_directory']).exists(),'EXACT_FROZEN_FOREIGN_NATIVE_OWNER')
        data=[manifest_ref,prepared_target]
        for key in ('members_reference','tasks_reference'):
            r=shard[key];t=mapping.get(r['path'],r);C.need(t['bytes']==r['bytes'] and t['sha256']==r['sha256'],'EXACT_NATIVE_INPUT_COPY');data.append(t)
        python=str(C.ALPHA/'chemprop_compatible_v2/bin/python')
        plan={k:shard[k] for k in ('endpoint','cpus','node','wall_seconds','stop_dispatch_before_wall_seconds','output_cap_bytes','output_directory')}
        plan.update(schema='N1_FINITE_ALPHA_RUN_PLAN_V1',role='run',shard_id=sid,whole_remaining_count=manifest['remaining_frozen'],
            actual_export_job_id=str(manifest['actual_export_job_id']),assignment_manifest_reference=origin,locator_map=mapping,
            legacy_control16_deployment_reference=legacy_ref,environment_review_reference=environment_ref,storage_scope_review_reference=storage_ref,
            total_future_reserved_bytes=future['total_future_reserved_bytes'],all_future_reservations_reference=future_ref,
            aggregate_cost_group_path=str(control/'actual_cost_group.json'),control_directory=str(directory),startup_proof_path=str(proof),script_path=str(script),
            job_name='dv1_n1_finite_'+sid+'_'+C.sha(str(control).encode())[:8],python_executable=python,
            pythonpath=str(package.parent)+':'+str(C.ALPHA/'code'),workdir=str(C.ALPHA),source_references=source_refs,data_references=data,
            execution_argv=[python,'-B','-m','portable_n1_source_remaining_v1.run','--plan',str(path),'--startup-proof',str(proof)])
        review={'schema':'ROOT_DISJOINT_REMAINING_REVIEW_V4','status':'APPROVED','reviewer':'root','plan_body_sha256':C.value_sha(plan),
            'no_retry_or_claim_reset':True,'no_scientific_recipe_change':True,'exact_frozen_N1_shard_authorized':True,
            'not_an_override_of_old_full_source_false':True,'user_two_times_comparable_allocated_cost_stop_new_natural_drain':True,
            'aggregate_allocation_ceiling_over500_corehours_reviewed':True,'exact_task_keys_sha256':shard['task_keys_sha256'],
            'assignment_manifest_reference':origin,'root_reason':a.root_reason,'full_unbounded_N1_source_or_Common_release':False}
        plan['root_review_reference']=C.save(directory/'root_review.json',review);pr=C.save(path,plan);sr=M.script(path,script)
        plans.append({'shard_id':sid,'molecules':shard['molecules'],'plan_reference':pr,'script_reference':sr,'cpus':shard['cpus'],'node':shard['node']})
    C.save(control/'build_receipt.json',{'schema':'N1_FINITE_NATIVE_PLANS_ROOT_REVIEWED_V1','status':'PREPARED_NOT_SUBMITTED',
        'assignment_manifest_reference':origin,'plans':plans,'new_SCI_QM_calls':0,'old_false_gate_overridden':False,
        'post_actual_submission_cost_group_and_fresh_proofs_still_required':True})
    print(json.dumps({'status':'PREPARED_NOT_SUBMITTED','plans':plans}));return 0


if __name__=='__main__':raise SystemExit(main())
