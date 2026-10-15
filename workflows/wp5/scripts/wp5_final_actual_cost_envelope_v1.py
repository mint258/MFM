"""Project a final actual sacct union and exact quota evidence into delivery views."""
from __future__ import annotations
import argparse,ast,json,time
from pathlib import Path
from wp5_acceptance_catalog_v3 import ROOT,sha,jobmap_rows,publish
TERMINAL={"COMPLETED","FAILED","CANCELLED","NODE_FAIL","PREEMPTED","BOOT_FAIL","OUT_OF_MEMORY","TIMEOUT","DEADLINE","REVOKED"}
def ref(path):return {"path":str(path),"sha256":sha(path)}
def core_hours(rows):return sum(int(r["ElapsedRaw"])*int(r["AllocCPUS"])/3600 for r in rows.values())
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--accounting",type=Path);p.add_argument("--quota-report",type=Path)
    p.add_argument("--formal-jobmap",type=Path,default=ROOT/"reports/wp5_acceptance_control_jobmap_actual541_v1.json")
    p.add_argument("--acceptance-jobmap",type=Path);p.add_argument("--out",type=Path);p.add_argument("--check",action="store_true");a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print("FINAL_COST_ENVELOPE_AST_PASS_NO_QUERY_NO_SCI");return
    if not all((a.accounting,a.quota_report,a.acceptance_jobmap,a.out)):p.error("actual accounting/quota/acceptance-jobmap/new out required")
    formal=jobmap_rows(json.loads(a.formal_jobmap.read_text()))
    declared=json.loads(a.acceptance_jobmap.read_text());items=declared["jobs"] if isinstance(declared,dict) else declared
    acceptance={}
    for entry in items:
        job=str(entry["job_id"])
        if job in acceptance or job in formal:raise ValueError("ACCEPTANCE_PARENT_ID_DUPLICATED_OR_FORMAL")
        acceptance[job]=entry
    if len(formal)!=541 or not acceptance:raise ValueError("EXACT541_FORMAL_PLUS_EXPLICIT_ACCEPTANCE_PARENTS_REQUIRED")
    raw=json.loads(a.accounting.read_text());quota_doc=json.loads(a.quota_report.read_text())
    if raw["sacct_returncode"]!=0:raise ValueError("FINAL_ACTUAL_SACCT_FAILED")
    fields=list(raw["fields"]);columns=["JobID" if f=="JobIDRaw" else f for f in fields]
    if len(set(columns))!=len(columns) or not {"JobID","User","State","Start","End","ElapsedRaw","AllocCPUS"}.issubset(columns):
        raise ValueError("FINAL_SOURCE_COLUMNS_REQUIRED")
    rows={};lines={}
    for line in raw["sacct_stdout"].splitlines(keepends=True):
        if not line.strip():continue
        values=[v.strip() for v in line.rstrip("\r\n").split("|")]
        if values[-1]=="":values.pop()
        if len(values)!=len(columns):raise ValueError("FINAL_SOURCE_ROW_WIDTH")
        row=dict(zip(columns,values));job=row["JobID"]
        if job in rows or row["User"]!="zixiao":raise ValueError("FINAL_SOURCE_DUPLICATE_OR_USER_DIFFERS")
        if row["State"].split()[0].rstrip("+") not in TERMINAL:raise ValueError("FINAL_PARENT_NOT_TERMINAL:"+job)
        if min(int(row["AllocCPUS"]),int(row["ElapsedRaw"]))<0:raise ValueError("INVALID_ACTUAL_RESOURCE_ACCOUNTING")
        rows[job]=row;lines[job]=line
    expected=set(formal)|set(acceptance)
    if set(rows)!=expected:raise ValueError("EXACT_FINAL_FORMAL_PLUS_ACCEPTANCE_IDS_NOT_CLOSED")
    quota=quota_doc["quota_parsed"]
    for key in ("used_kib","remaining_bytes","files_reported"):
        if not isinstance(quota.get(key),(int,float)) or isinstance(quota[key],bool) or quota[key]<0:
            raise ValueError("ACTUAL_EXACT_QUOTA_FIELD_REQUIRED:"+key)
    a.out.mkdir(parents=True,exist_ok=False)
    sources={"actual_union_accounting":ref(a.accounting),"actual_quota":ref(a.quota_report),
             "formal_jobmap":ref(a.formal_jobmap),"acceptance_jobmap":ref(a.acceptance_jobmap),"script":ref(__file__)}
    formal_rows={job:rows[job] for job in formal};acceptance_rows={job:rows[job] for job in acceptance}
    envelope={"schema":"WP5_FINAL_FORMAL_ACCOUNTING_WITH_QUOTA_V1","status":"ACTUAL541_FORMAL_TERMINAL_WITH_FINAL_QUOTA",
              "time":raw["time"],"normalization_created_epoch":time.time(),"job_count":541,
              "sacct":{"returncode":raw["sacct_returncode"],"argv":["metadata-formal541-normalized-view","--format="+",".join(columns)],
                       "stdout":"".join(lines[job] for job in rows if job in formal),"stderr":raw["sacct_stderr"]},
              "quota_parsed":quota,"quota_observed_time":quota_doc["time"],"sources":sources,
              "normalization":{"JobIDRaw_alias":"JobID","formal_row_values_changed":False,
                               "selection":"Exact541 formal parent IDs from SHA-bound jobmap; acceptance parent rows remain in their separate ledger",
                               "argv_is_column_declaration_not_new_query":True},
              "formal_only_allocated_core_hours":core_hours(formal_rows),"acceptance_job_costs_included":False,
              "Slurm_queried":False,"SCI_opened":False,"queue_opened":False}
    publish(a.out/"formal541_with_final_quota_v1.json",envelope)
    ledger={"schema":"WP5_FINAL_ACCEPTANCE_PARENT_COST_LEDGER_V1","status":"ALL_DECLARED_ACCEPTANCE_PARENTS_TERMINAL",
            "parent_count":len(acceptance),"actual_allocated_core_hours":core_hours(acceptance_rows),
            "parents":[{**acceptance[job],"actual_sacct":row} for job,row in acceptance_rows.items()],
            "sources":sources,"formal_population_counted":False,"Slurm_queried":False}
    publish(a.out/"acceptance_parent_cost_ledger_v1.json",ledger)
    combined={"schema":"WP5_FINAL_COMBINED_ACTUAL_PARENT_COST_V1","status":"DECLARED_ACTUAL_FORMAL_AND_ACCEPTANCE_PARENT_IDS_CLOSED",
              "formal_parent_count":541,"acceptance_parent_count":len(acceptance),"unique_parent_count":len(rows),
              "formal_actual_allocated_core_hours":core_hours(formal_rows),
              "acceptance_actual_allocated_core_hours":core_hours(acceptance_rows),
              "combined_actual_allocated_core_hours":core_hours(rows),"actual_parent_ids":sorted(rows,key=int),
              "cost_definition":"Actual each parent AllocCPUS*ElapsedRaw/3600 exactly once, including failed formal attempts. No batch/extern duplication or predicted times.",
              "scope":"Only explicitly registered actual541 formal plus declared final acceptance parents; no future/unregistered test costs are claimed.",
              "sources":sources,"Slurm_queried":False,"SCI_opened":False,"queue_opened":False}
    publish(a.out/"combined_actual_parent_cost_v1.json",combined)
    print(json.dumps({"out":str(a.out),"formal_cost":combined["formal_actual_allocated_core_hours"],
                      "acceptance_cost":combined["acceptance_actual_allocated_core_hours"],
                      "total_actual_cost":combined["combined_actual_allocated_core_hours"],"parents":len(rows)}))
if __name__=="__main__":main()
