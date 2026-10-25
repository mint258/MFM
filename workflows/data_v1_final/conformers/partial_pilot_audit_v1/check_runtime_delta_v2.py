"""Pure metadata byte-delta proof; no entry/runtime import, AST exec or data IO."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).parent
REPO=HERE.parents[3]


def ref(path):
    raw=path.read_bytes()
    return {"path":str(path),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}


def main():
    old_adapter=HERE.parent/"pilot_closure_cpu_v1/runtime_adapter.py"
    new_adapter=HERE/"runtime_adapter_v2.py"
    old_config=REPO/"configs/data_v1/conformers/pilot_closure_cpu_v1.json"
    new_config=REPO/"configs/data_v1/conformers/partial_pilot_cpu_runconfig_v2.json"
    before=old_adapter.read_bytes();after=new_adapter.read_bytes()
    needle=b'"cpu_analysis_v1.runtime"'
    if before.count(needle)!=1 or before.replace(needle,b'"cpu_analysis_v1.runtime_v2"')!=after:
        raise ValueError("ADAPTER_CHANGE_NOT_EXACTLY_RUNTIME_V2_DYNAMIC_IMPORT")
    raw=old_config.read_bytes();newraw=new_config.read_bytes()
    path=b"cpu_analysis_v1/runtime.py"
    if raw.count(path)!=1 or raw.replace(path,b"cpu_analysis_v1/runtime_v2.py")!=newraw:
        raise ValueError("RUNCONFIG_CHANGE_NOT_EXACTLY_RUNTIME_V2_PATH")
    a=json.loads(raw);b=json.loads(newraw)
    if a["closure_config"]!=b["closure_config"] or a["closure"]!=b["closure"] or a["fixtures"]!=b["fixtures"]:
        raise ValueError("ORIGINAL_INPUT_OR_SCOPE_RESOURCE_CHANGED")
    old_validator=HERE.parent/"pilot_closure_v1/close_pilot.py"
    if ref(old_validator)["sha256"]!="e7c8992c06c305a53c3d706e0335b6a94db752d9053594c7bc0571f3e642907f":
        raise ValueError("FROZEN_SCIENTIFIC_PACKAGE_VALIDATOR_CHANGED")
    print(json.dumps({"status":"PARTIAL_CPU_RUNTIME_BINDING_DELTA_PROVED",
        "old_adapter":ref(old_adapter),"new_adapter":ref(new_adapter),
        "old_cpu_runconfig":ref(old_config),"new_cpu_runconfig":ref(new_config),
        "unchanged_package_validator":ref(old_validator),
        "adapter_delta":"one literal dynamic import runtime -> runtime_v2",
        "runconfig_delta":"only central_runtime_path runtime.py -> runtime_v2.py",
        "resource_parameters_and_original_config_pin_identical":True,
        "runtime_or_entry_executed":False,"scientific_calls":0,"data_pages_read":False}))


if __name__=="__main__":main()
