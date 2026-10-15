"""One fixed native-only candidate per Expansion full identity, structure-only.

CSV targets stay opaque. Candidate representatives are chosen in original train
then official-test source order before any geometry attempt. Reuse projects a
complete all-native-atom, chirality-aware bijection and independently verifies
specified stereo from the projected coordinates. No H is deleted; no retry or
seed sweep occurs. Failures stay explicit original members with no fallback.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from downstream_binding_data import canonical, check_seal, encoded, json_input, raw_binding, require, seal, verify_binding
from materialize_downstream_bindings import Budget, OriginalMembership, publish


def native_mapping(reference, target, coordinates, *, maximum_matches=256):
    """Map every source-native atom; full identity alone is never the proof."""
    from rdkit import Chem
    from phychem_mfm.phase1.generated_geometry import _specified_stereo
    left, right = reference.mol, target.mol
    original = [m.ToBinary(Chem.PropertyPickleOptions.AllProps) for m in (left, right)]
    n = reference.n_atoms
    try:
        require(n == target.n_atoms and reference.identity.inchikey == target.identity.inchikey,
                "Same full identity/native cardinality required for candidate projection")
        require(len(Chem.GetMolFrags(left)) == len(Chem.GetMolFrags(right)) == 1,
                "Disconnected native candidate projection is unsupported")
        a, b = Chem.Mol(left), Chem.Mol(right)
        a.RemoveAllConformers(); b.RemoveAllConformers()
        require(not a.GetStereoGroups() and not b.GetStereoGroups(), "Enhanced stereo projection is unsupported")
        Chem.AssignStereochemistry(a, cleanIt=True, force=True); Chem.AssignStereochemistry(b, cleanIt=True, force=True)
        require(Chem.MolToSmiles(a, canonical=True, isomericSmiles=True) == Chem.MolToSmiles(b, canonical=True, isomericSmiles=True),
                "Full native isomeric graphs differ")
        matches = b.GetSubstructMatches(a, useChirality=True, uniquify=False, maxMatches=maximum_matches+1)
        require(0 < len(matches) <= maximum_matches, "Full native mapping absent or exceeds bounded symmetry search")
        def atom_fields(atom):
            return (atom.GetAtomicNum(), atom.GetIsotope(), atom.GetFormalCharge(), atom.GetIsAromatic(),
                    atom.GetNumRadicalElectrons(), atom.GetNumExplicitHs(), atom.GetNumImplicitHs(), atom.GetNoImplicit())
        valid = []
        for mapping in matches:
            if len(mapping) != n or set(mapping) != set(range(n)):
                continue
            if any(atom_fields(a.GetAtomWithIdx(i)) != atom_fields(b.GetAtomWithIdx(mapping[i])) for i in range(n)):
                continue
            if any((bond := b.GetBondBetweenAtoms(mapping[x.GetBeginAtomIdx()], mapping[x.GetEndAtomIdx()])) is None
                   or (str(bond.GetBondType()), bond.GetIsAromatic(), bond.GetIsConjugated()) !=
                      (str(x.GetBondType()), x.GetIsAromatic(), x.GetIsConjugated()) for x in a.GetBonds()):
                continue
            if a.GetNumBonds() != b.GetNumBonds():
                continue
            # Independent clean graph CIP labels, mapped atom by atom.
            if any((a.GetAtomWithIdx(i).GetProp("_CIPCode") if a.GetAtomWithIdx(i).HasProp("_CIPCode") else None) !=
                   (b.GetAtomWithIdx(mapping[i]).GetProp("_CIPCode") if b.GetAtomWithIdx(mapping[i]).HasProp("_CIPCode") else None)
                   for i in range(n)):
                continue
            valid.append(tuple(mapping))
        require(valid, "Native candidate projection lacks complete atom/bond/stereo proof")
        mapping = min(valid)  # deterministic symmetry convention, disclosed below
        result = [None] * n
        for source_id, target_id in enumerate(mapping):
            result[target_id] = tuple(coordinates[source_id])
        work = Chem.Mol(right); work.RemoveAllConformers()
        conf = Chem.Conformer(n); conf.Set3D(True)
        for i, xyz in enumerate(result):
            conf.SetAtomPosition(i, xyz)
        work.AddConformer(conf, assignId=True)
        work = Chem.AddHs(work, addCoords=True)
        stereo = _specified_stereo(work, work, n, 0)
        proof = seal({"schema_version": "phase1_expansion_complete_native_candidate_projection_v1",
            "reference_to_target_native_ids": list(mapping), "native_atom_count": n,
            "complete_native_bijection": True, "isotope_charge_hydrogen_counts_and_all_bonds_preserved": True,
            "fresh_graph_CIP_and_projected_3D_specified_stereo_verified": True,
            "stereo_validation": stereo, "matching_qualified_count": len(valid),
            "selection": "lexicographically first complete chirality-aware mapping; no target labels or scores",
            "max_matches": maximum_matches, "native_H_deleted": False,
            "AddHs_for_stereo_check_only": True, "encoder_extra_H_rows": 0,
            "chemical_geometry_or_stereochemistry_truth_verified": False})
        return result, proof
    finally:
        require([m.ToBinary(Chem.PropertyPickleOptions.AllProps) for m in (left, right)] == original,
                "Source molecules changed during native candidate projection")


def run(request, output, budget):
    project = Path(request["project"]).absolute(); sys.path.insert(0, str(project)); sys.dont_write_bytecode = True
    from phychem_mfm.training.checkpoint import source_provenance
    from phychem_mfm.phase1 import downstream_source_records as records
    from phychem_mfm.phase1.downstream_structures import read_az_raw_smiles
    from phychem_mfm.phase1.generated_geometry import prepare_native_generated_geometry
    from phychem_mfm.phase1.source_geometry import geometry_tensor_sha256
    import torch
    source_before = source_provenance(project)
    actual = json_input(request["source_receipt"], check=budget.check)["actual_source"]
    require(source_before["source_sha256"] == actual["source_sha256"] and source_before["git_commit"] == actual["git_commit"],
            "Actual source receipt differs")
    protocol = json_input(request["protocol"], check=budget.check); check_seal(protocol)
    require(protocol["state"] == "frozen", "Already frozen geometry rule required")
    definition = next(d for d in protocol["downstream"]["dataset_definitions"] if d["dataset_id"] == "expansionrx")
    recipe = protocol["downstream"]["geometry_and_mapping_policy"]["generated_candidate_recipe"]
    require(recipe["schema_version"] == "phase1_native_generated_geometry_v1" and recipe["accepted_mmff_status"] == 0
            and recipe["embedding_max_iterations"] == 200 and recipe["embedding_timeout_seconds"] == 2
            and recipe["mmff_max_iterations"] == 500 and recipe["num_threads"] == 1
            and recipe["fallback_or_seed_sweep"] is False and recipe["rdkit_version"] == "2025.09.5"
            and recipe["legacy_stereo_perception"] is True, "Unsupported sealed geometry recipe")
    membership = OriginalMembership(protocol, request["membership_summary"], budget.check)
    helper_ref = request["graph_join_helper"]; verify_binding(helper_ref, budget.check)
    spec = importlib.util.spec_from_file_location("bound_expansion_source_join", helper_ref["path"])
    helper = importlib.util.module_from_spec(spec); sys.modules[spec.name] = helper; spec.loader.exec_module(helper)
    selection, sources, structures, representatives = [], [], {}, {}
    # Only the two raw structure/name columns are UTF8-decoded here.
    for bucket in ("expansionrx_train", "expansionrx_test"):
        original = membership.rows[bucket]; ref = original[0]["source_frame"]["source_file"]
        require(ref["path"] == definition["training_path" if bucket.endswith("train") else "official_test_path"],
                "Sealed Expansion source path differs")
        verify_binding(ref, budget.check); sources.append(ref)
        content = Path(ref["path"]).read_bytes(); frames = records._csv_rows(content, with_spans=True)
        _, _, header, _ = next(frames); names = tuple(helper._text(v) for v in header)
        require(len(names) == len(set(names)) and "SMILES" in names and "Molecule Name" in names, "Raw source header differs")
        for ordinal, member in enumerate(original, 1):
            budget.check(); start, end, fields, spans = next(frames)
            helper._joined_member(bucket, member, ordinal, fields, names, spans, start, end, content, ref)
            native = read_az_raw_smiles(helper._text(fields[names.index("SMILES")]))
            uid, key = member["member_uid"], native.identity.inchikey
            structures[uid] = native
            representative = representatives.setdefault(key, uid)
            material = canonical({"recipe": "native_etkdgv3_mmff94_seed_v1", "atomic_numbers": native.atomic_numbers,
                                  "ordered_graph_hash": records.source_ordered_graph_sha256(native)})
            selection.append({"member_uid": uid, "source_member_index": member["member_index"],
                "declared_role": member["declared_role"], "member_row_sha256": canonical(member),
                "raw_source": ref, "raw_frame_sha256": member["source_frame"]["raw_frame_sha256"],
                "structural_sha256": native.provenance["source_sha256"], "full_inchikey": key,
                "representative_member_uid": representative, "native_n_atoms": native.n_atoms,
                "seed_material_sha256": material, "seed": 1 + int(material[:8], 16) % (2**31-2)})
        require(next(frames, None) is None, "Expansion raw source has extra rows")
    selection_receipt = seal({"schema_version": "phase1_expansion_target_opaque_candidate_selection_v1",
        "protocol": request["protocol"], "membership_summary": request["membership_summary"],
        "records": selection, "representative_count": len(representatives), "target_fields_decoded": False,
        "one_generation_attempt_per_full_identity": True, "selection": "first original train then official-test source row"})
    selection_ref = publish(output, "selection.json", selection_receipt, budget)
    candidates = {}
    for uid in representatives.values():
        budget.check(); row = next(s for s in selection if s["member_uid"] == uid)
        try:
            geometry = prepare_native_generated_geometry(structures[uid], seed=row["seed"])
            candidates[uid] = {"ready": True, "coords": geometry.native_coordinates_float64.tolist(),
                               "geometry_provenance": deepcopy(geometry.provenance)}
        except ValueError as exc:
            candidates[uid] = {"ready": False, "coords": None, "failure_class": type(exc).__name__,
                "failure_message_sha256": hashlib.sha256(str(exc).encode()).hexdigest()}
    result_rows = []
    for selected in selection:
        budget.check(); uid, rep = selected["member_uid"], selected["representative_member_uid"]
        candidate, native = candidates[rep], structures[uid]
        coords, mapping, error = None, None, None
        if candidate["ready"]:
            try:
                if uid == rep:
                    coords = deepcopy(candidate["coords"])
                    mapping = seal({"schema_version": "phase1_expansion_complete_native_candidate_projection_v1",
                        "status": "EXACT_ORIGINAL_NATIVE_ROWS", "reference_to_target_native_ids": list(range(native.n_atoms)),
                        "native_atom_count": native.n_atoms, "complete_native_bijection": True,
                        "same_source_structure_object": True, "source_structure_sha256": native.provenance["source_sha256"],
                        "stereo_validation": deepcopy(candidate["geometry_provenance"]["stereo_validation"]),
                        "geometry_provenance_sha256": candidate["geometry_provenance"]["geometry_provenance_sha256"],
                        "extra_geometry_attempt_or_stereo_generation": False})
                else:
                    coords, mapping = native_mapping(structures[rep], native, candidate["coords"])
            except ValueError as exc:
                error = {"failure_class": type(exc).__name__, "failure_message_sha256": hashlib.sha256(str(exc).encode()).hexdigest()}
        else:
            error = {k: v for k, v in candidate.items() if k.startswith("failure_")}
        hashes = None
        if coords is not None:
            fp64 = torch.tensor(coords, dtype=torch.float64); pos = fp64.to(torch.float32)
            require(bool(torch.isfinite(pos).all()), "Projected native coordinate FP32 overflow")
            hashes = {"native_coordinates_float64": geometry_tensor_sha256(fp64),
                      "pos": geometry_tensor_sha256(pos), "x": geometry_tensor_sha256(torch.tensor(native.x, dtype=torch.long)),
                      "source_atom_ids": geometry_tensor_sha256(torch.arange(native.n_atoms, dtype=torch.long))}
        result_rows.append(seal({**selected, "status": "GEOMETRY_READY" if coords is not None else "NOT_READY",
            "native_x": list(native.x), "native_coordinates_float64": coords, "native_tensor_hashes": hashes,
            "representative_geometry": candidate.get("geometry_provenance"), "native_projection": mapping,
            "failure": error, "target_fields_decoded": False,
            "legacy_DEV_AddHs_cache_used": False, "all_original_native_atoms_preserved": True}))
    membership.verify_unchanged(budget.check)
    for ref in (request["protocol"], request["source_receipt"], helper_ref, *sources):
        verify_binding(ref, budget.check)
    source_after = source_provenance(project); require(source_after == source_before, "Source changed during generation")
    budget.check(); budget.finalizing = True
    receipt = seal({"schema_version": "phase1_expansion_frozen_native_geometry_inventory_v1", "complete": True,
        "status": "COMPLETE_FIXED_RECIPE_GEOMETRY_INVENTORY", "target_fields_decoded": False,
        "membership_summary_sha256": request["membership_summary"]["sha256"], "selection": selection_ref,
        "record_count": len(result_rows), "representative_count": len(candidates), "records": result_rows,
        "ready_count": sum(r["status"] == "GEOMETRY_READY" for r in result_rows),
        "not_ready_count": sum(r["status"] == "NOT_READY" for r in result_rows),
        "all_generation_success_claimed": False, "source_before": source_before, "source_after": source_after,
        "input_raw_bytes_unchanged": True, "elapsed_seconds": time.monotonic()-budget.started})
    publish(output, "geometry_inventory.json", receipt, budget)
    return receipt


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--request", required=True); parser.add_argument("--expected-request-sha256", required=True)
    args = parser.parse_args(); ref = raw_binding(args.request); require(ref["sha256"] == args.expected_request_sha256, "Request SHA differs")
    request = json_input(ref); check_seal(request)
    require(request.get("schema_version") == "phase1_expansion_native_geometry_request_v1"
            and request.get("state") == "READY_ACTUAL_BINDINGS"
            and str(request.get("actual_job_id")) == os.environ.get("SLURM_JOB_ID"), "Actual immutable execution request required")
    require(os.getuid() == 1278 and socket.gethostname().split(".")[0] == "compute-0-20"
            and os.environ.get("CUDA_VISIBLE_DEVICES") == "" and os.environ.get("SLURM_JOB_ID", "").isdigit(),
            "Root-owned CPU20 allocation required")
    raw = subprocess.check_output(["scontrol", "show", "job", "-o", os.environ["SLURM_JOB_ID"]], timeout=15)
    require(len(raw) <= 65536, "Allocation response cap exceeded")
    live = dict(t.split("=", 1) for t in raw.decode("ascii").split() if "=" in t)
    require(live.get("UserId") == "zixiao(1278)" and live.get("NodeList") == "compute-0-20"
            and live.get("JobState") == "RUNNING" and live.get("NumCPUs") == "16"
            and live.get("MinMemoryNode") in ("64G", "65536M", "65536MB"), "Owned16CPU64G allocation differs")
    output = Path(request["output_dir"]); output.mkdir(parents=True, exist_ok=False); budget = Budget(request["budgets"], output)
    try:
        verify_binding(request["executing_helper"], budget.check)
        require(Path(request["executing_helper"]["path"]).absolute() == Path(__file__).absolute(), "Executing helper path differs")
        for ref in request["implementation_files"]:
            verify_binding(ref, budget.check)
        result = run(request, output, budget)
        for ref in request["implementation_files"]:
            verify_binding(ref, budget.check)
        print(encoded({k: result[k] for k in ("status", "complete", "record_count", "ready_count", "not_ready_count")}).decode()); return 0
    except Exception as exc:
        budget.finalizing = True
        publish(output, "FAILED.json", seal({"complete": False, "error_class": type(exc).__name__,
            "error_message_sha256": hashlib.sha256(str(exc).encode()).hexdigest()}), budget)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
