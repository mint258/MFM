"""Original physical-record roles only; never apply frozen training-molecule roles."""
from ..identity_v2 import projection_v2 as original
from ..common import require


ROLE_SEMANTICS = "ORIGINAL_PHYSICAL_RECORD_MEMBERSHIP_ONLY"
EXPECTED_PHYSICAL_ROLES_NOT_MEASURED_BY547 = {
    "SOURCE_TRAIN": 11104772, "SOURCE_FULL": 115760, "SOURCE_ROUTINE": 11322, "SOURCE_EMBARGO": 4900}


def formal_row(row):
    value = original.formal_row(row)
    flags = {name: row[name] for name in ("member_train", "member_full", "member_routine")}
    value["role"] = "SOURCE_ROUTINE" if flags["member_routine"] else "SOURCE_FULL" if flags["member_full"] else "SOURCE_TRAIN"
    value["memberships"] = ["SOURCE_FULL", "SOURCE_ROUTINE"] if flags["member_routine"] else [value["role"]]
    value.update(original_physical_member_flags=flags, role_semantics=ROLE_SEMANTICS, effective_training_roles_applied=False)
    return value


def embargo_row(row):
    value = original.embargo_row(row)
    value.update(role="SOURCE_EMBARGO", memberships=["SOURCE_EMBARGO"], original_physical_member_flags=None,
                 role_semantics=ROLE_SEMANTICS, effective_training_roles_applied=False)
    return value


def whole_source_scope(*, total_rows, unique_source_ids, role_counts, embargo_classes, missing_identity_rows, raw_bool_counts):
    require(total_rows == unique_source_ids == 11236754 and dict(role_counts) == EXPECTED_PHYSICAL_ROLES_NOT_MEASURED_BY547 and
            dict(embargo_classes) == {"known_fullkey_embargo": 4100, "unknown_non_h_composition_embargo": 800} and
            missing_identity_rows == 0 and raw_bool_counts == {"member_train": 11104772, "member_full": 127082, "member_routine": 11322},
            "Whole original physical-member flags/unique IDs differ from historical expected values")
    return {"status": "ALL_ORIGINAL_PHYSICAL_RECORD_MEMBERSHIPS_AND_EMBARGO_EXPORTED", "records": total_rows,
            "role_semantics": ROLE_SEMANTICS, "effective_training_roles_applied": False,
            "original_physical_membership_counts": dict(role_counts), "observed_original_bool_counts": raw_bool_counts,
            "historical_expected_physical_counts": EXPECTED_PHYSICAL_ROLES_NOT_MEASURED_BY547,
            "547_metadata_measured_bool_counts": False, "later_common_filter_applied": False,
            "frozen_training_molecule_roles_applied": False}
