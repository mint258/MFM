"""CPU-only three-CID stage replay; scientific AST unchanged except checkpoints."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
import math
import os
from pathlib import Path
import socket
import threading
import time
import traceback

from . import common, data_authority_cpu_v1 as authority, screen
from workflows.data_v1_final.execution.cpu_analysis_v1 import runtime as cpu_runtime
from .common import ARTIFACT_ROOT, check_quota, dump_new, load, reference, require, verify, wp5_key


def json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {"non_finite_float": repr(value)}
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def mol_property_snapshot(mol):
    """Property getters only: no smiles, ring perception or sanitization here."""
    return {"atoms": mol.GetNumAtoms(), "bonds": mol.GetNumBonds(),
            "atomic_numbers": [a.GetAtomicNum() for a in mol.GetAtoms()],
            "aromatic_atom_indices": [a.GetIdx() for a in mol.GetAtoms() if a.GetIsAromatic()],
            "formal_charges": [a.GetFormalCharge() for a in mol.GetAtoms()],
            "explicit_h_counts": [a.GetNumExplicitHs() for a in mol.GetAtoms()],
            "bond_properties": [[b.GetBeginAtomIdx(), b.GetEndAtomIdx(), str(b.GetBondType()), b.GetIsAromatic()]
                                for b in mol.GetBonds()]}


def diagnose_case(case):
    cpu_runtime.checkpoint()
    cid, smiles, ordinal = case["cid"], case["smiles"], case["ordinal"]
    Chem, DataStructs, Descriptors, Lipinski, rdMolDescriptors, Murcko, Fingerprint = screen.rdkit_modules()
    stages, values = [], {}

    def stage(name, function, describe=lambda x: x):
        cpu_runtime.checkpoint()
        began = time.monotonic()
        try:
            value = function()
            stages.append({"stage": name, "status": "PASS", "result": json_safe(describe(value)),
                           "seconds": time.monotonic() - began})
            values[name] = value
            return True, value
        except Exception as exc:
            stages.append({"stage": name, "status": "ERROR", "exception_type": type(exc).__name__,
                           "message": str(exc), "exact_traceback": traceback.format_exc(),
                           "seconds": time.monotonic() - began})
            return False, None

    # Run the actual frozen function first, independently of the stage replica.
    ok, original = stage("registered_screen.features_exact_call", lambda: screen.features(cid, smiles, ordinal))
    exact_status = "PASS" if ok else "ERROR"
    parsed, pair = stage("old_chemical_flags", lambda: screen.chemical_flags(smiles),
                         lambda pair: {"flags": pair[1], "parsed": pair[0] is not None,
                                       "native_mol_properties": None if pair[0] is None else mol_property_snapshot(pair[0])})
    old_flags = pair[1] if parsed else None
    if not parsed or pair[0] is None or any(pair[1].values()):
        return {**case, "worker_thread_id": threading.get_native_id(), "registered_features_status": exact_status,
                "old_chemical_flags": old_flags, "feature_replica_skipped_by_old_chemical_rules": True, "stages": stages}
    mol = pair[0]
    stage("identity.full_inchikey", lambda: Chem.MolToInchiKey(mol))
    if "identity.full_inchikey" in values:
        stage("identity.wp5_key", lambda: wp5_key(values["identity.full_inchikey"]))
    stage("identity.non_h_element_counts", lambda: sorted(Counter(a.GetAtomicNum() for a in mol.GetAtoms()
                                                                  if a.GetAtomicNum() != 1).items()))
    good_scaffold, scaffold = stage("scaffold.GetScaffoldForMol", lambda: Murcko.GetScaffoldForMol(mol), mol_property_snapshot)
    if good_scaffold:
        good_generic, generic = stage("scaffold.MakeScaffoldGeneric", lambda: Murcko.MakeScaffoldGeneric(scaffold), mol_property_snapshot)
        if good_generic:
            stage("scaffold.MolToSmiles", lambda: Chem.MolToSmiles(generic, isomericSmiles=False))

    def cut_non_ring_bonds():
        ring = Chem.RWMol(Chem.Mol(mol))
        remove = [b.GetIdx() for b in ring.GetBonds() if not b.IsInRing()]
        for idx in sorted(remove, reverse=True):
            bond = ring.GetBondWithIdx(idx)
            ring.RemoveBond(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx())
        return ring.GetMol()

    cut_ok, ring = stage("ring_system.cut_all_non_ring_bonds_exact_old_order", cut_non_ring_bonds, mol_property_snapshot)
    if cut_ok:
        frags_ok, fragments = stage("ring_system.GetMolFrags_sanitizeFrags_false", lambda: Chem.GetMolFrags(ring, asMols=True, sanitizeFrags=False),
                                    lambda frags: [mol_property_snapshot(frag) for frag in frags])
        if frags_ok:
            for i, fragment in enumerate(fragments):
                cpu_runtime.checkpoint()
                if not fragment.GetNumBonds():
                    stages.append({"stage": f"ring_system.fragment_{i}.skip_no_bonds", "status": "SKIPPED_EXACT_OLD_BRANCH"})
                    continue
                sane, _ = stage(f"ring_system.fragment_{i}.Chem.SanitizeMol_exact_old_call", lambda f=fragment: Chem.SanitizeMol(f), int)
                if sane:
                    generic_ok, generic = stage(f"ring_system.fragment_{i}.MakeScaffoldGeneric", lambda f=fragment: Murcko.MakeScaffoldGeneric(f), mol_property_snapshot)
                    if generic_ok:
                        stage(f"ring_system.fragment_{i}.MolToSmiles", lambda g=generic: Chem.MolToSmiles(g, isomericSmiles=False))
    # These independent original-molecule stages run even when a ring fragment
    # fails. They do not repair or replace any previous intermediate molecule.
    cpu_runtime.checkpoint()
    fresh, _ = screen.chemical_flags(smiles)
    stage("independent.fingerprint.ecfp4_2048", lambda: DataStructs.BitVectToBinaryText(
        Fingerprint.GetMorganGenerator(radius=2, fpSize=2048, includeChirality=False).GetFingerprint(fresh)).hex())
    descriptor_functions = {"isomeric_smiles": lambda: Chem.MolToSmiles(fresh, isomericSmiles=True),
                            "molecular_weight_Da": lambda: Descriptors.MolWt(fresh), "rings": lambda: rdMolDescriptors.CalcNumRings(fresh),
                            "aromatic_rings": lambda: rdMolDescriptors.CalcNumAromaticRings(fresh),
                            "rotatable_bonds": lambda: Lipinski.NumRotatableBonds(fresh), "hbd": lambda: Lipinski.NumHDonors(fresh),
                            "hba": lambda: Lipinski.NumHAcceptors(fresh), "tpsa_A2": lambda: rdMolDescriptors.CalcTPSA(fresh),
                            "logp": lambda: Descriptors.MolLogP(fresh),
                            "stereocenters": lambda: len(Chem.FindMolChiralCenters(fresh, includeUnassigned=True))}
    for name, function in descriptor_functions.items():
        stage("independent.original_molecule." + name, function)
    replica_errors = [s for s in stages if s["status"] == "ERROR" and s["stage"] != "registered_screen.features_exact_call"]
    return {**case, "worker_thread_id": threading.get_native_id(), "registered_features_status": exact_status,
            "old_chemical_flags": old_flags, "first_replica_error_stage": replica_errors[0]["stage"] if replica_errors else None,
            "stages": stages, "feature_repair_or_chemical_rule_change_applied": False}


def read_target_prefix(raw_path, targets, cap):
    found, scanned = {}, 0
    with gzip.open(raw_path, "rt", encoding="utf-8", errors="strict", newline="") as stream:
        for ordinal in range(1, cap + 1):
            cpu_runtime.checkpoint()
            line = stream.readline()
            if not line:
                break
            scanned = ordinal
            parts = line.rstrip("\r\n").split("\t")
            require(len(parts) == 2 and parts[0].isascii() and parts[0].isdecimal() and int(parts[0]) > 0,
                    "Malformed official raw CID/SMILES row")
            cid = int(parts[0])
            if cid in targets:
                require(cid not in found, "Duplicate target CID in official prefix")
                found[cid] = {"cid": cid, "ordinal": ordinal, "smiles": parts[1]}
                if set(found) == targets:
                    break
    require(set(found) == targets, "A requested diagnostic CID is absent from the bounded prefix")
    return [found[cid] for cid in sorted(found)], scanned


def run(plan_path, intent_path):
    node = socket.gethostname().split(".")[0]
    require(os.getuid() == 1278 and authority.allowed_cpu_node(node) and os.environ.get("SLURM_JOB_ID", "").isdecimal() and
            int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16, "Actual reviewed CPU-only Slurm16 allocation required")
    plan, intent = load(plan_path), load(intent_path)
    require(plan["schema"] == "pubchem_prefix_feature_stage_diagnostic_cpu_plan_v1" and plan["status"] == "READY" and
            plan["chemical_rules_changed"] is False and plan["feature_repair_applied"] is False and
            plan["pool_or_screening_release_authorized"] is False and 1 <= plan["max_prefix_rows"] <= 10000 and
            plan["peak_output_cap_bytes"] == 32 * 1024 ** 2, "Only read-only bounded stage diagnosis is authorized")
    targets = set(plan["target_cids"])
    require(plan["target_cids"] == [7, 52, 53], "Only the same three actual failed-prefix CIDs are authorized")
    request = intent["request"]
    require(intent["uid"] == 1278 and request["node"] == node and request["cpus"] == 16 and request["memory_gib"] == 4 and
            0 < request["wall_seconds"] <= 3600 and request["estimated_peak_output_bytes"] == plan["peak_output_cap_bytes"] + 32 * 1024 ** 2 and
            request["root_review"]["status"] == "APPROVED", "Root diagnostic resource/scope review differs")
    declared = {r["path"]: r for r in request["source_references"]}
    needed = [reference(plan_path), plan["prefix_receipt"], plan["prefix_plan"], plan["prefix_rejections"],
              plan["raw_receipt"], plan["cpu_decision_reference"], plan["central_runtime_reference"],
              *plan["code_sources"], *plan["data_authorization_receipts"]]
    require(all(declared.get(r["path"]) == r for r in needed), "Root did not bind exact diagnostic inputs")
    for ref in needed[1:]:
        require(ref["bytes"] <= 8 * 1024 ** 2, "Only small source/proof metadata may enter login source refs")
        verify(ref)
    actual = {str(Path(p).absolute()) for p in (__file__, common.__file__, authority.__file__, screen.__file__, cpu_runtime.__file__)}
    require(actual <= {r["path"] for r in plan["code_sources"]}, "Actual diagnostic import chain not pinned")
    previous, previous_plan = load(plan["prefix_receipt"]["path"]), load(plan["prefix_plan"]["path"])
    require(previous["schema"] == "PUBCHEM_BOUNDED_PREFIX_PILOT_V2" and previous["job_id"] == plan["expected_prefix_job_id"] and
            previous["plan"] == plan["prefix_plan"] and previous["source_receipt"] == plan["raw_receipt"] and
            previous["all_rejections"] == plan["prefix_rejections"], "Wrong original prefix evidence")
    old_source = next(r for r in previous_plan["code_sources"] if Path(r["path"]).name == "screen.py")
    current_source = reference(screen.__file__)
    require(all(current_source[k] == old_source[k] for k in ("bytes", "sha256")), "Registered screen.py changed since original prefix")
    raw = load(plan["raw_receipt"]["path"])
    require(request["data_references"] == [raw["file"]], "Diagnostic must read only the same official raw body")
    cpu_proof = cpu_runtime.root_guard(intent_path, plan_path, plan["peak_output_cap_bytes"], wall_limit=3600)
    cpu_runtime.checkpoint()
    data = authority.authorize_data(plan, intent, [raw["file"]], node=node)
    out = Path(plan["output_root"]).absolute()
    require(out.is_relative_to(ARTIFACT_ROOT / "diagnostics") and not out.exists(), "Fresh diagnostic output required")
    out.mkdir(parents=True)
    began = time.monotonic()
    try:
        feed = Path(plan["quota_feed"])
        require(feed.is_file() and feed.stat().st_uid == 1278 and not feed.is_symlink(), "Task-owned quota feed required")
        dump_new(out / "quota_start.json", load(feed))
        check_quota(out / "quota_start.json", request["estimated_peak_output_bytes"])
        cpu_runtime.checkpoint()
        authority.verify_authorized_data(data)
        cpu_runtime.checkpoint()
        cases, scanned = read_target_prefix(raw["file"]["path"], targets, plan["max_prefix_rows"])
        old_errors = {}
        with Path(plan["prefix_rejections"]["path"]).open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if row["cid"] in targets:
                    old_errors[row["cid"]] = row
        for case in cases:
            cpu_runtime.checkpoint()
            case["original_prefix_rejection"] = old_errors.get(case["cid"])
        with ThreadPoolExecutor(max_workers=min(16, len(cases))) as pool:
            results = list(pool.map(diagnose_case, cases))
        cpu_runtime.checkpoint()
        authority.verify_final_stats(data)
        dump_new(out / "case_stage_traces.json", {"cases": results})
        errors = Counter(s["stage"] for result in results for s in result["stages"] if s["status"] == "ERROR")
        report = {"schema": "pubchem_prefix_feature_stage_diagnostic_cpu_receipt_v1", "status": "READ_ONLY_STAGE_TRACES_RECORDED_NO_REPAIR",
                  "node": node, "job_id": os.environ["SLURM_JOB_ID"], "plan": reference(plan_path), "root_submission": reference(intent_path),
                  "original_prefix": plan["prefix_receipt"], "registered_screen_source": current_source, "cpu_runtime_proof": cpu_proof,
                  "raw_source": raw["file"], "data_authority": data, "selected_cids": sorted(targets),
                  "selected_cases": len(cases), "prefix_rows_parsed": scanned, "prefix_row_cap": plan["max_prefix_rows"],
                  "actual_case_thread_ids": sorted({r["worker_thread_id"] for r in results}), "allocated_cpus": 16,
                  "small_case_threads_requested": min(16, len(cases)), "stage_error_counts": dict(errors),
                  "traces": reference(out / "case_stage_traces.json"), "wall_seconds": time.monotonic() - began,
                  "chemical_rules_changed": False, "feature_repair_applied": False, "source_screening_or_pool_release_performed": False}
        cpu_runtime.checkpoint()
        dump_new(out / "receipt.json", report)
        require(sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) <= plan["peak_output_cap_bytes"], "Diagnostic output cap exceeded")
    except Exception as exc:
        dump_new(out / "failure.json", {"status": "FAILED_READ_ONLY_FEATURE_DIAGNOSTIC", "error_type": type(exc).__name__,
                 "error": str(exc), "wall_seconds": time.monotonic() - began})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root-submit-intent", type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.root_submit_intent)


if __name__ == "__main__":
    main()
