"""Final-D4 population gate; source-TRAIN anomaly references are insufficient."""
from __future__ import annotations

from support import load,require


def validate_authority(common,diagnostic,roles_sha):
    if common.get("status")!="COMMON_POPULATION_V1_FROZEN":
        raise ValueError("FINAL_NORMALIZATION_COMMON_POPULATION_NOT_FROZEN")
    if common.get("roles_manifest_sha256")!=roles_sha or not common.get("membership_tables"):
        raise ValueError("FINAL_COMMON_ROLE_OR_MEMBERSHIP_PINS_MISSING")
    if diagnostic.get("status")!="SEEN_MOLECULE_UNSEEN_GEOMETRY_DIAGNOSTIC_FROZEN":
        raise ValueError("FINAL_NORMALIZATION_DIAGNOSTIC_GEOMETRIES_NOT_FROZEN")
    if (diagnostic.get("all_excluded_geometries_materialized") is not True
            or diagnostic.get("diagnostic_TRAIN_molecules")!=20000
            or diagnostic.get("excluded_PM7_geometries")!=20000
            or diagnostic.get("excluded_Sprime_geometries")!=20000):
        raise ValueError("DIAGNOSTIC_EXCLUSION_COVERAGE_NOT_EXACT")
    if not diagnostic.get("excluded_geometry_tables"):
        raise ValueError("DIAGNOSTIC_EXCLUSION_PHYSICAL_PINS_MISSING")


def require_final_authority(common_pin,diagnostic_pin,roles_pin):
    common=load(require(common_pin));diagnostic=load(require(diagnostic_pin));require(roles_pin)
    validate_authority(common,diagnostic,roles_pin["sha256"])
    if diagnostic.get("common_population_manifest_sha256")!=common_pin["sha256"]:
        raise ValueError("DIAGNOSTIC_AND_COMMON_POPULATION_BINDINGS_DIFFER")
    for pin in common["membership_tables"]+diagnostic["excluded_geometry_tables"]:require(pin)
    return {"common_population":common_pin,"diagnostic_exclusions":diagnostic_pin,"roles":roles_pin,
        "status":"POPULATION_AUTHORITY_VALIDATED_STILL_REQUIRES_MASKED_QUANTILES_AND_READBACK"}
