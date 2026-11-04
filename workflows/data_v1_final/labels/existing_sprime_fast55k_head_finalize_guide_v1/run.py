"""Real local finalizer of one completed TRAIN pass; no new statistics or QM."""
import argparse,datetime,json,os,pathlib,socket,time,traceback
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v13 import contract as C,run as P
from workflows.data_v1_final.labels.existing_sprime_fast55k_head_stats_resume_v1 import runtime as R
from workflows.data_v1_final.labels.existing_sprime_fast55k_head_stats_resume_v3 import runtime as V3
from workflows.data_v1_final.labels.existing_sprime_fast55k_head_v1 import run as H
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import bindings as B,loss as L

COMPLETE='PROVISIONAL55K_FAST_TYPED_NATIVE_RANDOM_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_LOCAL_EXIT_ZERO'

class FinalMemory(R.MemoryBinding):
    def start_observer(self,proof,binding):
        return R.I.R.start_observer(proof,dict(binding,resource_evidence_output=str(R.ROOT)+'_guide_finalize_resource_observation'))

def report(io,plan,components,numeric,output):
    fields=io.load_data(plan['field_map_reference'],2<<20)
    _,physical=B.inventory(dict(fields=fields,plan=dict(element_basis=plan['element_basis'])))
    actual={row['key']:row for row in numeric['winsorized_component_and_invariant_audit']['series']};groups=[]
    fids={f['field_id']for f in fields if f['registry_id']==674}
    for group in physical:
        if not set(group['field_ids'])&fids:continue
        C.need(set(group['field_ids'])<=fids and group['components']==list(L.COMPONENTS),'ACTUAL_R674_COMPLETE_SIX_FIELD_SCHEMA')
        key=group['key']+'/frobenius_norm';row=actual.get(key)
        recipe=L.scale_recipe(None if row is None else row['std_ddof0'],
          population_reference=components['population_reference'],statistic_reference=components['numeric_repetitions'][0],
          series_key=key,observed_population_reference=components['population_reference']if row is not None else None)
        recipe.update(actual_training_loss_enabled=False,loss_state='LOSS_DISABLED_PER_USER_PENDING_D6')
        groups.append(dict(physical_group=group['key'],loss_recipe_candidate=recipe,
          complete6_exclusion_bias_audit_status='NOT_RUN_DISABLED_TARGET_NONBLOCKING_PENDING_LATER_VERSION',
          raw_mean_F_report=dict(status='NOT_RUN_DISABLED_TARGET_NONBLOCKING',raw_complete6_TRAIN_F_mean=None,mean_F_over_bound_s=None),
          raw_component_mean_vector_separate=numeric['winsorized_component_and_invariant_audit']['raw_complete_physical_joint_audit'].get(group['key']),
          new_data_mask_from_loss_ineligibility=False))
    return io.save(output,dict(schema='PROVISIONAL_R674_USER_POLICY_LOSS_ELIGIBILITY_V1',
      user_decision_reference=plan['user_D1_decision_reference'],user_design_policy_reference=plan['user_D1_design_policy_reference'],
      population_version_reference=components['population_reference'],groups=groups,original_series_size_rho_reference=None,
      original_series_size_rho_status='D2_REQUIRED_MOLECULE_SCALARS_COMPUTED_IN_PARALLEL_D3_CPU_PARENT',
      r674_loss='LOSS_DISABLED',additional_QM_calls=0,additional_scalar_or_tensor_statistics_computed=False,
      source_and_original_masks_unchanged=True,full_training_release=False))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);args=parser.parse_args()
    envelope=C.meta(C.P.pin(args.plan));control=pathlib.Path(envelope['control_directory']);plan=dict(envelope['operative_plan'])
    policy=C.meta(envelope['guide_validation_scope_reference']);continuation=C.meta(envelope['first_complete_pass_continuation_reference'])
    authority=C.meta(envelope['headnode_authority_reference'])
    C.need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID')
      and authority['status']=='USER_AUTHORIZED' and authority['D4_only']is True,'REAL_USER_AUTHORIZED_D4_HEAD_FINALIZER')
    C.need(policy['status']=='USER_DIRECTED' and policy['operative_scope']['full_second_statistics_pass_required']is False
      and continuation['schema']=='ACTUAL_LOCAL_D4_FIRST_COMPLETE_PASS_GUIDE_CONTINUATION_V1'
      and continuation['guide_validation_scope_reference']==envelope['guide_validation_scope_reference']
      and continuation['first_complete_pass_preserved']is True
      and continuation['scientific_methods_or_quality_rules_changed']is False,'USER_REQUIRED_GUIDE_SINGLE_COMPLETE_PASS')
    prior=C.meta(continuation['actual_prior_receipt_reference']);oldproof=C.meta(continuation['actual_prior_proof_reference'])
    oldexit=C.meta(continuation['actual_prior_exit_reference']);oldlaunch=C.meta(continuation['actual_prior_launch_reference'])
    C.need(oldexit['exit_code']==1 and oldexit['actual_pid']==oldproof['pid']==oldlaunch['pid']
      and str(oldexit['actual_start_ticks'])==str(oldproof['start_ticks'])==str(oldlaunch['start_ticks'])
      and not pathlib.Path('/proc',str(oldproof['pid'])).exists() and not prior['held'] and prior['errors']==[]
      and len(prior['numeric_repetitions'])==1 and prior['numeric_repetitions'][0]==continuation['first_numeric_reference'],
      'REAL_CLOSED_SINGLE_COMPLETE_PASS_NO_CONCURRENT_STATISTICS_PARENT')
    root=pathlib.Path(plan['output_directory']);admin=root/'guide_finalize_metadata';admin.mkdir()
    origin=C.meta(envelope['statistics_resume_origin_reference'])
    plan['data_references']=C.unique([*plan['data_references'],*origin['runtime_additional_data_references']])
    R.ROOT=root;R.ADMIN=admin;R.ORIGIN=envelope['statistics_resume_origin_reference'];R.MemoryBinding=FinalMemory;H.WORKERS=16
    os.sched_setaffinity(0,set(range(16)));os.nice(10)
    pid=os.getpid();ticks=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19];started=time.time()
    identity='LOCAL_D4_PID'+str(pid)+'_START'+ticks
    marker=control/'head_storage_marker.json';marker.write_text(json.dumps(dict(pid=pid,uid=1278,execution_id=identity))+'\n')
    qi=control/'local_quota_identity.json';qi.write_text(json.dumps(dict(schema='ACTUAL_LOCAL_DIRECT_QUOTA_CLIENT_IDENTITY_V1',execution_kind='LOCAL_HEADNODE',pid=pid,uid=1278,start_ticks=ticks,started_unix_seconds=started,expires_unix_seconds=started+90000))+'\n')
    qr=control/'local_quota_review.json';qr.write_text(json.dumps(dict(execution_kind='LOCAL_HEADNODE',storage_marker_path=str(marker),snapshot_root=str(control/'quota_snapshots')))+'\n')
    plan.update(node='sonmi',workers=16,pending=32,plan_path=args.plan,quota_provider_identity_reference=C.P.pin(qi),quota_provider_review_reference=C.P.pin(qr))
    request=dict(schema='ACTUAL_LOCAL_HEAD_D4_REQUEST_V1',node='sonmi',cpus=16,wall_seconds=86400,memory_policy='OBSERVED_LOCAL_PROCESS_NO_SLURM_ALLOCATION',pilot=False,estimated_peak_output_bytes=plan['whole_output_cap_bytes'],data_references=plan['data_references'],local_quota_identity_reference=C.P.pin(qi),execution_kind='LOCAL_HEADNODE')
    rq=control/'actual_local_request.json';rq.write_text(json.dumps(request,sort_keys=True)+'\n')
    proof=dict(schema='ACTUAL_USER_AUTHORIZED_HEADNODE_D4_PROCESS_PROOF_V1',execution_kind='LOCAL_HEADNODE',execution_id=identity,job_id=identity,legacy_job_id_field_is_local_execution_id=True,Slurm_job_id=None,pid=pid,uid=1278,start_ticks=ticks,node='sonmi',actual_affinity=sorted(os.sched_getaffinity(0)),local_started_unix_seconds=started,request=request,request_reference=C.P.pin(rq),observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),root_observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    pp=control/'actual_local_process_proof.json';pp.write_text(json.dumps(proof,sort_keys=True)+'\n');plan['startup_proof_path']=str(pp)
    plan['source_references']=C.unique([*plan['source_references'],C.P.pin(qi),C.P.pin(qr),C.P.pin(pp)])
    io=R.ResumeIO();io.configure(plan);budget=None
    try:
        gate=V3.fixtures(P,admin/'source6');io.configure(plan);R.bind_worker_memory_metric()
        budget=R.Budget(plan,proof,root);budget.check(force=True)
        checkpoint=io.load_data(prior['checkpoint_reference'],8<<20)
        C.need(checkpoint['numeric_repetitions']==prior['numeric_repetitions'],'DURABLE_ACTUAL_FIRST_NUMERIC_CHECKPOINT')
        numeric=io.load_data(prior['numeric_repetitions'][0],256<<20)
        C.need(len(numeric['exact_tails']['catalog'])==888 and len(numeric['diagnostic_median_MAD'])==146
          and numeric['winsorized_component_and_invariant_audit']['fit_role']=='TRAIN_ONLY',
          'COMPLETE_ORIGINAL_FIRST_PASS_ALL_SERIES_AND_DIAGNOSTIC_FIELDS')
        components={k:prior[k]for k in ('prefix_reference','coverage_reference','geometry_reference','eligibility_reference','population_reference','typed_reader_config_reference','numeric_repetitions')}
        components['r674_report_reference']=report(io,plan,components,numeric,admin/'r674_loss_disabled_scale_candidates.json')
        checkpoint.update(phase='COMPLETE',r674_report_reference=components['r674_report_reference'],numeric_repetitions=prior['numeric_repetitions'],
          verification_scope='GUIDE_REQUIRED_ONE_COMPLETE_ACTUAL_PASS',full_second_statistics_pass_performed=False)
        cp=io.save(admin/'guide_complete_checkpoint.json',checkpoint);budget.check(force=True)
        receipt=dict(prior,status=COMPLETE,job_id=identity,actual_cpus=16,actual_node='sonmi',
          plan_reference=C.P.pin(args.plan),startup_proof_reference=C.P.pin(pp),fixture_gate=gate,
          checkpoint_reference=cp,held=False,errors=[],resource_soft_stop=False,**components,
          independent_numeric_replay_equal=None,verification_scope='GUIDE_REQUIRED_ONE_COMPLETE_ACTUAL_PASS',
          full_second_statistics_pass_performed=False,guide_required_checks_passed=True,
          guide_validation_scope_reference=envelope['guide_validation_scope_reference'],
          first_complete_pass_continuation_reference=envelope['first_complete_pass_continuation_reference'],
          Root_actual_C0_limited_acceptance_required=False,Root_actual_local_process_zero_exit_required=True,
          D2_size_rho_not_a_D4_normalization_gate=True,r674_extra_bias_and_raw_F_audit_performed=False,
          producer_execution_kind='LOCAL_HEADNODE',Slurm_job_id=None)
        rr=io.save(admin/'receipt.json',receipt)
        (control/'actual_final_receipt_path.json').write_text(json.dumps(rr)+'\n');return 0
    except BaseException as exc:
        (control/'local_failure.json').write_text(json.dumps(dict(error=repr(exc),traceback=traceback.format_exc(),actual_pid=pid,execution_id=identity,no_fake_Slurm_job_or_C0=True))+'\n');raise
    finally:
        if budget is not None:budget.close()

if __name__=='__main__':raise SystemExit(main())
