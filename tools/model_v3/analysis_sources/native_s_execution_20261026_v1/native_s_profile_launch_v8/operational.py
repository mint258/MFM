"""Create job-specific operational frames from the actual supervised child.

No Root authority is synthesized here. The Root coordinator must first create
the finite principal/feed/lease and the exact source-bound sbatch submission.
"""
from __future__ import annotations
import os
from pathlib import Path
import sys
from common import *

def policy():
    return dict(schema='model_v3_long_run_policy_v1',segment_bytes=OUTER,segment_seconds=7200,
        durable_bytes=3<<30,metadata_bytes=32<<20,metadata_records=2000,managed_roots=24,
        inode_limit=10000,quota_max_age_seconds=90,checkpoint_bytes=384<<20,
        counts=dict(launch_attempts=2,successful_segments=1,failed_attempts=1,checkpoint_attempts=4,
            complete_checkpoints=4,successful_panels=0,failed_panels=0,wsd_children=0,events=0,ack_attempts=0))

def configuration(adapter,contract):
    return dict(schema='existing_native_S_storage_configuration_v2',engineering_only=False,
        purpose=adapter.PROFILE,profile_updates=20,Root_storage_commit=adapter.ROOT_COMMIT,
        Root_runtime_pin=adapter.runtime_pin(contract),
        science=dict(scope=adapter.SCOPE,source=adapter.SOURCE,plan=adapter.PLAN,
            members=[[0,'fp32'],[0,'bf16'],[1,'fp32'],[1,'bf16']],model=dict(dim=512,layers=6,heads=8,ff_mult=2),
            sampling='original_TRAIN_record_natural_counts_not_molecule_uniform',native_repo=str(RUNTIME)),
        long_run_policy=policy(),capacity=dict(child_seconds=6900,GPU_fraction=.85,
            max_checkpoints_per_segment=2,checkpoint_reserve_seconds=300,
            checkpoint_reserve_bytes=64<<20,non_checkpoint_bytes=128<<20))

def budget_roots(phase,job,stdio):
    phase=Path(phase);job=str(job)
    return [phase/'control',phase/f'job_{job}'/'management',phase/f'job_{job}'/'child',
        phase/'ledger',phase/'lineage'],sorted(set(stdio.values()))

def whole_census(phase,job,stdio,monitor):
    """Disjoint directory roots and physical unique external stdio files.

    The W&B census is invoked at the real child root, retaining its exact SDK
    link allowlist. We never apply it to a nested wrapper directory.
    """
    roots,logs=budget_roots(phase,job,stdio)
    require(not any(a!=b and (a.is_relative_to(b) or b.is_relative_to(a)) for a in roots for b in roots),
        'Whole-job roots overlap')
    totals={str(path):monitor.owned_output_bytes(path) for path in roots}
    seen=set();log_bytes=0
    for name in logs:
        path=Path(name)
        require(path.is_absolute() and not path.is_symlink() and not any(path.is_relative_to(root) for root in roots),
            'Stdio must be a separate ordinary file')
        info=path.stat();require(info.st_uid==os.getuid(),'Stdio UID differs')
        key=info.st_dev,info.st_ino
        if key not in seen:seen.add(key);log_bytes+=info.st_size
    management=sum(size for name,size in totals.items() if name!=str(roots[2]))
    # 16MiB static management + frozen supervisor32MiB journal +32MiB stdio
    # +2MiB supervisor receipt/report +14MiB finalization fits96MiB exactly.
    # The journal lives in management; its independent32MiB cap is enforced
    # by the frozen supervisor. Static management is measured separately.
    journal=roots[1]/'supervisor.json.jsonl'
    journal_bytes=journal.stat().st_size if journal.exists() else 0
    require(management-journal_bytes<=16<<20 and log_bytes<=32<<20,
        'Management or inherited stdio consumed original96MiB reserve')
    total=sum(totals.values())+log_bytes
    require(total<=OUTER,'Whole persistent job exceeded original2GiB')
    return dict(schema='native_S_whole_job_census_v1',directory_bytes=totals,
        unique_stdio_bytes=log_bytes,whole_bytes=total,cap_bytes=OUTER,
        semantics='sampled_physical_unique_disjoint_roots; not_exact_temporal_peak')

def private_domains(receipt,*,job_id):
    import root_coverage
    require(receipt['schema']=='model_v3_private_storage_v1' and str(receipt['job_id'])==str(job_id)
        and len(receipt['roots'])==1,'Exact fresh task private-storage schema required for first profile')
    result=[]
    for root in receipt['roots']:
        path=root_coverage.task_scratch_metadata(root,job_id=job_id)
        result.append(dict(path=path,domain='node_local_ephemeral'))
    require(all(any(Path(path).is_relative_to(Path(root['path'])) for root in receipt['roots'])
        for path in receipt['environment'].values()),'Private environment escapes actual sampled scratch')
    return result


def build(callback,contract,*,phase,submission,observations,runner,observer):
    import root_coverage
    phase=Path(phase);control=phase/'control'; job=os.environ['SLURM_JOB_ID']
    management=phase/f'job_{job}'/'management'
    launch=read_ref(submission)
    require(launch['actual_sbatch_job_id']==job and launch['phase']==str(phase)
        and launch['status']=='SUBMITTED' and callback['precision']==launch['precision'],
        'Actual Root submission/member differs')
    require(read_ref(launch['candidate_ready'])['contract']==binding(os.environ['MODEL_V3_NATIVE_S_RUNTIME_CONTRACT']),
        'Actual candidate contract differs from Root submission')
    prelaunch=read(management/'prelaunch.json')
    require(prelaunch['submission']==submission and prelaunch['process']['job_id']==job,'Actual prelaunch source mismatch')
    inline_ref=None
    if launch['launch_validation_mode']=='PROFILE_LAUNCH_VALIDATION':
        inline_ref=binding(management/'inline_launch_QA.json');qa=read_ref(inline_ref)
        from inline_qa import verdict
        expected=read(HERE/'CPU_test_request.json')['expected_parameterized_cases_from_static_review']
        require(qa['status']==verdict(qa['returncode'],qa['counts'],qa['sources_before'],qa['sources_after'],expected)
            and qa['job_id']==job and qa['actual_environment']['CUDA_VISIBLE_DEVICES']==''
            and qa['independent_CPU_parent_C0_claimed'] is False and qa['actual_parent_C0'] is None,
            'Inline launch QA must actually precede model, without a fabricated external C0')
    parent=root_coverage.parent_observation()
    record=management/'supervisor.json'
    require(Path(observations)==Path(str(record)+'.jsonl'),
        'Child observations assertion must equal real supervisor derived journal')
    require(parent['argv'].count('--observations')==1 and parent['argv'].index('--observations')>parent['argv'].index('--'),
        'Observations assertion must be child-only, never invalid supervisor option')
    require(root_coverage.option(parent['argv'],'--record')==str(record),
        'Actual supervisor record path differs')
    config=binding(control/'configuration.json');principal=binding(control/'principal.json')
    principal_value=read_ref(principal)
    receipt=callback['private_storage']
    private=private_domains(receipt,job_id=job)
    import native_s_storage as adapter
    require(adapter.root_coverage is root_coverage and Path(root_coverage.__file__).absolute()==HERE/'root_coverage.py',
        'Actual frozen adapter must use this explicit source-bound ops coverage extension')
    coverage_source=root_coverage.ops_extension_source()
    files=('configuration.json','principal.json','Root_reservation_record.json','initial_roots.json',
        'lease.json','quota_descriptor.json','submission.json')
    artifacts=[dict(role='Root_control:'+name,path=str(control/name),type='file',raw_reference=binding(control/name)) for name in files]
    artifacts.append(dict(role='worker_prelaunch',path=str(management/'prelaunch.json'),type='file',
        raw_reference=binding(management/'prelaunch.json')))
    if launch.get('operational_source_snapshot') is not None:
        snapshot=launch['operational_source_snapshot']
        from operations import verify_source_snapshot
        verify_source_snapshot(snapshot,launch['package_manifest'])
        artifacts.append(dict(role='operational_source_snapshot',path=str(Path(snapshot['path']).parent),
            type='directory',relative_manifest=dict(raw_reference=snapshot,entries_field='files',
                path_field='relative_path',bytes_field='bytes',sha256_field='sha256')))
    if inline_ref is not None:
        artifacts.append(dict(role='inline_launch_QA',path=inline_ref['path'],type='file',raw_reference=inline_ref))
    supervisor_source=binding(RUNTIME/'tools/model_v3/run_supervised.py')
    launch_ref=write(management/'actual_supervisor_launch.json',dict(schema='native_S_actual_supervisor_launch_v2',
        argv=parent['argv'],job_id=job,uid=os.getuid(),supervisor_source=supervisor_source,
        stdio=parent['stdio'],prepared_external_artifacts=artifacts,
        actual_parent_process=parent,observations_argument_semantics='child_assertion_of_parent_derived_journal'))
    stdio=sorted(set(parent['stdio'].values()))
    registry=read(control/'initial_roots.json')
    controls=[row for row in registry['roots'] if row['path']==str(control)]
    require(len(controls)==1 and controls[0]==dict(path=str(control),type='directory',kind='management',must_exist=True),
        'Actual control accounting root must match initial registry exactly')
    external=[dict(controls[0]),dict(path=str(management),type='directory',kind='external_guard',must_exist=True)]
    external.extend(dict(path=name,type='file',kind='external_guard',must_exist=True) for name in stdio)
    child=Path(callback['output_root']);lineage=phase/'lineage'
    rows=[]
    def add(role,path,kind='directory',domain='durable',accounting_root=None):
        rows.append(dict(role=role,path=str(path),type=kind,domain=domain,
            accounting_root=str(accounting_root or path)))
    add('child_output',child,accounting_root=child)
    for row in artifacts:add(row['role'],row['path'],row['type'],accounting_root=control if Path(row['path']).is_relative_to(control) else management)
    for role,path in [('supervisor_record',record),('supervisor_observations',observations),
        ('private_receipt',receipt['receipt_path'])]:add(role,path,'file',accounting_root=management)
    for role,name in parent['stdio'].items():add('slurm_'+role,name,'file',accounting_root=name)
    for row in private:add('private_root',row['path'],domain=row['domain'])
    for key,path in receipt['environment'].items():add('environment:'+key,path,domain='private_environment')
    for key,name in [('WANDB_CACHE_DIR','cache'),('WANDB_DATA_DIR','wandb_data'),('WANDB_CONFIG_DIR','wandb_config')]:
        add(key,child/name,accounting_root=child)
    add('lineage',lineage,accounting_root=lineage)
    add('management',principal_value['durable_root'])
    request=dict(schema='existing_native_S_storage_request_v1',configuration=config,
        native_member={k:callback[k] for k in ('scope','plan','seed','precision','code_sha','prereg_sha','sources','runtime')},
        long_run=dict(reservation_principal=principal,initial_roots=binding(control/'initial_roots.json'),
            quota_feed_descriptor=binding(control/'quota_descriptor.json'),lease=binding(control/'lease.json')))
    storage,_=adapter.load_runtime(allow_candidate_profile=True)
    admission=write(management/'Root_segment_admission.json',dict(schema='model_v3_Root_long_run_segment_admission_v1',
        authority='ROOT_ACTUAL',stable_request_identity_sha256=adapter.stable_native_request(request,storage),
        reservation_principal=principal,lease=request['long_run']['lease'],quota_feed_descriptor=request['long_run']['quota_feed_descriptor'],
        workload='native_S_profile_only',segment_id='nativeS_profile_'+job,job_id=job,job_root=str(child),
        lineage_root=str(lineage),external_roots=external,supervisor_source=supervisor_source,
        supervisor_launch=launch_ref,private_root_domains=private,root_coverage=rows,
        actual_prelaunch=binding(management/'prelaunch.json'),resources=prelaunch['resource_observations'],
        launch_validation_mode=launch['launch_validation_mode'],actual_inline_launch_QA=inline_ref,
        operational_source_status=launch['operational_source_status'],operational_source_snapshot=launch.get('operational_source_snapshot'),
        actual_coverage_extension_source=coverage_source,
        usable_scientific_result=False,
        profile_runner_source=binding(runner),profile_observer_source=binding(observer),
        resource_envelope=dict(outer_output_budget_bytes=OUTER,child_output_budget_bytes=CHILD,
            supervisor_output_reserve_bytes=96<<20,private_storage_budget_bytes=PRIVATE,additional_durable_private_growth_hold_bytes=0)))
    request['long_run']['Root_segment_admission']=admission
    ref=write(management/'request.json',request)
    os.environ.update(MODEL_V3_NATIVE_S_STORAGE_REQUEST=ref['path'],MODEL_V3_NATIVE_S_STORAGE_REQUEST_SHA256=ref['sha256'])
    import runtime_monitor
    whole_census(phase,job,parent['stdio'],runtime_monitor)
    return dict(request=ref,parent=parent,phase=str(phase),job_id=job)
