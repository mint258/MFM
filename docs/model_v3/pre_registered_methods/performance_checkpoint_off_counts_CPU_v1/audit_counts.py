"""CPU-only native TRAIN counts audit; call the frozen sampler, never a dataset."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import dataclass
import csv
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import time

MIB = 1 << 20
ROWS = 11_104_772
COUNT_BYTES = 44_419_088
TARGET = 500_000
UPDATES = 500
OUTPUT_CAP = 8 * MIB
INPUT_CAP = 128 * MIB
ROOT = Path("/share/home/zixiao/descriptor_analysis")
WORKTREE = ROOT / "MFM_model_v3_performance_integration_v1"
META_CAP = 2 * MIB


def require(condition, message):
    if not condition:
        raise ValueError(message)


def deadline_check(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError("Counts audit exceeded its bounded wall time")


def file_identity(path):
    p = Path(path)
    value = p.lstat()
    require(stat.S_ISREG(value.st_mode) and not p.is_symlink()
            and value.st_uid == 1278 and value.st_nlink == 1,
            "Owned ordinary single-link input required: " + str(p))
    require(p.resolve(strict=True) == p.absolute(), "Aliased input path")
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def bound_ref(ref, *, maximum=META_CAP, deadline):
    require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"},
            "Exact raw-reference fields required")
    p = Path(ref["path"])
    require(p.is_absolute() and type(ref["bytes"]) is int
            and 0 < ref["bytes"] <= maximum, "Invalid bounded raw-reference size")
    require(type(ref["sha256"]) is str and len(ref["sha256"]) == 64
            and all(c in "0123456789abcdef" for c in ref["sha256"]), "Invalid SHA256")
    before = file_identity(p)
    require(before[2] == ref["bytes"], "Input byte count differs")
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        for block in iter(lambda: handle.read(MIB), b""):
            deadline_check(deadline)
            digest.update(block)
    require(file_identity(p) == before, "Input changed while hashing")
    require(digest.hexdigest() == ref["sha256"], "Input SHA256 differs: " + str(p))
    return {"reference": ref, "identity": list(before)}


def load_json(ref, *, deadline):
    bound_ref(ref, deadline=deadline)
    value = json.loads(Path(ref["path"]).read_bytes())
    require(type(value) is dict, "Metadata object required")
    return value


def write_json(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    require(len(raw) <= META_CAP, "Output JSON exceeds 2 MiB")
    with Path(path).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def output_ref(path):
    p = Path(path)
    raw = p.read_bytes()
    return {"path": str(p), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def output_size(directory):
    total = 0
    for p in Path(directory).iterdir():
        identity = file_identity(p)
        total += identity[2]
    require(total <= OUTPUT_CAP, "Counts audit output exceeds 8 MiB")
    return total


def derived_views(loader_source, reference):
    """Read the actual inherited constructor recipe; never instantiate its views."""
    tree = ast.parse(Path(loader_source).read_bytes(), filename=str(loader_source))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "FullCorpusViewsDataset")
    init = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                and node.name == "__init__")
    loops = [node for node in ast.walk(init) if isinstance(node, ast.For)
             and isinstance(node.target, ast.Tuple)
             and [getattr(x, "id", None) for x in node.target.elts] == ["mode", "level"]]
    require(len(loops) == 1 and isinstance(loops[0].iter, ast.Tuple),
            "Unrecognized frozen native-view constructor")
    result = []
    for pair in loops[0].iter.elts:
        require(isinstance(pair, ast.Tuple) and len(pair.elts) == 2
                and isinstance(pair.elts[0], ast.Constant)
                and isinstance(pair.elts[1], ast.Name), "Native-view recipe changed")
        name, level_name = pair.elts[0].value, pair.elts[1].id
        require(type(name) is str and level_name in ("topology_level", "geometry_level"),
                "Unsupported native view")
        result.append({"mode": name, "level_argument": level_name,
                       "level": reference["views"][level_name]})
    calls = [node for node in ast.walk(loops[0]) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "DegradeConfig"]
    require(len(calls) == 1, "Native DegradeConfig constructor differs")
    keywords = {item.arg: item.value for item in calls[0].keywords}
    require(isinstance(keywords.get("mode"), ast.Name) and keywords["mode"].id == "mode",
            "Native mode no longer comes from the constructor recipe")
    for key in ("topo_delete_frac", "geom_angle_std_deg", "geom_bond_scale_std"):
        require(isinstance(keywords.get(key), ast.Constant)
                and keywords[key].value == 0.0, "Native count-preserving view policy changed")
    require(len(result) == reference["sampler"]["padded_cost_multiplier"]
            and len({row["mode"] for row in result}) == len(result),
            "Sampler multiplier differs from actual distinct native views")
    return result


def checked_import(name, expected):
    module = importlib.import_module(name)
    require(Path(module.__file__).resolve(strict=True) == Path(expected).resolve(strict=True),
            "Imported module came from a different runtime: " + name)
    return module


@dataclass(frozen=True)
class CountsOnlyMetadata:
    """Metadata facade for CountIndex; explicitly NOT a native record provider."""
    atoms_path: Path
    rows: int
    content_sha256: str
    _atoms_identity: tuple

    def __len__(self):
        return self.rows


def summarize_global(counts, multiplier, sampler_settings, deadline):
    import numpy as np

    histogram = Counter()
    for start in range(0, ROWS, 1 << 20):
        deadline_check(deadline)
        values, frequencies = np.unique(counts[start:start + (1 << 20)], return_counts=True)
        for value, frequency in zip(values, frequencies):
            histogram[int(value)] += int(frequency)
        require(len(histogram) <= 65536, "Count histogram exceeds its finite metadata bound")
    require(sum(histogram.values()) == ROWS and 0 not in histogram, "Invalid native atom counts")
    maximum = max(histogram)
    return histogram, {
        "records": ROWS, "min_native_atoms": min(histogram), "max_native_atoms": maximum,
        "total_native_atoms": sum(n * count for n, count in histogram.items()),
        "views_per_base_record": multiplier,
        "maximum_singleton_padded_cost": multiplier * maximum * maximum,
        "records_with_singleton_cost_above_500k":
            sum(count for n, count in histogram.items() if multiplier * n * n > TARGET),
        "records_at_sampler_native_atom_limit":
            sum(count for n, count in histogram.items() if n >= sampler_settings["max_native_atoms"]),
        "records_above_sampler_native_atom_limit":
            sum(count for n, count in histogram.items() if n > sampler_settings["max_native_atoms"]),
        "singleton_over_budget_policy": "singleton_no_discard",
        "500k_is_a_target_not_an_absolute_singleton_cap": True,
        "global_max_in_first_500_updates": None,
    }


def original_prefix(sampler, count_index, multiplier, destination, global_max, deadline):
    # No record IDs, molecule IDs, logical ordinal lists or target values are exported.
    fields = ["update", "base_records", "physical_graphs", "native_atoms", "physical_atoms",
              "max_native_atoms", "dense_batch", "dense_nodes", "padded_nodes",
              "padded_cost", "valid_pairs", "oversized_singleton",
              "two_saved_distance_buffers_all_six_layers_bytes"]
    ordered_hash, counts_hash = hashlib.sha256(), hashlib.sha256()
    seen = set()
    totals = {"updates": 0, "base_records": 0, "native_atoms": 0, "physical_graphs": 0,
              "physical_atoms": 0, "padded_cost": 0, "oversized_singleton_updates": 0}
    maxima = {name: 0 for name in ("base_records", "physical_graphs", "native_atoms",
                                  "max_native_atoms", "padded_cost",
                                  "two_saved_distance_buffers_all_six_layers_bytes")}
    shapes = Counter()
    first20 = None
    max_seen = 0
    iterator = iter(sampler)
    with Path(destination).open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for update in range(1, UPDATES + 1):
            deadline_check(deadline)
            batch = next(iterator)
            require(type(batch) is list and 0 < len(batch) <= sampler.max_molecules,
                    "Original sampler emitted an invalid batch")
            require(all(type(i) is int and 0 <= i < ROWS and i not in seen for i in batch)
                    and len(set(batch)) == len(batch), "Duplicate or out-of-population prefix ordinal")
            seen.update(batch)
            native = [count_index.ref(i).native_n_atoms for i in batch]
            n, maximum = len(batch), max(native)
            atoms = sum(native)
            cost = multiplier * n * maximum * maximum
            oversized = cost > TARGET or atoms > sampler.max_native_atoms
            require(not oversized or n == 1, "Over-budget batch is not an original explicit singleton")
            ordered_hash.update(struct.pack("<I", n))
            counts_hash.update(struct.pack("<I", n))
            for logical, count in zip(batch, native):
                ordered_hash.update(struct.pack("<Q", logical))
                counts_hash.update(struct.pack("<I", count))
            row = {
                "update": update, "base_records": n, "physical_graphs": multiplier * n,
                "native_atoms": atoms, "physical_atoms": multiplier * atoms,
                "max_native_atoms": maximum, "dense_batch": multiplier * n, "dense_nodes": maximum,
                "padded_nodes": multiplier * n * maximum, "padded_cost": cost,
                "valid_pairs": multiplier * sum(count * count for count in native),
                "oversized_singleton": oversized,
                # Saved SiLU input and second Linear input; a component, NOT a peak upper bound.
                "two_saved_distance_buffers_all_six_layers_bytes": 2 * 6 * cost * 512 * 4,
            }
            writer.writerow(row)
            sampler.commit_batch(batch)
            require(sampler.samples_consumed == len(seen), "Committed sampler exposure differs")
            for key in ("base_records", "native_atoms", "physical_graphs", "physical_atoms", "padded_cost"):
                totals[key] += row[key]
            totals["updates"] = update
            totals["oversized_singleton_updates"] += int(oversized)
            for key in maxima:
                maxima[key] = max(maxima[key], row[key])
            max_seen = max(max_seen, maximum)
            shapes[(multiplier * n, maximum)] += 1
            if update == 20:
                first20 = {"updates": 20, "totals": dict(totals),
                           "ordered_logical_prefix_sha256": ordered_hash.hexdigest(),
                           "ordered_counts_prefix_sha256": counts_hash.hexdigest(),
                           "sampler_state": sampler.state_dict()}
            if update % 20 == 0:
                handle.flush()
                require(handle.tell() <= OUTPUT_CAP // 2, "Prefix CSV exceeds its finite bound")
        handle.flush()
        os.fsync(handle.fileno())
    require(totals["updates"] == UPDATES and len(seen) == totals["base_records"], "Incomplete prefix")
    return {
        "totals": totals, "maxima": maxima, "first20": first20,
        "final_sampler_state": sampler.state_dict(),
        "ordered_logical_prefix_sha256": ordered_hash.hexdigest(),
        "ordered_counts_prefix_sha256": counts_hash.hexdigest(),
        "dense_shapes": [{"batch": b, "nodes": n, "updates": count}
                         for (b, n), count in sorted(shapes.items())],
        "global_max_in_first_500_updates": max_seen == global_max,
        "all_population_records_enumerated": False,
        "prefix_ordinal_uniqueness_checked": True,
        "input_population_filtered": False,
        "prefix_shape_scope": "exact_original_sampler_counts_projection_no_model_forward",
        "fixed20_reset_to_trajectory_origin": "first20 is the first20 of this same 500-update prefix",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--inputs-sha256", required=True)
    parser.add_argument("--source-pins-sha256", required=True)
    parser.add_argument("--expected-node", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--max-wall-seconds", type=int, default=600)
    args = parser.parse_args()
    started = time.monotonic()
    require(30 <= args.max_wall_seconds <= 600, "Counts audit wall cap must be 30..600 seconds")
    deadline = started + args.max_wall_seconds
    require(os.name == "posix" and os.getuid() == 1278 and os.environ.get("SLURM_JOB_ID"),
            "Actual UID1278 Slurm CPU child required")
    node = socket.gethostname().split(".")[0]
    require(node == args.expected_node and node in
            {"compute-0-2", *("compute-0-" + str(i) for i in range(8, 20))},
            "Actual expected CPU node required")
    require(int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16
            and len(os.sched_getaffinity(0)) >= 16, "At least16 actual allocated CPUs required")
    require(os.environ.get("CUDA_VISIBLE_DEVICES") in ("", "-1"), "CUDA must be hidden for this CPU child")
    output = args.output_root.absolute()
    require(not output.exists() and not output.is_symlink(), "Fresh output root required")
    output = output.resolve(strict=False)
    require(any(output.is_relative_to(ROOT / "runs" / name)
                for name in ("model_v3_20261025", "model_v3_20261026")),
            "Counts outputs must remain under Root-owned model runs")
    require(output.parent.is_dir(), "Root must create the parent output directory")
    output.mkdir()
    result = {
        "schema": "model_v3_native_TRAIN_checkpoint_off_counts_audit_v1",
        "status": "FAILED_HOLD_PRESERVED", "failure": None,
        "job_id": os.environ["SLURM_JOB_ID"], "node": node, "uid": os.getuid(),
        "sys_executable": sys.executable, "python_version": sys.version,
        "expected_frozen_code_identity": "9e16d4c5a15c558051499d3dc0c55c9bd3787734",
        "model_dataset_loader_or_optimizer_created": False, "LMDB_Arrow_or_labels_opened": False,
        "CPU_counts_metadata_opened": False, "CUDA_initialized": False,
        "GPU_capacity_or_A_numeric_acceptance": False,
        "actual_parent_C0_not_proven_by_this_child": True,
    }
    count_index = counts = count_mapping = None
    try:
        package = Path(__file__).resolve().parent
        pins_path = package / "source_pins.json"
        pins_ref = {"path": str(pins_path), "bytes": pins_path.stat().st_size,
                    "sha256": args.source_pins_sha256}
        pins = load_json(pins_ref, deadline=deadline)
        require(pins["schema"] == "model_v3_checkpoint_off_counts_source_pins_v1",
                "Unexpected source manifest")
        own_before = [bound_ref(ref, deadline=deadline) for ref in pins["files"]]
        input_ref = {"path": str(args.inputs.absolute()), "bytes": args.inputs.stat().st_size,
                     "sha256": args.inputs_sha256}
        require(input_ref in pins["files"], "Inputs are outside the frozen package")
        inputs = load_json(input_ref, deadline=deadline)
        require(inputs["schema"] == "model_v3_checkpoint_off_counts_inputs_v1"
                and inputs["seed"] == 0 and inputs["epoch"] == 0 and inputs["updates"] == UPDATES
                and inputs["target_max_padded_cost"] == TARGET
                and inputs["runtime_root"] == str(WORKTREE), "Unsupported counts audit policy")
        refs = inputs["references"]
        source_before = {name: bound_ref(ref, deadline=deadline) for name, ref in refs.items()}
        manifest = load_json(refs["manifest"], deadline=deadline)
        snapshot = load_json(refs["shard_snapshot"], deadline=deadline)
        reference = load_json(refs["B1_reference"], deadline=deadline)
        atom_ref = inputs["atom_counts"]
        declared_atoms = [row for row in manifest["references"]
                          if row["role"] == "train" and row["kind"] == "atom_counts"]
        require(len(declared_atoms) == 1 and atom_ref ==
                {key: declared_atoms[0][key] for key in ("path", "bytes", "sha256")},
                "Counts input differs from the original manifest")
        require(manifest["status"] == "INPUT_METADATA_CLOSED_NATIVE_SAMPLE_PASS"
                and manifest["roles"]["train"]["records"] == ROWS
                and declared_atoms[0]["rows"] == ROWS
                and atom_ref["bytes"] == COUNT_BYTES == ROWS * 4
                and reference["train_records"] == ROWS
                and reference["seed"] == inputs["seed"]
                and reference["input_manifest_sha256"] == refs["manifest"]["sha256"],
                "Bound TRAIN population differs")
        require(snapshot["status"] == "READ_ONLY_NATIVE_SHARD_SNAPSHOT",
                "Original snapshot metadata status differs")
        require(reference["frozen_protocol_reference"] ==
                {"path": refs["frozen_protocol"]["path"], "sha256": refs["frozen_protocol"]["sha256"]},
                "Frozen reference protocol differs")
        total_inputs = sum(ref["bytes"] for ref in refs.values()) + atom_ref["bytes"]
        total_inputs += input_ref["bytes"] + pins_ref["bytes"] + sum(ref["bytes"] for ref in pins["files"])
        require(total_inputs <= INPUT_CAP, "Conservative selected inputs exceed 128 MiB")
        count_before = bound_ref(atom_ref, maximum=64 * MIB, deadline=deadline)
        result["CPU_counts_metadata_opened"] = True

        import numpy as np
        import torch
        require(not torch.cuda.is_initialized(), "CPU counts audit found an initialized CUDA runtime")
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        module_refs = {
            "phychem_mfm.phase1.full_corpus_loader": "full_corpus_loader",
            "phychem_mfm.phase1.identity": "identity",
            "s_native_adapter_v1": "s_native_adapter_v1",
            "s_native_adapter_v2": "s_native_adapter_v2",
            "prepare": "prepare",
        }
        modules = {name: checked_import(name, refs[key]["path"]) for name, key in module_refs.items()}
        loader = modules["phychem_mfm.phase1.full_corpus_loader"]
        adapter = modules["s_native_adapter_v2"]
        identity = modules["phychem_mfm.phase1.identity"].canonical_hash
        require(adapter.CountIndex is modules["s_native_adapter_v1"].CountIndex,
                "Native CountIndex alias differs")
        require(modules["prepare"].ROOT == ROOT / "runs/sprime_s_convergence_20261013",
                "Native metadata root differs")
        views = derived_views(refs["full_corpus_loader"]["path"], reference)
        multiplier = len(views)
        settings = dict(reference["sampler"])
        require(settings == {"atom_bucket_width": 16, "block_size": 4096,
                             "max_molecules": 512, "max_native_atoms": 65536,
                             "max_padded_cost": 8000000, "padded_cost_multiplier": multiplier},
                "Original sampler metadata changed")
        settings["max_padded_cost"] = TARGET
        content = identity({"input_manifest_sha256": refs["manifest"]["sha256"], "role": "train"})
        facade = CountsOnlyMetadata(Path(atom_ref["path"]), ROWS, content,
                                    adapter.identity(atom_ref["path"]))
        require(tuple(count_before["identity"]) == facade._atoms_identity, "Counts input identity drifted")
        count_index = adapter.CountIndex(facade)
        original = loader.BlockAtomBatchSampler(count_index, seed=0, epoch=0, **reference["sampler"])
        sampler = loader.BlockAtomBatchSampler(count_index, seed=0, epoch=0, **settings)
        require(sampler.contract["oversized_molecule_policy"] == "singleton_no_discard"
                and sampler.contract["partial_block_and_epoch_batches"] == "retain"
                and sampler.contract_sha256 != original.contract_sha256,
                "Counts audit must retain original sampling rules with a distinct500k contract")

        counts = np.memmap(atom_ref["path"], dtype="<u4", mode="r", shape=(ROWS,))
        histogram, global_stats = summarize_global(counts, multiplier, settings, deadline)
        histogram_path = output / "global_native_atom_count_histogram.csv"
        with histogram_path.open("x", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["native_atoms", "records", "views_per_record", "singleton_padded_cost",
                             "above_500k", "two_saved_distance_buffers_all_six_layers_bytes"])
            for n, frequency in sorted(histogram.items()):
                singleton_cost = multiplier * n * n
                writer.writerow([n, frequency, multiplier, singleton_cost, singleton_cost > TARGET,
                                 2 * 6 * singleton_cost * 512 * 4])
            handle.flush()
            os.fsync(handle.fileno())
        prefix_path = output / "sampler_seed0_epoch0_first500_updates_500k.csv"
        prefix = original_prefix(sampler, count_index, multiplier, prefix_path,
                                 global_stats["max_native_atoms"], deadline)
        global_stats["global_max_in_first_500_updates"] = prefix["global_max_in_first_500_updates"]
        result.update({
            "source_package": pins_ref, "inputs": input_ref,
            "source_before": source_before, "own_source_before": own_before,
            "selected_inputs_bytes_conservative_with_duplicate_small_refs": total_inputs,
            "atom_counts": count_before, "dtype": "<u4", "view_recipe_from_frozen_source": views,
            "index_content_sha256": content,
            "original_8M_contract": original.contract, "original_8M_contract_sha256": original.contract_sha256,
            "new_500k_contract": sampler.contract, "new_500k_contract_sha256": sampler.contract_sha256,
            "no_8M_prefix_or_201216_record_total_reused": True,
            "global_counts": global_stats, "new_prefix": prefix,
            "artifacts": {"global_histogram": output_ref(histogram_path), "prefix": output_ref(prefix_path)},
            "memory_component_scope":
                "2 SiLU/Linear saved512-wide F32 buffers x6 layers; NOT a model or allocator peak upper bound",
            "unmeasured_extra_memory":
                ["other distance tensors", "QKV/attention", "FFN/LayerNorm", "S/other heads",
                 "gradients", "Adam states", "resident reference model", "workspace/context/allocator"],
            "required_future_GPU_guard": "unchanged original85percent actual process-memory guard",
            "runtime": {"numpy_version": np.__version__, "torch_version": str(torch.__version__),
                        "torch_threads": torch.get_num_threads(),
                        "torch_interop_threads": torch.get_num_interop_threads(),
                        "allowed_cpus": sorted(os.sched_getaffinity(0))},
        })
        # Close both read-only mappings before final file/source revalidation.
        count_mapping = count_index._atoms
        count_index.close()
        if count_mapping is not None:
            count_mapping._mmap.close()
            count_mapping = None
        counts._mmap.close()
        counts = None
        result["atom_counts_after"] = bound_ref(atom_ref, maximum=64 * MIB, deadline=deadline)
        result["source_after"] = {name: bound_ref(ref, deadline=deadline) for name, ref in refs.items()}
        result["own_source_after"] = [bound_ref(ref, deadline=deadline) for ref in pins["files"]]
        result["source_package_after"] = bound_ref(pins_ref, deadline=deadline)
        require(result["atom_counts_after"] == count_before
                and result["source_after"] == source_before
                and result["own_source_after"] == own_before, "Source or counts input changed")
        require(not torch.cuda.is_initialized(), "CPU-only audit initialized CUDA")
        remaining_count_descriptors = []
        for fd in Path("/proc/self/fd").iterdir():
            try:
                if os.readlink(fd) == atom_ref["path"]:
                    remaining_count_descriptors.append(fd.name)
            except FileNotFoundError:
                continue
        result["counts_descriptors_closed"] = not remaining_count_descriptors
        require(result["counts_descriptors_closed"], "Counts descriptor remains open")
        deadline_check(deadline)
        result["status"] = "COUNTS_AUDIT_COMPLETE_PENDING_ACTUAL_CPU_OUTER_C0"
    except BaseException as exc:
        result["failure"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if count_index is not None:
            mapping = count_index._atoms
            count_index.close()
            if mapping is not None:
                mapping._mmap.close()
        if count_mapping is not None:
            count_mapping._mmap.close()
        if counts is not None:
            counts._mmap.close()
        result["elapsed_seconds"] = time.monotonic() - started
        result["output_bytes_before_RESULT"] = output_size(output)
        write_json(output / "RESULT.json", result)
        output_size(output)
    print(json.dumps({"status": result["status"], "failure": result["failure"],
                      "result": str(output / "RESULT.json")}, sort_keys=True), flush=True)
    return 0 if result["failure"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
