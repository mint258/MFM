"""Metadata-only exhaustive 146-component/129-target proposal, no label reads."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def pin(path):
    p=Path(path);raw=p.read_bytes()
    return {"path":str(p.absolute()),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}


def require(item):
    actual=pin(item["path"])
    if any(actual[k]!=item[k] for k in ("bytes","sha256")):
        raise ValueError("PROPOSAL_METADATA_SOURCE_CHANGED:"+item["path"])
    return item["path"]


def aggregation(field):
    level=field["level"];leaf=field["source_path"].split(".")[-1]
    if level=="molecule":
        return ("TRAIN_ELEMENT_RESIDUAL_SCALAR" if leaf=="heat_of_formation_kcal_mol" else "RAW_SCALAR",
                "one existing molecular scalar; HOF alone requires its own TRAIN element residual")
    if level=="molecule_vector":
        return "JOINT_XYZ_L2", "sqrt(x^2+y^2+z^2); all three components jointly valid; fixed source origin"
    if level=="molecule_tensor":
        return "SYMMETRIC_FROBENIUS", "sqrt(xx^2+yy^2+zz^2+2*(xy^2+xz^2+yz^2)); all six jointly valid"
    if level=="atom_vector":
        return "ATOM_VECTOR_RMS_NORM", "sqrt(sum_atoms(norm(xyz)^2)/N_atoms); complete N-by-3 target; global L2 reported only as sensitivity"
    if level=="atom":
        if leaf in {"atomic_shell_population_e","enpart_one_center_eV","FOD_atom_e","SASA_atom_A2"}:
            return "SEMANTIC_ATOM_SUM", "signed sum of every semantically owned valid atom row; no absolute-value substitution"
        return "SEMANTIC_ATOM_RMS", "sqrt(mean(v_atom^2)) on the exact semantic atom scope; signed mean and sum_abs are separate sensitivities"
    if level=="sparse_atom_pair":
        if leaf=="enpart_pairs_eV":
            return "STORED_PAIR_ENERGY_SUM", "signed sum of stored atom-pair energy terms, once per declared pair key; omitted pairs not imputed"
        return "STORED_PAIR_RMS", "sqrt(mean(v_entry^2)) of exact stored pair/orbital-entry multiset; no dense N^2 completion"
    raise ValueError("UNCLASSIFIED_ENABLED_LEVEL:"+level)


def nature(field):
    leaf=field["source_path"].split(".")[-1];level=field["level"]
    if field["group"]=="D":
        if leaf=="MolMR":return "MOLECULAR_ATOM_ADDITIVE_ESTIMATOR", "RDKit Crippen.cpp sums atomic MR; molar bulk quantity and molecular pooling are distinct meanings"
        if leaf=="HallKierAlpha":return "MOLECULAR_ATOM_ADDITIVE_CORRECTION", "RDKit HallKierAlpha sums dimensionless atom-type/radius corrections; previous generic intensive tag needs review"
        if leaf=="BertzCT":return "NONADDITIVE_TOPOLOGICAL_INFORMATION_INDEX", "RDKit entropy/count expression contains count*log(count); dimensionless does not establish intensivity"
        if leaf in {"MolLogP","FractionCSP3"}:return "RATIO_OR_LOG_RATIO_INTENSIVE_DESCRIPTOR", "ratio/log-ratio definition; an additive estimator does not make logP thermodynamically extensive"
        if leaf=="ExactMolWt" or leaf.startswith("Num") or leaf in {"HeavyAtomCount","RingCount"}:
            return "ADDITIVE_COMPOSITION_OR_GRAPH_COUNT", "mass/count descriptor; graph-rule definition and physical amount-of-substance scaling distinguished"
        if leaf in {"TPSA","LabuteASA","volume_A3","SASA_total_A2","SASA_atom_A2"}:
            return "GEOMETRIC_OR_ATOM_ADDITIVE_SURFACE_VOLUME", "size-dependent estimator/surface/volume; not inferred from rho or assumed linear in heavy atom count"
        if leaf.startswith("PMI"):return "MASS_AND_GEOMETRY_SECOND_MOMENT", "inertia scales with mass and squared distance; not a simple atom-count extensive scalar"
        if leaf=="PBF_A":return "NONADDITIVE_GEOMETRIC_MEAN_DISTANCE", "mean distance to best-fit plane; length unit does not decide intensive/extensive pooling"
        raise ValueError("UNCLASSIFIED_DESCRIPTOR:"+leaf)
    if level in {"atom","atom_vector","sparse_atom_pair"}:
        return "LOCAL_ATOM_OR_PAIR_PHYSICAL_TARGET", "local supervision; a molecule-level size diagnostic does not change local head/pooling"
    if level in {"molecule_vector","molecule_tensor"}:
        return "PHYSICAL_MULTIPOLE_MOMENT_FIXED_ORIGIN", "rotation-covariant physical moment, origin-sensitive where applicable; invariant norm is only the size statistic"
    if field["element_reference_eligible"]:
        return "MOLECULAR_ENERGY_OR_SOLVATION_CONTRIBUTION", "energy definition supports additive-fragment candidate with method/context dependence; source TRAIN fit needed"
    if leaf in {"cosmo_area_A2","cosmo_volume_A3"}:
        return "GEOMETRIC_SURFACE_OR_VOLUME", "actual area/volume; no inference from size correlation"
    if leaf=="NFOD_e":return "INTEGRATED_ELECTRONIC_POPULATION", "integrated FOD electron-number-like quantity; local sum counterpart remains separately supervised"
    if leaf in {"EA_eV","IP_eV","vertical_EA_eV","vertical_IP_eV","homo_eV","lumo_eV"}:
        return "ELECTRONIC_ENERGY_DIFFERENCE_OR_ORBITAL_LEVEL", "intensive-like molecular electronic descriptor; not total molecular energy"
    raise ValueError("UNCLASSIFIED_PHYSICAL_NATURE:"+field["field_key"])


def unit_review(field):
    leaf=field["source_path"].split(".")[-1]
    result={"stored_registry_unit":field["unit"],"stored_source_unit":field["source_unit"],
            "proposed_unit":field["unit"],"numeric_values_or_scales_changed":False,
            "status":"INHERITED_FROZEN_METADATA_PENDING_D1_JOINT_SIGNOFF"}
    if leaf=="MolMR":
        result.update(proposed_unit="cm^3 mol^-1 (candidate numeric convention only)",
            dimension_authority="IUPAC Green Book p37: molar refraction has SI dimension m^3 mol^-1",
            status="PENDING_ORIGINAL_CALIBRATION_NUMERIC_SCALE_AND_RUNTIME_LINEAGE",
            source_scale_proven=False)
    elif leaf=="super_heavy_atom_rows" and field["component"] in {"Dn","De"}:
        result.update(proposed_unit="eV^-1",status="SOURCE_DIMENSIONAL_INFERENCE_REQUIRES_EXPLICIT_D1_ACCEPTANCE")
    elif leaf=="fukui" or "fukui_Coulson" in field["source_path"]:
        result.update(proposed_unit="1 versus electron-number/charge-difference convention unresolved",
            status="CONFLICT_PROTOCOL_DIMENSIONLESS_VERSUS_REGISTRY_E_NO_AUTOMATIC_RESCALING")
    elif field["unit"]=="bond-order population":
        result.update(proposed_unit="1 (bond-order/electron-population numerical convention)",
            status="NOTATION_RECONCILIATION_REQUIRED_NO_NUMERIC_CONVERSION")
    return result


def build(cfg, registry):
    fields=sorted((f for f in registry["fields"] if f["status"]=="enabled"),key=lambda f:f["field_key"])
    if len(fields)!=146:raise ValueError("EXPECTED_146_ENABLED_COMPONENTS")
    components=[];targets=collections.defaultdict(list)
    for fid,f in enumerate(fields):
        op,formula=aggregation(f);kind,basis=nature(f)
        joint=f["level"] in {"molecule_vector","molecule_tensor"}
        target=(f["field_key"].rsplit(".",1)[0]+".invariant") if joint else f["field_key"]
        row={"field_id":fid,"field_key":f["field_key"],"physical_statistic_target_id":target,
            "group":f["group"],"task":f["task"],"registry_id":f["registry_id"],"source_path":f["source_path"],
            "component":f["component"],"level":f["level"],"shape":f["shape"],
            "primary_aggregation":op,"formula":formula,"unit_review":unit_review(f),
            "previous_extensivity_tag":f["extensivity"],"proposed_definition_based_nature":kind,"nature_basis":basis,
            "rho":None,"rho_pair_n":None,"rho_status":"NOT_MEASURED_NEW_AGGREGATION_PROPOSAL",
            "family_v1_final":None,"geometry_frame_or_origin_proof":f.get("reference_frame"),
            "all_pending_before_freeze":["Root aggregation/scope review","complete canonical masked coverage",
                "correct TRAIN population and HOF references","measured primary/sensitivity rho and missingness by size",
                "source units/runtime provenance reconciliation","model family/head/pooling joint agreement"]}
        if f["source_path"].endswith("sigma_pi_entries"):
            row["invariance_status"]="PENDING_PRINTED_ORBITAL_BASIS_SCOPE_PROOF_RMS_ONLY_PERMUTATION_INVARIANT_UNTIL_THEN"
            row["all_pending_before_freeze"].append("orbital-entry basis/rotation/cutoff completeness review; no claim of proved invariant")
        components.append(row);targets[target].append(f["field_key"])
    levels=dict(collections.Counter(f["level"] for f in fields))
    if len(targets)!=129 or levels!={k:v for k,v in cfg["expected_counts"].items() if k not in {"enabled_components","physical_statistic_targets"}}:
        raise ValueError("PHYSICAL_TARGET_OR_LEVEL_PARTITION_CHANGED")
    inactive=collections.Counter(f["status"] for f in registry["fields"] if f["status"]!="enabled")
    return {"schema":"SIZE_SEMANTICS_PROPOSAL_V1","status":"PROPOSAL_NOT_APPROVED_NOT_MEASURED_NOT_FINAL_REGISTRY",
        "counts":{"components":146,"physical_statistic_targets":129,"levels":levels,"other_registry_statuses":dict(inactive)},
        "targets":[{"target_id":key,"member_field_keys":value,"rho":None,"rho_status":"NOT_MEASURED"} for key,value in sorted(targets.items())],
        "components":components,"rank_and_scope_policy":{k:cfg[k] for k in ("primary_rank_weighting","secondary_rank_weighting",
            "primary_array_eligibility","partial_sensitivity","source_scope_before_final_authority","final_scope",
            "size_threshold_abs_rho","rho_tail_policy","minimum_pairs_for_defined_coefficient","constant_policy","zero_policy","Pprime")},
        "source_lineage_pins":[cfg["registry"],*cfg["lineage_sources"]],"scientific_label_bodies_read":False,
        "registry_or_source_units_modified":False,"model_target_head_count_inferred":False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",required=True);p.add_argument("--output-root",required=True);a=p.parse_args()
    cfg=load(a.config)
    for item in [cfg["registry"],*cfg["lineage_sources"]]:require(item)
    result=build(cfg,load(cfg["registry"]["path"]))
    out=Path(a.output_root);out.mkdir(parents=True,exist_ok=False)
    raw=(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+"\n").encode()
    (out/"component_proposal.json").write_bytes(raw)
    lines=["# 全146分量待冻结清单（提案，rho均未测）","", "| field | target | primary aggregation | unit review | physical nature |", "| --- | --- | --- | --- | --- |"]
    for r in result["components"]:
        lines.append("| "+" | ".join(str(r[k]) for k in ("field_key","physical_statistic_target_id","primary_aggregation"))+" | "+r["unit_review"]["status"]+" | "+r["proposed_definition_based_nature"]+" |")
    (out/"component_pending_freeze.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    receipt={"status":result["status"],"config":pin(a.config),"generator":pin(__file__),"outputs":[pin(out/n) for n in ("component_proposal.json","component_pending_freeze.md")],"counts":result["counts"],"scientific_label_bodies_read":False}
    (out/"metadata_receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"components":146,"physical_statistic_targets":129,"output":str(out)}))


if __name__=="__main__":main()
