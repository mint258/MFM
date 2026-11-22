"""Primary descriptive budget-curve tables from original, retained bootstrap draws."""
import argparse
import csv
import json
import math
import os
import socket
import contextlib
import io
import runpy
from pathlib import Path

from budget_curve import (C, REPO, PLAN, expected_points, source_complete, validate_plan)
from execution_ledger import read, write

RESULTS = REPO / "results/p_recipe/fixed_20261115/confirmation"
CACHE = C / "fixed_20261115/budget_curve_primary_cache.json"
SUMMARY = RESULTS / "budget_curve_summary.json"
CSV = RESULTS / "budget_curve.csv"
FIGURE = RESULTS / "budget_curve.png"


def metrics(scores):
    """Consume the original primary scores once; never fit, predict or resample."""
    import numpy as np
    result = {}
    for name in ("R1", "R3"):
        value = scores[name]
        draws = value["paired_bootstrap"]["values"]
        if (not value.get("complete") or value.get("bootstrap_samples") != 1000
                or value.get("bootstrap_defined") != 1000 or len(draws) != 1000
                or any(x is None or not math.isfinite(x) for x in draws)):
            raise ValueError("The original molecular bootstrap is not fully defined")
        seed = value["paired_bootstrap"].get("seed", 20261025)
        if seed != 20261025:
            raise ValueError("Changed bootstrap seed")
        low, high = map(float, np.quantile(draws, [.025, .975]))
        result[name] = dict(mean=value["mean_normalized_improvement"],
                           ci_lower=low, ci_upper=high, bootstrap_values=draws,
                           included_tasks=sorted(value["included_tasks"]), bootstrap_seed=seed)
    return result


def paired_delta(a, b):
    """Paired algebra on already retained draws; no new bootstrap or WIN/LOSS."""
    import numpy as np
    if (a["included_tasks"] != b["included_tasks"]
            or a["bootstrap_seed"] != b["bootstrap_seed"]
            or len(a["bootstrap_values"]) != 1000 or len(b["bootstrap_values"]) != 1000):
        raise ValueError("The retained molecular draws are not a matched protocol")
    delta = np.asarray(a["bootstrap_values"]) - np.asarray(b["bootstrap_values"])
    low, high = map(float, np.quantile(delta, [.025, .975]))
    return dict(delta=a["mean"] - b["mean"], ci_lower=low, ci_upper=high)


def plateau(points):
    """Earliest observed point after which no later R3 gain exceeds its own tau."""
    ordered = sorted(points, key=lambda x: x["samples"])
    if not ordered or ordered[-1]["samples"] != 9000000:
        raise ValueError("The own 9M endpoint is required for tau")
    tau = max(.01, .05 * ordered[-1]["R3"])
    first = next(p for i, p in enumerate(ordered)
                 if all(later["R3"] - p["R3"] <= tau for later in ordered[i + 1:]))
    return dict(tau=tau, earliest_observed_plateau_samples=first["samples"],
                interpretation="Descriptive observed checkpoints only; not proof of convergence")


def val_rows(source):
    """Keep the producer's separate family losses; do not invent a total loss."""
    outputs = []
    current = dict(source)
    seen = set()
    while True:
        output = Path(current["output"])
        if output in seen:
            raise ValueError("Cyclic resume ancestry")
        seen.add(output)
        outputs.append((current["run"], output))
        parent = current.get("resume_from_output")
        if not parent:
            break
        current = read(Path(parent) / "configuration.json")
    values = {}
    for run, output in reversed(outputs):
        path = REPO / "results/p_recipe/training" / run / "family_losses.csv"
        if not path.is_file():
            raise FileNotFoundError("Publish the original closed family CSV first: " + str(path))
        with path.open(newline="") as stream:
            for row in csv.DictReader(stream):
                if not row["kind"].startswith("VAL"):
                    continue
                samples = int(row["samples"])
                if samples % 500000 or not 500000 <= samples <= 9000000:
                    continue
                key = (samples, row["family"])
                item = dict(samples=samples, family=row["family"], loss=float(row["loss"]),
                            kind=row["kind"], physical_run=run)
                if key in values and values[key]["loss"] != item["loss"]:
                    raise ValueError("Conflicting original fixed-VAL rows across resume ancestry")
                values[key] = item
    return list(values.values())


def table_rows(cache):
    families = sorted({v["family"] for values in cache.get("VAL", {}).values() for v in values})
    points = cache.get("points", {})
    output = []
    for arm in ("T1", "T2", "T4", "T5", "T6"):
        vals = {(v["samples"], v["family"]): v for v in cache.get("VAL", {}).get(arm, [])}
        for samples in range(500000, 9000001, 500000):
            point = points.get(arm + ":" + str(samples))
            if point is None and not any((samples, family) in vals for family in families):
                continue
            row = dict(arm=arm, samples=samples, source_training_budget=9000000,
                       source_run=point["source_run"] if point else "", readout_run=point["run"] if point else "",
                       readout_complete=point is not None, descriptive_only=True)
            for name in ("R1", "R3"):
                for field in ("mean", "ci_lower", "ci_upper"):
                    row[name + "_" + field] = point["metrics"][name][field] if point else ""
                a, b = points.get("T2:" + str(samples)), points.get("T1:" + str(samples))
                paired = paired_delta(a["metrics"][name], b["metrics"][name]) if arm == "T2" and a and b else {}
                for field in ("delta", "ci_lower", "ci_upper"):
                    row[name + "_T2_minus_T1_" + field] = paired.get(field, "")
            for family in families:
                row["VAL_loss_" + family] = vals.get((samples, family), {}).get("loss", "")
            row["VAL_kind"] = next((v["kind"] for (n, _), v in vals.items() if n == samples), "")
            output.append(row)
    return output


def require_complete(summary):
    if (summary.get("authority") != "docs/p_recipe/USER_DIRECTIVE_20261121.md"
            or summary.get("status") != "COMPLETE" or summary.get("closed_readouts") != 22
            or summary.get("expected_readouts") != 22 or summary.get("missing_readouts")
            or set(summary.get("closed_original_9M_arms", [])) != {"T1", "T2", "T4", "T5", "T6"}
            or not summary.get("plot_complete")):
        raise ValueError("Final REPORT waits for all22 readouts, five original endpoints and the budget figure")
    if {tuple(x) for x in summary.get("closed_readout_points", [])} != set(expected_points()):
        raise ValueError("Final REPORT requires every explicitly named intermediate checkpoint")
    return summary


def plot(rows, target):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fields = ["R3_mean", "R1_mean"] + [k for k in rows[0] if k.startswith("VAL_loss_")]
    ncols = 3
    figure, axes = plt.subplots(math.ceil(len(fields) / ncols), ncols,
                               figsize=(15, 3.1 * math.ceil(len(fields) / ncols)), squeeze=False)
    for axis, field in zip(axes.flat, fields):
        for arm in ("T1", "T2", "T4", "T5", "T6"):
            selected = [r for r in rows if r["arm"] == arm and r[field] != ""]
            if not selected:
                continue
            x = [r["samples"] / 1000000 for r in selected]
            axis.plot(x, [r[field] for r in selected], marker="o", markersize=3, label=arm)
            if field in ("R1_mean", "R3_mean"):
                prefix = field[:2]
                axis.fill_between(x, [r[prefix + "_ci_lower"] for r in selected],
                                  [r[prefix + "_ci_upper"] for r in selected], alpha=.12)
        axis.set(title=field.replace("VAL_loss_", "Fixed VAL: "), xlabel="Samples (million)")
        axis.grid(alpha=.2)
    for axis in list(axes.flat)[len(fields):]:
        axis.set_visible(False)
    axes.flat[0].legend(ncol=5, fontsize=8)
    figure.suptitle("Existing 9M trajectories: L6/H0 R1/R3 and original fixed-VAL family losses")
    figure.tight_layout()
    figure.savefig(target, dpi=180)
    plt.close(figure)


def regressions(points, original_vals):
    ordered = sorted(points, key=lambda x: x["samples"])
    values = {(v["samples"], v["family"]): v["loss"] for v in original_vals}
    result = []
    for a, b in zip(ordered, ordered[1:]):
        if b["R3"] >= a["R3"]:
            continue
        families = sorted({family for n, family in values if n == a["samples"]}
                          & {family for n, family in values if n == b["samples"]})
        falling = [f for f in families if values[b["samples"], f] < values[a["samples"], f]]
        if falling:
            result.append(dict(from_samples=a["samples"], to_samples=b["samples"],
                               R3_before=a["R3"], R3_after=b["R3"],
                               VAL_families_still_decreasing=falling,
                               all_comparable_VAL_families_decreasing=len(falling) == len(families),
                               mechanism_inferred=False, extra_diagnostics_performed=False))
    return result


def admit_statistics():
    node = socket.gethostname().split(".")[0]
    if node not in {"compute-0-" + str(i) for i in (8,9,10,11,12,13,15,16,17,19)}:
        raise RuntimeError("Budget-curve statistics require a healthy CPU-only node")
    if os.environ.get("CUDA_VISIBLE_DEVICES"):
        raise RuntimeError("Budget-curve statistics must have no CUDA device")
    from budget_curve import admit_joint_storage
    admit_joint_storage()


def first_timing(points):
    completed = [p for p in points if p["new_readout"]]
    if not completed:
        return None
    first = min(completed, key=lambda p: p["statistics_completed_at"])
    seconds = first["gpu_readout_seconds"] + first["statistics_cpu_seconds"]
    return dict(arm=first["arm"], samples=first["samples"], run=first["run"],
                statistics_completed_at=first["statistics_completed_at"],
                measured_compute_seconds=seconds, estimate_all_22_compute_seconds=22*seconds,
                queue_time_included=False, excess_1p5_estimate_action="REPORT_AND_CONTINUE")


def aggregate(plan_path=PLAN):
    """The authorized primary table producer caches closed scores rather than rereading them."""
    admit_statistics()
    plan = validate_plan(read(plan_path))
    ledger = read(C / "study_execution.json")
    cache = read(CACHE) if CACHE.is_file() else dict(points={}, VAL={}, first_readout_timing=None)
    sources = {arm: read(next(r["source_configuration"] for r in plan["readouts"] if r["arm"] == arm))
               for arm in ("T1", "T2", "T4", "T5", "T6")}
    closed_sources = [arm for arm, source in sources.items() if source_complete(source, ledger)]
    candidates = [(arm, 9000000, source, False) for arm, source in sources.items() if arm in closed_sources]
    for row in plan["readouts"]:
        if row.get("configuration"):
            candidates.append((row["arm"], row["samples"], read(row["configuration"]), True))
    for arm, samples, c, is_new in candidates:
        key = arm + ":" + str(samples)
        if key in cache["points"]:
            continue
        record = ledger["runs"].get(c["run"], {})
        cpu = ledger.get("cpu_statistics", {}).get(c["run"], {})
        summary_path = Path(c["output"]) / "summary.json"
        if (record.get("state") != "COMPLETED" or record.get("exit_code") not in (0, "0:0")
                or cpu.get("state") != "COMPLETED" or cpu.get("exit_code") not in (0, "0:0")
                or not summary_path.is_file()):
            continue
        summary = read(summary_path)
        if summary.get("status") != "COMPLETE" or summary.get("samples") != samples:
            continue
        result = dict(arm=arm, samples=samples, run=c["run"],
                      source_run=c.get("source_run", c["run"]), new_readout=is_new,
                      metrics=metrics(read(Path(c["output"]) / "readout/scores.json")),
                      native_GPU_job=record["job_id"], native_GPU_state=record["state"],
                      native_GPU_exit=record["exit_code"], native_CPU_job=cpu["job_id"],
                      native_CPU_state=cpu["state"], native_CPU_exit=cpu["exit_code"],
                      statistics_completed_at=summary.get("statistics_completed_at"),
                      gpu_readout_seconds=summary.get("gpu_readout_seconds"),
                      statistics_cpu_seconds=summary.get("statistics_cpu_seconds", 0.))
        cache["points"][key] = result
        cache["first_readout_timing"] = first_timing(cache["points"].values())
        # Persist each original result immediately after its primary consumption.
        write(CACHE, cache)
    for arm in closed_sources:
        if arm not in cache["VAL"]:
            cache["VAL"][arm] = val_rows(sources[arm])
            write(CACHE, cache)
    missing = [dict(arm=a, samples=n) for a, n in expected_points()
               if a + ":" + str(n) not in cache["points"]]
    for row in plan["readouts"]:
        if row["arm"] + ":" + str(row["samples"]) in cache["points"]:
            row["state"] = "COMPLETE"
    rows = table_rows(cache)
    RESULTS.mkdir(parents=True, exist_ok=True)
    if rows:
        with CSV.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    summary = dict(authority=plan["authority"], expected_readouts=22, closed_readouts=22-len(missing),
                   missing_readouts=missing, closed_original_9M_arms=closed_sources,
                   closed_readout_points=[[a,n] for a,n in expected_points() if a+":"+str(n) in cache["points"]],
                   status="COMPLETE" if not missing and len(closed_sources) == 5 else "IN_PROGRESS",
                   plot_complete=False, first_readout_timing=cache.get("first_readout_timing"),
                   descriptive_only=True, new_training=False, new_seeds=False,
                   no_3M_screening_comparison=True, VAL_losses="Original per-family values, no invented aggregate",
                   bootstrap="Original 1000 retained molecular draws, seed20261025, percentile95CI",
                   interpretation={})
    for arm in closed_sources:
        required = [n for a, n in expected_points() if a == arm] + [9000000]
        if all(arm + ":" + str(n) in cache["points"] for n in required):
            points = [dict(samples=n, R3=cache["points"][arm + ":" + str(n)]["metrics"]["R3"]["mean"])
                      for n in required]
            summary["interpretation"][arm] = plateau(points)
            summary["interpretation"][arm]["R3_falls_while_VAL_decreases"] = regressions(points, cache["VAL"][arm])
    total = sum(p["gpu_readout_seconds"] + p["statistics_cpu_seconds"]
                for p in cache["points"].values() if p["new_readout"])
    summary["observed_new_readouts_compute_seconds"] = total
    timing = summary.get("first_readout_timing")
    summary["exceeds_1p5_initial_total_estimate"] = bool(
        timing and total > 1.5 * timing["estimate_all_22_compute_seconds"])
    summary["excess_action"] = "REPORT_AND_CONTINUE"
    summary["pending_user_decision"] = (["Budget curve: later R3 falls while recorded VAL family loss decreases; any extra diagnosis requires user decision and has not been run."]
        if any(v.get("R3_falls_while_VAL_decreases") for v in summary["interpretation"].values()) else [])
    if summary["status"] == "COMPLETE":
        if not FIGURE.is_file():
            plot(rows, FIGURE)
        summary["plot_complete"] = True
        plan["status"] = "COMPLETE"
    summary["endpoints"] = {a: {r: {k:v for k,v in cache["points"][a+":9000000"]["metrics"][r].items()
                                    if k!="bootstrap_values"} for r in ("R1","R3")}
                            for a in closed_sources if a+":9000000" in cache["points"]}
    write(SUMMARY, summary)
    write(plan_path, plan)
    return summary


def report_section(summary_path=SUMMARY, csv_path=CSV):
    summary = require_complete(read(summary_path))
    with Path(csv_path).open(newline="") as stream:
        rows = [r for r in csv.DictReader(stream) if r["R3_mean"] != ""]
    lines = ["## 9M预算曲线", "",
        "仅描述同一条9M运行的轨迹，不做胜负判定、不触发seed1或配方修改。"
        "各条按自身9M预算cosine退火，3M/6M学习率约为峰值75%/25%，9M到0；"
        "中间断点不与已训完的3M筛选运行比较。", "",
        "[完整精度CSV](../../results/p_recipe/fixed_20261115/confirmation/budget_curve.csv)。"
        "固定VAL沿用原生产者每500k记录的各家族损失，未合成未记录的总损失。", "",
        "![9M预算曲线](../../results/p_recipe/fixed_20261115/confirmation/budget_curve.png)", "",
        "| 运行 | 样本/M | R1 [95%CI] | R3 [95%CI] |", "| --- | ---: | --- | --- |"]
    def cell(row, name):
        return (f'{float(row[name+"_mean"]):.8g} '
                f'[{float(row[name+"_ci_lower"]):.8g}, {float(row[name+"_ci_upper"]):.8g}]')
    for row in rows:
        lines.append(f'| {row["arm"]} | {int(row["samples"])/1000000:g} | {cell(row,"R1")} | {cell(row,"R3")} |')
    lines.extend(["", "同断点T2−T1的R1/R3配对Δ及CI见完整表；区间来自原保留配对抽样，不重新bootstrap。", ""])
    for arm, value in summary["interpretation"].items():
        lines.append(f'{arm}：τ={value["tau"]:.8g}，观测断点中从'
                     f'{value["earliest_observed_plateau_samples"]/1000000:g}M之后未见超过τ的后续R3提升。')
        for fall in value.get("R3_falls_while_VAL_decreases", []):
            lines.append(f'{arm}：{fall["from_samples"]/1000000:g}M至{fall["to_samples"]/1000000:g}M的R3回落，'
                         f'固定VAL中{", ".join(fall["VAL_families_still_decreasing"])}家族损失仍下降；'
                         '仅如实描述，不推断机制，未执行额外诊断。')
    lines.extend(["", "这是观测点上的描述，不证明收敛，也不据此给出机制解释。", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default=str(PLAN))
    args = parser.parse_args()
    print(json.dumps(aggregate(args.plan)), flush=True)
