"""Pure lifecycle/resource decisions shared by profile CLI and CPU tests."""
from __future__ import annotations
import os
import json

GUARD_RESERVE=96*1024**2
SAVE_RESERVE_SECONDS=300


class CommittedProfilePause(RuntimeError):
    """Stop before another numerical update; caller saves committed state."""


def inherited_budget(outer_bytes,environment=None):
    environment=os.environ if environment is None else environment
    raw=environment.get('MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES')
    if not isinstance(raw,str) or not raw.isdecimal():
        raise ValueError('Supervisor-derived child output budget is required')
    value=int(raw)
    if type(outer_bytes) is not int or not 128*1024**2+GUARD_RESERVE<=outer_bytes<=2*1024**3 or value!=outer_bytes-GUARD_RESERVE:
        raise ValueError('Inherited child budget must equal admitted outer minus96MiB')
    return value


def should_pause(started,wall_seconds,now):
    if type(wall_seconds) is not int or wall_seconds<=SAVE_RESERVE_SECONDS:
        raise ValueError('A real300-second checkpoint/cleanup reserve is required')
    return now-started>=wall_seconds-SAVE_RESERVE_SECONDS


def completion_errors(*,failure,cleanup_errors,target_updates,actual_updates,sdk_count,payload_count):
    result=list(cleanup_errors)
    if failure is not None: result.append(dict(component='profile_failure',**failure))
    if actual_updates!=target_updates:
        result.append(dict(component='profile_endpoint',type='IncompleteProfile',message='Committed pause did not reach the fixed short target'))
    if sdk_count!=1 or payload_count!=1:
        result.append(dict(component='profile_artifacts',type='IncompleteProfile',message='Exactly one native SDK and safe checkpoint payload required'))
    return result


def enforce_failed_exit(errors,*,original_failure):
    # An original exception is already being re-raised by the CLI except path.
    # New finalization/artifact failures must create a nonzero exit themselves.
    if errors and original_failure is None:
        raise RuntimeError('Profile failed or incomplete: '+str(errors))


def summary_from_mirror(path,*,maximum_rows=102):
    result={}; previous=None; rows=0
    def merge(destination,source):
        for key,value in source.items():
            if isinstance(value,dict):
                if not isinstance(destination.get(key),dict): destination[key]={}
                merge(destination[key],value)
            else: destination[key]=value
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            value=json.loads(line,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite mirror value')))
            if value['commit'] is not True or type(value['step']) is not int or (previous is not None and value['step']!=previous+1):
                raise ValueError('Committed continuous mirror steps required')
            rows+=1
            if rows>maximum_rows: raise ValueError('Bounded short-profile mirror rows exceeded')
            merge(result,value['row']); previous=value['step']
    if not rows: raise ValueError('Profile mirror is empty')
    return result
