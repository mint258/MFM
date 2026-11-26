"""Future-only physical estimate after actual metadata vfork/exec tracing."""
from fullft_ram_envelope_20261127 import GiB
import subprocess
import sys
from pathlib import Path
from storage_20261122 import CONTROL as C

SCHEMA='S_FUTURE_FULLFT_PHYSICAL_RAM_20261127_V2'
PROOF=C/'fullft_physical_ram_20261127.json'


def require_physical_proof():
    from fullft_ram_envelope_20261127 import read
    proof=read(PROOF);parent=read(proof['native_record'])
    command=read(Path(proof['native_record']).with_name('command_exit.json'))
    if (proof.get('schema')!=SCHEMA or proof.get('status')!='PHYSICAL_RESOURCE_ESTIMATE_READY'
            or proof.get('new_tests')!=2 or not proof.get('real_metadata_spawn_trace')
            or proof.get('future_peak_ram_bytes')!=8*GiB
            or proof['estimate']['estimated_physical_host_peak_bytes']>8*GiB
            or parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
            or command.get('exit_code')!=0 or not parent.get('owned_descendants_exited')
            or not parent.get('observer_joined')):
        raise ValueError('Actual same-interpreter vfork/metadata estimate must close first')
    return proof


def validate_physical_contract(c):
    proof=require_physical_proof()
    if (c.get('host_ram_envelope_source')!=str(PROOF)
            or c.get('host_ram_runtime_python')!=proof['python'] or sys.executable!=proof['python']
            or not getattr(subprocess,'_USE_VFORK',False)
            or c['providers_sha256']!=proof['providers_sha256']):
        raise ValueError('8GiB requires the actually traced interpreter/provider/contract')


def estimate_physical(main_peak,metadata_peak,*,verified_shared_address_spawn):
    if not verified_shared_address_spawn or not 0<metadata_peak<=256*1024**2 or main_peak<=0:
        raise ValueError('Unknown spawn/metadata footprint cannot receive the smaller envelope')
    return dict(observed_main_peak_bytes=main_peak,observed_metadata_peak_bytes=metadata_peak,
        per_metadata_family_allowance_bytes=256*1024**2,concurrent_metadata_families=2,
        additional_wrapper_and_transient_allowance_bytes=GiB,
        estimated_physical_host_peak_bytes=main_peak+2*256*1024**2+GiB,
        measured_whole_tree_peak=False,pretraining_reservations_changed=False,
        basis='Actual same-interpreter metadata vfork/exec shares parent address space until exec; no full parent copies charged as additional physical RAM')
