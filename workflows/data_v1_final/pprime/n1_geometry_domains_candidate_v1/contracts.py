"""Pure candidate contracts; checked witnesses are supplied by a future CPU port."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

KEY = "n1_pprime_geometry_domains_candidate_v1"
REQUEST = "N1_PPRIME_GEOMETRY_DOMAINS_CANDIDATE_REQUEST_V1"
SCHEMA = "N1_PPRIME_GEOMETRY_DOMAINS_NONEXECUTABLE_CANDIDATE_V1"
INT64_MAX = (1 << 63) - 1
ORDER_SEED = 20261025
SOURCE = "uff_sprime"
EXTRA_NAMESPACE = "data_v1_n1_pprime2"
DOMAINS = ("ordinary_sprime_training", "pprime_compute_first2", "pprime_training_after_diagnostic")
PACKET_CAP = 256 << 20
METHODS = 3
EXECUTION_IMPLEMENTED = False

class ContractError(ValueError):
    pass

def need(condition, message):
    if not condition:
        raise ContractError(message)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")

def value_sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def physical_id(value):
    # Same pure nonnegative-int64 boundary as the original identity.py. This
    # new allocator has a different namespace; original ordinary IDs never move.
    need(type(value) is int and 0 <= value <= INT64_MAX, "NONNEGATIVE_INT64_PHYSICAL_ID_REQUIRED")
    return value

def sha(value):
    need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "EXACT_SHA256_REQUIRED")
    return value

def text(value):
    need(type(value) is str and value and not any(c in value for c in "\x00\r\n"), "LITERAL_NONEMPTY_ID_REQUIRED")
    return value

def reference(value, *, small=False):
    need(type(value) is dict and set(value) == {"path", "bytes", "sha256"}, "EXACT_PRODUCER_TRIPLE_REQUIRED")
    text(value["path"])
    need(type(value["bytes"]) is int and value["bytes"] > 0 and
         (not small or value["bytes"] <= 2 << 20), "REFERENCE_INTEGER_SIZE_BOUND_REQUIRED")
    sha(value["sha256"])
    return dict(value)

def data_reference(value):
    ref = reference(value)
    need(ref["path"].startswith(("/share/home/zixiao/descriptor_analysis/runs/",
                                 "/gfshome/alpha/codex_data_v1_20261026/")) and
         ".." not in ref["path"].split("/") and "//" not in ref["path"], "LITERAL_DATA_LOCATOR_REQUIRED")
    return ref

def owner(value):
    need(type(value) is dict and set(value) == {"endpoint", "uid", "job_id"}, "EXACT_ORIGIN_ENDPOINT_UID_JOB_REQUIRED")
    text(value["endpoint"]); text(value["job_id"])
    need(type(value["uid"]) is int and value["uid"] > 0, "ORIGIN_UID_REQUIRED")
    return dict(value)

def source_bindings():
    path = Path(__file__).with_name("source_evidence_v1.json")
    need(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= 2 << 20,
         "FROZEN_SMALL_SOURCE_EVIDENCE_REQUIRED")
    value = json.loads(path.read_bytes())
    need(value["schema"] == "N1_GEOMETRY_DOMAINS_SOURCE_EVIDENCE_V1" and
         value["source_only_not_execution_authority"] is True, "SOURCE_BINDING_SCHEMA_REQUIRED")
    return value["bindings"]

