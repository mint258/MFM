"""Bind a future native task copy to the observed target-node clock.

The immutable login task remains the standby/handoff contract. Its producer
identity is still recorded by the controller. Only the separate child entry
copy gets an earlier-or-equal finite deadline anchor; no live task is edited.
"""
from copy import deepcopy
from native_clock_anchor_20261127 import native_clock_anchor


def node_clock_task(task):
    contract=task['contract'];c=task['configuration']
    if (contract.get('schema')!='S_FINITE_NATIVE_V1' or contract.get('uid')!=1278
            or contract.get('run')!=c.get('run') or contract.get('node')!=c.get('node')
            or c.get('node') not in ('compute-0-20','compute-0-22')
            or not 1800<=contract['duration_seconds']<=48*3600):
        raise ValueError('Exact existing finite native extension identity required')
    anchor=native_clock_anchor(contract['created_at'])
    result=deepcopy(task)
    result['contract']['created_at']=anchor
    result['node_clock_binding_20261127']=dict(original_login_created_at=contract['created_at'],
        effective_native_anchor=anchor,maximum_future_clock_seconds=5,
        maximum_original_age_seconds=60,duration_seconds=contract['duration_seconds'],
        original_contract_deadline=contract['created_at']+contract['duration_seconds'],
        effective_deadline=anchor+contract['duration_seconds'],deadline_extended=False,
        scientific_configuration_changed=False)
    return result
