"""Portable storage bridge only: original pickle bytes, never numerical recoding."""
import base64,copy,importlib,pickle,sys
from pathlib import Path
from .contract import canonical,sha,need,verify

STATE={}


def install_sources(deployment,*,initialize_science):
    names=('common','science','selection','statistics_tools','run_pilot','prepare')
    need(not any(name in sys.modules for name in names),'FRESH_UNAMBIGUOUS_ORIGINAL_MODULE_NAMESPACE_REQUIRED')
    rows=deployment['science_sources'];paths={row['basename']:Path(row['target_locator']['path']) for row in rows}
    need(set(paths)=={'common.py','science.py','selection.py','statistics_tools.py','run_pilot.py','sprime_v6.py','prepare.py'} and
         len({p.parent for p in paths.values()})==1,'EXACT_SEVEN_FLAT_ORIGINAL_SOURCES_REQUIRED')
    for row in rows:verify(row['target_locator'])
    sys.path.insert(0,str(next(iter(paths.values())).parent))
    common=importlib.import_module('common');runner=importlib.import_module('run_pilot')
    need(Path(common.__file__).absolute()==paths['common.py'] and Path(runner.__file__).absolute()==paths['run_pilot.py'],
         'ACTUAL_IMPORTED_ORIGINAL_SOURCE_PATH_REQUIRED')
    STATE.update(common=common,runner=runner,deployment=deployment)
    if initialize_science:
        science=importlib.import_module('science')
        need(Path(science.__file__).absolute()==paths['science.py'],'ACTUAL_ORIGINAL_SCIENCE_IMPORT_REQUIRED')
        science.worker_init(deployment['recipe_target_locator']['path'])
        core=science.SCIENCE
        need(Path(core.__file__).absolute()==paths['sprime_v6.py'],'ACTUAL_BYTE_IDENTICAL_CORE_IMPORT_REQUIRED')
        # The original I/O read() is replaced, all graph/stereo/RMSD/selection functions remain original.
        STATE.update(science=science,core=core)
        from .contract import load
        import platform,numpy,torch
        from importlib import metadata
        from rdkit import rdBase
        versions=load(deployment['environment_review_target_locator'])['expected_versions']
        actual={'python':platform.python_version(),'numpy':str(numpy.__version__),'torch':str(torch.__version__),
            'rdkit':str(rdBase.rdkitVersion),'torch_geometric':metadata.version('torch-geometric')}
        need(actual['python']==versions['python']=='3.11.14' and actual['numpy']==versions['numpy']=='2.2.6' and
             actual['rdkit']==versions['rdkit']=='2025.09.5' and actual['torch']==versions['torch']=='2.5.1+cpu' and
             actual['torch_geometric']==versions['torch_geometric']=='2.7.0',
             'ACTUAL_SECONDARY_ENVIRONMENT_DIFFERS_FROM_REVIEWED_GOLDEN_ENVIRONMENT')
        STATE['actual_versions']=actual
        core.read=read_payload
    return common,runner


def bind_envelope(envelope,expected):
    task=envelope['task'];mid=task['meta']['molecule_id']
    need(mid==expected['molecule_id'] and sha(canonical(task))==expected['task_sha256']==envelope['task_sha256'],
         'ORIGINAL_MAIN_SCIENTIFIC_TASK_CHANGED')
    pointers=task['records'];items=envelope['record_payloads'];mapped={}
    need(len(items)==len(pointers),'EXACT_PORTABLE_RECORD_PAYLOAD_COUNT_REQUIRED')
    for entry in items:
        key=entry['pointer_sha256'];need(key not in mapped,'DUPLICATE_PORTABLE_POINTER')
        mapped[key]=entry
    need(set(mapped)=={sha(canonical(pointer)) for pointer in pointers},'PORTABLE_POINTER_SET_DIFFERS_FROM_ORIGINAL_TASK')
    for pointer in pointers:
        entry=mapped[sha(canonical(pointer))]
        raw=base64.b64decode(entry['original_pickle_base64'],validate=True)
        need(len(raw)==entry['payload_bytes'] and sha(raw)==entry['payload_sha256']==pointer['record_payload_sha256'],
             'EXACT_ORIGINAL_RECORD_PICKLE_BYTES_REQUIRED')
    STATE['payloads']=mapped
    return task


def read_payload(pointer):
    """Equivalent to core.read after its LMDB get: SHA, unpickle, atom count.

    source_path/real_index remain unchanged provenance inside the pointer and
    pointer SHA; this function never resolves or opens those main-only paths.
    """
    entry=STATE['payloads'][sha(canonical(pointer))]
    payload=base64.b64decode(entry['original_pickle_base64'],validate=True)
    need(len(payload)==entry['payload_bytes'] and sha(payload)==pointer['record_payload_sha256'],
         'ACTUAL_RECORD_MANIFEST_MISMATCH')
    raw=pickle.loads(payload)
    core=STATE['core']
    if len(core.plain(core.field(raw,'x')))!=int(pointer['total_atoms']):
        raise ValueError('ACTUAL_RECORD_MANIFEST_MISMATCH')
    return raw


def scientific_sha(packet):
    value=copy.deepcopy(packet)
    need('elapsed_seconds' in value['summary'],'ORIGINAL_PACKET_TIMING_FIELD_REQUIRED')
    del value['summary']['elapsed_seconds']
    return sha(canonical(value))
