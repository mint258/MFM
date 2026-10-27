"""Candidate per-MID orchestration, deliberately without an executable reader.

The future CPU port owns stable-FD/full-SHA validation, 16-worker/32-pending
dispatch, resource observations, durable writer and final readback. Its sink
must fsync each append before returning. This library does not claim those
operations occurred and cannot write a COMPLETE reference manifest.
"""
from __future__ import annotations

from . import contracts as C, selection, worker, projection


def produce_mid(member, source_rows, sink, kernel, *, maximum_variants,
                maximum_variant_utf8_bytes):
    m = C.membership(member)
    C.need(m is not None, "ONLY_ACTUAL_FINAL_COMMON_MOLECULES_ENTER_PRODUCER")
    C.need(type(maximum_variants) is int and maximum_variants > 0 and
           type(maximum_variant_utf8_bytes) is int and maximum_variant_utf8_bytes > 0,
           "ROOT_REVIEWED_FINITE_VARIANT_MEMORY_BOUNDS_REQUIRED")
    variants = {}
    count = 0
    bytes_used = 0
    stopped = None
    for row in source_rows:
        s = selection.select(row)
        C.need(row["molecule_id"] == m["molecule_id"], "SOURCE_ROW_OUTSIDE_EXACT_COMMON_MID")
        count += 1
        # All records and accepted historical differences survive, including
        # repeated physical conformers. Source evidence precedes any key call.
        sink.append({"phase": "SOURCE_IDENTITY", "source_record_ordinal_within_MID": count - 1,
                     "molecule_id": m["molecule_id"], "effective_role": m["effective_role"],
                     **s})
        key = s["variant_id"]
        if key in variants:
            C.need(variants[key]["source_smiles_for_original_template"] ==
                   s["source_smiles_for_original_template"], "SOURCE_VARIANT_SHA_COLLISION_HOLD")
        elif stopped is None:
            amount = len(s["source_smiles_for_original_template"].encode("utf-8")) if key else 0
            if len(variants) + 1 > maximum_variants or bytes_used + amount > maximum_variant_utf8_bytes:
                stopped = "VARIANT_MEMORY_BOUND_REACHED_NO_MOLECULE_EXCLUDED"
            else:
                # Do not retain one representative row's historical identity:
                # every original row is already independently in SOURCE events.
                variants[key] = {k: s[k] for k in ("variant_id", "status", "source_smiles_for_original_template")}
                bytes_used += amount
    if count != m["records"]:
        stopped = "FORMAL_NATIVE_RECORD_CENSUS_CHANGED"
    if stopped is not None or not variants:
        result = {**m, "status": "HOLD", "hold_reasons": [stopped or "NO_SOURCE_RECORDS"],
                  "strict5_projection": None, "native_records_observed": count,
                  "production_or_pool_release_authorized": False}
        sink.append({"phase": "MID_HOLD", **result})
        return result
    results = []
    for ordinal, key in enumerate(sorted(variants, key=lambda v: "" if v is None else v)):
        value = worker.derive(variants[key], ordinal, kernel)
        # This durable result precedes any strict5 or future Parquet flush.
        sink.append({"phase": "GRAPH_RESULT", "molecule_id": m["molecule_id"], **value})
        results.append(value)
    result = projection.reduce_variants(m["molecule_id"], m["effective_role"], count, results)
    sink.append({"phase": "MID_REDUCTION", **result})
    return result

