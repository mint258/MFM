"""D transport around the original P three-seed primary statistics producer.

New FT conditions consume the existing P scratch predictions. Controls already
closed in a D primary result are contrasted through retained draws, without
loading their original predictions or bootstrapping them again.
"""
import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import sys

from .finetune_entry import TASKS, validate as validate_finetune

AUTHORITY = "docs/d_recipe/USER_DIRECTIVE_20261123.md"
P_AUTHORITY = "docs/p_recipe/USER_DIRECTIVE_20261122B.md"
REPO = Path(__file__).resolve().parents[2]
P_TOOLS = REPO.parent / "MFM_p_recipe/tools/p_recipe"


def read(path):
    return json.loads(Path(path).read_text())


def validate_sources(c, *, reader=read):
    if (c.get("D_authority") != AUTHORITY or c.get("ready") is not True
            or c.get("registered_main_work_complete") is not True
            or c.get("selection_change_allowed") is not False
            or c.get("E1_seed_mean_draws", False) or c.get("frozen")):
        raise ValueError("Only descriptive D full FT after registered main work; reuse frozen scores separately")
    if (not c["groups"] or set(c["groups"]) != set(c["candidate_configurations"])
            or set(c["scratch"]) != set(TASKS) or set(c["scratch_configurations"]) != set(TASKS)
            or set(c["reference"]) != set(TASKS)
            or any(len(paths) != 1 for paths in c["reference"].values())):
        raise ValueError("Exact four-task primary inputs and original reference required")
    required, point_bindings, stores = set(), {}, set()
    tables = [(None, c["scratch"], c["scratch_configurations"])]
    tables += [(name, table, c["candidate_configurations"][name]) for name, table in c["groups"].items()]
    for name, predictions, configurations in tables:
        if set(predictions) != set(TASKS) or set(configurations) != set(TASKS):
            raise ValueError("Every source uses the original four tasks")
        for task in TASKS:
            paths, configs = predictions[task], configurations[task]
            if len(paths) != 3 or len(set(paths)) != 3 or len(configs) != 3 or len(set(configs)) != 3:
                raise ValueError("Three distinct original FT seeds0/1/2 in order required")
            for seed, (prediction, filename) in enumerate(zip(paths, configs)):
                source = reader(filename)
                if (source.get("authority") != P_AUTHORITY or source.get("kind") != "F"
                        or source.get("task") != task or type(source.get("seed")) is not int
                        or source["seed"] != seed or source.get("internal_split_seed") != 20261112
                        or source.get("bootstrap_seed") != 20261025
                        or str(Path(source["output"]) / "prediction.pt") != prediction):
                    raise ValueError("Source task, protocol, ordered seed or original prediction differs")
                if name is None:
                    binding = source["source_binding"]
                    if (source.get("mode") != "scratch"
                            or binding.get("role") != "architecture_only_random_initialization"
                            or binding.get("pretraining_samples_used") != 0):
                        raise ValueError("Reuse the same original P scratch protocol, never a pretrained baseline")
                else:
                    validate_finetune(source)
                    if source.get("registered_main_work_complete") is not True:
                        raise ValueError("Candidate FT must retain its actual main-work gate")
                    binding = source["source_binding"]
                    if name in point_bindings and point_bindings[name] != binding:
                        raise ValueError("A condition cannot mix different source checkpoints across tasks/seeds")
                    point_bindings[name] = binding
                stores.add((source["store"], source["reference_manifest"]))
                summary_path = str(Path(source["output"]) / "summary.json")
                summary = reader(summary_path)
                if summary.get("status") != "COMPLETE" or summary.get("configuration") != filename:
                    raise ValueError("Actual source FT producer must close with its exact configuration")
                required.add(summary_path)
    if len(stores) != 1 or set(c["required_complete_summaries"]) != required:
        raise ValueError("Source population or exact complete-summary dependencies differ")
    for contrast in c.get("contrasts", []):
        if (contrast["left"] not in c["groups"] or contrast["left"] == contrast["right"]
                or (not contrast.get("right_primary") and contrast["right"] not in c["groups"])):
            raise ValueError("Each contrast must use a new left condition and an explicit existing control")
    return point_bindings


def original_entry():
    sys.path[:0] = [str(P_TOOLS), str(REPO / "current")]
    spec = importlib.util.spec_from_file_location("d_original_P_F_statistics", P_TOOLS / "finetune_statistics_entry.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.paired_contrast = importlib.import_module("finetune_statistics").paired_contrast
    return module


@contextmanager
def installed_admission(entry, admit):
    previous = entry.require_cpu_admission
    try:
        entry.require_cpu_admission = admit
        yield
    finally:
        entry.require_cpu_admission = previous


def own_admission(c):
    sys.path.insert(0, str(P_TOOLS))
    import cpu_ssh_runtime as provider
    provider.verified_deadline(c)
    if os.environ.get("CUDA_VISIBLE_DEVICES"):
        raise ValueError("D FT statistics require an authenticated CPU SSH worker without CUDA")
    from .shared_admission import admit
    admit(c, [Path(c["output"])])


def run(c, *, entry=None, admit=None):
    from .shared_admission import atomic_json
    point_bindings = validate_sources(c)
    admit = own_admission if admit is None else admit
    admit(c)  # Before importing the original heavy scientific modules.
    entry = original_entry() if entry is None else entry
    output = Path(c["output"])
    definition = dict(groups=c["groups"], scratch=c["scratch"], reference=c["reference"],
                      contrasts=c.get("contrasts", []), point_bindings=point_bindings)
    complete = output / "D_complete.json"
    if complete.exists():
        result = read(complete)
        if result["definition"] != definition or result["run"] != c["run"]:
            raise ValueError("Closed D primary belongs to a different condition; preserve it")
        return result
    primary_path = output / "primary.json"
    marker = output / "primary_complete.json"
    if not marker.exists():
        with installed_admission(entry, admit):
            code = entry.run(c)
        if code == 75:
            return dict(status="CONTINUATION_REQUIRED", returncode=75)
        if code:
            raise RuntimeError("Original P FT statistics did not complete")
    primary = read(primary_path)
    if (primary.get("status") != "COMPLETE" or read(marker).get("status") != "COMPLETE"
            or primary["retained"]["identity"]["input_identity"] != entry.bindings(c)):
        raise ValueError("Reuse only the exact closed original primary input binding")
    # The P primary lock also serializes publication if two invocations race
    # after that producer has closed. It does not reopen prediction arrays.
    import fcntl
    with (output / "owner.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if complete.exists():
            result = read(complete)
            if result["definition"] != definition:
                raise ValueError("Closed D contrast definition changed")
            return result
        contrasts = []
        for row in c.get("contrasts", []):
            other = read(row["right_primary"]) if row.get("right_primary") else None
            for task in TASKS:
                contrasts.append(entry.paired_contrast(
                    primary, row["left"], row["right"], task, right_primary=other))
        atomic_json(output / "D_contrasts.json", dict(authority=AUTHORITY, contrasts=contrasts,
            descriptive_only=True, selection_change_allowed=False, new_bootstrap=False))
        result = dict(status="COMPLETE", run=c["run"], definition=definition,
            authority=AUTHORITY, primary=str(primary_path), contrasts=str(output / "D_contrasts.json"),
            point_estimand="three_seed_mean_MAE_and_shared_scratch_mean_MAE",
            CI_estimand="paired_molecular_scores_of_three_seed_mean_predictions",
            bootstrap_draws=1000, bootstrap_seed=20261025,
            existing_control_primary_reused=True, selection_change_allowed=False)
        atomic_json(complete, result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    args = parser.parse_args()
    result = run(read(args.configuration))
    print(json.dumps(result), flush=True)
    return result.get("returncode", 0)


if __name__ == "__main__":
    raise SystemExit(main())

