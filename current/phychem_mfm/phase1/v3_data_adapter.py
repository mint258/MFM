"""Model-side real-Data admission/reader seam, not a Data delivery schema.

A separately reviewed, source-bound Data authority verifier translates the
ACTUAL release to this consumption protocol.  This module cannot mint joint
ACKs, D4 values, Common memberships, or final TRAIN authority.  The existing
proxy/full/grid request and Root admission remain necessary in addition.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import stat
import sys

import torch

from .v3_contract import LabelRegistry, TrainNormalization, DisabledNormalization, canonical_hash, require
from .v3_data import DecodedSample, ManifestSampleDataset, collate_v3_samples
from .v3_label_domains import (OrderedEntryInputs, OrderedEntryTarget, Tensor6Inputs, Tensor6Target,
                               validate_source_reference)
from .v3_structural import build_structural_views, eligibility_from_choices

ALL_A_POLICY = {
    "r73": "ordered_entries_authoritative_F64_once_F32",
    "tensor6_eligibility": "all_valid6_same_actual_geometry",
    "tensor6_scale": "TRAIN_frobenius_winsor_0.001_0.999_std_ddof0",
    "tensor6_center": 0,
    "tensor6_radial_dimension": 9,
    "tensor6_huber_delta": 1,
    "tensor6_target_weight": 1,
    "frame_provenance": "source_inference_with_explicit_assumptions_independent192_UNKNOWN",
}
REQUIRED_EVIDENCE = ("joint_contract", "release", "registry", "physical_mapping", "common_population",
                     "effective_train", "heldout_exclusion", "d4_statistics", "geometry", "codebook")
ROLES = ("TRAIN", "VAL", "TRAIN_UNSEEN_CONFORMATION")
DATA_RELEASE_ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/releases")


def rawref(value):
    require(type(value) is dict and set(value) == {"path", "bytes", "sha256"}, "Exact real metadata/source rawref required")
    require(type(value["path"]) is str and Path(value["path"]).is_absolute()
            and type(value["bytes"]) is int and 0 < value["bytes"] <= 2 << 20
            and type(value["sha256"]) is str and len(value["sha256"]) == 64
            and all(c in "0123456789abcdef" for c in value["sha256"]), "Invalid bounded metadata/source reference")
    return deepcopy(value)


def bound_bytes(value):
    ref = rawref(value); path = Path(ref["path"])
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and not path.is_symlink() and before.st_size == ref["bytes"], "Metadata/source file identity or bytes differs")
    data = path.read_bytes(); after = path.lstat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            and hashlib.sha256(data).hexdigest() == ref["sha256"], "Metadata/source changed or SHA differs")
    return data


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate metadata key")
        result[key] = value
    return result


def bound_json(ref):
    def bad_constant(value):
        raise ValueError("Nonfinite metadata constant: " + value)
    return json.loads(bound_bytes(ref).decode("utf-8"), object_pairs_hook=_object, parse_constant=bad_constant)


@dataclass(frozen=True)
class VerifiedDataRelease:
    """Model consumption projection, never a replacement Data authority format."""
    request_sha256: str
    evidence: dict
    verifier: dict
    projection: dict
    authority_family: str = "model_protocol_fixture_only"
    request: dict | None = field(default=None, repr=False)
    _seal: str = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "evidence", deepcopy(self.evidence))
        object.__setattr__(self, "verifier", deepcopy(self.verifier))
        object.__setattr__(self, "projection", deepcopy(self.projection))
        object.__setattr__(self, "request", deepcopy(self.request))
        object.__setattr__(self, "_seal", self.sha256)

    @property
    def data_version(self): return self.projection["data_version"]
    @property
    def is_final(self): return self.projection["scope"] != "authoritative_pilot"
    @property
    def is_actual_data_release(self): return self.authority_family == "actual_final_release_v1"
    @property
    def sha256(self):
        return canonical_hash({"request": self.request_sha256, "evidence": self.evidence,
                               "verifier": self.verifier, "projection": self.projection, "authority_family": self.authority_family})

    @property
    def data_sha256(self):
        # A provider identity must be computable BEFORE the final request is
        # sealed. Including request_sha256 here creates an impossible hash loop.
        projection = {k: v for k, v in self.projection.items() if k != "request_sha256"}
        return canonical_hash({"evidence": self.evidence, "verifier": self.verifier, "projection": projection, "authority_family": self.authority_family})

    def reverify(self):
        require(self.sha256 == self._seal, "Verified consumption projection mutated after authority verification")
        # A public constructor/dataclasses.replace can recompute a local seal;
        # it cannot grant authority. Re-run the SAME bound family/interpreter
        # gate against the saved request and original evidence every time.
        require(type(self.request) is dict and canonical_hash(self.request) == self.request_sha256,
                "Bound request required to reverify release authority")
        verified = verify_release_binding(self.request, evidence=self.evidence, verifier=self.verifier)
        require(verified.authority_family == self.authority_family
                and canonical_hash(verified.projection) == canonical_hash(self.projection),
                "Bound release family/projection authority differs; self-seal is not admission")
        # Metadata only. Never open referenced science sidecars/shards here.
        for binding in self.projection["targets"].values():
            if "source_frame_metadata" in binding: bound_bytes(binding["source_frame_metadata"])
        require(canonical_hash(self.projection["policy"]) == canonical_hash(ALL_A_POLICY), "User-selected ALL-A policy changed")


def _actual_final_release(documents, references, request):
    """Exact metadata joins from Data final_release_v1 Source, no DATA reads.

    The bound interpreter still verifies semantic mappings/Common/D4. This
    mechanical layer cannot turn a USER_FROZEN_DESIGN into a joint release.
    """
    release, joint = documents["release"], documents["joint_contract"]
    require(joint.get("schema") == "ROOT_MODEL_JOINT_FINAL_LABEL_POLICY_V1"
            and joint.get("status") == "JOINTLY_FROZEN", "Actual final Data joint-policy family required")
    for key in ("actual_final_Model_ack_not_conditional", "root_signoff", "model_signoff",
                "partial_mask_policy_explicit", "r73_pair_dependent_double_basis_onsite_ordinal_explicit",
                "r674_native_symmetric6_no_trace_projection", "actual_child_coordinate_frames_explicit"):
        require(joint.get(key) is True, "Missing actual joint signoff/domain policy: " + key)
    for key in ("root_review_reference", "model_ack_reference", "contract_reference"):
        bound_bytes(joint[key])  # ACK/contract may be Markdown; never pretend it is JSON.
    require(release.get("schema") == "ROOT_FINAL_LABEL_RELEASE_V1"
            and release.get("final_consumer_release") is True and release.get("D2_published") is True
            and release.get("D4_P_D_published") is True, "Final Data release, not a candidate/design, required")
    full = release.get("status") == "FULL_V1_FROZEN"
    require((full and release.get("release_scope") == "FULL_V1" and request["mode"] != "authoritative_pilot"
             and all(release.get(k) is True for k in ("training_ready", "D4_published", "independent_Pprime_published")))
            or (release.get("status") == "BOUNDED_DIAGNOSTIC_P_D_RELEASE_NOT_FULL_V1"
                and release.get("release_scope") == "BOUNDED_D3_50K_TRAIN_5K_ROUTINE_VAL"
                and request["mode"] == "authoritative_pilot"
                and all(release.get(k) is False for k in ("training_ready", "D4_published", "independent_Pprime_published"))),
            "Bounded P/D release cannot grant full TRAIN/proxy authority")
    outputs = {key: release[key] for key in ("registry_reference", "mapping_reference", "normalization_reference",
                                           "mask_release_reference", "size_rho_reference")}
    require(release["joint_policy_reference"] == references["joint_contract"]
            and outputs["registry_reference"] == references["registry"]
            and outputs["mapping_reference"] == references["physical_mapping"]
            and outputs["normalization_reference"] == references["d4_statistics"], "Actual release output/joint refs differ")
    for value in outputs.values(): bound_bytes(value)
    release_id = release.get("release_id")
    require(type(release_id) is str and 1 <= len(release_id) <= 80 and all(x.isascii() and (x.isalnum() or x == "_") for x in release_id),
            "Exact finite release identifier required")
    expected_root = DATA_RELEASE_ROOT / release_id
    require(Path(references["release"]["path"]) == expected_root / "release.json", "Actual Data publication path required, not a copied report/header")
    review = bound_json(release["root_publication_review_reference"])
    require(review.get("schema") == "ROOT_FINAL_LABEL_PUBLICATION_REVIEW_V1"
            and review.get("status") == "APPROVED_EXACT_ACTUAL_C0_RELEASE" and review.get("reviewer") == "root"
            and review.get("joint_policy_reference") == references["joint_contract"]
            and review.get("exact_outputs") == outputs, "Independent exact Root publication review required")
    configurations = release.get("configurations")
    require(type(configurations) is dict and set(configurations) == set(outputs), "All five published configuration wrappers required")
    filenames = {"registry_reference": "label_registry_v3.json", "mapping_reference": "physical_target_mapping_v3.json",
                 "normalization_reference": "normalization_v1.json", "mask_release_reference": "validity_masks_v1.json",
                 "size_rho_reference": "size_families_v1.json"}
    for key, wrapper_ref in configurations.items():
        wrapper = bound_json(wrapper_ref)
        require(wrapper.get("schema") == "FINAL_LABEL_CONFIGURATION_REFERENCE_V1"
                and wrapper.get("status") == ("FROZEN_FULL_V1" if full else "FROZEN_BOUNDED_DIAGNOSTIC_P_D_SCOPE")
                and wrapper.get("configuration_kind") == key and wrapper.get("configuration_reference") == outputs[key]
                and wrapper.get("release_scope") == release["release_scope"]
                and wrapper.get("actual_parent_references") == release["actual_parent_references"]
                and wrapper.get("joint_policy_reference") == references["joint_contract"]
                and wrapper.get("root_publication_review_reference") == release["root_publication_review_reference"]
                and Path(wrapper_ref["path"]) == expected_root / filenames[key], "Published configuration wrapper binding differs")
    before = bound_json(review["candidate_reference"])
    refs = release["actual_parent_references"]
    require(before.get("schema") == "FINAL_LABEL_POST_C0_ROOT_REVIEW_CANDIDATE_V1"
            and before.get("status") == "PENDING_INDEPENDENT_ROOT_FINAL_REVIEW"
            and before.get("release_id") == release["release_id"] and before.get("release_scope") == release["release_scope"]
            and before.get("actual_parent_references") == refs and before.get("exact_outputs") == outputs
            and before.get("joint_policy_reference") == references["joint_contract"]
            and refs["candidate"] == release["candidate_reference"], "Post-C0 Root review/candidate lineage differs")
    candidate, startup, accounting = (bound_json(refs[k]) for k in ("candidate", "startup_proof", "accounting"))
    request_body = startup["request"]; jid = str(startup["job_id"])
    require(candidate.get("schema") == "FINAL_LABEL_RELEASE_CANDIDATE_V1"
            and candidate.get("status") == "COMPLETE_EXACT_FINAL_CANDIDATE_REQUIRES_ACTUAL_PARENT_C0_AND_ROOT_SEAL"
            and candidate.get("release_id") == release["release_id"] and candidate.get("release_scope") == release["release_scope"]
            and candidate.get("current_actual_parent_job_id") == jid
            and candidate.get("current_startup_proof_reference") == refs["startup_proof"]
            and candidate.get("current_parent_C0_claimed") is False
            and all(candidate.get(k) == value for k, value in outputs.items())
            and candidate.get("joint_policy_reference") == references["joint_contract"], "Actual family candidate source/output identity differs")
    require(request_body.get("scope_key") == "family_export_day_v1" and request_body.get("cpus") == 16
            and request_body.get("wall_seconds") == 86400 and bound_json(startup["request_reference"]) == request_body
            and Path(request_body["scope_parameters"]["output_directory"]) in Path(refs["candidate"]["path"]).parents,
            "Actual original family producer/request/output binding differs")
    require(accounting.get("schema") == "DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1"
            and accounting.get("status") == "ACTUAL_PARENT_ACCOUNTING_CLOSED"
            and accounting.get("endpoint") == "202.38.247.57:22" and accounting.get("uid") == 1278
            and type(accounting.get("query_returncode")) is int and accounting["query_returncode"] == 0
            and accounting.get("raw_sacct_reference") == refs["raw"],
            "Actual Data parent accounting/raw binding required")
    rows = [row for row in accounting["parents"] if str(row["job_id"]) == jid]
    require(len(rows) == 1 and rows[0].get("state") == "COMPLETED" and rows[0].get("exit_code") == "0:0"
            and type(rows[0].get("alloc_cpus")) is int and rows[0]["alloc_cpus"] == 16, "Actual family parent C0 required")
    lines = bound_bytes(refs["raw"]).decode("utf-8-sig").splitlines()
    require(bool(lines) and len(set(lines[0].split("|"))) == len(lines[0].split("|")), "Exact raw accounting header required")
    raw_rows = [dict(zip(lines[0].split("|"), line.split("|"))) for line in lines[1:] if line.split("|")[0] == jid]
    require(len(raw_rows) == 1 and all(raw_rows[0].get(k) == value for k, value in
            {"UID": "1278", "State": "COMPLETED", "ExitCode": "0:0", "AllocCPUS": "16"}.items()), "Raw Data parent C0 identity differs")
    directive = bound_json(candidate["root_reviewed_directive_reference"])
    require(directive.get("schema") == "ROOT_FINAL_LABEL_RELEASE_DIRECTIVE_V1"
            and directive.get("status") == "ROOT_REVIEWED_ACTUAL_D4_AND_JOINT_POLICY_INPUTS"
            and directive.get("reviewer") == "root" and directive.get("joint_policy_reference") == references["joint_contract"]
            and directive.get("release_id") == release["release_id"] and directive.get("release_scope") == release["release_scope"]
            and before.get("root_reviewed_directive_reference") == candidate["root_reviewed_directive_reference"]
            and joint["registry_source_reference"] == directive.get("base_registry_reference")
            and joint["mapping_source_reference"] == directive.get("mapping_reference"), "Exact Root directive/Model joint contract and source mapping required")
    for key in ("base_registry_reference", "mapping_reference", "root_actual_d4_acceptance_reference", "d4_closure_reference"):
        bound_bytes(directive[key])
    registry, mapping, normalizations = documents["registry"], documents["physical_mapping"], documents["d4_statistics"]
    require(registry.get("status") == "FROZEN_ACTUAL_DEFINITIONS_FAMILIES_AND_SCOPED_STATISTICS"
            and registry.get("physical_joint_policy_reference") == references["joint_contract"]
            and mapping.get("status") == "FROZEN" and mapping.get("joint_policy_reference") == references["joint_contract"]
            and mapping.get("registry_sha256") == references["registry"]["sha256"]
            and normalizations.get("schema") == "FINAL_TRAIN_TARGET_NORMALIZATION_CANDIDATE_V1"
            and normalizations.get("status") == "ACTUAL_SERIES_EXACT_JOINT_RECIPE_BOUND"
            and normalizations.get("policy_reference") == references["joint_contract"], "Final registry/mapping/normalization source family differs")
    if full:
        require(candidate.get("Pprime_complete") is True
                and release.get("model_actual_acceptance_reference") == review.get("model_actual_acceptance_reference")
                and review.get("model_actual_acceptance_reference") is not None,
                "FULL_V1 requires the candidate's actual Pprime and exact Root-reviewed Model acceptance")
        model = bound_json(release["model_actual_acceptance_reference"])
        require(model.get("schema") == "ROOT_MODEL_ACTUAL_NATIVE_CONSUMER_ACCEPTANCE_V1"
                and model.get("status") == "ACTUAL_REQUIRED_NATIVE_MODEL_CHECKS_ACCEPTED"
                and model.get("release_candidate_reference") == refs["candidate"]
                and model.get("all_required_model_checks_passed") is True and model.get("actual_runtime_evidence_references"),
                "FULL_V1 needs actual Model runtime acceptance, not synthetic source QA")
        for reference in model["actual_runtime_evidence_references"]: bound_bytes(reference)


def verify_release_binding(request, *, evidence, verifier):
    """Invoke the pinned ACTUAL-release interpreter, not a caller PASS boolean.

    The interpreter must export verify_model_v3_release_authority(request,
    documents).  Its return is the versioned MODEL consumption projection below.
    It must cross-check real published statuses/populations/refs in documents;
    no final Data schema is invented or inferred from a fixture/source role.
    """
    require(type(evidence) is dict and set(evidence) == set(REQUIRED_EVIDENCE), "Complete real release/D4/Common/heldout evidence required")
    refs = {key: rawref(value) for key, value in evidence.items()}
    docs = {key: bound_json(value) for key, value in refs.items()}
    joint = docs["joint_contract"]
    require(type(joint) is dict, "Actual same-version Model/Data joint ACK required")
    if joint.get("schema") == "ROOT_MODEL_JOINT_FINAL_LABEL_POLICY_V1":
        require(request.get("UNIT_FIXTURE_ONLY_NOT_A_REAL_REQUEST") is not True
                and docs["release"].get("UNIT_FIXTURE_ONLY_NOT_A_REAL_RELEASE") is not True,
                "Synthetic fixtures cannot acquire actual Data release authority")
        try:
            _actual_final_release(docs, refs, request)
        except (KeyError, TypeError, IndexError, AttributeError) as error:
            raise ValueError("Unknown/incomplete actual Data release metadata; HOLD, no inferred authority") from error
        authority_family = "actual_final_release_v1"
    else:
        require(request.get("UNIT_FIXTURE_ONLY_NOT_A_REAL_REQUEST") is True
                and docs["release"].get("UNIT_FIXTURE_ONLY_NOT_A_REAL_RELEASE") is True
                and joint.get("status") == "MODEL_DATA_JOINT_CONTRACT_FROZEN"
                and joint.get("version") == "3.0" and joint.get("model_confirmation") is True
                and joint.get("data_confirmation") is True,
                "Actual same-version joint ACK required; old MODEL_DATA header is engineering-only")
        authority_family = "model_protocol_fixture_only"
    source = rawref(verifier); bound_bytes(source)
    name = "model_v3_actual_Data_verifier_" + source["sha256"]
    spec = importlib.util.spec_from_file_location(name, source["path"])
    require(spec is not None and spec.loader is not None, "Explicit reviewed release interpreter required")
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    function = getattr(module, "verify_model_v3_release_authority", None)
    require(callable(function), "Missing actual Data release verification function")
    projection = function(deepcopy(request), deepcopy(docs))
    require(type(projection) is dict and set(projection) == {
        "schema", "request_sha256", "evidence_sha256", "data_version", "scope", "policy",
        "TRAIN_population", "heldout_base_and_all_direct_children_excluded", "validation_population_bindings",
        "role_index_sha256", "targets", "reader_source", "D4_bindings", "normalization_sha256"}, "Unknown or incomplete model consumption projection")
    require(projection["schema"] == "model_v3_verified_Data_consumption_projection_v1"
            and projection["request_sha256"] == canonical_hash(request)
            and projection["evidence_sha256"] == canonical_hash(refs), "Release interpreter did not bind this exact request and evidence")
    require(type(projection["data_version"]) is str and bool(projection["data_version"])
            and projection["scope"] in ("authoritative_proxy", "authoritative_full_train", "authoritative_grid_train", "authoritative_pilot")
            and projection["scope"] == request.get("mode"), "Final Data scope/version differs; pilot/source FULL is not final TRAIN")
    expected_population = ("versioned_provisional_pilot_TRAIN" if projection["scope"] == "authoritative_pilot"
                           else "Common_intersection_effective_TRAIN")
    require(canonical_hash(projection["policy"]) == canonical_hash(ALL_A_POLICY)
            and projection["TRAIN_population"] == expected_population
            and projection["heldout_base_and_all_direct_children_excluded"] is True, "Actual scoped TRAIN/heldout and ALL-A policy not verified")
    require(type(projection["role_index_sha256"]) is dict and set(projection["role_index_sha256"]) == set(ROLES)
            and type(projection["validation_population_bindings"]) is dict
            and set(projection["validation_population_bindings"]) == set(ROLES[1:]), "Actual full validation/role bindings required")
    for digest in projection["role_index_sha256"].values():
        require(type(digest) is str and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "Actual role index SHA required")
    require(type(projection["targets"]) is dict and bool(projection["targets"])
            and type(projection["D4_bindings"]) is dict, "Actual physical target and D4 bindings required")
    digest = projection["normalization_sha256"]
    require(type(digest) is str and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest),
            "Interpreter must bind actual D4 normalization projection for ALL model fields")
    rawref(projection["reader_source"]); bound_bytes(projection["reader_source"])
    # The interpreter may import only its reviewed dependencies; its own bytes
    # and every original metadata reference are rebound after it returns.
    for reference in refs.values(): bound_bytes(reference)
    bound_bytes(source)
    return VerifiedDataRelease(canonical_hash(request), refs, source, deepcopy(projection),
                               authority_family, request=deepcopy(request))


def _pointer(value, keys):
    require(type(keys) in (tuple, list) and all(type(k) in (str, int) for k in keys), "Explicit statistics JSON path required")
    for key in keys:
        require((type(value) is dict and type(key) is str and key in value)
                or (type(value) is list and type(key) is int and 0 <= key < len(value)), "Missing real D4 statistics path")
        value = value[key]
    return value


def _tensor6_record(release, field_name):
    require(isinstance(release, VerifiedDataRelease), "Verified actual release required")
    release.reverify()
    binding = release.projection["D4_bindings"].get(field_name)
    required = {"registry_id", "condition", "task", "series_key", "statistics_pointer",
        "population_sha256", "heldout_exclusion_sha256", "series_source", "statistics_source",
        "quantile_probabilities", "statistic"}
    require(type(binding) is dict and required <= set(binding)
            and set(binding) <= required | {"raw_mean_F_binding"}, "Actual tensor D4 binding required")
    require(type(binding["registry_id"]) is int and binding["registry_id"] == 674
            and type(binding["condition"]) is str and bool(binding["condition"])
            and type(binding["task"]) is str and bool(binding["task"])
            and binding["series_key"] == "physical/674/" + binding["task"] + "/frobenius_norm",
            "Exact registry674/task Frobenius series required")
    require(type(binding["quantile_probabilities"]) is list
            and canonical_hash(binding["quantile_probabilities"]) == canonical_hash([0.001, 0.999])
            and binding["statistic"] == "std_ddof0", "Actual TRAIN 0.1/99.9 percent winsorized std policy required")
    target = release.projection["targets"].get(field_name)
    require(type(target) is dict and binding["condition"] == target.get("condition"), "Tensor D4 target condition differs")
    require(binding["population_sha256"] == release.evidence["effective_train"]["sha256"]
            and binding["heldout_exclusion_sha256"] == release.evidence["heldout_exclusion"]["sha256"], "D4 effective TRAIN/heldout population binding differs")
    for key in ("series_source", "statistics_source"): bound_bytes(binding[key])
    document = bound_json(release.evidence["d4_statistics"])
    record = _pointer(document, binding["statistics_pointer"])
    require(type(record) is dict and "n" in record and "std_ddof0" in record
            and type(record["n"]) is int and record["n"] >= 0, "Unknown/malformed D4 statistics schema; not a missing-scale disposition")
    if document.get("schema") == "FINAL_TRAIN_TARGET_NORMALIZATION_CANDIDATE_V1":
        # Actual final_release_v1 output, not an invented WinsorMoments header.
        require(document.get("status") == "ACTUAL_SERIES_EXACT_JOINT_RECIPE_BOUND"
                and document.get("policy_reference") == release.evidence["joint_contract"]
                and record.get("target_id") == target["target_id"]
                and record.get("source_series_key") == binding["series_key"]
                and record.get("centering") == "FIXED_ZERO"
                and type(record.get("center_value")) in (int, float) and record["center_value"] == 0.
                and record.get("per_head_single_scale") is True and record.get("scale_rule") == "SERIES_STD_DDOF0"
                and record.get("winsorization_only_statistical_copies") is True
                and record.get("original_training_labels_modified") is False,
                "Actual published tensor normalization recipe differs")
        require("scale" in record and (record["scale"] is None if record["std_ddof0"] is None else
                type(record["scale"]) in (int, float) and record["scale"] == record["std_ddof0"]),
                "Published scale and actual series std differ")
        lower, upper = record.get("lower"), record.get("upper")
    else:
        require(not release.is_actual_data_release, "Unknown actual published D4 schema; HOLD")
        # Explicit existing raw WinsorMoments record. Typos/missing pointers,
        # source/hash/policy errors remain global failures, never disabled.
        require("winsor_lower" in record and "winsor_upper" in record
                and record.get("labels_modified") is False, "Unknown D4 statistic or label clipping is not accepted")
        lower, upper = record["winsor_lower"], record["winsor_upper"]
    evidence = {"statistics_reference": deepcopy(release.evidence["d4_statistics"]),
        "statistics_pointer": list(binding["statistics_pointer"]), "series_key": binding["series_key"],
        "condition": binding["condition"], "effective_train_reference": deepcopy(release.evidence["effective_train"]),
        "heldout_exclusion_reference": deepcopy(release.evidence["heldout_exclusion"]),
        "joint_policy_reference": deepcopy(release.evidence["joint_contract"])}
    return binding, target, record, lower, upper, evidence


def tensor6_normalization(release, field_name, *, target_local=False):
    """Actual statistics -> ready normalizer OR explicit target-local no-scale.

    Only actual null/empty/zero/nonfinite scale facts are classified. Invalid
    authority, references, unknown schema, negative std or recipe errors raise.
    """
    binding, target, record, lower, upper, evidence = _tensor6_record(release, field_name)
    reason, detail = None, None
    value = record["std_ddof0"]
    require(value is None or type(value) in (int, float), "Malformed actual std; not a readiness state")
    if lower is None or upper is None:
        require(lower is None and upper is None and (record["n"] == 0 or value is None),
                "Malformed/missing winsor bounds, not an explicit empty/unbound scale")
    else:
        require(type(lower) in (int, float) and type(upper) in (int, float)
                and math.isfinite(lower) and math.isfinite(upper) and lower <= upper,
                "Malformed winsorization bounds; not a readiness state")
    if record["n"] == 0:
        require(value is None or value == 0, "Empty statistic with a nonempty std is malformed")
        reason, detail = "EMPTY", "actual_statistic_n_zero"
    elif value is None:
        reason, detail = "MISSING", "actual_statistic_std_unbound"
    else:
        require(type(value) in (int, float), "Malformed actual std; not a readiness state")
        if not math.isfinite(value): reason, detail = "NONFINITE", "actual_statistic_std_nonfinite"
        elif value == 0: reason, detail = "ZERO", "actual_statistic_std_zero"
        else:
            require(value > 0, "Negative actual std is a schema/data error")
    if reason is None:
        require(type(lower) in (int, float) and type(upper) in (int, float)
                and math.isfinite(lower) and math.isfinite(upper) and lower <= upper,
                "Malformed winsorization bounds; not a readiness state")
        f32 = torch.tensor(float(value), dtype=torch.float32)
        if not bool(torch.isfinite(f32)): reason, detail = "NONFINITE", "actual_positive_std_overflows_F32"
        elif float(f32) == 0: reason, detail = "ZERO", "actual_positive_std_underflows_F32"
    if reason is not None:
        require(target_local is True, "Legacy strict normalization rejects unavailable or degenerate scale")
        evidence["classification_detail"] = detail
        return DisabledNormalization(field_name, target["target_id"], reason,
            release.evidence["d4_statistics"]["sha256"], release.data_version, evidence)
    return TrainNormalization((0.,), (float(value),), release.evidence["d4_statistics"]["sha256"], release.data_version)


def tensor6_raw_mean_report(release, field_name):
    """Read a genuinely raw F mean, or accurately report pending; never fit it.

    The optional MODEL binding points to an actual Data metadata record with
    explicit raw_mean_F/n leaves. Generic mean/audit_series_mean cannot qualify.
    """
    binding, _, record, _, _, _ = _tensor6_record(release, field_name)
    normalization = tensor6_normalization(release, field_name, target_local=True)
    report = {"status": "RAW_MEAN_F_REPORT_PENDING", "raw_mean_F": None, "raw_mean_F_over_s": None,
              "source": None, "current_centering_changed": False}
    mean_binding = binding.get("raw_mean_F_binding")
    if mean_binding is None: return report
    require(type(mean_binding) is dict and set(mean_binding) == {"reference", "record_pointer", "series_key",
        "population_sha256", "heldout_exclusion_sha256", "statistic"}, "Unknown raw-F report binding")
    require(mean_binding["statistic"] == "RAW_UNWINSORIZED_FROBENIUS_MEAN"
            and mean_binding["series_key"] == binding["series_key"]
            and mean_binding["population_sha256"] == binding["population_sha256"]
            and mean_binding["heldout_exclusion_sha256"] == binding["heldout_exclusion_sha256"],
            "Raw-F report must use the same actual TRAIN/heldout series")
    raw = _pointer(bound_json(mean_binding["reference"]), mean_binding["record_pointer"])
    require(type(raw) is dict and "raw_mean_F" in raw and "n" in raw,
            "Explicit actual raw_mean_F record required; winsor mean is not a substitute")
    require(type(raw["n"]) is int and raw["n"] == record["n"], "Raw-F report population count differs")
    report["source"] = deepcopy(mean_binding["reference"])
    if raw["n"] == 0 or raw["raw_mean_F"] is None: return report
    mean = raw["raw_mean_F"]
    require(type(mean) in (int, float) and math.isfinite(mean) and mean >= 0, "Invalid actual raw F mean")
    report.update(status="RAW_MEAN_F_AVAILABLE_SCALE_DISABLED" if isinstance(normalization, DisabledNormalization)
                  else "RAW_MEAN_F_AND_RATIO_AVAILABLE", raw_mean_F=float(mean))
    if isinstance(normalization, TrainNormalization):
        report["raw_mean_F_over_s"] = float(mean) / normalization.scale[0]
        report["next_version_centering_review_gt10"] = report["raw_mean_F_over_s"] > 10
    return report

class _CheckedFactory:
    read_only = node_local = True

    def __init__(self, factory, release, role, loss_disabled_fields=()):
        self.factory, self.release, self.role = factory, release, role
        self.loss_disabled_fields = tuple(loss_disabled_fields)
        self.data_version = release.data_version

    def __call__(self):
        return _CheckedReader(self.factory(), self.release, self.loss_disabled_fields)


class _CheckedReader:
    def __init__(self, reader, release, loss_disabled_fields=()):
        require(callable(getattr(reader, "read", None)) and callable(getattr(reader, "close", None)), "Readonly reader must implement read/close")
        self.reader, self.release = reader, release
        self.loss_disabled_fields = tuple(loss_disabled_fields)

    def read(self, choice):
        sample = self.reader.read(choice)
        require(isinstance(sample, DecodedSample), "Real reader must return existing DecodedSample")
        inputs = getattr(sample, "domain_inputs", {})
        geometry_ref = getattr(sample, "geometry_ref", None)
        for name, target in sample.fields.items():
            if not isinstance(target, (OrderedEntryTarget, Tensor6Target)): continue
            validate_source_reference(geometry_ref)
            binding = self.release.projection["targets"].get(name)
            require(type(binding) is dict and all(type(binding.get(k)) is str and binding[k]
                    for k in ("target_id", "condition", "unit", "sign", "frame", "origin_policy")), "Joint target unit/sign/frame/origin/condition declaration required")
            frame = {k: binding[k] for k in ("target_id", "condition", "unit", "sign", "frame", "origin_policy")}
            frame["joint_policy"] = self.release.evidence["joint_contract"]
            context = inputs.get(name)
            if name in self.loss_disabled_fields:
                # Check retained source identity, not nonexistent numeric head inputs.
                target.__post_init__()
                if isinstance(target, OrderedEntryTarget):
                    frame["source_frame_metadata"] = rawref(binding.get("source_frame_metadata"))
                    require(target.inputs.frame_binding == frame
                            and target.inputs.codebook.source == self.release.evidence["codebook"]
                            and target.inputs.geometry_ids == (choice.conformer_id,)
                            and target.inputs.geometry_bindings == (geometry_ref,),
                            "Disabled ordered source/frame/codebook identity differs")
                else:
                    require(target.geometry_ids == (choice.conformer_id,) and target.values.shape == (1, 6)
                            and name in self.release.projection["D4_bindings"],
                            "Disabled tensor source/actual geometry/D4 binding differs")
                continue
            if isinstance(target, OrderedEntryTarget):
                # A numeric frame cannot be inferred from unit/frame labels,
                # the joint ACK, or the source-position reference alone.
                frame["source_frame_metadata"] = rawref(binding.get("source_frame_metadata"))
                require(isinstance(context, OrderedEntryInputs) and context.frame_binding == frame
                        and target.inputs.frame_binding == frame and context.codebook.sha256 == target.inputs.codebook.sha256
                        and context.codebook.source == self.release.evidence["codebook"]
                        and context.geometry_ids == target.inputs.geometry_ids == (choice.conformer_id,)
                        and context.geometry_bindings == target.inputs.geometry_bindings == (geometry_ref,)
                        and torch.equal(context.atom_index, target.atom_index)
                        and torch.equal(context.channel_index, target.channel_index), "Ordered source/codebook/physical head inputs differ")
                require(context.frame_origin is not None and context.frame_basis is not None
                        and target.inputs.frame_origin is not None and target.inputs.frame_basis is not None
                        and torch.equal(context.frame_origin, target.inputs.frame_origin)
                        and torch.equal(context.frame_basis, target.inputs.frame_basis),
                        "Real r73 head requires explicit numeric origin/basis from signed source-frame metadata")
            else:
                require(isinstance(context, Tensor6Inputs) and context.frame_binding == frame
                        and context.geometry_ids == target.geometry_ids == (choice.conformer_id,), "Tensor needs independent explicit source-origin and actual geometry")
                require(name in self.release.projection["D4_bindings"], "Tensor exposure requires actual D4")
                # A complete tensor with mismatched component geometry is kept
                # for audit but remains ineligible; no source mask is rewritten.
                require(target.values.shape == (1, 6), "One full6 tensor per actual geometry required")
        return sample

    def close(self): self.reader.close()


class RealDataProvider:
    """Actual reader -> existing collate/PairedCorpusBatch -> PreparedV3Batch."""
    read_only = node_local = True

    def __init__(self, release, *, indexes, registry, reader_factory, structural_binding, validation_choices, physical_policy=None, normalizations=None):
        require(isinstance(release, VerifiedDataRelease), "Final actual release binding required")
        release.reverify()
        require(isinstance(registry, LabelRegistry) and registry.authority == "data_line"
                and registry.version == release.data_version, "Real same-version registry required")
        require(type(indexes) is dict and set(indexes) == set(ROLES), "Independent TRAIN/VAL/unseen indexes required")
        require(getattr(reader_factory, "read_only", None) is True and getattr(reader_factory, "node_local", None) is True
                and reader_factory.data_version == release.data_version
                and reader_factory.source_ref == release.projection["reader_source"], "Source-bound readonly node-local reader factory required")
        bound_bytes(reader_factory.source_ref)
        for field in registry.fields:
            if field.level == "ordered_entry":
                binding = release.projection["targets"].get(field.name)
                require(type(binding) is dict, "Joint ordered target binding required")
                bound_bytes(binding.get("source_frame_metadata"))
        implementation = inspect.getsourcefile(reader_factory if inspect.isfunction(reader_factory) else type(reader_factory))
        require(implementation is not None and Path(implementation).resolve() == Path(reader_factory.source_ref["path"]).resolve(),
                "Reader factory implementation is not the pinned source")
        for role, index in indexes.items():
            require(index.authority == "data_line" and index.role == role and index.version == release.data_version
                    and index.content_sha256 == release.projection["role_index_sha256"][role], "Actual released role/membership differs")
        require(type(validation_choices) is dict and set(validation_choices) == set(ROLES[1:]), "Both complete validation choice populations required")
        self.validation_choices = {}
        for role, batches in validation_choices.items():
            require(type(batches) in (tuple, list) and bool(batches) and all(type(x) in (tuple, list) and bool(x) for x in batches), "Explicit finite validation batches required")
            self.validation_choices[role] = tuple(tuple(x) for x in batches)
            require(canonical_hash([[asdict(x) for x in batch] for batch in batches]) ==
                    release.projection["validation_population_bindings"][role], "Validation choices are not the full released population")
        self.release, self.registry, self.binding = release, registry, structural_binding
        self.data_version = release.data_version
        self.source_sha256 = canonical_hash({"adapter": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                             "release": release.data_sha256, "reader": reader_factory.source_ref,
                                             "label_domains": hashlib.sha256(Path(__file__).with_name("v3_label_domains.py").read_bytes()).hexdigest()})
        require(not release.is_actual_data_release or physical_policy is not None,
                "Actual Data provider requires its same-version physical-policy binding")
        self.physical_policy = physical_policy
        if physical_policy is not None:
            from .v3_physical_policy import PhysicalLossPolicy, physical_policy_for_release
            require(isinstance(physical_policy, PhysicalLossPolicy)
                    and physical_policy.projection == physical_policy_for_release(
                        release, registry, physical_policy.reference).projection,
                    "Provider physical policy must match the exact joint evidence and target map")
            physical_policy.validate_for_registry(registry, enabled_fields=())
            self.source_sha256 = canonical_hash({"original_adapter_binding": self.source_sha256,
                                                "physical_loss_policy": physical_policy.projection})
        require(not release.is_actual_data_release or normalizations is not None,
                "Actual provider needs the bound D4 dispositions before selecting head transport")
        self.loss_disabled_fields = ()
        if normalizations is not None:
            from .v3_contract import validate_normalizations
            validate_normalizations(registry, normalizations)
            require(canonical_hash({k: asdict(v) for k, v in normalizations.items()})
                    == release.projection["normalization_sha256"], "Provider D4 dispositions differ from actual release")
            self.loss_disabled_fields = tuple(f.name for f in registry.fields
                if isinstance(normalizations.get(f.name), DisabledNormalization)
                or (physical_policy is not None and physical_policy.disabled(f.name)))
            if self.loss_disabled_fields:
                self.source_sha256 = canonical_hash({"original_adapter_binding": self.source_sha256,
                    "loss_disabled_transport_fields": list(self.loss_disabled_fields)})
        self.datasets = {role: ManifestSampleDataset(index, _CheckedFactory(reader_factory, release, role, self.loss_disabled_fields))
                         for role, index in indexes.items()}

    def prepare(self, choices, *, role, view_config, enabled_groups, enabled_fields):
        from .v3_trainer import PreparedV3Batch
        require(role in self.datasets, "Unknown/nonreleased role")
        choices = tuple(choices)
        require(bool(choices), "Nonempty explicit released choices required")
        decoded = tuple(self.datasets[role][choice] for choice in choices)
        batch = collate_v3_samples(decoded, self.registry, loss_disabled_fields=self.loss_disabled_fields)
        masks = eligibility_from_choices(choices, self.registry, self.binding, enabled_fields=enabled_fields)
        views = build_structural_views(batch.encoder_batch, ordinals=tuple(c.ordinal for c in choices), config=view_config,
                                       include_structural="S" in enabled_groups, graph_eligibility=masks)
        pd = {name: target for name, target in batch.targets.items() if self.registry.by_name()[name].group in ("D", "P")}
        return PreparedV3Batch(tuple(choices), views, pd, self.source_sha256, self.data_version, role,
                               {name: x.pair_index for name, x in pd.items() if x.pair_index is not None},
                               domain_inputs=batch.domain_inputs, geometry_context=batch.geometry_context)

    def validation_batches(self, *, role, view_config, enabled_groups, enabled_fields):
        require(role in self.validation_choices, "Only frozen ROUTINE VAL and TRAIN-unseen populations allowed")
        batches = self.validation_choices[role]
        return len(batches), (self.prepare(batch, role=role, view_config=view_config,
                             enabled_groups=enabled_groups, enabled_fields=enabled_fields) for batch in batches)

    def close(self):
        for dataset in self.datasets.values(): dataset.close()


def make_proxy_inputs(request, release, *, indexes, registry, reader_factory, structural_binding,
                      normalizations, validation_choices, full_train_contract=None, grid_train_contract=None, physical_policy_reference=None):
    """Return the ACTUAL existing trainer entry type; no alternate runner."""
    from .v3_proxy_run import ProxyInputs
    require(isinstance(release, VerifiedDataRelease) and release.request_sha256 == canonical_hash(request), "Release/request changed")
    release.reverify()  # Re-establish authority before using family/scope/normalization projections.
    scope = release.projection["scope"]
    require((scope == "authoritative_full_train") == (full_train_contract is not None)
            and (scope == "authoritative_grid_train") == (grid_train_contract is not None),
            "Full/grid contracts cannot be attached to proxy or provisional pilot inputs")
    normalizations = dict(normalizations)
    require(canonical_hash({k: asdict(v) for k, v in normalizations.items()}) == release.projection["normalization_sha256"],
            "All model normalizations must match the actual D4 interpreter projection")
    for field in registry.fields:
        if field.representation == "symmetric_tensor6":
            require(normalizations.get(field.name) == tensor6_normalization(release, field.name, target_local=release.is_actual_data_release), "Tensor normalization must come from actual bound TRAIN D4")
    physical_policy = None
    configuration = bound_json(request["configuration"]) if "configuration" in request else {}
    declared_physical = configuration.get("physical_policy_reference")
    require(physical_policy_reference is None or physical_policy_reference == declared_physical,
            "Caller physical policy must match the sealed configuration reference")
    require(not release.is_actual_data_release or declared_physical is not None,
            "Actual Data consumption requires its same-version physical-policy decision; missing is HOLD")
    if declared_physical is not None:
        from .v3_physical_policy import physical_policy_for_release
        physical_policy = physical_policy_for_release(release, registry, declared_physical)
        contract = configuration["proxy_contract"]
        from .v3_losses import loss_prediction_fields
        loss_prediction_fields(registry, normalizations, enabled_groups=contract["groups"],
            enabled_fields=contract["fields"], physical_policy=physical_policy)
    provider = RealDataProvider(release, indexes=indexes, registry=registry, reader_factory=reader_factory,
                               structural_binding=structural_binding, validation_choices=validation_choices,
                               physical_policy=physical_policy,
                               normalizations=normalizations if physical_policy is not None or release.is_actual_data_release else None)
    receipt = {"model_consumption_projection_sha256": release.sha256, "evidence": deepcopy(release.evidence),
               "verifier": deepcopy(release.verifier), "user_ALL_A_policy": deepcopy(ALL_A_POLICY),
               "authority_family": release.authority_family}
    if physical_policy is not None:
        receipt["physical_loss_policy"] = physical_policy.projection
    if full_train_contract is not None:
        receipt["full_TRAIN_consumption_contract_sha256"] = canonical_hash(full_train_contract)
    inputs = ProxyInputs(indexes["TRAIN"], provider, registry, structural_binding, normalizations, receipt,
                         deepcopy(release.projection["validation_population_bindings"]),
                         "data_line_final" if release.is_final else "data_line_pilot", release.is_actual_data_release,
                         canonical_hash(request), full_train_contract, grid_train_contract)
    if physical_policy is not None: inputs = inputs.with_physical_policy(physical_policy)
    actual = {"index_sha256": inputs.index.content_sha256, "registry_sha256": registry.content_sha256,
              "normalization_sha256": canonical_hash({k: asdict(v) for k, v in normalizations.items()}),
              "adapter_sha256": provider.source_sha256, "data_version": release.data_version}
    require(request.get("input_projection") == actual, "Exact request/index/registry/D4/reader projection differs")
    return inputs
