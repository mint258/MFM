"""Deterministic target-independent candidate pool; export only real no-fill rows.

This module is independent of the old 10-conformer producer. Its kernel is
injected so prefix, shortage, provenance and no-retry semantics are testable
without performing chemistry. Native scientific functions live in native.py.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import struct
import time

class IntegrityError(ValueError):
    pass


RECIPE = {
    "schema": "PUBCHEM_UFF3_RECIPE_V1",
    "rdkit": "2025.09.5",
    "candidate_budget": 30,
    "initial_export_limit": 3,
    "seed_domain": "sprime-ETKDGv3-v1:",
    "embedding": {"method": "ETKDGv3", "numThreads": 1,
        "enforceChirality": True, "pruneRmsThresh": -1.0,
        "maxIterations": 200, "useRandomCoords": False},
    "uff": {"snapshotFreq": 1, "maxIts": 2000,
        "energyTol": 1e-6, "forceTol": 1e-4},
    "dedup_rmsd_A": 0.5,
    "selection": "original_energy_order_greedy_RMSD_only_no_fill",
    "ordering_seed": 20261025,
    "retry": False,
    "zero_embedding_fallback": False,
    "forcefield_replacement": False,
    "new_PM7_xTB_Pprime_calls": False,
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def recipe_sha():
    return sha(canonical(RECIPE))


def source_identity(source):
    required = ("pubchem_version", "cid", "full_key", "source_smiles", "isomeric_smiles", "stream", "stream_rank")
    if any(k not in source for k in required):
        raise ValueError("SOURCE_IDENTITY_FIELDS_MISSING")
    if type(source["cid"]) is not int or source["cid"] <= 0:
        raise ValueError("INVALID_CID")
    if source["stream"] not in ("R", "N") or type(source["stream_rank"]) is not int or source["stream_rank"] < 1:
        raise ValueError("INVALID_STREAM_OR_RANK")
    return sha(canonical(source))


def molecule_id(source):
    source_identity(source)
    return "expansion-pubchem:{pubchem_version}:{cid}:{full_key}".format(**source)


def seed_for(mid):
    """Bit-identical to unmodified S-prime science.seed_for(mid, False)."""
    value = int.from_bytes(hashlib.sha256((RECIPE["seed_domain"] + mid).encode()).digest()[:4], "big")
    return max(value & 0x7fffffff, 1)


def geometry_sha(numbers, xyz):
    if len(xyz) != len(numbers) or any(len(row) != 3 for row in xyz):
        raise ValueError("GEOMETRY_ATOM_SHAPE")
    if any(not math.isfinite(float(v)) for row in xyz for v in row):
        raise ValueError("NONFINITE_GEOMETRY")
    raw = b"".join(struct.pack("<q", int(v)) for v in numbers)
    raw += b"".join(struct.pack("<d", float(v)) for row in xyz for v in row)
    return sha(raw)


def no_fill_order(candidates, distance, threshold=0.5):
    """Exactly the first, energy-greedy phase of original select_fill.

    Build the whole canonical order, independently of requested export count.
    Never enter the original farthest-point below-threshold fill phase.
    """
    if len({r["candidate_key"] for r in candidates}) != len(candidates):
        raise ValueError("DUPLICATE_CANDIDATE_KEY")
    selected = []
    for row in sorted(candidates, key=lambda item: (item["energy"], item["candidate_key"])):
        closest = min((distance(row, old) for old in selected), default=math.inf)
        if selected and not math.isfinite(closest):
            raise ValueError("NONFINITE_RMSD")
        if closest >= threshold:
            selected.append(dict(row, below_dedup_threshold=False,
                min_rmsd_to_previously_selected_A=None if not selected else closest))
    return selected


def evidence_value(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite_float_hex": value.hex()}
    if isinstance(value, dict):
        return {k: evidence_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [evidence_value(v) for v in value]
    return value


def _clean_d20(value):
    value = copy.deepcopy(value)
    if len(value["names"]) != 20 or len(value["values"]) != 20 or len(value["valid_mask"]) != 20:
        raise ValueError("D20_SHAPE")
    for i, number in enumerate(value["values"]):
        if number is None or not math.isfinite(float(number)):
            value["values"][i] = None
            value["valid_mask"][i] = False
    return value


def create_cache(source, kernel, emit=lambda event: None, checkpoint=lambda: None):
    """One embedding call, at most one optimization call per candidate.

    All 30 internal candidates use a fixed budget independent of exported k.
    Complete candidate outcomes are retained to permit later append-only export
    without repeating embedding, successful optimization or failed optimization.
    A caller must persist emit events synchronously before the next native call.
    There is no automatic scientific retry or soft wall-clock termination.
    """
    mid = molecule_id(source)
    started = time.monotonic()
    cache = {"schema": "PUBCHEM_UFF3_CLOSED_CANDIDATE_CACHE_V1",
        "source": copy.deepcopy(source), "source_identity_sha256": source_identity(source),
        "molecule_id": mid, "recipe": copy.deepcopy(RECIPE), "recipe_sha256": recipe_sha(),
        "seed": seed_for(mid), "D20": None, "atomic_numbers": [], "attempts": [],
        "valid_candidates": [], "canonical_candidates": [], "embedding_calls": 0,
        "optimizer_calls": 0, "state": "UNKNOWN", "error": None,
        "complete": False, "new_QM_calls": 0}
    emit({"phase": "molecule_intent", "molecule_id": mid,
          "source_identity_sha256": cache["source_identity_sha256"], "recipe_sha256": recipe_sha()})
    try:
        checkpoint()
        prepared = kernel.prepare(source)
        cache["atomic_numbers"] = [int(z) for z in prepared["atomic_numbers"]]
        cache["D20"] = _clean_d20(prepared["D20"])
        cache["kernel_provenance"] = prepared.get("kernel_provenance")
        cache["unassigned_stereo"] = prepared.get("unassigned_stereo", [])
        emit({"phase": "graph_return", "D20": cache["D20"],
              "atomic_numbers": cache["atomic_numbers"],
              "unassigned_stereo": cache["unassigned_stereo"]})
        if cache["unassigned_stereo"]:
            cache["state"] = "STEREO_REFERENCE_UNAVAILABLE_NO_PM7"
        elif prepared.get("uff_supported") is False:
            cache["state"] = "UFF_UNSUPPORTED"
        else:
            checkpoint()
            emit({"phase": "embedding_intent", "seed": cache["seed"], "candidate_budget": 30})
            cache["embedding_calls"] = 1
            try:
                candidate_ids = [int(v) for v in kernel.embed(cache["seed"], 30)]
            except Exception as exc:
                cache["state"] = "EMBED_FAILED"
                cache["error"] = type(exc).__name__ + ": " + str(exc)
                candidate_ids = []
            if len(candidate_ids) > 30 or len(candidate_ids) != len(set(candidate_ids)) or any(v < 0 for v in candidate_ids):
                raise ValueError("INVALID_NATIVE_CANDIDATE_IDS")
            if not candidate_ids and cache["state"] != "EMBED_FAILED":
                cache["state"] = "EMBED_FAILED"
                cache["error"] = "ZERO_EMBEDDED_CANDIDATES_NO_FALLBACK"
            cache["embedded_candidate_ids"] = candidate_ids
            emit({"phase": "embedding_return", "candidate_ids": candidate_ids,
                  "error": cache["error"]})
            for candidate_id in candidate_ids:
                checkpoint()
                emit({"phase": "optimizer_intent", "candidate_id": candidate_id,
                      "parameters": RECIPE["uff"]})
                cache["optimizer_calls"] += 1
                row = None
                try:
                    row = kernel.optimize(candidate_id)
                    if row["candidate_id"] != candidate_id:
                        raise ValueError("NATIVE_CANDIDATE_ID_CHANGED")
                    row["candidate_key"] = "generated:%06d" % candidate_id
                    row["seed"] = cache["seed"]
                    row["geometry_sha256"] = geometry_sha(cache["atomic_numbers"], row["coordinates"])
                    valid = (row["optimizer_code"] == 0 and row["stereo_valid"] is True
                             and math.isfinite(float(row["energy"])))
                    event = {"candidate_id": candidate_id, "status": "SUCCESS" if valid else "NATIVE_REJECTED",
                             "candidate": row if valid else evidence_value(row)}
                    if valid:
                        cache["valid_candidates"].append(row)
                except IntegrityError:
                    raise
                except Exception as exc:
                    event = {"candidate_id": candidate_id, "status": "NATIVE_FAILED",
                             "error": type(exc).__name__ + ": " + str(exc),
                             "raw_native_candidate": evidence_value(row)}
                cache["attempts"].append(event)
                emit({"phase": "optimizer_return", **event})
            selected = no_fill_order(cache["valid_candidates"], kernel.distance)
            if hasattr(kernel, "check_original_selection"):
                kernel.check_original_selection(cache["valid_candidates"], selected)
            cache["canonical_candidates"] = selected
            if len(selected) >= 3:
                cache["state"] = "SUCCESS"
            elif cache["state"] != "EMBED_FAILED":
                cache["state"] = "INSUFFICIENT_UNIQUE_CONFORMERS"
        cache["complete"] = True
    except Exception as exc:
        cache["state"] = "TECHNICAL_UNKNOWN"
        cache["error"] = type(exc).__name__ + ": " + str(exc)
        cache["source_contract_hold"] = isinstance(exc, IntegrityError)
        # Never silently rerun an interrupted molecule/native candidate. Root
        # can adopt the durable scientific events; no implicit retry is offered.
    if not cache["complete"] and cache["valid_candidates"] and not cache.get("source_contract_hold"):
        # Keep every usable native return even when an allocation guard drains.
        cache["canonical_candidates"] = no_fill_order(cache["valid_candidates"], kernel.distance)
    cache["elapsed_seconds"] = time.monotonic() - started
    cache["cache_content_sha256"] = sha(canonical(cache))
    emit({"phase": "cache_closed", "cache_content_sha256": cache["cache_content_sha256"], "state": cache["state"]})
    return cache


def validate_cache(cache, source):
    if cache.get("schema") != "PUBCHEM_UFF3_CLOSED_CANDIDATE_CACHE_V1":
        raise ValueError("WRONG_CACHE_SCHEMA")
    if cache["source_identity_sha256"] != source_identity(source) or cache["source"] != source:
        raise ValueError("CACHE_SOURCE_CHANGED")
    if cache["recipe_sha256"] != recipe_sha() or cache["recipe"] != RECIPE:
        raise ValueError("CACHE_RECIPE_CHANGED")
    copied = dict(cache)
    expected = copied.pop("cache_content_sha256")
    if sha(canonical(copied)) != expected:
        raise ValueError("CACHE_CONTENT_CHANGED")
    if cache["seed"] != seed_for(molecule_id(source)) or cache["molecule_id"] != molecule_id(source):
        raise ValueError("CACHE_SEED_OR_ID_CHANGED")
    for row in cache["canonical_candidates"]:
        if row["geometry_sha256"] != geometry_sha(cache["atomic_numbers"], row["coordinates"]):
            raise ValueError("CACHE_GEOMETRY_CHANGED")
    return cache


def export_cache(cache, source, kernel, *, limit=3, previous_packet=None,
                 allow_future_extension=False, emit=lambda event: None):
    """Export <=3 now; explicit future extension reads closed cache only.

    Old physical IDs, float64 coordinates, energies and descriptors are copied
    byte-for-byte from previous_packet, and new rows are appended. No UFF or
    embedding method is invoked here. D20 is the one molecule-level cache row.
    """
    validate_cache(cache, source)
    if type(limit) is not int or limit < 1 or (limit > 3 and not allow_future_extension):
        raise ValueError("INITIAL_EXPORT_MAXIMUM_THREE")
    canonical_rows = cache["canonical_candidates"]
    previous_rows = [] if previous_packet is None else previous_packet["conformers"]
    if len(previous_rows) > limit:
        raise ValueError("EXTENSION_CANNOT_TRUNCATE_PRIOR_CONFORMERS")
    if previous_packet is not None:
        old = dict(previous_packet)
        old_hash = old.pop("packet_content_sha256")
        if sha(canonical(old)) != old_hash:
            raise ValueError("PREVIOUS_PACKET_CONTENT_OR_PREFIX_CHANGED")
        if previous_packet["candidate_cache_sha256"] != cache["cache_content_sha256"] or previous_packet["source"] != source:
            raise ValueError("PREVIOUS_PACKET_FROM_DIFFERENT_CACHE")
        for i, row in enumerate(previous_rows):
            if (row["conformer_id"] != i or i >= len(canonical_rows)
                    or row["geometry_sha256"] != canonical_rows[i]["geometry_sha256"]
                    or row["geometry_sha256"] != geometry_sha(cache["atomic_numbers"], row["coordinates"])
                    or row["energy"] != canonical_rows[i]["energy"]):
                raise ValueError("PRIOR_CONFORMER_PREFIX_CHANGED")
    packet = {"schema": "PUBCHEM_UFF3_SELECTED_PACKET_V1", "source": copy.deepcopy(source),
        "molecule_id": cache["molecule_id"], "dataset_version": "v2_candidate",
        "geometry_source": "uff_sprime", "training_eligible": False,
        "seed": cache["seed"], "order_seed": RECIPE["ordering_seed"],
        "D20": copy.deepcopy(cache["D20"]), "atomic_numbers": cache["atomic_numbers"],
        "atom_order_sha256": sha(b"".join(struct.pack("<q", z) for z in cache["atomic_numbers"])),
        "candidate_cache_sha256": cache["cache_content_sha256"], "recipe_sha256": recipe_sha(),
        "conformers": copy.deepcopy(previous_rows), "requested_conformers": limit,
        "actual_conformers": min(limit, len(canonical_rows)),
        "available_unique_in_closed_cache": len(canonical_rows),
        "insufficient_conformers": len(canonical_rows) < limit,
        "no_fill": True, "no_retry": True, "new_QM_calls": 0,
        "PM7_pointer": None, "PM7_HOF": None, "PM7_stereo_reference": None,
        "PM7_RMSD": None, "cache_state": cache["state"], "cache_complete": cache["complete"]}
    if canonical_rows:
        kernel.attach(cache)
    for i in range(len(previous_rows), min(limit, len(canonical_rows))):
        row = copy.deepcopy(canonical_rows[i])
        row["conformer_id"] = i
        row["coordinate_sha256"] = sha(b"".join(struct.pack("<d", float(v)) for p in row["coordinates"] for v in p))
        emit({"phase": "descriptor_intent", "conformer_id": i,
              "geometry_sha256": row["geometry_sha256"]})
        try:
            row["D3"], row["D3_issues"] = kernel.d3(row)
        except Exception as exc:
            row["D3"] = {k: None for k in ("PMI1", "PMI2", "PMI3", "PBF_A", "volume_A3", "SASA_total_A2", "SASA_atom_A2")}
            row["D3_issues"] = [type(exc).__name__ + ": " + str(exc)]
        packet["conformers"].append(row)
        emit({"phase": "descriptor_return", "conformer": row})
    packet["orders"] = (kernel.orders(packet["conformers"], cache["molecule_id"], RECIPE["ordering_seed"])
        if packet["conformers"] else {"fixed_random": [], "energy": [], "diversity": []})
    packet["generation_order"] = [r["conformer_id"] for r in packet["conformers"]]
    packet["state"] = "SUCCESS" if len(packet["conformers"]) == limit else cache["state"] if not canonical_rows else "INSUFFICIENT_UNIQUE_CONFORMERS"
    if cache.get('source_contract_hold'):
        packet['state']='SOURCE_INTEGRITY_HOLD'
    elif not cache['complete']:
        packet['state']='PARTIAL_NATIVE_CANDIDATE_POOL_ACTUAL_CONFORMERS_RETAINED'
    packet["packet_content_sha256"] = sha(canonical(packet))
    emit({"phase": "packet_closed", "packet": packet})
    return packet