"""Expand the registered F1 factorial into metadata only; never submit a job.

Configurations begin unactivated and unassigned. Actual dispatch binds a healthy
node/UUID, aggregate own reservation, tested source, and measured unit duration.
Existing configurations are preserved, including any later activation/progress.
"""
import argparse
import json
import math
import os
from pathlib import Path

AUTHORITY = "docs/p_recipe/USER_DIRECTIVE_20261122B.md"
TASKS = ("qm9.U0_atom", "qm9.homo", "exp.LogD", "exp.LogS")
ROOT = Path("/share/home/zixiao/descriptor_analysis")
REPO = ROOT / "MFM_p_recipe"
DIRECTORY = REPO / "configs/p_recipe/fixed_20261115/analysis_20261122"
OUTPUT = Path("/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/fixed_20261115/analysis_20261122")
STORE = ROOT / "runs/model_v3_20261025/selected_train_store_4520421/native_store/training_store.json"
REFERENCE = "/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/reference_C1_0/predictions.json"
SOURCES = (("T2", 1000000), ("T2", 3000000), ("T2", 6000000), ("T2", 9000000),
           ("T1", 9000000), ("T5", 9000000), ("T6", 9000000))


def configurations(plan):
    if plan.get("authority") != AUTHORITY:
        raise ValueError("Latest registered analysis authority required")
    protocol = plan["protocol"]
    if (tuple(protocol["tasks"]) != TASKS or protocol["finetune_seeds"] != [0, 1, 2]
            or protocol["batch_size"] != 32 or protocol["precision"] != "float32"
            or protocol["tf32"] is not False or protocol["bootstrap_draws"] != 1000
            or protocol["internal_split_seed"] != 20261112
            or protocol["bootstrap_seed"] != 20261025):
        raise ValueError("Registered F protocol differs")
    optimizer = protocol["optimizer"]
    if (optimizer["kind"] != "AdamW" or optimizer["encoder_lr"] != 1e-4
            or optimizer["head_lr"] != 1e-3 or optimizer["betas"] != [.9, .999]
            or optimizer["weight_decay"] != .01
            or protocol["schedule"] != dict(epochs=50, warmup_fraction=.05,
                                            kind="cosine", final_lr=0)):
        raise ValueError("The fixed fine-tuning optimizer/schedule cannot drift")
    entries = plan["source_resolution"]["bindings"]
    by_source = {(e["arm"], e["samples"]): e for e in entries}
    if len(entries) != 7 or set(by_source) != set(SOURCES):
        raise ValueError("Exactly the seven registered source checkpoint bindings required")
    modes = [("full", point) for point in SOURCES]
    modes += [("top2", ("T2", n)) for n in (1000000, 9000000)]
    modes += [("scratch", ("random", 0))]
    result = []
    for mode, point in modes:
        binding = dict(by_source[("T2", 9000000)] if mode == "scratch" else by_source[point])
        if mode == "scratch":
            binding.update(role="architecture_only_random_initialization",
                           comparison_arm="random", pretraining_samples_used=0)
        for task in TASKS:
            for seed in (0, 1, 2):
                arm, samples = point
                label = arm + "_" + str(samples // 1000000) + "M"
                run = "F1_" + mode + "_" + label + "_" + task.replace(".", "_") + "_s" + str(seed)
                result.append(dict(schema="P_F1_RUN_20261122_V1", authority=AUTHORITY,
                    kind="F", batch="F1", run=run, task=task, mode=mode, seed=seed,
                    seed_role="finetuning", pretraining_seed=None if mode=="scratch" else 0,
                    bootstrap_seed=20261025, internal_split_seed=20261112,
                    source_binding=binding, store=str(STORE), reference_manifest=REFERENCE,
                    output=str(OUTPUT / run), output_mount="/lfshome", cleanup_seconds=900,
                    entry_provider="unchanged_shared_exit_lifecycle", ready=False, node=None, gpu_uuid=None,
                    nvidia_smi=None, reservation_ids=[], uid_quota_snapshot=None,
                    cpus=16, ram_peak_bytes=64 * 2**30, requested_memory_mib=65536,
                    remaining_output_bytes=994277760, local_output_peak_bytes=32 * 2**20+65536,
                    minimum_free_gpu_mib=22000,
                    work_unit_seconds=120, unit_duration_basis="Initial conservative bound; refine from actual first-run units",
                    proposed_time_limit_minutes=360,
                    configured_hyperparameters="Unchanged plan.protocol and finetune.py constants",
                    source_validation="Not yet executed; activation prohibited",
                    scientific_configuration_immutable=True))
    if len(result) != 120 or len({c["run"] for c in result}) != 120:
        raise ValueError("The registered F1 factorial is not120 unique runs")
    return result



def second_batch_configurations(plan):
    # Validate the shared protocol through the exact first-batch expansion.
    template = configurations(plan)[0]
    labels = ("round2_M1", "round2_B4", "round2_B3", "round3_M2", "T4_9M")
    bindings = {row["label"]:row for row in plan["source_resolution"]["followup_bindings"]}
    if tuple(plan["F2"]["source_binding_labels"]) != labels or not set(labels) <= bindings.keys():
        raise ValueError("The second-batch sources differ from registration")
    result = []
    for label in labels:
        binding = dict(bindings[label])
        expected_samples = 9000000 if label=="T4_9M" else 3000000
        if binding["samples"] != expected_samples or binding["source_training_budget"] != expected_samples:
            raise ValueError("Second batch requires each source's own registered endpoint")
        for task in TASKS:
            for seed in (0,1,2):
                run = "F2FT_full_" + label + "_" + task.replace(".","_") + "_s" + str(seed)
                result.append(dict(template, run=run, batch="F2", mode="full",
                    task=task, seed=seed, source_binding=binding,
                    output=str(OUTPUT/run), reservation_ids=[],
                    start_after="F1 complete; no additional user gate"))
    if len(result) != 60 or len({c["run"] for c in result}) != 60:
        raise ValueError("Exactly60 second-batch full fine-tunes required")
    return result


def materialize(plan_path):
    plan = json.loads(Path(plan_path).read_text())
    values = configurations(plan)
    directory = Path(plan_path).parent / "F1"
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for c in values:
        path = directory / (c["run"] + ".json")
        if path.is_file():
            existing = json.loads(path.read_text())
            keys = ("schema", "authority", "kind", "batch", "run", "task", "mode", "seed",
                    "source_binding", "store", "reference_manifest", "output")
            if any(existing.get(k) != c[k] for k in keys):
                raise ValueError("Existing scientific identity changed: " + str(path))
            # Never reset a valid assignment, activation, checkpoint or cost.
        else:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump(c, stream, indent=2)
                stream.write("\n")
        paths.append(str(path))
    return paths


def assign(configuration, *, node, gpu_uuid, reservation_ids, nvidia_smi,
           work_unit_seconds, unit_duration_basis):
    """Pure binding after actual admission/validation; no submission."""
    c = dict(configuration)
    if (node not in {"compute-0-"+str(i) for i in range(8)}
            or not gpu_uuid.startswith("GPU-") or not os.path.isabs(nvidia_smi)
            or not reservation_ids or not math.isfinite(work_unit_seconds)
            or work_unit_seconds <= 0 or not isinstance(unit_duration_basis, str)
            or not unit_duration_basis.strip()):
        raise ValueError("Actual eligible target and measured duration required")
    c.update(node=node, gpu_uuid=gpu_uuid, reservation_ids=list(reservation_ids),
             nvidia_smi=nvidia_smi, work_unit_seconds=work_unit_seconds,
             unit_duration_basis=unit_duration_basis)
    # Binding is not test evidence and is not activation. The caller sets ready
    # only after the real required validation and actual admission have closed.
    return c


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--materialize", action="store_true")
    args = parser.parse_args()
    if args.materialize:
        print(json.dumps(materialize(args.plan)))
    else:
        values = configurations(json.loads(Path(args.plan).read_text()))
        print(json.dumps(dict(runs=len(values), modes={m:sum(c["mode"]==m for c in values)
              for m in ("full","top2","scratch")}, activated=False)))