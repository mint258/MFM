"""Produce source-catalog atom-site evidence; never infer sites from macro counts."""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem

from .pka_macro_targets import full_key
from .pkahub_annotations import transition
from .pprime_tmpfs_queue import capacity

DEFAULT_CATALOG = Path(__file__).resolve().parents[2] / "configs/benchmark_data/pKahub_titratable_catalog.json"


@lru_cache(maxsize=1)
def compiled_catalog(path=str(DEFAULT_CATALOG)):
    catalog = json.loads(Path(path).read_text())
    result = []
    for row in catalog["patterns"]:
        query = Chem.MolFromSmarts(row["smarts"])
        if query is None:
            raise ValueError("Published SMARTS failed to parse: " + row["name"])
        sites = []
        for map_id in row["site_atom_maps"]:
            indices = [a.GetIdx() for a in query.GetAtoms()
                       if a.HasProp("molAtomMapNumber") and a.GetAtomMapNum() == map_id]
            if len(indices) != 1:
                raise ValueError("Published query site map not unique: " + row["name"])
            sites.append(indices[0])
        result.append((row, query, sites))
    return result


def site_evidence(smiles):
    params = Chem.SmilesParserParams()
    params.removeHs = False
    source = Chem.MolFromSmiles(smiles, params)
    if source is None:
        return dict(site_count=None, sites=[], status="GRAPH_UNRESOLVED", blockers=["PARSE_FAILED"])
    mol = Chem.AddHs(source)
    hits = defaultdict(lambda: dict(kinds=set(), groups=set()))
    for spec, query, query_sites in compiled_catalog():
        for match in mol.GetSubstructMatches(query, uniquify=True, maxMatches=100000):
            for query_index in query_sites:
                atom = match[query_index]
                if atom >= source.GetNumAtoms() or mol.GetAtomWithIdx(atom).GetAtomicNum() == 1:
                    raise ValueError("Published heavy-atom site mapped to an added hydrogen")
                hits[atom]["kinds"].add(spec["kind"])
                hits[atom]["groups"].add(spec["name"])
    sites = [dict(model_atom_index=i, kinds=sorted(info["kinds"]),
                  source_group_names=sorted(info["groups"]))
             for i, info in sorted(hits.items())]
    blockers = []
    if len(Chem.GetMolFrags(source)) != 1:
        blockers.append("DISCONNECTED_SOURCE_GRAPH")
    if any(a.GetFormalCharge() for a in source.GetAtoms()):
        blockers.append("CHARGED_ATOMS_NOT_NEUTRALIZED")
    # A catalogue match is not a license to ignore an unmatched nitrogen or donor.
    for atom in source.GetAtoms():
        index, z = atom.GetIdx(), atom.GetAtomicNum()
        if index in hits:
            continue
        if z == 7:
            blockers.append("UNCATALOGUED_NITROGEN:" + str(index))
        elif z in (8, 15, 16, 33, 34) and atom.GetTotalNumHs(includeNeighbors=True):
            blockers.append("UNCATALOGUED_HETEROATOM_DONOR:" + str(index))
    status = ("MULTIPLE_CATALOG_SITES" if len(sites) > 1 else
              "SINGLE_CATALOG_SITE" if len(sites) == 1 and not blockers else
              "SITE_EVIDENCE_UNRESOLVED")
    return dict(site_count=len(sites), sites=sites, status=status, blockers=blockers)


def proposed_target(target, evidence, measured_steps, atom_mapping):
    kind = target["endpoint"].removeprefix("macro_pKa_")
    if evidence["status"] != "SINGLE_CATALOG_SITE":
        return None
    site = evidence["sites"][0]
    if kind not in site["kinds"]:
        return None
    step = (target["charge_pre"], target["charge_post"])
    # A lone reported transition never establishes a site, but additional distinct
    # experimental transitions disprove this conservative one-transition proposal.
    expected = (0, -1) if kind == "acid" else (1, 0)
    if step != expected or measured_steps != {expected}:
        return None
    index = site["model_atom_index"]
    if not 0 <= index < len(atom_mapping) or atom_mapping[index] < 0:
        raise ValueError("Proposed atom has no original source-atom mapping")
    return dict(target,
        endpoint="atomic_pKa_" + kind,
        model_atom_index=index, source_atom_index=atom_mapping[index],
        site_group_names=site["source_group_names"],
        experimental_macro_reused_under_single_site_definition=True,
        experimental_microscopic_annotation=False,
        eligibility_status="PROPOSED_SOURCE_CATALOG_DEFINITION_NOT_FROZEN",
        definition_approved=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--quota-snapshot", required=True, type=Path)
    p.add_argument("--attempt", required=True)
    a = p.parse_args()
    def safe():
        capacity(a.root, a.quota_snapshot, needed=256 * 1024**2)
    safe()
    root = a.root / "directive19/pKahub"
    macro_path = root / "job_4536891/manifest.json"
    macro = json.loads(macro_path.read_text())
    domain = json.loads(Path(macro["source_domain_manifest"]).read_text())
    steps = defaultdict(set)
    atom_mappings = {}
    key_cache = {}
    for batch in pq.ParquetFile(domain["records"]).iter_batches(batch_size=2048):
        safe()
        for row in batch.to_pylist():
            if not row["domain_eligible"]:
                continue
            raw = json.loads(row["original_fields_json"])
            s = raw["reprSMILES_processed"]
            if s not in key_cache:
                key_cache[s] = full_key(s)
            key = key_cache[s]
            step = transition(raw.get("assigned_charge_state_transition"))
            if step is not None:
                steps[key].add(step)
            atom_mappings[row["record_id"]] = row["model_atom_to_source"]
    cache = {}
    evidence_rows, proposals = [], []
    observed_keys = set()
    counts = Counter()
    for role, filename in (("TRAIN_POOL", macro["training_targets"]),
                           ("EXTERNAL_BLIND", macro["blind_targets"])):
        for batch in pq.ParquetFile(filename).iter_batches(batch_size=2048):
            safe()
            for target in batch.to_pylist():
                smiles = target["model_smiles"]
                if smiles not in cache:
                    cache[smiles] = site_evidence(smiles)
                evidence = cache[smiles]
                key = target["full_InChIKey"]
                identity = (role, key)
                if identity not in observed_keys:
                    observed_keys.add(identity)
                    counts[role + ":" + evidence["status"]] += 1
                proposal = proposed_target(target, evidence, steps[key],
                                          atom_mappings[target["geometry_record_id"]])
                evidence_rows.append(dict(
                    target_record_id=target["record_id"], full_InChIKey=key,
                    benchmark_role=role, geometry_dataset=target["geometry_dataset"],
                    geometry_record_id=target["geometry_record_id"],
                    source_model_smiles=smiles, measured_charge_steps_json=json.dumps(sorted(steps[key])),
                    site_evidence_json=json.dumps(evidence), site_status=evidence["status"],
                    proposed_atomic_target=proposal is not None))
                if proposal is not None:
                    proposals.append(proposal)
                    counts[role + ":PROPOSED_ATOMIC_ENDPOINTS"] += 1
    safe()
    out = root / a.attempt
    out.mkdir(exist_ok=False)
    pq.write_table(pa.Table.from_pylist(evidence_rows), out / "site_evidence.parquet", compression="zstd")
    if proposals:
        safe()
        pq.write_table(pa.Table.from_pylist(proposals), out / "proposed_atomic_targets.parquet", compression="zstd")
    catalog = json.loads(DEFAULT_CATALOG.read_text())
    result = dict(status="SITE_DEFINITION_PROPOSAL_READY_NOT_TRAINING_LABELS",
        source_macro_manifest=str(macro_path), source_domain_manifest=macro["source_domain_manifest"],
        source_catalog=str(DEFAULT_CATALOG), source_catalog_reference=catalog["reference"],
        source_catalog_patterns=len(catalog["patterns"]), counts=dict(counts),
        evidence=str(out / "site_evidence.parquet"),
        proposed_atomic_targets=str(out / "proposed_atomic_targets.parquet") if proposals else None,
        single_site_definition_frozen=False, atomic_mechanism_ready=False,
        candidate_identity_units="Complete InChIKey molecules per role; endpoints counted separately",
        microscopic_experimental_records=0, predicted_microspecies_used_as_experimental=False,
        all_molecular_macro_targets_unchanged=True,
        graph_normalization_or_protonation_changes=False,
        no_single_site_inference_from_observed_macro_step_count=True,
        multi_site_microscopic_assignment=False,
        definition_caveat=catalog["scope_caveat"],
        original_data_deleted=False, new_content_hashes=False, independent_numeric_QA=False)
    safe()
    (out / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print("PKA_SITE_EVIDENCE_CLOSED", out / "manifest.json", counts, flush=True)


if __name__ == "__main__":
    main()
