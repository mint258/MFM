#!/usr/bin/env python3
"""Root-only stdlib assembly after source review and actual method publication. No payload reads."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

HERE=Path(__file__).absolute().parent
B=Path('/share/home/zixiao/descriptor_analysis')
N=B/'runs/model_v3_20261026'
OLD=N/'projection_fp32_e2e_v1_source'
STATIC=('passive_capture.py','run_passive_trace.py','prepare_metadata.py','launch_passive_trace_GPU_v1.py',
        'run_passive_trace_GPU_v1.sbatch','PROTOCOL_README.md','inputs_DRAFT.json','dependencies.json')

def need(ok,message):
    if not ok: raise ValueError(message)

def ref(path):
    path=Path(path).absolute()
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=2<<20,'Ordinary source/small metadata required')
    raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def bound(leaf):
    need(ref(leaf['path'])==leaf,'Raw source/metadata changed: '+leaf['path'])
    return json.loads(Path(leaf['path']).read_bytes())

def save(path,value):
    raw=(json.dumps(value,sort_keys=True,allow_nan=False,indent=2)+'\n').encode()
    need(len(raw)<=2<<20,'Final metadata exceeds2MiB')
    with Path(path).open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method-publication',type=Path,required=True)
    parser.add_argument('--method-publication-sha256',required=True)
    parser.add_argument('--published-prefix',default='docs/model_v3/pre_registered_methods/projection_passive_stage_trace_v3/')
    args=parser.parse_args()
    need(not (HERE/'execution_request_v1.json').exists() and not (HERE/'source_pins_v1.json').exists(),
         'Fresh final metadata only; preserve all old attempts')
    draft=json.loads((HERE/'inputs_DRAFT.json').read_bytes())
    deps=json.loads((HERE/'dependencies.json').read_bytes())
    original=bound(draft['projection_request'])
    oldpins=bound(draft['projection_source_pins'])
    baseline=bound(draft['baseline4550_result'])
    supervisor=bound(draft['baseline4550_supervisor'])
    need(baseline['schema']=='model_v3_projection_FP32_complete48_GPU_result_v1'
         and baseline['status']=='PHYSICAL_CRITERION_FAIL' and baseline['failure'] is None
         and baseline['counts']==dict(tests=48,failures=36,errors=0,skipped=0)
         and baseline['source_before_after_equal'] is True
         and baseline['ordinary_all_arithmetic_FP32_encoder_forwards']==192
         and baseline['actual_projection_helper_calls']==2304,'Actual complete4550 result required')
    need(supervisor['status']=='FAILED' and supervisor['exit_code']==1
         and supervisor['first_failure']==dict(phase='child_exit',exit_code=1)
         and supervisor['remaining_recorded_processes_before_retirement']==[]
         and supervisor['private_storage_cleanup_errors']==[], '4550 physical failure/engineering cleanup differs')
    need(original['local_commit']=='f4652e940823141ac376eba5b6b1195f700fa692'
         and original['public_commit']=='b2c4c6772d751ba08ac611cbe563ee2e1b40e709'
         and original['exact_shared_tree']=='411ebc59652f8aecf2d06938842aeca4782a184d','Original immutable projection candidate only')
    authority=bound(original['original_capture_manifest'])
    need(authority['job_id']=='4521492' and authority['status']=='CAPTURE_COMPLETE','Original1492 parameter authority required')
    oldcases={row['case_id']:row for row in authority['cases']}
    need([row['case_id'] for row in baseline['cases']]==original['expected_case_ids']
         and len(oldcases)==48,'Exact full48 baseline and seeded authority population required')
    refs={}
    def add(leaf):
        need(set(leaf)=={'path','bytes','sha256'},'Rawref3 required')
        need(leaf['path'] not in refs or refs[leaf['path']]==leaf,'Conflicting input identity')
        refs[leaf['path']]=leaf
    for leaf in original['source_refs']+oldpins['files']+oldpins['protected_dependencies']+deps['direct_dependencies']:
        add(leaf)
    for leaf in [draft[k] for k in ('projection_request','projection_source_pins','baseline4550_result','baseline4550_supervisor')]:
        add(leaf)
    add(original['original_capture_manifest'])
    parameters={}
    for row in baseline['cases']:
        case_id=row['case_id']
        saved=bound(row['case_json'])
        measured=saved['measured']
        need(saved['schema']=='model_v3_projection_FP32_complete48_case_v1' and measured['case_id']==case_id
             and measured['complete_terminal_count']==13 and row['passed']==measured['passed']
             and measured['actual_terminal_output_artifact']==row['actual_terminal_output_artifact']
             and measured['encoder_configuration']['backbone_config']['attention_projection_mode']
                 ==original['attention_projection_mode'],'Actual4550 case identity/config differs')
        need(len(row['actual_terminal_output_artifact']['arrays'])==52
             and row['actual_terminal_output_artifact']['bytes']<=512<<10
             and row['actual_terminal_output_artifact']['numeric_bytes']<=320<<10,'All52 bounded F32 terminals required')
        source=oldcases[case_id]['capture_case'];captured=bound(source)
        need(captured['case_id']==case_id,'1492 case identity differs')
        parameters[case_id]=captured['original_measurement']['weight_summary']['all_named_parameter_sha256']
        need(parameters[case_id]==measured['weight_summary']['all_named_parameter_sha256']
             ==saved['construction']['actual_parameter_sha256'],'Original1492/4550 parameter identity differs')
        add(row['case_json']);add(source)
    pubref=ref(args.method_publication)
    need(pubref['sha256']==args.method_publication_sha256,'Actual method publication rawSHA required')
    publication=bound(pubref)
    need(publication['schema']=='model_v3_exact_tree_publication_actual_v1' and publication['branch']=='model-v3'
         and publication['repository_full_name']=='mint258/MFM'
         and publication['public_branch_readback_verified'] is True
         and publication['public_Git_API_tree_readback_verified'] is True,'Actual Root public readbacks required')
    published={leaf['path']:leaf for leaf in publication['files']}
    prefix=args.published_prefix.rstrip('/')+'/'
    method_files=[]
    for name in STATIC:
        current=ref(HERE/name);raw=Path(current['path']).read_bytes()
        blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+bytes([0])+raw).hexdigest()
        item=published[prefix+name]
        need(item['type']=='blob' and item['sha']==blob,'Method current raw bytes do not match actual published blob: '+name)
        method_files.append(dict(runtime_path=current['path'],bytes=current['bytes'],sha256=current['sha256'],
            repository_relative_path=prefix+name,git_blob_sha=blob))
        add(current)
    add(pubref)
    # Stat every selected file, including original terminal NPZ, without opening NPZ at assembly.
    selected=list(refs.values())+[{k:row['actual_terminal_output_artifact'][k] for k in ('path','bytes','sha256')}
                                 for row in baseline['cases']]
    physical={}
    for leaf in selected:
        path=Path(leaf['path']);st=path.stat()
        need(path.is_file() and not path.is_symlink() and st.st_size==leaf['bytes'],'Selected source/control/payload stat differs')
        identity=(st.st_dev,st.st_ino)
        need(identity not in physical or physical[identity]==st.st_size,'Conflicting selected physical input')
        physical[identity]=st.st_size
    # Reserve8MiB for final request, pins and bounded launch/public/control receipts. Final driver rechecks actual sum.
    need(sum(physical.values())+(8<<20)<=128<<20,'All selected inputs plus reserved metadata exceed128MiB')
    request=deepcopy(original)
    request.pop('test_file',None)
    request.update(schema='model_v3_projection_passive_stage_trace_GPU_request_v1',
        status='FINAL_BOUND_PUBLIC_PASSIVE_TRACE_REQUEST',diagnostic_entry=str(HERE/'run_passive_trace.py'),
        projection_request=draft['projection_request'],baseline4550_result=draft['baseline4550_result'],
        baseline4550_supervisor=draft['baseline4550_supervisor'],baseline_cases=baseline['cases'],
        original1492_parameter_sha256=parameters,encoder_reference_source=draft['encoder_reference_source'],
        local_observer_source=draft['local_observer_source'],trace_cap_bytes=512<<20,trace_role_cap_bytes=4<<20,
        selected_input_stat_bytes=sum(physical.values()),selected_input_cap_bytes=128<<20,
        input_metadata_reserve_bytes=8<<20,full_FP64_encoder_forwards=0,
        trace_method_publication=pubref,trace_method_files=method_files,source_refs=list(refs.values()),
        scientific_acceptance=False,prior_hidden_H0_from4550_available=False,
        no_new_encoder_baseline=True,no_model_backend_policy_mutation=True)
    save(HERE/'execution_request_v1.json',request)
    pins=dict(schema='model_v3_projection_passive_stage_trace_GPU_launch_source_pins_v1',
        files=[ref(HERE/name) for name in STATIC],protected_dependencies=list(refs.values()),
        execution_request=ref(HERE/'execution_request_v1.json'),
        inherited_projection_source_pins=draft['projection_source_pins'],not_GPU_execution_or_acceptance=True)
    save(HERE/'source_pins_v1.json',pins)
    print(json.dumps(dict(execution_request=ref(HERE/'execution_request_v1.json'),
                         source_pins=ref(HERE/'source_pins_v1.json'),NPZ_payload_opened=False,
                         no_GPU_execution_or_scientific_acceptance=True)))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
