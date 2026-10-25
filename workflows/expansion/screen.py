"""Bounded, ordered, CPU-parallel CID/SMILES screening with source provenance.

No neutralization, tautomer canonicalization, isotope stripping, stereo removal
or heavy-atom cutoff is introduced. X01-X05 keep their WP0 definitions.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
import multiprocessing
from pathlib import Path
import sqlite3
import time

from .common import check_quota, dump_new, external_output, load, reference, require, require_compute, wp5_key

WHITELIST = {1, 5, 6, 7, 8, 9, 14, 15, 16, 17, 34, 35, 53}
RDKIT = "2025.09.5"


def rdkit_modules():
    from rdkit import Chem, DataStructs, RDLogger, rdBase
    from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors
    from rdkit.Chem.Scaffolds import MurckoScaffold
    from rdkit.Chem import rdFingerprintGenerator
    require(tuple(map(int, rdBase.rdkitVersion.split("."))) == (2025, 9, 5), "RDKit must match v1: 2025.09.5")
    RDLogger.DisableLog("rdApp.error")
    return Chem, DataStructs, Descriptors, Lipinski, rdMolDescriptors, MurckoScaffold, rdFingerprintGenerator


def chemical_flags(smiles):
    """Return explicit exclusion flags, preserving source isotope/stereo state."""
    Chem, *_ = rdkit_modules()
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None, {"PARSE_FAILED": True}
    explicit = Chem.AddHs(m)
    return m, {
        "X01": "." in smiles or len(Chem.GetMolFrags(m)) > 1,
        "X02": any(a.GetAtomicNum() not in WHITELIST for a in explicit.GetAtoms()),
        "X03": Chem.GetFormalCharge(m) != 0,
        "X04": any(a.GetNumRadicalElectrons() > 0 for a in m.GetAtoms()),
        "X05": sum(a.GetAtomicNum() for a in explicit.GetAtoms()) % 2 == 1,
    }


def features(cid, smiles, ordinal):
    Chem, DataStructs, Descriptors, Lipinski, rdMolDescriptors, Murcko, Fingerprint = rdkit_modules()
    mol, flags = chemical_flags(smiles)
    reasons = [k for k, v in flags.items() if v]
    if reasons:
        return {"cid": cid, "ordinal": ordinal, "reasons": reasons}
    key = Chem.MolToInchiKey(mol)
    wp = wp5_key(key)
    counts = Counter(a.GetAtomicNum() for a in mol.GetAtoms() if a.GetAtomicNum() != 1)
    scaffold = Murcko.MakeScaffoldGeneric(Murcko.GetScaffoldForMol(mol))
    scaffold_key = Chem.MolToSmiles(scaffold, isomericSmiles=False)
    # Ring-system identity uses generic connected components of ring bonds.
    ring = Chem.RWMol(Chem.Mol(mol))
    remove = [b.GetIdx() for b in ring.GetBonds() if not b.IsInRing()]
    for idx in sorted(remove, reverse=True):
        b = ring.GetBondWithIdx(idx)
        ring.RemoveBond(b.GetBeginAtomIdx(), b.GetEndAtomIdx())
    ring_systems = []
    for frag in Chem.GetMolFrags(ring.GetMol(), asMols=True, sanitizeFrags=False):
        if frag.GetNumBonds():
            Chem.SanitizeMol(frag)
            ring_systems.append(Chem.MolToSmiles(Murcko.MakeScaffoldGeneric(frag), isomericSmiles=False))
    fp = Fingerprint.GetMorganGenerator(radius=2, fpSize=2048, includeChirality=False).GetFingerprint(mol)
    return {"cid": cid, "ordinal": ordinal, "reasons": [], "source_smiles": smiles,
            "isomeric_smiles": Chem.MolToSmiles(mol, isomericSmiles=True), "full_key": key, "wp5_key": wp,
            "heavy_atoms": sum(counts.values()), "elements": sorted(counts),
            "non_h_composition": json.dumps(sorted(counts.items()), separators=(",", ":")),
            "element_combination": ",".join(map(str, sorted(counts))),
            "isotopic_atoms": sum(a.GetIsotope() > 0 for a in mol.GetAtoms()),
            "molecular_weight_Da": Descriptors.MolWt(mol), "rings": rdMolDescriptors.CalcNumRings(mol),
            "aromatic_rings": rdMolDescriptors.CalcNumAromaticRings(mol),
            "rotatable_bonds": Lipinski.NumRotatableBonds(mol), "hbd": Lipinski.NumHDonors(mol),
            "hba": Lipinski.NumHAcceptors(mol), "tpsa_A2": rdMolDescriptors.CalcTPSA(mol),
            "logp": Descriptors.MolLogP(mol),
            "stereocenters": len(Chem.FindMolChiralCenters(mol, includeUnassigned=True)),
            "generic_murcko": scaffold_key, "generic_ring_systems": sorted(ring_systems),
            "ecfp4_2048_hex": DataStructs.BitVectToBinaryText(fp).hex()}


def screen_batch(batch):
    results = []
    for cid, smiles, ordinal in batch:
        try:
            results.append(features(cid, smiles, ordinal))
        except Exception as exc:
            results.append({"cid": cid, "ordinal": ordinal, "reasons": ["IDENTITY_OR_FEATURE_FAILED"],
                            "error": type(exc).__name__ + ": " + str(exc)[:500]})
    return results


def ordered_parallel(batches, workers):
    """At most 2*workers input batches are queued; executor.map is not used."""
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as pool:
        waiting = deque()
        for batch in batches:
            waiting.append(pool.submit(screen_batch, batch))
            if len(waiting) >= 2 * workers:
                yield waiting.popleft().result(timeout=3600)
        while waiting:
            yield waiting.popleft().result(timeout=3600)


def cid_batches(path, max_rows=None, batch_size=256):
    batch = []
    with gzip.open(path, "rt", encoding="utf-8", errors="strict", newline="") as stream:
        for ordinal, line in enumerate(stream, 1):
            if max_rows is not None and ordinal > max_rows:
                break
            parts = line.rstrip("\r\n").split("\t")
            require(len(parts) == 2 and parts[0].isascii() and parts[0].isdecimal() and int(parts[0]) > 0,
                    "Malformed official CID/SMILES row at ordinal " + str(ordinal))
            batch.append((int(parts[0]), parts[1], ordinal))
            if len(batch) == batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


def screen(source_receipt, output, workers, quota_receipt, projected_bytes, max_rows=None):
    require_compute(workers)
    from .common import verify
    source = load(source_receipt)
    require(source["schema"] == "pubchem_download_complete_v1", "Source must be a complete pinned download")
    raw = verify(source["file"])
    check_quota(quota_receipt, projected_bytes)
    output = external_output(output)
    output.mkdir(parents=True)
    db_path = output / "screened_candidates.sqlite"
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA journal_mode=DELETE")
    db.execute("CREATE TABLE candidates(full_key TEXT PRIMARY KEY,cid INTEGER UNIQUE,wp5_key TEXT,features TEXT NOT NULL)")
    db.execute("CREATE TABLE aliases(cid INTEGER PRIMARY KEY,full_key TEXT NOT NULL,source_ordinal INTEGER NOT NULL)")
    counts, examples = Counter(), {}
    started = time.monotonic()
    try:
        for batch in ordered_parallel(cid_batches(raw, max_rows), workers):
            for row in batch:
                counts["input_records"] += 1
                if row["reasons"]:
                    for reason in row["reasons"]:
                        counts["overlap:" + reason] += 1
                        examples.setdefault(reason, [])
                        if len(examples[reason]) < 20:
                            examples[reason].append(row)
                    counts["first:" + row["reasons"][0]] += 1
                    continue
                counts["after_X_and_identity"] += 1
                db.execute("INSERT INTO aliases VALUES(?,?,?)", (row["cid"], row["full_key"], row["ordinal"]))
                old = db.execute("SELECT cid FROM candidates WHERE full_key=?", (row["full_key"],)).fetchone()
                if old:
                    counts["pubchem_duplicate_full_key"] += 1
                if old is None or row["cid"] < old[0]:
                    db.execute("INSERT OR REPLACE INTO candidates VALUES(?,?,?,?)", (row["full_key"], row["cid"], row["wp5_key"],
                               json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False)))
            db.commit()
            require(sum(p.stat().st_size for p in output.iterdir() if p.is_file()) <= projected_bytes,
                    "STOP: output exceeded its quota-reviewed byte budget")
        unique = db.execute("SELECT count(*) FROM candidates").fetchone()[0]
    finally:
        db.close()
    dump_new(output / "receipt.json", {"schema": "pubchem_screen_v1", "status": "BOUNDED_PILOT" if max_rows else "COMPLETE",
        "complete_source": max_rows is None, "source": reference(source_receipt), "rdkit_version": RDKIT,
        "workers": workers, "max_input_rows": max_rows, "counts": dict(counts), "unique_full_keys": unique,
        "sequential_funnel_order": ["PARSE_FAILED", "X01", "X02", "X03", "X04", "X05", "IDENTITY_OR_FEATURE_FAILED"],
        "overlap_counts_are_not_disjoint": True, "examples": examples, "wall_seconds": time.monotonic() - started,
        "heavy_atom_upper_bound": None, "isotope_policy": "preserve", "stereo_policy": "preserve_source",
        "database": reference(db_path)})


def regression(rows):
    """Original v1 input projection: compare X flags; geometry/QC are separate."""
    n = matched = 0
    mismatches = []
    for row in rows:
        n += 1
        require("source_ref" in row and "expected_flags" in row and "smiles" in row,
                "Regression needs original input pointer and original X flags")
        try:
            _, observed = chemical_flags(row["smiles"])
            expected = row["expected_flags"]
            require(set(expected) == {"X01", "X02", "X03", "X04", "X05"}, "Original five X flags required")
            same = all(type(expected[k]) is bool and observed.get(k) == expected[k] for k in expected)
        except Exception as exc:
            same, observed = False, {"error": type(exc).__name__ + ": " + str(exc)}
        if same:
            matched += 1
        else:
            mismatches.append({"source_ref": row["source_ref"], "expected": row["expected_flags"], "observed": observed,
                               "explanation": row.get("mismatch_explanation")})
    require(n > 0, "Empty regression input")
    agreement = matched / n
    unexplained = sum(not r["explanation"] for r in mismatches)
    return {"schema": "pubchem_v1_X_regression_v1", "records": n, "matched": matched,
            "agreement": agreement, "unexplained_mismatches": unexplained, "mismatches": mismatches,
            "status": "PASS" if agreement >= 0.999 and unexplained == 0 else "STOP_REVIEW",
            "scope": "Graph X01-X05 only; geometry-derived X01 and later QC must be compared separately",
            "full_v1_selection_regression_passed": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("screen", "regression"))
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--quota-receipt", type=Path)
    p.add_argument("--projected-output-bytes", type=int)
    p.add_argument("--max-input-rows", type=int)
    a = p.parse_args()
    require_compute(a.workers)
    if a.action == "screen":
        require(a.quota_receipt and a.projected_output_bytes and (a.max_input_rows is None or a.max_input_rows > 0), "Explicit storage budget required")
        screen(a.input, a.output, a.workers, a.quota_receipt, a.projected_output_bytes, a.max_input_rows)
    else:
        with a.input.open(encoding="utf-8") as stream:
            result = regression(json.loads(line) for line in stream)
        result["input"] = reference(a.input)
        dump_new(external_output(a.output), result)
        require(result["status"] == "PASS", "STOP: regression failed; no expansion submission")


if __name__ == "__main__":
    main()
