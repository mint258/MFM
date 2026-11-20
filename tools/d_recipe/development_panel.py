"""Section-5 controls over the adopted endpoint's retained native H0.

Explicit GPU/CPU phases; no encoder fallback, job submission, model selection,
new endpoints or changes to the frozen recipe. A reuses the main R3 result.
B/C use the original probe loop; LightGBM and composition ridge run on CPU.
"""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path

import numpy as np
import torch

from .descriptor_features import DownstreamDescriptorStore, D3_FEATURE_FIELDS
from .dev_descriptor_readouts import run_descriptor_probe
from .dev_lightgbm import run_lightgbm_probe

REPO = Path(__file__).resolve().parents[2]


def _read(path):
    return json.loads(Path(path).read_text())


def _publish(path, value, guard):
    guard.check(path.parent)
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def _context(c, cpu, guard):
    from .resources import execution_site, DJointGuard
    execution_site(c, cpu=cpu)
    native, best = c["readout_configuration"], _read(c["current_best"])
    expected_arm = ("9M-D-R0" if best["arm"] == "D-R0" else "9M-D-final") if native["samples"] == 9_000_000 else best["arm"]
    if (best.get("status") != "FROZEN" or native["arm"] != expected_arm
            or best["arm"] not in ("D-R0", "D-R1", "D-L1", "D-L2", "D-G1", "D-K1")
            or best["library"] != c["library"] or native["seed"] != 0
            or native["samples"] not in (3_000_000, 9_000_000)):
        raise ValueError("Explicit frozen adopted D recipe and its seed0 endpoint required")
    # Capacity is the prospective same-capacity protocol, never a tuning choice.
    if c["capacity_policy"] not in ("total_params_matching", "hidden_width_256"):
        raise ValueError("Explicit registered capacity policy required")
    guard = DJointGuard(c) if guard is None else guard
    output = Path(c["output"])
    guard.check(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "summary.json"
    binding = dict(configuration={k: v for k, v in c.items() if k != "phase"},
                   adopted_arm=best["arm"], adopted_library=best["library"])
    state = _read(path) if path.exists() else None
    if state is not None and state["binding"] != binding:
        raise ValueError("Development panel output belongs to a different frozen condition")
    original = _read(Path(native["output"]) / "predictions.json")
    if original["run"] != native["run"] or original["samples"] != native["samples"]:
        raise ValueError("Reused A predictions belong to a different native endpoint")
    return native, output, path, binding, state, guard, original


def _inputs(c):
    from phychem_mfm.phase1.v3_dev_store import TrainOnlyPackedStore
    from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
    from phychem_mfm.phase1.v3_latent_evaluation import cached_rows
    from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec, task_rows
    from phychem_mfm.phase1.v3_downstream_targets import atomization_rows, ATOMIZATION_TASK_ID
    from phychem_mfm.phase1.v31_normalization_routes import resolve_normalization_routes
    from tools.p_recipe.evaluate import feature_path
    from .dev_panel_inputs import task_descriptors
    native = c["readout_configuration"]
    protocol, panel = _read(REPO / "configs/p_recipe/protocol.json"), _read(REPO / "configs/dev_panel_v3.json")
    by_id = {row["task_id"]: row for row in panel["tasks"]}
    tasks = [TaskSpec(**{k: by_id[name][k] for k in
        ("task_id", "dataset_id", "field", "output_level", "error_metric", "pooling")})
        for name in protocol["scored_tasks"]]
    tasks = [replace(task, pooling="mean") for task in tasks]  # unchanged P readout rule
    if len(tasks) != 7 or any(t.output_level != "graph" for t in tasks):
        raise ValueError("Use the unchanged seven primary graph tasks")
    d3 = _read(c["d3_manifest"])
    if d3.get("status") != "RAW_COMPLETE" or d3.get("complete_source_population") is not True:
        raise ValueError("Closed complete native member D3 production required")
    with open(d3["membership_reference"]["path"], encoding="utf-8") as stream:
        members = [json.loads(line) for line in stream]
    descriptor = DownstreamDescriptorStore(c["descriptor_manifest"], c["library"])
    fields = [f for f in _read(c["training_view"])["fields"] if f["field_key"] in D3_FEATURE_FIELDS]
    normalizations = resolve_normalization_routes(_read(c["normalizations"]), fields, dataset="P_D")
    store = TrainOnlyPackedStore(native["store"], verify_digests=False)
    feature_c = native
    if native.get("diagnostic_feature_root"):
        from .layer_features import cached_layer_configuration
        feature_c = cached_layer_configuration(native, 6, output=native["output"])
    result = []
    for dataset in sorted({task.dataset_id for task in tasks}):
        path = feature_path(feature_c, dataset)
        if not path.is_file():
            raise FileNotFoundError("Retained final H0 unavailable; no encoder fallback: " + dataset)
        payload = torch.load(path, map_location="cpu", weights_only=True)
        cached = cached_rows(payload)
        view = GroupedTrainingView(store, dataset, "official" if dataset == "expansionrx" else "0", store.group_map)
        for task in (t for t in tasks if t.dataset_id == dataset):
            reader = atomization_rows if task.task_id == ATOMIZATION_TASK_ID else task_rows
            train, validation = reader(view, cached, task, role="train"), reader(view, cached, task, role="train_inner_validation")
            batches = {}
            for source in set((c["mlp_descriptor_value_source"], c["lightgbm_descriptor_value_source"])):
                if source not in ("raw", "frozen_train_standardized"):
                    raise ValueError("Explicit descriptor value source required")
                batches[source] = tuple(task_descriptors(rows, dataset, descriptor, members,
                    standardized=source == "frozen_train_standardized", normalization=normalizations)
                    for rows in (train, validation))
            result.append(dict(task=task, train=train, validation=validation, batches=batches,
                               n_ref=payload["n_ref"], d3_members=members))
    return result


def _save_cell(path, prediction, detail, guard, **extra):
    from phychem_mfm.phase1.v3_dev_evaluation_v2 import _pack
    guard.check(path.parent)
    temporary = path.with_suffix(".partial")
    torch.save(dict(prediction=_pack(prediction), detail=detail, **extra), temporary)
    temporary.replace(path)


def _cell_path(output, task, cell):
    return output / (task.task_id.replace(".", "_") + "__" + cell + ".pt")


def run_gpu(c, *, guard=None, inputs=None, probe=None):
    native, output, path, binding, state, guard, original = _context(c, False, guard)
    if state is not None and state["status"] in ("GPU_DEVELOPMENT_READOUTS_COMPLETE_WAITING_CPU", "COMPLETE"):
        return state
    from tools.p_recipe.evaluate import History
    probe = run_descriptor_probe if probe is None else probe
    state = state or dict(binding=binding, status="PREPARING", cells={}, decision_input=False,
        encoder_forward_repeated=False, A_reused_main_R3=True)
    _publish(path, state, guard)
    history = History(output / "probe_history.jsonl")
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    for data in (_inputs(c) if inputs is None else inputs):
        task = data["task"]
        if task.task_id + "/R3" not in original["files"]:
            raise ValueError("Original A must cover each unchanged primary task")
        for cell, branch in (("B_MLP", "B"), ("C", "C")):
            target = _cell_path(output, task, cell)
            if not target.exists():
                guard.check(output)
                history.cell = task.task_id + "/" + cell
                train_d, validation_d = data["batches"][c["mlp_descriptor_value_source"]]
                prediction, detail = probe(data["train"], data["validation"], task, train_d, validation_d,
                    branch=branch, capacity_policy=c["capacity_policy"],
                    descriptor_value_source=c["mlp_descriptor_value_source"], n_ref=data["n_ref"],
                    tracker=history, relative_std_floor=True, internal_epoch_selection=True, seed=0, device="cuda",
                    train_member_keys=train_d.member_uids, validation_member_keys=validation_d.member_uids)
                _save_cell(target, prediction, detail, guard)
            state["cells"][task.task_id + "/" + cell] = str(target)
            _publish(path, state, guard)
    state["status"] = "GPU_DEVELOPMENT_READOUTS_COMPLETE_WAITING_CPU"
    _publish(path, state, guard)
    return state


def run_cpu(c, *, guard=None, inputs=None, lightgbm=None, ridge=None, comparison=None):
    native, output, path, binding, state, guard, original = _context(c, True, guard)
    if state is not None and state["status"] == "COMPLETE":
        return state
    if state is None or state["status"] != "GPU_DEVELOPMENT_READOUTS_COMPLETE_WAITING_CPU":
        raise ValueError("Wait for the fixed B/C MLP cells")
    from phychem_mfm.phase1.v3_dev_evaluation import ridge_probe, compare_panel
    from phychem_mfm.phase1.v3_dev_evaluation_v2 import _unpack
    from .dev_panel_inputs import composition_rows
    lightgbm = run_lightgbm_probe if lightgbm is None else lightgbm
    ridge, comparison = ridge_probe if ridge is None else ridge, compare_panel if comparison is None else comparison
    threads = c["cpu_threads"]
    if type(threads) is not int or not 1 <= threads <= int(os.environ.get("SLURM_CPUS_PER_TASK", 0)):
        raise ValueError("CPU fits must use the actual demand-based allocation")
    torch.set_num_threads(threads)
    rows = list(_inputs(c) if inputs is None else inputs)
    for data in rows:
        task = data["task"]
        target = _cell_path(output, task, "B_LightGBM")
        if not target.exists():
            previous = torch.load(_cell_path(output, task, "B_MLP"), map_location="cpu", weights_only=True)
            train_d, validation_d = data["batches"][c["lightgbm_descriptor_value_source"]]
            guard.check(output)
            prediction, detail, model = lightgbm(data["train"], data["validation"], task, train_d, validation_d,
                optimization_molecule_uids=previous["detail"]["optimization_molecule_uids"],
                descriptor_value_source=c["lightgbm_descriptor_value_source"], n_jobs=threads,
                train_member_keys=train_d.member_uids, validation_member_keys=validation_d.member_uids)
            _save_cell(target, prediction, detail, guard, model_text=model.booster_.model_to_string())
        state["cells"][task.task_id + "/B_LightGBM"] = str(target)
        target = _cell_path(output, task, "composition_ridge")
        if not target.exists():
            guard.check(output)
            train, validation = (composition_rows(part, task.dataset_id, data["d3_members"])
                                 for part in (data["train"], data["validation"]))
            prediction, detail = ridge(train, validation, task, relative_std_floor=True)
            _save_cell(target, prediction, detail, guard)
        state["cells"][task.task_id + "/composition_ridge"] = str(target)
        _publish(path, state, guard)
    score_path = output / "scores.json"
    if not score_path.exists():
        reference = _read(native["reference_manifest"])
        tasks = [data["task"].task_id for data in rows]
        random = {task: _unpack(torch.load(reference["files"][task + "/R3"], map_location="cpu", weights_only=True)["prediction"])
                  for task in tasks}
        a_scores = _read(Path(native["output"]) / "scores.json")["R3"]
        summaries = {"A": a_scores}
        for cell in ("B_MLP", "B_LightGBM", "C", "composition_ridge"):
            actual = {task: _unpack(torch.load(state["cells"][task + "/" + cell],
                map_location="cpu", weights_only=True)["prediction"]) for task in tasks}
            individual = output / (cell + "_scores.json")
            if individual.exists():
                summaries[cell] = _read(individual)
            else:
                guard.check(output)
                summaries[cell] = comparison(actual, random, architecture_sha256="C1-0-reference",
                    reference_architecture_sha256="C1-0-reference", bootstrap_samples=1000,
                    confidence=.95, seed=20261025, retain_paired_samples=True, retain_task_samples=True)
                summaries[cell]["included_tasks"] = tasks
                _publish(individual, summaries[cell], guard)
        summaries["incremental_comparisons"] = {
            "C_vs_B_MLP": _contrast(summaries["C"], summaries["B_MLP"]),
            "C_vs_B_LightGBM": _contrast(summaries["C"], summaries["B_LightGBM"])}
        _publish(score_path, summaries, guard)
    state.update(status="COMPLETE", scores=str(score_path), A_reused_main_statistics=True,
                 recipe_selection_changed=False, final_benchmark_C1_complete=False)
    _publish(path, state, guard)
    return state


def _contrast(candidate, control):
    """Existing paired draws only; descriptive, with no arm/seed decision."""
    from phychem_mfm.phase1.p_recipe import paired_decision
    if candidate["paired_bootstrap"]["groups"] != control["paired_bootstrap"]["groups"]:
        raise ValueError("Section5 comparisons require the same native molecular bootstrap draws")
    def interval(a, b, draws_a, draws_b):
        result = paired_decision(a, b, draws_a, draws_b)
        return {key: result[key] for key in ("delta", "ci_lower", "ci_upper")}
    result = interval(candidate["mean_normalized_improvement"], control["mean_normalized_improvement"],
        candidate["paired_bootstrap"]["values"], control["paired_bootstrap"]["values"])
    result["tasks"] = {name: interval(candidate["tasks"][name]["normalized_improvement"],
        control["tasks"][name]["normalized_improvement"],
        candidate["paired_bootstrap"]["task_values"][name], control["paired_bootstrap"]["task_values"][name])
        for name in candidate["tasks"]}
    return dict(result, decision_input=False, additional_bootstrap_draws=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    c = _read(parser.parse_args().configuration)
    if c["phase"] not in ("gpu", "cpu"):
        raise ValueError("Explicit GPU or CPU development phase required")
    (run_gpu if c["phase"] == "gpu" else run_cpu)(c)


if __name__ == "__main__":
    main()
