"""Closed-cost stage-0 planning and frozen D20 normalization binding, no fits.

Plans are forecasts, not disk reservations or job submissions. The actual
shared-disk/UID/peer guard remains mandatory immediately before each write.
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import platform
import sys


FROZEN_ROUTES = "/lfshome/zixiao/data_v1_20261025/window2_TRAIN_normalization_parameters_20261107_v1/routes.json"


def closed_costs(costs):
    """Both libraries need terminal evidence; an unresolved library is skipped."""
    selected = {}
    for library in ("L1", "L2"):
        cost = costs[library]
        if cost.get("status") == "UNRESOLVED":
            selected[library] = {"status": "UNRESOLVED", "reason": cost.get("reason")}
        elif (cost.get("status") == "PILOT_COST_COMPLETE_NOT_DELIVERY"
              and cost.get("library") == library and cost.get("molecules") == 5000):
            selected[library] = {"status": "READY"}
        else:
            raise ValueError("Both registered 5000-molecule library costs must close: " + library)
    return selected


def load_closed_costs(root):
    return closed_costs({library: json.loads((Path(root) / (library + "_cost.json")).read_text())
                         for library in ("L1", "L2")})


def existing_d20_parameters(routes, training_view, *, recipe_root=None):
    """Resolve the existing model routes, never substitute raw-container stats."""
    if recipe_root is not None:
        sys.path.insert(0, str(Path(recipe_root).resolve() / "current"))
    from phychem_mfm.phase1.v31_normalization_routes import resolve_normalization_routes
    disabled = {"D20.NumBridgeheadAtoms", "D20.NumSpiroAtoms", "D20.MolMR"}
    fields = [field for field in training_view["fields"] if field["field_key"].startswith("D20.")
              and field.get("enabled", True) and field["field_key"] not in disabled]
    bound = resolve_normalization_routes(routes, fields, dataset="P_D")
    return {name.removeprefix("D20."): copy.deepcopy(spec) for name, spec in bound.items()}


def estimate_peak(*, rows, fields, panel_bytes_per_row, structures_existing_bytes=None,
                  existing_parameter_bytes=0, chunk_rows=256):
    """Explicit newly-written disk forecast; RAM workspaces are listed separately.

    Structure forecasts extrapolate the largest observed serialized panel row
    plus 512 bytes of full-role/identity metadata. They are not size limits;
    source preparation still pauses on real storage headroom if tails grow.
    ``rows`` must be the actual requested cohort count supplied by its producer.
    """
    if type(rows) is not int or rows <= 0 or chunk_rows not in (256, 512):
        raise ValueError("Actual positive cohort rows and fixed chunk size required")
    if not math.isfinite(panel_bytes_per_row) or panel_bytes_per_row <= 0:
        raise ValueError("Measured serialized pilot row bytes required")
    if (any(type(count) is not int or count <= 0 for count in fields.values())
            or set(fields) - {"L1", "L2"}):
        raise ValueError("Positive measured field counts required")
    if structures_existing_bytes is not None and (type(structures_existing_bytes) is not int or structures_existing_bytes < 0):
        raise ValueError("Existing structures bytes must be an actual nonnegative count")
    total_fields = sum(fields.values())
    libraries = len(fields)
    structures_forecast = math.ceil(rows * (panel_bytes_per_row + 512))
    structures_new = structures_forecast if structures_existing_bytes is None else 0
    parts = (rows + chunk_rows - 1) // chunk_rows
    components = {
        "raw_values_F64": rows * total_fields * 8,
        "explicit_status_u8": rows * total_fields,
        "array_headers": libraries * 2 * 4096,
        "structures_jsonl_new": structures_new,
        "role_row_index_forecast": rows * 16,
        "field_and_checkpoint_json": total_fields * 3072 + libraries * (parts * 16 + 65536),
        "statistics_atomic_json_temporary": total_fields * 3072 + existing_parameter_bytes,
        "preparation_checkpoint_atomic_temporary": 2**20,
        "production_writer_workspace_reserve": chunk_rows * max(fields.values(), default=0) * 18 + 2**21,
    }
    peak = sum(components.values())
    return {"rows": rows, "row_basis": "producer requested cohort count", "fields": dict(fields),
        "components_new_bytes": components, "peak_new_bytes": peak,
        "structure_forecast_bytes": structures_forecast,
        "structures_existing_bytes": structures_existing_bytes,
        "ram_working_forecast_bytes": rows * 80 + chunk_rows * max(fields.values(), default=0) * 18,
        "floor_and_peer_reservations_included": False,
        "reservation_status": "FORECAST_ONLY_NOT_RESERVED",
        "admission": "Actual-node storage.guard adds current /share floor, UID quota and peer future reservations"}


def generate_plan(pilot_config, costs, field_lists, population_summary, *, run_root,
                  measured_panel_row_bytes, existing_parameters_path, existing_parameter_bytes=0,
                  workers=4, chunk_rows=256, structures_existing_bytes=None,
                  recipe_root="/share/home/zixiao/descriptor_analysis/MFM_d_recipe"):
    terminal = closed_costs(costs)
    if type(workers) is not int or workers < 1:
        raise ValueError("Demand-based positive worker count required")
    root = Path(run_root)
    if not root.is_absolute() or not str(root).startswith("/share/"):
        raise ValueError("Registered /share run root required")
    fields = {}
    for library, status in terminal.items():
        if status["status"] != "READY":
            continue
        names = list(field_lists[library])
        if len(names) != len(set(names)) or len(names) != costs[library]["fields"]:
            raise ValueError("Measured field count/order is not consistent: " + library)
        fields[library] = len(names)
    budget = estimate_peak(rows=population_summary["row_count"], fields=fields,
        panel_bytes_per_row=measured_panel_row_bytes, structures_existing_bytes=structures_existing_bytes,
        existing_parameter_bytes=existing_parameter_bytes, chunk_rows=chunk_rows)
    peak = budget["peak_new_bytes"]
    preparation = {key: pilot_config[key] for key in ("corpus", "geometry_index")}
    preparation.update(pilot_root=pilot_config["output"], output=str(root / "structures"),
                       peak_bytes=peak, chunk_rows=1024)
    production = dict(input_rows=str(root / "structures" / "structures.jsonl"),
        pilot_root=pilot_config["output"], output=str(root / "stores"),
        peak_bytes=peak, workers=workers, chunk_rows=chunk_rows,
        existing_parameters_json={"L1": existing_parameters_path})
    return {"schema": "D_FULL_PRODUCTION_PLAN_V1", "libraries": terminal, "budget": budget,
        "configs": {"prepare": preparation, "produce": production,
                    "finalize": dict(production, workers=1)},
        "slurm": {"partition": "cpu", "allowed_nodes": "compute-0-[8-19]", "nodes": 1,
                  "exclude": "compute-0-[0-7,18,20-22]", "exclusive": False,
                  "cpus_per_stage": {"population_summary": 1, "prepare": 1,
                                     "produce": workers + 1, "finalize": 1},
                  "produce_cpu_basis": "calculator workers plus one encoding/flush parent",
                  "recipe_root": str(recipe_root)},
        "existing_parameters": {"path": existing_parameters_path, "source_routes": FROZEN_ROUTES,
                                "dataset": "P_D", "new_fit": False},
        "stages_to_run": ["prepare", "produce", "finalize"] if fields else [],
        "jobs_submitted": False, "reception_acceptance": "pending"}


def summarize_population_metadata(population_rows, references):
    """Count the existing population result; no new identity or numeric audit."""
    counts = {role: 0 for role in ("TRAIN", "VAL", "VAL_DIAGNOSTIC")}
    for row in population_rows:
        counts[row["role"]] += 1
    return {"schema": "D_POPULATION_METADATA_SUMMARY_V1", "row_count": len(population_rows),
            "role_counts": counts, "source_references": copy.deepcopy(references),
            "status": "REQUESTED_COHORT_METADATA_ONLY", "reception_acceptance": "pending",
            "independent_identity_audit_performed": False}


def population_summary(config):
    load_closed_costs(config["output"])
    from .prepare import population
    # Reuse the preparation metadata reader once. Do not run validate_rows,
    # open original LMDBs, construct graphs or inspect descriptor distributions.
    selected, references = population(config)
    return summarize_population_metadata(selected, references)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("plan", "population_summary"), default="plan")
    parser.add_argument("--pilot-config", required=True)
    parser.add_argument("--population-summary",
                        help="producer metadata JSON with actual row_count; no speculative denominator")
    parser.add_argument("--summary-output")
    parser.add_argument("--training-view")
    parser.add_argument("--routes", default=FROZEN_ROUTES)
    parser.add_argument("--run-root")
    parser.add_argument("--config-output")
    parser.add_argument("--recipe-root", default="/share/home/zixiao/descriptor_analysis/MFM_d_recipe",
                        help="existing recipe tree providing current/phychem_mfm normalization resolver")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    node = platform.node()
    if (not os.environ.get("SLURM_JOB_ID") or not node.startswith("compute-0-")
            or not 8 <= int(node.rsplit("-", 1)[-1]) <= 19):
        raise RuntimeError("Planning/writes require an allocated CPU node 8-19")
    def load(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))
    # The data-v1 branch intentionally has no copy of this model-line module.
    # Put the configured existing recipe tree before the data current/ package.
    sys.path.insert(0, str(Path(args.recipe_root).resolve() / "current"))
    config = load(args.pilot_config)
    if args.command == "population_summary":
        if not args.summary_output:
            parser.error("population_summary requires --summary-output")
        destination = Path(args.summary_output).resolve()
        if destination.exists():
            print(json.dumps({"status": "EXISTING_METADATA_SUMMARY_REUSED", "summary": str(destination)}))
            return
        summary = population_summary(config)
        from .storage import guard
        guard(destination.parent, peak_bytes=2**20)
        destination.parent.mkdir(parents=True, exist_ok=True)
        pending = Path(str(destination) + ".partial")
        pending.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(pending, destination)
        print(json.dumps({"status": summary["status"], "summary": str(destination), "rows": summary["row_count"]}))
        return
    if not all((args.population_summary, args.training_view, args.run_root, args.config_output)):
        parser.error("plan requires --population-summary, --training-view, --run-root and --config-output")
    pilot = Path(config["output"])
    costs = {library: load(pilot / (library + "_cost.json")) for library in ("L1", "L2")}
    terminal = closed_costs(costs)
    names = {library: load(pilot / (library + "_fields.json"))["ordered_names"]
             for library, state in terminal.items() if state["status"] == "READY"}
    panel = load(pilot / "panel.json")["molecules"]
    max_row_bytes = max(len(json.dumps(row, ensure_ascii=False).encode("utf-8")) + 1 for row in panel)
    parameters = existing_d20_parameters(load(args.routes), load(args.training_view), recipe_root=args.recipe_root)
    parameters_text = json.dumps(parameters, indent=2, allow_nan=False) + "\n"
    output = Path(args.config_output).resolve()
    existing_path = output / "existing_D20_parameters.json"
    summary = load(args.population_summary)
    plan = generate_plan(config, costs, names, summary, run_root=args.run_root,
        measured_panel_row_bytes=max_row_bytes, existing_parameters_path=str(existing_path),
        existing_parameter_bytes=len(parameters_text.encode("utf-8")), workers=args.workers,
        structures_existing_bytes=summary.get("structure_bytes_actual"), recipe_root=args.recipe_root)
    from .storage import guard
    guard(output.parent, peak_bytes=2**20)
    output.mkdir(parents=True, exist_ok=True)
    # No storage admission is recorded here for the future full-data budget.
    for name, value in dict(plan["configs"], plan=plan, existing_D20_parameters=parameters).items():
        path = output / (name + ".json")
        if path.exists():
            if load(path) != value:
                raise ValueError("Existing plan/config differs; choose a new output directory")
            continue
        guard(output, peak_bytes=2**20)
        pending = Path(str(path) + ".partial")
        pending.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(pending, path)
    print(json.dumps({"status": "PLANNED_NOT_SUBMITTED", "plan": str(output / "plan.json"),
                      "peak_new_bytes": plan["budget"]["peak_new_bytes"]}))


if __name__ == "__main__":
    main()
