#!/usr/bin/env python3
"""Root metadata preparation only. No Torch/NumPy, model, arrays, sbatch or network."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path

B=Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';HERE=Path(__file__).absolute().parent

def need(ok,message):
    if not ok:raise ValueError(message)
def ref(path):
    path=Path(path).absolute();need(path.is_file() and not path.is_symlink(),'Ordinary source/metadata required')
    raw=path.read_bytes();return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def bound(leaf):
    need(leaf['bytes']<=2*1024**2 and ref(leaf['path'])==leaf,'Bounded closed metadata changed')
    return json.loads(Path(leaf['path']).read_bytes())
def write(path,value):
    raw=(json.dumps(value,sort_keys=True,allow_nan=False,indent=2)+'\n').encode()
    need(len(raw)<=2*1024**2,'New control exceeds2MiB')
    with path.open('xb') as stream:
        stream.write(raw);stream.flush()
        import os
        os.fsync(stream.fileno())
    return ref(path)
def assemble():
    need(not (HERE/'execution_request_v1.json').exists() and not (HERE/'source_pins_v1.json').exists(),'Fresh bindings only')
    deps=json.loads((HERE/'DRAFT_DEPENDENCIES.json').read_bytes())
    inventory=json.loads((HERE/'DRAFT_SOURCE_INVENTORY.json').read_bytes())
    need(ref(HERE/'DRAFT_DEPENDENCIES.json')==inventory['dependency_inventory'],'Frozen dependency inventory changed')
    for leaf in inventory['files']+deps['files']:need(ref(leaf['path'])==leaf,'Reviewed source/metadata changed')
    root=bound(deps['Root1838']);manifest=bound(root['manifest'])
    need(root['schema']=='model_v3_centered_fixed_H0_capture_Root_metadata_closure_v1'
         and root['status']=='ACTUAL_GPU_C0_FULL48_EXTERNAL52_REPLAY_CLOSED_CPU_DIAGNOSTIC_ALLOWED'
         and manifest['job_id']=='4521838' and manifest['status']=='CAPTURE_COMPLETE'
         and root['case_count']==48 and root['encoder_forwards']==192 and root['source_before_after_equal'],
         'Actual current centered all48 baseline required')
    baseline_request=bound(manifest['request'])
    need(baseline_request['local_commit']=='cf8ce66d97cd518ebf279b40ee20294919bb95e1'
         and baseline_request['public_commit']=='f8417157dc23326d1beca8e19e4725755d9f13c6'
         and baseline_request['exact_shared_tree']=='2389ab046ee23f2ba92fcb61179d853dfdee8357',
         'Exact centered candidate source identity differs')
    cases={};terminals={};proofs=[deps['Root1838'],root['manifest'],manifest['request'],root['complete'],root['supervisor'],root['accounting']]
    for leaf in manifest['cases']:
        case=bound(leaf['capture_case']);identity=case['case_id']
        need(identity==leaf['case_id'] and case['same_forward_control'] and len(case['calls'])==4
             and case['original1492_parameter_sha256']==baseline_request['original1492_parameter_sha256'][identity],
             'Baseline case/seed/parameter binding differs')
        need(all(case['packed']['arrays'][call['keys']['H0']]['shape']==[44,512]
                 and case['packed']['arrays'][call['keys']['H0']]['dtype']=='<f4' for call in case['calls']),
             'All four baseline typed FP32 H0 headers required')
        terminal=case['original_measurement']['actual_terminal_output_artifact']
        need(len(terminal['arrays'])==52 and case['original_measurement']['complete_terminal_count']==13,
             'Original thirteen fields/four forwards required')
        path=Path(terminal['path']);need(path.is_file() and not path.is_symlink() and path.stat().st_size==terminal['bytes'],
             'Actual terminal stat differs; prepare does not hash/read NPZ')
        cases[identity]=leaf['capture_case'];terminals[identity]={k:terminal[k] for k in ('path','bytes','sha256')}
        proofs.append(leaf['capture_case'])
    need(list(cases)==baseline_request['expected_case_ids'] and len(cases)==48,'No selected cases permitted')
    request=deepcopy(baseline_request)
    request.update(schema='model_v3_encoder_local_op_GPU_request_v1',executable=str(HERE/'run_local_op_GPU.py'),
        baseline1838_case_refs=cases,baseline1838_terminal_refs=terminals,Root1838=deps['Root1838'],
        encoder_reference_source=deps['encoder_reference_source'],
        purpose='SAME_ACTUAL_INPUT_LOCAL_OPERATOR_DIAGNOSTIC_NOT_CANDIDATE',scientific_acceptance=False,
        full_FP64_encoder_forwards=0,original_encoder_forwards=192,
        local_reference_scope='INDEPENDENT_REAL_FORMULA_ALGORITHM_AND_FP64_NOT_DTYPE_ONLY',
        local_replay_mismatch='RETAIN_ALL48_THEN_HOLD',reference_outputs_injected=False)
    values=baseline_request['source_refs']+deps['files']+proofs
    sources={leaf['path']:leaf for leaf in values};need(all(sources[v['path']]==v for v in values),'Conflicting source refs')
    request['source_refs']=list(sources.values())
    # Include inherited resource dependencies before publishing final source bindings.
    source_values=list(sources.values())+deps['inherited_protected_dependencies']
    identities={}
    for leaf in source_values+list(terminals.values()):
        path=Path(leaf['path']);st=path.stat()
        need(path.is_file() and not path.is_symlink() and st.st_size==leaf['bytes'],'Input source/terminal stat differs')
        identities[(st.st_dev,st.st_ino)]=st.st_size
    need(sum(identities.values())<=128*1024**2,'Selected inputs exceed128MiB; no waiver')
    request_ref=write(HERE/'execution_request_v1.json',request)
    own=[ref(path) for path in sorted(HERE.iterdir()) if path.is_file() and path.name!='source_pins_v1.json']
    pins={'schema':'model_v3_encoder_local_op_GPU_launch_source_pins_v1',
        'status':'SOURCE_BOUND_NO_NEW_PUBLICATION_OR_EXECUTION_CLAIM','execution_request':request_ref,'files':own,
        'protected_dependencies':deps['files']+deps['inherited_protected_dependencies'],
        'original192_FP32_encoder_forwards':True,'FP64_encoder_forwards':0,'scientific_adoption':False}
    pins_ref=write(HERE/'source_pins_v1.json',pins)
    for leaf in own+[pins_ref]:
        st=Path(leaf['path']).stat();identities[(st.st_dev,st.st_ino)]=st.st_size
    need(sum(identities.values())<=128*1024**2,'Complete new bindings+selected inputs exceed128MiB')
    return {'request':request_ref,'source_pins':pins_ref,'selected_input_stat_bytes':sum(identities.values()),
            'input_cap_bytes':128*1024**2,'NPZ_read':False,'new_execution_claimed':False}
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--assemble',action='store_true',required=True)
    parser.parse_args();print(json.dumps(assemble(),sort_keys=True))