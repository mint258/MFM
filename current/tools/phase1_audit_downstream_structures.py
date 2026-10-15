#!/usr/bin/env python3
"""Bounded downstream STRUCTURE audit; never consume targets or SoM labels.

Default: first 12 CSV records per dataset, 120 seconds, no mutation/reordering.
Run on an authorized compute node, never through a local Windows interpreter.
The full source bytes are hashed, but only the explicit structure projection is
interpreted. XYZ comment/extra atom columns/trailing annotations are ignored.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import signal
import sys
import time

IMPORT_STARTED = time.monotonic()
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rdkit import Chem, rdBase
from phychem_mfm.phase1.identity import IDENTITY_POLICY, molecule_identity, canonical_hash


DATASETS = ("qm7", "qm9", "cyp_isoform", "az_exactsom")
DEFAULT_SCAFFOLD_ROOT = Path("/share/home/zixiao/benchmark_dataset/scaffold_split")
# Do not broaden this to *_som_*, annotation flags, isoform outcomes or targets.
STRUCTURE_COLUMNS = frozenset({
    "sample_id", "sample_uid", "compound_id", "fold", "split_group_key",
    "SMILES", "SMILES_isomeric", "xyz_path", "mol_block", "n_atoms", "source_sdf",
})
KEY_PATTERN = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
MAX_FIELD_BYTES = 2 * 1024 * 1024
MAX_XYZ_BYTES = 8 * 1024 * 1024
MAX_XYZ_LINE_BYTES = 65536


class BudgetExceeded(RuntimeError):
    pass


class StructureAuditError(ValueError):
    pass


class Deadline:
    def __init__(self, seconds, *, began=None):
        self.began = time.monotonic() if began is None else began
        self.end = self.began + float(seconds)

    def check(self):
        if time.monotonic() >= self.end:
            raise BudgetExceeded("Bounded structure audit wall budget reached")


def project_structure_row(header, row):
    """Index only allowed structure columns, including when targets coexist."""
    selected = {}
    for index, name in enumerate(header):
        if name not in STRUCTURE_COLUMNS:
            continue
        if name in selected:
            raise StructureAuditError("Duplicate structure column in CSV header")
        if index >= len(row):
            raise StructureAuditError("Truncated CSV structure row")
        selected[name] = row[index]
    return selected


def sha256_file(path, deadline):
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            deadline.check()
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise StructureAuditError("Source changed while its bytes were hashed")
    return {"sha256": digest.hexdigest(), "bytes": after.st_size, "mtime_ns": after.st_mtime_ns}


def smiles_structure(smiles, deadline):
    deadline.check()
    if not isinstance(smiles, str) or not smiles.strip() or len(smiles) > 65536:
        raise StructureAuditError("Missing or oversized structure SMILES")
    identity = molecule_identity(smiles)
    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise StructureAuditError("Structure SMILES parsing failed")
    deadline.check()
    return identity, mol


def resolve_xyz_path(value, csv_path):
    if not value:
        raise StructureAuditError("Missing xyz_path structure reference")
    given = Path(value)
    if given.is_absolute():
        candidates = [given]
    else:
        # The source schema does not specify the relative-path base. Refuse
        # ambiguous existing files rather than choosing whichever is found first.
        benchmark = csv_path.parent.parent.parent
        candidates = [csv_path.parent / given, benchmark / given, benchmark / csv_path.parent.name / given]
    found = {path.resolve() for path in candidates if path.is_file()}
    if len(found) != 1:
        raise StructureAuditError("XYZ reference is missing or has ambiguous relative-path resolution")
    path = found.pop()
    if path.suffix.lower() != ".xyz":
        raise StructureAuditError("XYZ reference does not identify an .xyz structure file")
    return path


def read_xyz_structure(path, deadline, *, max_atoms=4096):
    """Read the declared structure block, skipping all dataset target metadata."""
    before = path.stat()
    if before.st_size > MAX_XYZ_BYTES:
        raise StructureAuditError("XYZ exceeds bounded structure file size")
    numbers, finite_rows = [], 0
    with path.open("rt", encoding="utf-8-sig") as handle:
        first = handle.readline(MAX_XYZ_LINE_BYTES + 1)
        if len(first) > MAX_XYZ_LINE_BYTES:
            raise StructureAuditError("Oversized XYZ atom-count line")
        try:
            declared = int(first.strip())
        except ValueError:
            raise StructureAuditError("Invalid XYZ atom-count declaration") from None
        if not 0 < declared <= max_atoms:
            raise StructureAuditError("XYZ atom count outside bounded range")
        # QM comments may contain final targets: discard without splitting them.
        comment = handle.readline(MAX_XYZ_LINE_BYTES + 1)
        if not comment:
            raise StructureAuditError("Missing XYZ comment line")
        if len(comment) > MAX_XYZ_LINE_BYTES:
            raise StructureAuditError("Oversized XYZ comment line; target metadata was not interpreted")
        for _ in range(declared):
            deadline.check()
            line = handle.readline(MAX_XYZ_LINE_BYTES + 1)
            if not line or len(line) > MAX_XYZ_LINE_BYTES:
                raise StructureAuditError("Truncated or oversized XYZ coordinate row")
            fields = line.split()
            if len(fields) < 4:
                raise StructureAuditError("XYZ coordinate row lacks element and three coordinates")
            with rdBase.BlockLogs():
                try:
                    z = int(fields[0]) if fields[0].isdigit() else Chem.GetPeriodicTable().GetAtomicNumber(fields[0])
                except (RuntimeError, ValueError):
                    raise StructureAuditError("Invalid XYZ element symbol") from None
            if not 1 <= z <= 118:
                raise StructureAuditError("XYZ element outside atomic-number range")
            try:
                # Some QM XYZ files use Mathematica *^ or Fortran D exponents.
                coordinates = [float(fields[index].replace("*^", "e").replace("D", "E").replace("d", "e"))
                               for index in (1, 2, 3)]
            except ValueError:
                raise StructureAuditError("Invalid XYZ coordinate value") from None
            finite_rows += int(all(math.isfinite(value) for value in coordinates))
            numbers.append(z)
            # Do not read/convert columns 4+ (e.g. quantum atomic labels).
        # Dataset-specific tail fields are not read or interpreted.
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise StructureAuditError("XYZ structure changed during the bounded read")
    deadline.check()
    return numbers, {"declared_atoms": declared, "coordinate_rows_read": len(numbers),
                     "finite_coordinate_rows": finite_rows, "structure_bytes": after.st_size,
                     "structure_mtime_ns": after.st_mtime_ns,
                     "comment_extra_columns_and_tail": "not interpreted"}


def audit_qm_record(row, csv_path, deadline):
    identity, mol = smiles_structure(row.get("SMILES"), deadline)
    with rdBase.BlockLogs():
        hydrogenated = Chem.AddHs(mol)
    if hydrogenated.GetNumAtoms() > 4096:
        raise StructureAuditError("SMILES AddHs atom count exceeds bounded range")
    expected = [atom.GetAtomicNum() for atom in hydrogenated.GetAtoms()]
    path = resolve_xyz_path(row.get("xyz_path"), Path(csv_path))
    actual, xyz = read_xyz_structure(path, deadline)
    same_count, same_order = len(expected) == len(actual), expected == actual
    same_multiset = Counter(expected) == Counter(actual)
    issues = []
    if not same_count:
        issues.append("SMILES AddHs and XYZ atom counts differ")
    if not same_multiset:
        issues.append("SMILES AddHs and XYZ element multisets differ")
    if not same_order:
        issues.append("SMILES AddHs and XYZ Z/order differ; no permutation was applied")
    if xyz["finite_coordinate_rows"] != xyz["declared_atoms"]:
        issues.append("XYZ has non-finite coordinates")
    mismatches = [{"position_1based": index + 1, "smiles_atomic_number": left, "xyz_atomic_number": right}
                  for index, (left, right) in enumerate(zip(expected, actual)) if left != right][:12]
    return {"inchikey": identity.inchikey, "identity_column": "SMILES", "xyz_path": str(path),
            "smiles_add_hs_atoms": len(expected), "xyz": xyz,
            "same_atom_count": same_count, "same_atomic_number_order": same_order,
            "same_element_multiset": same_multiset, "first_order_mismatches": mismatches,
            "smiles_atomic_number_order_sha256": canonical_hash(expected),
            "xyz_atomic_number_order_sha256": canonical_hash(actual),
            "atom_correspondence": "element sequence check only; same-element atom mapping not independently proved",
            "permutation_applied": False, "checks_passed": not issues, "issues": issues}


def audit_cyp_record(row, deadline):
    identity, smiles_mol = smiles_structure(row.get("SMILES_isomeric"), deadline)
    block = row.get("mol_block")
    if not isinstance(block, str) or not block.strip() or len(block.encode("utf-8")) > MAX_FIELD_BYTES:
        raise StructureAuditError("Missing or oversized source mol_block")
    with rdBase.BlockLogs():
        # Keep explicit H and the source atom order, including its original indices.
        mol = Chem.MolFromMolBlock(block, sanitize=True, removeHs=False, strictParsing=True)
        key = Chem.MolToInchiKey(Chem.Mol(mol)) if mol is not None else ""
    if mol is None or not KEY_PATTERN.fullmatch(key or ""):
        raise StructureAuditError("Source mol_block cannot produce a full Standard InChIKey")
    if not 0 < mol.GetNumAtoms() <= 4096:
        raise StructureAuditError("Source mol_block atom count outside bounded range")
    try:
        declared = int(row.get("n_atoms", ""))
    except ValueError:
        raise StructureAuditError("Invalid source n_atoms structure count") from None
    original_order = [atom.GetAtomicNum() for atom in mol.GetAtoms()]
    smiles_order = [atom.GetAtomicNum() for atom in smiles_mol.GetAtoms()]
    issues = []
    if key != identity.inchikey:
        issues.append("SMILES_isomeric and source mol_block full InChIKeys differ")
    if declared != len(original_order):
        issues.append("Declared n_atoms differs from original source mol_block")
    ordinary_identity = None
    if row.get("SMILES"):
        ordinary_identity, _ = smiles_structure(row["SMILES"], deadline)
        if ordinary_identity.inchikey != identity.inchikey:
            issues.append("SMILES and SMILES_isomeric disagree; freeze an authoritative identity source explicitly")
    deadline.check()
    return {"inchikey": identity.inchikey, "identity_column": "SMILES_isomeric",
            "mol_block_inchikey": key, "smiles_inchikey": ordinary_identity.inchikey if ordinary_identity else None,
            "identity_matches_source_mol_block": key == identity.inchikey,
            "declared_n_atoms": declared, "mol_block_atoms": len(original_order),
            "n_atoms_matches_source": declared == len(original_order),
            "mol_block_atomic_number_order_sha256": canonical_hash(original_order),
            "mol_block_first_atomic_numbers": original_order[:12],
            "smiles_order_matches_mol_block": smiles_order == original_order,
            "mol_block_sha256": hashlib.sha256(block.encode("utf-8")).hexdigest(),
            "source_atom_order": "original mol_block; removeHs=False; never canonicalized or renumbered",
            "som_source_index_map": "NOT PROVED: annotation indices are intentionally not read",
            "permutation_applied": False, "checks_passed": not issues, "issues": issues}


def audit_az_record(row, deadline):
    identity, mol = smiles_structure(row.get("SMILES"), deadline)
    result = {"inchikey": identity.inchikey, "identity_column": "SMILES", "smiles_atoms": mol.GetNumAtoms(),
              "som_source_index_map": "NOT PROVED: no original mol_block and no annotation indices read",
              "permutation_applied": False, "checks_passed": True, "issues": []}
    if row.get("SMILES_isomeric"):
        isomeric, _ = smiles_structure(row["SMILES_isomeric"], deadline)
        result["smiles_isomeric_inchikey"] = isomeric.inchikey
        result["smiles_columns_identity_agree"] = identity.inchikey == isomeric.inchikey
        if not result["smiles_columns_identity_agree"]:
            result["checks_passed"] = False
            result["issues"].append("SMILES and SMILES_isomeric disagree; identity source requires explicit resolution")
    return result


def audit_dataset(name, path, report, deadline, *, limit):
    report.update({"dataset": name, "source_csv": str(path), "sampling": "first records in existing CSV order",
                   "record_limit": limit, "records": [], "status": "started"})
    report["source"] = sha256_file(path, deadline)
    with path.open("rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        report["structure_schema"] = [field for field in header if field in STRUCTURE_COLUMNS]
        report["other_columns_ignored"] = len(header) - len(report["structure_schema"])
        for row_index in range(limit):
            deadline.check()
            try:
                raw = next(reader)
            except StopIteration:
                report["end_of_file_observed"] = True
                break
            selected = project_structure_row(header, raw)
            record = {"source_record_ordinal_1based": row_index + 1,
                      **{field: selected[field] for field in ("sample_id", "sample_uid", "compound_id", "fold", "split_group_key", "source_sdf")
                         if field in selected}, "structure_schema": sorted(selected)}
            report["records"].append(record)
            try:
                # Preserve a valid identity even if the subsequent XYZ/source
                # structure check fails. Only declared structure columns enter.
                identity_column = "SMILES_isomeric" if name == "cyp_isoform" else "SMILES"
                identity, _ = smiles_structure(selected.get(identity_column), deadline)
                record.update({"inchikey": identity.inchikey, "identity_column": identity_column})
                if name in {"qm7", "qm9"}:
                    record.update(audit_qm_record(selected, path, deadline))
                elif name == "cyp_isoform":
                    record.update(audit_cyp_record(selected, deadline))
                else:
                    record.update(audit_az_record(selected, deadline))
            except BudgetExceeded:
                record.update({"checks_passed": False, "issues": ["not completed: wall budget reached"]})
                raise
            except Exception as error:
                # Avoid dumping input rows, mol blocks, comments or target data.
                reason = str(error) if isinstance(error, StructureAuditError) else "Structure parsing/read failed; raw input omitted"
                record.update({"checks_passed": False, "issues": [reason], "failure_type": type(error).__name__})
    deadline.check()
    after = path.stat()
    if (after.st_size, after.st_mtime_ns) != (report["source"]["bytes"], report["source"]["mtime_ns"]):
        raise StructureAuditError("CSV source changed after its hash was recorded")
    report["observed_records"] = len(report["records"])
    report["status"] = "completed_bounded"


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--scaffold-root", type=Path, default=DEFAULT_SCAFFOLD_ROOT)
    parser.add_argument("--records-per-dataset", type=int, default=12)
    parser.add_argument("--max-wall-seconds", type=float, default=120.)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.records_per_dataset <= 12 or not 0 < args.max_wall_seconds <= 120:
        parser.error("Structure audit is limited to 1..12 records per dataset and at most 120 seconds")
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite an existing structure audit")
    csv.field_size_limit(MAX_FIELD_BYTES)
    deadline = Deadline(args.max_wall_seconds, began=IMPORT_STARTED)
    report = {"scope": "BOUNDED STRUCTURE-ONLY AUDIT; NOT FULL DATASET OR FOLD PROOF",
              "identity_policy": IDENTITY_POLICY, "rdkit_version": rdBase.rdkitVersion,
              "source_root": str(args.scaffold_root.resolve()), "wall_limit_seconds": args.max_wall_seconds,
              "max_records_per_dataset": args.records_per_dataset,
              "target_values_and_som_indices": "not selected, converted, inspected or exported",
              "source_hashing": "raw file bytes only; no target interpretation",
              "all_existing_files_and_splits_unchanged": True, "formal_eligibility": False,
              "unproved": ["complete dataset identities and fold consistency", "same-element atom correspondences",
                           "SoM annotation-to-source atom index maps"], "datasets": []}
    previous_handler = None
    alarm_armed = False
    try:
        deadline.check()
        if hasattr(signal, "setitimer"):
            def timeout_handler(_signum, _frame):
                raise BudgetExceeded("Bounded structure audit wall budget reached")
            previous_handler = signal.signal(signal.SIGALRM, timeout_handler)
            alarm_armed = True
            signal.setitimer(signal.ITIMER_REAL, max(.001, deadline.end - time.monotonic()))
        for name in DATASETS:
            entry = {}
            report["datasets"].append(entry)
            try:
                audit_dataset(name, args.scaffold_root / name / "fold_assignments.csv", entry, deadline,
                              limit=args.records_per_dataset)
            except BudgetExceeded:
                entry["status"] = "incomplete_wall_budget"
                raise
            except Exception as error:
                reason = str(error) if isinstance(error, StructureAuditError) else "Source schema/read failed; raw input omitted"
                entry.update({"status": "failed", "failure_type": type(error).__name__, "reason": reason})
        failed = any(entry.get("status") != "completed_bounded" or
                     any(not record.get("checks_passed", False) for record in entry.get("records", []))
                     or not entry.get("records") for entry in report["datasets"])
        report["status"] = "FAIL_OR_INCOMPLETE" if failed else "COMPLETED_BOUNDED_CHECKS_ONLY"
    except BudgetExceeded:
        report["status"] = "FAIL_OR_INCOMPLETE"
        report["termination"] = "wall_budget_reached; remaining records/datasets not audited"
    finally:
        if alarm_armed:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
        report["wall_seconds_including_imports"] = time.monotonic() - IMPORT_STARTED
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
        temporary.replace(args.output)
        print(json.dumps({"status": report.get("status"), "scope": report["scope"], "output": str(args.output),
                          "audited_records": sum(len(entry.get("records", [])) for entry in report["datasets"])}))
    return 0 if report.get("status") == "COMPLETED_BOUNDED_CHECKS_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
