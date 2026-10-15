"""Root-executed all-source downstream materializer; no model or score selection.

Construction is target-free. Original role bytes and source/member identity
joins close before selected target decoding. Numeric targets are written only
to bounded physical binary files. Malformed annotations remain explicit errors
and prevent READY publication; seven native-geometry failures remain members.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import io
import math
import os
from pathlib import Path
import resource
import signal
import socket
import struct
import subprocess
import sys
import time

from downstream_binding_data import (CONTRACT_SCHEMA, DATASETS, RECORD_MAGIC, ROLES, SCHEMA,
    canonical, check_seal, encoded, frame_hash, json_input, loads, raw_binding, record_bytes,
    require, seal, verify_binding)

COUNTS = {"qm7": 7165, "qm9": 133885, "cyp_isoform": 2003, "az_exactsom": 109,
          "expansionrx_train": 5326, "expansionrx_test": 2282}
NUMERIC_RECIPE = "strict_ascii_scalar_nan_inf_unknown_finite_fp32_v1"
MASK_DOMAIN = "phase1_source_native_candidate_and_supervision_mask_v1"
AZ_MARKER_SOURCE_SHA256 = "18a563674711e4b2e2f0be9dc149261fed2e6e17fda4f1af0cc9901ac7b9f536"


class Budget:
    def __init__(self, caps, output):
        self.started, self.caps, self.output = time.monotonic(), caps, output
        self.finalizing = False
        signal.signal(signal.SIGALRM, lambda *_: os._exit(124))
        signal.setitimer(signal.ITIMER_REAL, caps["absolute_seconds"])
        self.last = 0.0

    def check(self):
        elapsed = time.monotonic() - self.started
        require(elapsed <= self.caps["absolute_seconds"] and (self.finalizing or elapsed <= self.caps["work_seconds"]),
                "Materialization deadline exceeded")
        require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= self.caps["rss_bytes"], "RSS cap exceeded")
        if elapsed - self.last >= 10:
            size = 0
            for folder, dirs, names in os.walk(self.output, followlinks=False):
                require(all(not Path(folder, d).is_symlink() for d in dirs), "Output directory symlink unsupported")
                for name in names:
                    p = Path(folder, name)
                    require(not p.is_symlink() and p.is_file(), "Output ordinary file required")
                    size += p.stat().st_size
            require(size <= self.caps["output_bytes"], "Output cap exceeded")
            self.last = elapsed


def publish(output, name, value, budget):
    budget.check()
    raw = encoded(value) + b"\n"
    require(len(raw) <= 512 * 1024**2, "Published metadata cap exceeded")
    path = output / name
    with path.open("xb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return raw_binding(path, budget.check)


def jsonl(ref, *, maximum_rows, check):
    verify_binding(ref, check)
    rows, digest, size = [], hashlib.sha256(), 0
    with Path(ref["path"]).open("rb") as stream:
        for line in stream:
            check()
            require(line.endswith(b"\n") and len(line) <= 2 * 1024**2 and len(rows) < maximum_rows,
                    "Closed source metadata row/count cap exceeded")
            digest.update(line); size += len(line); rows.append(loads(line))
    require(size == ref["bytes"] and digest.hexdigest() == ref["sha256"], "JSONL changed during ingestion")
    return rows


def artifact_input(summary, suffix):
    matches = [v for k, v in summary["inputs"].items() if k.endswith(suffix)]
    require(len(matches) == 1, "Original source artifact is not uniquely bound")
    return matches[0]


def closed_som_ledger_binding(ref, *, name, summary_ref, check=lambda: None):
    """Project only four old closed descriptors; preserve their path/SHA/rows."""
    require(name in ("cyp_sources", "az_sources", "cyp_folds", "az_folds")
            and type(ref) is dict and set(ref) == {"path", "rows", "sha256"}
            and type(ref["path"]) is str and Path(ref["path"]).is_absolute()
            and Path(ref["path"]).name == name + ".jsonl"
            and Path(ref["path"]).parent == Path(summary_ref["path"]).parent
            and type(ref["rows"]) is int and 0 < ref["rows"] <= 3000
            and type(ref["sha256"]) is str and len(ref["sha256"]) == 64
            and all(c in "0123456789abcdef" for c in ref["sha256"]),
            "Exact legacy four-ledger source descriptor required")
    actual = raw_binding(ref["path"], check)
    require(actual["path"] == ref["path"] and actual["sha256"] == ref["sha256"],
            "Historical ledger path or raw SHA differs during size observation")
    return actual


class OriginalMembership:
    """Consume existing membership exports, verify every old role CSV; do not split."""
    def __init__(self, protocol, summary_ref, check):
        self.summary_ref, self.inputs = summary_ref, [summary_ref]
        self.summary = json_input(summary_ref, check=check)
        s = self.summary
        require(s.get("schema_version") == "phase1_ordered_source_membership_execution_v1"
                and s.get("complete") is True and s["status"] == "COMPLETE_TARGET_FREE_MEMBERSHIP_EXPORT"
                and s["target_values_decoded"] is False and s["ordered_counts"] == COUNTS,
                "Closed full original membership required")
        manifest_ref = s["artifacts"]["membership_manifest.json"]
        self.manifest = json_input(manifest_ref, check=check); self.inputs.append(manifest_ref)
        require(self.manifest["ordered_counts"] == COUNTS and self.manifest["target_values_decoded"] is False,
                "Original membership manifest count/state differs")
        scope_ref = self.manifest["scientific_scope_choices"]
        scope = json_input(scope_ref, check=check); self.inputs.append(scope_ref)
        require(all(scope[k] == protocol["downstream"]["scope_clarification"][k]
                    for k in ("scaffold_rotation", "expansionrx")), "Original scope choices differ from frozen science")
        self.rows = {key: [] for key in COUNTS}
        self.inputs.append(s["artifacts"]["members.jsonl"])
        for row in jsonl(self.inputs[-1], maximum_rows=150771, check=check):
            dataset = row["dataset"]
            bucket = "expansionrx_" + row["declared_role"] if dataset == "expansionrx" else dataset
            require(bucket in self.rows and row["member_index"] == len(self.rows[bucket])
                    and type(row["member_index"]) is int and row["label_masks"] == "NOT_MATERIALIZED"
                    and type(row["source_frame"]) is dict and type(row["geometry_artifact_ref"]) is dict,
                    "Original member order/source/geometry schema differs")
            if dataset != "expansionrx":
                require(type(row["fold"]) is int and 0 <= row["fold"] < 10, "Original fold invalid")
            self.rows[bucket].append(row)
        require({k: len(v) for k, v in self.rows.items()} == COUNTS
                and sum(len(v) for v in self.rows.values()) == s["closed_member_rows"] == 150770,
                "Full original member conservation differs")
        for bucket, rows in self.rows.items():
            require(len({r["member_uid"] for r in rows}) == len(rows), "Original member UID duplicate")
        require(sum(r["inchikey"] is None for r in self.rows["qm7"]) == 25,
                "Original unresolved QM7 identity inventory changed")
        self.views, self.view_refs = {}, {}
        for entry in s["rotations"]:
            check()
            dataset, fold, role = entry["dataset"], entry["outer_test_fold"], entry["role"]
            require(dataset in DATASETS[:-1] and type(fold) is int and 0 <= fold < 10 and role in ROLES,
                    "Unknown original role/fold")
            matches = [ref for ref in s["artifacts"].values() if ref["path"] == entry["path"]]
            require(len(matches) == 1, "Role artifact not uniquely byte-bound")
            ref = matches[0]; verify_binding(ref, check); self.inputs.append(ref)
            raw = Path(ref["path"]).read_bytes()
            table = list(csv.reader(io.StringIO(raw.decode("utf-8"), newline="")))
            require(table and table[0] == ["member_index", "fold"] and all(len(r) == 2
                    and all(v.isascii() and v.isdecimal() for v in r) for r in table[1:]), "Role CSV columns invalid")
            expected = [r["member_index"] for r in self.rows[dataset] if
                (r["fold"] == fold if role == "test" else r["fold"] == (fold + 1) % 10
                 if role == "train_inner_validation" else r["fold"] not in (fold, (fold + 1) % 10))]
            require([(int(r[0]), int(r[1])) for r in table[1:]] == [(i, self.rows[dataset][i]["fold"]) for i in expected]
                    and len(expected) == entry["rows"] and canonical(expected) == entry["ordered_member_indices_sha256"],
                    "Actual original role membership/order differs")
            key = dataset, str(fold), role
            require(key not in self.views, "Duplicate original role CSV")
            self.views[key], self.view_refs[key] = expected, ref
        require(len(self.views) == 120, "All four original ten-rotation inventories required")
        for side in ("train", "test"):
            bucket = "expansionrx_" + side
            ref = s["artifacts"][bucket + "_indices.json"]
            value = json_input(ref, check=check); self.inputs.append(ref)
            require(value["ordered_member_indices"] == list(range(COUNTS[bucket]))
                    and value["role"] == side and value["source_order_preserved"] is True,
                    "Original official Expansion row order differs")
            offset = 0 if side == "train" else COUNTS["expansionrx_train"]
            self.views["expansionrx", "official", side] = [offset+i for i in value["ordered_member_indices"]]
            self.view_refs["expansionrx", "official", side] = ref
        self.views["expansionrx", "official", "train_inner_validation"] = []

    def verify_unchanged(self, check):
        for ref in self.inputs:
            verify_binding(ref, check)


def observed_scalar(raw, numeric_pattern):
    require(len(raw) <= 4096, "Selected scalar exceeds cap")
    text = raw.decode("utf-8")
    require(text.isascii(), "Selected numeric scalar requires ASCII")
    value = text.strip(" \t\r\n\v\f")
    if not value:
        return float("nan"), False
    require(numeric_pattern.fullmatch(value) is not None, "Malformed selected numeric scalar")
    try:
        decimal = Decimal(value)
        if not decimal.is_finite():
            return float("nan"), False
        binary64 = float(decimal)
        require(math.isfinite(binary64), "Finite target overflows FP64")
        binary32 = struct.unpack("<f", struct.pack("<f", binary64))[0]
        require(math.isfinite(binary32), "Finite target overflows FP32")
        return float(binary32), True
    except (InvalidOperation, OverflowError, struct.error) as exc:
        raise ValueError("Selected numeric transport failed") from exc


def primary_or_absence(record, records):
    block = record.structural_text.encode("utf-8")
    require(record.opaque_frame.startswith(block), "Native structure is not physical frame prefix")
    count = sum(bool((h := records._PROPERTY.fullmatch(line.rstrip(b"\r\n"))) is not None
                     and h.group(1) == b"PRIMARY_SOM") for line in record.opaque_frame[len(block):].splitlines(keepends=True))
    require(count <= 1, "Duplicate PRIMARY cannot become unknown")
    if count:
        text, proof = records._primary_property(record)
        return text, {**proof, "property_present": True}
    return None, seal({"schema_version": "phase1_cyp_property_absence_v1", "property_name": "PRIMARY_SOM",
        "property_present": False, "source_file_sha256": record.provenance["source_file_sha256"],
        "source_record_1based": record.provenance["source_record_1based"],
        "raw_frame_sha256": record.provenance["raw_frame_sha256"], "structural_sha256": record.provenance["structural_sha256"],
        "property_values_decoded": False, "missing_is_not_present_empty": True}, "property_presence_receipt_sha256")


def join_som(member, record, store):
    frame, geom, p = member["source_frame"], member["geometry_artifact_ref"], record.provenance
    raw = frame["source_file"]
    require(record.member["sample_uid"] == member["member_uid"] and record.member["sample_id"] == member["sample_id"]
            and record.member["fold"] == member["fold"] and record.structure.identity.inchikey == member["inchikey"]
            and p["dataset"] == member["dataset"] and frame["record_id"] == record.record_id
            and p["source_record_1based"] == frame["source_record_1based"]
            and Path(raw["path"]).name == p["source_file"] and p["source_file_sha256"] == raw["sha256"]
            and store.source_bindings[p["source_file"]]["bytes"] == raw["bytes"]
            and p["structural_sha256"] == frame["structure_sha256"]
            and geom["record_id"] == record.record_id and geom["native_n_atoms"] == record.structure.n_atoms,
            "Actual source/native/member join failed before annotation decode")


def az_exact_or_verified_marker(groups, flags, record, member, fields, parser, n_author_atoms):
    """One physically pinned source marker; the pure grammar stays unchanged."""
    if groups == "['none']" and flags == "['1']":
        p = record.provenance
        require(record.record_id == "az:Cmpd36" and member["member_uid"] == "az::Cmpd36"
                and member["member_index"] == 6 and member["fold"] == 0
                and p["source_file"] == "az_120_compounds.csv" and p["source_record_1based"] == 36
                and p["source_file_sha256"] == AZ_MARKER_SOURCE_SHA256
                and record.structure.n_atoms == n_author_atoms == 37,
                "AZ marker requires its exact closed physical source/member/native association")
        return None, "SOURCE_NONE_MARKER_UNKNOWN", seal({
            "schema_version": "phase1_az_verified_single_source_empty_marker_v1",
            "source_file_sha256": AZ_MARKER_SOURCE_SHA256, "record_id": record.record_id,
            "member_uid": member["member_uid"], "source_record_1based": 36,
            "native_atom_count": 37, "original_literal_groups": groups, "original_literal_flags": flags,
            "complete_selected_field_bytes": deepcopy(fields), "exact_author_atom_ids": [],
            "policy": "frozen missing_or_empty_exact_policy=preserve_unknown",
            "supervision": "all false; targets unknown NaN; candidates native-complete",
            "field_present": True, "not_present_empty_or_missing_property": True,
            "chemical_negative_or_annotation_completeness_truth_verified": False,
            "pure_strict_parser_changed": False, "literal_author_loader_reproduced": False,
            "prior_failed_strict_execution_reclassified": False})
    annotation = parser(groups, flags, n_author_atoms=n_author_atoms)
    return annotation, annotation.annotation_state, None


def closed_geometry_kind(status, basis):
    """Project only the three closed source/status pairs to historical kind."""
    require(type(status) is str and type(basis) is str,
            "Closed geometry status and basis must be literal strings")
    kinds = {("GEOMETRY_READY", "ORIGINAL_SOURCE_3D"): "original_source_3d",
             ("GEOMETRY_READY", "SAVED_GENERATED_CANDIDATE"): "cached_generated",
             ("NOT_READY", "SAVED_GENERATED_CANDIDATE"): "not_ready"}
    require((status, basis) in kinds, "Unexpected closed geometry status/basis pair")
    return kinds[(status, basis)]


def som_payload(member, store, candidates, tasks, modules):
    records, Chem, rdBase, cyp_map, decode, az_map, parse_az = modules
    record = store.get(member["source_frame"]["record_id"]); join_som(member, record, store)
    sample = records.materialize_geometry(record, candidates=candidates, source_units="angstrom")
    expected = member["geometry_artifact_ref"]
    require(sample.status == expected["status"] and closed_geometry_kind(sample.status, sample.provenance["geometry_basis"]) == expected["kind"],
            "Actual geometry availability differs before annotation decoding")
    geometry = sample.geometry
    if geometry is not None:
        require(geometry.provenance["geometry_provenance_sha256"] == expected["geometry_provenance_sha256"]
                and geometry.provenance["encoder_tensor_hashes"] == expected["encoder_tensor_hashes"],
                "Actual closed geometry receipt/tensors differ")
    n, p = record.structure.n_atoms, record.provenance
    original = record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
    targets = [[float("nan")] * len(tasks) for _ in range(n)]
    candidate, supervision = [[False] * len(tasks) for _ in range(n)], [[False] * len(tasks) for _ in range(n)]
    try:
        if member["dataset"] == "cyp_isoform":
            with rdBase.BlockLogs():
                author = next(Chem.ForwardSDMolSupplier(io.BytesIO(record.structural_text.encode("utf-8") + b"\n$$$$\n")), None)
            require(author is not None, "Independent default author supplier failed")
            mapping = cyp_map(record.structure.mol, author, source_file=p["source_file"],
                source_file_sha256=p["source_file_sha256"], source_record_1based=p["source_record_1based"],
                source_block_sha256=p["structural_sha256"])
            text, fields = primary_or_absence(record, records)
            column = tasks.index(p["source_file"][:-4])
            annotation = decode(text, mapping, isoform=tasks[column], empty_policy="preserve_unknown") if fields["property_present"] else None
            for i, author_id in enumerate(mapping.native_to_author):
                candidate[i][column] = author_id is not None
                if annotation is not None and annotation.supervision_mask[i]:
                    supervision[i][column] = True; targets[i][column] = float(annotation.labels[i])
            state = annotation.annotation_state if annotation is not None and hasattr(annotation, "annotation_state") else (
                annotation.provenance["annotation_state"] if annotation is not None else "MISSING_PROPERTY_UNKNOWN")
        else:
            mapping = az_map(record.structure.mol, record.structural_text, source_file=p["source_file"],
                source_file_sha256=p["source_file_sha256"], source_record_1based=p["source_record_1based"],
                raw_frame_sha256=p["raw_frame_sha256"], source_smiles_sha256=p["structural_sha256"])
            groups, flags, fields = records._az_annotation_fields(record, store._csv_headers[p["source_file"]])
            # Empty textual CSV fields are not fabricated literal lists: absence
            # is declared only for two wholly blank fields, with actual hashes.
            marker = None
            if not groups.strip(" \t\r\n\v\f") and not flags.strip(" \t\r\n\v\f"):
                annotation, state = None, "MISSING_FIELDS_UNKNOWN"
            else:
                annotation, state, marker = az_exact_or_verified_marker(groups, flags, record, member, fields,
                    parse_az, len(mapping.author_to_native))
            positive = set(mapping.author_to_native[i] for i in annotation.exact_author_ids) if annotation else set()
            for i in range(n):
                candidate[i][0] = True
                if positive:
                    supervision[i][0] = True; targets[i][0] = float(i in positive)
        proof = {"schema_version": "phase1_same_source_downstream_labels_v1", "record_id": record.record_id,
            "record_binding_sha256": p["record_binding_sha256"], "raw_frame_sha256": p["raw_frame_sha256"],
            "structural_sha256": p["structural_sha256"], "selected_field_bytes": fields,
            "mapping_sha256": canonical(mapping.provenance), "annotation_state": state,
            "annotation_receipt_sha256": canonical(annotation.provenance) if annotation is not None else None,
            "source_member_geometry_join_before_target_decode": True,
            "chemical_negative_or_annotation_completeness_truth_verified": False,
            "geometry_provenance": deepcopy(geometry.provenance) if geometry else None,
            "native_source_graph_binding": deepcopy(sample.native_source_graph_binding)}
        if member["dataset"] == "az_exactsom":
            proof["verified_source_marker"] = marker
        coordinates = (geometry.native_coordinates_float64.tolist() if hasattr(geometry, "native_coordinates_float64")
                       else record.structure.pos_angstrom) if geometry else None
        return record.structure.x, coordinates, targets, candidate, supervision, state, seal(proof)
    finally:
        require(record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == original,
                "Native source molecule changed during annotation extraction")


def moments(rows, indices, tasks):
    count, mean, m2 = [0]*tasks, [0.0]*tasks, [0.0]*tasks
    for i in indices:
        row = rows[i]
        if not row["geometry_ready"] or row["annotation_state"] == "MALFORMED":
            continue
        for t, observed in enumerate(row["_supervision"][0]):
            if observed:
                value = row["_targets"][0][t]; count[t] += 1
                delta = value - mean[t]; mean[t] += delta/count[t]; m2[t] += delta*(value-mean[t])
    means = [mean[i] if count[i] else None for i in range(tasks)]
    scales = [(math.sqrt(max(0.0, m2[i]/count[i])) or 1.0) if count[i] else None for i in range(tasks)]
    return count, means, scales


def ordered_cell_hash(endpoint_id, declaration, fold_id, members, indices, column, membership_raw_sha):
    samples, masks = hashlib.sha256(), hashlib.sha256()
    dataset = members[0]["dataset_id"] if members else declaration["dataset"]
    common = {"dataset": dataset, "endpoint": endpoint_id, "fold_id": fold_id,
              "membership_manifest_raw_sha256": membership_raw_sha, "units": declaration["units"]}
    frame_hash(samples, encoded({**common, "domain": "phase1_complete_original_cell_members_v1"}))
    frame_hash(masks, encoded({**common, "domain": MASK_DOMAIN,
        "packing": "per member column, native ID ascending, little-endian bits, zero tail padding"}))
    def packed(values):
        return sum(int(v) << i for i, v in enumerate(values)).to_bytes((len(values)+7)//8, "little")
    complete = True
    for i in indices:
        row = members[i]
        ident = encoded({"member_index": row["source_member_index"], "member_uid": row["member_uid"]})
        frame_hash(samples, ident); frame_hash(masks, ident)
        if row["annotation_state"] == "MALFORMED":
            complete = False; continue
        n = row["target_rows"]
        frame_hash(masks, struct.pack("<I", n))
        frame_hash(masks, packed([v[column] for v in row["_candidate"]]))
        frame_hash(masks, packed([v[column] for v in row["_supervision"]]))
    return samples.hexdigest(), masks.hexdigest() if complete else None, complete


def run(request, output, budget):
    project = Path(request["project"]).absolute(); sys.path.insert(0, str(project)); sys.dont_write_bytecode = True
    from phychem_mfm.training.checkpoint import source_provenance
    from phychem_mfm.phase1 import downstream_source_records as records
    from phychem_mfm.phase1.downstream_structures import read_xyz_structure
    from phychem_mfm.phase1.som_atom_mapping import build_cyp_author_atom_mapping
    from phychem_mfm.phase1.som_annotation import decode_cyp_primary_annotation, SomAnnotationError
    from phychem_mfm.phase1.az_atom_mapping import build_az_author_atom_mapping
    from phychem_mfm.phase1.az_annotation import parse_az_exact_groups, AZAnnotationError
    from phychem_mfm.phase1.downstream_readout import SourceAlignedH0Readout, SourceAlignedLinearGraphReadout
    from rdkit import Chem, rdBase
    import torch
    source_before = source_provenance(project)
    source_receipt = json_input(request["source_receipt"], check=budget.check)
    actual = source_receipt["actual_source"]
    require(source_before["source_sha256"] == actual["source_sha256"] and source_before["git_commit"] == actual["git_commit"],
            "Actual downstream source differs from root receipt")
    protocol = json_input(request["protocol"], check=budget.check); check_seal(protocol)
    require(protocol["state"] == "frozen" and protocol["schema_version"] == "phase1_full_corpus_pretraining_v1",
            "Frozen current scientific protocol required")
    membership = OriginalMembership(protocol, request["membership_summary"], budget.check)
    definitions = {r["dataset_id"]: r for r in protocol["downstream"]["dataset_definitions"]}
    require(set(definitions) == set(DATASETS), "Frozen five-dataset scope differs")
    tasks = {k: tuple(t["task_id"] if type(t) is dict else t for t in d["tasks"]) for k, d in definitions.items()}
    require(tasks["cyp_isoform"] == ("1A2", "2A6", "2B6", "2C19", "2C8", "2C9", "2D6", "2E1", "3A4")
            and definitions["cyp_isoform"]["missing_property_policy"] == definitions["cyp_isoform"]["empty_property_policy"] == "preserve_unknown"
            and definitions["az_exactsom"]["label_policy"] == "strict_exact_binary_set", "Frozen atom annotation rule differs")
    graph_ref = request["graph_join_helper"]; verify_binding(graph_ref, budget.check)
    spec = importlib.util.spec_from_file_location("bound_graph_source_join", graph_ref["path"])
    helper = importlib.util.module_from_spec(spec); sys.modules[spec.name] = helper; spec.loader.exec_module(helper)
    som_ref = artifact_input(membership.summary, "full_som_structures_4511893/summary.json")
    som = json_input(som_ref, check=budget.check)
    source_rows, member_rows, ledger_bindings = [], [], {}
    for name in ("cyp_sources", "az_sources", "cyp_folds", "az_folds"):
        legacy = som["ledgers"][name]
        ref = closed_som_ledger_binding(legacy, name=name, summary_ref=som_ref, check=budget.check)
        rows = jsonl(ref, maximum_rows=3000, check=budget.check)
        require(len(rows) == legacy["rows"], "Closed historical ledger row count differs")
        (source_rows if name.endswith("sources") else member_rows).extend(rows)
        membership.inputs.append(ref)
        ledger_bindings[name] = {"legacy_descriptor": deepcopy(legacy), "actual_raw_binding": ref,
                                 "observed_rows": len(rows)}
    ledger_projection = publish(output, "legacy_som_ledger_raw_bindings.json", seal({
        "schema_version": "phase1_legacy_som_ledger_raw_binding_projection_v1", "source_summary": som_ref,
        "ledgers": ledger_bindings, "raw_sizes_observed_in_current_execution": True,
        "historical_paths_raw_hashes_and_rows_preserved": True,
        "target_annotations_decoded_by_this_bridge": False}), budget)
    raw_sources = [b for k, b in som["sources"].items() if k == "az_raw" or k.startswith("cyp_raw/")]
    require(len(raw_sources) == 10, "Exact source10 raw-file inventory required")
    store = records.SourceRecordStore(request["benchmark_root"], source_files={Path(b["path"]).name:
        {"bytes": b["bytes"], "sha256": b["sha256"]} for b in raw_sources}, source_rows=source_rows, member_rows=member_rows)
    candidate_ref = artifact_input(membership.summary, "missing_geometry_stage34_4511904/candidate_records.jsonl")
    candidates = records.ClosedCandidateLedger(candidate_ref["path"], expected_sha256=candidate_ref["sha256"])
    membership.inputs.extend([som_ref, candidate_ref, *raw_sources])
    expansion = json_input(request["expansion_geometry"], check=budget.check); check_seal(expansion)
    require(expansion["complete"] is True and expansion["target_fields_decoded"] is False
            and expansion["membership_summary_sha256"] == request["membership_summary"]["sha256"],
            "Closed native-only Expansion geometry inventory required")
    exp_rows = {r["member_uid"]: r for r in expansion["records"]}
    require(len(exp_rows) == COUNTS["expansionrx_train"] + COUNTS["expansionrx_test"], "Expansion full source coverage differs")
    modules = records, Chem, rdBase, build_cyp_author_atom_mapping, decode_cyp_primary_annotation, build_az_author_atom_mapping, parse_az_exact_groups
    all_rows, by_dataset, errors, exposures = [], {k: [] for k in DATASETS}, [], Counter()
    payload_path = output / "records.bin"
    with payload_path.open("xb") as payload:
        payload.write(RECORD_MAGIC)
        for bucket, originals in membership.rows.items():
            dataset = "expansionrx" if bucket.startswith("expansionrx_") else bucket
            columns = tasks[dataset]
            if dataset in ("qm7", "qm9", "expansionrx"):
                ref = originals[0]["assignment_source"] if dataset in ("qm7", "qm9") else originals[0]["source_frame"]["source_file"]
                verify_binding(ref, budget.check); membership.inputs.append(ref)
                content = Path(ref["path"]).read_bytes(); frames = records._csv_rows(content, with_spans=True)
                _, _, header, _ = next(frames); names = tuple(helper._text(v) for v in header)
                require(len(names) == len(set(names)) and all(t in names for t in columns), "Frozen selected CSV fields absent")
            for ordinal, member in enumerate(originals, 1):
                budget.check(); dataset_index = len(by_dataset[dataset]); state, error = None, None
                if dataset in ("qm7", "qm9", "expansionrx"):
                    start, end, fields, spans = next(frames)
                    require(len(fields) == len(names), "Complete CSV row column count differs")
                    joined = helper._joined_member(bucket, member, ordinal, fields, names, spans, start, end, content, ref)
                    if dataset in ("qm7", "qm9"):
                        f = member["source_frame"]
                        verify_binding(f, budget.check)
                        native = read_xyz_structure(f["path"], units=definitions[dataset]["source_coordinate_unit"])
                        require(native.n_atoms == f["native_n_atoms"] and native.provenance["source_atomic_number_order_hash"] == f["source_native_order_sha256"],
                                "Original XYZ native row/order binding differs before targets")
                        old_geometry = member["geometry_artifact_ref"]
                        require(canonical(native.source_atom_map) == old_geometry["source_atom_map_hash"]
                                and canonical({"source_units": definitions[dataset]["source_coordinate_unit"],
                                    "coordinate_scale": native.provenance["coordinate_scale"],
                                    "atomic_numbers": native.atomic_numbers, "pos_angstrom": native.pos_angstrom})
                                    == old_geometry["coordinate_projection_hash"],
                                "Existing native XYZ map/coordinate projection differs")
                        x, coords, geometry_proof = native.x, native.pos_angstrom, native.provenance
                    else:
                        g = exp_rows[member["member_uid"]]; check_seal(g)
                        require(g["member_row_sha256"] == canonical(member), "Expansion geometry belongs to different source member")
                        x, coords, geometry_proof = g["native_x"], g["native_coordinates_float64"], g
                    values = [observed_scalar(fields[names.index(t)], helper.NUMERIC) for t in columns]
                    targets = [[v for v, _ in values]]; candidate = [[True]*len(columns)]; supervision = [[s for _, s in values]]
                    state = "OBSERVED_OR_UNKNOWN_NUMERIC"
                    proof = seal({"source_join": joined, "source_file": ref, "raw_frame_sha256": hashlib.sha256(content[start:end]).hexdigest(),
                        "target_field_byte_hashes": {t: hashlib.sha256(fields[names.index(t)]).hexdigest() for t in columns},
                        "selected_target_numeric_recipe": NUMERIC_RECIPE, "target_conversion": "none",
                        "native_geometry": deepcopy(geometry_proof), "source_member_geometry_join_before_target_decode": True})
                else:
                    try:
                        x, coords, targets, candidate, supervision, state, proof = som_payload(member, store, candidates, columns, modules)
                    except (SomAnnotationError, AZAnnotationError) as exc:
                        # Keep the original row and actual failure; no unknown-label success.
                        record = store.get(member["source_frame"]["record_id"]); join_som(member, record, store)
                        sample = records.materialize_geometry(record, candidates=candidates, source_units="angstrom")
                        x = record.structure.x
                        coords = (sample.geometry.native_coordinates_float64.tolist() if hasattr(sample.geometry, "native_coordinates_float64")
                                  else record.structure.pos_angstrom) if sample.geometry else None
                        targets = [[float("nan")]*len(columns) for _ in x]
                        candidate = [[False]*len(columns) for _ in x]; supervision = deepcopy(candidate)
                        state = "MALFORMED"; error = type(exc).__name__
                        proof = seal({"source_record": deepcopy(record.provenance), "annotation_state": state,
                            "failure_class": error, "failure_message_sha256": hashlib.sha256(str(exc).encode()).hexdigest(),
                            "malformed_is_not_unknown_or_negative": True, "selected_target_values_written": False})
                        errors.append({"dataset": dataset, "member_index": dataset_index, "member_uid": member["member_uid"],
                                       "failure_class": error, "failure_message_sha256": proof["failure_message_sha256"]})
                require(all(t in (0.0, 1.0) for tr, sr in zip(targets, supervision) for t, observed in zip(tr, sr) if observed)
                        if definitions[dataset]["output_level"] == "atom" else True, "Observed binary set has another value")
                raw = record_bytes(tuple(x), coords, targets, candidate, supervision); offset = payload.tell(); payload.write(raw)
                row = {"dataset_id": dataset, "member_index": dataset_index, "source_member_index": member["member_index"],
                    "member_uid": member["member_uid"], "source_fold": member.get("fold"), "declared_role": member.get("declared_role"),
                    "original_member_row_sha256": canonical(member), "native_n_atoms": len(x), "target_rows": len(targets),
                    "tasks": columns, "geometry_ready": coords is not None, "annotation_state": state,
                    "unavailable_reason": error or (None if coords is not None else "FIXED_GEOMETRY_NOT_READY"),
                    "offset": offset, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "provenance": proof,
                    "_targets": targets, "_candidate": candidate, "_supervision": supervision}
                by_dataset[dataset].append(row); all_rows.append(row); exposures[dataset] += 1
            if dataset in ("qm7", "qm9", "expansionrx"):
                require(next(frames, None) is None, "CSV contains additional original rows")
                verify_binding(ref, budget.check)
        payload.flush(); os.fsync(payload.fileno())
    payload_ref = raw_binding(payload_path, budget.check)
    with payload_path.open("rb") as stream:
        require(stream.read(len(RECORD_MAGIC)) == RECORD_MAGIC, "Closed physical payload magic differs")
        for row in all_rows:
            budget.check()
            require(stream.tell() == row["offset"], "Closed physical record order/offset differs")
            raw = stream.read(row["bytes"])
            require(len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"],
                    "Closed physical native record bytes differ")
        require(stream.read(1) == b"", "Closed physical records have a trailing payload")
    contracts = []
    # Readout constructors consume RNG: preserve caller/global state exactly.
    rng = torch.get_rng_state().clone()
    try:
        configs = {}
        for dataset, definition in definitions.items():
            level, count = definition["output_level"], len(tasks[dataset])
            configs[dataset] = {"main": SourceAlignedH0Readout(384, count, output_level=level,
                hidden_dim=64, atom_layers=1, pooling="mean" if level == "graph" else None).config_dict()}
            if level == "graph":
                configs[dataset]["aux"] = SourceAlignedLinearGraphReadout(384, count, pooling="mean").config_dict()
    finally:
        torch.set_rng_state(rng)
    bridge = json_input(request["readout_bridge"], check=budget.check); check_seal(bridge)
    require(bridge["schema_version"] == "phase1_frozen_input_dimension_actual_readout_metadata_bridge_v1"
            and bridge["complete"] is True and bridge["protocol_content_sha256"] == protocol["content_sha256"]
            and bridge["scientific_readout_rules_changed"] is False and bridge["targets_or_dataset_read"] is False,
            "Actual384 readout metadata bridge differs from frozen rule")
    for dataset, declarations in configs.items():
        require(declarations["main"] == bridge["configs"][dataset]["main"]
                and canonical(declarations["main"]) == bridge["configs"][dataset]["main_config_sha256"],
                "Actual source main config differs from independently closed384 bridge")
        if "aux" in declarations:
            require(declarations["aux"] == bridge["configs"][dataset]["auxiliary"]
                    and canonical(declarations["aux"]) == bridge["configs"][dataset]["auxiliary_config_sha256"],
                    "Actual source auxiliary config differs from independently closed384 bridge")
    readout_refs = {dataset: {role: publish(output, f"readout.{dataset}.{role}.json", config, budget)
                    for role, config in declarations.items()} for dataset, declarations in configs.items()}
    for dataset in DATASETS:
        definition, rows = definitions[dataset], by_dataset[dataset]
        folds = ("official",) if dataset == "expansionrx" else tuple(str(i) for i in range(10))
        for fold in folds:
            budget.check(); indices = {r: membership.views[dataset, fold, r] for r in ROLES}
            train_hash = canonical([rows[i]["sha256"] for i in indices["train"]])
            split_hash = canonical({r: [rows[i]["member_uid"] for i in indices[r]] for r in ROLES})
            if definition["output_level"] == "graph":
                n, means, scales = moments(rows, indices["train"], len(tasks[dataset])); kind = "train_affine"
            else:
                n = [sum(sum(int(v[t]) for v in rows[i]["_supervision"]) for i in indices["train"]
                         if rows[i]["geometry_ready"] and rows[i]["annotation_state"] != "MALFORMED")
                     for t in range(len(tasks[dataset]))]
                means, scales = [0.0 if v else None for v in n], [1.0 if v else None for v in n]; kind = "identity"
            units = ([t["unit"] for t in definition["tasks"]] if type(definition["tasks"][0]) is dict else
                     [protocol["downstream"]["analysis_rules"]["endpoints"][endpoint]["units"]
                      for endpoint in definition["endpoint_ids"]])
            normalization = seal({"kind": kind, "means": means, "scales": scales, "fit_scope": "train",
                "availability": [v is not None for v in means], "observed_counts": n,
                "train_data_sha256": train_hash, "split_manifest_sha256": split_hash,
                "fit_source_sha256": canonical([rows[i]["provenance"]["content_sha256"] for i in indices["train"]]),
                "recipe": "observed_ready_train_FP32_targets_FP64_Welford_population_std_zero_variance_one_v1"})
            contracts.append(seal({"schema_version": CONTRACT_SCHEMA, "dataset_id": dataset, "fold_id": fold,
                "protocol_content_sha256": protocol["content_sha256"], "original_inventory_count": len(rows),
                "tasks": tasks[dataset], "units": units, "output_level": definition["output_level"],
                "member_indices": indices, "ordered_members": {r: [rows[i]["member_uid"] for i in indices[r]] for r in ROLES},
                "normalization": normalization, "original_role_files": {r: membership.view_refs.get((dataset, fold, r)) for r in ROLES},
                "source_binding": request["membership_summary"], "mask_binding": payload_ref, "geometry_binding": payload_ref,
                "readout_binding": {role: {"config": config, "config_sha256": canonical(config), "file": readout_refs[dataset][role],
                    "config_hash_recipe": "canonical finite sorted UTF8 JSON ensure_ascii=false",
                    "file_hash_recipe": "physical raw JSON file bytes including newline"} for role, config in configs[dataset].items()},
                "optimizer": deepcopy(protocol["downstream"]["optimization_policy"]),
                "sample_set_policy": "all_original_members_then_common_ready_and_observed_training_filter",
                "annotation_complete": not any(row["annotation_state"] == "MALFORMED" for row in rows)}))
    require(len(contracts) == 41, "Complete original readout contract scope differs")
    cells, primary_count = {}, 0
    for endpoint, declaration in protocol["downstream"]["analysis_rules"]["endpoints"].items():
        prefix, task = endpoint.split(".", 1)
        dataset = {"qm7": "qm7", "qm9": "qm9", "cyp": "cyp_isoform", "az": "az_exactsom", "exp": "expansionrx"}[prefix]
        rows, column = by_dataset[dataset], tasks[dataset].index(task)
        endpoint_cells = []
        for spec_cell in declaration["cells"]:
            fold = "official" if dataset == "expansionrx" else spec_cell["fold_id"]
            idx = membership.views[dataset, fold, "test"]
            sample_sha, mask_sha, complete = ordered_cell_hash(endpoint, declaration, spec_cell["fold_id"], rows, idx, column,
                membership.summary["artifacts"]["membership_manifest.json"]["sha256"])
            endpoint_cells.append({"fold_id": spec_cell["fold_id"], "readout_seed": spec_cell["readout_seed"],
                "sample_set_sha256": sample_sha, "label_mask_sha256": mask_sha, "complete": complete})
            primary_count += 1
        cells[endpoint] = {"readout_config_sha256": canonical(configs[dataset]["main"]), "cells": endpoint_cells}
        cells[endpoint]["historical_declared_readout_config_sha256"] = declaration["readout_config_sha256"]
        cells[endpoint]["historical_reference_equals_current_physical_config"] = (
            cells[endpoint]["readout_config_sha256"] == declaration["readout_config_sha256"])
        cells[endpoint]["actual_config_binding_basis"] = "frozen input_dimension384 + unchanged readout rules + actual source constructor"
        cells[endpoint]["actual_readout_reference_bridge"] = request["readout_bridge"]
        require(protocol["downstream"]["input_dimension"] == 384 and configs[dataset]["main"]["input_dim"] == 384
                and configs[dataset]["main"]["hidden_dim"] == protocol["downstream"]["readout_policy"]["atom_hidden_dim"] == 64
                and configs[dataset]["main"]["atom_layers"] == protocol["downstream"]["readout_policy"]["atom_layers"] == 1,
                "Actual384 readout rules differ from frozen science")
    require(len(cells) == 32 and primary_count == 239, "All frozen primary endpoint/cell scope differs")
    auxiliary_cells = {}
    for task in definitions["qm9"]["tasks"][:3]:
        endpoint, column = task["endpoint_id"], tasks["qm9"].index(task["task_id"])
        entries = []
        for fold in range(10):
            sample_sha, mask_sha, complete = ordered_cell_hash(endpoint, {"units": task["unit"]}, str(fold),
                by_dataset["qm9"], membership.views["qm9", str(fold), "test"], column,
                membership.summary["artifacts"]["membership_manifest.json"]["sha256"])
            entries.append({"fold_id": str(fold), "readout_seed": 0, "sample_set_sha256": sample_sha,
                            "label_mask_sha256": mask_sha, "complete": complete})
        auxiliary_cells[endpoint] = {"readout_config_sha256": canonical(configs["qm9"]["main"]), "cells": entries,
                                    "primary_inference": False}
    contract_ref = publish(output, "contracts.json", seal({"contracts": contracts}), budget)
    cell_ref = publish(output, "primary_cell_bindings.json", seal({"endpoints": cells, "cell_count": primary_count,
        "all_cells_complete": not errors, "mask_hash_recipe": MASK_DOMAIN,
        "auxiliary_report_endpoints": auxiliary_cells, "all_report_endpoints": 35, "all_report_cells": 269,
        "historical_512_reference_bridge": request["readout_bridge"],
        "formal_runtime_bindings_passed": False}), budget)
    clean_rows = [seal({k: v for k, v in row.items() if not k.startswith("_")}, "record_metadata_sha256") for row in all_rows]
    index_ref = publish(output, "record_index.json", seal({"records": clean_rows}), budget)
    membership.verify_unchanged(budget.check)
    for ref in (request["protocol"], request["source_receipt"], request["expansion_geometry"], request["readout_bridge"], graph_ref):
        verify_binding(ref, budget.check)
    source_after = source_provenance(project)
    require(source_after == source_before, "Actual full downstream source changed")
    complete = not errors
    manifest = seal({"schema_version": SCHEMA, "complete": complete, "annotation_complete": complete,
        "scientific_choices_changed": False, "protocol": request["protocol"], "membership_summary": request["membership_summary"],
        "formal_runner_bindings_passed": False,
        "source_before": source_before, "source_after": source_after, "input_raw_bytes_unchanged": True,
        "files": [payload_ref, contract_ref, cell_ref, index_ref, ledger_projection,
                  *[r for roles in readout_refs.values() for r in roles.values()]],
        "legacy_som_ledger_bindings": ledger_projection,
        "input_files": list({r["path"]: {k: r[k] for k in ("path", "bytes", "sha256")} for r in
            [*membership.inputs, request["protocol"], request["source_receipt"], request["expansion_geometry"], request["readout_bridge"], graph_ref]}.values()),
        "records_file": payload_ref,
        "record_index": index_ref, "contracts": contract_ref, "primary_cells": cell_ref,
        "ordered_counts": dict(exposures), "original_member_rows": 150770,
        "primary_endpoints": 32, "primary_cells_count": 239, "readout_groups": 41, "auxiliary_graph_groups": 21,
        "not_ready_retained": sum(not r["geometry_ready"] for r in all_rows), "malformed_annotations": errors,
        "outer_targets_exposed_under_frozen_rules": True, "metric_values_produced": False,
        "formal_pretraining_eligibility_unchanged": True})
    publish(output, "store_manifest.json", manifest, budget)
    budget.check(); budget.finalizing = True
    return seal({"schema_version": "phase1_downstream_materialization_execution_v1", "complete": complete,
        "status": "COMPLETE_FROZEN_RULE_DOWNSTREAM_BINDINGS" if complete else "PARTIAL_MALFORMED_ANNOTATION_RETAINED",
        "source_before": source_before, "source_after": source_after, "member_count": len(all_rows),
        "primary_cells": 239, "bound_primary_cells": sum(c["complete"] for e in cells.values() for c in e["cells"]),
        "malformed_annotations": errors, "input_raw_bytes_unchanged": True, "elapsed_seconds": time.monotonic()-budget.started,
        "store_manifest": raw_binding(output / "store_manifest.json", budget.check)})


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--request", required=True); parser.add_argument("--expected-request-sha256", required=True)
    args = parser.parse_args(); request_ref = raw_binding(args.request)
    require(request_ref["sha256"] == args.expected_request_sha256, "Actual request SHA differs")
    request = json_input(request_ref); check_seal(request)
    require(request.get("schema_version") == "phase1_frozen_downstream_materialization_request_v1"
            and request.get("state") == "READY_ACTUAL_BINDINGS"
            and str(request.get("actual_job_id")) == os.environ.get("SLURM_JOB_ID"), "Actual immutable execution request required")
    require(os.getuid() == 1278 and socket.gethostname().split(".")[0] == "compute-0-20"
            and os.environ.get("CUDA_VISIBLE_DEVICES") == "" and os.environ.get("SLURM_JOB_ID", "").isdigit(),
            "Root-owned CPU20 Slurm allocation required")
    raw = subprocess.check_output(["scontrol", "show", "job", "-o", os.environ["SLURM_JOB_ID"]], timeout=15)
    require(len(raw) <= 65536, "Allocation response cap exceeded")
    live = dict(t.split("=", 1) for t in raw.decode("ascii").split() if "=" in t)
    require(live.get("UserId") == "zixiao(1278)" and live.get("NodeList") == "compute-0-20"
            and live.get("JobState") == "RUNNING" and live.get("NumCPUs") == "16"
            and live.get("MinMemoryNode") in ("64G", "65536M", "65536MB"), "Actual owned16CPU64G allocation differs")
    output = Path(request["output_dir"]); output.mkdir(parents=True, exist_ok=False)
    budget = Budget(request["budgets"], output)
    try:
        verify_binding(request["executing_helper"], budget.check)
        require(Path(request["executing_helper"]["path"]).absolute() == Path(__file__).absolute(), "Executing helper physical path differs")
        for ref in request["implementation_files"]:
            verify_binding(ref, budget.check)
        result = run(request, output, budget); publish(output, "summary.json", result, budget)
        for ref in request["implementation_files"]:
            verify_binding(ref, budget.check)
        print(encoded({"status": result["status"], "complete": result["complete"], "member_count": result["member_count"]}).decode())
        return 0 if result["complete"] else 1
    except Exception as exc:
        budget.finalizing = True
        result = seal({"complete": False, "status": "FAILED_CLOSED", "error_class": type(exc).__name__,
            "error_message_sha256": hashlib.sha256(str(exc).encode()).hexdigest(), "elapsed_seconds": time.monotonic()-budget.started})
        if not (output / "FAILED.json").exists():
            publish(output, "FAILED.json", result, budget)
        print(encoded(result).decode()); return 1


if __name__ == "__main__":
    raise SystemExit(main())
