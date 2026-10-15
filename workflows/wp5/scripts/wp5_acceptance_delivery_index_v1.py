
"""Assemble a delivery reference index from already closed verification evidence.
No permanent SCI body is read, hashed again, rewritten, or declared newly verified.
"""
from __future__ import annotations
import argparse,ast,hashlib,json,os,time
from pathlib import Path
from wp5_acceptance_catalog import ROOT,publish,require_slurm
REQUIRED_SUPPLEMENTAL_ROLES={"population_closure","runtime_freeze","packing","daily_reports","account_file_count"}
def require(condition,message):
    if not condition:raise ValueError(message)
def sha256(data):return hashlib.sha256(data).hexdigest()
def read_metadata(path,expected=None):
    path=Path(path);require(path.suffix.lower() in {".json",".md",".txt",".csv",".sbatch",".py",".sh"},"METADATA_REFERENCE_ONLY:"+str(path))
    before=path.stat();require(before.st_size<=32*1024*1024,"SMALL_METADATA_REFERENCE_ONLY:"+str(path))
    data=path.read_bytes();after=path.stat()
    require((before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),"METADATA_CHANGED_DURING_READ")
    ref={"path":str(path),"sha256":sha256(data),"bytes":len(data),"verification_basis":"METADATA_BYTES_SHA_BOUND_ONLY"}
    if expected is not None:require(ref["sha256"]==expected,"METADATA_SHA_DIFFERS:"+str(path))
    return data,ref
def document(path,expected=None):
    raw,ref=read_metadata(path,expected);return json.loads(raw),ref
def artifact_key(row):return (str(row["path"]),row["sha256"],int(row["bytes"]))
def verified_artifacts(catalog,verification):
    require(catalog.get("status")=="CLOSED" and verification.get("status")=="PASS" and verification.get("latest_closed") is True,"CLOSED_CATALOG_AND_FULL_VERIFIER_PASS_REQUIRED")
    require(not verification.get("file_exceptions") and verification.get("serious_schema_issue_rows")==0,"FULL_VERIFIER_HAS_UNRESOLVED_FAILURES")
    declared={artifact_key(row):row for row in catalog["artifacts"]}
    verified={artifact_key(row):row for row in verification["files_verified"]}
    require(len(declared)==len(catalog["artifacts"]) and len(verified)==len(verification["files_verified"]),"DUPLICATE_ARTIFACT_PROOF")
    require(set(declared)==set(verified),"CATALOG_FULL_VERIFIER_ARTIFACT_SET_DIFFERS")
    return [{**declared[key],"verification_basis":"FINAL_FULL_VERIFIER_SHA_AND_READBACK",
             "permanent_body_reopened_by_index":False} for key in sorted(declared)]
def private_check():
    catalog={"status":"CLOSED","artifacts":[{"path":"private.parquet","bytes":8,"sha256":"a"*64}]}
    verification={"status":"PASS","latest_closed":True,"file_exceptions":[],"serious_schema_issue_rows":0,
                  "files_verified":[{"path":"private.parquet","bytes":8,"sha256":"a"*64}]}
    rows=verified_artifacts(catalog,verification);assert rows[0]["verification_basis"]=="FINAL_FULL_VERIFIER_SHA_AND_READBACK"
    changed={**verification,"files_verified":[{"path":"private.parquet","bytes":8,"sha256":"b"*64}]}
    try:verified_artifacts(catalog,changed);raise AssertionError("Unverified artifact accepted")
    except ValueError:pass
    try:verified_artifacts(catalog,{**verification,"status":"NOT_PASS"});raise AssertionError("Failed verifier accepted")
    except ValueError:pass
    print(json.dumps({"status":"DELIVERY_REFERENCE_INDEX_PRIVATE_RULES_PASS",
        "matching_full_verifier_proof_accepted":True,"unverified_or_failed_proof_rejected":True,
        "SCI_or_original_read":False,"QM_started":False}))
def main(args):
    require_slurm(args.workers)
    catalog,cat_ref=document(args.catalog);verification,verify_ref=document(args.verification)
    delivery,delivery_ref=document(args.delivery_summary);supplement,supplement_ref=document(args.supplemental_manifest)
    require(verification["bindings"]["catalog_sha256"]==cat_ref["sha256"],"VERIFIER_CATALOG_BINDING_DIFFERS")
    for name,ref in (("catalog",cat_ref),("verification",verify_ref)):
        actual=delivery["bindings"][name];require(actual["path"]==ref["path"] and actual["sha256"]==ref["sha256"],"DELIVERY_EVIDENCE_BINDING_DIFFERS:"+name)
    artifacts=verified_artifacts(catalog,verification)
    require(supplement.get("schema")=="WP5_FINAL_DELIVERY_INDEX_INPUTS_V1","SUPPLEMENTAL_INDEX_SCHEMA_DIFFERS")
    supplemental=[]
    for row in supplement.get("references",[]):
        require(isinstance(row.get("role"),str) and row["role"],"SUPPLEMENTAL_ROLE_REQUIRED")
        _,ref=read_metadata(row["path"],row["sha256"])
        supplemental.append({**ref,"role":row["role"],"note":row.get("note"),
             "scientific_readback_status":"NOT_REASSESSED_BY_METADATA_INDEX"})
    roles={row["role"] for row in supplemental}
    missing=sorted(REQUIRED_SUPPLEMENTAL_ROLES-roles)
    authority=catalog["authority"];population=[]
    for name in ("population","molecules"):
        population.append({"role":name,"path":authority[name],"sha256":authority[name+"_sha256"],
            "verification_basis":"CLOSED_CATALOG_AUTHORITY_SHA","body_reopened_by_index":False})
    jobmap,jobmap_ref=document(authority["jobmap"],authority["jobmap_sha256"])
    require(delivery["bindings"]["jobmap"]["sha256"]==jobmap_ref["sha256"],"DELIVERY_JOBMAP_DIFFERS")
    from wp5_acceptance_catalog import jobmap_rows
    actual_jobs=jobmap_rows(jobmap)
    dictionaries,dict_ref=document(args.dictionaries,verification["bindings"]["dictionaries_sha256"])
    dictionary_rows=dictionaries["dictionaries"]
    from wp5_acceptance_catalog import CALCS
    require(len(dictionary_rows)==12 and {row["calc_type"] for row in dictionary_rows}==set(CALCS),"EXACT_TWELVE_FROZEN_DICTIONARIES_REQUIRED")
    dict_index=[{**row,"verification_basis":"FINAL_VERIFIER_FROZEN_DICTIONARY_MANIFEST",
                 "body_reopened_by_index":False} for row in dictionary_rows]
    acceptance=[]
    for name in ("recompute","pilot","accounting"):
        row=delivery["bindings"][name];_,ref=read_metadata(row["path"],row["sha256"]);acceptance.append({**ref,"role":name})
    storage=[]
    for row in delivery.get("storage_evidence",[]):
        _,ref=read_metadata(row["path"],row["sha256"]);storage.append({**ref,"stage":row["stage"],"status":row["status"],"node":row.get("node")})
    out=args.out;require(out.is_absolute() and out.is_relative_to(ROOT/"acceptance"),"NEW_ACCEPTANCE_INDEX_OUTPUT_REQUIRED");out.mkdir(parents=True,exist_ok=False)
    index={"schema":"WP5_FINAL_DELIVERY_REFERENCE_INDEX_V1","status":"REFERENCE_INDEX_COMPLETE" if not missing else "REFERENCE_INDEX_INCOMPLETE",
      "created_epoch":time.time(),"science_acceptance_status":delivery["status"],
      "index_status_definition":"Reference coverage and SHA-bound evidence only; this index never turns REVIEW/DIFF/unknown into scientific PASS.",
      "catalog":cat_ref,"full_verification":verify_ref,"delivery_summary":delivery_ref,
      "population_authority":population,"permanent_artifacts":artifacts,
      "dictionaries_manifest":dict_ref,"zstd_dictionaries":dict_index,"formal_jobmap":jobmap_ref,"actual_formal_parent_jobs":len(actual_jobs),
      "acceptance_reports":acceptance,"storage_reports":storage,"supplemental_manifest":supplement_ref,
      "supplemental_metadata":supplemental,"missing_supplemental_roles":missing,
      "F64_permanent_storage":True,"Float32_exported":False,"LMDB_created":False,
      "SCI_bodies_reopened_or_rehashed":False,"original_data_written":False,"QM_started":False,
      "source":{"path":str(Path(__file__)),"sha256":sha256(Path(__file__).read_bytes())}}
    publish(out/"delivery_index.json",index)
    lines=["# WP5 最终交付索引","",
      "科学验收状态："+delivery["status"]+"；索引状态："+index["status"]+"。",
      "本索引复用最终全量验证的永久文件 SHA 与读回证据，不重新扫描科学内容。","",
      "| 交付项 | 路径 | SHA256/依据 |","|---|---|---|"]
    def add(role,row):lines.append("| "+str(role)+" | "+row["path"]+" | "+row["sha256"]+" |")
    for row in population:add(row["role"],row)
    for role,row in (("catalog",cat_ref),("全量读回/分布",verify_ref),("首页",delivery_ref),("job ID 对照",jobmap_ref),("12字典清单",dict_ref)):add(role,row)
    for row in acceptance+storage+supplemental:add(row.get("role",row.get("stage","metadata")),row)
    lines+=["","永久 Parquet/归档的逐文件 SHA、12 个字典引用均列在 delivery_index.json；保留全部历史 attempt。"]
    if missing:lines+=["","尚缺交付引用："+", ".join(missing)+"。"]
    (out/"DELIVERY_INDEX.md").write_text("\n".join(lines)+"\n")
    print(json.dumps({"status":index["status"],"science_acceptance_status":delivery["status"],"permanent_files":len(artifacts),
                      "formal_parent_jobs":len(actual_jobs),"missing_roles":missing,"out":str(out)}))
    if missing:raise SystemExit(2)
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--check",action="store_true")
    for name in ("catalog","verification","delivery-summary","dictionaries","supplemental-manifest","out"):parser.add_argument("--"+name,type=Path)
    parser.add_argument("--workers",type=int,default=24);args=parser.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());private_check()
    else:
        if any(getattr(args,name) is None for name in ("catalog","verification","delivery_summary","dictionaries","supplemental_manifest","out")):parser.error("All final evidence paths and a new --out are required")
        main(args)
