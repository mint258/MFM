"""Lossless metadata view for delivery2; no Slurm query, SCI, or queue access."""
from __future__ import annotations
import argparse,ast,json,time
from pathlib import Path
from wp5_acceptance_catalog_v3 import ROOT,sha,jobmap_rows,publish
TERMINAL={"COMPLETED","FAILED","CANCELLED","NODE_FAIL","PREEMPTED","BOOT_FAIL","OUT_OF_MEMORY","TIMEOUT","DEADLINE","REVOKED"}

def normalize(source,jobmap,out):
    raw=json.loads(Path(source).read_text());jobs=jobmap_rows(json.loads(Path(jobmap).read_text()))
    if raw["sacct_returncode"]!=0:raise ValueError("ACTUAL_SOURCE_SACCT_QUERY_FAILED")
    fields=list(raw["fields"])
    if fields.count("JobIDRaw")!=1 or "JobID" in fields:raise ValueError("EXACT_JOBIDRAW_HEADER_REQUIRED")
    columns=["JobID" if name=="JobIDRaw" else name for name in fields]
    if not {"User","State","ElapsedRaw","AllocCPUS","Start","End"}.issubset(columns):
        raise ValueError("DELIVERY_ACCOUNTING_SOURCE_FIELDS_MISSING")
    rows={}
    for line in raw["sacct_stdout"].splitlines():
        if not line.strip():continue
        values=[value.strip() for value in line.split("|")]
        if values[-1]=="":values.pop()
        if len(values)!=len(columns):raise ValueError("SOURCE_ACCOUNTING_ROW_WIDTH_DIFFERS")
        row=dict(zip(columns,values));job=row["JobID"]
        if job in rows or job not in jobs or row["User"]!="zixiao":raise ValueError("SOURCE_JOB_ID_USER_OR_DUPLICATE")
        if row["State"].split()[0].rstrip("+") not in TERMINAL:raise ValueError("SOURCE_JOB_NOT_TERMINAL")
        if int(row["ElapsedRaw"])<0 or int(row["AllocCPUS"])<0:raise ValueError("NEGATIVE_ACCOUNTING_VALUE")
        rows[job]=row
    if raw.get("job_count")!=541 or len(rows)!=541 or set(rows)!=set(jobs):
        raise ValueError("EXACT541_REGISTERED_SOURCE_ROWS_REQUIRED")
    core=sum(int(row["ElapsedRaw"])*int(row["AllocCPUS"])/3600 for row in rows.values())
    doc={"schema":"WP5_FORMAL_ACCOUNTING_NORMALIZED_VIEW_V1",
         "status":"ACTUAL541_TERMINAL_ACCOUNTING_NORMALIZED","time":raw["time"],
         "normalization_created_epoch":time.time(),"job_count":len(rows),
         "raw_source":{"path":str(source),"sha256":sha(source)},
         "jobmap":{"path":str(jobmap),"sha256":sha(jobmap)},
         "original_fields":fields,"normalized_fields":columns,
         "normalization":{"column_alias":{"JobIDRaw":"JobID"},"row_values_changed":False,
                          "stdout_bytes_changed":False,"new_accounting_query_executed":False,
                          "argv_role":"Column declaration for normalized view, not an actual new sacct command"},
         "sacct":{"returncode":raw["sacct_returncode"],
                  "argv":["metadata-normalized-accounting-view","--format="+",".join(columns)],
                  "stdout":raw["sacct_stdout"],"stderr":raw["sacct_stderr"]},
         "formal_only_allocated_core_hours":core,
         "cost_scope":"Actual541 formal parent jobs only; final acceptance and random200 job costs are not included",
         "SCI_opened":False,"production_queue_opened":False,"Slurm_queried":False}
    if "quota_parsed" in raw:doc["quota_parsed"]=raw["quota_parsed"]
    publish(out,doc)
    print(json.dumps({"out":str(out),"sha256":sha(out),"jobs":len(rows),
                      "formal_only_allocated_core_hours":core,
                      "raw_stdout_unchanged":True,"acceptance_job_costs_included":False}))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path);p.add_argument("--jobmap",type=Path,default=ROOT/"reports/wp5_acceptance_control_jobmap_actual541_v1.json")
    p.add_argument("--out",type=Path);p.add_argument("--check",action="store_true");args=p.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());print("ACCOUNTING_VIEW_AST_PASS_NO_QUERY_NO_SCI");return
    if args.source is None or args.out is None:p.error("--source and independent --out required")
    if args.source.resolve()==args.out.resolve():raise ValueError("SOURCE_OVERWRITE_FORBIDDEN")
    if args.out.exists():raise ValueError("NEW_NORMALIZED_VIEW_REQUIRED")
    normalize(args.source,args.jobmap,args.out)
if __name__=="__main__":main()
