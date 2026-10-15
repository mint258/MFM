"""Assemble WP5 acceptance delivery first page from closed evidence. No QM."""
from __future__ import annotations
import argparse,ast,json,datetime,os
from pathlib import Path
from wp5_acceptance_catalog import ROOT,CALCS,sha,publish,require_slurm,jobmap_rows
def query_columns(argv):
    for index,value in enumerate(argv):
        if value.startswith("--format="):return value.split("=",1)[1].split(",")
        if value=="--format":return argv[index+1].split(",")
    raise ValueError("ACCOUNTING_FORMAT_NOT_DECLARED")
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("catalog","verification","recompute","pilot","jobmap","accounting"):p.add_argument("--"+name,type=Path)
    p.add_argument("--storage-reports",type=Path,nargs="*");p.add_argument("--out",type=Path);p.add_argument("--workers",type=int,default=24);p.add_argument("--check",action="store_true");a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print("ACCEPTANCE_DELIVERY_AST_PASS_NO_QM");return
    require_slurm(a.workers)
    if any(getattr(a,name) is None for name in ("catalog","verification","recompute","pilot","jobmap","accounting")):raise ValueError("All six evidence paths required")
    out=a.out or ROOT/"acceptance"/("delivery_"+os.environ["SLURM_JOB_ID"]);out.mkdir(parents=True,exist_ok=False)
    catalog=json.loads(a.catalog.read_text());verify=json.loads(a.verification.read_text());recompute=json.loads(a.recompute.read_text());pilot=json.loads(a.pilot.read_text())
    observation=json.loads(a.accounting.read_text());jobs=jobmap_rows(json.loads(a.jobmap.read_text()));actual=observation["sacct"]
    if actual["returncode"]!=0:raise ValueError("ACTUAL_ACCOUNTING_QUERY_FAILED")
    columns=query_columns(actual["argv"]);records={}
    for line in actual["stdout"].splitlines():
        values=[value.strip() for value in line.split("|")]
        if values and values[-1]=="":values.pop()
        if len(values)!=len(columns):raise ValueError("ACTUAL_ACCOUNTING_ROW_WIDTH")
        row=dict(zip(columns,values));job=row["JobID"]
        if job not in jobs:continue
        if row["User"]!="zixiao" or job in records:raise ValueError("ACTUAL_JOB_USER_OR_DUPLICATE")
        records[job]=row
    missing=sorted(set(jobs)-records.keys());core_hours=None
    if not missing:
        try:core_hours=sum(int(row["ElapsedRaw"])*int(row["AllocCPUS"])/3600 for row in records.values())
        except (KeyError,ValueError):pass
    span=None;wall_reason=None
    try:
        starts=[datetime.datetime.fromisoformat(row["Start"]) for row in records.values()]
        ends=[datetime.datetime.fromisoformat(row["End"]) for row in records.values()]
        if missing:raise ValueError("Job rows missing")
        span=(max(ends)-min(starts)).total_seconds()/3600
    except (KeyError,ValueError,TypeError):wall_reason="Actual sacct Start/End absent/unknown; no predicted wall time substituted."
    import pyarrow.parquet as pq
    table=Path(a.verification).parent/"task_status_distribution.parquet"
    task_counts={calc:{"success":0,"total":0} for calc in CALCS}
    for row in pq.read_table(table).to_pylist():
        if row["task"] in task_counts:
            item=task_counts[row["task"]];item["total"]+=row["count"]
            if row["status"]=="SUCCESS":item["success"]+=row["count"]
    quota=observation.get("quota_parsed",{})
    used=quota.get("used_kib");used=used*1024 if used is not None else None
    remaining=quota.get("remaining_bytes");files=quota.get("files_reported")
    storage=[{"path":str(path),"sha256":sha(path),**json.loads(path.read_text())} for path in a.storage_reports or []]
    decision=[]
    for name,result in (("人口/12状态",catalog),("读回/数组",verify),("随机200",recompute),("pilot交集",pilot)):
        if result["status"] not in {"PASS","CLOSED"}:decision.append(name+"："+result["status"])
    nodes={report.get("node") for report in storage if report.get("stage")=="WP5_ACCEPTANCE_NODE_SCRATCH" and report["status"]=="PASS"}
    if nodes!={"compute-0-"+str(n) for n in range(14,20)}:decision.append("六节点本地scratch清空证据未齐")
    if not any(report.get("stage")=="WP5_ACCEPTANCE_SHARED_FILE_LAYOUT" and report["status"]=="PASS" for report in storage):decision.append("共享计算小文件清空证据未齐")
    if missing:decision.append("实际accounting缺少"+str(len(missing))+"个正式job")
    if wall_reason:decision.append("实际墙钟：须补Start/End，只读查询即可")
    summary={"status":"ACCEPTANCE_CLOSED" if not decision else "ACCEPTANCE_REQUIRES_REVIEW","completed_records":catalog["canonical_records"],"expected_records":catalog["expected_records"],
        "record_completion_rate":catalog["canonical_records"]/catalog["expected_records"],"latest_molecules":catalog["canonical_molecules"],"expected_molecules":catalog["expected_molecules"],
        "record_task_rows":catalog["canonical_record_tasks"],"task_success":task_counts,"actual_allocated_core_hours":core_hours,
        "actual_wall_span_hours":span,"wall_unknown_reason":wall_reason,"accounting_missing_jobs":missing,"actual_job_states":records,
        "quota_used_bytes":used,"quota_remaining_bytes":remaining,"account_files_reported":files,"formal_artifact_bytes":sum(ref["bytes"] for ref in catalog["artifacts"]),
        "pending_user_decisions":decision,"storage_evidence":storage,"G5_user_exception":catalog["G5_exception"],
        "actual_accounting_definition":"ElapsedRaw seconds * AllocCPUS /3600 for every formal main/cleanup job, including allocated idle/finalizer time. Predicted 65450 planning core-hours never substitute for actual allocation.",
        "new_QM_calls":0,"original_data_written":False,"LMDB_created":False,
        "bindings":{name:{"path":str(getattr(a,name)),"sha256":sha(getattr(a,name))} for name in ("catalog","verification","recompute","pilot","jobmap","accounting")}}
    publish(out/"delivery_summary.json",summary)
    def fmt(value,unit=""):return "未知" if value is None else f"{value:,.3f}"+unit
    lines=["# WP5 正式计算验收","",
        f"完成记录 **{catalog['canonical_records']:,}/{catalog['expected_records']:,}（{summary['record_completion_rate']:.6%}）**；记录×任务 **{catalog['canonical_record_tasks']:,}**。",
        f"实际分配核时 **{fmt(core_hours,' 核时')}**；实际跨job墙钟 **{fmt(span,' 小时')}**。",
        f"账户存储占用 **{fmt(used/1e12 if used is not None else None,' TB')}**；余量 **{fmt(remaining/1e12 if remaining is not None else None,' TB')}**；账户文件数 **{files if files is not None else '未知'}**。",
        "待用户决定："+("；".join(decision) if decision else "验收已闭合；接下来讨论 lmdb_1 字段和大小预算，本轮未写 LMDB。"),"",
        "| 任务 | 成功/明确状态 | 成功率 |","|---|---:|---:|"]
    for calc,item in task_counts.items():lines.append(f"| {calc} | {item['success']:,}/{item['total']:,} | {item['success']/item['total']:.6%} |" if item["total"] else f"| {calc} | 0/0 | 未知 |")
    lines+=["","G5 历史raw缺口仅采用已批准的独立例外；随机200和新的科学差异不套用该例外。","",
        "后附证据："+", ".join(str(getattr(a,name)) for name in ("catalog","verification","recompute","pilot"))+"。"]
    target=out/"WP5_delivery.md";target.write_text("\n".join(lines)+"\n")
    print(json.dumps({"summary":str(out/"delivery_summary.json"),"first_page":str(target),"status":summary["status"]}))
if __name__=="__main__":main()
