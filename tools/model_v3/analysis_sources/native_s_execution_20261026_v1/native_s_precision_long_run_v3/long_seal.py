"""Root actual-terminal sealer; unused global allowance stays held between jobs."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import os
from long_common import *


def main():
    root_identity();parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',type=Path,required=True);parser.add_argument('--submission',type=Path,required=True)
    parser.add_argument('--terminal',type=Path,required=True);args=parser.parse_args()
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','Root sealer hides CUDA')
    frame=read(args.submission);job=frame['actual_sbatch_job_id'];layout=slot_layout(args.phase,frame['slot'])
    management=layout['management'];terminal=binding(args.terminal);projection=read_ref(terminal)
    raw=read_ref(projection['raw_sacct']);state,code=terminal_rows(raw,job)
    require(projection['status']==state and projection['exit_code_raw']==code,'Actual terminal projection differs')
    _,adapter=import_runtime(frame['runtime_contract']['path']);storage,_=adapter.load_runtime()
    request=read(management/'request.json');configuration=read_ref(request['configuration'])
    supervisor=read(management/'supervisor.json')
    require(str(supervisor['job_id'])==job and supervisor['remaining_recorded_processes_before_retirement']==[]
        and supervisor['private_storage_cleanup_errors']==[],'Actual process/private closure missing')
    closure=write(management/'Root_storage_closure.json',dict(schema='model_v3_Root_storage_segment_closure_v1',
        authority='ROOT_ACTUAL',job_root=str(layout['child']),job_id=job,
        slurm_terminal=terminal,supervisor=binding(management/'supervisor.json')))
    ledger=adapter.ledger_class(storage)(request,configuration)
    result=ledger.seal_segment(job_root=layout['child'],Root_closure_ref=closure)
    global_bytes=ledger.census()
    # The disjoint registered output roots omit ancestor-directory inodes.
    # Count those actual metadata bytes explicitly rather than hide them.
    parents=[args.phase,args.phase/'slots',args.phase/'logs',args.phase/'lineages']
    parents += [slot_layout(args.phase,slot)['root'] for slot in range(1,109)]
    parent_bytes=sum(path.lstat().st_size for path in parents if path.exists())
    require(global_bytes+parent_bytes<=policy()['durable_bytes'],'Whole retained lineage plus directory overhead exceeds128GiB')
    import runtime_monitor,long_frames,root_phase
    baseline=read(management/'ledger_baseline.json');stdio=read(management/'actual_supervisor_launch.json')['stdio']
    current=long_frames.whole_census(args.phase,job,stdio,baseline,runtime_monitor)
    root=write(management/'ROOT_LEDGER_SEAL.json',dict(schema='native_S_long_actual_ledger_seal_v1',
        actual_terminal=terminal,storage_closure=closure,ledger_result=result,
        actual_global_registered_bytes=global_bytes,additional_directory_inode_bytes=parent_bytes,
        global_cap_bytes=policy()['durable_bytes'],current_whole_job_budget_census=current,
        all_originals_retained=True,scientific_acceptance=False))
    # Keep unused finite allowance reserved for the remaining members/segments.
    # This never resets prior profile entries or any other registered holds.
    principal=read_ref(frame['principal'])
    with root_phase.registry_lock(frame['registry']):
        registry=root_phase.registry_value(frame['registry'])
        own=registry['reservations'][principal['reservation_id']]
        require(own['principal']==frame['principal'],'Root registered principal changed')
        own['remaining_bytes']=max(0,policy()['durable_bytes']-global_bytes-parent_bytes)
        own['latest_actual_Root_seal']=root
        replace_feed(frame['registry'],registry)
    print(json.dumps(dict(status='ROOT_ACTUAL_SEGMENT_SEALED_GLOBAL_REMAINDER_HELD',seal=root,
        remaining_reserved_bytes=own['remaining_bytes'],scientific_acceptance=False)),flush=True)


if __name__=='__main__':main()
