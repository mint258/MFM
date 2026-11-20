"""Reconcile NMR test counts against the original Kwon 2020 release, no fitting."""
import argparse
import json
from pathlib import Path
import urllib.request
import zipfile

from .pprime_tmpfs_queue import capacity

SOURCE_COMMIT = "9e9db7706ed1b90b3b98018668beeba1372c0a05"
SOURCE_URL = ("https://raw.githubusercontent.com/seokhokang/nmr_mpnn/"
              + SOURCE_COMMIT + "/datasets.zip")


def describe_author_split(payload):
    from .nmr_graph_source import restricted_graph_load
    data = restricted_graph_load(payload)
    if not isinstance(data, dict) or "test_df" not in data:
        raise ValueError("Unexpected original Kwon split container")
    frame = data["test_df"]
    if "molecule_id" not in frame.columns:
        raise ValueError("Original author molecule identity is missing")
    ids = frame["molecule_id"]
    return dict(spectrum_records=len(frame), unique_original_molecule_ids=len(set(ids)),
                identity_basis="Original author test_df molecule_id; no graph canonicalization",
                target_values_checked=False)


def reconcile(source_counts, author_counts):
    result = {}
    for nucleus in ("13C", "1H"):
        source = source_counts[nucleus]
        author = author_counts[nucleus]
        result[nucleus] = dict(original_split_spectrum_records=source["records"],
            original_split_unique_source_molecule_ids=source["unique_original_molecules"],
            kwon_release_spectrum_records=author["spectrum_records"],
            kwon_release_unique_original_molecule_ids=author["unique_original_molecule_ids"],
            same_spectrum_record_count=source["records"] == author["spectrum_records"],
            same_unique_molecule_count=source["unique_original_molecules"] == author["unique_original_molecule_ids"])
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--quota-snapshot", required=True, type=Path)
    p.add_argument("--attempt", required=True)
    a = p.parse_args()
    def safe():
        capacity(a.root, a.quota_snapshot, needed=64 * 1024**2)
    safe()
    archive = a.root / "raw/NMRShiftDB2_Jonas2019/Kwon2020_datasets.zip"
    if not archive.exists():
        partial = archive.with_suffix(".zip.partial")
        if partial.exists():
            raise RuntimeError("Existing partial author archive retained; inspect before resuming")
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "benchmark-data-source/1"})
        with urllib.request.urlopen(request, timeout=90) as response, partial.open("xb") as stream:
            while True:
                chunk = response.read(1024**2)
                if not chunk:
                    break
                safe()
                stream.write(chunk)
        safe()
        partial.rename(archive)
    out = a.root / "directive19/NMR2018" / a.attempt
    safe()
    out.mkdir(exist_ok=False)
    # This source comparison is the sole NMR count check explicitly requested in directive19.
    # No target value, geometry or numerical prediction is compared.
    authors = {}
    with zipfile.ZipFile(archive) as outer:
        names = outer.namelist()
        for nucleus in ("13C", "1H"):
            candidates = [name for name in names if Path(name).name == "data_" + nucleus + ".pickle"]
            if len(candidates) != 1:
                raise ValueError("Original release test member missing/nonunique: " + nucleus + repr(names))
            safe()
            authors[nucleus] = describe_author_split(outer.read(candidates[0]))
            authors[nucleus]["original_archive_member"] = candidates[0]
    membership = a.root / "directive19/NMR2018/job_4536853/manifest.json"
    original = json.loads(membership.read_text())
    source_counts = {row["nucleus"]: dict(records=row["source_rows"],
                        unique_original_molecules=row["unique_molecule_ids"])
                     for row in original["counts"] if row["official_split"] == "test"}
    comparison = reconcile(source_counts, authors)
    result = dict(status="AUTHOR_RELEASE_TEST_COUNTS_EXTRACTED",
        test_count_comparison=comparison,
        all_test_spectrum_counts_match=all(row["same_spectrum_record_count"] for row in comparison.values()),
        all_test_unique_molecule_counts_match=all(row["same_unique_molecule_count"] for row in comparison.values()),
        source_commit=SOURCE_COMMIT, source_url=SOURCE_URL,
        original_archive=str(archive), author_test_counts=authors,
        original_membership_manifest=str(membership),
        numerical_targets_replayed=False, new_data_content_hashes=False,
        count_only_authority="docs/benchmark/USER_DIRECTIVE_20261119.md section2")
    safe()
    (out / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print("NMR_AUTHOR_COUNT_CLOSED", out / "manifest.json", authors, flush=True)


if __name__ == "__main__":
    main()
