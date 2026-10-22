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
def checked_reference(reference,expected_path=None,expected_sha=None):
    path=Path(reference['path'])
    if expected_path is not None and path.absolute()!=Path(expected_path).absolute():raise ValueError('PILOT_REVIEW_REFERENCE_PATH_DIFFERS')
    digest=sha(path)
    if len(reference.get('sha256',''))!=64 or digest!=reference['sha256']:raise ValueError('PILOT_REVIEW_REFERENCE_SHA_DIFFERS')
    if expected_sha is not None and digest!=expected_sha:raise ValueError('PILOT_REVIEW_SOURCE_AUTHORITY_SHA_DIFFERS')
    if 'bytes' in reference and path.stat().st_size!=reference['bytes']:raise ValueError('PILOT_REVIEW_REFERENCE_SIZE_DIFFERS')
    return path

def pilot_disclosure_review(pilot,pilot_path,review_path):
    if review_path is None:return None
    review=json.loads(Path(review_path).read_text())
    if review.get('schema')!='WP5_PILOT_DIFFERENCE_REVIEW_V1' or review.get('status')!='REVIEWED_DIFFERENCES_DISCLOSED':raise ValueError('CLOSED_EXPLICIT_PILOT_DISCLOSURE_REVIEW_REQUIRED')
    if review.get('decision_scope')!='DISCLOSURE_ONLY_NO_NUMERIC_EXCEPTION':raise ValueError('PILOT_REVIEW_MUST_NOT_WAIVE_NUMERICS')
    if review.get('original_pilot_result_overwritten') is not False or review.get('production_parameters_or_SCI_changed') is not False or review.get('tolerances_relaxed') is not False:raise ValueError('PILOT_REVIEW_MUTATION_OR_TOLERANCE_EXCEPTION_FORBIDDEN')
    if review.get('all_original_difference_rows_retained') is not True or review.get('unattributed_rows_retained') is not True:raise ValueError('PILOT_REVIEW_CANNOT_HIDE_UNATTRIBUTED_DIFFERENCES')
    if not isinstance(review.get('reviewed_by'),str) or not review['reviewed_by'].strip():raise ValueError('EXPLICIT_REVIEWER_REQUIRED')
    if not isinstance(review.get('review_statement'),str) or not review['review_statement'].strip():raise ValueError('EXPLICIT_DISCLOSURE_STATEMENT_REQUIRED')
    if type(review.get('requires_user_scientific_decision')) is not bool:raise ValueError('SCIENCE_DECISION_STATE_MUST_BE_EXPLICIT')
    if review.get('individual_causal_attribution_complete') is not False:raise ValueError('FEW_RECORD_DEBUG_IS_NOT_ALL_POPULATION_CAUSAL_PROOF')
    sources=review['sources'];checked_reference(sources['pilot'],pilot_path)
    checked_reference(sources['registry'],expected_sha=pilot['bindings']['registry_sha256'])
    checked_reference(sources['guide'],ROOT.parent.parent/'WP5 正式计算行动指南（Codex）.md')
    table=checked_reference(sources['difference_table'],pilot['differences'])
    import pyarrow.parquet as pq
    if pq.ParquetFile(table).metadata.num_rows!=pilot['difference_rows'] or sources['difference_table'].get('rows')!=pilot['difference_rows']:raise ValueError('PILOT_FULL_DIFFERENCE_TABLE_COUNT_DIFFERS')
    if review.get('raw_pilot_status')!=pilot['status'] or review.get('raw_field_counts')!=pilot['field_counts']:raise ValueError('PILOT_RAW_STATUS_OR_ALL_FIELD_COUNTS_CHANGED')
    for name in ('difference_rows','unresolved_difference_rows','comparison_counts_before_scope_classification','classified_difference_counts'):
        if review['raw_counts'].get(name)!=pilot[name]:raise ValueError('PILOT_RAW_DIFFERENCE_COUNTS_CHANGED:'+name)
    if sum(pilot['classified_difference_counts'].values())!=pilot['difference_rows']:raise ValueError('PILOT_CLASSIFIED_COUNT_NOT_CLOSED')
    unattributed=review.get('not_individually_attributed_rows')
    if type(unattributed) is not int or not 0<=unattributed<=pilot['difference_rows']:raise ValueError('EXPLICIT_UNATTRIBUTED_ROW_COUNT_REQUIRED')
    for reference in review.get('evidence',[]):checked_reference(reference)
    return {'path':str(review_path),'sha256':sha(review_path),'status':review['status'],'decision_scope':review['decision_scope'],
        'reviewed_by':review['reviewed_by'],'review_statement':review['review_statement'],'requires_user_scientific_decision':review['requires_user_scientific_decision'],
        'not_individually_attributed_rows':unattributed,'all_difference_rows_still_available':True,'pilot_numerical_PASS_claimed':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("catalog","verification","recompute","pilot","jobmap","accounting"):p.add_argument("--"+name,type=Path)
    p.add_argument("--pilot-review",type=Path,help="Explicit disclosure review; never alters original pilot DIFF or current200 requirements");p.add_argument("--storage-reports",type=Path,nargs="*");p.add_argument("--out",type=Path);p.add_argument("--workers",type=int,default=24);p.add_argument("--check",action="store_true");a=p.parse_args()
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
    disclosure=pilot_disclosure_review(pilot,a.pilot,a.pilot_review)
    decision=[]
    for name,result in (("人口/12状态",catalog),("读回/数组",verify),("随机200",recompute)):
        if result["status"] not in {"PASS","CLOSED"}:decision.append(name+"："+result["status"])
    if pilot['status'] not in {'PASS','CLOSED'}:
        if pilot['status']!='DIFFERENCES_REQUIRE_REVIEW' or disclosure is None:decision.append('pilot交集：'+pilot['status'])
        elif disclosure['requires_user_scientific_decision']:decision.append('pilot差异披露完成；独立审阅明确要求用户科学决定')
    nodes={report.get("node") for report in storage if report.get("stage")=="WP5_ACCEPTANCE_NODE_SCRATCH" and report["status"]=="PASS"}
    if nodes!={"compute-0-"+str(n) for n in (12,13,14,17,18,19)}:decision.append("六节点本地scratch清空证据未齐")
    if not any(report.get("stage")=="WP5_ACCEPTANCE_SHARED_FILE_LAYOUT" and report["status"]=="PASS" for report in storage):decision.append("共享计算小文件清空证据未齐")
    if missing:decision.append("实际accounting缺少"+str(len(missing))+"个正式job")
    if wall_reason:decision.append("实际墙钟：须补Start/End，只读查询即可")
    summary={"status":("ACCEPTANCE_CLOSED_WITH_DISCLOSED_PILOT_DIFFERENCES" if disclosure else "ACCEPTANCE_CLOSED") if not decision else "ACCEPTANCE_REQUIRES_REVIEW","completed_records":catalog["canonical_records"],"expected_records":catalog["expected_records"],
        "record_completion_rate":catalog["canonical_records"]/catalog["expected_records"],"latest_molecules":catalog["canonical_molecules"],"expected_molecules":catalog["expected_molecules"],
        "record_task_rows":catalog["canonical_record_tasks"],"task_success":task_counts,"actual_allocated_core_hours":core_hours,
        "actual_wall_span_hours":span,"wall_unknown_reason":wall_reason,"accounting_missing_jobs":missing,"actual_job_states":records,
        "quota_used_bytes":used,"quota_remaining_bytes":remaining,"account_files_reported":files,"formal_artifact_bytes":sum(ref["bytes"] for ref in catalog["artifacts"]),
        "pending_user_decisions":decision,"pilot_raw_status":pilot["status"],"pilot_raw_difference_rows":pilot.get("difference_rows"),"pilot_raw_unresolved_difference_rows":pilot.get("unresolved_difference_rows"),"pilot_disclosure_review":disclosure,"pilot_numerically_identical":pilot.get("difference_rows")==0,"pilot_disclosure_is_not_numerical_PASS":disclosure is not None,"storage_evidence":storage,"G5_user_exception":catalog["G5_exception"],
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
    if disclosure:lines.extend(['',f"pilot 原始状态仍为 **{pilot['status']}**，差异 **{pilot['difference_rows']:,}** 行，原始未解释计数 **{pilot['unresolved_difference_rows']:,}** 行；独立披露审阅 **{disclosure['status']}**。此状态不表示数值一致，不放宽容差；未逐条归因 **{disclosure['not_individually_attributed_rows']:,}** 行及完整原差异表继续保留。",'审阅来源：'+disclosure['path']+'；SHA256 '+disclosure['sha256']+'。'])
    target=out/"WP5_delivery.md";target.write_text("\n".join(lines)+"\n")
    print(json.dumps({"summary":str(out/"delivery_summary.json"),"first_page":str(target),"status":summary["status"]}))
if __name__=="__main__":main()
