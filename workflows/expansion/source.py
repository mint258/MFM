"""Official direct PubChem source probe and strict resumable download.

Only this command performs network access. There are no mirrors/proxies or
automatic fallback protocols. Updating a changing snapshot requires a new pin.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import socket
import time
import urllib.parse
import urllib.request

from .common import check_quota, digest, dump_new, external_output, load, reference, require, require_compute

URL = "https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/CID-SMILES.gz"


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlsplit(newurl)
        require(u.scheme == "https" and u.hostname == "ftp.ncbi.nlm.nih.gov", "Nonofficial source redirect refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def opener():
    # Direct official access. Never acquire/use proxy credentials or a mirror.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), OfficialRedirect())


def probe(pin, client=None):
    require(pin["url"] == URL, "Only the reviewed official CID-SMILES URL is allowed")
    client = client or opener()
    with client.open(urllib.request.Request(URL, method="HEAD"), timeout=30) as response:
        require(response.status == 200, "STOP: official PubChem source unavailable")
        got = {"url": response.url, "content_length": int(response.headers["Content-Length"]),
               "last_modified": response.headers["Last-Modified"], "etag": response.headers.get("ETag")}
    require(got["url"] == URL, "Source URL changed")
    for key in ("content_length", "last_modified"):
        require(got[key] == pin[key], "PubChem snapshot changed: " + key)
    if pin.get("etag") is not None:
        require(got["etag"] == pin["etag"], "PubChem ETag changed")
    return got


def download(pin_path, target, quota_path, seconds=7200):
    require_compute()
    pin = load(pin_path)
    target = external_output(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    state_path = target.with_name(target.name + ".download.json")
    pin_ref = reference(pin_path)
    client = opener()
    observed = probe(pin, client)
    size = pin["content_length"]
    start = partial.stat().st_size if partial.exists() else 0
    require(0 <= start <= size, "Partial file size exceeds pinned source")
    check_quota(quota_path, size - start)
    if state_path.exists():
        state = load(state_path)
        require(state["pin"] == pin_ref, "Partial download belongs to another pin")
    else:
        require(start == 0, "Unowned partial download refused")
        dump_new(state_path, {"schema": "pubchem_download_v1", "pin": pin_ref, "head": observed,
                              "hostname": socket.gethostname(), "started_unix_seconds": time.time()})
    began = time.monotonic()
    if start < size:
        headers = {"Accept-Encoding": "identity"}
        if start:
            headers.update({"Range": f"bytes={start}-", "If-Range": pin.get("etag") or pin["last_modified"]})
        request = urllib.request.Request(URL, headers=headers)
        with client.open(request, timeout=30) as response:
            require(response.headers.get("Last-Modified") == pin["last_modified"], "GET snapshot changed")
            if start:
                require(response.status == 206, "Resume needs a real 206; never append a 200 response")
                expected = f"bytes {start}-{size - 1}/{size}"
                require(response.headers.get("Content-Range") == expected, "Resume byte range differs")
            else:
                require(response.status == 200, "Initial download needs HTTP 200")
            require(int(response.headers["Content-Length"]) == size - start, "GET length differs")
            with partial.open("ab" if start else "xb") as stream:
                total = start
                while True:
                    require(time.monotonic() - began <= seconds, "Download time budget reached; owned partial retained")
                    block = response.read(min(1 << 20, size - total + 1))
                    if not block:
                        break
                    total += len(block)
                    require(total <= size, "Source exceeded pinned size")
                    stream.write(block)
                stream.flush()
                os.fsync(stream.fileno())
        require(total == size, "Truncated download; partial retained for explicit resume")
    require(partial.stat().st_size == size, "Incomplete source file")
    probe(pin, client)
    got_sha = digest(partial)
    if pin.get("sha256"):
        require(got_sha == pin["sha256"], "Official source SHA256 differs")
    # Link publishes without overwriting even if a competing writer appears.
    os.link(partial, target)
    dump_new(str(target) + ".receipt.json", {"schema": "pubchem_download_complete_v1", "pin": pin_ref,
        "file": reference(target), "source_version": pin["last_modified"], "publication": "hardlink_to_owned_partial",
        "partial_retained": str(partial), "network_bypass_attempted": False})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("probe", "download"))
    p.add_argument("--pin", required=True, type=Path)
    p.add_argument("--receipt", type=Path)
    p.add_argument("--target", type=Path)
    p.add_argument("--quota-receipt", type=Path)
    a = p.parse_args()
    require_compute()
    if a.action == "probe":
        require(a.receipt is not None, "Probe receipt path required")
        dump_new(external_output(a.receipt), {"schema": "pubchem_head_pin_verified_v1", "pin": reference(a.pin), "head": probe(load(a.pin))})
    else:
        require(a.target is not None and a.quota_receipt is not None, "Download target and fresh quota receipt required")
        download(a.pin, a.target, a.quota_receipt)


if __name__ == "__main__":
    main()
