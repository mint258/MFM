"""Pure metadata catalog checks; the official locator document is the boundary."""
from __future__ import annotations

import re
from urllib.parse import urlsplit


SCOPE = "sb5_official_source_headers_v1"
CAP = 64 * 1024 ** 2
WALL = 900
NAMES = {"BACE", "BBBP", "ClinTox", "ESOL", "FreeSolv", "HIV", "Lipophilicity", "MUV", "PCBA",
         "PDBbind", "QM7", "QM7b", "QM8", "QM9", "SIDER", "Tox21", "ToxCast"}
HOSTS = {"deepchemdata.s3-us-west-1.amazonaws.com", "deepchemdata.s3.us-west-1.amazonaws.com",
         "dataverse.harvard.edu", "drive.google.com", "coconut.s3.uni-jena.de"}
HEADS = {"deepchem/deepchem": "455d07f3e17e880a4d980b5b0365e4a02b417e14",
         "mims-harvard/TDC": "c310c35f27e3f506411018ac43d97b8ba23ca652",
         "SXKDZ/MARCEL": "dae6b3b824b68d1362ed3b9fa23b34a45fa5366c",
         "Steinbeck-Lab/coconut": "6f1f6e45fe18d4868ca8653c1e3f111ecc68c202"}
LIMITS = {"method": "HEAD", "unique_candidate_urls": 30, "actual_worker_threads": 16,
          "network_concurrency": 4, "per_host_concurrency": 1, "max_redirects": 5,
          "connect_timeout_seconds": 8, "per_url_total_timeout_seconds": 20,
          "per_url_budget_includes_lease_waits_and_redirects": True,
          "timeout_overrun_observation_grace_seconds": 2, "absolute_child_wall_time_guaranteed": False,
          "force_terminate_child_allowed": False, "existing_proxy_environment_credentials_inherited": True,
          "max_curl_stdout_bytes": 256 * 1024, "max_curl_stderr_bytes": 32 * 1024,
          "max_persisted_header_field_characters": 1024,
          "payload_GET_allowed": False, "release_metadata_GET_allowed": False,
          "curlrc_disabled_for_no_implicit_auth": True, "normal_network_environment_inherited": True,
          "proxy_configuration_changed": False, "retries": 0,
          "block_further_same_host_after_HTTP429": True, "logical_source_inspection": "NOT_INSPECTED",
          "new_boundary_fixture_count": 5,
          "max_per_url_json_bytes": 128 * 1024, "max_logical_manifest_bytes": 128 * 1024,
          "max_final_receipt_bytes": 512 * 1024,
          "coverage_status": "PENDING", "physical_sha_or_count_proven": False,
          "pool_release_authorized": False, "decontamination_accepted": False}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def literal_https(url):
    need(type(url) is str and 0 < len(url) <= 16384 and not any(ord(c) < 33 or ord(c) == 127 for c in url),
         "LITERAL_HTTPS_URL_REQUIRED")
    value = urlsplit(url)
    need(value.scheme == "https" and value.hostname and value.username is None and value.password is None
         and value.port in (None, 443) and not value.fragment, "HTTPS_NO_URL_USERINFO_OR_ALTERNATE_PORT")
    return value


def validate_catalog(catalog, official_document):
    need(catalog.get("schema") == "SB5_OFFICIAL_SOURCE_HEAD_CATALOG_V1"
         and catalog.get("status") == "OFFICIAL_LOCATORS_ONLY_ALL_COVERAGE_PENDING"
         and catalog.get("source_document") == "docs/expansion/external_all_source_locators_v3.md", "EXACT_LOCATOR_CATALOG_REQUIRED")
    rows = catalog["probe_sources"]
    need(len(rows) == len({r["source_id"] for r in rows}) == len({r["url"] for r in rows}) == 30,
         "EXACT_30_UNIQUE_OFFICIAL_HEAD_LOCATORS")
    by_id = {r["source_id"]: r for r in rows}
    for row in rows:
        parsed = literal_https(row["url"])
        need(parsed.hostname in HOSTS and row["url"] in official_document and row["method"] == "HEAD",
             "URL_NOT_SUPPORTED_BY_PINNED_OFFICIAL_LOCATOR_DOCUMENT")
        need(row["coverage_status"] == "PENDING" and row["physical_sha256"] is None
             and row["record_count"] is None and row["logical_members_inspected"] is False, "NO_FABRICATED_FILE_OR_COVERAGE_PIN")
        evidence = row["official_text_reference"]
        need(evidence in official_document and any(evidence.startswith("https://github.com/" + repo + "/blob/" + commit + "/")
             and row["metadata_source_commit"] == commit for repo, commit in HEADS.items()), "EXACT_IMMUTABLE_OFFICIAL_TEXT_EVIDENCE")
        need(re.fullmatch(r"[a-z0-9_]+", row["source_id"]), "SAFE_SOURCE_ID_REQUIRED")
    tdc = catalog["tdc_admet"]
    endpoints = tdc["endpoint_names"]
    need(len(endpoints) == len(set(endpoints)) == 22 and all(name in official_document for name in endpoints),
         "PRESERVE_ALL_22_DOCUMENTED_TDC_ENDPOINTS")
    logical = tdc["logical_csv_sources"]
    need(len(logical) == 44 and {(r["endpoint"], r["role"]) for r in logical}
         == {(name, role) for name in endpoints for role in ("train_val", "test")}, "ALL_44_TDC_LOGICAL_CSVS_REQUIRED")
    for row in logical:
        need(row["archive_probe_source_id"] == "tdc_admet_group_zip" and row["inspection_status"] == "NOT_INSPECTED"
             and row["coverage_status"] == "PENDING" and row["expected_loader_path"]
             == "admet_group/" + row["endpoint"] + "/" + row["role"] + ".csv", "HEAD_ZIP_IS_NOT_A_MEMBER_INSPECTION")
    mn = catalog["moleculenet"]
    need(mn["proposed_union_preserved"] is True and set(mn["required_dataset_names"]) == NAMES
         and len(mn["logical_datasets"]) == 17 and {r["dataset"] for r in mn["logical_datasets"]} == NAMES,
         "PRESERVE_17_MOLECULENET_UNION")
    for row in mn["logical_datasets"] + catalog["marcel"]["logical_datasets"]:
        need(row["inspection_status"] == "NOT_INSPECTED" and row["coverage_status"] == "PENDING"
             and row["probe_source_ids"] and set(row["probe_source_ids"]) <= set(by_id), "LOGICAL_SCOPE_REMAINS_PENDING")
    need({r["dataset"] for r in catalog["marcel"]["logical_datasets"]} == {"Drugs75K", "Kraken"}, "BOTH_MARCEL_ARCHIVES_REQUIRED")
    coconut = catalog["coconut"]
    need(coconut["complete_active_inactive_required"] is True and coconut["release_pin"] is None
         and coconut["displayed_date_is_clock_template"] is True and coconut["csv_inactive_coverage"] == "PENDING"
         and coconut["inspection_status"] == "NOT_INSPECTED", "COCONUT_TEMPLATE_IS_NOT_A_RELEASE_PIN")
    mapped = {"tdc_admet_group_zip", *coconut["probe_source_ids"]}
    for row in mn["logical_datasets"] + catalog["marcel"]["logical_datasets"]:
        mapped.update(row["probe_source_ids"])
    need(mapped == set(by_id), "EVERY_PHYSICAL_HEAD_LOCATOR_MUST_HAVE_A_REQUIRED_LOGICAL_SCOPE")
    return rows


def parameters(catalog_pin):
    return {**LIMITS, "catalog_reference": catalog_pin, "tdc_logical_csv_count": 44,
            "moleculenet_required_dataset_count": 17, "marcel_required_dataset_count": 2,
            "coconut_active_inactive_required": True}
