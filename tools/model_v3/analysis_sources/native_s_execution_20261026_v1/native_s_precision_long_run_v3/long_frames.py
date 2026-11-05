"""Actual child operational frames and separate job/global accounting."""
from __future__ import annotations
import os
from pathlib import Path
import stat
from long_common import *


def ledger_baseline(phase,monitor):
    root=Path(phase)/'ledger'
    if not root.exists():
        return dict(path=str(root),exists=False,bytes=0,device=None,inode=None,
            semantics='observed_absence_before_this_job; not_unknown_size')
    info=root.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid() and not root.is_symlink(),
        'Ordinary owned shared ledger required')
    return dict(path=str(root),exists=True,bytes=monitor.owned_output_bytes(root),
        device=info.st_dev,inode=info.st_ino,
        semantics='retained_shared_metadata_input_before_this_job; complete_global_policy_still_applies')


def whole_census(phase,job,stdio,baseline,monitor):
    phase=Path(phase);slot=Path(baseline['slot_root']);management=slot/'management';child=slot/'child'
    require(baseline['job_id']==str(job) and slot.parent==phase/'slots','Actual job/slot baseline differs')
    roots=dict(control=phase/'control',management=management,child=child,ledger=phase/'ledger',lineages=phase/'lineages')
    totals={key:monitor.owned_output_bytes(path) for key,path in roots.items() if key!='ledger'}
    require(str(roots['ledger'])==baseline['path'],'Shared ledger baseline path differs')
    if baseline['exists']:
        info=roots['ledger'].lstat()
        require((info.st_dev,info.st_ino)==(baseline['device'],baseline['inode']),
            'Shared historical ledger identity changed')
    # Charge the ENTIRE finite shared-ledger ceiling to every job. This is
    # stricter than charging only this job's growth and avoids per-step scans
    # through all32768 historical JSON files.075 enforces this512MiB ceiling
    # on every metadata write; its refresh/final seal still scan actual roots.
    ledger_charge=policy()['metadata_bytes']
    seen=set();stdio_bytes=0
    for name in set(stdio.values()):
        path=Path(name);require(not path.is_symlink() and not any(path.is_relative_to(p) for p in roots.values()),
            'Actual Slurm stdio scope overlaps declared roots')
        info=path.stat();require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid(),'Owned regular Slurm stdio required')
        identity=info.st_dev,info.st_ino
        if identity not in seen:stdio_bytes+=info.st_size;seen.add(identity)
    journal=management/'supervisor.json.jsonl';journal_bytes=journal.stat().st_size if journal.exists() else 0
    directory_overhead=sum(path.lstat().st_size for path in (phase,phase/'slots',phase/'logs',slot) if path.exists())
    static=totals['control']+totals['management']+totals['lineages']-journal_bytes+directory_overhead
    require(static<=16<<20 and journal_bytes<=32<<20 and stdio_bytes<=32<<20,
        'Per-job management/journal/stdio exhausted original96MiB reserve')
    whole=totals['child']+static+journal_bytes+stdio_bytes+ledger_charge
    require(whole<=OUTER,'Whole job including shared metadata growth exceeds original2GiB')
    return dict(schema='native_S_long_whole_job_census_v1',whole_job_bytes=whole,cap_bytes=OUTER,
        child_bytes=totals['child'],shared_ledger_ceiling_charged_bytes=ledger_charge,
        shared_ledger_baseline=baseline,actual_current_shared_ledger_bytes=None,
        static_management_bytes=static,supervisor_journal_bytes=journal_bytes,unique_stdio_bytes=stdio_bytes,
        full_shared_control_bytes=totals['control'],full_lineage_metadata_bytes=totals['lineages'],
        historical_outputs_not_deleted_or_ignored_by_global_ledger=True,
        semantics='job_output_physical_census_plus_entire_finite_shared_ledger_cap; conservative_not_measured_peak')


def build(callback,contract,*,phase,submission,observations,baseline):
    import native_s_storage as adapter,root_coverage,operational as profile_frames,runtime_monitor
    phase=Path(phase);control=phase/'control';job=os.environ['SLURM_JOB_ID']
    child=Path(callback['output_root']);management=child.parent/'management'
    launch=read_ref(submission)
    require(launch['status']=='SUBMITTED' and launch['actual_sbatch_job_id']==job and launch['phase']==str(phase)
        and (launch['seed'],launch['precision'])==(callback['seed'],callback['precision']),
        'Root actual long submission/member differs')
    require(binding(os.environ['MODEL_V3_NATIVE_S_RUNTIME_CONTRACT'])==launch['runtime_contract'],
        'Immutable runtime contract differs')
    parent=root_coverage.parent_observation();record=management/'supervisor.json'
    require(Path(observations)==Path(str(record)+'.jsonl')
        and root_coverage.option(parent['argv'],'--record')==str(record),
        'Actual supervisor record/observations differ')
    require(parent['argv'].count('--observations')==1
        and parent['argv'].index('--observations')>parent['argv'].index('--'),
        'Observations is a child assertion, never a supervisor option')
    supervisor_argv=parent['argv'][:parent['argv'].index('--')]
    require(root_coverage.option(supervisor_argv,'--wall-seconds')==str(SUPERVISOR_SECONDS),
        'Actual bounded supervisor wall differs')
    config=binding(control/'configuration.json');principal=binding(control/'principal.json')
    require(config==launch['configuration'] and principal==launch['principal'],'Shared immutable science config/principal differs')
    receipt=callback['private_storage'];private=profile_frames.private_domains(receipt,job_id=job)
    require(adapter.root_coverage is root_coverage and Path(root_coverage.__file__).absolute()==V8/'root_coverage.py',
        'Long child must reuse actual V8 coverage extension unchanged')
    extension=root_coverage.ops_extension_source()
    artifacts=[]
    for role,ref in [('configuration',config),('principal',principal),
        ('Root_reservation_record',binding(control/'Root_reservation_record.json')),
        ('initial_roots',launch['initial_roots']),
        ('quota_descriptor',binding(control/'quota_descriptor.json')),
        ('lease',launch['lease']),('submission',submission),
        ('ledger_baseline',binding(management/'ledger_baseline.json')),
        ('prelaunch',binding(management/'prelaunch.json'))]:
        artifacts.append(dict(role=role,path=ref['path'],type='file',raw_reference=ref))
    source_manifest=binding(management/'source_snapshot/MANIFEST.json')
    artifacts.append(dict(role='long_source_snapshot',path=str(management/'source_snapshot'),type='directory',
        relative_manifest=dict(raw_reference=source_manifest,entries_field='files',path_field='relative_path',
            bytes_field='bytes',sha256_field='sha256')))
    supervisor_source=binding(RUNTIME/'tools/model_v3/run_supervised.py')
    launch_ref=write(management/'actual_supervisor_launch.json',dict(schema='native_S_actual_supervisor_launch_v2',
        argv=parent['argv'],job_id=job,uid=os.getuid(),supervisor_source=supervisor_source,stdio=parent['stdio'],
        prepared_external_artifacts=artifacts,actual_parent_process=parent,
        readonly_input_evidence=[launch['profile']]))
    registry_ref=launch['initial_roots'];controls=[row for row in read_ref(registry_ref)['roots'] if row['path']==str(control)]
    require(controls==[dict(path=str(control),kind='management',type='directory',must_exist=True)],
        'Control accounting root must match the one original immutable registry record')
    # These finite slots were registered before sbatch with must_exist=False.
    # Preserve the exact immutable record when they become real; root_seen
    # then prevents an observed historical output from silently disappearing.
    external=[dict(controls[0]),dict(path=str(management),kind='external_guard',type='directory',must_exist=False)]
    external += [dict(path=name,kind='external_guard',type='file',must_exist=False) for name in sorted(set(parent['stdio'].values()))]
    lineage=phase/'lineages'/f'seed{callback["seed"]}_{callback["precision"]}'
    rows=[]
    def add(role,path,kind='directory',domain='durable',accounting_root=None):
        rows.append(dict(role=role,path=str(path),type=kind,domain=domain,accounting_root=str(accounting_root or path)))
    add('child_output',child)
    for artifact in artifacts:
        path=Path(artifact['path'])
        # Read-only readiness refs may be outside this lineage. They are
        # source evidence, never newly produced output or private growth.
        if path.is_relative_to(control):account=control
        elif path.is_relative_to(management):account=management
        else:continue
        add(artifact['role'],path,artifact['type'],accounting_root=account)
    for role,path in [('supervisor_record',record),('supervisor_observations',observations),('private_receipt',receipt['receipt_path'])]:
        add(role,path,'file',accounting_root=management)
    for role,path in parent['stdio'].items():add('slurm_'+role,path,'file')
    for value in private:add('private_root',value['path'],domain=value['domain'])
    for key,path in receipt['environment'].items():add('environment:'+key,path,domain='private_environment')
    for key,path in [('WANDB_CACHE_DIR','cache'),('WANDB_DATA_DIR','wandb_data'),('WANDB_CONFIG_DIR','wandb_config')]:
        add(key,child/path,accounting_root=child)
    add('lineage',lineage);add('management',phase/'ledger')
    prelaunch=read(management/'prelaunch.json')
    request=dict(schema='existing_native_S_storage_request_v1',configuration=config,
        native_member={key:callback[key] for key in ('scope','plan','seed','precision','code_sha','prereg_sha','sources','runtime')},
        long_run=dict(reservation_principal=principal,initial_roots=registry_ref,
            quota_feed_descriptor=binding(control/'quota_descriptor.json'),lease=launch['lease'],profile=launch['profile']))
    storage,_=adapter.load_runtime()
    admitted=write(management/'Root_segment_admission.json',dict(schema='model_v3_Root_long_run_segment_admission_v1',
        authority='ROOT_ACTUAL',stable_request_identity_sha256=adapter.stable_native_request(request,storage),
        reservation_principal=principal,lease=launch['lease'],quota_feed_descriptor=request['long_run']['quota_feed_descriptor'],
        workload='native_S_B_member',segment_id=launch['segment_id'],job_id=job,job_root=str(child),lineage_root=str(lineage),
        external_roots=external,supervisor_source=supervisor_source,supervisor_launch=launch_ref,
        private_root_domains=private,root_coverage=rows,actual_prelaunch=binding(management/'prelaunch.json'),
        resources=prelaunch['resource_observations'],actual_coverage_extension_source=extension,
        resource_envelope=dict(outer_output_budget_bytes=OUTER,child_output_budget_bytes=CHILD,
            supervisor_output_reserve_bytes=96<<20,private_storage_budget_bytes=PRIVATE,
            additional_durable_private_growth_hold_bytes=0)))
    request['long_run']['Root_segment_admission']=admitted
    ref=write(management/'request.json',request)
    os.environ.update(MODEL_V3_NATIVE_S_STORAGE_REQUEST=ref['path'],MODEL_V3_NATIVE_S_STORAGE_REQUEST_SHA256=ref['sha256'])
    whole_census(phase,job,parent['stdio'],baseline,runtime_monitor)
    return dict(request=ref,parent=parent)
