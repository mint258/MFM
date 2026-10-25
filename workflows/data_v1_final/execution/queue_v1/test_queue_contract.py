"""Twelve synthetic queue contracts; no files, scheduler, network or science I/O."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import unittest

from . import queue_contract as q


def pin(path, raw):
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def fixture_request(script_change=None):
    name = "dv1_q_synthetic_contract"
    script_path = q.RUN + "/control/scripts/" + name + ".sbatch"
    authority = q.RUN + "/repository/configs/data_v1/synthetic_queue_authority.json"
    script = ("#!/bin/bash\n#SBATCH --job-name=" + name + "\n#SBATCH --partition=cpu\n"
              "#SBATCH --nodelist=compute-0-17\n#SBATCH --nodes=1\n#SBATCH --ntasks=1\n"
              "#SBATCH --cpus-per-task=16\n#SBATCH --mem=64G\n#SBATCH --exclusive=user\n"
              "#SBATCH --time=01:00:00\nset -euo pipefail\n")
    if script_change:
        script = script_change(script)
    files = {script_path: script.encode(), authority: b'{"synthetic_authority_only":true}\n'}
    request = {"schema": "DATA_V1_QUEUED_REQUEST_V1", "kind": "analysis", "node": "compute-0-17",
        "job_name": name, "cpus": 16, "memory_gib": 64, "wall_seconds": 3600,
        "estimated_peak_output_bytes": 4096, "estimated_total_core_hours": 16, "pilot": True,
        "workdir": q.PROJECT, "exclusive_user": True,
        "startup_proof_path": q.RUN + "/control/queue_startup/" + name + ".json", "startup_wait_seconds": 120,
        "script_reference": pin(script_path, files[script_path]), "source_references": [pin(authority, files[authority])],
        "queue_authority_reference": pin(authority, files[authority]), "data_references": [{
            "path": q.RUN + "/synthetic_never_read.parquet", "bytes": 10**12, "sha256": "a" * 64}],
        "execution_argv": [q.PYTHON, "-B", "-m", "synthetic_not_executed"], "dependencies": [],
        "root_review": {"status": "APPROVED", "reviewer": "root"}}
    return request, files


def node(real=262144, allocated=65536, cpus=16, total=112):
    return (f"NodeName=compute-0-17 Partitions=cpu,all RealMemory={real} AllocMem={allocated} "
            f"CPUTot={total} CPUAlloc={cpus} State=MIXED")


def job(jid="700", owner=1278, memory="64G", cpus=16, state="RUNNING", nodes="compute-0-17", **changes):
    request, _ = fixture_request()
    fields = {"JobId": jid, "UserId": f"synthetic({owner})", "JobName": request["job_name"],
        "JobState": state, "Partition": "cpu", "NodeList": nodes, "NumNodes": "1", "NumCPUs": str(cpus),
        "NumTasks": "1", "MinMemoryNode": memory, "OverSubscribe": "USER", "Requeue": "0",
        "WorkDir": q.PROJECT, "Command": request["script_reference"]["path"]}
    fields.update(changes)
    return " ".join(k + "=" + v for k, v in fields.items())


def startup_proof():
    request, _ = fixture_request()
    epoch = 2_000_000_000.0
    observed = datetime.fromtimestamp(epoch, timezone.utc).isoformat()
    proof = {"observed_at": observed, "uid": 1278, "job_id": "700", "boot_id": "synthetic-boot",
        "request_reference": {"path": q.RUN + "/control/requests/" + request["job_name"] + ".json",
                              "bytes": 100, "sha256": "b" * 64},
        "request": deepcopy(request), "node_metadata": node(), "job_metadata": job(),
        "existing_jobs_all_users": [], "committed_memory_mib": 0,
        "account_free_bytes": 200_000_000_000 + request["estimated_peak_output_bytes"], "quota_raw": "synthetic quota",
        "memory_basis": q.MEMORY_BASIS, "script_reference": deepcopy(request["script_reference"]),
        "source_references": deepcopy(request["source_references"]),
        "queue_authority_reference": deepcopy(request["queue_authority_reference"]),
        "memory_observation": {"node": request["node"], "uid": 1278, "observed_at": observed,
            "observed_unix_seconds": epoch, "boot_id": "synthetic-boot", "total_bytes": 256 * q.GIB,
            "available_bytes": 200 * q.GIB, "used_bytes": 56 * q.GIB}}
    return request, proof, epoch


class QueueContractTests(unittest.TestCase):
    def denied(self, code, function, *args, **kwargs):
        with self.assertRaises(q.ContractError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def fresh(self, request, proof, now):
        return q.validate_fresh_startup_proof(proof, request, now_unix=now, uid=1278, boot_id="synthetic-boot")

    def test_01_exact_small_pins_and_no_data_reader_callback(self):
        request, files = fixture_request()
        reads = []
        def reader(path):
            reads.append(path)
            return files[path]
        result = q.validate_request(request, read_small=reader)
        self.assertEqual(result["status"], "VALIDATED_QUEUED_REQUEST_NOT_ADMISSION")
        self.assertEqual(set(reads), set(files))
        self.assertNotIn(request["data_references"][0]["path"], reads)
        self.assertFalse(result["data_bodies_read_or_stat"])

    def test_02_resource_role_wall_and_exclusive_request_boundaries(self):
        original, files = fixture_request()
        for patch, code in (({"cpus": 112}, "EXACT_16CPU_64GIB_REQUIRED"),
                ({"memory_gib": 32}, "EXACT_16CPU_64GIB_REQUIRED"),
                ({"wall_seconds": 14401}, "STRICT_SITE_FOUR_HOUR_WALL_REQUIRED"),
                ({"node": "compute-0-21"}, "NODE_OUTSIDE_AUTHORIZED_CPU_ROLE"),
                ({"kind": "qm", "node": "compute-0-2"}, "NODE_OUTSIDE_AUTHORIZED_CPU_ROLE"),
                ({"exclusive_user": False}, "WORKDIR_OR_USER_EXCLUSIVITY_REQUIRED"),
                ({"resource_policy": "CPU_BOUNDED_TEST_LIVE_MEMORY_V1"}, "NO_MEMORY_EXEMPTION_FOR_QUEUED_EXECUTION")):
            with self.subTest(patch=patch):
                request = deepcopy(original); request.update(patch)
                self.denied(code, q.validate_request, request, read_small=files.__getitem__)
        request, files = fixture_request(lambda s: s.replace("--exclusive=user", "--exclusive=exclusive"))
        self.denied("SBATCH_RESOURCE_IDENTITY_DIFFERS", q.validate_request, request, read_small=files.__getitem__)

    def test_03_changed_oversized_or_unbound_source_pins_stop_before_data(self):
        request, files = fixture_request()
        changed = dict(files); changed[request["queue_authority_reference"]["path"]] += b"changed"
        self.denied("SMALL_SOURCE_PHYSICAL_PIN_CHANGED", q.validate_request, request, read_small=changed.__getitem__)
        oversized = deepcopy(request); oversized["source_references"][0]["bytes"] = q.SMALL_CAP + 1
        self.denied("SMALL_SOURCE_ONLY_NO_DATA_BODY_READ", q.validate_request, oversized,
                    read_small=lambda _: self.fail("Oversized metadata must not be opened"))
        unbound = deepcopy(request)
        unbound["queue_authority_reference"] = pin(q.RUN + "/unregistered_authority.json", b"x")
        self.denied("EXACT_QUEUE_AUTHORITY_PIN_NOT_IN_SOURCES", q.validate_request, unbound, read_small=files.__getitem__)

    def test_04_scontrol_multiline_records_and_duplicate_fields_fail_closed(self):
        text = job().replace(" UserId=", "\n   UserId=") + "\n\n" + job("701", owner=42, memory="8G")
        rows = q.parse_scontrol_jobs(text)
        self.assertEqual([r["JobId"] for r in rows], ["700", "701"])
        self.assertEqual(rows[0]["WorkDir"], q.PROJECT)
        self.denied("DUPLICATE_JOB_RECORD", q.parse_scontrol_jobs, job() + "\n" + job())
        self.denied("DUPLICATE_OR_AMBIGUOUS_SCONTROL_FIELD", q.parse_scontrol_jobs, job() + " MinMemoryNode=0")

    def test_05_any_other_zero_or_missing_memory_is_not_admission(self):
        request, _ = fixture_request()
        for owner in (42, 1278):
            with self.subTest(owner=owner):
                self.denied("OTHER_JOB_ZERO_MEMORY_IS_UNBOUNDED_NO_ADMISSION", q.admit_memory,
                            request, q.parse_scontrol_node(node(cpus=16)), q.parse_scontrol_jobs(job("701", owner=owner, memory="0")))
        missing = q.parse_scontrol_jobs(job("701", owner=42))[0]
        missing.pop("MinMemoryNode")
        self.denied("OTHER_JOB_MEMORY_DECLARATION_MISSING_OR_CONFLICTING", q.admit_memory,
                    request, q.parse_scontrol_node(node(cpus=16)), [missing])

    def test_06_per_cpu_memory_and_compressed_multinode_are_conservative(self):
        request, _ = fixture_request()
        other = q.parse_scontrol_jobs(job("701", owner=42, cpus=32, nodes="compute-0-[16-18]"))[0]
        other.pop("MinMemoryNode"); other["MinMemoryCPU"] = "2G"; other["NumNodes"] = "3"
        result = q.admit_memory(request, q.parse_scontrol_node(node(allocated=0, cpus=16)), [other])
        self.assertEqual(result["sum_other_declared_memory_mib"], 65536)
        self.assertEqual(result["projected_memory_mib"], 131072)

    def test_07_known_own64_is_subtracted_once_before_other_maximum(self):
        request, _ = fixture_request()
        jobs = q.parse_scontrol_jobs(job() + "\n" + job("701", owner=42, memory="32G"))
        result = q.admit_memory(request, q.parse_scontrol_node(node(allocated=96 * 1024, cpus=32)), jobs, own_job_id="700")
        self.assertEqual(result["own_memory_mib_excluded"], 65536)
        self.assertEqual(result["committed_memory_mib"], 32768)
        self.assertEqual(result["projected_memory_mib"], 98304)
        self.assertEqual([r["job_id"] for r in result["existing_jobs_all_users"]], ["701"])
        self.denied("EXACT_OWN_JOB_METADATA_REQUIRED_BEFORE_SUBTRACTION", q.admit_memory,
                    request, q.parse_scontrol_node(node(cpus=0)), [], own_job_id="700")

    def test_08_cr_core_allocmem_below_own_clamps_but_other_sum_stays(self):
        request, _ = fixture_request()
        jobs = q.parse_scontrol_jobs(job() + "\n" + job("701", owner=42, memory="32G"))
        result = q.admit_memory(request, q.parse_scontrol_node(node(allocated=0, cpus=32)), jobs, own_job_id="700")
        self.assertEqual(result["alloc_memory_other_mib"], 0)
        self.assertEqual(result["committed_memory_mib"], 32768)
        self.assertEqual(result["cpu_allocation"]["own_excluded"], 16)

    def test_09_exact85_boundary_unattributed_alloc_and_inventory_gaps(self):
        request, _ = fixture_request()
        others = q.parse_scontrol_jobs(job("701", owner=42, memory="106G"))
        exact = q.admit_memory(request, q.parse_scontrol_node(node(real=200 * 1024, allocated=0, cpus=16)), others)
        self.assertEqual(exact["projected_memory_mib"], 170 * 1024)
        above = q.parse_scontrol_jobs(job("701", owner=42, memory=str(106 * 1024 + 1) + "M"))
        self.denied("WAIT_FOR_STRICT_ALL_USER_DECLARED_MEMORY", q.admit_memory, request,
                    q.parse_scontrol_node(node(real=200 * 1024, allocated=0, cpus=16)), above)
        self.denied("WAIT_FOR_STRICT_ALL_USER_DECLARED_MEMORY", q.admit_memory, request,
                    q.parse_scontrol_node(node(real=200 * 1024, allocated=111 * 1024, cpus=16)), others)
        self.denied("INCOMPLETE_ALL_USER_JOB_INVENTORY", q.admit_memory, request,
                    q.parse_scontrol_node(node(cpus=32)), others)

    def test_10_actual_startup_uid_state_node_resources_script_and_no_requeue(self):
        request, _ = fixture_request()
        result = q.validate_startup_job(request, job(), expected_job_id="700", uid=1278,
                                         script_reference=request["script_reference"])
        self.assertTrue(result["exclusive_user"])
        for changes, code in (({"OverSubscribe": "NO"}, "ACTUAL_EXCLUSIVE_USER_NO_REQUEUE_REQUIRED"),
                ({"Requeue": "1"}, "ACTUAL_EXCLUSIVE_USER_NO_REQUEUE_REQUIRED"),
                ({"NumCPUs": "112"}, "ACTUAL_STARTUP_ALLOCATION_NOT_EXACT_16CPU_64G"),
                ({"MinMemoryNode": "32G"}, "ACTUAL_STARTUP_ALLOCATION_NOT_EXACT_16CPU_64G"),
                ({"UserId": "foreign(42)"}, "ACTUAL_ROOT_RUNNING_JOB_REQUIRED"),
                ({"JobState": "PENDING"}, "ACTUAL_ROOT_RUNNING_JOB_REQUIRED"),
                ({"NodeList": "compute-0-18"}, "ACTUAL_STARTUP_NODE_OR_NAME_DIFFERS"),
                ({"WorkDir": "/tmp"}, "ACTUAL_WORKDIR_OR_SCRIPT_BINDING_DIFFERS"),
                ({"Command": "/tmp/other.sbatch"}, "ACTUAL_WORKDIR_OR_SCRIPT_BINDING_DIFFERS")):
            with self.subTest(changes=changes):
                self.denied(code, q.validate_startup_job, request, job(**changes), expected_job_id="700",
                            uid=1278, script_reference=request["script_reference"])

    def test_11_fresh_target_clock_uid_boot_and120second_boundary(self):
        request, proof, epoch = startup_proof()
        self.assertEqual(self.fresh(request, proof, epoch + 120)["status"], "FRESH_STRICT_STARTUP_PROOF_VERIFIED")
        formatting_delay = deepcopy(proof)
        formatting_delay["observed_at"] = datetime.fromtimestamp(epoch + .0005, timezone.utc).isoformat()
        formatting_delay["memory_observation"]["observed_at"] = formatting_delay["observed_at"]
        self.assertEqual(self.fresh(request, formatting_delay, epoch)["age_seconds"], 0)
        self.denied("STARTUP_PROOF_STALE_OR_FUTURE", self.fresh, request, proof, epoch + 120.001)
        self.denied("STARTUP_PROOF_STALE_OR_FUTURE", self.fresh, request, proof, epoch - 0.001)
        for key, value in (("uid", 42), ("boot_id", "different-boot")):
            changed = deepcopy(proof); changed[key] = value
            self.denied("STARTUP_UID_OR_BOOT_DIFFERS", self.fresh, request, changed, epoch)
        changed = deepcopy(proof); changed["memory_observation"]["observed_unix_seconds"] -= 2
        self.denied("OBSERVATION_NOT_SAME_FRESH_TARGET_CLOCK", self.fresh, request, changed, epoch)

    def test_12_fresh_proof_recomputes_memory_pins_quota_and_refuses_exception(self):
        request, proof, epoch = startup_proof()
        self.assertEqual(self.fresh(request, proof, epoch)["remaining_account_bytes_after_output"], 200_000_000_000)
        for change, code in (({"committed_memory_mib": 1}, "DECLARED_MEMORY_PROOF_NOT_RECOMPUTABLE"),
                ({"account_free_bytes": proof["account_free_bytes"] - 1}, "WHOLE_OUTPUT_PLUS_200GB_RESERVE_REQUIRED"),
                ({"memory_exemption": True}, "STARTUP_MEMORY_EXEMPTION_FORBIDDEN"),
                ({"live_envelope_admission_passed": False}, "LIVE_OR_EXECUTION_ADMISSION_NOT_GRANTED"),
                ({"source_references": []}, "STARTUP_SOURCE_REFERENCES_DIFFER"),
                ({"existing_jobs_all_users": [{"metadata": job()}]}, "OWN_JOB_REPEATED_IN_OTHER_JOBS")):
            with self.subTest(change=change):
                altered = deepcopy(proof); altered.update(change)
                self.denied(code, self.fresh, request, altered, epoch)
        altered = deepcopy(proof)
        altered["existing_jobs_all_users"] = [{"metadata": job("701", owner=42, memory="0")}]
        self.denied("OTHER_JOB_ZERO_MEMORY_IS_UNBOUNDED_NO_ADMISSION", self.fresh, request, altered, epoch)


if __name__ == "__main__":
    unittest.main()
