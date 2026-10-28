"""Fixed-20-batch plus paired-500-update S execution-candidate acceptance.

Use run_supervised.py inside an owned single-GPU Slurm allocation. Synthetic or
--smoke results only validate the harness and cannot accept an A-class change.
Both models stay on one GPU; timings are diagnostic paired compute timings,
not standalone production throughput measurements.
"""
from __future__ import annotations

from dataclasses import asdict
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from profile_s_baseline import REPO, PUBLIC_PREREG, digest, save, source_bindings
from a_execution_runtime import (add_arguments, validate_arguments, load_references, bind_environment,
    stream_for, canonical_sha, corpus_receipt, append_json, guard_resources, install_termination_handler,
    prepare_deterministic_controls, apply_deterministic_controls)
from a_checkpoint_export import validate_export_destination, export_candidate_checkpoint


_RULE_DOCUMENT_REPO_PATH = "docs/model_v3/DECISION_RULES_A_ACCEPTANCE_V2_20261028.md"


def add_acceptance_arguments(parser):
    # Deliberately local to the paired tool. No Torch import before CUBLAS setup.
    parser.add_argument("--acceptance-version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--acceptance-rule-document", type=Path)
    parser.add_argument("--acceptance-rule-document-sha256")
    parser.add_argument("--acceptance-prereg-sha")
    parser.add_argument("--acceptance-rule-publication", type=Path)
    parser.add_argument("--acceptance-rule-publication-sha256")
    parser.add_argument("--fixed-batch-only", action="store_true",
        help="v2 old-cohort recheck only: original20 fixed batches, no500 and no full A qualification")


def _read_acceptance_metadata(path, expected_sha):
    import stat
    path = Path(path).absolute()
    if not isinstance(expected_sha, str) or not re.fullmatch("[0-9a-f]{64}", expected_sha):
        raise ValueError("Exact lower-case rule/publication raw SHA256 required")
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or before.st_uid != os.getuid() or not 0 < before.st_size <= 2 * 1024**2):
        raise ValueError("Owned ordinary bounded rule/publication metadata required")
    raw = path.read_bytes()
    after = path.lstat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_uid", "st_nlink")
    if (any(getattr(before, key) != getattr(after, key) for key in fields)
            or hashlib.sha256(raw).hexdigest() != expected_sha):
        raise ValueError("Rule/publication metadata changed")
    return {"path": str(path), "bytes": len(raw), "sha256": expected_sha}, raw


def bind_acceptance_rules(args):
    """Bind the existing actual Root publication format, without network claims."""
    version = getattr(args, "acceptance_version", "v1")
    names = ("acceptance_rule_document", "acceptance_rule_document_sha256",
             "acceptance_prereg_sha", "acceptance_rule_publication",
             "acceptance_rule_publication_sha256")
    values = {name: getattr(args, name, None) for name in names}
    fixed_only = getattr(args, "fixed_batch_only", False)
    if version == "v1":
        if fixed_only or any(value is not None for value in values.values()):
            raise ValueError("v2 rule inputs/fixed-only cannot be silently attached to v1")
        return None
    if version != "v2" or any(value is None for value in values.values()):
        raise ValueError("v2 requires the exact rule document and actual Root publication inputs")
    if not re.fullmatch("[0-9a-f]{40}", values["acceptance_prereg_sha"]):
        raise ValueError("Full immutable rule-publication commit required")
    if getattr(args, "smoke", False):
        raise ValueError("v2 scientific/recheck entry requires original20, not smoke")
    if fixed_only and (getattr(args, "smoke", False)
                       or getattr(args, "export_candidate_checkpoint", None) is not None):
        raise ValueError("v2 fixed-only must run original20, without smoke/export")
    doc_ref, doc_raw = _read_acceptance_metadata(values["acceptance_rule_document"],
                                                values["acceptance_rule_document_sha256"])
    pub_ref, pub_raw = _read_acceptance_metadata(values["acceptance_rule_publication"],
                                                values["acceptance_rule_publication_sha256"])
    pub = json.loads(pub_raw)
    repositories = [pub[key] for key in ("repository_full_name", "repository") if key in pub]
    if (not repositories or any(value != "mint258/MFM" for value in repositories)
            or pub.get("schema") != "model_v3_exact_tree_publication_actual_v1"
            or pub.get("public_code_sha") != values["acceptance_prereg_sha"]
            or not isinstance(pub.get("tree_sha"), str)
            or not re.fullmatch("[0-9a-f]{40}", pub["tree_sha"])
            or pub.get("public_branch_readback_verified") is not True
            or pub.get("public_Git_API_tree_readback_verified") is not True):
        raise ValueError("Actual exact-tree Root rule publication/readback differs")
    entries = pub.get("files")
    if not isinstance(entries, list):
        raise ValueError("Actual publication file list required")
    selected = [row for row in entries if row.get("path") == _RULE_DOCUMENT_REPO_PATH]
    blob_sha = hashlib.sha1(b"blob " + str(len(doc_raw)).encode("ascii") + b"\0" + doc_raw).hexdigest()
    if (len(selected) != 1 or selected[0].get("type") != "blob"
            or selected[0].get("mode") not in ("100644", "100755")
            or selected[0].get("sha") != blob_sha):
        raise ValueError("Exact public rule-document Git blob differs from actual raw bytes")
    checker = pub.get("checker_closure")
    if (not isinstance(checker, dict) or set(checker) != {"path", "bytes", "sha256"}
            or type(checker["bytes"]) is not int or checker["bytes"] <= 0):
        raise ValueError("Actual publication checker closure rawref required")
    checker_ref, _ = _read_acceptance_metadata(checker["path"], checker["sha256"])
    if checker_ref != checker:
        raise ValueError("Publication checker closure rawref changed")
    return {
        "schema": "model_v3_A_acceptance_rule_binding_v2", "version": "v2",
        "rule_document": doc_ref, "rule_publication": pub_ref,
        "public_rule_commit": values["acceptance_prereg_sha"], "public_rule_tree": pub["tree_sha"],
        "public_rule_blob": blob_sha, "public_rule_repository": repositories[0],
        "source_refs": {"rule_document": doc_ref, "Root_publication": pub_ref,
                        "publication_checker_closure": checker_ref},
        "publication_scope": "actual_Root_receipt_and_raw_blob_bound; Root_preflight_verifies_public_authority",
        "network_or_Git_verification_performed_by_child": False,
        "fixed_batch_only": fixed_only,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    add_acceptance_arguments(parser)
    parser.add_argument("--export-candidate-checkpoint", type=Path,
        help="Opt in H0-only export after full native20+500 gates and cleanup; fresh immediate child of --output")
    args = parser.parse_args()
    selected = validate_arguments(args, paired=True)
    args.acceptance_rule_binding = bind_acceptance_rules(args)
    if args.performance_execution is not None and args.export_candidate_checkpoint is not None:
        raise ValueError("New execution integration has no admitted H0 export adapter; keep diagnostic export disabled")
    args.export_candidate_checkpoint = validate_export_destination(args.export_candidate_checkpoint,
        output_root=args.output, repository_root=REPO)
    args.deterministic_controls_binding = prepare_deterministic_controls(args.deterministic_controls)
    import fcntl
    locks = Path("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks")
    args.output.mkdir(parents=True)
    install_termination_handler()
    with (locks / (selected + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            return run(args, selected)
        except BaseException as exc:
            if not (args.output / "run_status.json").exists():
                save(args.output / "run_status.json", {"status": "STARTUP_FAILED", "code_sha": args.code_sha,
                    "failure": {"type": type(exc).__name__, "message": str(exc)}, "resume_supported": False,
                    **({"acceptance_rules": args.acceptance_rule_binding}
                       if args.acceptance_rule_binding is not None else {})})
            raise


def run(args, uuid):
    # Rebind actual metadata even for direct callers; never trust a caller-filled binding dict.
    rule_binding = bind_acceptance_rules(args)
    import torch
    args.deterministic_controls_receipt = apply_deterministic_controls(args.deterministic_controls_binding)
    import wandb
    from phychem_mfm.model.v3_performance import (PerformanceOptions, build_performance_model,
        performance_forward_pretrain, execution_context, make_adamw)
    from phychem_mfm.training.v3_performance_acceptance import (floating_outputs, gradients, compare_tensors, trajectory_report,
        compare_gradients_v2, analytic_zero_gradient_parameters, a_gradient_contract_v2, a_gradient_contract_sha256_v2)
    from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1JointSchedule, Phase1LossPolicy
    from phychem_mfm.supervision import SupervisionConfig
    from phychem_mfm.training.losses import LossWeights
    from s_model_memory_v1 import build_memory_bounded_model
    from s_input_stream import SInputStream
    from runtime_monitor import gpu_observation, owned_output_bytes, owned_process_observation

    torch.set_num_threads(8)
    torch.set_num_interop_threads(1)
    if torch.cuda.device_count() != 1 or args.expected_gpu not in torch.cuda.get_device_name(0):
        raise RuntimeError("Actual GPU type/visibility differs")
    environment = bind_environment(args, uuid)
    gpu = environment["gpu"]
    options = PerformanceOptions(**json.loads(args.candidate_options.read_text()))
    if options.precision != "fp32":
        raise ValueError("This harness is only the A-class fp32 gate, not a B-class precision study")
    baseline_options = PerformanceOptions()
    reference, a4, config, bound_configuration = load_references(args)
    from a_execution_runtime import load_performance_execution, execution_request_reference, execution_observation
    integration = load_performance_execution(args, config, bound_configuration, resident_models=2)
    torch.manual_seed(args.seed)
    reference_model = build_memory_bounded_model(config).cuda().train()
    torch.manual_seed(args.seed)
    candidate_model = build_performance_model(config, options, execution=integration).cuda().train()
    left, right = reference_model.state_dict(), candidate_model.state_dict()
    if set(left) != set(right) or not all(torch.equal(left[name], right[name]) for name in left):
        raise RuntimeError("Execution candidate changed initial parameters/state keys")
    models = {"reference": reference_model, "candidate": candidate_model}
    fixed_only = bool(rule_binding and rule_binding["fixed_batch_only"])
    analytic_zero_names = ()
    if rule_binding is not None:
        proofs = {name: analytic_zero_gradient_parameters(model) for name, model in models.items()}
        shapes = [{row["name"]: row["shape"] for row in proof} for proof in proofs.values()]
        if shapes[0] != shapes[1]:
            raise ValueError("Reference/candidate analytic-zero Parameter sets/shapes differ")
        analytic_zero_names = tuple(row["name"] for row in proofs["reference"])
        rule_binding = {**rule_binding, "semantic_contract": a_gradient_contract_v2(),
            "semantic_contract_sha256": a_gradient_contract_sha256_v2(),
            "analytic_zero_parameter_proofs": proofs}
    runtime_options = {"reference": baseline_options, "candidate": options}
    weights = LossWeights.from_mapping({**reference["training"]["loss"], "denoise_sigma": .1,
                                       "geom_angle_std_deg": 0., "geom_bond_scale_std": 0.})
    policy = Phase1LossPolicy.from_mapping(a4["loss_policy"])
    supervision = SupervisionConfig.from_variant("S")
    batches, updates = (2, 2) if args.smoke else (20, 500)
    if fixed_only:
        updates = 0
    configuration = {**bound_configuration, **environment,
                     "model": config, "reference": asdict(baseline_options), "candidate": asdict(options),
                     "code_sha": args.code_sha, "prereg_sha": args.prereg_sha, "seed": args.seed,
                     "gpu": gpu, "optimizer": a4["optimizer"], "fixed_batches": batches,
                     "schedule": {"kind": "fixed_lr_numeric_equivalence", "lr": a4["optimizer"]["lr"]},
                     "trajectory_updates": updates, "smoke": args.smoke, "input": args.input,
                     "candidate_options_sha256": digest(args.candidate_options),
                     "torch_version": str(torch.__version__), "cuda_version": torch.version.cuda,
                     "logical_python": str(Path(sys.executable).absolute())}
    if rule_binding is not None:
        configuration["acceptance_rules"] = rule_binding
        configuration["acceptance_rule_source_refs"] = rule_binding["source_refs"]
        configuration["acceptance_scope"] = "V2_FIXED20_RECHECK_ONLY" if fixed_only else "V2_FULL20_AND500"
    if integration is not None:
        configuration["performance_execution_request"] = execution_request_reference(args)
        configuration["performance_execution"] = candidate_model.v3_performance_execution
    configuration["checkpoint_export"] = {"requested": args.export_candidate_checkpoint is not None,
        "destination": str(args.export_candidate_checkpoint) if args.export_candidate_checkpoint is not None else None,
        "scope": "H0_only_after_native20batch500update_gates_and_input_SDK_cleanup", "resume_supported": False}
    stream = None
    trackers = {}
    failure, final_status, cleanup_errors = None, "FAILED", []
    output_cap = int(os.environ.get("MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES", str(2 * 1024**3)))
    started = time.monotonic()
    science_finished = None
    checkpoint_export = None
    complete = False
    trajectory_started = False
    committed_trajectory_updates = 0
    final_stream_state = None
    try:
        stream = stream_for(args, reference)
        configuration["data_version"] = stream.bindings
        canonical = json.dumps(configuration, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        configuration["configuration_sha256"] = hashlib.sha256(canonical).hexdigest()
        save(args.output / "configuration.json", configuration)
        os.environ["WANDB_MODE"] = "offline"
        os.environ["WANDB_CACHE_DIR"] = str(args.output / "cache")
        os.environ["WANDB_DATA_DIR"] = str(args.output / "wandb_data")
        for name in models:
            trackers[name] = wandb.init(project="mfm_model_v3_development", mode="offline", dir=str(args.output),
                name=f"A_{name}_{os.environ['SLURM_JOB_ID']}", config={**configuration, "paired_role": name}, reinit="create_new")

        def loss_for(outputs, batch, update):
            return compute_phase1_loss(outputs, batch, None, supervision, weights,
                                       Phase1JointSchedule(), update, policy=policy)

        fixed = []
        first_receipt_sha = None
        all_input_receipts = []
        for number in range(batches):
            corpus = stream.next()
            receipt = corpus_receipt(corpus, stream.index)
            all_input_receipts.append(receipt["receipt_sha256"])
            if first_receipt_sha is None:
                first_receipt_sha = receipt["receipt_sha256"]
            batch = corpus.encoder_batch.to("cuda", non_blocking=True)
            snapshots = {}
            for name in ("reference", "candidate"):
                models[name].zero_grad(set_to_none=True)
                with execution_context(runtime_options[name]):
                    outputs = performance_forward_pretrain(models[name], batch, supervision.objectives)
                    loss = loss_for(outputs, batch, 0)
                    if not bool(torch.isfinite(loss.total)):
                        raise FloatingPointError("Nonfinite fixed-batch loss")
                    loss.total.backward()
                snapshots[name] = floating_outputs(outputs), gradients(models[name])
                del outputs, loss
            forward = compare_tensors(snapshots["reference"][0], snapshots["candidate"][0], tolerance=1e-5)
            gradient = (compare_tensors(snapshots["reference"][1], snapshots["candidate"][1], tolerance=1e-4)
                if rule_binding is None else compare_gradients_v2(snapshots["reference"][1], snapshots["candidate"][1],
                    analytic_zero_names=analytic_zero_names))
            fixed.append({"batch": number, "record_keys": list(corpus.record_keys), "forward": forward,
                          "input_receipt": receipt,
                          "gradient": gradient, "pass": forward["pass"] and gradient["pass"]})
            del snapshots
            stream.commit(corpus)
            append_json(args.output / "consumption.jsonl", {"phase": "fixed_batch", "batch": number,
                "input": receipt, "committed_stream": stream.state_dict()})
            append_json(args.output / "resources.jsonl", {"phase": "fixed_batch", "batch": number,
                **guard_resources(args.output, uuid)})
        fixed_gate = {"gate": "A_fixed_batch_equivalence", "batches": batches,
                      "pass": all(row["pass"] for row in fixed), "results": fixed}
        if rule_binding is not None:
            fixed_gate["acceptance_rules"] = rule_binding
        save(args.output / "fixed_batch_gate.json", fixed_gate)
        if fixed_only:
            final_status = "V2_FIXED20_RECHECK_PASSED" if fixed_gate["pass"] else "V2_FIXED20_RECHECK_FAILED"
            save(args.output / "summary.json", {"status": final_status,
                "scope": "V2_FIXED20_RECHECK_ONLY", "full_A_numeric_acceptance": False,
                "fixed_batch_pass": fixed_gate["pass"], "fixed_batches": batches,
                "trajectory_updates": 0, "trajectory_pass": None, "trajectory_executed": False,
                "old_trajectory_reuse_or_combined_qualification": "NOT_ADJUDICATED_BY_THIS_RUN",
                "configuration_sha256": configuration["configuration_sha256"],
                "code_sha": args.code_sha, "prereg_sha": args.prereg_sha, "gpu_uuid": uuid,
                "input": args.input, "smoke": False, "resume_supported": False,
                "candidate_options_sha256": configuration["candidate_options_sha256"],
                "fixed_input_receipts_sha256": canonical_sha(all_input_receipts),
                "acceptance_rules": rule_binding})
            science_finished = time.monotonic()
            return 0 if fixed_gate["pass"] else 2
        if not fixed_gate["pass"]:
            final_status = "FIXED_BATCH_GATE_FAILED"
            return 2
        stream.reset()
        first_trajectory = stream.next()
        if corpus_receipt(first_trajectory, stream.index)["receipt_sha256"] != first_receipt_sha:
            raise RuntimeError("Reset changed original first batch IDs/order/noise/input tensors")
        save(args.output / "stream_reset.json", {"same_first_input_sha256": first_receipt_sha,
            "committed_state_after_reset_before_update": stream.state_dict(), "workers_closed_before_reset": True})
        optimizers = {"reference": torch.optim.AdamW(reference_model.parameters(), **a4["optimizer"]),
                      "candidate": make_adamw(candidate_model, a4["optimizer"], options)}
        histories = {"reference": {}, "candidate": {}}
        consumed_records = 0
        trajectory_started = True
        for update in range(1, updates + 1):
            corpus = first_trajectory if update == 1 else stream.next()
            if update == 1:
                first_trajectory = None
            receipt = corpus_receipt(corpus, stream.index)
            batch = corpus.encoder_batch.to("cuda", non_blocking=True)
            order = ("reference", "candidate") if update % 2 else ("candidate", "reference")
            for name in order:
                torch.cuda.synchronize()
                tick = time.perf_counter()
                optimizer = optimizers[name]
                optimizer.zero_grad(set_to_none=True)
                with execution_context(runtime_options[name]):
                    outputs = performance_forward_pretrain(models[name], batch, supervision.objectives)
                    loss = loss_for(outputs, batch, update - 1)
                    if not bool(torch.isfinite(loss.total)):
                        raise FloatingPointError("Nonfinite trajectory loss")
                    loss.total.backward()
                    norm = torch.nn.utils.clip_grad_norm_(models[name].parameters(), 1.)
                    if not bool(torch.isfinite(norm)):
                        raise FloatingPointError("Nonfinite trajectory gradient")
                    optimizer.step()
                torch.cuda.synchronize()
                value = float(loss.total.detach().cpu())
                histories[name][update] = value
                row = {"optimizer_updates": update, "loss": value,
                       "gradient_norm": float(norm.detach().cpu()), "compute_seconds": time.perf_counter() - tick,
                       "base_records": len(corpus.logical_indices), "native_atoms": sum(corpus.native_atom_counts),
                       "consumed_base_records": consumed_records + len(corpus.logical_indices),
                       "input_receipt_sha256": receipt["receipt_sha256"],
                       "valid_label_counts": dict(loss.counts),
                       "peak_allocated_bytes": torch.cuda.max_memory_allocated()}
                trackers[name].log(row, step=update, commit=True)
                with (args.output / (name + "_history.jsonl")).open("a") as log:
                    log.write(json.dumps({**row, "valid_label_counts": loss.counts}, allow_nan=False) + "\n")
                    log.flush()
                    os.fsync(log.fileno())
                del outputs, loss
            stream.commit(corpus)
            committed_trajectory_updates = update
            consumed_records += len(corpus.logical_indices)
            append_json(args.output / "consumption.jsonl", {"phase": "trajectory", "optimizer_updates": update,
                "input": receipt, "committed_stream": stream.state_dict()})
            resource = guard_resources(args.output, uuid)
            if integration is not None:
                resource["performance_execution"] = execution_observation(candidate_model)
            append_json(args.output / "resources.jsonl", {"phase": "trajectory", "optimizer_updates": update, **resource})
            if update % 25 == 0 or update == updates:
                print(json.dumps({"updates": update, "consumed_base_records": consumed_records,
                    "foreign_gpu_risk_observed": resource["foreign_gpu_risk_observed"]}), flush=True)
        gate = trajectory_report(histories["reference"], histories["candidate"], expected_updates=updates)
        save(args.output / "trajectory_gate.json", gate)
        complete = args.input == "native_s" and not args.smoke and fixed_gate["pass"] and gate["pass"]
        final_status = "PAIRED_GATES_PASS" if gate["pass"] else "TRAJECTORY_GATE_FAILED"
        save(args.output / "summary.json", {"status": final_status, "full_A_numeric_acceptance": complete,
             "scope": "This execution candidate and batch stream only; all-GPU speed tables remain required",
             "configuration_sha256": configuration["configuration_sha256"], "code_sha": args.code_sha,
             "prereg_sha": args.prereg_sha, "gpu_uuid": uuid, "input": args.input, "smoke": args.smoke,
             "fixed_input_receipts_sha256": canonical_sha(all_input_receipts),
             "candidate_options_sha256": configuration["candidate_options_sha256"],
             "consumed_trajectory_base_records": consumed_records, "resume_supported": False,
             "timing_kind": "paired_two_resident_models_diagnostic_not_standalone_speed",
             "fixed_batch_pass": fixed_gate["pass"], "trajectory_pass": gate["pass"],
             **({"acceptance_rules": rule_binding, "acceptance_scope": "V2_FULL20_AND500"}
                if rule_binding is not None else {})})
        science_finished = time.monotonic()
        final_stream_state = stream.state_dict()
        return 0 if gate["pass"] else 2
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        if science_finished is None:
            science_finished = time.monotonic()
        finalization_started = time.monotonic()
        if stream is not None:
            try:
                stream.close()
            except BaseException as exc:
                cleanup_errors.append({"component": "stream", "type": type(exc).__name__, "message": str(exc)})
        for name, tracker in trackers.items():
            try:
                tracker.finish(exit_code=0 if final_status in ("PAIRED_GATES_PASS", "V2_FIXED20_RECHECK_PASSED") and not cleanup_errors else 1)
            except BaseException as exc:
                cleanup_errors.append({"component": name, "type": type(exc).__name__, "message": str(exc)})
        if complete and failure is None and not cleanup_errors:
            try:
                checkpoint_export = export_candidate_checkpoint(args.export_candidate_checkpoint,
                    output_root=args.output, repository_root=REPO, model=candidate_model,
                    optimizer=optimizers["candidate"], configuration=configuration, fixed_gate=fixed_gate,
                    trajectory_gate=gate, consumed_samples=consumed_records,
                    stream_state=final_stream_state, output_budget_bytes=output_cap)
            except BaseException as exc:
                cleanup_errors.append({"component": "candidate_checkpoint_export", "type": type(exc).__name__, "message": str(exc)})
        save(args.output / "run_status.json", {"status": final_status, "failure": failure,
             "cleanup_errors": cleanup_errors, "elapsed_seconds": time.monotonic() - started,
             "stream_cleanup": getattr(stream, "last_cleanup", None),
             "resume_supported": False,
             "scientific_elapsed_seconds": science_finished - started,
             "finalization_elapsed_seconds": time.monotonic() - finalization_started,
             "checkpoint_export": checkpoint_export,
             "job_id": os.environ["SLURM_JOB_ID"],
             **({"acceptance_rules": rule_binding,
                 "acceptance_scope": "V2_FIXED20_RECHECK_ONLY" if fixed_only else "V2_FULL20_AND500",
                 "trajectory_started": trajectory_started,
                 "committed_trajectory_updates": committed_trajectory_updates,
                 "trajectory_completed": updates > 0 and committed_trajectory_updates == updates}
                if rule_binding is not None else {})})
        if cleanup_errors and failure is None:
            raise RuntimeError("Paired evidence cleanup failed; inspect run_status.json")


if __name__ == "__main__":
    raise SystemExit(main())
