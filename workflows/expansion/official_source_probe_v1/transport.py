"""Bounded direct HEAD commands using the inherited network environment.

No response body is requested. Raw header buffers stay in memory and are never
persisted; only allowlisted fields and credential-redacted URLs are exported.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
import re
import selectors
import subprocess
import threading
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from .catalog import LIMITS, literal_https, need


SAFE_HEADERS = {"content-length", "etag", "last-modified", "content-type", "content-disposition", "location"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_url(url):
    """Redact every query value, except the registered nonsecret usp=sharing."""
    value = literal_https(url)
    fields = [(key, val if key == "usp" and val == "sharing" else "REDACTED")
              for key, val in parse_qsl(value.query, keep_blank_values=True)]
    return {"url": urlunsplit((value.scheme, value.netloc, value.path, urlencode(fields), "")),
            "unredacted_url_sha256": digest(url.encode()), "query_values_redacted": fields != parse_qsl(value.query, keep_blank_values=True)}


def field_value(value):
    limit = LIMITS["max_persisted_header_field_characters"]
    return {"value": value[:limit], "truncated": len(value) > limit,
            "full_characters": len(value), "full_value_sha256": digest(value.encode("utf-8"))}


def parse_headers(raw, requested_url):
    """Keep allowed fields only, including proxy CONNECT/informational blocks."""
    need(len(raw) <= LIMITS["max_curl_stdout_bytes"], "HEAD_HEADER_BUFFER_LIMIT")
    blocks, current = [], None
    for line in raw.decode("iso-8859-1").splitlines():
        match = re.fullmatch(r"HTTP/(?:1\.[01]|2|3)\s+(\d{3})(?:\s+.*)?", line)
        if match:
            need(len(blocks) < 16, "TOO_MANY_INFORMATIONAL_OR_PROXY_HEADER_BLOCKS")
            current = {"http_status": int(match[1]), "headers": {}}
            blocks.append(current)
        elif current is not None and ":" in line and not line[:1].isspace():
            name, value = line.split(":", 1)
            name, value = name.lower(), value.strip()
            if name in SAFE_HEADERS:
                values = current["headers"].setdefault(name, [])
                need(len(values) < 16, "TOO_MANY_DUPLICATE_ALLOWED_HEADERS")
                if name == "location":
                    # The raw target is returned only in memory for the next HEAD.
                    target = urljoin(requested_url, value)
                    values.append({**safe_url(target), **field_value(safe_url(target)["url"])})
                    current.setdefault("_raw_locations", []).append(target)
                else:
                    values.append(field_value(value))
    need(blocks and all(100 <= b["http_status"] <= 599 for b in blocks), "NO_VALID_HTTP_HEAD_STATUS")
    last = blocks[-1]
    lengths = last["headers"].get("content-length", [])
    valid = bool(lengths) and all(not v["truncated"] and v["value"].isdecimal() for v in lengths)
    unique = {v["value"] for v in lengths} if valid else set()
    last["content_length_bytes"] = int(next(iter(unique))) if len(unique) == 1 else None
    last["content_length_state"] = "CONSISTENT_DECIMAL" if len(unique) == 1 else ("ABSENT" if not lengths else "INVALID_OR_AMBIGUOUS")
    locations = last.get("_raw_locations", [])
    next_url = locations[0] if len(set(locations)) == 1 else None
    need(len(set(locations)) <= 1, "AMBIGUOUS_REDIRECT_LOCATION")
    for block in blocks:
        block.pop("_raw_locations", None)
    return blocks, next_url


def curl_argv(url, remaining_seconds):
    literal_https(url)
    need(0 < remaining_seconds <= LIMITS["per_url_total_timeout_seconds"], "FINITE_HEAD_TIME_BUDGET")
    return ["curl", "--disable", "--silent", "--show-error", "--head", "--dump-header", "-",
            "--output", os.devnull, "--connect-timeout", str(min(LIMITS["connect_timeout_seconds"], remaining_seconds)),
            "--max-time", str(remaining_seconds), "--retry", "0", "--max-redirs", "0", "--proto", "=https", "--", url]


def bounded_capture(argv, seconds, *, stop=None, on_overrun=None):
    """Bound buffers, observe overrun and drain naturally; never send a signal."""
    started = time.monotonic()
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               shell=False)  # Inherit normal proxy/network configuration; never set env/proxy flags.
    selector = selectors.DefaultSelector()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    totals = {"stdout": 0, "stderr": 0}
    caps = {"stdout": LIMITS["max_curl_stdout_bytes"], "stderr": LIMITS["max_curl_stderr_bytes"]}
    overrun = False
    notice_failed = False
    try:
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        deadline = started + seconds + LIMITS["timeout_overrun_observation_grace_seconds"]
        while selector.get_map() or process.poll() is None:
            if not overrun and time.monotonic() > deadline and process.poll() is None:
                overrun = True
                if stop is not None:
                    stop.set()  # No new HEAD dispatch; already running children drain.
                if on_overrun is not None:
                    try:
                        on_overrun({"status": "CURL_TIMEOUT_OVERRUN_DRAINING_NATURALLY", "curl_pid": process.pid,
                            "curl_max_time_seconds": seconds, "observed_seconds": time.monotonic() - started,
                            "signals_sent": False, "new_dispatch_stopped": True,
                            "absolute_child_wall_time_guaranteed": False})
                    except Exception:
                        notice_failed = True  # Keep draining even if durable notice export failed.
            for key, _ in selector.select(.1):
                try:
                    block = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                name = key.data
                totals[name] += len(block)
                remaining = caps[name] - len(buffers[name])
                buffers[name].extend(block[:max(0, remaining)])
        process.wait()
    finally:
        process.wait()  # Natural exit only; Slurm's predeclared wall remains authoritative.
        selector.close()
        for stream in (process.stdout, process.stderr):
            stream.close()
    return {"returncode": process.returncode, "stdout": bytes(buffers["stdout"]), "stderr": bytes(buffers["stderr"]),
            "stdout_total_bytes": totals["stdout"], "stderr_total_bytes": totals["stderr"],
            "buffer_overflow": any(totals[n] > caps[n] for n in caps), "timeout_overrun": overrun,
            "overrun_notice_export_failed": notice_failed, "forced_signals_sent": False,
            "subprocess_wall_seconds_observed": time.monotonic() - started}


def error_metadata(raw):
    # Error strings may contain redirected URL tokens. Preserve a digest and a safe curl code only.
    match = re.search(rb"curl:\s*\((\d+)\)", raw)
    return {"stderr_prefix_sha256": digest(raw), "stderr_prefix_bytes": len(raw),
            "curl_error_number_from_stderr": int(match[1]) if match else None,
            "stderr_text_persisted": False}


def probe_url(row, *, capture=bounded_capture, blocked_hosts=None):
    started = time.monotonic()
    deadline = started + LIMITS["per_url_total_timeout_seconds"]
    target = row["url"]
    hops, seen = [], set()
    outcome = "HEAD_OBSERVED"
    for index in range(LIMITS["max_redirects"] + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            outcome = "PER_URL_TOTAL_TIMEOUT"
            break
        try:
            parsed = literal_https(target)
            if blocked_hosts is not None and parsed.hostname in blocked_hosts:
                hops.append({"request": safe_url(target), "request_dispatched": False,
                             "suppressed_reason": "SAME_HOST_HTTP429"})
                outcome = "NOT_REQUESTED_AFTER_SAME_HOST_HTTP429"
                break
            need(target not in seen, "REDIRECT_LOOP")
            seen.add(target)
            result = capture(curl_argv(target, remaining), remaining)
            hop = {"request": safe_url(target), "method": "HEAD", "curl_returncode": result["returncode"],
                   "timeout_overrun": result["timeout_overrun"], "forced_signals_sent": False,
                   "overrun_notice_export_failed": result.get("overrun_notice_export_failed", False),
                   "subprocess_wall_seconds_observed": result.get("subprocess_wall_seconds_observed"),
                   "error": error_metadata(result["stderr"]),
                   "stdout_bytes": result["stdout_total_bytes"], "stderr_bytes": result["stderr_total_bytes"],
                   "response_header_prefix_sha256": digest(result["stdout"]),
                   "raw_response_headers_persisted": False}
            hops.append(hop)
            if result.get("dispatch_suppressed_reason"):
                hop["request_dispatched"] = False
                hop["http_status"] = None
                outcome = result["dispatch_suppressed_reason"]
                break
            if result["buffer_overflow"]:
                outcome = "HEADER_OR_STDERR_BUFFER_LIMIT"
                break
            if result["stdout"]:
                hop["http_blocks"], next_url = parse_headers(result["stdout"], target)
                hop["http_status"] = hop["http_blocks"][-1]["http_status"]
            else:
                next_url = None
                hop["http_status"] = None
            if result["timeout_overrun"]:
                outcome = "CURL_TIMEOUT_OVERRUN_NATURALLY_DRAINED"
                break
            if result["returncode"] != 0:
                outcome = "CURL_TRANSPORT_FAILED"
                break
            status = hop["http_status"]
            if status in {301, 302, 303, 307, 308} and next_url is not None:
                if index == LIMITS["max_redirects"]:
                    outcome = "REDIRECT_LIMIT"
                    break
                # Only the server's actual Location is followed; no alternate path/domain search.
                target = next_url
                continue
            if status == 429:
                outcome = "HTTP429_NO_RETRY"
                if blocked_hosts is not None:
                    blocked_hosts.add(parsed.hostname)
            elif status is not None and status >= 400:
                outcome = "HTTP_ERROR_RETAINED_NO_RETRY"
            break
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            # Do not persist exception text: it can embed token-bearing URLs or headers.
            outcome = "HEAD_METADATA_PROTOCOL_OR_COMMAND_FAILED"
            safe_code = str(exc) if re.fullmatch(r"[A-Z0-9_]{1,120}", str(exc)) else None
            hops.append({"request": safe_url(target) if _safe_target(target) else None,
                         "exception_type": type(exc).__name__, "validation_code": safe_code, "exception_text_persisted": False})
            break
    last = next((h for h in reversed(hops) if "http_status" in h), {})
    return {"source_id": row["source_id"], "candidate": safe_url(row["url"]), "method": "HEAD", "outcome": outcome,
            "http_status": last.get("http_status"), "final_url": hops[-1].get("request") if hops else safe_url(row["url"]),
            "redirect_chain": hops, "seconds": time.monotonic() - started,
            "locator_semantics": row["locator_semantics"], "official_text_reference": row["official_text_reference"],
            "coverage_status": "PENDING", "logical_source_inspection": "NOT_INSPECTED",
            "physical_sha256": None, "record_count": None, "release_version_proven": False,
            "payload_bytes_requested": 0, "GET_requests": 0, "network_configuration_changed": False,
            "curlrc_disabled_implicit_parameters_not_used": True}


def _safe_target(target):
    try:
        literal_https(target)
        return True
    except ValueError:
        return False


def probe_many(rows, stop, checkpoint, *, capture=None, on_result=None, on_overrun=None):
    need(len(rows) >= 16, "SIXTEEN_NONEMPTY_HEAD_WORKERS_REQUIRED")
    barrier = threading.Barrier(16, timeout=15)
    network = threading.BoundedSemaphore(LIMITS["network_concurrency"])
    hosts = {urlsplit(row["url"]).hostname: threading.Lock() for row in rows}
    host_registry = threading.Lock()
    blocked_hosts = set()
    local = threading.local()

    def suppressed(reason):
        return {"returncode": None, "stdout": b"", "stderr": b"", "stdout_total_bytes": 0,
                "stderr_total_bytes": 0, "buffer_overflow": False, "timeout_overrun": False, "forced_signals_sent": False,
                "dispatch_suppressed_reason": reason}

    def leased_capture(argv, seconds):
        # One lease covers exactly one HEAD. Release both before following Location;
        # redirect A->B and B->A therefore cannot retain each other's host lease.
        deadline = time.monotonic() + seconds
        host = literal_https(argv[-1]).hostname
        with host_registry:
            host_lock = hosts.setdefault(host, threading.Lock())
        host_owned = network_owned = False
        try:
            for lock, label in ((host_lock, "host"), (network, "network")):
                while True:
                    checkpoint()
                    if stop.is_set():
                        raise RuntimeError("COOPERATIVE_STOP_BEFORE_NEXT_HEAD_LEASE")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return suppressed("PER_URL_TOTAL_TIMEOUT_BEFORE_HEAD_DISPATCH")
                    if lock.acquire(timeout=min(.1, remaining)):
                        if label == "host":
                            host_owned = True
                        else:
                            network_owned = True
                        break
            if host in blocked_hosts:
                return suppressed("NOT_REQUESTED_AFTER_SAME_HOST_HTTP429")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return suppressed("PER_URL_TOTAL_TIMEOUT_BEFORE_HEAD_DISPATCH")
            actual_argv = curl_argv(argv[-1], remaining)
            if capture is None:
                def notice(details):
                    if on_overrun is not None:
                        on_overrun({**details, "source_id": local.source_id, "request": safe_url(argv[-1])})
                result = bounded_capture(actual_argv, remaining, stop=stop, on_overrun=notice)
            else:
                result = capture(actual_argv, remaining)
            if result["timeout_overrun"]:
                stop.set()
            # No raw headers are retained. Rate-limit observation is serialized under
            # the actual responding host lease, before another URL may use that host.
            statuses = re.findall(rb"(?m)^HTTP/(?:1\.[01]|2|3)\s+(\d{3})(?:\s|$)", result["stdout"])
            if statuses and statuses[-1] == b"429":
                blocked_hosts.add(host)
            return result
        finally:
            if network_owned:
                network.release()
            if host_owned:
                host_lock.release()

    def worker(number):
        identity = {"worker": number, "thread_ident": threading.get_ident(), "native_thread_id": threading.get_native_id(),
                    "assigned_sources": len(rows[number::16]), "source_ids": []}
        results = []
        barrier.wait()
        for row in rows[number::16]:
            checkpoint()
            if stop.is_set():
                raise RuntimeError("COOPERATIVE_STOP_BEFORE_NEXT_HEAD")
            local.source_id = row["source_id"]
            result = probe_url(row, capture=leased_capture, blocked_hosts=blocked_hosts)
            if on_result is not None:
                on_result(result)  # Persist once immediately, before another logical URL.
            identity["source_ids"].append(row["source_id"])
            results.append(result)
        return identity, results

    with ThreadPoolExecutor(max_workers=16, thread_name_prefix="official-head") as pool:
        futures = [pool.submit(worker, i) for i in range(16)]
        outputs = [future.result() for future in futures]
    workers = [row[0] for row in outputs]
    results = [r for row in outputs for r in row[1]]
    need(len({w["native_thread_id"] for w in workers}) == 16 and all(w["assigned_sources"] > 0 for w in workers),
         "ACTUAL_SIXTEEN_NONEMPTY_THREADS_NOT_OBSERVED")
    need(len(results) == len(rows) and {r["source_id"] for r in results} == {r["source_id"] for r in rows},
         "EVERY_CANDIDATE_REQUIRES_ONE_OBSERVATION_OR_EXPLICIT_UNREQUESTED_RECORD")
    return workers, sorted(results, key=lambda r: r["source_id"])
