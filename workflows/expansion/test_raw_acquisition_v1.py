"""New raw-acquisition edge cases only; no network or old-suite repetition."""
import gzip
import hashlib
import io
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error

from . import download_raw_v1 as raw
from .common import reference
from .source import URL


class Response(io.BytesIO):
    status = 206
    url = URL
    def __init__(self, body, first, last, pin):
        super().__init__(body)
        self.headers = {"Content-Range": f"bytes {first}-{last}/{pin['content_length']}",
                        "Content-Length": str(last - first + 1), "Last-Modified": pin["last_modified"]}


class RawAcquisitionTests(unittest.TestCase):
    def pin(self, n):
        return {"url": URL, "content_length": n, "last_modified": "Sat, 24 Oct 2026 18:17:31 GMT"}

    def test_sixteen_ranges_cover_every_byte_once(self):
        spans = raw.ranges(1488715010)
        self.assertEqual(len(spans), 16)
        self.assertEqual(spans[0][0], 0)
        self.assertEqual(spans[-1][1], 1488715009)
        self.assertTrue(all(spans[i][1] + 1 == spans[i + 1][0] for i in range(15)))

    def test_bad_200_range_length_or_snapshot_are_rejected(self):
        pin = self.pin(100)
        for change in ("status", "range", "length", "time"):
            response = Response(b"12345", 10, 14, pin)
            if change == "status": response.status = 200
            if change == "range": response.headers["Content-Range"] = "bytes 0-4/100"
            if change == "length": response.headers["Content-Length"] = "100"
            if change == "time": response.headers["Last-Modified"] = "another snapshot"
            with self.assertRaises(ValueError): raw.validate_range(response, 10, 14, pin)

    def test_owned_partial_resumes_only_missing_range(self):
        pin = self.pin(16)
        with tempfile.TemporaryDirectory() as tmp:
            task = (pin, tmp, 0, 0, 15, time.monotonic() + 30)
            raw._NETWORK, raw._STOP = threading.Semaphore(1), threading.Event()
            requested = []
            class Client:
                def open(self, request, **kwargs):
                    requested.append(request.get_header("Range"))
                    return Response(b"abcdefghijklmnop", 0, 15, pin)
            with patch.object(raw, "opener", return_value=Client()):
                first = raw.download_part(task)
            self.assertEqual(first["status"], "COMPLETE")
            self.assertEqual(requested, ["bytes=0-15"])
            # Explicit owned-plan resume: retain the first four bytes, then append
            # a real 206 for bytes 4..15; no replacement of foreign/unowned files.
            (Path(tmp) / "part_00.partial").write_bytes(b"abcd")
            class ResumeClient:
                def open(self, request, **kwargs):
                    requested.append(request.get_header("Range"))
                    return Response(b"efghijklmnop", 4, 15, pin)
            with patch.object(raw, "opener", return_value=ResumeClient()):
                resumed = raw.download_part(task)
            self.assertEqual(resumed["status"], "COMPLETE")
            self.assertEqual(resumed["resumed_bytes"], 4)
            self.assertEqual(requested[-1], "bytes=4-15")
            self.assertEqual((Path(tmp) / "part_00.partial").read_bytes(), b"abcdefghijklmnop")

    def test_429_stops_new_requests_and_never_retries(self):
        pin = self.pin(16)
        with tempfile.TemporaryDirectory() as tmp:
            raw._NETWORK, raw._STOP = threading.Semaphore(1), threading.Event()
            calls = []
            class Client:
                def open(self, request, **kwargs):
                    calls.append(request.full_url)
                    raise urllib.error.HTTPError(URL, 429, "Too Many Requests", {}, None)
            with patch.object(raw, "opener", return_value=Client()):
                failed = raw.download_part((pin, tmp, 0, 0, 15, time.monotonic() + 30))
                prevented = raw.download_part((pin, tmp, 1, 0, 15, time.monotonic() + 30))
            self.assertEqual(failed["http_status"], 429)
            self.assertEqual(prevented["status"], "FAILED")
            self.assertEqual(len(calls), 1)

    def test_assembly_validates_whole_sha_and_actual_gzip_crc(self):
        payload = b"raw framing only\n" * 1000
        data = gzip.compress(payload, mtime=0)
        with tempfile.TemporaryDirectory() as tmp:
            parts = []
            for i, (first, last) in enumerate(raw.ranges(len(data))):
                p = Path(tmp) / f"p{i}"
                p.write_bytes(data[first:last + 1])
                parts.append({"file": reference(p)})
            checked = raw.assemble_and_crc(parts, Path(tmp) / "good.gz")
            self.assertEqual(checked["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(checked["uncompressed_bytes_read"], len(payload))
            # Corrupt the CRC trailer and bind the corrupted part to ensure the
            # gzip validator, rather than only a stale-source hash, detects it.
            crc_pos = len(data) - 8
            for index, (first, last) in enumerate(raw.ranges(len(data))):
                if first <= crc_pos <= last:
                    changed = Path(parts[index]["file"]["path"])
                    content = bytearray(changed.read_bytes()); content[crc_pos - first] ^= 1
                    changed.write_bytes(content); parts[index] = {"file": reference(changed)}
                    break
            with self.assertRaises((gzip.BadGzipFile, EOFError)):
                raw.assemble_and_crc(parts, Path(tmp) / "bad.gz")

    def test_stale_submission_snapshot_is_not_fresh_quota(self):
        stdout = "Disk quotas for user zixiao (uid 1278): \n/dev/sda1 1000 0 500000000 0 0 0\n"
        value = raw.quota_from_preflight({"quota": {"returncode": 0, "stdout": stdout}, "observed_unix_seconds": time.time() - 301})
        from .common import dump_new, check_quota
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "quota.json"
            dump_new(p, value)
            with self.assertRaises(ValueError): check_quota(p, raw.CAP)

    def test_actual_root_intent_resources_and_source_bindings(self):
        from copy import deepcopy
        source = {"path": "/reviewed/source.py", "bytes": 3, "sha256": "a" * 64}
        submission = {"uid": 1278, "request": {"node": "compute-0-20", "cpus": 16, "memory_gib": 4,
            "wall_seconds": 3600, "estimated_peak_output_bytes": raw.CAP,
            "root_review": {"status": "APPROVED", "reviewer": "root"}, "source_references": [source]}}
        self.assertTrue(raw.validate_root_submission(submission, [source]))
        for key, bad in (("node", "compute-0-6"), ("cpus", 1), ("memory_gib", 64), ("wall_seconds", 7200)):
            changed = deepcopy(submission); changed["request"][key] = bad
            with self.assertRaises(ValueError): raw.validate_root_submission(changed, [source])
        changed = deepcopy(submission); changed["request"]["source_references"][0]["sha256"] = "b" * 64
        with self.assertRaises(ValueError): raw.validate_root_submission(changed, [source])


if __name__ == "__main__":
    unittest.main()
