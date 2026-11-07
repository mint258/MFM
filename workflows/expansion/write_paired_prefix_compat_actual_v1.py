"""Root-only small-metadata report; no scheduler, chemistry or large-body I/O."""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import socket


ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025")
SMALL_CAP = 2 * 1024 ** 2
SCOPE = "prefix_feature_paired_10000"
FORBIDDEN = ("repair_applied", "pool_modified", "released_candidate_pool_authorized",
             "decontamination_acceptance_authorized", "uff_or_D_family_export_authorized",
             "training_authorized", "full_source_screening_authorized")
ACCOUNT_BYTES = 79540
ACCOUNT_SHA = "fff49e0cf1da1fe699ebd5f93561b437d081ec3c142e1a8fde21a087431a15f1a"
AUDIT_SHA = "5170794837e3ae68824ab3400c91a20cd962758cdd929d3ddb717d3ce52bf33ff"


def require(ok, message):
    if not ok:
        raise ValueError(message)


class SmallEvidence:
    def __init__(self):
        self.pins = {}

    def read(self, path):
        path = Path(path)
        require(path.is_absolute() and ".." not in path.parts and path.is_file() and not path.is_symlink(), "Literal small regular input required")
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            require(before.st_size <= SMALL_CAP, "Never read a large data body on login: " + str(path))
            raw = stream.read(SMALL_CAP + 1)
            after = os.fstat(stream.fileno())
        frame = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
        require(len(raw) == before.st_size <= SMALL_CAP and frame(before) == frame(after), "Small evidence changed")
        pin = {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        require(str(path) not in self.pins or self.pins[str(path)] == pin, "Evidence changed between references")
        self.pins[str(path)] = pin
        return raw

    def ref(self, path):
        self.read(path)
        return self.pins[str(Path(path))]

    def load(self, path):
        return json.loads(self.read(path))

    def verify(self, pin):
        require(set(pin) == {"path", "bytes", "sha256"} and pin["bytes"] <= SMALL_CAP and self.ref(pin["path"]) == pin,
                "Exact small pin differs: " + str(pin.get("path")))


def write_new(path, raw):
    require(len(raw) <= 128 * 1024, "Bounded metadata output required")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def actual_round(evidence, root, suffix, job, tests, test_module):
    job_name = "dv1_paired_prefix_replay_cpu_" + suffix
    outer = root / "artifacts/expansion/diagnostics" / ("paired_prefix_cpu_" + suffix)
    receipt = evidence.load(outer / "candidate_evaluation/receipt.json")
    stages = evidence.load(outer / "stage_receipt.json")
    monitor = evidence.load(root / "artifacts/cpu_analysis_guards" / job_name / "closure.json")
    stdout_path = root / "control" / (job_name + "_" + job + ".out")
    stdout = evidence.read(stdout_path).decode().replace("\r\n", "\n")
    ok_lines = re.findall(r"^test_\S+ \(" + re.escape(test_module) + r"\.[^\n]+\) \.\.\. ok$", stdout, flags=re.MULTILINE)
    ran = re.search(r"\nRan " + str(tests) + r" tests in ([0-9.]+)s\n\nOK\n", stdout)
    require(len(ok_lines) == len(set(ok_lines)) == tests and ran is not None, "Actual fixture count/OK evidence is absent")
    intent_pin, plan_pin = receipt["root_submission"], receipt["plan"]
    for pin in (intent_pin, plan_pin, stages["stages_reference"]):
        evidence.verify(pin)
    intent = evidence.load(intent_pin["path"])
    request = intent["request"]
    require(receipt["schema"] == "pubchem_paired_prefix_candidate_receipt_v1" and
            receipt["job_id"] == monitor["job_id"] == job and receipt["node"] == "compute-0-17" and receipt["uid"] == 1278 and
            stages["schema"] == "FINITE_CPU_STAGE_SEQUENCE_V1" and stages["scope_key"] == monitor["scope_key"] == SCOPE and
            stages["root_preflight"] == monitor["intent_reference"] == intent_pin and
            len(stages["stages"]) == 2 and stages["stages"][0]["returncode"] == 0 and
            stages["stages"][0]["argv"] == ["/share/home/zixiao/.conda/envs/chemprop/bin/python", "-B", "-m", "unittest", test_module, "-v"] and
            request["scope_key"] == SCOPE and request["node"] == "compute-0-17" and request["cpus"] == 16 and
            request["memory_gib"] == 4 and request["wall_seconds"] == 3600 and request["partition"] == "cpu" and
            request["estimated_peak_output_bytes"] == 301989888 and monitor["command"] == request["execution_argv"] and
            stages["forced_signals_sent"] is False and stages["automatic_submission_or_retry"] is False and
            stages["failure"] is None and monitor["failure"] is None and
            monitor["first_denial"] is None and monitor["monitor_io_failure"] is None and monitor["signals_sent"] is False and
            monitor["monitor_thread_closed"] is True and monitor["durable_evidence_exported"] is True and monitor["samples"] == 9,
            "Actual finite scope/stages/monitor binding differs")
    stage_spec = evidence.load(stages["stages_reference"]["path"])
    require([(s["name"], s["argv"]) for s in stage_spec["stages"]] ==
            [(s["name"], s["argv"]) for s in stages["stages"]], "Executed stages differ from bound stage source")
    declared = {pin["path"]: pin for pin in request["source_references"]}
    require(declared.get(plan_pin["path"]) == plan_pin and declared.get(stages["stages_reference"]["path"]) == stages["stages_reference"],
            "Actual plan/stage source not declared in Root intent")
    for pin in monitor["evidence_exports"]:
        evidence.verify(pin)
    workers = receipt["actual_worker_records"]
    require(len(workers) == 16 and all(str(pid).isdecimal() and int(pid) > 0 and type(n) is int and n > 0 for pid, n in workers.items()) and
            sum(workers.values()) == 10000 and receipt["complete_input_and_historical_coverage"] is True and
            receipt["all753_confirmed_recovered"] is True and receipt["inputs_unchanged"] is True and
            receipt["legacy_success_aliases"] == 8198 and receipt["legacy_historical_full_feature_rows"] == 8197 and
            receipt["historical_duplicate_alias_full_features_were_not_stored"] is True and
            receipt["historical_feature_fields_inferred_from_old_trace"] is False and
            receipt["proposed_unreleased_feature_counts"] == {"aliases": 8951, "unique_full_keys": 8949} and
            receipt["common_scope_pending"] is True and receipt["complete_source"] is False and receipt["candidate_evaluated_only"] is True and
            receipt["rdkit"] == "2025.09.5" and receipt["heavy_atom_upper_bound"] is None and receipt["isotope_policy"] == "preserve" and
            all(receipt[k] is False for k in FORBIDDEN), "Coverage/inputs/policy or release gate differs")
    counts = receipt["counts"]
    require(counts["input_records"] == 10000 and counts["ORIGINAL_SUCCESS_ALIAS"] == counts["legacy_aliases_checked"] == 8198 and
            counts["historical_stored_rows_checked"] == 8197 and counts["legacy_alias_without_separate_stored_features"] == 1 and
            counts["ORIGINAL_FEATURE_ERROR"] == counts["classification:RECOVERED_CONFIRMED_GENERIC_RING_ORDER"] == 753 and
            counts["ORIGINAL_CHEMICAL_REJECTION"] == counts["classification:CHEMICAL_REJECTION_UNCHANGED"] == 1049 and
            sum(v for key, v in counts.items() if key.startswith("classification:")) == 10000, "Round conservation failed")
    return receipt, stages, monitor, intent, {"tests": tests, "elapsed_seconds": float(ran.group(1)),
                "stdout_reference": evidence.ref(stdout_path), "actual_ok_lines": ok_lines}


def generate(repository, run_root, reviewer):
    repo, root = Path(repository), Path(run_root)
    require(os.name == "posix" and os.getuid() == 1278 and socket.gethostname().split(".")[0] == "sonmi" and
            reviewer == "root" and root == ROOT and repo == root / "repository" and
            Path(__file__).absolute() == repo / "workflows/expansion/write_paired_prefix_compat_actual_v1.py",
            "Root must first integrate/review then personally generate small metadata report on sonmi")
    report_path = repo / "docs/expansion/paired_prefix_compat_actual_v1.md"
    proof_path = root / "artifacts/expansion/diagnostics/paired_prefix_compat_actual_v1.json"
    require(all(not p.exists() and not p.is_symlink() for p in (report_path, proof_path)), "Preserve existing reports; exclusive new outputs required")
    evidence = SmallEvidence()
    account_path = root / "control/owned_accounting_cpu_v14.json"
    account = evidence.load(account_path)
    require(evidence.ref(account_path) == {"path": str(account_path), "bytes": ACCOUNT_BYTES, "sha256": ACCOUNT_SHA} and
            account["schema"] == "DATA_V1_OWNED_ACCOUNTING_POINT_IN_TIME_V2" and account["query_returncode"] == 0,
            "Exact actual v14 accounting required; no old snapshot substitute")
    evidence.verify(account["raw_sacct_reference"])
    raw_parent_rows = [row for row in csv.DictReader(io.StringIO(evidence.read(account["raw_sacct_reference"]["path"]).decode()), delimiter="|")
                       if row["JobIDRaw"].isdecimal()]
    require(all(sum(row["JobIDRaw"] == job for row in raw_parent_rows) == 1 for job in ("4520593", "4520597")), "Unique raw sacct parents required")
    raw_parents = {row["JobIDRaw"]: row for row in raw_parent_rows}
    a, astage, amon, aintent, atests = actual_round(evidence, root, "v1", "4520593", 3, "workflows.expansion.test_candidate_prefix_replay_cpu_v2")
    b, bstage, bmon, bintent, btests = actual_round(evidence, root, "v2", "4520597", 4, "workflows.expansion.test_features_legacy_compatible_v2")
    require(a["status"] == "PAIRED_PREFIX_HAS_DRIFT_OR_UNRESOLVED_ERRORS_NOT_APPLIED" and astage["status"] == "STAGE_FAILED_NO_RETRY" and
            astage["stages"][1]["returncode"] == amon["child_returncode"] == 1 and
            amon["status"] == "TEST_NOT_ACCEPTED_MEMORY_OR_RUNTIME_FAILURE" and
            a["counts"]["classification:OLD_PASS_HAS_DRIFT"] == a["counts"]["records_with_mismatch"] == 320 and
            a["counts"]["classification:OLD_PASS_ALL_FIELDS_PRESERVED"] == 7878 and
            b["status"] == "PAIRED_PREFIX_CANDIDATE_EVALUATED_NOT_APPLIED" and bstage["status"] == "ALL_STAGES_COMPLETED" and
            bstage["stages"][1]["returncode"] == bmon["child_returncode"] == 0 and bmon["status"] == "COMPLETED_NO_MEMORY_DENIAL" and
            b["counts"]["classification:OLD_PASS_ALL_FIELDS_PRESERVED"] == 8198 and
            b["counts"].get("records_with_mismatch", 0) == b["counts"].get("classification:OLD_PASS_HAS_DRIFT", 0) == 0,
            "593STOP and597 actual complete scientific gate must both be preserved")
    old_failure = evidence.load(root / "artifacts/expansion/diagnostics/paired_prefix_cpu_v1/candidate_evaluation/failure.json")
    require(old_failure["status"] == "FAILED_PAIRED_PREFIX_NOT_APPLIED" and
            old_failure["error"] == "Pairing drift or unresolved failures retained; no repair/pool release" and
            old_failure["counts_so_far"] == a["counts"], "Preserved593 scientific gate failure differs")
    for key in ("raw_current_full_SHA_and_frame", "oldDB_current_full_SHA_and_frame", "original_rejections", "full_X_proof"):
        require(a[key] == b[key], "Original raw/old pool/fullX proof changed between rounds")
    audit_path = root / "control/paired_prefix_mismatch_audit_v1.json"
    audit = evidence.load(audit_path)
    require(evidence.ref(audit_path)["sha256"] == AUDIT_SHA and audit["status"] == "READONLY_CAUSE_AUDIT_NOT_ACCEPTANCE" and
            audit["receipt"] == evidence.ref(root / "artifacts/expansion/diagnostics/paired_prefix_cpu_v1/candidate_evaluation/receipt.json") and
            audit["database"] == a["paired_result_database"] and audit["results"]["paired_difference_keys"] == [["generic_ring_systems", 320]] and
            audit["results"]["historical_difference_keys"] == [] and
            audit["results"]["original_exception_types"] == [["KekulizeException", "FEATURE_FUNCTION", 753]], "Actual320-field audit changed")
    evidence.verify(audit["source_reference"])
    feature_proof = b["source_scope_proof"]
    require(feature_proof["status"] == "COMPOSITIONAL_OLD_SUCCESS_PASSTHROUGH_EXACT_RING_KEKULIZE_FALLBACK_V2" and
            feature_proof["strategy"] == "OLD_SUCCESS_PASSTHROUGH_EXACT_OLD_RING_KEKULIZE_ONLY" and
            feature_proof["nested_generic_fallback_proof"] == a["source_scope_proof"] and
            feature_proof["frozen_old_ring_site"]["sanitize_line"] == 70 and
            feature_proof["frozen_old_ring_site"]["traceback_code_object_identity_required"] is True and
            feature_proof["old_success_returns_original_result_object"] is True and feature_proof["other_exceptions_rethrown"] is True and
            feature_proof["wrapper_AST_equals_original_features_AST"] is False, "Honest compositional strategy proof differs")
    parents = []
    for job, state, exit_code, intent in (("4520593", "FAILED", "1:0", aintent), ("4520597", "COMPLETED", "0:0", bintent)):
        found = [row for row in account["actual_parents"] if row["JobIDRaw"] == job]
        require(len(found) == 1, "Unique actual parent required")
        row = found[0]
        require(all(row[k] == raw_parents[job][k] for k in ("JobIDRaw", "State", "ExitCode", "ElapsedRaw", "AllocCPUS", "NodeList", "Partition")) and
                row["State"] == state and row["ExitCode"] == exit_code and row["NodeList"] == "compute-0-17" and row["Partition"] == "cpu" and
                int(row["AllocCPUS"]) == 16 and int(row["ElapsedRaw"]) == 8 and
                row["allocated_core_seconds_observed"] == int(row["ElapsedRaw"]) * int(row["AllocCPUS"]) == 128,
                "Actual parent state/cost differs from raw sacct; steps must not replace parents")
        evidence.verify(row["receipt_reference"])
        submission = evidence.load(row["receipt_reference"]["path"])
        require(submission["job_id"] == job and submission["sbatch_returncode"] == 0 and submission["request"] == intent["request"],
                "Parent accounting/submission/intent chain differs")
        parents.append(row)
    evidence.ref(Path(__file__).absolute())
    input_references = list(evidence.pins.values())
    total = sum(row["allocated_core_seconds_observed"] for row in parents)
    observed = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    lines = ["# 10k 前缀兼容候选评估实际记录", "", "本报告仅汇总已完成任务的小型证据，未读取 raw 或 SQLite 正文，未重跑测试或科学计算。",
             "", "4520597 在 compute-0-17 以16CPU、4GiB完成；8198个旧成功CID的本轮全部特征保持原样，8197条历史完整特征一致；753条旧环片段异常全部恢复，1049条化学排除及顺序不变。输入共10000条，16个worker均实际处理记录。",
             "", "历史只有8197条完整去重特征和8198个alias；重复alias没有单独历史完整特征。本轮分别核对历史完整特征、alias身份和8198次独立legacy/candidate全字段比较，不从旧trace推造缺失字段。",
             "", "4520593 保留为FAILED/1:0：首次generic-first候选导致320条旧成功记录仅generic_ring_systems变化；原历史特征与旧代码重放零差异。Root只读审计确认753条原异常均为KekulizeException，具体radical/implicit-H机制未被宣称实证。",
             "", "兼容候选优先原样返回旧结果；仅精确KekulizeException且真实traceback命中已pin旧features代码对象的第70行sanitize才调用已验证fallback。其他异常重抛；证明为组合证明，不声称新wrapper的AST等于旧features。",
             "", f"新增兼容fixtures由4520597实际日志证明Ran 4 tests及OK，耗时{btests['elapsed_seconds']}秒；旧3项prefix fixtures沿用4520593实际PASS，未在597重跑。两轮原始raw/旧pool的完整SHA与前后stat证据一致。597监控9个样本、无memorydenial，持久证据导出完成。",
             "", "| 父任务 | 实际状态 | Exit | ElapsedRaw秒 | CPU | 分配核秒 |", "|---|---|---|---:|---:|---:|"]
    lines += ["| " + " | ".join(str(row[k]) for k in ("JobIDRaw", "State", "ExitCode", "ElapsedRaw", "AllocCPUS", "allocated_core_seconds_observed")) + " |" for row in parents]
    lines += ["", f"两次父任务合计{total}分配核秒（{total / 3600:.12f}核时）。成本取owned_accounting_cpu_v14实际父任务ElapsedRaw×AllocCPUS，包含593失败，不重复计steps；不是CPU利用率或receipt内部计时。",
              "", "新评估产物含8951个alias、8949个full key，保持未放行。repair_applied=false、pool_modified=false；COMMON_PENDING继续保留，未证明全来源去污染，未授权正式pool、UFF、QM、训练或全源筛选。593 STOP及原pool均保留。",
              "", "Compact proof（全部小证据path/bytes/SHA、实际父任务和日志引用）：`" + str(proof_path) + "`。", "", "报告生成时间：" + observed + "。", ""]
    write_new(report_path, "\n".join(lines).encode())
    proof = {"schema": "PAIRED_PREFIX_COMPAT_ACTUAL_METADATA_CLOSURE_V1", "status": "BOUNDED10000_COMPAT_CANDIDATE_ACTUAL_PASS_NOT_APPLIED",
             "observed_at": observed, "report": evidence.ref(report_path), "actual_parents": parents,
             "allocated_core_seconds": total, "allocated_core_hours": total / 3600, "steps_counted_in_cost": False,
             "original593STOP_preserved": True, "original320_drift_only_generic_ring_systems": True,
             "legacy_success_cids_preserved": 8198, "historical_complete_feature_rows_checked": 8197,
             "duplicate_alias_without_separate_historical_features": 1, "old_failures_recovered": 753,
             "unchanged_chemical_rejections": 1049, "input_records": 10000, "workers_per_round": 16,
             "fixtures_actual_stdout": {"4520593": atests, "4520597": btests}, "original_inputs_unchanged": True,
             "proposed_unreleased_counts": b["proposed_unreleased_feature_counts"], "common_scope_pending": True,
             "metadata_only": True, "large_bodies_read_hashed_or_stat_ed": False, "tests_or_science_rerun": False,
             "radical_mechanism_claimed_proven": False, "input_references": input_references,
             **{key: False for key in FORBIDDEN}}
    write_new(proof_path, (json.dumps(proof, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode())
    print(json.dumps({"status": "ACTUAL_BOUNDED_METADATA_REPORT_WRITTEN_NO_RELEASE", "report": evidence.ref(report_path),
                      "compact_proof": evidence.ref(proof_path), "allocated_core_seconds": total,
                      "repair_applied": False, "pool_modified": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--reviewer", required=True, choices=["root"])
    args = parser.parse_args()
    generate(args.repository, args.run_root, args.reviewer)


if __name__ == "__main__":
    main()
