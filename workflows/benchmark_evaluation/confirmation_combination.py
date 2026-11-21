"""Join closed second-seed stage evidence without rereading predictions or scores."""
from .selection import IncompleteComparison
from .c1_reporting import TERMINAL

def combine_stage_reports(reports):
    indexed={}
    for report in reports:
        stage=report.get("stage")
        if stage not in {"B1","C1"} or stage in indexed:
            raise IncompleteComparison("Exactly one original closed B1 and C1 evidence stage is required")
        if (report.get("status")!="CONDITIONAL_CONFIRMATION_STAGE_REPORT_CLOSED"
            or report.get("all_declared_producers_terminal") is not True
            or report.get("original_TEST_binding_enforced") is not True
            or report.get("original_primary_scores_recomputed") is not False):
            raise IncompleteComparison("Stage evidence is pending or changed the original scientific boundary")
        if report.get("required_configurations")!=len(report["records"]):
            raise IncompleteComparison("Stage record count differs from its frozen required plan")
        keys=[]
        for row in report["records"]:
            key=(row["endpoint_key"],row["model"]) if stage=="B1" else (
                row["endpoint_key"],row["feature_group"],row["learner"])
            keys.append(key)
            if row["evidence"].get("status") not in {"COMPLETED","UNRESOLVED"}:
                raise IncompleteComparison("A required confirmation cell remains pending")
        if len(set(keys))!=len(keys):raise IncompleteComparison("Duplicate stage confirmation configuration")
        indexed[stage]=report
    if set(indexed)!={"B1","C1"}:raise IncompleteComparison("Both required evidence stages must close")
    baseline=indexed["B1"];c1=indexed["C1"]
    if baseline["frozen_B1_roster"]!=c1["frozen_B1_roster"]:
        raise IncompleteComparison("Second-seed stages refer to different frozen B1 populations")
    if baseline.get("C1_primary_manifest") not in {None,c1["C1_primary_manifest"]}:
        raise IncompleteComparison("Baseline confirmation has a conflicting primary C1 source")
    accounting={}
    for report in indexed.values():
        if not report.get("native_accounting"):raise IncompleteComparison("Native producer accounting is absent")
        for job,record in report["native_accounting"].items():
            if record.get("state") not in TERMINAL:raise IncompleteComparison("A declared original producer remains active")
            if job in accounting and accounting[job]!=record:
                raise IncompleteComparison("The same native source has conflicting terminal accounting")
            accounting[job]=dict(record)
    return dict(status="CONDITIONAL_CONFIRMATION_REPORT_CLOSED",
        frozen_B1_roster=baseline["frozen_B1_roster"],C1_primary_manifest=c1["C1_primary_manifest"],
        B1=baseline["records"],C1=c1["records"],native_accounting=accounting,
        all_declared_producers_terminal=True,original_TEST_binding_enforced=True,
        original_primary_scores_recomputed=False,task_roster_reselection=False,
        score_replay=False,final_SHA_produced=False)
