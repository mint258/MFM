"""Project an exact, caller-declared actual-parent sacct union into delivery views.

Metadata only. Formal SCI parents (including explicitly registered supplemental
SCI retries) and acceptance parents stay in separate actual-cost ledgers.
"""
from __future__ import annotations
import argparse,ast,json,math,re,time
from pathlib import Path
from wp5_acceptance_catalog_v3 import ROOT,sha,publish
TERMINAL={"COMPLETED","FAILED","CANCELLED","NODE_FAIL","PREEMPTED","BOOT_FAIL","OUT_OF_MEMORY","TIMEOUT","DEADLINE","REVOKED"}
UNKNOWN={"","unknown","none","null","n/a","na","-","(null)"}

def ref(path):return {"path":str(path),"sha256":sha(path)}
def core_hours(rows):return sum(int(r["ElapsedRaw"])*int(r["AllocCPUS"])/3600 for r in rows.values())
def parent_id(value):
    job=str(value)
    if not re.fullmatch(r"[1-9][0-9]*",job):raise ValueError("ACTUAL_NUMERIC_PARENT_ID_REQUIRED")
    return job

def formal_rows(value):
    """Same job_id+node recognition as catalog3, rejecting duplicate IDs."""
    found={}
    def walk(item):
        if isinstance(item,dict):
            if item.get("job_id") is not None and item.get("node"):
                job=parent_id(item["job_id"])
                if job in found:raise ValueError("FORMAL_PARENT_ID_DUPLICATED")
                if item.get("user") not in (None,"zixiao"):raise ValueError("FORMAL_PARENT_USER_DIFFERS")
                found[job]=item
            for child in item.values():walk(child)
        elif isinstance(item,list):
            for child in item:walk(child)
    walk(value)
    if isinstance(value,dict) and "actual_job_count" in value and value["actual_job_count"]!=len(found):
        raise ValueError("DECLARED_FORMAL_JOBMAP_COUNT_DIFFERS")
    return found

def declared_parents(formal_doc,acceptance_doc,expected,baseline_doc=None):
    if isinstance(expected,bool) or not isinstance(expected,int) or expected<1:raise ValueError("POSITIVE_EXPECTED_FORMAL_PARENTS_REQUIRED")
    formal=formal_rows(formal_doc)
    if len(formal)!=expected:raise ValueError("EXACT_EXPECTED_FORMAL_PARENT_COUNT_REQUIRED")
    items=acceptance_doc["jobs"] if isinstance(acceptance_doc,dict) else acceptance_doc
    acceptance={}
    for entry in items:
        job=parent_id(entry["job_id"])
        if job in acceptance or job in formal:raise ValueError("ACCEPTANCE_PARENT_ID_DUPLICATED_OR_FORMAL")
        if entry.get("user") not in (None,"zixiao"):raise ValueError("ACCEPTANCE_PARENT_USER_DIFFERS")
        acceptance[job]=entry
    if not acceptance:raise ValueError("EXPLICIT_ACCEPTANCE_PARENTS_REQUIRED")
    baseline=None
    if baseline_doc is not None:
        baseline=formal_rows(baseline_doc)
        if not baseline or not set(baseline).issubset(formal):raise ValueError("EXACT_BASELINE_FORMAL_IDS_NOT_PRESERVED")
        for job,old in baseline.items():
            new=formal[job]
            if old["node"]!=new["node"] or old.get("user") is not None and old.get("user")!=new.get("user"):
                raise ValueError("BASELINE_FORMAL_PARENT_NODE_OR_USER_DIFFERS:"+job)
    return formal,acceptance,baseline

def actual_rows(raw,formal,acceptance):
    if raw.get("sacct_returncode")!=0:raise ValueError("FINAL_ACTUAL_SACCT_FAILED")
    fields=list(raw["fields"]);columns=["JobID" if f=="JobIDRaw" else f for f in fields]
    required={"JobID","User","State","Start","End","ElapsedRaw","AllocCPUS"}
    if len(set(columns))!=len(columns) or not required.issubset(columns):raise ValueError("FINAL_SOURCE_COLUMNS_REQUIRED")
    rows={};lines={}
    for line in raw["sacct_stdout"].splitlines(keepends=True):
        if not line.strip():continue
        values=[v.strip() for v in line.rstrip("\r\n").split("|")]
        if values[-1]=="":values.pop()
        if len(values)!=len(columns):raise ValueError("FINAL_SOURCE_ROW_WIDTH")
        row=dict(zip(columns,values));job=parent_id(row["JobID"])
        if any(row[field].casefold() in UNKNOWN for field in required):raise ValueError("FINAL_SOURCE_REQUIRED_VALUE_MISSING_OR_UNKNOWN:"+job)
        if job in rows or row["User"]!="zixiao":raise ValueError("FINAL_SOURCE_DUPLICATE_OR_USER_DIFFERS")
        if row["State"].split()[0].rstrip("+") not in TERMINAL:raise ValueError("FINAL_PARENT_NOT_TERMINAL:"+job)
        if min(int(row["AllocCPUS"]),int(row["ElapsedRaw"]))<0:raise ValueError("INVALID_ACTUAL_RESOURCE_ACCOUNTING")
        rows[job]=row;lines[job]=line
    if set(rows)!=set(formal)|set(acceptance):raise ValueError("EXACT_FINAL_FORMAL_PLUS_ACCEPTANCE_IDS_NOT_CLOSED")
    if "job_count" in raw and raw["job_count"]!=len(rows):raise ValueError("DECLARED_SOURCE_ACCOUNTING_COUNT_DIFFERS")
    return columns,rows,lines

def check_fixture(expected):
    ast.parse(Path(__file__).read_text())
    n=expected
    if n<2:raise ValueError("CHECK_FIXTURE_EXPECTED_COUNT_AT_LEAST_TWO")
    formal_doc={"actual_job_count":n,"jobs":[{"job_id":str(j),"node":"compute-0-13","user":"zixiao"} for j in range(1,n+1)]}
    baseline_doc={"actual_job_count":n-1,"jobs":formal_doc["jobs"][:-1]}
    acceptance_doc={"jobs":[{"job_id":str(n+1),"stage":"metadata_fixture","user":"zixiao"}]}
    formal,acceptance,baseline=declared_parents(formal_doc,acceptance_doc,n,baseline_doc)
    fields=["JobIDRaw","User","State","ExitCode","Start","End","ElapsedRaw","AllocCPUS"]
    lines=[str(j)+"|zixiao|COMPLETED|0:0|2026-10-16T00:00:00|2026-10-16T00:00:10|10|24|\n" for j in range(1,n+2)]
    raw={"sacct_returncode":0,"fields":fields,"sacct_stdout":"".join(lines),"job_count":n+1}
    columns,rows,original=actual_rows(raw,formal,acceptance)
    assert len(formal)==n and len(baseline)==n-1 and len(rows)==n+1 and "".join(original.values())==raw["sacct_stdout"]
    assert columns[0]=="JobID" and abs(core_hours(rows)-(n+1)*240/3600)<1e-8
    cases=[]
    def rejects(name,fn):
        try:fn()
        except (ValueError,KeyError,TypeError):cases.append(name);return
        raise AssertionError("FIXTURE_DID_NOT_REJECT:"+name)
    rejects("formal_count_missing",lambda:declared_parents({"jobs":formal_doc["jobs"][:-1]},acceptance_doc,n))
    rejects("formal_duplicate",lambda:declared_parents({"jobs":formal_doc["jobs"]+[formal_doc["jobs"][0]]},acceptance_doc,n))
    rejects("baseline_missing",lambda:declared_parents(formal_doc,acceptance_doc,n,{"jobs":[{"job_id":str(n+2),"node":"compute-0-13"}]}))
    rejects("formal_acceptance_overlap",lambda:declared_parents(formal_doc,{"jobs":[{"job_id":"1"}]},n))
    rejects("acceptance_duplicate",lambda:declared_parents(formal_doc,{"jobs":acceptance_doc["jobs"]*2},n))
    rejects("source_duplicate",lambda:actual_rows({**raw,"sacct_stdout":raw["sacct_stdout"]+lines[0]},formal,acceptance))
    rejects("source_missing",lambda:actual_rows({**raw,"sacct_stdout":"".join(lines[:-1])},formal,acceptance))
    rejects("unknown_end",lambda:actual_rows({**raw,"sacct_stdout":raw["sacct_stdout"].replace("2026-10-16T00:00:10","Unknown",1)},formal,acceptance))
    rejects("wrong_user",lambda:actual_rows({**raw,"sacct_stdout":raw["sacct_stdout"].replace("|zixiao|","|other|",1)},formal,acceptance))
    rejects("nonterminal",lambda:actual_rows({**raw,"sacct_stdout":raw["sacct_stdout"].replace("|COMPLETED|","|RUNNING|",1)},formal,acceptance))
    rejects("source_field_missing",lambda:actual_rows({**raw,"fields":[x for x in fields if x!="End"]},formal,acceptance))
    return {"status":"FINAL_COST_ENVELOPE_V2_METADATA_FIXTURE_PASS","expected_formal_parents":n,"baseline_formal_parents":n-1,
            "accepted_unique_union_parents":len(rows),"rejection_cases":cases,"raw_stdout_bytes_unchanged":True,
            "Slurm_queried":False,"SCI_opened":False,"queue_opened":False,"fixture_files_created":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--accounting",type=Path);p.add_argument("--quota-report",type=Path)
    p.add_argument("--formal-jobmap",type=Path,default=ROOT/"reports/wp5_acceptance_control_jobmap_actual541_v1.json")
    p.add_argument("--expected-formal-parents",type=int,required=True)
    p.add_argument("--baseline-formal-jobmap",type=Path)
    p.add_argument("--acceptance-jobmap",type=Path);p.add_argument("--out",type=Path);p.add_argument("--check",action="store_true");a=p.parse_args()
    if a.check:print(json.dumps(check_fixture(a.expected_formal_parents)));return
    if not all((a.accounting,a.quota_report,a.acceptance_jobmap,a.out)):p.error("actual accounting/quota/acceptance-jobmap/new out required")
    formal,acceptance,baseline=declared_parents(json.loads(a.formal_jobmap.read_text()),json.loads(a.acceptance_jobmap.read_text()),
        a.expected_formal_parents,json.loads(a.baseline_formal_jobmap.read_text()) if a.baseline_formal_jobmap else None)
    raw=json.loads(a.accounting.read_text());quota_doc=json.loads(a.quota_report.read_text())
    columns,rows,lines=actual_rows(raw,formal,acceptance)
    quota=quota_doc["quota_parsed"]
    for key in ("used_kib","remaining_bytes","files_reported"):
        if not isinstance(quota.get(key),(int,float)) or isinstance(quota[key],bool) or not math.isfinite(quota[key]) or quota[key]<0:
            raise ValueError("ACTUAL_EXACT_QUOTA_FIELD_REQUIRED:"+key)
    a.out.mkdir(parents=True,exist_ok=False)
    sources={"actual_union_accounting":ref(a.accounting),"actual_quota":ref(a.quota_report),
             "formal_jobmap":ref(a.formal_jobmap),"acceptance_jobmap":ref(a.acceptance_jobmap),"script":ref(__file__)}
    if a.baseline_formal_jobmap:sources["baseline_formal_jobmap"]=ref(a.baseline_formal_jobmap)
    formal_cost_rows={job:rows[job] for job in formal};acceptance_cost_rows={job:rows[job] for job in acceptance}
    scope={"expected_formal_parent_count":a.expected_formal_parents,"actual_formal_parent_count":len(formal),
           "baseline_subset_verified":baseline is not None,"baseline_formal_parent_count":len(baseline) if baseline is not None else None,
           "additional_formal_parent_ids":sorted(set(formal)-set(baseline),key=int) if baseline is not None else None,
           "additional_parent_scope":"Explicitly registered actual supplemental SCI parents remain formal SCI cost; acceptance parents remain separate."}
    envelope={"schema":"WP5_FINAL_FORMAL_ACCOUNTING_WITH_QUOTA_V2","status":"ACTUAL_FORMAL_PARENTS_TERMINAL_WITH_FINAL_QUOTA",
              "time":raw["time"],"normalization_created_epoch":time.time(),"job_count":len(formal),"formal_scope":scope,
              "sacct":{"returncode":raw["sacct_returncode"],"argv":["metadata-formal-parents-normalized-view","--format="+",".join(columns)],
                       "stdout":"".join(lines[job] for job in rows if job in formal),"stderr":raw["sacct_stderr"]},
              "quota_parsed":quota,"quota_observed_time":quota_doc["time"],"sources":sources,
              "normalization":{"JobIDRaw_alias":"JobID","formal_row_values_changed":False,"formal_source_row_bytes_changed":False,
                               "selection":"Exact caller-declared formal parent IDs from SHA-bound jobmap; acceptance parent rows remain in their separate ledger",
                               "argv_is_column_declaration_not_new_query":True},
              "formal_only_allocated_core_hours":core_hours(formal_cost_rows),"acceptance_job_costs_included":False,
              "Slurm_queried":False,"SCI_opened":False,"queue_opened":False}
    publish(a.out/"formal_parents_with_final_quota_v2.json",envelope)
    ledger={"schema":"WP5_FINAL_ACCEPTANCE_PARENT_COST_LEDGER_V2","status":"ALL_DECLARED_ACCEPTANCE_PARENTS_TERMINAL",
            "parent_count":len(acceptance),"actual_allocated_core_hours":core_hours(acceptance_cost_rows),
            "parents":[{**acceptance[job],"actual_sacct":row} for job,row in acceptance_cost_rows.items()],
            "sources":sources,"formal_population_counted":False,"Slurm_queried":False}
    publish(a.out/"acceptance_parent_cost_ledger_v2.json",ledger)
    combined={"schema":"WP5_FINAL_COMBINED_ACTUAL_PARENT_COST_V2","status":"DECLARED_ACTUAL_FORMAL_AND_ACCEPTANCE_PARENT_IDS_CLOSED",
              "formal_parent_count":len(formal),"acceptance_parent_count":len(acceptance),"unique_parent_count":len(rows),"formal_scope":scope,
              "formal_actual_allocated_core_hours":core_hours(formal_cost_rows),
              "acceptance_actual_allocated_core_hours":core_hours(acceptance_cost_rows),
              "combined_actual_allocated_core_hours":core_hours(rows),"actual_parent_ids":sorted(rows,key=int),
              "cost_definition":"Actual each parent AllocCPUS*ElapsedRaw/3600 exactly once, including failed formal attempts. No batch/extern duplication or predicted times.",
              "scope":"Only explicitly registered actual formal SCI parents (including supplemental SCI parents) plus declared final acceptance parents; no future/unregistered test costs are claimed.",
              "sources":sources,"Slurm_queried":False,"SCI_opened":False,"queue_opened":False}
    publish(a.out/"combined_actual_parent_cost_v2.json",combined)
    print(json.dumps({"out":str(a.out),"formal_cost":combined["formal_actual_allocated_core_hours"],
                      "acceptance_cost":combined["acceptance_actual_allocated_core_hours"],
                      "total_actual_cost":combined["combined_actual_allocated_core_hours"],"parents":len(rows),"formal_parents":len(formal)}))
if __name__=="__main__":main()
