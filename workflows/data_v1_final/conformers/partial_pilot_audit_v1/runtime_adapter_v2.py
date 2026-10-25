"""Small CPU execution binding; delegates all live admission/monitoring to Root."""
from __future__ import annotations
import concurrent.futures as cf
import importlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
PARENT=Path(__file__).parent.parent
sys.path.insert(0,str(PARENT/"formal_v1"))
from full_common import IO
RUNTIME=None


def validate_scope(request,runconfig,mode):
    if mode not in {"fixtures","closure"}:raise ValueError("CURRENT_SMALL_ANALYSIS_SCOPE_ONLY")
    expected=runconfig[mode]
    if request.get("kind")!="analysis" or request.get("partition")!="cpu" or request.get("pilot") is not True:
        raise ValueError("CPU_SMALL_ANALYSIS_REQUEST_ONLY")
    if request.get("scope_key")!=expected["scope_key"] or request.get("resource_policy")!="CPU_BOUNDED_TEST_LIVE_MEMORY_V1":
        raise ValueError("EXACT_ROOT_CPU_SMALL_SCOPE_REQUIRED")
    if any(request.get(key)!=expected[key] for key in ("cpus","memory_gib","wall_seconds")):
        raise ValueError("ORIGINAL_SCOPE_RESOURCES_REQUIRED")
    return expected


def admit(intent_path,entry_path,runconfig_path,closure_config_path,mode):
    global RUNTIME
    intent=json.loads(Path(intent_path).read_text());pins=intent["request"]["source_references"]
    runconfig=json.loads(Path(runconfig_path).read_text())
    if runconfig.get("schema")!="DATA_V1_CPU_PILOT_CLOSURE_RUNCONFIG_V1":
        raise ValueError("CPU_EXECUTION_METADATA_REQUIRED")
    for path in (entry_path,runconfig_path,closure_config_path,Path(__file__)):
        if IO.reference(path) not in pins:raise ValueError("CPU_ENTRY_RUNCONFIG_AND_SOURCE_PINS_REQUIRED")
    if IO.reference(closure_config_path)!=runconfig["closure_config"]:
        raise ValueError("ORIGINAL_CLOSURE_CONFIG_PIN_REQUIRED")
    scope=validate_scope(intent["request"],runconfig,mode)
    runtime_path=Path(runconfig["central_runtime_path"])
    matches=[ref for ref in pins if ref["path"]==str(runtime_path)]
    if len(matches)!=1:raise ValueError("ROOT_ACTUAL_CENTRAL_RUNTIME_PIN_REQUIRED")
    IO.require_pin(matches[0])
    sys.path.insert(0,str(runtime_path.parent.parent))
    RUNTIME=importlib.import_module("cpu_analysis_v1.runtime_v2")
    if Path(RUNTIME.__file__).absolute()!=runtime_path or IO.reference(runtime_path)!=matches[0]:
        raise ValueError("WRONG_OR_MUTATED_CENTRAL_RUNTIME")
    proof=RUNTIME.root_guard(Path(intent_path),Path(entry_path),scope["cap_bytes"],scope["wall_seconds"])
    RUNTIME.checkpoint()
    return {"central_runtime":matches[0],"scope_key":scope["scope_key"],"root_guard_proof":proof}


def checkpoint():
    if RUNTIME is None:raise ValueError("CENTRAL_CPU_GUARD_NOT_ADMITTED")
    return RUNTIME.checkpoint()


def bounded_map(pool,fn,items,checkpoint_fn=None):
    """At most16 IO tasks in flight; finite waits keep Root guard checkpoints live."""
    check=checkpoint if checkpoint_fn is None else checkpoint_fn
    iterator=iter(items);active=set();exhausted=False
    while active or not exhausted:
        check()
        while len(active)<16 and not exhausted:
            check()
            try:item=next(iterator)
            except StopIteration:exhausted=True;break
            active.add(pool.submit(fn,item))
        if not active:break
        done,_=cf.wait(active,timeout=0.5,return_when=cf.FIRST_COMPLETED)
        for future in done:
            check();active.remove(future);yield future.result()
