"""One producer pass over source CSVs: domain records and counts, no model results."""
import argparse
from collections import Counter
import csv
import json
import os
from pathlib import Path
import subprocess
import time
from rdkit import RDLogger
import pyarrow as pa
import pyarrow.parquet as pq
from .acquire import guard, quota_headroom
from .domain import assess

SCHEMA=pa.schema([
    ("dataset",pa.string()),("source_file",pa.string()),("source_row",pa.int64()),
    ("record_id",pa.string()),("original_smiles",pa.string()),("model_smiles",pa.string()),
    ("model_atom_to_source",pa.list_(pa.int32())),("heavy_atoms",pa.int32()),
    ("charge",pa.int32()),("salt_removed",pa.bool_()),("domain_eligible",pa.bool_()),
    ("retained",pa.bool_()),("blind_fallback_required",pa.bool_()),
    ("exclusion_reasons",pa.list_(pa.string())),("official_split",pa.string()),
    ("original_fields_json",pa.string())
])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--plan",required=True,type=Path)
    p.add_argument("--dataset",required=True)
    p.add_argument("--attempt",required=True)
    p.add_argument("--quota-snapshot",type=Path)
    a=p.parse_args()
    plan=json.loads(a.plan.read_text())
    source=plan["assets"][a.dataset]
    root=Path(plan["data_root"])
    inputs=[x for x in source["files"] if x["name"].lower().endswith(".csv")]
    if "domain_files" in source:
        requested=source["domain_files"]
        if len(requested)!=len(set(requested)) or set(requested)-{x["name"] for x in inputs}:
            raise ValueError("Invalid explicit domain source file selection")
        inputs=[x for x in inputs if x["name"] in requested]
    if not inputs:raise ValueError("No CSV adapter for this source group")
    snapshot=[None,None]
    forecast=sum(x["bytes"] for x in inputs)*12+67108864
    def protect():
        if snapshot[0] is None or time.monotonic()-snapshot[1]>60:
            if a.quota_snapshot:
                q=json.loads(a.quota_snapshot.read_text())
                age=time.time()-q["observed_epoch"]
                if (q["uid"]!=os.getuid() or q["returncode"]!=0
                        or not 0<=age<=90 or q["generation"]!="benchmarkB020261119"):
                    raise RuntimeError("quota publisher missing, stale or mismatched")
                snapshot[:]=[quota_headroom(q["raw"],os.getuid()),time.monotonic()]
            else:
                q=subprocess.check_output(["ssh","-n","-o","BatchMode=yes","-o","ConnectTimeout=10",
                    "sonmi","quota","-v","-u","zixiao"],text=True,timeout=60)
                snapshot[:]=[quota_headroom(q,os.getuid()),time.monotonic()]
        guard(root,forecast,snapshot[0],snapshot[1],114569896448)
    protect()
    out=root/"domain"/a.dataset/a.attempt
    out.mkdir(parents=True,exist_ok=False)
    adme=a.dataset in {"ExpansionRx","PharmaBench","ASAP_Polaris2025","Biogen_ADME","TDC_ADMET"}
    blind=bool(source.get("blind_no_filter",False))
    counts=[]
    buffer=[]
    RDLogger.DisableLog("rdApp.error")
    with pq.ParquetWriter(out/"all_rows.parquet",SCHEMA,compression="zstd") as sink:
        def flush():
            if buffer:
                protect()
                sink.write_table(pa.Table.from_pylist(buffer,schema=SCHEMA))
                buffer.clear()
        for asset in inputs:
            path=root/"raw"/a.dataset/asset["name"]
            total=eligible=retained=fallback=salts=0
            reasons=Counter()
            primary=Counter()
            with path.open(encoding="utf-8-sig",newline="") as stream:
                reader=csv.DictReader(stream)
                candidates=([source["smiles_column"]] if source.get("smiles_column") in reader.fieldnames
                            else [n for n in reader.fieldnames if n.lower().replace(" ","_") in
                                  {"smiles","canonical_smiles","chromophore_smiles"}])
                if len(candidates)!=1:
                    raise ValueError("Ambiguous/missing SMILES column: "+str(reader.fieldnames))
                smiles_column=candidates[0]
                for index,raw in enumerate(reader):
                    result=assess(raw[smiles_column],adme=adme,blind=blind,
                                  multiplicity=raw.get("multiplicity"))
                    total+=1;eligible+=result["domain_eligible"];retained+=result["retained"]
                    fallback+=result["blind_fallback_required"];salts+=result["salt_removed"]
                    reasons.update(result["reasons"])
                    if result["reasons"]:primary[result["reasons"][0]]+=1
                    split=raw.get(source["split_column"]) if source.get("split_column") else raw.get("split",raw.get("Split"))
                    if a.dataset=="ExpansionRx":
                        split="test_blinded" if "test_blinded" in asset["name"] else "train"
                    buffer.append({
                        "dataset":a.dataset,"source_file":asset["name"],"source_row":index,
                        "record_id":a.dataset+":"+asset["name"]+":"+str(index),
                        "original_smiles":result["original_smiles"],"model_smiles":result["model_smiles"],
                        "model_atom_to_source":result["model_atom_to_source"],
                        "heavy_atoms":result["heavy_atoms"],"charge":result["charge"],
                        "salt_removed":result["salt_removed"],"domain_eligible":result["domain_eligible"],
                        "retained":result["retained"],"blind_fallback_required":result["blind_fallback_required"],
                        "exclusion_reasons":result["reasons"],"official_split":split,
                        "original_fields_json":json.dumps(raw,ensure_ascii=False)
                    })
                    if len(buffer)>=4096:flush()
            counts.append({"source_file":asset["name"],"before":total,"domain_eligible":eligible,
                "retained":retained,"blind_fallback_required":fallback,"salts_removed":salts,
                "reason_counts_nonexclusive":dict(reasons),"primary_reason_counts":dict(primary)})
            print("DOMAIN_SOURCE_CLOSED",a.dataset,asset["name"],total,eligible,retained,flush=True)
        flush()
    protect()
    report={"status":"DOMAIN_COUNTS_COMPLETE","dataset":a.dataset,"counts":counts,
            "records":str(out/"all_rows.parquet"),"rdkit":"2025.09.5",
            "blind_no_filter":blind,"source_commit":source.get("source_commit"),
            "source_revisions":source.get("source_revisions"),
            "source_files_not_model_records":[x["name"] for x in source["files"]
                if x["name"].lower().endswith(".csv") and x not in inputs],
            "label_or_conformation_ready":False,"independent_readback":False,
            "protonation_policy":"preserve source; net charge0, no neutralization",
            "atom_map_definition":"model SMILES parser atom order (removeHs=False) to original source SMILES parser order"}
    (out/"manifest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    with (out/"counts.csv").open("w",newline="") as stream:
        fieldnames=["source_file","before","domain_eligible","retained","blind_fallback_required","salts_removed"]
        table=csv.DictWriter(stream,fieldnames=fieldnames)
        table.writeheader()
        table.writerows({k:r[k] for k in fieldnames} for r in counts)
    print("DOMAIN_MANIFEST",out/"manifest.json",flush=True)

if __name__=="__main__":main()
