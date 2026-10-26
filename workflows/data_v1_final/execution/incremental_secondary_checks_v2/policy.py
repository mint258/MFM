"""Exact fixture allowlist and finite output/runtime ceilings."""
from pathlib import Path
import re

from ..cpu_auto_memory_queue_v2 import shared


SCOPE = "incremental_secondary_fifteen_fixtures_v2"
PLAN_SCHEMA = "INCREMENTAL_SECONDARY_FIXTURE_PLAN_V1"
RECEIPT_SCHEMA = "ACTUAL_INCREMENTAL_SECONDARY_FIXTURES_V1"
CHILD_SCHEMA = "ACTUAL_INCREMENTAL_FIXTURE_SUITE_V1"
MODE = "FIXTURE_ONLY"
WALL = 600
CAP = 1024 ** 3
LOG_CAP = 4 * 1024 ** 2
TOTAL = 15
HERE = "workflows/data_v1_final/execution/incremental_secondary_checks_v2"
TECHNICAL_RETRY = {"prior_failed_parent": "4521134", "prior_parent_status": "FAILED_NOT_UPGRADED",
    "why": "PARENT_OWNED_TEMP_DIRECTORY_ENOENT_MONITOR_RACE",
    "same_fifteen_incremental_fixtures_rerun": True, "old_legacy_fixture_suites_rerun": False}

SUITES = [
    {"suite_id": "full_identity_policy", "count": 3, "import_mode": "package",
     "test_path": "workflows/expansion/identity_full_after_profile_v1/test_full_policy.py",
     "module": "workflows.expansion.identity_full_after_profile_v1.test_full_policy",
     "class": "FullIdentityPolicyBoundaries"},
    {"suite_id": "secondary_source_acquisition", "count": 4, "import_mode": "direct",
     "test_path": "workflows/expansion/secondary_source_acquisition_v1/test_v1.py",
     "module": "_incremental_secondary_source_fixtures",
     "class": "SecondarySourceBoundaries", "direct_names": ["contracts", "transport", "profile"]},
    {"suite_id": "portable_secondary_uff", "count": 5, "import_mode": "package",
     "test_path": "workflows/data_v1_final/conformers/portable_secondary_uff_v1/test_portable.py",
     "module": "workflows.data_v1_final.conformers.portable_secondary_uff_v1.test_portable",
     "class": "PortableBoundaries"},
    {"suite_id": "frame_native_precision", "count": 3, "import_mode": "direct",
     "test_path": "workflows/data_v1_final/pprime/frame_native_precision_diagnosis_v1/test_v1.py",
     "module": "_incremental_native_precision_fixtures",
     "class": "NativePrecisionFixtures", "direct_names": ["precision", "tokens"]},
]


def parameters():
    return {"stage": MODE, "suites": SUITES, "expected_test_cases": TOTAL,
        "technical_retry": TECHNICAL_RETRY,
        "isolation": "ONE_FRESH_SEQUENTIAL_PYTHON_PROCESS_PER_SUITE",
        "skips_allowed": 0, "expected_failures_allowed": 0,
        "real_scientific_records_authorized": 0, "network_requests_authorized": 0,
        "new_UFF_tasks_authorized": 0, "new_QM_tasks_authorized": 0,
        "synthetic_temporary_file_IO_allowed": True,
        "synthetic_numerical_and_serialization_fixtures_allowed": True,
        "old_fixture_suites_rerun": False, "parallel_fixture_workers_claimed": False,
        "wall_ceiling_seconds": WALL, "whole_output_cap_bytes": CAP,
        "per_stream_retained_log_cap_bytes": LOG_CAP,
        "forced_signals_authorized": False}


def execution_argv(plan, proof):
    return [shared.PY, "-B", "-m", HERE.replace("/", ".") + ".run",
            "--plan", str(plan), "--startup-proof", str(proof)]


def validate_plan(plan):
    shared.need(plan.get("schema") == PLAN_SCHEMA and plan.get("status") == "READY" and
        plan.get("scope_key") == SCOPE and plan.get("scope_parameters") == parameters() and
        plan.get("scope_mode") == MODE and plan.get("pilot") is True,
        "EXACT_FIFTEEN_FIXTURE_ONLY_PLAN_REQUIRED")
    shared.need(plan.get("wall_seconds") == WALL and plan.get("whole_output_cap_bytes") == CAP and
        plan.get("data_references") == [] and plan.get("scientific_release_authorized") is False,
        "NO_REAL_DATA_OR_SCIENTIFIC_RELEASE_IN_FIXTURE_STAGE")
    out = Path(plan["output_root"])
    shared.need(out.is_absolute() and out.parent == shared.ROOT / "artifacts/incremental_secondary_checks_v2" and
        re.fullmatch(r"[a-z0-9][a-z0-9_]{0,63}", out.name) and
        ".." not in out.parts and not out.is_symlink(), "NEW_OWNED_FIXTURE_OUTPUT_REQUIRED")
    refs = plan.get("code_sources")
    shared.need(type(refs) is list and len(refs) > 4 and
        len({r["path"] for r in refs}) == len(refs), "UNIQUE_COMPLETE_SMALL_CODE_SOURCES_REQUIRED")
    return out


def find_suite(name):
    rows = [row for row in SUITES if row["suite_id"] == name]
    shared.need(len(rows) == 1, "ONLY_EXACT_ALLOWLISTED_SUITE_CAN_RUN")
    return rows[0]
