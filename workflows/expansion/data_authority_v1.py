"""Bind large data through small, exact Root-authorized compute receipts.

The login submission guard hashes only these small receipts. Dataset contents
are still fully hashed by consumers on the compute node, never by this guard.
"""
from pathlib import Path

from .common import load, require, verify


def file_stat(path):
    s = Path(path).stat()
    return {"device": s.st_dev, "inode": s.st_ino, "size": s.st_size, "mtime_ns": s.st_mtime_ns, "uid": s.st_uid}


def projected(ref):
    return {k: ref[k] for k in ("path", "bytes", "sha256")}


def authorize_data(plan, submission, refs, *, node="compute-0-20"):
    small = {r["path"]: projected(r) for r in submission["request"]["source_references"]}
    data = {r["path"]: projected(r) for r in submission["request"].get("data_references", [])}
    tickets = plan.get("data_authorization_receipts", [])
    if not tickets:
        require(plan.get("allow_small_fixture_legacy_authority") is True and
                all(r["bytes"] <= 32 * 1024 ** 2 and small.get(r["path"]) == projected(r) for r in refs),
                "Real data require an explicitly bound compute source-pin receipt; only opted-in <=32MiB fixtures may use legacy source references")
        return {"kind": "EXPLICIT_SMALL_FIXTURE_ONLY", "files": [{"reference": projected(r), "expected_stat": file_stat(r["path"])} for r in refs]}
    allowed_jobs = set(map(str, plan["authorized_data_pin_jobs"]))
    require(allowed_jobs and all(j.isdecimal() for j in allowed_jobs), "Exact authorized data-producer job IDs required")
    ledger = {}
    for ref in tickets:
        require(ref["bytes"] <= 8 * 1024 ** 2 and small.get(ref["path"]) == projected(ref), "Small authority receipt is not bound by Root source_references")
        receipt = load(verify(ref))
        job = str(receipt.get("job_id", ""))
        require(job in allowed_jobs, "Receipt belongs to an unreviewed data-producer job")
        if receipt.get("schema") == "DATA_V1_SOURCE_PIN_RECEIPT_V1":
            require(receipt["status"] == "ALL_BOUND_INPUTS_SHA_VERIFIED" and receipt["node"] == node, "Source-pin receipt is not complete on the execution node")
            for item in receipt["outputs"]:
                r = projected(item["reference"])
                require(item["before"] == item["after"], "Source changed during actual source-pin hash")
                after = item["after"]
                require(after["uid"] == 1278 and after["size"] == r["bytes"], "Source-pin owner/size differs")
                require(item["stable_file_identity"] == {"dev": after["device"], "ino": after["inode"], "mtime_ns": after["mtime_ns"]},
                        "Source-pin stable physical identity differs")
                ledger[r["path"]] = {"reference": r, "expected_stat": after, "authority": projected(ref), "producer_job_id": job}
        elif receipt.get("schema") == "pubchem_download_complete_v1":
            # Exact new raw producer, not a generic historical source ledger.
            require(receipt.get("acquisition_schema") == "pubchem_16_range_acquisition_v1" and
                    receipt.get("status") == "RAW_ACQUIRED_NO_CHEMICAL_SCREENING" and receipt.get("hostname") == node and
                    receipt.get("uid") == 1278 and receipt["gzip"]["gzip_read_to_eof_crc_validated"] is True and
                    len(receipt["parts"]) == 16 and all(p["status"] == "COMPLETE" for p in receipt["parts"]),
                    "Raw acquisition authority is not the exact completed sixteen-range producer")
            r = projected(receipt["file"])
            require(receipt["gzip"]["sha256"] == r["sha256"] and receipt["gzip"]["compressed_bytes"] == r["bytes"], "Raw producer whole-file proof differs")
            # This producer predates physical-stat receipt fields. Observe current
            # metadata on compute and require full body SHA + stable metadata in
            # the consumer, without inventing a historical inode observation.
            ledger[r["path"]] = {"reference": r, "expected_stat": file_stat(r["path"]), "authority": projected(ref),
                                 "producer_job_id": job, "stat_basis": "current_compute_observation_before_consumer_full_SHA"}
        else:
            raise ValueError("Unrecognized exact data authority receipt schema")
    selected = []
    for ref in refs:
        r = projected(ref)
        require(data.get(r["path"]) == r, "Actual data are not declared in request.data_references")
        require(r["path"] in ledger and ledger[r["path"]]["reference"] == r, "Data reference is absent from the authorized compute receipt")
        item = ledger[r["path"]]
        require(file_stat(r["path"]) == item["expected_stat"], "Current data stat differs from authorized source-pin after frame")
        selected.append(item)
    return {"kind": "SMALL_COMPUTE_RECEIPT_WITH_LARGE_DATA_REFERENCES", "files": selected, "receipt_refs": tickets}


def verify_authorized_data(authority):
    """Call only on compute: full hashes plus pre/post stable physical identity."""
    for item in authority["files"]:
        require(file_stat(item["reference"]["path"]) == item["expected_stat"], "Data identity changed before consumer hash")
        verify(item["reference"])
        require(file_stat(item["reference"]["path"]) == item["expected_stat"], "Data identity changed during consumer hash")


def verify_final_stats(authority):
    for item in authority["files"]:
        require(file_stat(item["reference"]["path"]) == item["expected_stat"], "Data identity changed during consumer execution")
