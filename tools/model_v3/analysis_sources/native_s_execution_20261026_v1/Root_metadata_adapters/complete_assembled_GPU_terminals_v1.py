"""Add actual supervisor references to new GPU terminal projections; preserve originals."""
import json,sys
from pathlib import Path
N=Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026')
sys.path.insert(0,str(N/'native_s_precision_long_run_v3'))
from long_common import binding,read_ref,read,write,require,require_C0,root_identity,RUNTIME
root_identity()
phase=N/'native_S_B20k_v3';folder=phase/'control/readiness_assembly'
original=binding(folder/'native_S_profile.json');profile=read_ref(original)
require(profile['schema']=='model_v3_Root_existing_native_S_profile_v2','Original full assembly required')
source=binding(RUNTIME/'tools/model_v3/run_supervised.py')
for precision,row in profile['measurements'].items():
    old_ref=row['actual_terminal'];terminal=read_ref(old_ref)
    require_C0(read_ref(terminal['raw_sacct']),terminal['job_id'])
    sdk=read_ref(row['native_SDK_verification']);inputs=read_ref(sdk['execution']['inputs'])
    closure_ref=inputs['Root_profile_closure'];closure=read_ref(closure_ref)
    require(closure['actual_terminal']==old_ref and closure['status']=='PROFILE_OUTER_C0_SCIENCE_HOLD','Original profile/root terminal chain differs')
    supervisor=read_ref(closure['supervisor'])
    require(str(supervisor['job_id'])==str(terminal['job_id']) and supervisor['status']=='COMPLETED'
        and supervisor['exit_code']==0 and supervisor['first_failure'] is None
        and supervisor['remaining_recorded_processes_before_retirement']==[] and supervisor['private_storage_cleanup_errors']==[]
        and supervisor['supervisor_source_sha256']==source['sha256'],'Actual original supervisor/source/process/private closure differs')
    row['actual_terminal']=write(folder/(precision+'_GPU_terminal_complete_v1.json'),dict(**terminal,
        supervisor=closure['supervisor'],supervisor_source=source,original_actual_terminal=old_ref,
        original_Root_profile_closure=closure_ref,metadata_completion_source=binding(__file__),same_actual_GPU_parent=True))
profile['original_assembly']=original
profile['Root_terminal_metadata_completion_source']=binding(__file__)
result=write(folder/'native_S_profile_with_supervisors_v1.json',profile)
print(json.dumps(dict(status='RAW_ACTUAL_GPU_SUPERVISOR_REFERENCES_ADDED_IN_NEW_PROJECTIONS',profile=result,originals_unchanged=True)))