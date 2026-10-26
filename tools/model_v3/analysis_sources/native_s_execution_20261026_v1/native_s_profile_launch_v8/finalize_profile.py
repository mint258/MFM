"""Root-only actual terminal/process/storage sealing and closed current census."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
from common import *
sys.dont_write_bytecode=True

def main():
    root_identity();p=argparse.ArgumentParser();p.add_argument('--phase',type=Path,required=True)
    p.add_argument('--terminal',type=Path,required=True);a=p.parse_args()
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','Root closure requires fresh CPU-hidden metadata process')
    frame=read(a.phase/'control/submission.json');job=frame['actual_sbatch_job_id'];management=a.phase/f'job_{job}'/'management'
    import runtime_origin
    contract=runtime_origin.read_contract(frame['candidate_contract']['path'],allow_candidate_profile=True)
    runtime_origin.configure_paths(contract)
    import native_s_storage,operational,runtime_monitor
    storage,_=native_s_storage.load_runtime(allow_candidate_profile=True)
    request=read(management/'request.json');configuration=read_ref(request['configuration'])
    terminal=read(a.terminal);raw=read_ref(terminal['raw_sacct']);state,code=terminal_rows(raw,job)
    exit_status,signal=map(int,code.split(':'));effective_exit=exit_status if signal==0 else 128+signal
    require(terminal['status']==state and terminal['exit_code']==effective_exit,'Terminal projection differs from actual raw accounting')
    supervisor=read(management/'supervisor.json')
    require(str(supervisor['job_id'])==job and supervisor['remaining_recorded_processes_before_retirement']==[]
        and supervisor['private_storage_cleanup_errors']==[],'Owned processes/private storage not closed')
    closure=write(management/'Root_storage_closure.json',dict(schema='model_v3_Root_storage_segment_closure_v1',
        authority='ROOT_ACTUAL',job_root=str(a.phase/f'job_{job}'/'child'),job_id=job,
        slurm_terminal=binding(a.terminal),supervisor=binding(management/'supervisor.json')))
    ledger=native_s_storage.ledger_class(storage)(request,configuration)
    result=ledger.seal_segment(job_root=a.phase/f'job_{job}'/'child',Root_closure_ref=closure)
    parent=read(management/'actual_supervisor_launch.json')['actual_parent_process']
    census=operational.whole_census(a.phase,job,parent['stdio'],runtime_monitor)
    require(census['whole_bytes']<=OUTER-(1<<20),'Root closure lacks original finalization margin')
    write(management/'ROOT_LEDGER_SEAL.json',dict(schema='native_S_actual_profile_ledger_seal_v1',
        actual_terminal=binding(a.terminal),closure=closure,ledger_result=result,current_whole_census=census,
        final_census_semantics='current_after_SDK_and_supervisor_exit_before_small_Root_seal_receipt',
        scientific_acceptance=False,production_20k_allowed=False))
    # Exact closed-size bound after our final receipt; separate stdout remains
    # an explicit sampled file until Slurm closes it. Never call this a peak.
    final=operational.whole_census(a.phase,job,parent['stdio'],runtime_monitor)
    print(json.dumps(dict(status='ROOT_SEALED_RETAINED_ALL_ORIGINALS',current_census=final,
        production_20k_allowed=False)),flush=True)

if __name__=='__main__':main()
