"""Frozen typed I/O reused for this one bounded local-op measurement."""
from pathlib import Path
import hashlib
import json
import importlib.util
import sys
HERE=Path(__file__).absolute().parent
B=Path('/share/home/zixiao/descriptor_analysis')
OLD=B/'runs/model_v3_20261026/centered_fixed_H0_diagnostic_v1_source'
def need(ok,message):
    if not ok:raise ValueError(message)
def load_file(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module
old=load_file(OLD/'diagnostic_common.py','_encoder_local_frozen_capture_IO')
FIELDS,INPUT_CAP,STATE_BYTES=old.FIELDS,old.INPUT_CAP,old.STATE_BYTES
InputBudget,bound,ref=old.InputBudget,old.bound,old.ref
require,save_plain=old.require,old.save_plain
state_arrays,tensor_state_identity=old.state_arrays,old.tensor_state_identity
load_npz,metadata_selfcheck,load_shadow=old.load_npz,old.metadata_selfcheck,old.load_shadow
verify_publication=old.verify_publication

def source_snapshot(request,pins_sha):
    pins=bound({**ref(HERE/'source_pins_v1.json'),'sha256':pins_sha})
    need(pins['schema']=='model_v3_encoder_local_op_GPU_launch_source_pins_v1','Dedicated local-op source required')
    values=request['source_refs']+pins['files']+pins['protected_dependencies']
    sources={leaf['path']:leaf for leaf in values};need(all(sources[v['path']]==v for v in values),'Conflicting source refs')
    sources[str(HERE/'source_pins_v1.json')]=ref(HERE/'source_pins_v1.json')
    verify_publication(request)
    selected=list(sources.values())+list(request['baseline1838_terminal_refs'].values())
    identities={}
    for leaf in selected:
        path=Path(leaf['path']);st=path.stat()
        need(path.is_file() and not path.is_symlink() and st.st_size==leaf['bytes'], 'Selected input stat differs')
        identity=(st.st_dev,st.st_ino)
        need(identity not in identities or identities[identity]==leaf['bytes'],'Conflicting physical input identity')
        identities[identity]=leaf['bytes']
    need(sum(identities.values())<=INPUT_CAP, 'All selected source/metadata/terminal input exceeds128MiB')
    for leaf in sources.values():need(ref(leaf['path'])==leaf,'Source drift: '+leaf['path'])
    return sources

def external_terminal_control(request,case_id,measured):
    import numpy as np
    saved=bound(request['baseline1838_case_refs'][case_id])['original_measurement']
    need(saved['case_id']==measured['case_id']==case_id and saved['case']==measured['case']
         and saved['encoder_configuration']==measured['encoder_configuration'],'Baseline1838 case/config differs')
    for key in ('registry_sha256','fixture_geometry_sha256','original_physical_geometry_sha256',
                'original_view_identity_sha256','encoder_forward_shapes','complete_terminal_count','weight_summary'):
        need(saved[key]==measured[key],'Baseline1838 complete fixture/state metadata differs: '+key)
    expected=saved['actual_terminal_output_artifact'];actual=measured['actual_terminal_output_artifact']
    need(len(expected['arrays'])==len(actual['arrays'])==52 and set(expected['arrays'])==set(actual['arrays']),
         'All52 external terminal arrays required')
    need(ref(expected['path'])=={key:expected[key] for key in ('path','bytes','sha256')},'Baseline1838 terminal raw digest changed')
    controls=[]
    with np.load(expected['path'],allow_pickle=False) as baseline,np.load(actual['path'],allow_pickle=False) as fresh:
        need(set(baseline.files)==set(fresh.files)==set(expected['arrays']),'Terminal keys differ')
        for key in baseline.files:
            a,b=baseline[key],fresh[key]
            need(a.dtype==b.dtype==np.float32 and a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all(),
                 'Terminal raw dtype/shape/finiteness differs')
            controls.append({'array':key,'bitwise_equal':a.tobytes()==b.tobytes()})
    return {'scope':'ALL52_ACTUAL1838_EXTERNAL_TERMINALS','reference':{k:expected[k] for k in ('path','bytes','sha256')},
        'arrays':controls,'baseline_physics_passed':saved['passed'],'new_physics_passed':measured['passed'],
        'passed':all(row['bitwise_equal'] for row in controls) and saved['passed']==measured['passed']}