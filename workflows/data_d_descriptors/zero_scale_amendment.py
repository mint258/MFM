"""Explicitly authorized metadata-only continuation of closed TRAIN statistics."""
from copy import deepcopy
from pathlib import Path

from .statistics import D20_SHARED_NAMES, _location_scale


def finalize_amendment(config):
    from .produce import publish, read_json, require_cpu

    require_cpu(config)
    output = Path(config["output"]).resolve()
    approval_path = Path(config["zero_scale_amendment"]).resolve()
    approval = read_json(approval_path)
    if (approval.get("schema") != "D_NEW_LIBRARY_ZERO_SCALE_AMENDMENT_V1"
            or approval.get("id") != "20261122_zero_scale"
            or approval.get("status") != "APPROVED_BEFORE_AMENDED_PRODUCTION"
            or approval.get("statistics_refit") is not False
            or approval.get("epsilon_added") is not False
            or approval.get("raw_arrays_changed") is not False
            or approval.get("existing_D20_D3_D4_changed") is not False
            or set(approval.get("libraries", {})) != {"L1", "L2"}):
        raise ValueError("EXPLICIT_REGISTERED_ZERO_SCALE_AMENDMENT_REQUIRED")
    destination = output / "final_manifest_zero_scale_amendment_20261122.json"
    original = output / "final_manifest.json"
    if (Path(approval["amended_manifest"]).resolve() != destination
            or Path(approval["original_unresolved_manifest"]).resolve() != original):
        raise ValueError("AMENDMENT_MUST_PRESERVE_ORIGINAL_MANIFEST")
    if destination.exists():
        return read_json(destination)
    if config.get("unresolved_libraries"):
        raise ValueError("DO_NOT_COMBINE_AMENDMENT_AND_UNRESOLVED_OVERRIDE")
    if read_json(original).get("status") != "UNRESOLVED":
        raise ValueError("ORIGINAL_UNRESOLVED_CLOSEOUT_REQUIRED")
    manifest = deepcopy(read_json(output / "manifest.json"))
    if set(manifest["libraries"]) != {"L1", "L2"}:
        raise ValueError("REGISTERED_TWO_LIBRARIES_REQUIRED")
    for library, entry in manifest["libraries"].items():
        spec = approval["libraries"][library]
        expected_count = {"L1": 7, "L2": 65}[library]
        excluded = spec["excluded_fields"]
        if (len(excluded) != expected_count or len(set(excluded)) != expected_count
                or spec["excluded_count"] != expected_count):
            raise ValueError("EXACT_APPROVED_ZERO_SCALE_FIELD_COUNT_REQUIRED:" + library)
        if library == "L1" and set(excluded).intersection(D20_SHARED_NAMES):
            raise ValueError("EXISTING_D20_FIELDS_MUST_REMAIN_UNCHANGED")
        marker = output / (library + "_statistics.json")
        if Path(spec["original_statistics"]).resolve() != marker:
            raise ValueError("ORIGINAL_CLOSED_STATISTICS_REFERENCE_REQUIRED:" + library)
        statistics = read_json(marker)  # Missing markers fail; never fit or read arrays.
        fields = statistics["fields"]
        if (statistics.get("library") != library or statistics.get("fit_role") != "TRAIN"
                or [field["name"] for field in fields] != entry["ordered_fields"]):
            raise ValueError("ORIGINAL_TRAIN_FIELD_ORDER_REQUIRED:" + library)
        actual = [field["name"] for field in fields
                  if field["enabled"]
                  and field["normalization_status"] == "ZERO_SCALE_NOT_DIVIDABLE"]
        if actual != excluded:
            raise ValueError("ONLY_EXACT_APPROVED_ZERO_SCALE_FIELDS_MAY_BE_DROPPED:" + library)
        by_name = {field["name"]: field for field in fields}
        if any(_location_scale(by_name[name]["parameters"])[1] != 0.0 for name in excluded):
            raise ValueError("NONZERO_SCALES_MUST_NOT_BE_DROPPED:" + library)
        entry["enabled_columns"] = []
        entry["normalization"] = []
        for column, field in enumerate(fields):
            active = field["enabled"] and field["name"] not in excluded
            parameters = None
            if active:
                # A loader alias only: preserve every original parameter/value.
                parameters = dict(deepcopy(field["parameters"]), field_name=field["name"])
                if "std_population" in parameters and "std_ddof0" not in parameters:
                    parameters["std_ddof0"] = parameters["std_population"]
                entry["enabled_columns"].append(column)
            entry["normalization"].append(parameters)
        entry["statistics"] = str(marker)
        entry["state"] = "PRODUCER_COMPLETE_RECEPTION_PENDING"
        entry["reception_acceptance"] = "pending"
        entry["field_filter_amendment"] = dict(
            id=approval["id"], source=str(approval_path),
            excluded_fields=excluded, removal_reason="original_TRAIN_winsorized_std_exactly_zero",
            original_statistics_preserved=True, statistics_refitted=False)
    manifest["status"] = "PRODUCER_COMPLETE_RECEPTION_PENDING"
    manifest["preregistration_amendment"] = str(approval_path)
    manifest["original_unresolved_manifest"] = str(original)
    publish(destination, manifest, config)
    return manifest
