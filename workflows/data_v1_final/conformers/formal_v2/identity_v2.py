"""Preserve historical S-prime physical IDs; append new provenance identities."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
PARENT=Path(__file__).parent.parent
sys.path.insert(0,str(PARENT/"formal_v1"))
from full_common import IO,ledger_path
from selection import stable_key

INT64_MAX=(1<<63)-1
SELECTION_SHA="41f21f5586c06f3c6fd7cfa9712623adc8091da996c72f6d71170dd4b716e2cb"


def physical_id(value):
    if type(value) is not int or not 0<=value<=INT64_MAX:
        raise ValueError("NONNEGATIVE_INT64_PHYSICAL_SPRIME_ID_REQUIRED")
    return value


def require_task_key(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("ACTUAL_ONCE_LEDGER_TASK_KEY_REQUIRED")
    return value


def append_generated(rows,original_n,max_original_idx):
    """Input max is over ALL old rows, including failed/nonconverged selected IDs."""
    n=physical_id(original_n)
    maximum=-1 if max_original_idx is None else physical_id(max_original_idx)
    start=max(n,maximum+1)
    keys=set();ordered=[]
    for row in rows:
        key=(require_task_key(row["task_key"]),physical_id(row["seed"]),physical_id(row["candidate_id"]))
        if key in keys:raise ValueError("DUPLICATE_NEW_PROVENANCE_IDENTITY")
        keys.add(key);ordered.append((key,row))
    if ordered and start+len(ordered)-1>INT64_MAX:raise ValueError("APPEND_PHYSICAL_ID_INT64_OVERFLOW")
    return [dict(row,sprime_conf_idx=start+i,canonical_sprime_conf_idx=start+i,
                 identity_namespace="data_v1_fill",source_conformer_id=None,
                 source_attempt_max_sprime_conf_idx=max_original_idx,original_N=n)
            for i,(_,row) in enumerate(sorted(ordered,key=lambda item:item[0]))]


def old_identity(original_idx):
    index=physical_id(original_idx)
    return {"sprime_conf_idx":index,"canonical_sprime_conf_idx":index,
            "identity_namespace":"accepted_original_sprime","source_conformer_id":index}


def fixed_random_ids(mid,ids):
    values=[physical_id(value) for value in ids]
    if len(values)!=len(set(values)):raise ValueError("DUPLICATE_PHYSICAL_SPRIME_ID")
    return sorted(values,key=lambda value:(stable_key(20261025,mid,"uff_sprime",value),str(value)))


def attempt_binding(packet,value,pilot_imports):
    """Read actual persisted identities; never derive a task key from a molecule."""
    mid=packet["molecule_id"];source=packet["source"];start=packet.get("formal_start")
    imported=pilot_imports.get(mid)
    if imported is not None:
        if start is not None or imported["source"]!=source:
            raise ValueError("PILOT_IMPORT_SOURCE_OR_ATTEMPT_TYPE_CHANGED")
        key=require_task_key(imported["task_key"]);path=ledger_path(value,key)
        observed=json.loads(path.read_text())
        if observed.get("schema")!="SPRIME_PILOT_ATTEMPT_IMPORTED_V1" or observed.get("source")!=source or observed.get("task_key")!=key or observed.get("molecule_id")!=mid:
            raise ValueError("ACTUAL_IMPORTED_PILOT_ONCE_LEDGER_REQUIRED")
    else:
        if not isinstance(start,dict) or start.get("schema")!="SPRIME_ONCE_ATTEMPT_STARTED_V1":
            raise ValueError("ACTUAL_FORMAL_START_IDENTITY_REQUIRED")
        key=require_task_key(start.get("task_key"));path=ledger_path(value,key)
        observed=json.loads(path.read_text())
        if observed!=start or observed.get("molecule_id")!=mid:
            raise ValueError("FORMAL_RESULT_DIFFERS_FROM_ACTUAL_ONCE_LEDGER")
    return {"task_key":key,"once_ledger_path":str(path),"once_ledger_sha256":IO.digest(path),
            "once_ledger_bytes":path.stat().st_size}


def random_identity_contract():
    selection=IO.reference(PARENT/"selection.py")
    if selection["sha256"]!=SELECTION_SHA:raise ValueError("FROZEN_RANDOM_ALGORITHM_CHANGED")
    return {"random_identity_basis":"canonical_sprime_conf_idx",
        "canonical_sprime_conf_idx_policy":"accepted original sprime_conf_idx unchanged; generated append after max(all original attempted idx, original N-1); physical gaps allowed",
        "physical_identity_int_type":"int64","order_rank_contiguous_zero_based":True,
        "random_order_seed":20261025,"random_order_source_literal":"uff_sprime",
        "random_order_sort":"SHA256(UTF8 data-v1-conformer-order:{seed}:{molecule_id}:uff_sprime:{physical_sprime_conf_idx}), then str(physical_sprime_conf_idx)",
        "random_order_algorithm":selection,"identity_algorithm":IO.reference(Path(__file__)),
        "old_raw_identity":{"namespace":"accepted_original_sprime","source_conformer_id":"original_sprime_conf_idx"},
        "generated_raw_identity":{"namespace":"data_v1_fill","fields":["task_key","seed","candidate_id"]},
        "kernel_sprime_conf_idx_basis":"diagnostic package row rank only; forbidden as physical/random identity",
        "reuse_rule":"same frozen physical ID, coordinates, perturb record_id and full scientific input; equal coordinates alone insufficient"}
