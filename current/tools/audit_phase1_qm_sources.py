#!/usr/bin/env python3
"""Full existing-member QM structure audit; NOT_FROZEN, CPU only.

Only structural CSV values are decoded. XYZ comments, charge columns,
frequencies and InChi lines remain opaque bytes. QM9 original/relaxed source
SMILES are separate identities, never an atom permutation or a new split.
QM7 XYZ has no authoritative bond/stereo identity: it always remains UNPROVEN.
No source files, folds, formal protocol or final-test manifest are written.

Run through a Slurm CPU allocation. Defaults: <=200000 members per dataset,
840 internal seconds, <=128 MiB per CSV, <=8 MiB per XYZ (existing reader),
<=512 MiB total audit output. Plan roughly 3 KiB per member plus defects; at
the cap this can exceed the output budget, yielding PARTIAL rather than a
false complete result. Filesystem free space is not an account quota check.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import signal
import sys
import time

PROCESS_STARTED = time.monotonic()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rdkit import Chem, rdBase
from phychem_mfm.phase1.downstream_structures import (
    MAX_LINE_BYTES, MAX_STRUCTURE_BYTES, read_xyz_structure,
)
from phychem_mfm.phase1.identity import IDENTITY_POLICY, canonical_hash, molecule_identity
from tools.audit_phase1_som_structures import BudgetExceeded, Deadline, csv_byte_rows, project_columns

MAX_MEMBERS = 200000
MAX_CSV_BYTES = 128 * 1024 * 1024
MAX_OUTPUT_BYTES = 512 * 1024 * 1024
MAX_WALL_SECONDS = 840
STRUCTURE_COLUMNS = frozenset({"dataset", "sample_id", "fold", "xyz_path", "SMILES", "split_group_key"})
REQUIRED_COLUMNS = frozenset({"sample_id", "fold", "xyz_path", "SMILES", "split_group_key"})
QM9_FORMAT_REFERENCE = "https://doi.org/10.1038/sdata.2014.22#Table2"
PREPROCESS_SNAPSHOTS = {
    "download_qm7_qm9.py": "966ea9820c0cc0b00e4c13553a2b59cc4fcabb30ada6dedd52c41ced1fee6ea1",
    "split_qm7_qm9_scaffold10.py": "2568dc9e41fb8e0522394e1647e7873ddcf88862f873dd9e37e9b92263feaa49",
}


class AuditError(ValueError):
    pass


class SourceRecordError(AuditError):
    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence


@contextmanager
def wall_alarm(seconds):
    """Unix CPU job alarm; record-boundary deadline also works without SIGALRM."""
    enabled = hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer")
    previous = previous_timer = None
    if enabled:
        def expired(_signum, _frame):
            raise BudgetExceeded("Internal QM source audit wall budget reached")
        try:
            previous = signal.signal(signal.SIGALRM, expired)
            previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
        except ValueError:  # API called outside the main thread, or Windows.
            enabled = False
    try:
        yield
    finally:
        if enabled:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
            if previous_timer and previous_timer[0] > 0:
                signal.setitimer(signal.ITIMER_REAL, *previous_timer)


class OutputLedger:
    def __init__(self, path, budget):
        self.path, self.budget = path, budget
        self.rows, self.digest = 0, hashlib.sha256()
        self.handle = path.open("xb")

    def write(self, row):
        encoded = (json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False,
                              separators=(",", ":")) + "\n").encode("utf-8")
        # Leave bounded finalization space for the summary and final defect.
        if self.budget[0] + len(encoded) > MAX_OUTPUT_BYTES - 1024 * 1024:
            raise BudgetExceeded("Audit output byte budget reached")
        self.handle.write(encoded)
        self.handle.flush()
        self.digest.update(encoded)
        self.rows += 1
        self.budget[0] += len(encoded)

    def metadata(self):
        return {"path": str(self.path.resolve()), "rows": self.rows, "sha256": self.digest.hexdigest()}

    def close(self):
        self.handle.close()


def source_bytes(path, deadline, limit):
    deadline.check()
    before = path.stat()
    if before.st_size > limit:
        raise BudgetExceeded("Source file exceeds bounded byte limit")
    with path.open("rb") as handle:
        source = handle.read(limit + 1)
    after = path.stat()
    deadline.check()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise AuditError("Source changed during read")
    if len(source) != after.st_size or len(source) > limit:
        raise AuditError("Source truncated or exceeds bounded byte limit")
    return source, {"path": str(path.resolve()), "bytes": len(source),
                    "mtime_ns": after.st_mtime_ns, "sha256": hashlib.sha256(source).hexdigest()}


def projected_qm_csv(path, deadline, max_records, metadata):
    source, evidence = source_bytes(path, deadline, MAX_CSV_BYTES)
    metadata.update(evidence)
    framed = csv_byte_rows(source, deadline)
    raw_header = next(framed, None)
    try:
        header = [value.decode("utf-8") for value in raw_header] if raw_header else None
    except UnicodeDecodeError:
        raise AuditError("CSV header is not valid UTF-8") from None
    if header is None or not REQUIRED_COLUMNS.issubset(header):
        raise AuditError("CSV lacks required QM structural columns")
    project_columns(header, [None] * len(header), STRUCTURE_COLUMNS)
    for ordinal, row in enumerate(framed, 1):
        deadline.check()
        if ordinal > max_records:
            raise BudgetExceeded("Existing member CSV exceeds record limit")
        if len(row) != len(header):
            raise AuditError("CSV record field count differs from header")
        selected = project_columns(header, row, STRUCTURE_COLUMNS)
        try:
            yield ordinal, {name: value.decode("utf-8") for name, value in selected.items()}
        except UnicodeDecodeError:
            raise AuditError("Selected QM structural field is not valid UTF-8") from None
    current = path.stat()
    if (current.st_size, current.st_mtime_ns) != (evidence["bytes"], evidence["mtime_ns"]):
        raise AuditError("CSV changed during structural projection")


def strict_integer(value, name, *, minimum=0, maximum=None):
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise AuditError(f"{name} is not a canonical nonnegative integer")
    number = int(value)
    if number < minimum or (maximum is not None and number > maximum):
        raise AuditError(f"{name} is outside its declared range")
    return number


def row_identity(row, dataset):
    if "dataset" in row and row["dataset"] != dataset:
        raise AuditError("CSV dataset differs from its declared dataset")
    return (strict_integer(row["sample_id"], "sample_id", minimum=1),
            strict_integer(row["fold"], "fold", maximum=9))


def connected_xyz_path(row, dataset, source_root, csv_path):
    sample_id, _ = row_identity(row, dataset)
    value = row["xyz_path"]
    if not value:
        raise AuditError("Empty XYZ source reference")
    supplied = Path(value)
    path = (supplied if supplied.is_absolute() else csv_path.parent / supplied).resolve()
    if path.parent != source_root.resolve():
        raise AuditError("XYZ source lies outside its known generator directory")
    pattern = r"qm7_([0-9]+)\.xyz" if dataset == "qm7" else r"dsgdb9nsd_([0-9]+)\.xyz"
    match = re.fullmatch(pattern, path.name)
    if match is None or int(match.group(1)) != sample_id:
        raise AuditError("XYZ filename ID does not exactly connect to existing sample_id")
    return path


def nonstereo_graph_smiles(smiles):
    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise AuditError("SMILES graph cannot be parsed")
        return Chem.MolToSmiles(Chem.RemoveHs(mol), canonical=True, isomericSmiles=False)


def qm9_source_identities(source, atom_count, deadline):
    """Project only two SMILES tokens on 1-based line N+4; all else opaque."""
    stream = io.BytesIO(source)
    # N, comment and N atom rows have already been checked by read_xyz_structure.
    for _ in range(atom_count + 2):
        deadline.check()
        line = stream.readline(MAX_LINE_BYTES + 1)
        if not line or len(line) > MAX_LINE_BYTES:
            raise AuditError("QM9 structure prefix is truncated or line exceeds limit")
    frequency = stream.readline(MAX_LINE_BYTES + 1)
    if not frequency or len(frequency) > MAX_LINE_BYTES:
        raise AuditError("QM9 opaque frequency line is missing or exceeds limit")
    line = stream.readline(MAX_LINE_BYTES + 1)
    if not line or len(line) > MAX_LINE_BYTES:
        raise AuditError("QM9 source SMILES line is missing or exceeds limit")
    tokens = line.split(maxsplit=2)
    if len(tokens) != 2:
        raise AuditError("QM9 source SMILES line must contain exactly two structural tokens")
    try:
        original, relaxed = (token.decode("ascii") for token in tokens)
    except UnicodeDecodeError:
        raise AuditError("QM9 source SMILES token is not ASCII") from None
    # Check only framing/presence of InChi, never decode or parse its value.
    inchi = stream.readline(MAX_LINE_BYTES + 1)
    if not inchi or len(inchi) > MAX_LINE_BYTES:
        raise AuditError("QM9 opaque InChi line is missing or exceeds limit")
    deadline.check()
    identities, errors = {}, {}
    for name, smiles, token in (("original_gdb", original, tokens[0]), ("relaxed", relaxed, tokens[1])):
        deadline.check()
        identities[name] = {"smiles": smiles, "inchikey": None,
                            "token_sha256": hashlib.sha256(token).hexdigest()}
        try:
            identity = molecule_identity(smiles, source_field=f"qm9_{name}_smiles")
            identities[name]["inchikey"] = identity.inchikey
        except BudgetExceeded:
            raise
        except Exception as exc:
            errors[name] = str(exc)
    deadline.check()
    return {**identities, "identity_errors": errors,
            "source_keys_equal": identities["original_gdb"]["inchikey"] == identities["relaxed"]["inchikey"] if not errors else None,
            "identity_source_line_1based": atom_count + 4,
            "source_smiles_line_sha256": hashlib.sha256(line).hexdigest(),
            "identity_status": "SOURCE_GRAPH_KEYS_ONLY; geometry/stereo correspondence UNPROVEN",
            "identity_atom_mapping_proven": False,
            "csv_identity_source": "original_gdb first token; never switch to relaxed",
            "format_reference": QM9_FORMAT_REFERENCE}


def audit_qm_source_record(row, dataset, source_root, assignment_path, deadline):
    path = connected_xyz_path(row, dataset, source_root, assignment_path)
    deadline.check()
    units = "bohr" if dataset == "qm7" else "angstrom"
    result = {"source_path": str(path), "source_units": units, "output_units": "angstrom",
              "source_full_identity_status": "UNPROVEN", "source_keys": {}}
    try:
        # Keep byte/source evidence even if geometry or one identity fails.
        source, source_metadata = source_bytes(path, deadline, MAX_STRUCTURE_BYTES)
        result.update(source_sha256=source_metadata["sha256"], source_bytes=source_metadata["bytes"])
        structure = read_xyz_structure(path, units=units)
        deadline.check()
        if structure.provenance["source_sha256"] != result["source_sha256"]:
            raise AuditError("XYZ changed between geometry and identity projections")
        result.update(n_atoms=structure.n_atoms,
                      source_atomic_number_order_hash=structure.provenance["source_atomic_number_order_hash"],
                      coordinate_scale=structure.provenance["coordinate_scale"],
                      coordinate_projection_hash=canonical_hash({"source_units": units,
                          "coordinate_scale": structure.provenance["coordinate_scale"],
                          "atomic_numbers": structure.atomic_numbers, "pos_angstrom": structure.pos_angstrom}),
                      source_atom_map_hash=canonical_hash(structure.source_atom_map),
                      source_atom_map_policy="XYZ row i -> encoder atom i; retain H; no permutation",
                      atom_encoding="zero_based", mapping_audit_complete=False)
        if dataset == "qm9":
            identities = qm9_source_identities(source, structure.n_atoms, deadline)
            result.update(identities)
            result["source_keys"] = {name: identities[name]["inchikey"] for name in ("original_gdb", "relaxed")
                                     if identities[name]["inchikey"] is not None}
            if identities["identity_errors"]:
                raise AuditError("One or more QM9 source SMILES identities failed; see identity_errors")
            # Verify the exact historical source graph while retaining source stereo.
            if nonstereo_graph_smiles(identities["original_gdb"]["smiles"]) != nonstereo_graph_smiles(row["SMILES"]):
                raise AuditError("Original GDB source graph does not connect to existing CSV graph")
        else:
            result["identity_status"] = "SOURCE_FULL_IDENTITY_UNPROVEN: XYZ and nonstereo CSV insufficient"
            result["source_keys_equal"] = None
        current = path.stat()
        if (current.st_size, current.st_mtime_ns) != (source_metadata["bytes"], source_metadata["mtime_ns"]):
            raise AuditError("XYZ changed between geometry and identity projections")
        deadline.check()
    except BudgetExceeded as exc:
        exc.evidence = result
        raise
    except Exception as exc:
        raise SourceRecordError(str(exc), result) from exc
    return result


def audit_qm_sources(benchmark_root, *, output_dir, datasets=("qm7", "qm9"),
                     max_wall_seconds=840, max_records=200000, clock=time.monotonic):
    if (isinstance(max_wall_seconds, bool) or not isinstance(max_wall_seconds, (int, float))
            or not math.isfinite(max_wall_seconds) or not 0 < max_wall_seconds <= MAX_WALL_SECONDS):
        raise ValueError("Internal wall budget must be positive and <=840 seconds")
    if type(max_records) is not int or not 1 <= max_records <= MAX_MEMBERS:
        raise ValueError("Per-dataset member cap must be 1..200000")
    datasets = tuple(datasets)
    if not datasets or len(set(datasets)) != len(datasets) or set(datasets) - {"qm7", "qm9"}:
        raise ValueError("Select distinct qm7/qm9 datasets only")
    root, output = Path(benchmark_root).resolve(), Path(output_dir).resolve()
    if output.is_relative_to(root) or output.is_relative_to(PROJECT_ROOT):
        raise ValueError("Output must be outside the benchmark input tree and source repository")
    output.mkdir(parents=True, exist_ok=False)
    deadline, budget = Deadline(max_wall_seconds, clock=clock), [0]
    records = OutputLedger(output / "source_records.jsonl", budget)
    defects = OutputLedger(output / "defects.jsonl", budget)
    fold_ledger = OutputLedger(output / "fold_members.jsonl", budget)
    summary = {"scope": "NOT_FROZEN; complete existing-member structure/source-key audit only",
               "formal_eligible": False, "complete_scope": False,
               "identity_policy": IDENTITY_POLICY, "rdkit_version": rdBase.rdkitVersion,
               "benchmark_root": str(root), "datasets": {}, "sources": {},
               "limits": {"max_records_per_dataset": max_records, "max_wall_seconds": max_wall_seconds,
                          "max_csv_bytes": MAX_CSV_BYTES, "max_xyz_bytes": MAX_STRUCTURE_BYTES,
                          "max_output_bytes": MAX_OUTPUT_BYTES, "estimated_bytes_per_member": 3072},
               "preprocess_snapshot_sha256": PREPROCESS_SNAPSHOTS,
               "filesystem_free_bytes_at_start": shutil.disk_usage(output).free,
               "quota_status": "not measured; submitter must check account quota",
               "source_version_binding": "observed exact file hashes; upstream archive binding not independently established",
               "targets_decoded": False, "members_or_folds_changed": False,
               "boundaries": ["QM7 authoritative full identity always UNPROVEN; no charge/bond perception",
                              "QM9 source graph keys do not prove XYZ stereo or graph atom mapping",
                              "original/relaxed mismatch is recorded, never a sample exclusion",
                              "union of source keys is audit evidence, never a frozen final-test list"]}
    defect_count, code = 0, 0

    def defect(dataset, stage, error, **reference):
        nonlocal defect_count
        defects.write({"dataset": dataset, "stage": stage, "error": str(error), **reference})
        defect_count += 1

    try:
        with wall_alarm(max_wall_seconds):
            for dataset in datasets:
                deadline.check()
                stats = summary["datasets"][dataset] = {
                    "assignment_rows": 0, "source_records_successful": 0,
                    "assignment_complete": False, "fold_files_complete": 0,
                    "fold_members_checked": 0, "original_relaxed_differences": 0,
                    "source_full_identity_status": "UNPROVEN", "key_overlap_proof_available": False}
                assignments, path_owners, key_refs = {}, {}, defaultdict(list)
                start_defects, assignment_valid = defect_count, True
                assignment_path = root / "scaffold_split" / dataset / "fold_assignments.csv"
                source_root = root / dataset / ("extracted/xyz" if dataset == "qm7" else "extracted_figshare")
                metadata = summary["sources"][str(assignment_path)] = {}
                try:
                    for ordinal, row in projected_qm_csv(assignment_path, deadline, max_records, metadata):
                        stats["assignment_rows"] += 1
                        reference = {"dataset": dataset, "assignment_ordinal_1based": ordinal,
                                     "sample_id": row["sample_id"], "fold": row["fold"],
                                     "declared_xyz_path": row["xyz_path"], "structural_row_hash": canonical_hash(row)}
                        summary["partial_active_reference"] = reference
                        evidence = {}
                        try:
                            sample_id, fold = row_identity(row, dataset)
                            if sample_id in assignments:
                                raise AuditError("Duplicate existing assignment sample_id")
                            path = connected_xyz_path(row, dataset, source_root, assignment_path)
                            if str(path) in path_owners:
                                raise AuditError("Source path has more than one existing member")
                            path_owners[str(path)] = sample_id
                            assignments[sample_id] = (fold, canonical_hash(row), reference)
                            evidence = audit_qm_source_record(row, dataset, source_root, assignment_path, deadline)
                            records.write({**reference, "status": "structure_ok", **evidence})
                            stats["source_records_successful"] += 1
                            if evidence["source_keys_equal"] is False:
                                stats["original_relaxed_differences"] += 1
                            for name, key in evidence["source_keys"].items():
                                key_refs[key].append({**reference, "source_graph": name})
                        except BudgetExceeded as exc:
                            summary["partial_source_evidence"] = getattr(exc, "evidence", evidence)
                            raise
                        except Exception as exc:
                            assignment_valid = False
                            defect(dataset, "assignment/source", exc, **{k: v for k, v in reference.items() if k != "dataset"})
                            records.write({**reference, **getattr(exc, "evidence", {}),
                                           "status": "failed", "error": str(exc)})
                        summary.pop("partial_active_reference", None)
                    stats["assignment_complete"] = True
                    if not stats["assignment_rows"]:
                        assignment_valid = False
                        defect(dataset, "assignment", "Existing assignment has no members")
                except BudgetExceeded:
                    raise
                except Exception as exc:
                    assignment_valid = False
                    defect(dataset, "assignment_csv", exc)

                checked_ids, expected_counts = set(), Counter(item[0] for item in assignments.values())
                for fold in range(10):
                    deadline.check()
                    path = assignment_path.parent / f"fold_{fold + 1}.csv"
                    fold_metadata = summary["sources"][str(path)] = {}
                    seen, count = set(), 0
                    try:
                        for ordinal, row in projected_qm_csv(path, deadline, max_records, fold_metadata):
                            count += 1
                            reference = {"file": str(path), "file_fold_0based": fold,
                                         "record_ordinal_1based": ordinal, "sample_id": row["sample_id"]}
                            try:
                                sample_id, row_fold = row_identity(row, dataset)
                                if row_fold != fold or sample_id in seen:
                                    raise AuditError("Fold file contains wrong fold or duplicate member")
                                seen.add(sample_id)
                                if sample_id not in assignments:
                                    raise AuditError("Fold file contains member absent from existing assignment")
                                expected_fold, row_hash, _ = assignments[sample_id]
                                if expected_fold != fold or row_hash != canonical_hash(row):
                                    raise AuditError("Fold structural member/ID/fold/path differs from assignment")
                                checked_ids.add(sample_id)
                                stats["fold_members_checked"] += 1
                                fold_ledger.write({"dataset": dataset, **reference,
                                                   "structural_row_hash": row_hash, "status": "matched"})
                            except BudgetExceeded:
                                raise
                            except Exception as exc:
                                defect(dataset, "fold_member", exc, **reference)
                        stats["fold_files_complete"] += 1
                        missing = sorted(sample_id for sample_id, item in assignments.items() if item[0] == fold and sample_id not in seen)
                        if count != expected_counts[fold] or missing:
                            defect(dataset, "fold_coverage", "Fold membership/count differs from assignment",
                                   file=str(path), fold=fold, observed_rows=count,
                                   expected_rows=expected_counts[fold], missing_sample_ids=missing)
                    except BudgetExceeded:
                        raise
                    except Exception as exc:
                        defect(dataset, "fold_csv", exc, file=str(path))
                if checked_ids != set(assignments):
                    defect(dataset, "fold_coverage", "Ten folds do not cover existing assignments exactly",
                           missing_sample_ids=sorted(set(assignments) - checked_ids))
                full_success = (assignment_valid and stats["assignment_complete"]
                                and stats["fold_files_complete"] == 10
                                and stats["source_records_successful"] == stats["assignment_rows"]
                                and defect_count == start_defects)
                stats["all_structure_and_membership_checks_passed"] = full_success
                stats["unique_source_keys_union"] = len(key_refs)
                stats["source_key_union_hash"] = canonical_hash(sorted(key_refs)) if full_success and dataset == "qm9" else None
                stats["cross_fold_key_count"] = None
                if full_success and dataset == "qm9":
                    stats["key_overlap_proof_available"] = True
                    overlapping = 0
                    for key, references in key_refs.items():
                        deadline.check()
                        if len({item["fold"] for item in references}) > 1:
                            overlapping += 1
                            defect(dataset, "source_key_overlap", "Source key spans existing folds; no reassignment",
                                   inchikey=key, references=references)
                    stats["cross_fold_key_count"] = overlapping
            summary["complete_scope"] = all(item["assignment_complete"] and item["fold_files_complete"] == 10
                                              for item in summary["datasets"].values()) and len(summary["datasets"]) == len(datasets)
            deadline.check()
            code = 2 if defect_count else 0
            summary["status"] = "COMPLETED_WITH_DEFECTS" if defect_count else "COMPLETED_NOT_FROZEN_IDENTITIES_UNPROVEN"
    except BudgetExceeded as exc:
        code, summary["status"] = 3, "PARTIAL"
        summary["complete_scope"] = False
        for item in summary["datasets"].values():
            item["key_overlap_proof_available"] = False
            item["cross_fold_key_count"] = None
        # If output is full, final failure still fits reserved finalization space.
        try:
            defect(None, "budget", exc)
        except BudgetExceeded:
            summary["finalization_defect"] = str(exc)
    except Exception as exc:
        code, summary["status"] = 2, "FAILED_OR_INCOMPLETE"
        summary["complete_scope"] = False
        defect(None, "audit", exc)
    finally:
        summary["defect_count"] = defect_count
        summary["wall_seconds"] = max(0.0, clock() - deadline.started)
        summary["exit_code"] = code
        summary["ledgers"] = {"source_records": records.metadata(), "fold_members": fold_ledger.metadata(),
                              "defects": defects.metadata()}
        for ledger in (records, defects, fold_ledger):
            ledger.close()
        summary["ledger_bytes"] = budget[0]
        with (output / "summary.json").open("x", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2)
            handle.write("\n")
    return summary, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", type=Path, default=Path("/share/home/zixiao/benchmark_dataset"))
    parser.add_argument("--datasets", choices=("qm7", "qm9"), nargs="+", default=["qm7", "qm9"])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-wall-seconds", type=float, default=840)
    parser.add_argument("--max-records", type=int, default=200000)
    args = parser.parse_args()
    if not 0 < args.max_wall_seconds <= MAX_WALL_SECONDS:
        parser.error("--max-wall-seconds must be positive and <=840")
    remaining = args.max_wall_seconds - (time.monotonic() - PROCESS_STARTED)
    if remaining <= 0:
        parser.error("Wall budget was consumed before audit startup")
    summary, code = audit_qm_sources(args.benchmark_root, output_dir=args.output_dir,
                                    datasets=args.datasets, max_wall_seconds=remaining, max_records=args.max_records)
    print(json.dumps({"status": summary["status"], "complete_scope": summary["complete_scope"],
                      "formal_eligible": False, "output_dir": str(args.output_dir), "exit_code": code}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
