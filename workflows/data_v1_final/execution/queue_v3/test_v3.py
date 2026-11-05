"""Fourteen new synthetic contracts; no scheduler, corpus, network or process I/O.

The last check reads only the two small Python source files for exact inverse
proof. Claim checks compute paths only; no persistent claim or fixture is made.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from ..queue_v1 import test_queue_contract as prior
from . import contract as q
from .verify_proof_delta import verify


def encoded(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def fixture_spec(mode="BOUNDED_METADATA_PREPARATION"):
    request, files = prior.fixture_request()
    root = q.RUN + "/control/"
    parent = prior.pin(root + "synthetic_parent.json", b'{"actual_fixture_parent":true}\n')
    files[parent["path"]] = b'{"actual_fixture_parent":true}\n'
    pilot = mode == "FIXTURE_ONLY"
    spec = {"schema": "ROOT_REVIEWED_QUEUED_STAGE_SPEC_V3", "kind": "analysis", "pilot": pilot,
        "cpus": 16, "memory_gib": 64, "scope_key": "synthetic_exact_scope",
        "scope_parameters": {"shard_id": 0, "read_only": True}, "source_status_stage": "scan",
        "source_status_manifest": False, "wall_seconds": 3600,
        "estimated_peak_output_bytes": 60 * q.old.GIB, "stage_output_cap_bytes": 24 * q.old.GIB,
        "source_references": request["source_references"], "data_references": request["data_references"],
        "execution_argv": [q.old.PYTHON, "-B", "-m", "synthetic_not_executed",
                           "--startup-proof", "__ROOT_STARTUP_PROOF__"]}
    review = {"schema": "EXACT_ANALYSIS_QUEUE_SCOPE_ROOT_REVIEW_V3",
        "status": "APPROVED_FOR_EXACT_STAGE", "reviewer": "root", "scope_mode": mode,
        "parent_evidence_references": [] if pilot else [parent]}
    for key in ("scope_key", "scope_parameters", "pilot", "wall_seconds",
                "estimated_peak_output_bytes", "execution_argv", "source_status_stage", "stage_output_cap_bytes"):
        review[key] = deepcopy(spec[key])
    profile = None
    if mode == "BOUNDED_PERFORMANCE_BATCH":
        review["bounded_batch_limits_reviewed"] = True
    if mode == "FULL_SOURCE_AFTER_PROFILE":
        profile = parent
        review.update(profile_reviewed=True, approved_profile_reference=parent)
    if mode == "FULL_SOURCE_INVENTORY_PRIOR_CRC":
        spec["stage_output_cap_bytes"] = review["stage_output_cap_bytes"] = 10 * q.old.GIB
        review.update(inventory_only=True, candidate_release_authorized=False,
                      crc_full_eof_actual_passed=True, crc_receipt_reference=parent)
    raw = encoded(review); path = root + "synthetic_review.json"; files[path] = raw
    spec["scope"] = {"mode": mode, "review": prior.pin(path, raw), "parent_profile": profile}
    return spec, review, files


def rebind_review(spec, review, files):
    path = spec["scope"]["review"]["path"]; raw = encoded(review); files[path] = raw
    spec["scope"]["review"] = prior.pin(path, raw)


def bound_request(spec, files):
    request, original = prior.fixture_request(); files.update(original)
    path = q.RUN + "/control/synthetic_stage_spec.json"; raw = encoded(spec); files[path] = raw
    ref = prior.pin(path, raw)
    for key, value in spec.items():
        if key not in {"schema", "source_references", "execution_argv"}:
            request[key] = deepcopy(value)
    request["schema"] = "DATA_V1_QUEUED_REQUEST_V1"
    request["execution_argv"] = [s.replace("__ROOT_STARTUP_PROOF__", request["startup_proof_path"])
                                 for s in spec["execution_argv"]]
    request["root_review"]["stage_spec_reference"] = ref
    refs = [*request["source_references"], ref, spec["scope"]["review"],
            *json.loads(files[spec["scope"]["review"]["path"]])["parent_evidence_references"]]
    request["source_references"] = list({r["path"]: r for r in refs}.values())
    return request


def registry(jid, request):
    ref = {"path": q.RUN + "/control/requests/" + request["job_name"] + ".json",
           "bytes": 100, "sha256": "a" * 64}
    return {"schema": "REGISTERED_QUEUED_CPU_JOBS_V3",
            "jobs": [{"job_id": jid, "request_reference": ref}]}


class QueueV3Tests(unittest.TestCase):
    def test_01_honest_nonpilot_and_fixture_scope(self):
        for mode in ("FIXTURE_ONLY", "BOUNDED_METADATA_PREPARATION"):
            spec, review, files = fixture_spec(mode)
            self.assertEqual(q.validate_scope_spec(spec, read_small=files.__getitem__)["mode"], mode)
            spec["pilot"] = not spec["pilot"]
            with self.assertRaisesRegex(ValueError, "(FIXTURE_ONLY_REQUIRES_TRUE_PILOT|FULL_OR_PREPARATION_REQUIRES_FALSE_PILOT)"):
                q.validate_scope_spec(spec, read_small=files.__getitem__)

    def test_02_domain_fields_and_startup_token_preserved(self):
        spec, review, files = fixture_spec(); request = bound_request(spec, files)
        q.validate_bound_request(request, read_small=files.__getitem__)
        self.assertFalse(request["pilot"])
        self.assertIs(request["source_status_manifest"], False)
        self.assertEqual(request["execution_argv"][-1], request["startup_proof_path"])
        for key in ("source_status_stage", "scope_parameters", "source_status_manifest"):
            bad = deepcopy(request); bad[key] = None
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "PRODUCER_DOMAIN_FIELD_NOT_PRESERVED"):
                q.validate_bound_request(bad, read_small=files.__getitem__)

    def test_03_exact_scope_review_and_argv_binding(self):
        for key, value in (("scope_parameters", {}), ("execution_argv", ["other"]), ("reviewer", "not-root")):
            spec, review, files = fixture_spec(); review[key] = value; rebind_review(spec, review, files)
            with self.subTest(key=key), self.assertRaises(ValueError):
                q.validate_scope_spec(spec, read_small=files.__getitem__)
        spec, review, files = fixture_spec(); files[spec["scope"]["review"]["path"]] += b"changed"
        with self.assertRaisesRegex(ValueError, "PIN_CHANGED"):
            q.validate_scope_spec(spec, read_small=files.__getitem__)

    def test_04_strict_resources_and_analysis_role_not_relaxed(self):
        for patch in ({"kind": "qm"}, {"cpus": 8}, {"memory_gib": 32}, {"wall_seconds": 14401}):
            spec, review, files = fixture_spec(); spec.update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                q.validate_scope_spec(spec, read_small=files.__getitem__)
        spec, review, files = fixture_spec(); request = bound_request(spec, files)
        for patch in ({"node": "compute-0-21"}, {"memory_gib": 32}, {"memory_exemption": True}):
            bad = deepcopy(request); bad.update(patch)
            with self.subTest(patch=patch), self.assertRaises(q.old.ContractError):
                q.old.validate_request(bad, read_small=files.__getitem__)

    def test_05_inventory_uses_prior_crc_not_circular_full_profile(self):
        spec, review, files = fixture_spec("FULL_SOURCE_INVENTORY_PRIOR_CRC")
        self.assertIsNone(spec["scope"]["parent_profile"])
        q.validate_scope_spec(spec, read_small=files.__getitem__)
        for key, value in (("crc_full_eof_actual_passed", False), ("candidate_release_authorized", True)):
            bad_review = deepcopy(review); bad_review[key] = value
            rebind_review(spec, bad_review, files)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "PRIOR_CRC_INVENTORY"):
                q.validate_scope_spec(spec, read_small=files.__getitem__)
        spec, review, files = fixture_spec("FULL_SOURCE_INVENTORY_PRIOR_CRC")
        spec["stage_output_cap_bytes"] = review["stage_output_cap_bytes"] = 10 * q.old.GIB + 1
        rebind_review(spec, review, files)
        with self.assertRaisesRegex(ValueError, "10GIB_CAP"):
            q.validate_scope_spec(spec, read_small=files.__getitem__)

    def test_06_full_follow_on_requires_exact_actual_profile_review(self):
        spec, review, files = fixture_spec("FULL_SOURCE_AFTER_PROFILE")
        q.validate_scope_spec(spec, read_small=files.__getitem__)
        spec["scope"]["parent_profile"] = None
        with self.assertRaisesRegex(ValueError, "FULL_STAGE_REQUIRES_ACTUAL"):
            q.validate_scope_spec(spec, read_small=files.__getitem__)

    def test_07_stage_cap_and_whole_phase_quota_are_distinct(self):
        spec, review, files = fixture_spec()
        result = q.validate_scope_spec(spec, read_small=files.__getitem__)
        self.assertEqual(result["stage_output_cap_bytes"], 24 * q.old.GIB)
        self.assertEqual(spec["estimated_peak_output_bytes"], 60 * q.old.GIB)
        spec["stage_output_cap_bytes"] = review["stage_output_cap_bytes"] = 61 * q.old.GIB
        rebind_review(spec, review, files)
        with self.assertRaisesRegex(ValueError, "WITHIN_WHOLE_PHASE_BUDGET"):
            q.validate_scope_spec(spec, read_small=files.__getitem__)

    def test_08_disjoint_original_and_new_registries_all_keys(self):
        old, files = prior.fixture_request(); new = deepcopy(old)
        new["job_name"] = "dv1_q_synthetic_new"
        new["startup_proof_path"] = q.RUN + "/control/queue_startup/" + new["job_name"] + ".json"
        before = registry("959", old); before["schema"] = "REGISTERED_QUEUED_CPU_JOBS_V1"
        after = registry("999", new)
        requests = {before["jobs"][0]["request_reference"]["path"]: old,
                    after["jobs"][0]["request_reference"]["path"]: new}
        regs = [(q.RUN + "/control/queued_phase_original.json", before),
                (q.REGISTRY_DIR + "/new_phase.json", after)]
        q.validate_disjoint(regs, load_request=lambda ref: requests[ref["path"]])
        duplicate = deepcopy(regs); duplicate[1][1]["jobs"][0]["job_id"] = "959"
        with self.assertRaisesRegex(ValueError, "REGISTRY_OVERLAP:job_id"):
            q.validate_disjoint(duplicate, load_request=lambda ref: requests[ref["path"]])
        duplicate = deepcopy(regs); duplicate[1][1] = registry("999", old)
        with self.assertRaisesRegex(ValueError, "REGISTRY_OVERLAP:request_path"):
            q.validate_disjoint(duplicate, load_request=lambda ref: requests[ref["path"]])
        broken = deepcopy(new); broken["startup_proof_path"] = old["startup_proof_path"]
        with self.assertRaisesRegex(ValueError, "REQUEST_OR_PROOF_NAMESPACE"):
            q.row_keys(after["jobs"][0], broken)

    def test_09_only_exact_own_held_cpu64_jobs_release(self):
        request, files = prior.fixture_request()
        job = q.old._fields(prior.job("999", state="PENDING", Reason="JobHeldUser", Priority="0",
            ReqNodeList=request["node"], TimeLimit="01:00:00", TRES="cpu=16,mem=64G,node=1,billing=16"))
        q.validate_held_job(request, job, expected_job_id="999")
        for key, value in (("UserId", "foreign(999)"), ("Requeue", "1"), ("MinMemoryNode", "0"),
                           ("Reason", "Resources"), ("Command", "/other"), ("NumCPUs", "112")):
            bad = deepcopy(job); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                q.validate_held_job(request, bad, expected_job_id="999")

    def test_10_live_observer_pid_boot_ticks_argv_cgroup_and_registry(self):
        reference = {"path": "/synthetic", "bytes": 1, "sha256": "a" * 64}
        saved = {"pid": 123, "uid": 1278, "boot_id": "boot", "start_ticks": 321,
            "pgid": 123, "sid": 123, "argv": ["synthetic"], "argv_sha256": "h",
            "cgroup": "synthetic", "cgroup_sha256": "c", "registry_reference": reference,
            "source_reference": reference}
        q.validate_observer_identity(saved, deepcopy(saved), expected_argv=["synthetic"],
            registry_reference=reference, source_reference=reference)
        for key in ("pid", "boot_id", "start_ticks", "pgid", "sid", "argv_sha256", "cgroup_sha256"):
            current = deepcopy(saved); current[key] = None
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "IDENTITY_CHANGED"):
                q.validate_observer_identity(saved, current, expected_argv=["synthetic"],
                    registry_reference=reference, source_reference=reference)

    def test_11_persistent_claim_paths_bind_job_request_and_proof(self):
        from .registry import claim_record, claim_paths
        request, files = prior.fixture_request(); reg = registry("999", request)
        path = q.REGISTRY_DIR + "/new_phase.json"
        claim = claim_record(path, reg["jobs"][0], request)
        paths = claim_paths(claim)
        self.assertEqual(len(set(paths)), 3)
        self.assertTrue(all("queue_v3_claims" in str(p) for p in paths))
        changed = deepcopy(claim); changed["keys"]["job_id"] = "1000"
        self.assertNotEqual(claim_paths(changed)[0], paths[0])
        self.assertEqual(claim_paths(changed)[1:], paths[1:])
        with self.assertRaisesRegex(ValueError, "CANONICAL_V3_REGISTRY"):
            q.registry_path(q.RUN + "/control/queued_phase_original.json")

    def test_12_proof_only_adds_redundant_actual_memory_basis_before_ready(self):
        here = Path(__file__).parent
        old = (here.parent / "queue_v1/observe.py").read_text(encoding="utf-8")
        new = (here / "proof_v3.py").read_text(encoding="utf-8")
        result = verify(old, new)
        self.assertTrue(result["inverse_function_bytes_equal"])
        self.assertTrue(result["inverse_normalized_ast_identical"])
        with self.assertRaisesRegex(ValueError, "OTHER_PROOF_SOURCE_CHANGE"):
            verify(old, new.replace("capacity*85", "capacity*95"))


    def test_13_honest_true_profile_allowed_but_full_true_rejected(self):
        for pilot in (True, False):
            spec, review, files = fixture_spec("BOUNDED_PERFORMANCE_BATCH")
            spec["pilot"] = review["pilot"] = pilot
            rebind_review(spec, review, files)
            self.assertEqual(q.validate_scope_spec(spec, read_small=files.__getitem__)["mode"],
                             "BOUNDED_PERFORMANCE_BATCH")
            request = bound_request(spec, files)
            q.validate_bound_request(request, read_small=files.__getitem__)
            self.assertIs(request["pilot"], pilot)
        for mode in ("BOUNDED_METADATA_PREPARATION", "FULL_SOURCE_INVENTORY_PRIOR_CRC", "FULL_SOURCE_AFTER_PROFILE"):
            spec, review, files = fixture_spec(mode)
            spec["pilot"] = review["pilot"] = True
            rebind_review(spec, review, files)
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "REQUIRES_FALSE_PILOT"):
                q.validate_scope_spec(spec, read_small=files.__getitem__)

    def test_14_site_held_one_to_one_range_with_exact_tres_node(self):
        request, files = prior.fixture_request()
        job = q.old._fields(prior.job("999", state="PENDING", Reason="JobHeldUser", Priority="0",
            ReqNodeList=request["node"], TimeLimit="01:00:00", TRES="cpu=16,mem=64G,node=1,billing=16"))
        for nodes in ("1", "1-1"):
            good = deepcopy(job); good["NumNodes"] = nodes
            self.assertTrue(q.validate_held_job(request, good, expected_job_id="999"))
        for nodes in ("0", "2", "1-2", "1-99"):
            bad = deepcopy(job); bad["NumNodes"] = nodes
            with self.subTest(nodes=nodes), self.assertRaisesRegex(ValueError, "NODE_DIFFERS"):
                q.validate_held_job(request, bad, expected_job_id="999")
        for tres in ("cpu=16,mem=64G,node=2", "cpu=16,mem=64G", "cpu=16,mem=64G,node=1,node=1",
                     "cpu=16,mem=64G,node=1,gres/gpu=1"):
            bad = deepcopy(job); bad["NumNodes"] = "1-1"; bad["TRES"] = tres
            with self.subTest(tres=tres), self.assertRaises(ValueError):
                q.validate_held_job(request, bad, expected_job_id="999")

if __name__ == "__main__":
    unittest.main()
