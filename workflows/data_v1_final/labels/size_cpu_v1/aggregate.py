"""Approved candidate size statistics; no mutation of values or validity masks."""
from __future__ import annotations

import collections
import math


def stable_rms(values):
    if not values:return None
    largest=max(abs(v) for v in values)
    if largest==0:return 0.0
    return largest*math.sqrt(math.fsum((v/largest)**2 for v in values)/len(values))


def median(values):
    if not values:return None
    from calibration import exact_mean_pair
    ordered=sorted(values);n=len(ordered)
    return ordered[n//2] if n%2 else exact_mean_pair(ordered[n//2-1],ordered[n//2])


def pair_keys(raw, leaf):
    if not isinstance(raw,list):return None
    keys=[]
    for row in raw:
        if not isinstance(row,dict):return None
        if leaf=="sigma_pi_entries":
            a=(row.get("atom_i"),row.get("basis_i"));b=(row.get("atom_j"),row.get("basis_j"))
            if any(type(x[0]) is not int or not isinstance(x[1],str) for x in (a,b)):return None
        else:
            a,b=row.get("i"),row.get("j")
            if type(a) is not int or type(b) is not int:return None
        keys.append(tuple(sorted((a,b))))
    return keys


def complete(entry):
    values,mask=entry["values_float64"],entry["value_mask"]
    if not values:return "EMPTY_OR_UNAVAILABLE_SOURCE"
    if len(values)!=len(mask):raise ValueError("SIZE_LEAF_MASK_LENGTH_DIFFERS")
    if not all(mask):return "PARTIAL_OR_INVALID_SOURCE_MASK"
    if not all(type(v) in (int,float) and math.isfinite(v) for v in values):
        raise ValueError("NONFINITE_UNMASKED_VALUE_REACHED_SIZE_AGGREGATION")
    return None


def aggregate(target, entries, numbers, model=None):
    """Return one value and an explicit rho-only exclusion; labels remain intact."""
    members=[entries[fid] for fid in target["field_ids"]]
    for member in members:
        reason=complete(member)
        if reason:return None,reason,{}
    op=target["operation"];a=members[0];v=a["values_float64"];extra={}
    if op in {"RAW_SCALAR","TRAIN_ELEMENT_RESIDUAL_SCALAR"}:
        if len(v)!=1:return None,"MOLECULE_SCALAR_LAYOUT_DIFFERS",extra
        value=v[0]
        if op=="TRAIN_ELEMENT_RESIDUAL_SCALAR":
            if not model or "coefficients" not in model:return None,"PENDING_MATCHED_TRAIN_HOF_ELEMENT_REFERENCE",extra
            count=collections.Counter(numbers)
            if set(count)-set(model["basis"]):raise ValueError("HOF_ELEMENT_REFERENCE_BASIS_DIFFERS")
            value-=model["intercept"]+math.fsum(count[z]*b for z,b in zip(model["basis"],model["coefficients"]))
    elif op=="JOINT_XYZ_L2":
        if any(len(e["values_float64"])!=1 for e in members):return None,"VECTOR_COMPONENT_LAYOUT_DIFFERS",extra
        value=math.hypot(*(e["values_float64"][0] for e in members))
    elif op=="SYMMETRIC_FROBENIUS":
        if any(len(e["values_float64"])!=1 for e in members):return None,"TENSOR_COMPONENT_LAYOUT_DIFFERS",extra
        xx,xy,yy,xz,yz,zz=[e["values_float64"][0] for e in members]
        value=math.hypot(xx,yy,zz,math.sqrt(2)*xy,math.sqrt(2)*xz,math.sqrt(2)*yz)
    elif op=="ATOM_VECTOR_RMS_NORM":
        if len(v)!=3*len(numbers) or a["atom_indices"]!=[i for i in range(len(numbers)) for _ in range(3)]:
            return None,"ATOM_VECTOR_NOT_COMPLETE_N_BY_XYZ",extra
        norms=[math.hypot(*v[i:i+3]) for i in range(0,len(v),3)]
        value=stable_rms(norms);extra["global_vector_L2"]=math.hypot(*norms)
    elif op in {"SEMANTIC_ATOM_SUM","SEMANTIC_ATOM_RMS"}:
        expected=[i for i,z in enumerate(numbers) if z>1] if a["field"]["source_path"].endswith("super_heavy_atom_rows") else list(range(len(numbers)))
        indices=a["atom_indices"]
        if len(v)!=len(expected) or len(indices)!=len(expected) or set(indices)!=set(expected):
            return None,"SEMANTIC_OWNED_ATOM_SCOPE_INCOMPLETE_OR_DUPLICATE",extra
        value=math.fsum(v) if op=="SEMANTIC_ATOM_SUM" else stable_rms(v)
        if op=="SEMANTIC_ATOM_RMS":
            extra={"signed_mean":math.fsum(v)/len(v),"sum_abs":math.fsum(abs(x) for x in v)}
    elif op in {"STORED_PAIR_ENERGY_SUM","STORED_PAIR_RMS"}:
        keys=a.get("pair_keys")
        if keys is None or len(keys)!=len(v):return None,"STORED_PAIR_KEY_LAYOUT_UNAVAILABLE",extra
        seen={}
        for key,x in zip(keys,v):
            if key in seen:
                return None,("DUPLICATE_PAIR_KEY_SAME_VALUE" if seen[key]==x else "DUPLICATE_PAIR_KEY_CONFLICT"),extra
            seen[key]=x
        value=math.fsum(v) if op=="STORED_PAIR_ENERGY_SUM" else stable_rms(v)
        extra["stored_entries"]=len(v)
    else:raise ValueError("UNAPPROVED_SIZE_AGGREGATION_OPERATION:"+op)
    if value is None or not math.isfinite(value):return None,"AGGREGATION_OVERFLOW_OR_UNDEFINED",extra
    if any(not math.isfinite(x) for x in extra.values()):
        extra={k:x for k,x in extra.items() if math.isfinite(x)}
        extra["some_sensitivities_overflowed"]=True
    return float(value),None,extra


def target_catalog(proposal, fields):
    by_key={f["field_key"]:f for f in fields};rows={r["field_key"]:r for r in proposal["components"]};targets=[]
    if set(by_key)!=set(rows):raise ValueError("SIZE_COMPONENT_SET_DIFFERS_FROM_CANONICAL_FIELD_MAP")
    for row in proposal["targets"]:
        members=[rows[key] for key in row["member_field_keys"]]
        operation=members[0]["primary_aggregation"]
        if len({m["primary_aggregation"] for m in members})!=1:raise ValueError("JOINT_TARGET_OPERATION_CONFLICT")
        if operation=="JOINT_XYZ_L2":order=["x","y","z"]
        elif operation=="SYMMETRIC_FROBENIUS":order=["xx","xy","yy","xz","yz","zz"]
        else:order=[members[0]["component"]]
        component={m["component"]:m for m in members}
        if set(component)!=set(order):raise ValueError("PHYSICAL_SIZE_TARGET_COMPONENT_SET_INCOMPLETE")
        ordered=[component[c] for c in order];task=ordered[0]["task"]
        if any(m["task"]!=task for m in ordered):raise ValueError("JOINT_SIZE_TARGET_CROSSES_TASK_CONTEXT")
        targets.append({"target_id":row["target_id"],"task":task,"field_ids":[by_key[m["field_key"]]["field_id"] for m in ordered],
            "member_field_keys":[m["field_key"] for m in ordered],"operation":operation,
            "basis_invariance_status":"BASIS_INVARIANCE_UNPROVEN" if any("sigma_pi_entries" in m["source_path"] for m in ordered) else "OPERATION_ROTATION_INVARIANT_IF_SOURCE_PHYSICAL_SEMANTICS_HOLD",
            "unit_reviews":[m["unit_review"] for m in ordered],"family_v1_final":None})
    if len(targets)!=129:raise ValueError("EXPECTED_129_PHYSICAL_STATISTIC_TARGETS")
    return targets
