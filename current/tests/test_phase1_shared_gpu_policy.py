"""Synthetic shared-policy observations; no real GPU protection is asserted."""
from copy import deepcopy

import pytest

from phychem_mfm.phase1 import formal_gate as gate
from phychem_mfm.phase1.formal_runtime import single_gpu_environment
from test_phase1_pretraining_scope import prepared, seal, codes
from test_phase1_formal_gate import _observation, UUID_0, UUID_1


@pytest.fixture
def shared(prepared):
    case = prepared["case"]
    protocol = case["protocol"]
    protocol["compute"]["gpu_isolation_policy"] = gate.SHARED_GPU_POLICY
    seal(prepared)
    case["slurm_config_text"] = ("GresTypes = (null)\nTaskPlugin = task/affinity\n"
                                  "ProctrackType = proctrack/cgroup\nPreemptMode = OFF\n")
    case["slurm_node_text"] = "NodeName=compute-0-20 Gres=(null) State=ALLOCATED CfgTRES=cpu=64\n"
    case["slurm_job_text"] = ("JobId=123 UserId=zixiao(3938) JobState=RUNNING Partition=gpu "
                              "Account=research NodeList=compute-0-20 AllocTRES=cpu=4,mem=12G "
                              "TimeLimit=02:00:00\n")
    # No GRES file, device constraint or SSH adoption is claimed.
    case["configuration_files"]["gres"].unlink()
    case["configuration_files"]["cgroup"].write_text("ConstrainCores=yes\n", encoding="utf-8")
    case["configuration_files"]["pam"].write_text("account required pam_unix.so\n", encoding="utf-8")
    observation = _observation()
    observation["environment"].update(CUDA_VISIBLE_DEVICES=UUID_0, SLURM_JOB_GPUS="", SLURM_STEP_GPUS="")
    observation["gpu_device_access"]["5"] = True  # Actual other-GPU access is unprotected.
    observation["runtime_environment"] = {key: value for key, value in protocol["compute"]["runtime_environment"].items()
                                           if key != "model"}
    observation["runtime_environment"]["default_dtype"] = "torch.float32"
    observation["gpu_processes"] = [{"uuid": UUID_0, "pid": 77, "uid": 3938,
                                       "cgroup": "0::/slurm/uid_3938/job_123/step_batch\n"}]
    return case, observation


def live(shared, monkeypatch):
    case, observation = shared
    monkeypatch.setattr(gate, "_live_configuration_paths", lambda *args: [])
    def capture(*, include_processes=False):
        assert include_processes is True
        return deepcopy(observation)
    monkeypatch.setattr(gate, "_capture_local_observation", capture)
    return gate.check_formal_gate(**case, live_allocation=True)


def test_shared_metadata_review_does_not_start_or_observe_gpu(shared, monkeypatch):
    monkeypatch.setattr(gate, "_capture_local_observation", lambda **kw: pytest.fail("Metadata cannot observe GPU"))
    report = gate.check_formal_gate(**shared[0])
    assert report.status == "REVIEW_ONLY" and not report.issues
    assert not report.may_start_formal_training and report.runtime_observation is None


def test_shared_live_status_preserves_unprotected_truth_and_actual_uuid(shared, monkeypatch):
    report = live(shared, monkeypatch)
    assert report.status == gate.SHARED_GPU_STATUS and not report.issues
    assert report.may_start_formal_training
    assert report.status != "PASS_LIVE_ALLOCATION"
    assert report.runtime_observation["gpu_protection_verified"] is False
    assert report.runtime_observation["gpu_scheduler_reservation_verified"] is False
    assert report.runtime_observation["gpu_device_access"]["5"] is True
    assert report.runtime_observation["cuda_devices"][0]["uuid"] == UUID_0


@pytest.mark.parametrize("memory", ("12G", "12288M", "12288"))
def test_actual_site_without_memory_tres_uses_exact_live_min_memory_node(shared, monkeypatch, memory):
    case, _ = shared
    case["slurm_job_text"] = case["slurm_job_text"].replace(",mem=12G", "") + " MinMemoryNode=" + memory
    report = live(shared, monkeypatch)
    assert report.status == gate.SHARED_GPU_STATUS and report.may_start_formal_training


@pytest.mark.parametrize("tres,node_memory", (("", "4G"), ("", "invalid"), (",mem=8G", "12G"),
                                            (",mem=invalid", "12G"), (",mem=12G", "4G")))
def test_missing_invalid_or_conflicting_live_memory_cannot_be_overridden(shared, monkeypatch, tres, node_memory):
    case, _ = shared
    case["slurm_job_text"] = case["slurm_job_text"].replace(",mem=12G", tres) + " MinMemoryNode=" + node_memory
    report = live(shared, monkeypatch)
    assert "runtime.cpu_memory" in codes(report) and not report.may_start_formal_training


def test_same_unregistered_cluster_remains_blocked_without_explicit_exception(shared):
    shared[0]["protocol"]["compute"].pop("gpu_isolation_policy")
    shared[0]["protocol"]["content_sha256"] = gate.canonical_sha256(shared[0]["protocol"], omit_content_hash=True)
    report = gate.check_formal_gate(**shared[0])
    assert not report.may_start_formal_training
    assert {"slurm.no_gpu_gres", "slurm.no_task_cgroup", "slurm.node_gres", "site_config.devices"} <= codes(report)


@pytest.mark.parametrize("policy", ("ignore_all_gates", True, {}, 1))
def test_unknown_isolation_policy_is_rejected(shared, policy):
    shared[0]["protocol"]["compute"]["gpu_isolation_policy"] = policy
    shared[0]["protocol"]["content_sha256"] = gate.canonical_sha256(shared[0]["protocol"], omit_content_hash=True)
    assert "protocol.gpu_isolation_policy" in codes(gate.check_formal_gate(**shared[0]))


def test_exception_cannot_be_reused_as_full_or_downstream_authority(shared):
    shared[0]["protocol"]["execution_scope"] = "full"
    shared[0]["protocol"]["content_sha256"] = gate.canonical_sha256(shared[0]["protocol"], omit_content_hash=True)
    assert "protocol.gpu_isolation_scope" in codes(gate.check_formal_gate(**shared[0]))


@pytest.mark.parametrize("defect,expected", (
    ("owner", "runtime.owner"), ("cgroup", "runtime.cgroup"), ("state", "runtime.job_state"),
    ("cpu", "runtime.scientific_cpus"), ("memory", "runtime.cpu_memory"), ("time", "runtime.time_limit"),
    ("uuid", "runtime.cuda_devices"), ("device", "runtime.device_binding"), ("access", "runtime.device_access"),
    ("model", "runtime.gpu_model"), ("free", "runtime.free_memory"),
    ("environment", "runtime.scientific_environment"), ("stale", "runtime.stale_observation"),
    ("foreign_uid", "runtime.foreign_gpu_process"), ("foreign_job", "runtime.foreign_gpu_process"),
    ("missing_processes", "runtime.gpu_processes"), ("duplicate_pid", "runtime.gpu_processes"),
))
def test_shared_mode_retains_real_allocation_and_gpu_rejection_guards(shared, monkeypatch, defect, expected):
    case, obs = shared
    if defect == "owner": obs["uid"] = 99
    elif defect == "cgroup": obs["cgroup"] = "0::/user.slice\n"
    elif defect == "state": case["slurm_job_text"] = case["slurm_job_text"].replace("RUNNING", "PENDING")
    elif defect == "cpu": case["slurm_job_text"] = case["slurm_job_text"].replace("cpu=4", "cpu=2")
    elif defect == "memory": case["slurm_job_text"] = case["slurm_job_text"].replace("mem=12G", "mem=10G")
    elif defect == "time": case["slurm_job_text"] = case["slurm_job_text"].replace("02:00:00", "08:00:00")
    elif defect == "uuid": obs["environment"]["CUDA_VISIBLE_DEVICES"] = "0"
    elif defect == "device": obs["gpu_inventory"][0]["device_minor"] = 5
    elif defect == "access": obs["gpu_device_access"]["4"] = False
    elif defect == "model": obs["gpu_inventory"][0]["name"] = "NVIDIA GeForce RTX 5090"
    elif defect == "free": obs["gpu_inventory"][0]["memory_free_mib"] = 10
    elif defect == "environment": obs["runtime_environment"]["cuda"] = "other"
    elif defect == "stale": obs["captured_at"] = "2020-01-01T00:00:00+00:00"
    elif defect == "foreign_uid": obs["gpu_processes"][0]["uid"] = 99
    elif defect == "foreign_job": obs["gpu_processes"][0]["cgroup"] = "0::/slurm/job_456/step_batch\n"
    elif defect == "missing_processes": obs.pop("gpu_processes")
    else: obs["gpu_processes"].append(deepcopy(obs["gpu_processes"][0]))
    report = live(shared, monkeypatch)
    assert expected in codes(report) and not report.may_start_formal_training


@pytest.mark.parametrize("config,expected", (
    ("PreemptMode = SUSPEND", "slurm.preemption_unknown"),
    ("ProctrackType = proctrack/pgid", "slurm.no_process_cgroup"),
))
def test_shared_risk_does_not_waive_cpu_process_ownership_or_preemption(shared, config, expected):
    key = config.split(" = ")[0]
    lines = [line for line in shared[0]["slurm_config_text"].splitlines() if not line.startswith(key)]
    shared[0]["slurm_config_text"] = "\n".join(lines + [config]) + "\n"
    assert expected in codes(gate.check_formal_gate(**shared[0]))


@pytest.mark.parametrize("cvd", ("0", "GPU-aaaaaaaa", UUID_0 + "," + UUID_1, "-1"))
def test_shared_single_gpu_environment_requires_complete_one_uuid(shared, cvd):
    with pytest.raises(RuntimeError):
        single_gpu_environment(shared[0]["protocol"], {"SLURM_JOB_ID": "123", "CUDA_VISIBLE_DEVICES": cvd})


def test_shared_single_uuid_preserves_environment_without_fictitious_gres(shared):
    env = {"SLURM_JOB_ID": "123", "CUDA_VISIBLE_DEVICES": UUID_0, "SLURM_NTASKS": "1"}
    before = deepcopy(env)
    assert single_gpu_environment(shared[0]["protocol"], env) == UUID_0
    assert env == before and "SLURM_JOB_GPUS" not in env


def test_shared_named_status_without_live_policy_observation_cannot_start():
    assert not gate.GateReport(gate.SHARED_GPU_STATUS).may_start_formal_training
    assert not gate.GateReport(gate.SHARED_GPU_STATUS, runtime_observation={"gpu_protection_verified": True}).may_start_formal_training
