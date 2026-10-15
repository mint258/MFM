#!/usr/bin/env python3
"""CPU structure-only CYP/AZ source audit; NOT_FROZEN, no target repair.

Run complete processing in a Slurm CPU allocation. Only explicitly allowed CSV
columns and SDF mol blocks are interpreted. SDF properties remain opaque bytes.
Git tree metadata may bind source versions without downloading data contents:
{repository: 'dmis-lab/ATTNSOM', commit: '<40 hex>', files:
 [{repository_path: 'cyp_dataset/1A2.sdf', git_blob_sha1: '<40 hex>', bytes: N}]}.
No members/folds are changed; raw-only IDs are reported without inferring why
historical preprocessing omitted them. Source version binding does not validate
SoM annotations, CYP H numbering, geometry suitability or formal decontamination.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import re
import signal
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rdkit import rdBase
from phychem_mfm.phase1.downstream_structures import (
    ATTNSOM_COMMIT, SOURCE_CONTRACT, read_az_raw_smiles, read_cyp_mol_block,
)
from phychem_mfm.phase1.identity import IDENTITY_POLICY, canonical_hash, molecule_identity

CYP_FILES = ("1A2.sdf", "2A6.sdf", "2B6.sdf", "2C8.sdf", "2C9.sdf",
             "2C19.sdf", "2D6.sdf", "2E1.sdf", "3A4.sdf")
FOLD_COLUMNS = frozenset({"dataset", "sample_id", "sample_uid", "compound_id", "isoform", "fold",
                          "SMILES", "scaffold_key", "exact_scaffold", "is_acyclic_key", "scaffold_found",
                          "parse_failed", "split_signature", "split_group_key", "source_sdf",
                          "SMILES_isomeric", "n_atoms", "mol_block"})
RAW_AZ_COLUMNS = frozenset({"Compound ID", "SMILES"})
BASE_COLUMNS = frozenset({"dataset", "sample_id", "sample_uid", "compound_id", "fold", "split_group_key",
                          "SMILES", "SMILES_isomeric", "n_atoms"})
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_BLOCK_BYTES = 2 * 1024 * 1024
SOURCE_CONTRACT_COMMIT = ATTNSOM_COMMIT


class AuditError(ValueError):
    pass


class BudgetExceeded(RuntimeError):
    pass


class Deadline:
    def __init__(self, seconds, clock=time.monotonic):
        self.clock, self.started, self.seconds = clock, clock(), float(seconds)

    def check(self):
        if self.clock() - self.started >= self.seconds:
            raise BudgetExceeded("Internal structure audit wall budget reached")


class Ledger:
    def __init__(self, path, stack):
        self.path, self.rows, self.digest = path, 0, hashlib.sha256()
        self.handle = stack.enter_context(path.open("xb"))

    def write(self, row):
        encoded = (json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode()
        self.handle.write(encoded)
        self.digest.update(encoded)
        self.rows += 1

    def metadata(self):
        return {"path": str(self.path.resolve()), "rows": self.rows, "sha256": self.digest.hexdigest()}


def project_columns(header, row, allowed):
    """Index only declared structure/source fields; do not collect target values."""
    result = {}
    for index, name in enumerate(header):
        if name not in allowed:
            continue
        if name in result or index >= len(row):
            raise AuditError("Duplicate or truncated structural CSV column")
        result[name] = row[index]
    return result


def csv_byte_rows(source, deadline):
    """Strict comma/quote CSV framing, without decoding any field values.

    The state machine preserves quoted CRLF/newlines and doubled quotes. A
    record's values remain bytes, including invalid UTF-8 in target columns.
    """
    if source.startswith(b"\xef\xbb\xbf"):
        source = source[3:]  # UTF-8 BOM is framing metadata, not a field value.
    state, row, field, index = "start", [], bytearray(), 0
    while index < len(source):
        if index % 65536 == 0:
            deadline.check()
        char = source[index]
        if state == "quoted":
            if char == 34:
                state = "after_quote"
            else:
                field.append(char)
        elif state == "after_quote" and char == 34:
            field.append(34)
            state = "quoted"
        elif char == 44 or char in (10, 13):
            row.append(bytes(field))
            field.clear()
            state = "start"
            if char != 44:
                yield row
                row = []
                if char == 13 and index + 1 < len(source) and source[index + 1] == 10:
                    index += 1
        elif state == "start" and char == 34:
            state = "quoted"
        elif state == "after_quote" or char == 34:
            raise AuditError("Malformed CSV quoting or bytes after closing quote")
        else:
            field.append(char)
            state = "unquoted"
        if len(field) > MAX_BLOCK_BYTES:
            raise BudgetExceeded("CSV field exceeds bounded byte limit")
        index += 1
    deadline.check()
    if state == "quoted":
        raise AuditError("Unterminated quoted CSV field")
    if row or field or state != "start":
        row.append(bytes(field))
        yield row


def projected_csv(path, allowed, required, deadline, max_records):
    deadline.check()
    with path.open("rb") as handle:
        source = handle.read(MAX_FILE_BYTES + 1)
    if len(source) > MAX_FILE_BYTES:
        raise BudgetExceeded("CSV exceeds bounded source byte limit")
    reader = csv_byte_rows(source, deadline)
    raw_header = next(reader, None)
    try:
        header = [field.decode("utf-8") for field in raw_header] if raw_header is not None else None
    except UnicodeDecodeError:
        raise AuditError("CSV header is not valid UTF-8") from None
    if header is None or not required.issubset(header):
        raise AuditError("Source CSV lacks required structural columns")
    project_columns(header, [None] * len(header), allowed)
    for ordinal, values in enumerate(reader, 1):
        deadline.check()
        if ordinal > max_records:
            raise BudgetExceeded("Source CSV exceeds per-dataset record limit")
        if len(values) != len(header):
            raise AuditError("CSV record field count differs from its header")
        selected = project_columns(header, values, allowed)
        try:
            yield ordinal, {name: value.decode("utf-8") for name, value in selected.items()}
        except UnicodeDecodeError:
            raise AuditError("CSV structural field is not valid UTF-8") from None


def source_hash(path, deadline):
    before = path.stat()
    if before.st_size > MAX_FILE_BYTES:
        raise BudgetExceeded("Source file exceeds bounded byte limit")
    sha256, blob = hashlib.sha256(), hashlib.sha1()
    blob.update(f"blob {before.st_size}\0".encode("ascii"))
    with path.open("rb") as handle:
        while True:
            deadline.check()
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            sha256.update(chunk)
            blob.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise AuditError("Source changed while hashing")
    return {"path": str(path.resolve()), "bytes": after.st_size, "mtime_ns": after.st_mtime_ns,
            "sha256": sha256.hexdigest(), "git_blob_sha1": blob.hexdigest()}


def assert_unchanged(path, metadata):
    current = path.stat()
    if (current.st_size, current.st_mtime_ns) != (metadata["bytes"], metadata["mtime_ns"]):
        raise AuditError("Source changed after hashing or during structural parsing")


def expected_metadata(path, deadline):
    if path is None:
        return None, None
    metadata_hash = source_hash(Path(path), deadline)
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if payload.get("repository") != "dmis-lab/ATTNSOM" or not re.fullmatch(r"[0-9a-f]{40}", payload.get("commit", "")):
        raise AuditError("Expected source metadata requires the repository and immutable commit")
    if payload["commit"] != SOURCE_CONTRACT_COMMIT:
        raise AuditError("Expected source commit differs from the fixed source numbering contract")
    entries = payload.get("files")
    if not isinstance(entries, list) or not entries:
        raise AuditError("Expected source metadata files must be nonempty")
    paths = set()
    for entry in entries:
        relative = entry.get("repository_path", "")
        if (not relative.startswith("cyp_dataset/") or ".." in relative.split("/")
                or relative in paths or not relative.endswith((".sdf", ".csv"))):
            raise AuditError("Invalid or duplicate expected repository source path")
        if (not re.fullmatch(r"[0-9a-f]{40}", entry.get("git_blob_sha1", ""))
                or type(entry.get("bytes")) is not int or entry["bytes"] < 0):
            raise AuditError("Expected source entry lacks blob hash or byte count")
        paths.add(relative)
    assert_unchanged(Path(path), metadata_hash)
    return payload, metadata_hash


def bind_source(metadata, repository_path, expected):
    if expected is None:
        metadata["source_version_status"] = "UNVERIFIED: no expected Git tree metadata supplied"
        return
    basename = Path(repository_path).name
    matches = [entry for entry in expected["files"] if Path(entry["repository_path"]).name == basename]
    if len(matches) != 1 or matches[0]["repository_path"] != repository_path:
        raise AuditError("Expected source metadata is missing or ambiguous for known repository path")
    entry = matches[0]
    if (entry["git_blob_sha1"], entry["bytes"]) != (metadata["git_blob_sha1"], metadata["bytes"]):
        raise AuditError("Server source differs from the declared fixed-commit Git blob")
    metadata.update(source_version_status="MATCHED declared Git tree metadata",
                    repository=expected["repository"], repository_commit=expected["commit"],
                    repository_path=repository_path)


def sdf_structure_blocks(path, deadline):
    """Yield structural mol blocks; never decode SDF properties or their values."""
    ordinal, block, bytes_used, in_properties = 1, [], 0, False
    with path.open("rb") as handle:
        while True:
            deadline.check()
            line = handle.readline(MAX_BLOCK_BYTES + 1)
            if not line:
                if in_properties or any(part.strip() for part in block):
                    raise AuditError("SDF final record lacks its delimiter")
                return
            if len(line) > MAX_BLOCK_BYTES:
                raise BudgetExceeded("SDF line exceeds bounded limit")
            if line.strip() == b"$$$$":
                if not in_properties:
                    yield ordinal, None
                else:
                    try:
                        decoded = b"".join(block).decode("utf-8")
                    except UnicodeDecodeError:
                        decoded = None
                    yield ordinal, decoded
                ordinal, block, bytes_used, in_properties = ordinal + 1, [], 0, False
            elif not in_properties:
                block.append(line)
                bytes_used += len(line)
                if bytes_used > MAX_BLOCK_BYTES:
                    raise BudgetExceeded("SDF structure block exceeds bounded limit")
                if line.strip() == b"M  END":
                    in_properties = True
            # Properties: only recognize the SDF record delimiter, no decoding.


def structure_evidence(structure):
    mol = structure.mol
    ordered_graph = {
        "atoms": [[atom.GetAtomicNum(), atom.GetIsotope(), atom.GetFormalCharge(), atom.GetNumExplicitHs()]
                  for atom in mol.GetAtoms()],
        "bonds": sorted([[min(b.GetBeginAtomIdx(), b.GetEndAtomIdx()), max(b.GetBeginAtomIdx(), b.GetEndAtomIdx()),
                           str(b.GetBondType()), bool(b.GetIsAromatic())] for b in mol.GetBonds()]),
    }
    coordinates = [[[c.GetAtomPosition(i).x, c.GetAtomPosition(i).y, c.GetAtomPosition(i).z]
                    for i in range(structure.n_atoms)] for c in mol.GetConformers()]
    return {"inchikey": structure.identity.inchikey, "n_atoms": structure.n_atoms,
            "atomic_numbers": list(structure.atomic_numbers), "source_atom_map": list(structure.source_atom_map),
            "ordered_graph_hash": canonical_hash(ordered_graph), "coordinates": coordinates,
            "explicit_h_atoms": sum(z == 1 for z in structure.atomic_numbers), "provenance": structure.provenance}


def exported_coordinates_match(left, right):
    if len(left) != len(right) or any(len(a) != len(b) for a, b in zip(left, right)):
        return False
    # MolToMolBlock's ordinary exporter writes four decimal places. This is a
    # source-order consistency check, not a coordinate-unit or 3D approval.
    return all(math.isfinite(x) and math.isfinite(y) and abs(x - y) <= 5.1e-5
               for a, b in zip(left, right) for p, q in zip(a, b) for x, y in zip(p, q))


def strict_integer(value, name, *, minimum, maximum=None):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value.strip()):
        raise AuditError(f"Invalid structural {name}")
    result = int(value)
    if result < minimum or (maximum is not None and result > maximum):
        raise AuditError(f"Structural {name} outside declared range")
    return result


def public_evidence(evidence):
    # Source XYZ-like coordinates are used only internally for raw/export order
    # consistency, not exported as an unapproved H0 geometry input.
    return {key: value for key, value in evidence.items() if key != "coordinates"}


def verify_ten_fold_membership(dataset, assignment_path, records, *, deadline, max_records,
                               hashed, defect, ledger, result):
    """Match only decoded structural projections; all target bytes stay opaque.

    Assignment folds are zero-based; filenames are fold_1.csv .. fold_10.csv.
    File order may differ from assignment order, but every member must occur
    exactly once with all selected structure/source/group values unchanged.
    """
    valid, assignments, assignment_uids = True, {}, set()

    def failed(reference, exception):
        nonlocal valid
        valid = False
        defect({"dataset": dataset, "stage": "ten_fold_membership", **reference}, exception)

    for ordinal, row in records:
        deadline.check()
        identifier = row["sample_id"]
        reference = {"assignment_record_1based": ordinal, "sample_id": identifier,
                     "sample_uid": row["sample_uid"]}
        try:
            fold = strict_integer(row["fold"], "assignment fold", minimum=0, maximum=9)
            if row["dataset"] != dataset or not row["split_group_key"]:
                raise AuditError("Assignment dataset or split_group_key is missing or inconsistent")
            if (not identifier or identifier in assignments or not row["sample_uid"]
                    or row["sample_uid"] in assignment_uids):
                raise AuditError("Missing or duplicate assignment stable member ID")
            assignments[identifier] = (fold, row)
            assignment_uids.add(row["sample_uid"])
        except BudgetExceeded:
            raise
        except Exception as exc:
            failed(reference, exc)
    result["assignment_members"] = len(assignments)
    result["assignment_structural_projection_sha256"] = canonical_hash([row for _, row in records])
    expected_counts = Counter(fold for fold, _ in assignments.values())
    result["expected_rows_by_fold_0based"] = {str(fold): expected_counts[fold] for fold in range(10)}
    selected_columns = set(records[0][1])
    seen_all, matched = set(), set()
    for fold in range(10):
        deadline.check()
        path = assignment_path.parent / f"fold_{fold + 1}.csv"
        reference = {"source_file": str(path), "filename_fold_1based": fold + 1, "fold_0based": fold}
        seen_file, count = set(), 0
        try:
            if path.resolve().parent != assignment_path.parent.resolve():
                raise AuditError("Fold member CSV resolves outside its known scaffold directory")
            metadata = hashed(path, f"{dataset}_fold_members/fold_{fold + 1}")
            for ordinal, row in projected_csv(path, FOLD_COLUMNS, selected_columns, deadline, max_records):
                deadline.check()
                count += 1
                result["observed_rows"] += 1
                if result["observed_rows"] > max_records:
                    raise BudgetExceeded("Ten fold CSVs exceed cumulative per-dataset record limit")
                identifier = row["sample_id"]
                member_ref = {**reference, "file_record_1based": ordinal, "sample_id": identifier,
                              "sample_uid": row["sample_uid"]}
                try:
                    if not identifier:
                        raise AuditError("Fold CSV member has no stable sample_id")
                    duplicate = identifier in seen_all
                    seen_all.add(identifier)
                    seen_file.add(identifier)
                    if duplicate:
                        result["duplicate_rows"] += 1
                        raise AuditError("Duplicate member within or across ten fold CSVs")
                    if identifier not in assignments:
                        result["extra_rows"] += 1
                        raise AuditError("Fold CSV member is absent from existing assignment")
                    declared = strict_integer(row["fold"], "fold member", minimum=0, maximum=9)
                    expected_fold, expected_row = assignments[identifier]
                    if declared != fold or expected_fold != fold:
                        result["wrong_fold_rows"] += 1
                        raise AuditError("Zero-based member/assignment fold differs from one-based filename")
                    if row != expected_row:
                        result["structural_drift_rows"] += 1
                        differing = sorted(name for name in set(row) | set(expected_row)
                                           if row.get(name) != expected_row.get(name))
                        raise AuditError("Fold structural/source/group fields drift from assignment: " + ", ".join(differing))
                    matched.add(identifier)
                    result["matched_rows"] += 1
                    ledger.write({"dataset": dataset, **member_ref, "status": "STRUCTURAL_MEMBER_MATCH",
                                  "structural_projection_sha256": canonical_hash(expected_row)})
                except BudgetExceeded:
                    raise
                except Exception as exc:
                    failed(member_ref, exc)
                    ledger.write({"dataset": dataset, **member_ref, "status": "FAILED"})
            metadata["structural_records"] = count
            assert_unchanged(path, metadata)
            result["files_read_complete"] += 1
            missing = sorted(identifier for identifier, (expected_fold, _) in assignments.items()
                             if expected_fold == fold and identifier not in seen_file)
            if missing or count != expected_counts[fold]:
                failed({**reference, "missing_sample_ids": missing, "expected_rows": expected_counts[fold],
                        "observed_rows": count}, AuditError("Fold file does not cover its assignment members exactly"))
        except BudgetExceeded:
            raise
        except Exception as exc:
            failed(reference, exc)
    missing = sorted(set(assignments) - matched)
    result["distinct_members_observed"] = len(seen_all)
    result["missing_or_unmatched_members"] = len(missing)
    if missing:
        failed({"missing_or_unmatched_sample_ids": missing},
               AuditError("Ten folds do not match every existing assignment member"))
    result["structural_membership_complete"] = bool(
        valid and result["files_read_complete"] == 10 and matched == set(assignments)
        and result["observed_rows"] == len(records) and len(assignments) == len(records))


def audit_som_structures(benchmark_root, *, output_dir, expected_source_metadata=None,
                         max_records=5000, max_wall_seconds=120., clock=time.monotonic):
    if type(max_records) is not int or not 0 < max_records <= 5000:
        raise ValueError("max_records must be positive and at most 5000 per dataset")
    if not 0 < float(max_wall_seconds) <= 120:
        raise ValueError("wall budget must be positive and at most 120 seconds")
    root, output = Path(benchmark_root).resolve(), Path(output_dir).resolve()
    if output == root or output.is_relative_to(root):
        raise ValueError("Structure audit output must be outside the benchmark input tree")
    output.mkdir(parents=True, exist_ok=False)
    deadline = Deadline(max_wall_seconds, clock)
    counters = {name: Counter({"raw_records": 0, "fold_records": 0, "fold_records_connected": 0,
                              "raw_explicit_h_atoms": 0, "raw_records_with_explicit_h": 0,
                              "fold_records_with_explicit_h": 0})
                for name in ("cyp_isoform", "az_exactsom")}
    sources, complete, raw_only = {}, {}, {}
    membership = {name: {"assignment_members": 0, "files_read_complete": 0, "observed_rows": 0,
                         "matched_rows": 0, "duplicate_rows": 0, "extra_rows": 0, "wrong_fold_rows": 0,
                         "structural_drift_rows": 0, "missing_or_unmatched_members": None,
                         "structural_membership_complete": False}
                  for name in counters}
    fold_keys = {name: defaultdict(list) for name in counters}
    expected, expected_hash, partial = None, None, False
    with ExitStack() as stack:
        ledgers = {name: Ledger(output / f"{name}.jsonl", stack) for name in
                   ("cyp_sources", "cyp_folds", "az_sources", "az_folds", "fold_members", "defects")}

        def defect(reference, exception):
            ledgers["defects"].write({**reference, "status": "FAILED", "error_type": type(exception).__name__,
                                     "error": str(exception)})

        def hashed(path, logical, repo_path=None):
            metadata = source_hash(path, deadline)
            sources[logical] = metadata
            if repo_path:
                bind_source(metadata, repo_path, expected)
            return metadata

        try:
            expected, expected_hash = expected_metadata(expected_source_metadata, deadline)
            folds = {}
            for dataset in counters:
                path = root / "scaffold_split" / dataset / "fold_assignments.csv"
                metadata = hashed(path, f"{dataset}_folds")
                required = BASE_COLUMNS | ({"isoform", "source_sdf", "mol_block"} if dataset == "cyp_isoform" else set())
                folds[dataset] = list(projected_csv(path, FOLD_COLUMNS, required, deadline, max_records))
                counters[dataset]["fold_records"] = len(folds[dataset])
                if not folds[dataset]:
                    raise AuditError("Current fold assignment source contains no records")
                assert_unchanged(path, metadata)
                complete[f"{dataset}_fold_read"] = True
                verify_ten_fold_membership(dataset, path, folds[dataset], deadline=deadline,
                    max_records=max_records, hashed=hashed, defect=defect, ledger=ledgers["fold_members"],
                    result=membership[dataset])
                complete[f"{dataset}_ten_fold_files_read"] = membership[dataset]["files_read_complete"] == 10

            cyp_raw = {}
            cyp_root = (root / "cyp_isoform" / "raw").resolve()
            for filename in CYP_FILES:
                path = cyp_root / filename
                if path.resolve().parent != cyp_root:
                    raise AuditError("CYP raw SDF resolves outside the declared raw root")
                metadata = hashed(path, f"cyp_raw/{filename}", f"cyp_dataset/{filename}")
                file_records = 0
                for ordinal, block in sdf_structure_blocks(path, deadline):
                    file_records += 1
                    counters["cyp_isoform"]["raw_records"] += 1
                    if counters["cyp_isoform"]["raw_records"] > max_records:
                        raise BudgetExceeded("CYP raw records exceed per-dataset limit")
                    reference = {"dataset": "cyp_isoform", "source_file": filename, "source_record_1based": ordinal}
                    try:
                        if block is None:
                            raise AuditError("SDF record lacks a complete structural mol block")
                        evidence = structure_evidence(read_cyp_mol_block(block))
                        cyp_raw[(filename, ordinal)] = evidence
                        counters["cyp_isoform"]["raw_explicit_h_atoms"] += evidence["explicit_h_atoms"]
                        counters["cyp_isoform"]["raw_records_with_explicit_h"] += int(evidence["explicit_h_atoms"] > 0)
                        ledgers["cyp_sources"].write({**reference, "status": "STRUCTURE_READ", **public_evidence(evidence)})
                    except Exception as exc:
                        defect(reference, exc)
                        ledgers["cyp_sources"].write({**reference, "status": "FAILED"})
                metadata["structural_records"] = file_records
                assert_unchanged(path, metadata)
            complete["cyp_raw_read"] = True
            cyp_seen, cyp_used, cyp_sample_ids = set(), set(), set()
            for ordinal, row in folds["cyp_isoform"]:
                deadline.check()
                reference = {"dataset": "cyp_isoform", "fold_record_1based": ordinal,
                             "sample_id": row["sample_id"], "sample_uid": row["sample_uid"]}
                try:
                    uid, isoform = row["sample_uid"], row["isoform"]
                    if (not uid or uid in cyp_seen or not row["compound_id"]
                            or not row["sample_id"] or row["sample_id"] in cyp_sample_ids):
                        raise AuditError("Missing or duplicate CYP sample_uid/sample_id/compound ID")
                    cyp_seen.add(uid)
                    cyp_sample_ids.add(row["sample_id"])
                    filename = f"{isoform}.sdf"
                    if filename not in CYP_FILES:
                        raise AuditError("CYP isoform is not an allowed source filename")
                    source = Path(row["source_sdf"])
                    if not source.is_absolute() or source.resolve() != (cyp_root / filename).resolve():
                        raise AuditError("CYP source_sdf is outside its known matching raw source")
                    record = strict_integer(uid.rsplit("::", 1)[-1], "SDF record ordinal", minimum=1)
                    if uid != f"{isoform}::{row['compound_id']}::{record}":
                        raise AuditError("CYP sample_uid does not bind isoform, compound ID and source record")
                    source_ref = (filename, record)
                    if source_ref in cyp_used:
                        raise AuditError("Duplicate CYP raw record connection")
                    cyp_used.add(source_ref)
                    raw = cyp_raw.get(source_ref)
                    if raw is None:
                        raise AuditError("CYP fold record has no valid raw structure source")
                    fold = strict_integer(row["fold"], "fold", minimum=0, maximum=9)
                    evidence = structure_evidence(read_cyp_mol_block(
                        row["mol_block"], expected_n_atoms=strict_integer(row["n_atoms"], "n_atoms", minimum=1)))
                    iso_key = molecule_identity(row["SMILES_isomeric"]).inchikey
                    if iso_key != evidence["inchikey"] or raw["inchikey"] != evidence["inchikey"]:
                        raise AuditError("CYP raw/block/isomeric full identities differ")
                    if raw["ordered_graph_hash"] != evidence["ordered_graph_hash"]:
                        raise AuditError("CYP source-order atom/bond graph differs from exported block")
                    if not exported_coordinates_match(raw["coordinates"], evidence["coordinates"]):
                        raise AuditError("CYP source-order coordinates differ beyond exporter precision")
                    fold_keys["cyp_isoform"][iso_key].append({**reference, "isoform": isoform, "fold": fold})
                    counters["cyp_isoform"]["fold_records_connected"] += 1
                    counters["cyp_isoform"]["fold_records_with_explicit_h"] += int(evidence["explicit_h_atoms"] > 0)
                    ledgers["cyp_folds"].write({**reference, "status": "SOURCE_ORDER_CONNECTED", "fold": fold,
                        "source_file": filename, "source_record_1based": record,
                        "coordinate_order_tolerance": 5.1e-5, **public_evidence(evidence)})
                except Exception as exc:
                    defect(reference, exc)
                    ledgers["cyp_folds"].write({**reference, "status": "FAILED"})
            raw_only["cyp_isoform"] = [{"source_file": file, "source_record_1based": number}
                                       for file, number in sorted(set(cyp_raw) - cyp_used)]
            complete["cyp_fold_audit"] = True

            az_path = root / "az_exactsom" / "raw" / "az_120_compounds.csv"
            az_raw_root = az_path.parent.resolve()
            if az_path.resolve().parent != az_raw_root:
                raise AuditError("AZ raw CSV resolves outside declared raw root")
            metadata = hashed(az_path, "az_raw", "cyp_dataset/az/az_120_compounds.csv")
            az_raw, az_seen = {}, set()
            for ordinal, row in projected_csv(az_path, RAW_AZ_COLUMNS, RAW_AZ_COLUMNS, deadline, max_records):
                counters["az_exactsom"]["raw_records"] += 1
                identifier = row["Compound ID"].strip()
                reference = {"dataset": "az_exactsom", "source_record_1based": ordinal, "compound_id": identifier}
                try:
                    if identifier in az_seen:
                        az_raw.pop(identifier, None)  # No first-row choice for an ambiguous ID.
                        raise AuditError("Missing or duplicate AZ raw Compound ID")
                    if not identifier:
                        raise AuditError("Missing or duplicate AZ raw Compound ID")
                    az_seen.add(identifier)
                    evidence = structure_evidence(read_az_raw_smiles(row["SMILES"]))
                    az_raw[identifier] = evidence
                    counters["az_exactsom"]["raw_explicit_h_atoms"] += evidence["explicit_h_atoms"]
                    counters["az_exactsom"]["raw_records_with_explicit_h"] += int(evidence["explicit_h_atoms"] > 0)
                    ledgers["az_sources"].write({**reference, "status": "STRUCTURE_READ", **public_evidence(evidence)})
                except Exception as exc:
                    defect(reference, exc)
                    ledgers["az_sources"].write({**reference, "status": "FAILED"})
            metadata["structural_records"] = counters["az_exactsom"]["raw_records"]
            assert_unchanged(az_path, metadata)
            complete["az_raw_read"] = True
            az_used, az_uids, az_sample_ids = set(), set(), set()
            for ordinal, row in folds["az_exactsom"]:
                deadline.check()
                identifier = row["compound_id"].strip()
                reference = {"dataset": "az_exactsom", "fold_record_1based": ordinal,
                             "sample_id": row["sample_id"], "sample_uid": row["sample_uid"], "compound_id": identifier}
                try:
                    if (not identifier or identifier in az_used or not row["sample_uid"] or row["sample_uid"] in az_uids
                            or not row["sample_id"] or row["sample_id"] in az_sample_ids):
                        raise AuditError("Missing or duplicate AZ fold ID/sample_uid")
                    az_used.add(identifier)
                    az_uids.add(row["sample_uid"])
                    az_sample_ids.add(row["sample_id"])
                    if row["sample_uid"] != f"az::{identifier}":
                        raise AuditError("AZ sample_uid does not bind its Compound ID")
                    raw = az_raw.get(identifier)
                    if raw is None:
                        raise AuditError("AZ fold ID lacks a valid unique raw source")
                    fold = strict_integer(row["fold"], "fold", minimum=0, maximum=9)
                    if raw["n_atoms"] != strict_integer(row["n_atoms"], "n_atoms", minimum=1):
                        raise AuditError("AZ raw/default-parser atom count differs from fold metadata")
                    if raw["inchikey"] != molecule_identity(row["SMILES_isomeric"]).inchikey:
                        raise AuditError("AZ raw/isomeric full identities differ")
                    fold_keys["az_exactsom"][raw["inchikey"]].append({**reference, "fold": fold})
                    counters["az_exactsom"]["fold_records_connected"] += 1
                    counters["az_exactsom"]["fold_records_with_explicit_h"] += int(raw["explicit_h_atoms"] > 0)
                    ledgers["az_folds"].write({**reference, "status": "RAW_ID_CONNECTED", "fold": fold,
                                             **public_evidence(raw)})
                except Exception as exc:
                    defect(reference, exc)
                    ledgers["az_folds"].write({**reference, "status": "FAILED"})
            raw_only["az_exactsom"] = sorted(az_seen - az_used)
            complete["az_fold_audit"] = True
            for dataset, key_refs in fold_keys.items():
                for key, references in key_refs.items():
                    deadline.check()
                    if len({ref["fold"] for ref in references}) > 1:
                        defect({"dataset": dataset, "inchikey": key, "references": references},
                               AuditError("Full molecular identity spans existing folds; no reassignment attempted"))
            complete["dataset_local_cross_fold_check"] = True
        except BudgetExceeded as exc:
            partial = True
            defect({"scope": "audit"}, exc)
        except Exception as exc:
            defect({"scope": "audit"}, exc)

        full = all(complete.get(stage) for stage in ("cyp_isoform_fold_read", "az_exactsom_fold_read", "cyp_raw_read",
                    "cyp_fold_audit", "az_raw_read", "az_fold_audit", "dataset_local_cross_fold_check",
                    "cyp_isoform_ten_fold_files_read", "az_exactsom_ten_fold_files_read"))
        code = 3 if partial or not full else (2 if ledgers["defects"].rows else 0)
        summary = {
            "scope": "NOT_FROZEN structure/source audit; no targets or target repair",
            "status": "STRUCTURE_AUDIT_PASS" if code == 0 else ("PARTIAL" if code == 3 else "FAILED"),
            "complete_scope": full, "exit_code": code, "defect_count": ledgers["defects"].rows,
            "counts": {name: dict(count) for name, count in counters.items()}, "completion": complete,
            "ten_fold_membership": membership,
            "ten_fold_member_coverage_complete": bool(code == 0 and full and all(
                item["structural_membership_complete"] for item in membership.values())),
            "raw_only": raw_only, "sources": sources, "expected_source_metadata": expected_hash,
            "expected_repository_commit": expected["commit"] if expected else None,
            "source_contract_commit": SOURCE_CONTRACT_COMMIT, "source_contract": SOURCE_CONTRACT,
            "identity_policy": IDENTITY_POLICY, "rdkit_version": rdBase.rdkitVersion,
            "dataset_unique_full_keys": {name: len(keys) for name, keys in fold_keys.items()},
            "source_version_binding_complete": bool(full and expected and all(
                item.get("source_version_status") == "MATCHED declared Git tree metadata"
                for name, item in sources.items() if name.startswith("cyp_raw/") or name == "az_raw")),
            "elapsed_seconds": clock() - deadline.started, "max_wall_seconds": max_wall_seconds,
            "max_records_per_dataset": max_records, "ledgers": {name: ledger.metadata() for name, ledger in ledgers.items()},
            "boundaries": ["No SoM indices/flags/comments/targets interpreted; full source bytes hashed only",
                "Ten fold files checked against assignments using only exact structural/source/group values; targets remain opaque",
                "Assignment fold 0..9 corresponds to filenames fold_1.csv..fold_10.csv; no member/fold reassignment",
                "CYP raw block/export graph and coordinate order checked; explicit-H annotation indexing still unverified",
                "CYP source record ordinal is connected; SDF ID/property values are deliberately not interpreted",
                "AZ source index is default raw-SMILES parser index; annotation repair/range not inspected",
                "Graph symmetry can leave indistinguishable atom mappings; no labels used to choose a permutation",
                "No source/member/fold changes, no 3D approval, no final benchmark freeze/decontamination proof"],
        }
        (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    return summary, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", default="/share/home/zixiao/benchmark_dataset")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expected-source-metadata")
    parser.add_argument("--max-records", type=int, default=5000)
    parser.add_argument("--max-wall-seconds", type=float, default=120.)
    args = parser.parse_args()
    # SIGALRM also bounds a slow native parser/hash/read on the Linux CPU node.
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(BudgetExceeded("Process wall budget reached")))
        signal.setitimer(signal.ITIMER_REAL, min(args.max_wall_seconds, 120.))
    try:
        summary, code = audit_som_structures(args.benchmark_root, output_dir=args.output_dir,
            expected_source_metadata=args.expected_source_metadata, max_records=args.max_records,
            max_wall_seconds=args.max_wall_seconds)
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.setitimer(signal.ITIMER_REAL, 0.)
    print(json.dumps({key: summary[key] for key in ("status", "complete_scope", "defect_count", "counts", "exit_code")}, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
