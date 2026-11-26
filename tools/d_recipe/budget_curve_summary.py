"""Primary D budget table; reuse P's retained-draw algebra and VAL reader.

This producer does not fit, predict, bootstrap, select a recipe or start jobs.
It is gated by the original two complete native9M confirmations. Each closed
score and source VAL CSV is consumed once into the primary result cache.
"""
import argparse
from contextlib import contextmanager
import csv
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import sys

from .budget_readout_plan import AUTHORITY, NATIVE_ARMS, points, require_confirmations

REPO = Path(__file__).resolve().parents[2]
RUNS = REPO.parent / "runs/d_recipe_20261120"
POPULATIONS = {"9M-D-R0": "T1", "9M-D-final": "T2",
               "D-final-P-T5": "T5", "D-final-P-T6": "T6"}
FAMILIES = {"graph_2d", "molecule_3d", "atom_sasa"}


def read(path):
    return json.loads(Path(path).read_text())


def original_report():
    path = REPO.parent / "MFM_p_recipe/tools/p_recipe/budget_curve_report.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("d_original_p_budget_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def d_val_scope(module):
    from .training import ResultRoot
    previous = module.REPO
    try:
        module.REPO = ResultRoot(REPO)
        yield
    finally:
        module.REPO = previous


def source_population(population, configuration):
    if population not in POPULATIONS:
        raise ValueError("Only the two native and two original P subset populations")
    allowed = points(configuration)
    if population in NATIVE_ARMS:
        if configuration.get("molecule_scaling") or configuration["arm"] != population:
            raise ValueError("Native population differs from its original source")
    elif (not configuration.get("molecule_scaling")
          or configuration["arm"] != "9M-D-final"
          or configuration["d_explicit_molecule_selection"]["P_arm"] != POPULATIONS[population]):
        raise ValueError("Subset population differs from its original P identity list")
    return tuple(allowed) + (9000000,)


def table_rows(cache, module):
    """Map D labels into the original P table, then restore unambiguous names."""
    native = dict(points={}, VAL={})
    reverse = {value: key for key, value in POPULATIONS.items()}
    for population, records in cache["VAL"].items():
        native["VAL"][POPULATIONS[population]] = records
    for key, point in cache["points"].items():
        population, samples = key.rsplit(":", 1)
        native["points"][POPULATIONS[population] + ":" + samples] = point
    rows = module.table_rows(native)
    for row in rows:
        population = reverse[row["arm"]]
        row["arm"] = population
        row["source_run"] = cache["sources"][population]["run"]
        row["population"] = "full_TRAIN" if population in NATIVE_ARMS else POPULATIONS[population]
        row["trajectory_scope"] = "Original9M cosine trajectory; no completed3M comparison"
        samples = row["samples"]
        for name in ("R1", "R3"):
            for field in ("delta", "ci_lower", "ci_upper"):
                old = name + "_T2_minus_T1_" + field
                row[name + "_final_minus_R0_" + field] = row.pop(old)
            subset = cache["points"].get(population + ":" + str(samples))
            full = cache["points"].get("9M-D-final:" + str(samples))
            delta = (module.paired_delta(subset["metrics"][name], full["metrics"][name])
                     if population not in NATIVE_ARMS and subset and full else {})
            for field in ("delta", "ci_lower", "ci_upper"):
                row[name + "_subset_minus_full_" + field] = delta.get(field, "")
    return rows


def aggregate(specification, *, module=None):
    from .shared_admission import atomic_json
    if specification.get("authority") != AUTHORITY:
        raise ValueError("Original D scaling authority required")
    tasks = read(REPO / "configs/p_recipe/protocol.json")["scored_tasks"]
    if len(tasks) != 7 or set(specification["scored_tasks"]) != set(tasks):
        raise ValueError("Keep the original seven-task readout protocol")
    sources = {population: read(path) for population, path in specification["sources"].items()}
    if not set(NATIVE_ARMS) <= sources.keys():
        raise ValueError("Both native confirmations are required")
    expected = {pop: source_population(pop, c) for pop, c in sources.items()}
    closed = {}
    for arm in NATIVE_ARMS:
        c = sources[arm]
        s = read(Path(c["output"]) / "summary.json")
        if s.get("run") != c["run"]:
            raise ValueError("Native summary/source identity differs")
        closed[arm] = dict(s, arm=arm, seed=c["seed"])
    require_confirmations(closed)
    cache_path = Path(specification["cache"])
    if not cache_path.resolve().is_relative_to(RUNS.resolve()):
        raise ValueError("Primary cache belongs in the owned D run scope")
    destination = REPO / "results/d_recipe/budget_curve.csv"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    module = original_report() if module is None else module
    with cache_path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cache = read(cache_path) if cache_path.exists() else dict(sources={}, points={}, VAL={})
        for pop, c in sources.items():
            binding = dict(run=c["run"], configuration=specification["sources"][pop],
                           scientific_binding=c["d_recipe"]["scientific_binding"])
            if pop in cache["sources"] and cache["sources"][pop] != binding:
                raise ValueError("Cached source binding changed; preserve the original producer")
            cache["sources"][pop] = binding
        candidates = [(pop, 9000000, c) for pop, c in sources.items()]
        seen = set()
        for row in specification.get("readouts", []):
            pop, n = row["population"], row["samples"]
            if pop not in sources or n not in expected[pop] or n == 9000000 or (pop, n) in seen:
                raise ValueError("Only distinct authorized intermediate readouts; reuse9M endpoint")
            seen.add((pop, n))
            c = read(row["configuration"])
            if (c.get("source_run") != sources[pop]["run"] or c.get("samples") != n
                    or c.get("source_training_budget") != 9000000
                    or c.get("layer") != 6 or c.get("representation") != "H0"
                    or c.get("descriptive_only") is not True):
                raise ValueError("Intermediate readout/source or original trajectory differs")
            candidates.append((pop, n, c))
        for pop, n, c in candidates:
            key = pop + ":" + str(n)
            if key in cache["points"]:
                if cache["points"][key]["run"] != c["run"]:
                    raise ValueError("A cached endpoint cannot be replaced by another run")
                continue
            path = Path(c["output"])
            summary = read(path / "summary.json") if (path / "summary.json").exists() else {}
            if (summary.get("status") != "COMPLETE" or summary.get("statistics_complete") is not True
                    or summary.get("samples") != n or summary.get("run") != c["run"]):
                continue
            metrics = module.metrics(read(path / "readout/scores.json"))
            if any(set(metrics[name]["included_tasks"]) != set(specification["scored_tasks"])
                   for name in ("R1", "R3")):
                raise ValueError("Original seven-task protocol coverage differs")
            cache["points"][key] = dict(run=c["run"], source_run=sources[pop]["run"], metrics=metrics)
            atomic_json(cache_path, cache)
        for pop, c in sources.items():
            if pop in cache["VAL"] or pop + ":9000000" not in cache["points"]:
                continue
            with d_val_scope(module):
                # Same-output handoff keeps every original VAL row in one CSV.
                source = dict(c)
                if source.get("resume_from_output") == source["output"]:
                    source.pop("resume_from_output")
                cache["VAL"][pop] = module.val_rows(source)
            atomic_json(cache_path, cache)
        rows = table_rows(cache, module)
        if rows:
            destination.parent.mkdir(parents=True, exist_ok=True)
            pending = destination.with_suffix(".csv.partial")
            with pending.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(pending, destination)
        missing = [[pop, n] for pop, ns in expected.items() for n in ns
                   if pop + ":" + str(n) not in cache["points"]]
        missing_val = [[pop, n, family] for pop in sources for n in range(500000, 9000001, 500000)
                       for family in sorted(FAMILIES)
                       if not any(v["samples"] == n and v["family"] == family
                                  for v in cache["VAL"].get(pop, []))]
        summary = dict(authority=AUTHORITY,
            status="COMPLETE" if not missing and not missing_val and len(sources) == 4 else "IN_PROGRESS",
            missing_readouts=missing, missing_fixed_VAL=missing_val,
            pending_subset_populations=sorted(set(POPULATIONS) - sources.keys()),
            closed_points=len(cache["points"]), descriptive_only=True,
            original_retained_molecular_bootstrap=True, new_bootstrap=False,
            selection_change_allowed=False, source_training_budget=9000000)
        atomic_json(destination.with_suffix(".summary.json"), summary)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    args = parser.parse_args()
    transport = read(args.configuration)
    path = REPO.parent / "MFM_p_recipe/tools/p_recipe/cpu_ssh_runtime.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("d_budget_CPU_provider", path)
    provider = importlib.util.module_from_spec(spec); spec.loader.exec_module(provider)
    provider.verified_deadline(transport)
    if os.environ.get("CUDA_VISIBLE_DEVICES"):
        raise ValueError("Budget aggregation uses a healthy CPU node without CUDA")
    from .shared_admission import admit
    specification = read(transport["specification"])
    admit(transport, [Path(specification["cache"]).parent, REPO / "results/d_recipe"])
    print(json.dumps(aggregate(specification)), flush=True)


if __name__ == "__main__":
    main()

