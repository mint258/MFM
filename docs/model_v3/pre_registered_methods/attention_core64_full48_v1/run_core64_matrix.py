#!/usr/bin/env python3
"""Source-bound original48 numeric GPU check; no new resource monitor."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

HERE = Path(__file__).absolute().parent


def require(ok, message):
    if not ok:
        raise ValueError(message)


def ref(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), "Ordinary source/input required: "+str(path))
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def bound(expected):
    require(ref(expected["path"]) == expected, "Source/input raw bytes differ: "+expected["path"])
    return json.loads(Path(expected["path"]).read_bytes())


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(str(Path(path).parent), os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


GIT_EOL_METADATA = frozenset((
    "docs/model_v3/numeric_stability_v1_SOURCE_PINS.json",
    "docs/model_v3/numeric_stability_v1_VALIDATION_REQUEST.json",
))


def git_blob_digest(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+bytes([0])+raw).hexdigest()


def public_git_bytes(path, raw, *, normalize_crlf=False):
    if normalize_crlf:
        require(path in GIT_EOL_METADATA, "CRLF projection is forbidden for this path")
        require(raw.count(b"\r\n") > 0 and raw.count(b"\r") == raw.count(b"\r\n"),
                "Only the two registered complete CRLF metadata files may project")
        return raw.replace(b"\r\n", b"\n")
    return raw


def validate_git_leaf(path, raw, leaf):
    projection = path in GIT_EOL_METADATA
    blob = public_git_bytes(path, raw, normalize_crlf=projection)
    require(len(blob) == leaf["bytes"] and git_blob_digest(blob) == leaf["git_blob_sha"],
            "Candidate source differs from registered Git blob: "+path)
    return {"path": path, "working_bytes": len(raw), "working_sha256": hashlib.sha256(raw).hexdigest(),
            "Git_projection": "registered_metadata_CRLF_to_LF" if projection else "exact_raw",
            "registered_Git_bytes": len(blob), "registered_Git_blob_sha": git_blob_digest(blob)}


def verify_publication(request):
    from core64_publication import verify_publication as actual
    return actual(request)


def metadata_selfcheck():
    require(git_blob_digest(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391", "Git empty blob/NUL oracle differs")
    try:
        public_git_bytes("current/phychem_mfm/factory.py", b"a\r\n", normalize_crlf=True)
    except ValueError:
        pass
    else:
        raise ValueError("A non-allowlisted source unexpectedly permitted normalization")
    try:
        validate_git_leaf("current/phychem_mfm/factory.py", b"a\n", {"bytes": 2, "git_blob_sha": "0"*40})
    except ValueError:
        pass
    else:
        raise ValueError("Wrong registered blob hash unexpectedly accepted")
    return {"Git_NUL_empty_oracle": True, "nonallowlisted_projection_rejected": True, "wrong_blob_rejected": True}

def bootstrap(args):
    raw = args.request.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == args.request_sha256, "Exact preregistered request required")
    request = json.loads(raw)
    require(request["schema"] == "model_v3_core64_attention_diagnostic_complete48_GPU_request_v1"
        and request["mode"] == "compensated_fp32_v1" and request["attention_aggregation_mode"] == "centered_core64_diagnostic_v1" and len(set(request["expected_case_ids"])) == 48
        and request["expected_case_count"] == 48 and request["absolute_tolerance"] == 1e-5
        and request["relative_tolerance"] == 0
        and request["mixed_precision_diagnostic_only"] is True
        and request["formal_FP32_gate_satisfied"] is False
        and request["model_freeze_candidate"] is False, "Original complete48 diagnostic-only protocol required")
    require(os.environ.get("MODEL_V3_NUMERIC_GPU_REQUEST_SHA") == args.request_sha256
        and os.environ.get("MODEL_V3_EXPECTED_NODE") == request["node"] == socket.gethostname().split('.')[0]
        and os.environ.get("SLURM_JOB_ID", "").isdigit()
        and os.environ.get("CUDA_VISIBLE_DEVICES") == request["gpu_uuid"], "Actual assigned GPU job/environment required")
    require(request['test_file'] == str(HERE/'test_core64_matrix.py') and request['status'] == 'FINAL_BOUND_PUBLIC_CORE64_DIAGNOSTIC_REQUEST', 'Draft or wrong test entry refused')
    pins = bound({**ref(HERE/"source_pins_v1.json"), "sha256": os.environ["MODEL_V3_NUMERIC_GPU_LAUNCH_PINS_SHA"]})
    require(pins["schema"] == "model_v3_core64_attention_diagnostic_complete48_GPU_launch_source_pins_v1", "Frozen numeric launch scope required")
    sources = {leaf["path"]: leaf for leaf in request["source_refs"]+pins["files"]+pins["protected_dependencies"]}
    sources[str(HERE/"source_pins_v1.json")] = ref(HERE/"source_pins_v1.json")
    for leaf in sources.values():
        require(ref(leaf["path"]) == leaf, "Source drift before GPU validation")
    verify_publication(request)
    return request, sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--admit-only", action="store_true")
    args = parser.parse_args()
    request, sources = bootstrap(args)
    if args.admit_only:
        # The old package is imported only in this short-lived admission process.
        # The main model/pytest process keeps its single new-package namespace.
        source = request["UUID_admission_source"]
        require(ref(source["path"]) == source, "Frozen native CUuuid admission differs")
        spec = importlib.util.spec_from_file_location("numeric_frozen_actual_CUuuid_admission", source["path"])
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        observation = module.admit_runtime({"device": "cuda:0", "expected_node": request["node"], "gpu_uuid": request["gpu_uuid"]})
        save(args.output_root/"CUDA_UUID_ADMISSION.json", observation)
        return 0
    out = args.output_root.absolute()
    require(not out.exists(), "Fresh supervised numeric output required")
    out.mkdir()
    save(out/"sources_before.json", sources)
    save(out/"PUBLIC_GIT_DUAL_IDENTITY.json", {"rows": verify_publication(request), "selfcheck": metadata_selfcheck()})
    code, failure, after, counts, rows = None, None, None, None, []
    try:
        subprocess.run([sys.executable, "-B", str(Path(__file__).absolute()), "--request", str(args.request),
            "--request-sha256", args.request_sha256, "--output-root", str(out), "--admit-only"], check=True)
        root = Path(request["repository"])
        expected_path = str(root/"current")
        require(os.environ.get("PYTHONPATH", "").split(':')[0] == expected_path, "Single actual numeric package tree required")
        import phychem_mfm
        require(Path(phychem_mfm.__file__).resolve() == (root/"current/phychem_mfm/__init__.py").resolve(), "Foreign package origin")
        require(os.environ.get("MODEL_V3_NUMERIC_TEST_DEVICE") == "cuda:0"
            and os.environ.get("MODEL_V3_NUMERIC_TEST_MODE") == request["mode"]
            and os.environ.get("MODEL_V3_NUMERIC_TEST_THREADS") == "1"
            and os.environ.get("PYTEST_ADDOPTS") == "-o tmp_path_retention_policy=all", "Fixed full-matrix test environment required")
        os.environ['MODEL_V3_CENTERED_CAPTURE_MANIFEST'] = request['original_capture_manifest']['path']
        os.environ['MODEL_V3_CENTERED_CAPTURE_MANIFEST_SHA'] = request['original_capture_manifest']['sha256']
        os.environ['MODEL_V3_CENTERED_ATTENTION_MODE'] = request['attention_aggregation_mode']
        capture = bound(request['original_capture_manifest'])
        require(capture['job_id'] == '4521492' and capture['status'] == 'CAPTURE_COMPLETE', 'Original seeded parameter capture required')
        from tiny_core64_controls import run as tiny_controls
        save(out/'INLINE_TINY_CANDIDATE_CONTROLS.json', tiny_controls())
        import pytest
        argv = [request["test_file"], "-q", "-p", "no:cacheprovider", "--basetemp="+str(out/"cases"),
                "--junitxml="+str(out/"matrix.xml")]
        save(out/"PYTEST_ARGV.json", {"argv": argv, "public_commit": request["public_commit"], "full48": True})
        class PlainCaseDirectories:
            count = 0
            @pytest.fixture(name="tmp_path")
            def case_directory(self, tmp_path_factory):
                name = "numeric_case_%02d" % self.count
                self.count += 1
                return tmp_path_factory.mktemp(name, numbered=False)
        directories = PlainCaseDirectories()
        code = int(pytest.main(argv, plugins=[directories]))
        require(directories.count == 48, "All48 case directories must be fresh ordinary directories")
        counts = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
        for suite in ET.parse(out/"matrix.xml").getroot().iter("testsuite"):
            for key in counts: counts[key] += int(suite.attrib.get(key, 0))
        for path in sorted((out/"cases").rglob("*__numeric_case.json")):
            value = json.loads(path.read_bytes())
            require(value["numeric_mode"] == request["mode"], "Case used wrong numerical mode")
            require(value['attention_aggregation_mode'] == request['attention_aggregation_mode'] == 'centered_core64_diagnostic_v1', 'Actual case aggregation mode differs')
            measured = value["measured"]
            rows.append({"case_id": measured["case_id"], "passed": measured["passed"], "case_json": ref(path),
                "actual_terminal_output_artifact": measured["actual_terminal_output_artifact"]})
        require(len(rows) == len({r["case_id"] for r in rows}) == 48
            and {r["case_id"] for r in rows} == set(request["expected_case_ids"])
            and counts["tests"] == 48 and counts["errors"] == counts["skipped"] == 0,
            "Full48 model/measurement coverage incomplete; never treat as successful subset")
    except BaseException as error:
        failure = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
    finally:
        try:
            after = {path: ref(path) for path in sources}
            save(out/"sources_after.json", after)
            require(after == sources, "Candidate/launcher/source inputs changed during matrix")
        except BaseException as error:
            failure = {"earlier": failure, "source_after": {"type": type(error).__name__, "message": str(error)}}
        passed = failure is None and code == 0 and len(rows) == 48 and all(r["passed"] for r in rows)
        result = {"schema": "model_v3_core64_attention_diagnostic_complete48_GPU_result_v1", "status": "DIAGNOSTIC_CRITERION_PASS" if passed else "DIAGNOSTIC_CRITERION_FAIL",
            "failure": failure, "pytest_exit_code": code, "counts": counts, "cases": rows,
            "public_commit": request["public_commit"], "local_commit": request["local_commit"],
            "exact_shared_tree": request["exact_shared_tree"], "source_before_after_equal": after == sources,
            "actual_native_data_reads": 0, "attention_aggregation_mode": request["attention_aggregation_mode"], "full_FP64_encoder_forwards": 0,
            "actual_complete_mixed_core64_encoder_forwards": 4*len(rows),
            "ordinary_all_arithmetic_FP32_encoder_forwards": 0,
            "arithmetic_scope": "FP32_PARAMETERS_IO_WITH_FP64_ATTENTION_CORE_DIAGNOSTIC",
            "formal_FP32_gate_satisfied": False, "model_freeze_candidate": False, "scientific_adoption": False}
        save(out/"RESULT.json", result)
        if passed: save(out/"COMPLETE.json", {"schema": "model_v3_core64_attention_diagnostic_complete48_GPU_complete_v1", "result": ref(out/"RESULT.json")})
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
