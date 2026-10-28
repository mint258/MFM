"""Finish FAILED1411 metadata only; reuse committed8/9, never seal/count/train again."""
from __future__ import annotations
import argparse
from collections import Counter
import json
import os
from pathlib import Path
from long_common import *


def inspect_ledger(storage,phase,configuration,principal):
    """Read-only view; do not construct/refresh/append a live ledger."""
    root=Path(phase)/'ledger';limits=configuration['long_run_policy']
    header=storage.read_bound(storage.binding(root/'PRINCIPAL.json'))
    require(header==dict(schema='model_v3_durable_ledger_v1',reservation_principal=principal,policy=limits),
        'Original principal/policy changed')
    view=object.__new__(storage.DurableLedger);view.root=root;view.limits=limits
    rows=storage.DurableLedger.records(view);roots=storage.DurableLedger.root_records(view)
    total=0;inodes=0;seen={row['identity'] for row in rows if row['kind']=='root_seen'}
    paths=[storage.physical(row['path']) for row in roots]
    require(len(set(paths))==len(paths) and not any(a!=b and (a.is_relative_to(b) or b.is_relative_to(a))
        for a in paths for b in paths),'Original registered roots overlap')
    for row,path in zip(roots,paths):
        if not path.exists():
            require(not row['must_exist'] and str(path) not in seen,'Historical observed root disappeared')
            continue
        require(path.stat().st_uid==os.getuid(),'Original output owner differs')
        require(path.is_dir() if row['type']=='directory' else path.is_file(),'Original registered type differs')
        total+=storage._runtime_census(path) if row['type']=='directory' else storage.binding(path)['bytes']
        inodes+=1
        if row['type']=='directory':
            for _,directories,files in os.walk(path,followlinks=False):inodes+=len(directories)+len(files)
    require(total<=limits['durable_bytes'] and inodes<=limits['inode_limit'],'Original global storage/inode ceiling exceeded')
    require(storage.owned_bytes(root)<=limits['metadata_bytes']
        and sum(1 for _ in root.rglob('*.json'))<=limits['metadata_records'],'Original metadata envelope exceeded')
    parents=[Path(phase),Path(phase)/'slots',Path(phase)/'logs',Path(phase)/'lineages']
    parents += [slot_layout(phase,slot)['root'] for slot in range(1,109)]
    extra=sum(path.lstat().st_size for path in parents if path.exists())
    require(total+extra<=limits['durable_bytes'],'Directory overhead exceeds original durable cap')
    return dict(rows=rows,total=total,parent_bytes=extra,inodes=inodes)


def main():
    root_identity();parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',type=Path,required=True);parser.add_argument('--pins-sha256',required=True)
    args=parser.parse_args();manifest,_=verify(args.pins_sha256)
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','Failed repair hides CUDA')
    require(args.phase==N/'native_S_B20k_v3','This repair is restricted to the actual failed phase')
    from long_operations import lock
    from seal_support import compute_census
    import root_phase
    with lock(args.phase):
        submission_path=args.phase/'control/attempts/slot_001.submitted.json'
        submission=binding(submission_path);frame=read_ref(submission)
        require(frame['actual_sbatch_job_id']=='4521411' and frame['slot']==1
            and frame['start_update']==0 and frame['resume_checkpoint'] is None,'Exact FAILED1411 source launch required')
        management=slot_layout(args.phase,1)['management'];terminal=binding(management/'actual_terminal.json')
        actual_terminal=read_ref(terminal);raw=read_ref(actual_terminal['raw_sacct'])
        require(terminal_rows(raw,'4521411')==['FAILED','1:0'] and actual_terminal['status']=='FAILED'
            and actual_terminal['exit_code']==1 and actual_terminal['exit_code_raw']=='1:0','Actual terminal must remain FAILED1')
        supervisor_ref=binding(management/'supervisor.json');supervisor=read_ref(supervisor_ref)
        require(str(supervisor['job_id'])=='4521411' and supervisor['status']=='FAILED'
            and supervisor['remaining_recorded_processes_before_retirement']==[]
            and supervisor['private_storage_cleanup_errors']==[],'Actual process/private closure incomplete')
        closure=binding(management/'Root_storage_closure.json');closed=read_ref(closure)
        require(closed==dict(schema='model_v3_Root_storage_segment_closure_v1',authority='ROOT_ACTUAL',
            job_root=frame['child_root'],job_id='4521411',slurm_terminal=terminal,supervisor=supervisor_ref),
            'Original storage closure must be reused verbatim')
        require(not (management/'ROOT_LONG_SEGMENT_CLOSURE.json').exists()
            and not (management/'ROOT_LEDGER_SEAL.json').exists(),'Repair already partially exists; never automatic replay')
        child=Path(frame['child_root'])
        require(not (child/'member_result.json').exists() and not list(child.glob('checkpoint_u*')),
            'Failed model progress or checkpoint cannot be adopted')
        _,adapter=import_runtime(frame['runtime_contract']['path'],metadata_only=True);storage,_=adapter.load_runtime()
        configuration=read_ref(frame['configuration']);principal=frame['principal']
        before=inspect_ledger(storage,args.phase,configuration,principal)
        require(len(before['rows'])==9,'Repair requires exact already committed9 intents')
        expected_counts=dict(root_seen=5,launch_attempts=1,observation=1,failed_attempts=1,segment_terminal=1)
        require(dict(Counter(row['kind'] for row in before['rows']))==expected_counts,'Original lifetime counts changed')
        fail_row,terminal_row=before['rows'][7:9]
        require(fail_row==dict(kind='failed_attempts',identity=frame['child_root'],body=dict(Root_closure=closure))
            and terminal_row==dict(kind='segment_terminal',identity=frame['child_root'],
                body=dict(Root_closure=closure,bytes_preserved=3435797,scientific_acceptance=False)),
            'Exact original failed and terminal intents required')
        original_indices=[binding(args.phase/'ledger/index'/f'{number:012d}.json') for number in range(1,10)]
        require(all(Path(read_ref(value)['record_ref']['path']).exists() for value in original_indices),
            'All original indexed records must actually be materialized')
        census,command=compute_census(args.phase,submission_path,frame)
        require(census['whole_job_bytes']+(1<<20)<=OUTER
            and census['static_management_bytes']+(1<<20)<=16<<20,'Repair receipts need original reserve')
        seal=write(management/'ROOT_LEDGER_SEAL.json',dict(schema='native_S_long_actual_ledger_seal_v1',
            status='FAILED_PREVIOUSLY_SEALED_METADATA_RECONCILED',actual_terminal=terminal,
            storage_closure=closure,ledger_result=binding(read_ref(original_indices[8])['record_ref']['path']),
            original_failed_and_terminal_index_refs=original_indices[7:9],original_index_chain=original_indices,
            actual_global_registered_bytes=before['total'],additional_directory_inode_bytes=before['parent_bytes'],
            global_cap_bytes=policy()['durable_bytes'],current_whole_job_budget_census=census,
            actual_same_host_census=command,operational_repair_source=binding(__file__),operational_manifest=manifest,
            host_identity_evidence=binding(N/'Native_S_1411_host_clock_and_inode_actual_v2.json'),
            seal_segment_called=False,counters_appended=0,original_failure='Quota feed stale or future',
            rejected_original_feed_was_saved=False,stale_versus_future='UNDETERMINED',
            all_originals_retained=True,scientific_acceptance=False))
        execution=write(management/'Root_seal_execution_v4.json',dict(schema='native_S_partial_seal_repair_v1',
            status='PREVIOUS_FAILED_SEAL_REUSED_NO_LIFECYCLE_REPLAY',seal=seal,same_host_census=command,
            not_a_new_model_job=True,actual_original_terminal=terminal))
        result=write(management/'ROOT_LONG_SEGMENT_CLOSURE.json',dict(schema='native_S_long_segment_Root_closure_v1',
            status='FAILED_OR_STORAGE_HOLD',submission=submission,actual_terminal=terminal,supervisor=supervisor_ref,
            optimizer_updates=0,checkpoint_directory=None,member_result=None,storage_seal=execution,
            failure=dict(actual_Slurm_state='FAILED',actual_Slurm_exit='1:0',process_private_closed=True,
                infrastructure_failure='Quota feed stale or future; exact refused feed was not retained',
                partial_seal_metadata_reconciled=True),scientific_acceptance=False,D5_authority=False,
            native_full_SDK_readback_and_four_curve_numeric_gates='REQUIRED_BEFORE_B_ACCEPTANCE'))
        after=inspect_ledger(storage,args.phase,configuration,principal)
        require(before['rows']==after['rows'] and original_indices==
            [binding(args.phase/'ledger/index'/f'{number:012d}.json') for number in range(1,10)],
            'Repair must not change lifetime records or counts')
        with root_phase.registry_lock(frame['registry']):
            registry=root_phase.registry_value(frame['registry']);own=registry['reservations'][read_ref(principal)['reservation_id']]
            require(own['principal']==principal,'Registered original principal differs')
            own['remaining_bytes']=max(0,policy()['durable_bytes']-after['total']-after['parent_bytes'])
            own['latest_actual_Root_seal']=seal;replace_feed(frame['registry'],registry)
        print(json.dumps(dict(status='FAILED1411_METADATA_RECONCILED_NO_MODEL_ACCEPTANCE',closure=result,
            ledger_counts_unchanged=expected_counts,remaining_reserved_bytes=own['remaining_bytes'],
            next_same_science_retry_starts_at_update=0,scientific_acceptance=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
