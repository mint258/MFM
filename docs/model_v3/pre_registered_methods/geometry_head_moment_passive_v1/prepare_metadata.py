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
OLD=N/'geometry_fp32_e2e_v1_source'
STATIC=('head_ports.py','passive_capture.py','run_head_moment_trace.py','prepare_metadata.py','launch_passive_trace_GPU_v1.py',
        'run_passive_trace_GPU_v1.sbatch','PROTOCOL_README.md','inputs_DRAFT.json','dependencies.json','PLAN.md')

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
    parser.add_argument('--published-prefix',default='docs/model_v3/pre_registered_methods/geometry_head_moment_passive_v1/')
    args=parser.parse_args()
    need(not (HERE/'execution_request_v1.json').exists() and not (HERE/'source_pins_v1.json').exists(),
         'Fresh final metadata only; preserve all old attempts')
    draft=json.loads((HERE/'inputs_DRAFT.json').read_bytes())
    deps=json.loads((HERE/'dependencies.json').read_bytes())
    need(draft['schema']=='model_v3_geometry_head_moment_passive_inputs_DRAFT_v1'
         and deps['schema']=='model_v3_geometry_head_moment_passive_dependencies_DRAFT_v1', 'Specific frozen input/dependency scope required')
    original=bound(draft['geometry_request'])
    oldpins=bound(draft['geometry_source_pins'])
    baseline=bound(draft['baseline4579_result'])
    supervisor=bound(draft['baseline4579_supervisor'])
    need(baseline['schema']=='model_v3_geometry_FP32_complete48_GPU_result_v1'
         and baseline['status']=='PHYSICAL_CRITERION_FAIL' and baseline['failure'] is None
         and baseline['counts']==dict(tests=48,failures=33,errors=0,skipped=0)
         and baseline['source_before_after_equal'] is True
         and baseline['ordinary_all_arithmetic_FP32_encoder_forwards']==192
         and baseline['actual_projection_helper_calls']==2304
         and baseline['actual_geometry_helper_calls']==512
         and baseline['geometry_mode']=='residual_expansion_fp32_v1','Actual complete4579 result required')
    need(supervisor['status']=='FAILED' and supervisor['exit_code']==1
         and supervisor['first_failure']==dict(phase='child_exit',exit_code=1)
         and supervisor['remaining_recorded_processes_before_retirement']==[]
         and supervisor['private_storage_cleanup_errors']==[], '4579 physical failure/engineering cleanup differs')
    need(original['local_commit']=='03e26bea6a29ef96ba5611760763329207212741'
         and original['public_commit']=='498ecbe7e88b1468067dde5692c10735fcadf2ea'
         and original['exact_shared_tree']=='2d3b8f17e06d73bc2bc47745ccde982625646dd0','Original immutable residual-geometry candidate only')
    closure=bound(draft['baseline4579_Root_closure'])
    need(closure['schema']=='model_v3_Root_complete48_geometry_FP32_scientific_failure_closure_v1'
         and closure['status']=='ACTUAL_COMPLETE48_GEOMETRY_FP32_SCIENTIFIC_CRITERION_FAIL_15_PASS_33_FAIL_SOURCE_RESOURCE_CLOSED'
         and closure['job_id']=='4524579' and closure['result']==draft['baseline4579_result']
         and closure['request']==draft['geometry_request'] and closure['source_pins']==draft['geometry_source_pins']
         and closure['supervisor']==draft['baseline4579_supervisor']
         and closure['counts']==baseline['counts'] and closure['all_sources_before_after_current_equal'] is True
         and closure['private_cleanup_and_recorded_processes_closed'] is True
         and closure['formal_FP32_gate_satisfied'] is False and closure['scientific_adoption'] is False,
         'Actual Root negative science/source/resource closure must remain FAILED, not be promoted to C0')
    raw=closure['actual_sacct']
    need(raw['argv']==['sacct','-X','-n','-P','-j','4524579',
          '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
         and type(raw['returncode']) is int and raw['returncode']==0 and raw['stderr']==''
         and raw['stdout'].strip()=='4524579|zixiao|FAILED|1:0|64|16|compute-0-21',
         'Actual owned FAILED1 scientific parent evidence differs')
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
    for leaf in [draft[k] for k in ('geometry_request','geometry_source_pins','baseline4579_result','baseline4579_supervisor','baseline4579_Root_closure')]:
        add(leaf)
    add(original['original_capture_manifest'])
    parameters={}
    for row in baseline['cases']:
        case_id=row['case_id']
        saved=bound(row['case_json'])
        measured=saved['measured']
        need(saved['schema']=='model_v3_geometry_FP32_complete48_case_v1' and measured['case_id']==case_id
             and measured['complete_terminal_count']==13 and row['passed']==measured['passed']
             and measured['actual_terminal_output_artifact']==row['actual_terminal_output_artifact']
             and measured['encoder_configuration']['backbone_config']['attention_projection_mode']
                 ==original['attention_projection_mode'],'Actual4579 case identity/config differs')
        need(len(row['actual_terminal_output_artifact']['arrays'])==52
             and row['actual_terminal_output_artifact']['bytes']<=512<<10
             and row['actual_terminal_output_artifact']['numeric_bytes']<=320<<10,'All52 bounded F32 terminals required')
        source=oldcases[case_id]['capture_case'];captured=bound(source)
        need(captured['case_id']==case_id,'1492 case identity differs')
        parameters[case_id]=captured['original_measurement']['weight_summary']['all_named_parameter_sha256']
        need(parameters[case_id]==measured['weight_summary']['all_named_parameter_sha256']
             ==saved['construction']['actual_parameter_sha256'],'Original1492/4579 parameter identity differs')
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
    request.update(schema='model_v3_geometry_head_moment_passive_GPU_request_v1',
        status='FINAL_BOUND_PUBLIC_GEOMETRY_HEAD_MOMENT_TRACE_REQUEST',diagnostic_entry=str(HERE/'run_head_moment_trace.py'),
        geometry_request=draft['geometry_request'],baseline4579_result=draft['baseline4579_result'],
        baseline4579_Root_closure=draft['baseline4579_Root_closure'],
        baseline4579_supervisor=draft['baseline4579_supervisor'],baseline_cases=baseline['cases'],
        original1492_parameter_sha256=parameters,encoder_reference_source=draft['encoder_reference_source'],
        local_observer_source=draft['local_observer_source'],trace_cap_bytes=512<<20,trace_role_cap_bytes=4<<20,
        selected_input_stat_bytes=sum(physical.values()),selected_input_cap_bytes=128<<20,
        input_metadata_reserve_bytes=8<<20,full_FP64_encoder_forwards=0,
        trace_method_publication=pubref,trace_method_files=method_files,source_refs=list(refs.values()),
        scientific_acceptance=False,prior_hidden_H0_from4579_available=False,
        no_new_encoder_baseline=True,no_model_backend_policy_mutation=True,
        expected_head_observations=384,expected_magnitude_norm_observations=192,
        expected_parameter_subset_bytes=48*263176,
        trace_contains_parameter_weights=True,
        parameter_scope='Seeded synthetic two independent charges-MLP subsets; role0 once per case only')
    save(HERE/'execution_request_v1.json',request)
    pins=dict(schema='model_v3_geometry_head_moment_passive_GPU_launch_source_pins_v1',
        files=[ref(HERE/name) for name in STATIC],protected_dependencies=list(refs.values()),
        execution_request=ref(HERE/'execution_request_v1.json'),
        inherited_geometry_source_pins=draft['geometry_source_pins'],not_GPU_execution_or_acceptance=True)
    save(HERE/'source_pins_v1.json',pins)
    print(json.dumps(dict(execution_request=ref(HERE/'execution_request_v1.json'),
                         source_pins=ref(HERE/'source_pins_v1.json'),NPZ_payload_opened=False,
                         no_GPU_execution_or_scientific_acceptance=True)))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
