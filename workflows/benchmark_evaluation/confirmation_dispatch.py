"""Prepare only newly required neural fits from explicit closed native task bindings."""
import ast
from collections import defaultdict
from .selection import IncompleteComparison,SEED
from .confirmation import prepare_confirmation_source
from .gpu_runtime import prepare_neural_source

def planned_jobs(plan,task_bindings,*,baseline=False):
    """Resolve original task metadata, never scientific scores, to one producer configuration."""
    groups={};reuse=[]
    for row in plan:
        learner=row.get("model") if baseline else row["learner"]
        if learner not in {"Chemprop-v2","TabPFN"}:
            raise IncompleteComparison("Traditional ML cannot enter neural confirmation dispatch")
        if int(row["confirmation_seed"])!=SEED+1 or int(row["primary_seed"])!=SEED:
            raise IncompleteComparison("The registered original and confirmation seed identities changed")
        if row.get("confirmation_native_job") not in (None,""):
            if row["reason"]!="SOURCE_BINDING_ERROR_REQUIRED_REDO_OF_TRAINED_1H_SAMPLES":
                raise IncompleteComparison("Unexpected reused confirmation job")
            reuse.append(dict(row));continue
        feature=None if baseline else row["feature_group"]
        candidates=[item for item in task_bindings
            if item["dataset"]==row["dataset"] and item["producer_task"]==row["producer_task"]
            and item["learner"]==learner and item.get("feature_group")==feature
            and (not row.get("primary_source_job") or str(item["primary_job"])==str(row["primary_source_job"]))]
        identities={str(item["primary_job"]) for item in candidates}
        if len(identities)!=1:
            raise IncompleteComparison("Required task has absent or ambiguous closed original producer binding")
        job=next(iter(identities));binding=candidates[0]
        identity=(job,learner,feature)
        if identity not in groups:
            groups[identity]=dict(primary_job=job,learner=learner,feature_group=feature,
                template_id=binding["template_id"],required_tasks=[],frozen_B1_roster_changed=False)
        if groups[identity]["template_id"]!=binding["template_id"]:
            raise IncompleteComparison("One original producer resolves to conflicting source templates")
        if any(item["endpoint_key"]==row["endpoint_key"] for item in groups[identity]["required_tasks"]):
            raise IncompleteComparison("Duplicate conditional endpoint would train a second seed twice")
        groups[identity]["required_tasks"].append(dict(row))
    return list(groups.values()),reuse

def prepare_job_source(group,source,*,default_dataset):
    """Run on CPU; preserve native task names, frozen folds and model budgets."""
    tasks=group["required_tasks"]
    if not tasks:raise IncompleteComparison("An empty conditional group cannot run")
    reasons={row["reason"] for row in tasks}
    if reasons!={"FINAL_SIGNIFICANT_IMPROVEMENT"}:
        raise IncompleteComparison("Actual sample-redo confirmation uses its recorded separate native job")
    download_calls={"urlopen","urlretrieve","hf_hub_download","snapshot_download","download_url_to_file"}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ""
            if name in download_calls:
                raise IncompleteComparison("Prepare/bind existing official checkpoint files on CPU before GPU confirmation; source still contains "+name)
    result=prepare_confirmation_source(source,group["learner"],tasks,
            default_dataset=default_dataset,reason="FINAL_SIGNIFICANT_IMPROVEMENT")
    result=prepare_neural_source(result,group["learner"])
    compile(result,"closed_native_conditional_neural_source","exec")
    return result,dict(primary_job=group["primary_job"],learner=group["learner"],
        template_id=group["template_id"],required_original_tasks=[
            dict(dataset=row["dataset"],producer_task=row["producer_task"],endpoint_key=row["endpoint_key"])
            for row in tasks],model_seed=SEED+1,split_and_statistics_seed=SEED,
        primary_retained_population_only=True,original_labels_or_masks_changed=False,
        task_roster_reselection=False,original_model_budget_unchanged=True,
        preparation_node_role="CPU_ONLY",GPU_statistics_deferred=True)
