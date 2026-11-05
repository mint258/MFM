"""Materialize a metadata-only label pilot plan; Root supplies owner/quota pins."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

from common import OWNER_KEYS, read_json, reference, write_json_new

CATALOG_SHA256 = "b5aed096ae0dc4c479a64b9b05e8709205911a0f9a474b71ae1490992ce28765"
VERIFICATION_SHA256 = "ce9b58e988f66f8a402dc93eeb050a8f7b55317cfe37db3c3b1f08dd7b2045e5"
LABEL_FAMILIES = {"pm7_neutral", "pm7_ions", "pm7_solvents", "xtb_singlepoint", "xtb_vipea",
    "xtb_vfukui", "xtb_alpb", "xtb_fod", "perturbed", "D20", "D3"}


def catalog_source_files(catalog, verification):
    if verification.get("status") not in {"PASS", "ACCEPTANCE_PASSED", "VERIFIED"}:
        # Actual accepted report uses status=PASS. Do not accept a generic
        # nonempty report as evidence that scientific files were verified.
        raise ValueError("CLOSED_READBACK_NOT_PASS:" + str(verification.get("status")))
    artifacts = {x["path"]:x for x in catalog["artifacts"]}
    if len(artifacts) != len(catalog["artifacts"]):
        raise ValueError("DUPLICATE_CATALOG_ARTIFACT")
    output=[]
    seen=set()
    for item in verification["files_verified"]:
        path=item["path"]
        source=artifacts.get(path)
        if source is None or any(item[key]!=source[key] for key in ("bytes","sha256")):
            raise ValueError("CATALOG_READBACK_SOURCE_IDENTITY_DIFFERS:"+path)
        if path in seen:
            raise ValueError("DUPLICATE_READBACK_SOURCE_PATH")
        seen.add(path)
        if Path(source["run_root"]) not in Path(path).parents:
            raise ValueError("SOURCE_OUTSIDE_CATALOG_RUN_ROOT")
        if item.get("family") not in LABEL_FAMILIES:
            continue
        jobs={int(hit[1]) for part in Path(path).parts if (hit:=re.fullmatch(r"job_(\d+)(?:_.*)?",part))}
        if jobs!={int(source["job_id"])} or item["family"]!=source["family"]:
            raise ValueError("CATALOG_SOURCE_JOB_OR_FAMILY_MAPPING_DIFFERS")
        groups=[int(hit[1]) for part in Path(path).parts if (hit:=re.fullmatch(r"group_(\d+)",part))]
        if groups!=[int(source["file_group"])]:
            raise ValueError("CATALOG_SOURCE_GROUP_MAPPING_DIFFERS")
        output.append({**item,"source_job_id":source["job_id"],"source_file_group":source["file_group"],
            "inherited_full_readback_verified":True})
    if not output:
        raise ValueError("NO_VERIFIED_LABEL_FAMILY_FILES")
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("catalog","verification","output-directory"):
        p.add_argument("--"+name,required=True)
    for name in ("record-manifest","registry","mask-rules","quota-receipt"):
        p.add_argument("--"+name)
    p.add_argument("--check-catalog-only",action="store_true")
    p.add_argument("--max-records",type=int,default=2000)
    p.add_argument("--max-output-gib",type=int,default=8)
    args=p.parse_args()
    if reference(args.catalog)["sha256"]!=CATALOG_SHA256 or reference(args.verification)["sha256"]!=VERIFICATION_SHA256:
        raise ValueError("ACCEPTED_WP5_METADATA_PIN_DIFFERS")
    if not 1<=args.max_records<=5000 or not 1<=args.max_output_gib<=32:
        raise ValueError("BOUNDED_PILOT_LIMITS_REQUIRED")
    catalog=read_json(args.catalog)
    verification=read_json(args.verification)
    files=catalog_source_files(catalog,verification)
    output=Path(args.output_directory).absolute()
    output.mkdir(parents=True,exist_ok=False)
    write_json_new(output/"source_files.json",files)
    if args.check_catalog_only:
        write_json_new(output/"projection_receipt.json",{"status":"CATALOG_METADATA_PROJECTION_VERIFIED",
            "catalog":reference(args.catalog),"verification":reference(args.verification),
            "source_files":reference(output/"source_files.json"),"projected_files":len(files),
            "scientific_source_file_bodies_read":False,"script":reference(__file__)})
        print("CATALOG_METADATA_PROJECTION_VERIFIED",len(files))
        return
    if not all((args.record_manifest,args.registry,args.mask_rules,args.quota_receipt)):
        raise ValueError("OWNER_REGISTRY_RULES_AND_QUOTA_REQUIRED_FOR_PLAN")
    population=Path(catalog["authority"]["population"])
    latest=Path(catalog["latest_molecules"])
    plan={"schema_version":"v1-label-pilot-plan.1","status":"PREPARED_NOT_SUBMITTED", "mode":"pilot",
        "workers":16,"max_records":args.max_records,"read_batch_records":16,"geometry_source":"pm7",
        "max_output_bytes":args.max_output_gib*1024**3,
        "sources":{"catalog":reference(args.catalog),"closed_verification":reference(args.verification),
            "record_manifest":reference(args.record_manifest),"registry":reference(args.registry),
            "mask_rules":reference(args.mask_rules),"source_files":reference(output/"source_files.json")},
        "canonical_provenance":{"identity_keys":list(OWNER_KEYS),"owner_state":"COMPLETE",
            "receipt_context_consistent":True,"export_published":True,
            "catalog":reference(args.catalog),
            "population":{"path":str(population),"bytes":population.stat().st_size,
                "sha256":catalog["authority"]["population_sha256"]},
            "latest_molecules":reference(latest)},
        "storage_budget":{"quota_receipt":reference(args.quota_receipt),"minimum_remaining_bytes":200_000_000_000,
            "total_declared_new_bytes":args.max_output_gib*1024**3+64*1024**2},
        "root_submission_required":True,"full_population_acceptance":False,
        "pilot_selection":"Root-provided canonical records, preferably complete molecules from one canonical owner job to bound projected source I/O"}
    write_json_new(output/"pilot_plan.json",plan)
    print("PREPARED_NOT_SUBMITTED",str(output/"pilot_plan.json"),"source_family_files",len(files))


if __name__=="__main__":
    main()
