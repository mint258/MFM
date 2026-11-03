"""Only explicit reader config differs; original pure science/quality objects."""
import hashlib,math
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as R
from workflows.data_v1_final.conformers.formal_cpu_auto_finalize_mapping_v2 import finalize as ORIGINAL
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import core as PM7
from workflows.data_v1_final.conformers.pm7_multinode_compat32_v1.compute import compute as pm7_compute
from workflows.data_v1_final.conformers.formal_cpu_auto_v3.identity import append_generated,random_identity_contract
IO=R.IO
merge_counts=ORIGINAL.merge_counts;membership=ORIGINAL.membership;exclusion_gates=ORIGINAL.exclusion_gates;scaffold_chunk=ORIGINAL.scaffold_chunk
geometry_orders=PM7.geometry_orders;unique_representatives=PM7.unique_representatives

def normalize_package(ref,value):
    import numpy as np
    packet=R.read_packet(ref,value)
    mid=packet["summary"]["molecule_id"]
    if mid!=ref["molecule_id"]:raise ValueError("PACKAGE_MOLECULE_ID_MISMATCH")
    rows=[];indices=set();candidate_keys=set();numbers=None
    for position,row in enumerate(packet["conformers"]):
        if type(row["sprime_conf_idx"]) is not int or any(type(z) is not int or not 1<=z<=118 for z in row["atomic_numbers"]):
            raise ValueError("ATOM_NUMBERS_AND_CONFORMER_ID_MUST_REMAIN_INTEGERS")
        if type(row["below_dedup_threshold"]) is not bool:
            raise ValueError("EXPLICIT_BOOLEAN_DEDUP_FLAG_REQUIRED")
        index=int(row["sprime_conf_idx"])
        if index!=position or index in indices or row["molecule_id"]!=mid:raise ValueError("DUPLICATE_OR_REORDERED_SUPPLEMENT_CONFORMER")
        indices.add(index)
        z=np.asarray(row["atomic_numbers"],dtype="<i8")
        xyz=np.asarray(row["coordinates"],dtype="<f8")
        atom_sha=hashlib.sha256(z.tobytes()).hexdigest()
        if row["status"]!="SUCCESS" or row["converged"] is not True or atom_sha!=row["atom_order_sha256"] or IO.geometry_sha(z,xyz)!=row["geometry_sha256"]:
            raise ValueError("SUPPLEMENT_COORDINATES_OR_ATOM_ORDER_INVALID")
        if row["source_record_id"]!=packet["summary"]["source_record_id"] or atom_sha!=packet["summary"]["atom_order_sha256"]:
            raise ValueError("SUPPLEMENT_SOURCE_ANCHOR_OR_SUMMARY_ATOM_ORDER_CHANGED")
        if numbers is not None and numbers!=z.tolist():raise ValueError("SUPPLEMENT_ATOM_SEQUENCE_CHANGED")
        numbers=z.tolist()
        origin=row["origin"]
        if origin=="accepted_sprime":
            if row["original_sprime_conf_idx"] is None:raise ValueError("OLD_ORIGINAL_INDEX_MISSING")
        elif origin in {"data_v1_fill_10N","data_v1_fill_retry1"}:
            key=(row["seed"],row["candidate_id"])
            if key in candidate_keys or type(row["candidate_id"]) is not int or row["candidate_id"]<0:raise ValueError("GENERATED_CANDIDATE_REUSED_OR_MISSING")
            candidate_keys.add(key)
        else:raise ValueError("UNREGISTERED_GEOMETRY_ORIGIN")
        if not math.isfinite(float(row["uff_energy_kcal_mol"])):
            raise ValueError("NONFINITE_ACCEPTED_UFF_ENERGY")
        rows.append({"molecule_id":mid,"kernel_sprime_conf_idx":index,"origin":origin,
            "original_sprime_conf_idx":row["original_sprime_conf_idx"],"candidate_id":row["candidate_id"],
            "seed":row["seed"],"uff_energy_kcal_mol":float(row["uff_energy_kcal_mol"]),
            "atom_order_sha256":atom_sha,"geometry_sha256":row["geometry_sha256"],
            "source_record_id":row["source_record_id"],"below_dedup_threshold":bool(row["below_dedup_threshold"]),
            "source_path":ref["path"],"source_sha256":ref["sha256"],"source_bytes":ref["bytes"],
            "source_format":"reproduction_json_gz","source_member":"conformers","source_row_index":position})
    return {"molecule_id":mid,"summary":packet["summary"],"rows":rows,"atomic_numbers":numbers,
            "source":ref,"formal_start":packet.get("formal_start")}
