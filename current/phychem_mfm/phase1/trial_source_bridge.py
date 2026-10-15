"""Read-only reuse of old trial evidence after a byte-checked interface change.

This verifies three supplied source snapshots and original retained metadata.
It neither reruns old optimization nor verifies GPU protection or chemistry.
The live formal gate and runner retain their separate allocation/source checks.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re

BRIDGE_FIELD = "trial_evidence.producer_consumer_bridge_sha256"
BRIDGE_SCHEMA = "phase1_trial_producer_consumer_bridge_v1"
CORE_SCHEMA = "phase1_trial_bridge_core_bytes_v1"
CORE_COUNT = 120
MAX_METADATA_BYTES = 4 << 20
MAX_SNAPSHOT_BYTES = 8 << 20
MAX_TRIAL_BYTES = 16 << 20
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
# No wildcard permits an altered optimizer, model, label or data-view module.
INTERFACE_PATHS = frozenset({
    "phychem_mfm/phase1/formal_gate.py",
    "phychem_mfm/phase1/formal_runtime.py",
    "phychem_mfm/phase1/decontamination_v2.py",
    "phychem_mfm/phase1/trial_source_bridge.py",
    "tests/test_phase1_runtime_compatibility.py",
    "tests/test_phase1_trial_source_bridge.py",
    "phychem_mfm/phase1/pretraining_scientific_authority.py",
    "tests/test_phase1_pretraining_scope.py",
    "tests/test_phase1_shared_gpu_policy.py",
    "tests/test_phase1_host_resource_policy.py",
})
TRIAL_FIELDS = {name: f"trial_evidence.{name}_sha256" for name in
                ("summary", "training_log", "gradient_checks", "tracking")}
DATA_FIELDS = {
    "source_manifest": "data.source_manifest_sha256",
    "normalization": "data.normalization_sha256",
    "normalization_train_ids": "data.normalization_train_ids_sha256",
}


class TrialSourceBridgeError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise TrialSourceBridgeError(message)


def _exact(value, keys, name):
    _require(type(value) is dict and set(value) == set(keys), f"Invalid {name} fields")


def _get(value, dotted):
    for part in dotted.split("."):
        _require(type(value) is dict and part in value, f"Missing protocol field: {dotted}")
        value = value[part]
    return value


def _sha(value):
    _require(type(value) is str and _SHA.fullmatch(value), "Invalid SHA256")
    return value


def _canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def constant(_):
        raise TrialSourceBridgeError("Nonfinite JSON constant")

    def floating(text):
        value = float(text)
        _require(math.isfinite(value), "Nonfinite JSON numeric overflow")
        return value

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=constant, parse_float=floating)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise TrialSourceBridgeError("Invalid bounded JSON metadata") from error


class _Files:
    def __init__(self, root):
        self.root = root
        self.cache = {}

    def read(self, ref, *, cap=MAX_METADATA_BYTES):
        _exact(ref, ("path", "bytes", "sha256"), "artifact reference")
        _require(type(ref["path"]) is str and ref["path"].strip(), "Missing artifact path")
        _require(type(ref["bytes"]) is int and 0 < ref["bytes"] <= cap,
                 "Invalid or oversized artifact length")
        _sha(ref["sha256"])
        path = Path(ref["path"])
        path = (path if path.is_absolute() else self.root / path).resolve(strict=True)
        key = (path, ref["bytes"], ref["sha256"])
        if key not in self.cache:
            _require(path.is_file() and path.stat().st_size == ref["bytes"],
                     "Actual artifact size differs")
            with path.open("rb") as stream:
                raw = stream.read(cap + 1)
            _require(len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"],
                     "Actual artifact bytes/hash differ")
            self.cache[key] = raw
        return self.cache[key]

    def document(self, ref):
        return _json(self.read(ref))


def _snapshot(raw):
    # Same byte framing as actual source_provenance: sorted relative POSIX path,
    # NUL, unmodified text-file bytes, NUL. Unknown framing fails closed.
    parts = raw.split(b"\0")
    _require(parts[-1] == b"" and len(parts) % 2 == 1 and len(parts) <= 8193,
             "Unrecognized source snapshot framing")
    result = {}
    previous = ""
    for i in range(0, len(parts) - 1, 2):
        path = parts[i].decode("utf-8")
        p = PurePosixPath(path)
        _require(path and not p.is_absolute() and str(p) == path and ".." not in p.parts
                 and "\\" not in path and path > previous and path not in result,
                 "Source paths are unsafe, duplicated or not sorted")
        result[path] = parts[i + 1]
        previous = path
    _require(result, "Empty source snapshot")
    return result


def _core_table(entries):
    _require(type(entries) is list and len(entries) == CORE_COUNT, "Exactly120 scientific core files required")
    result = {}
    for entry in entries:
        _exact(entry, ("path", "bytes", "sha256"), "scientific core file")
        path = entry["path"]
        _require(type(path) is str and path not in result and path not in INTERFACE_PATHS,
                 "Duplicated or interface-only path in scientific core")
        _require(type(entry["bytes"]) is int and entry["bytes"] >= 0, "Invalid core byte count")
        result[path] = (entry["bytes"], _sha(entry["sha256"]))
    return result


def _difference(before, after):
    return [{"path": path,
             "producer_sha256": hashlib.sha256(before[path]).hexdigest() if path in before else None,
             "consumer_sha256": hashlib.sha256(after[path]).hexdigest() if path in after else None}
            for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)]


def _closed_interface(files, declaration, source_sha):
    _exact(declaration, ("summary", "child_exitcode", "console_exitcode", "accounting", "accounting_exitcode"),
           "prior interface execution")
    summary = files.document(declaration["summary"])
    _require(summary.get("schema_version") == "phase1_actual_v2_metadata_consumer_verification_v1"
             and summary.get("status") == "COMPLETE_ACTUAL_KNOWN_AND_UNRESOLVED_NON_H_METADATA_PROOF"
             and summary.get("complete") is True and type(summary.get("process_exitcode")) is int
             and summary["process_exitcode"] == 0, "Prior interface execution is incomplete")
    _require(summary.get("job_id") == "4511947" and summary.get("source_before") == summary.get("source_after")
             and summary["source_before"].get("source_sha256") == source_sha,
             "Prior interface source/job differs")
    _require(type(summary.get("unchanged_core_files_verified")) is int
             and summary["unchanged_core_files_verified"] == CORE_COUNT
             and summary.get("actual_train_records") == 49993 and summary.get("actual_validation_records") == 7996
             and summary.get("molecular_perception_or_fit_or_model_or_target_values_run") is False,
             "Prior interface proof scope differs")
    for name in ("child_exitcode", "console_exitcode", "accounting_exitcode"):
        _require(files.read(declaration[name], cap=4096).strip() == b"0", "Prior closed process/accounting failed")
    rows = [row.split("|") for row in files.read(declaration["accounting"], cap=65536).decode("utf-8").splitlines()]
    matches = [row for row in rows if row and row[0] == "4511947"]
    _require(len(matches) == 1 and len(matches[0]) == 6
             and matches[0][1] == "zixiao" and matches[0][2] == "compute-0-20"
             and matches[0][3:] == ["2", "COMPLETED", "0:0"], "Prior closed Slurm accounting differs")
    return summary


def verify_trial_producer_consumer_bridge(protocol, artifacts):
    """Verify actual local byte bindings; no scheduler/network/model calls.

    The bridge deliberately preserves trial_evidence.source_sha256 as the old
    producer. A separately bound *new* consumer/core proof must be created after
    any validator patch; an old candidate hash cannot stand in for live source.
    """
    try:
        expected = _sha(_get(protocol, BRIDGE_FIELD))
        path = Path(artifacts[BRIDGE_FIELD]).resolve(strict=True)
        files = _Files(path.parent)
        bridge = files.document({"path": str(path), "bytes": path.stat().st_size, "sha256": expected})
        _exact(bridge, ("schema_version", "scientific_authority", "producer", "consumer", "prior_interface_source",
                       "data_bindings", "trial_raw_artifacts", "prior_core_compatibility", "core_compatibility",
                       "interface_consumer_execution", "old_optimizer_executed_on_consumer_source"), "bridge")
        _require(bridge["schema_version"] == BRIDGE_SCHEMA
                 and bridge["old_optimizer_executed_on_consumer_source"] is False,
                 "Bridge cannot relabel old optimization as execution on new source")
        source_versions, snapshots = {}, {}
        for name in ("producer", "consumer", "prior_interface_source"):
            version = bridge[name]
            _exact(version, ("commit", "source_sha256", "snapshot"), name)
            _require(type(version["commit"]) is str and _COMMIT.fullmatch(version["commit"]), "Invalid source commit")
            _require(_sha(version["source_sha256"]) == version["snapshot"]["sha256"], "Snapshot and source hash differ")
            source_versions[name] = version
            snapshots[name] = _snapshot(files.read(version["snapshot"], cap=MAX_SNAPSHOT_BYTES))
        producer, consumer, prior = (source_versions[name] for name in ("producer", "consumer", "prior_interface_source"))
        _require(_get(protocol, "trial_evidence.source_sha256") == producer["source_sha256"]
                 and _get(protocol, "source.source_sha256") == consumer["source_sha256"]
                 and _get(protocol, "source.commit") == consumer["commit"], "Protocol source domains differ from bridge")
        _require(_get(protocol, "trial_evidence.data_sha256") == _get(protocol, "data.source_manifest_sha256"),
                 "Trial training data differs from frozen source manifest")
        science = files.document(bridge["scientific_authority"])
        _require(science.get("schema_version") == "phase1_scientific_protocol_v1" and science.get("state") == "frozen"
                 and science.get("scientific_choices_complete") is True
                 and science.get("content_sha256") == _canonical({k: v for k, v in science.items() if k != "content_sha256"}),
                 "Scientific choice authority is not an intact frozen document")
        _require(science["source"]["producer_commit"] == producer["commit"]
                 and science["source"]["producer_source_sha256"] == producer["source_sha256"]
                 and science["source"]["core_byte_compatibility"]["sha256"] == bridge["prior_core_compatibility"]["sha256"],
                 "Scientific authority references another producer/prior core proof")
        data = bridge["data_bindings"]
        _exact(data, (*DATA_FIELDS, "validation_manifest"), "data bindings")
        for name, field in DATA_FIELDS.items():
            files.read(data[name], cap=MAX_TRIAL_BYTES)
            _require(data[name]["sha256"] == _get(protocol, field), "Protocol data/fit bytes differ")
        files.read(data["validation_manifest"])
        for name, science_key in (("source_manifest", "train_manifest"), ("validation_manifest", "validation_manifest"),
                                  ("normalization", "fitted_controls"), ("normalization_train_ids", "normalization_fit_ids")):
            _require(data[name]["sha256"] == science["data"][science_key]["sha256"], "Scientific data/fit binding changed")
        split_ref = {"path": str(artifacts["data.split_manifest_sha256"]),
                     "bytes": Path(artifacts["data.split_manifest_sha256"]).stat().st_size,
                     "sha256": _get(protocol, "data.split_manifest_sha256")}
        split = files.document(split_ref)
        _exact(split, ("schema_version", "train", "validation"), "pretraining split")
        _require(split["schema_version"] == "phase1_split_v1"
                 and split["train"] == files.document(data["source_manifest"])
                 and split["validation"] == files.document(data["validation_manifest"]), "Split wrapper changes actual manifests")
        original = files.document(bridge["prior_core_compatibility"])
        _require(original.get("schema_version") == "phase1_lf_archive_core_byte_compatibility_v1"
                 and original["baseline_archive_source_digest"]["sha256"] == producer["source_sha256"]
                 and original["candidate_archive_source_digest"]["sha256"] == prior["source_sha256"]
                 and type(original.get("scientific_files_checked")) is int
                 and original["scientific_files_checked"] == CORE_COUNT, "Prior core proof source domains differ")
        table = _core_table(original["unchanged_scientific_files"])
        core = files.document(bridge["core_compatibility"])
        _exact(core, ("schema_version", "producer_source_sha256", "prior_interface_source_sha256",
                      "consumer_source_sha256", "scientific_files", "interface_differences"), "new core proof")
        _require(core["schema_version"] == CORE_SCHEMA and core["producer_source_sha256"] == producer["source_sha256"]
                 and core["prior_interface_source_sha256"] == prior["source_sha256"]
                 and core["consumer_source_sha256"] == consumer["source_sha256"]
                 and _core_table(core["scientific_files"]) == table, "New core proof uses an old candidate or altered120-file scope")
        for snapshot in snapshots.values():
            for name, (size, digest) in table.items():
                _require(name in snapshot and len(snapshot[name]) == size
                         and hashlib.sha256(snapshot[name]).hexdigest() == digest, "Actual scientific core byte drift")
        differences = _difference(snapshots["producer"], snapshots["consumer"])
        _require(core["interface_differences"] == differences
                 and all(entry["path"] in INTERFACE_PATHS for entry in differences),
                 "Changed/added source is not an exact allowed interface-only change")
        _require(all(entry["path"] in INTERFACE_PATHS for entry in
                     _difference(snapshots["prior_interface_source"], snapshots["consumer"])),
                 "Consumer drifts outside prior interface/core scope")
        interface = _closed_interface(files, bridge["interface_consumer_execution"], prior["source_sha256"])
        _require(interface["producer_source"]["actual_source_sha256"] == producer["source_sha256"], "Prior execution used another producer")
        _exact(bridge["trial_raw_artifacts"], TRIAL_FIELDS, "original trial slots")
        for name, field in TRIAL_FIELDS.items():
            ref = bridge["trial_raw_artifacts"][name]
            files.read(ref, cap=MAX_TRIAL_BYTES)
            _require(ref["sha256"] == _get(protocol, field), "Original trial slot hash changed")
        trial = files.document(bridge["trial_raw_artifacts"]["summary"])
        _require(trial.get("status") == "CLOSED_BOUNDED_FULL_FIT_COST_VERIFIED"
                 and type(trial.get("last_child_exitcode")) is int and trial["last_child_exitcode"] == 0
                 and trial["source"].get("source_sha256") == producer["source_sha256"]
                 and trial["source"].get("git_commit") == producer["commit"], "Original full-fit trial closure/source differs")
        declared_inputs = trial.get("input_sha256")
        _require(type(declared_inputs) is dict and all(data[name]["sha256"] in declared_inputs.values()
                 for name in DATA_FIELDS), "Original trial did not bind the same source manifest/controls/fit IDs")
        return {"status": "VERIFIED_TRIAL_PRODUCER_CONSUMER_BYTE_BRIDGE", "bridge_sha256": expected,
                "producer_source_sha256": producer["source_sha256"], "consumer_source_sha256": consumer["source_sha256"],
                "prior_interface_source_sha256": prior["source_sha256"], "actual_scientific_core_files_checked": CORE_COUNT,
                "interface_consumer_job_id": interface["job_id"], "old_optimizer_executed_on_consumer_source": False,
                "scope": "metadata/source compatibility only; no GPU protection, new optimization or chemical truth"}
    except TrialSourceBridgeError:
        raise
    except (OSError, KeyError, TypeError, ValueError, AttributeError, UnicodeError, RecursionError) as error:
        raise TrialSourceBridgeError("Incomplete, unreadable or malformed trial/source bridge") from error
