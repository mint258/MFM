"""Conservative future-only host-RAM envelope, not a measured tree peak.

The pinned full-FT provider fits inline with CPU threads, not reader workers.
At most one foreground metadata query and one observer guard can concurrently
fork from the fitting process. Sum the parent and two full-size copies, then
add1GiB for executed small guard/query descendants and wrapper overhead. RSS
double-counts shared pages, deliberately retaining that conservative bound.
Pretraining reservations and all scientific settings are outside this policy.
"""
import json
from pathlib import Path
from storage_20261122 import CONTROL as C

GiB=1024**3
SCHEMA='S_FUTURE_FULLFT_RAM_ENVELOPE_20261127_V1'
PROOF=C/'fullft_ram_envelope_20261127.json'
read=lambda path:json.loads(Path(path).read_text())


def estimate(main_peak,child_peak):
    if min(main_peak,child_peak)<=0:raise ValueError('Completed observed process peaks required')
    copy=max(main_peak,child_peak)
    return dict(main_peak_bytes=main_peak,child_peak_bytes=child_peak,
        estimated_parent_plus_two_full_size_forks_bytes=3*copy,
        nested_metadata_and_wrapper_allowance_bytes=GiB,
        estimated_concurrent_host_peak_bytes=3*copy+GiB,
        measured_whole_process_tree_peak=False,pretraining_reservations_changed=False)


def require_closed_proof():
    proof=read(PROOF)
    parent=read(proof['native_record'])
    command=read(Path(proof['native_record']).with_name('command_exit.json'))
    if (proof.get('schema')!=SCHEMA or proof.get('status')!='RESOURCE_ESTIMATE_READY'
            or proof.get('new_tests')!=2
            or proof.get('observed_complete_fits')!=24 or proof.get('future_peak_ram_bytes')!=16*GiB
            or proof['estimate']['estimated_concurrent_host_peak_bytes']>16*GiB
            or parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
            or command.get('exit_code')!=0 or not parent.get('owned_descendants_exited')
            or not parent.get('observer_joined')):
        raise ValueError('A genuine completed all-four-task resource estimate is required')
    return proof


def future_ram(ledger,provider_pins,*,python=None):
    """Opt in only after root activates a closed estimate at a natural boundary."""
    state=read(C/'current_state.json')
    from fullft_physical_ram_20261127 import SCHEMA as PHYSICAL_SCHEMA,PROOF as PHYSICAL_PROOF
    if state.get('future_fullft_ram_policy') not in (SCHEMA,PHYSICAL_SCHEMA):return 64*GiB,None
    proof=require_closed_proof()
    if proof['providers_sha256']!=provider_pins:raise ValueError('Scientific provider topology changed')
    main=proof['estimate']['main_peak_bytes'];child=proof['estimate']['child_peak_bytes']
    for row in ledger['statistics'].values():
        if row.get('mode') not in ('finetune','finetune_native') or not row.get('resource_closed'):continue
        for path in {row['lifecycle_record'],row.get('native_lifecycle_record') or row['lifecycle_record']}:
            record=read(path)
            if record.get('exit_code') not in (0,75) or not record.get('owned_descendants_exited'):continue
            main=max(main,record.get('peak_RSS_bytes',0));child=max(child,record.get('child_peak_RSS_bytes',0))
    # Higher subsequent observations may increase future reservations, never
    # lower an active one. A refused next admission simply returns to root.
    if state.get('future_fullft_ram_policy')==PHYSICAL_SCHEMA:
        from fullft_physical_ram_20261127 import require_physical_proof,estimate_physical
        physical=require_physical_proof()
        if physical['providers_sha256']!=provider_pins:raise ValueError('Provider changed after physical estimate')
        if python==physical['python']:
            bound=estimate_physical(main,physical['estimate']['observed_metadata_peak_bytes'],
                verified_shared_address_spawn=True)
            if bound['estimated_physical_host_peak_bytes']<=8*GiB:return 8*GiB,str(PHYSICAL_PROOF)
    ram=16*GiB if estimate(main,child)['estimated_concurrent_host_peak_bytes']<=16*GiB else 64*GiB
    return ram,str(PROOF) if ram==16*GiB else None


def validate_memory_contract(c):
    if c.get('peak_ram_bytes')==64*GiB:return
    if c.get('peak_ram_bytes')==8*GiB:
        from fullft_physical_ram_20261127 import validate_physical_contract
        validate_physical_contract(c)
        return
    if c.get('peak_ram_bytes')!=16*GiB or c.get('host_ram_envelope_source')!=str(PROOF):
        raise ValueError('Only legacy64GiB or explicitly estimated future16GiB fullFT')
    proof=require_closed_proof()
    if proof['providers_sha256']!=c['providers_sha256']:
        raise ValueError('Actual pinned fullFT provider differs from estimated topology')
