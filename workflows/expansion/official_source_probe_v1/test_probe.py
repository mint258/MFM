"""Five source-only boundaries: synthetic HEADs, no network/body/scheduler calls."""
from __future__ import annotations

import copy
import ast
import inspect
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from . import catalog, transport


def fake_result(raw):
    return {"returncode": 0, "stdout": raw, "stderr": b"", "stdout_total_bytes": len(raw), "stderr_total_bytes": 0,
            "buffer_overflow": False, "timeout_overrun": False, "forced_signals_sent": False}


def fake_row(number, host="example.test"):
    return {"source_id": "fixture_" + str(number), "url": "https://" + host + "/item/" + str(number),
            "locator_semantics": "SYNTHETIC_FIXTURE", "official_text_reference": "SYNTHETIC_NOT_AN_OFFICIAL_LOCATOR"}


class OfficialHeadBoundaries(unittest.TestCase):
    def test_catalog_has_all_44_17_and_30_without_claiming_any_inspected_member(self):
        repo = Path(__file__).resolve().parents[3]
        value = json.loads((repo / "configs/data_v1/expansion/official_source_head_catalog_v1.json").read_text(encoding="utf-8"))
        document = (repo / value["source_document"]).read_text(encoding="utf-8")
        self.assertEqual(len(catalog.validate_catalog(value, document)), 30)
        self.assertEqual(len(value["tdc_admet"]["logical_csv_sources"]), 44)
        self.assertTrue(all(r["inspection_status"] == "NOT_INSPECTED" for r in value["tdc_admet"]["logical_csv_sources"]))
        narrowed = copy.deepcopy(value)
        narrowed["moleculenet"]["logical_datasets"] = [r for r in narrowed["moleculenet"]["logical_datasets"] if r["dataset"] != "QM7b"]
        with self.assertRaisesRegex(ValueError, "PRESERVE_17"):
            catalog.validate_catalog(narrowed, document)

    def test_headers_discard_secrets_and_do_not_invent_content_length(self):
        raw = (b"HTTP/1.1 302 Found\r\nSet-Cookie: VERY_SECRET_COOKIE\r\nAuthorization: SECRET_AUTH\r\n"
               b"Proxy-Authenticate: SECRET_PROXY\r\nLocation: https://signed.example.test/blob?token=SECRET_TOKEN&key=SECRET_KEY\r\n\r\n")
        blocks, target = transport.parse_headers(raw, "https://example.test/source")
        self.assertIn("SECRET_TOKEN", target)  # Needed only in memory to issue the actual redirect HEAD.
        saved = json.dumps(blocks)
        for secret in ("VERY_SECRET_COOKIE", "SECRET_AUTH", "SECRET_PROXY", "SECRET_TOKEN", "SECRET_KEY"):
            self.assertNotIn(secret, saved)
        self.assertNotIn("set-cookie", saved)
        self.assertIsNone(blocks[-1]["content_length_bytes"])
        bad, _ = transport.parse_headers(b"HTTP/2 200\r\nContent-Length: 3\r\nContent-Length: 4\r\n\r\n", "https://example.test/x")
        self.assertEqual(bad[-1]["content_length_state"], "INVALID_OR_AMBIGUOUS")
        with self.assertRaisesRegex(ValueError, "NO_URL_USERINFO"):
            transport.safe_url("https://user:password@example.test/x")

    def test_each_redirect_is_head_only_and_normal_proxy_environment_is_not_overridden(self):
        calls = []
        configured_proxy = "http://fixture-user:FIXTURE_PROXY_SECRET@proxy.example.test:3128"

        def capture(argv, seconds):
            calls.append(argv)
            self.assertEqual(transport.os.environ["HTTPS_PROXY"], configured_proxy)
            self.assertLessEqual(seconds, 20)
            self.assertIn("--head", argv)
            for forbidden in ("--location", "--proxy", "--noproxy", "--insecure", "--user", "--netrc", "--request", "GET"):
                self.assertNotIn(forbidden, argv)
            if len(calls) == 1:
                return fake_result(b"HTTP/1.1 303 See Other\r\nLocation: https://next.example.test/x?signature=PRIVATE\r\n\r\n")
            return fake_result(b"HTTP/2 200\r\nContent-Length: 123\r\nETag: abc\r\nLast-Modified: yesterday\r\nContent-Type: text/csv\r\n\r\n")

        with patch.dict(transport.os.environ, {"HTTPS_PROXY": configured_proxy}):
            observed = transport.probe_url(fake_row(0), capture=capture)
        self.assertEqual(len(calls), 2)
        self.assertEqual(observed["http_status"], 200)
        self.assertEqual(observed["redirect_chain"][-1]["http_blocks"][-1]["content_length_bytes"], 123)
        self.assertEqual(observed["GET_requests"], 0)
        self.assertNotIn("PRIVATE", json.dumps(observed))
        self.assertNotIn("FIXTURE_PROXY_SECRET", json.dumps(observed))
        self.assertNotIn("FIXTURE_PROXY_SECRET", json.dumps(calls))
        self.assertIsNone(observed["physical_sha256"])
        # Source-level no-signal assertion covers all production paths, not only
        # the happy fake capture. Popen must also inherit, never rewrite env.
        tree = ast.parse(inspect.getsource(transport))
        calls_ast = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        self.assertFalse([node for node in calls_ast if isinstance(node.func, ast.Attribute)
                          and node.func.attr in {"kill", "terminate", "send_signal"}])
        popen = [node for node in calls_ast if isinstance(node.func, ast.Attribute) and node.func.attr == "Popen"]
        self.assertEqual(len(popen), 1)
        self.assertNotIn("env", {keyword.arg for keyword in popen[0].keywords})

    def test_sixteen_real_threads_release_each_hop_lease_and_obey_four_and_one(self):
        active = {"total": 0, "peak": 0, "hosts": {}}
        lock = threading.Lock()

        def capture(argv, _):
            host = urlsplit(argv[-1]).hostname
            with lock:
                active["total"] += 1
                active["peak"] = max(active["peak"], active["total"])
                active["hosts"][host] = active["hosts"].get(host, 0) + 1
                self.assertEqual(active["hosts"][host], 1)
                self.assertLessEqual(active["total"], 4)
            time.sleep(.002)
            with lock:
                active["total"] -= 1
                active["hosts"][host] -= 1
            # Two hosts redirect toward each other; no old host lease survives.
            if "/item/" in argv[-1]:
                target = "h" + str((int(host[1]) + 1) % 6) + ".example.test"
                return fake_result(("HTTP/2 302\r\nLocation: https://" + target + "/final\r\n\r\n").encode())
            return fake_result(b"HTTP/2 200\r\nContent-Length: 0\r\n\r\n")

        rows = [fake_row(i, "h" + str(i % 6) + ".example.test") for i in range(30)]
        callbacks = []
        workers, observations = transport.probe_many(rows, threading.Event(), lambda: None, capture=capture,
                                                    on_result=lambda row: callbacks.append(row["source_id"]))
        self.assertEqual(len({w["native_thread_id"] for w in workers}), 16)
        self.assertEqual(sum(w["assigned_sources"] for w in workers), 30)
        self.assertEqual(len(callbacks), len(set(callbacks)))
        self.assertEqual(set(callbacks), {r["source_id"] for r in observations})
        self.assertTrue(all(r["http_status"] == 200 for r in observations))
        self.assertEqual(active["total"], 0)

    def test_429_stops_same_host_and_missing_root_review_is_not_request_ready(self):
        calls = []

        def capture(argv, _):
            calls.append(argv)
            return fake_result(b"HTTP/2 429\r\nContent-Type: text/html\r\n\r\n")

        callbacks = []
        _, rows = transport.probe_many([fake_row(i) for i in range(30)], threading.Event(), lambda: None, capture=capture,
                                      on_result=lambda row: callbacks.append(row["source_id"]))
        self.assertEqual(len(calls), 1)
        self.assertEqual(sum(r["outcome"] == "HTTP429_NO_RETRY" for r in rows), 1)
        self.assertEqual(sum(r["outcome"] == "NOT_REQUESTED_AFTER_SAME_HOST_HTTP429" for r in rows), 29)
        self.assertEqual(len(callbacks), 30)
        self.assertEqual(len(set(callbacks)), 30)
        from workflows.data_v1_final.execution.queue_v3 import contract
        spec = {"schema": "ROOT_REVIEWED_QUEUED_STAGE_SPEC_V1", "kind": "analysis", "pilot": False,
                "scope_key": catalog.SCOPE, "scope_parameters": {}, "wall_seconds": 900, "estimated_peak_output_bytes": catalog.CAP}
        with self.assertRaisesRegex(ValueError, "EXPLICIT_SCOPE_MODE_REVIEW_AND_PARENT_REQUIRED"):
            contract.validate_scope_spec(spec, read_small=lambda _: self.fail("no invented future review may be opened"))


def run_boundaries():
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OfficialHeadBoundaries))
    catalog.need(result.wasSuccessful() and result.testsRun == 5, "FIVE_NEW_HEAD_BOUNDARIES_MUST_PASS")
    return {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
            "network_or_dataset_bodies_used": False}


if __name__ == "__main__":
    unittest.main()
