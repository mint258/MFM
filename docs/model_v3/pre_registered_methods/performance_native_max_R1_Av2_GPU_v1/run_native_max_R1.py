"""One native global-maximum singleton, one model, 2+20 real updates.

Capacity-shape observation only. This is neither the original S sampler nor an
A 20/500 qualifier, ABBA member, universal 8M bound or automatic-selection proof.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace

from native_max_input import (B, N, ROOT, HERE, CODE, PUBLIC, GPU, KIND, MAX_N, VIEWS,
    require, deadline_check, reference, read, write, verify_sources, select_maximum, open_native_input)

# One existing immutable namespace; no modules/path switching between runtimes.
sys.path.insert(0, str(ROOT / 'tools/model_v3'))
from profile_s_baseline import REPO
from a_execution_runtime import (prepare_deterministic_controls, apply_deterministic_controls,
    bind_environment, load_references, load_performance_execution, execution_request_reference,
    execution_observation, canonical_sha, corpus_receipt, append_json, guard_resources,
    install_termination_handler)
require(REPO == ROOT, 'Actual original performance runtime origin differs')


def strict_resources(output, *, expect_owned):
    """Validate the actual existing monitor row; unknown is not zero."""
    row = guard_resources(output, GPU)
    gpu = row['gpu_observation']
    require(gpu['uuid'] == GPU and type(gpu['total_bytes']) is int and gpu['total_bytes'] > 0,
            'Known exact physical GPU capacity required')
    apps = gpu['compute_processes']
    require(type(apps) is list and type(gpu['foreign_processes']) is list,
            'Actual monitor process lists required')
    for item in apps:
        require(type(item['pid']) is int and item['pid'] > 0 and type(item['own']) is bool
                and type(item['used_memory_bytes']) is int and item['used_memory_bytes'] >= 0,
                'Unknown NVML ownership or memory cannot close capacity')
    foreign = [item for item in apps if not item['own']]
    require(foreign == gpu['foreign_processes'] and not foreign
            and row['foreign_gpu_risk_observed'] is False,
            'No selected-UUID foreign compute context is permitted')
    owned = [item for item in apps if item['own']]
    require(not expect_owned or owned, 'Actual model allocation lacks an owned NVML observation')
    for name in ('peak_allocated_bytes', 'peak_reserved_bytes', 'process_rss_sum_bytes', 'output_bytes'):
        require(type(row[name]) is int and row[name] >= 0, 'Unknown runtime resource quantity')
    require(max(sum(item['used_memory_bytes'] for item in owned),
                row['peak_allocated_bytes'], row['peak_reserved_bytes']) <= .85 * gpu['total_bytes'],
            'Original physical GPU85% cap exceeded')
    return row


def actual_shape(corpus):
    import torch
    batch = corpus.encoder_batch
    require(batch.pos.device.type == batch.x.device.type == batch.batch.device.type == 'cpu'
            and batch.pos.dtype == torch.float32 and batch.x.dtype == torch.long,
            'Actual native CPU/F32 position and native element tensors required')
    counts = torch.bincount(batch.batch, minlength=VIEWS).tolist()
    require(counts == [MAX_N] * VIEWS and int(batch.pos.shape[0]) == VIEWS * MAX_N
            and batch.pos.shape[1] == 3 and torch.isfinite(batch.pos).all().item(),
            'All three complete native maximum views must survive actual collation')
    require(batch.sample_type_id.reshape(-1).tolist() == [0, 1, 2],
            'Original clean/geom/topo graph association differs')
    edge = getattr(batch, 'edge_index', None)
    return dict(base_records=1, physical_graphs=VIEWS, native_atoms=MAX_N,
        physical_atoms=VIEWS * MAX_N, dense_shape=[VIEWS, MAX_N],
        padded_cost=VIEWS * MAX_N**2, valid_dense_ordered_pairs_including_self=VIEWS * MAX_N**2,
        valid_dense_ordered_pairs_excluding_self=VIEWS * MAX_N * (MAX_N - 1),
        actual_input_edge_columns=None if edge is None else int(edge.shape[1]),
        input_edge_count_is_not_a_head_label_denominator=True)


def optimizer_metadata(optimizer):
    """Shapes/storage population only; never moment values or checkpoint files."""
    tensor_bytes, tensor_count = {}, 0
    for state in optimizer.state.values():
        for value in state.values():
            if hasattr(value, 'numel') and hasattr(value, 'element_size'):
                device = str(value.device)
                tensor_bytes[device] = tensor_bytes.get(device, 0) + int(value.numel()) * value.element_size()
                tensor_count += 1
    return dict(parameter_state_entries=len(optimizer.state), state_tensor_count=tensor_count,
                logical_state_tensor_bytes_by_device=tensor_bytes, values_exported=False)


def run(args):
    started = time.monotonic()
    total_deadline = started + 6600  # Original supervisor6900, reserve300.
    preparation_deadline = min(total_deadline, started + 600)
    stream = tracker = None
    failure, cleanup_errors = None, []
    status = 'FAILED'
    steps_completed = 0
    resources = []
    selected_ref = configuration_ref = source_after = first_receipt = None
    final_optimizer = None
    configuration = {}
    selection = None
    pin = None
    summary_payload = None
    last_SDK_row = None
    tracking_run_id = SDK_directory = SDK_descriptor = expected_summary_ref = None
    SDK_finish_returned = False
    SDK_finish_exit_code = None
    durable_step_rows = SDK_log_calls_returned = 0
    try:
        pin, deps, root_frames = verify_sources(args.pins_sha256, preparation_deadline)
        selection, selected_ref = select_maximum(deps, args.output, preparation_deadline)
        # CPU count selection and all immutable-source checks above use stdlib only.
        runtime = SimpleNamespace(output=args.output, seed=0, input='native_s', workers=0,
            code_sha=CODE, prereg_sha=PUBLIC, expected_gpu='5090', max_padded_cost=8_000_000,
            candidate_options=Path(deps['raw_refs']['candidate_options']['path']),
            reference_config=Path(deps['raw_refs']['reference_config']['path']),
            shard_snapshot_sha256=deps['raw_refs']['S_original_snapshot']['sha256'],
            performance_execution=Path(deps['raw_refs']['manual_execution']['path']),
            performance_execution_sha256=deps['raw_refs']['manual_execution']['sha256'])
        runtime.deterministic_controls_binding = prepare_deterministic_controls(True)
        import torch
        runtime.deterministic_controls_receipt = apply_deterministic_controls(runtime.deterministic_controls_binding)
        import wandb
        require(wandb.__version__ == '0.28.1', 'Original reviewed offline SDK0.28.1 required')
        torch.set_num_threads(8)
        torch.set_num_interop_threads(1)
        from phychem_mfm.model.v3_performance import (PerformanceOptions, build_performance_model,
            execution_context, make_adamw, performance_forward_pretrain)
        from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1JointSchedule, Phase1LossPolicy
        from phychem_mfm.supervision import SupervisionConfig
        from phychem_mfm.training.losses import LossWeights
        original_reference, a4, model_config, configuration = load_references(runtime)
        require(model_config['backbone']['layers'] == 6 and model_config['backbone']['dim'] == 512,
                'Original actual6x512 architecture required')
        options = PerformanceOptions(**json.loads(runtime.candidate_options.read_bytes()))
        require(options.distance_checkpointing is True and options.backbone_checkpointing is True
                and options.head_checkpointing is False and options.precision == 'fp32'
                and options.compile_backbone is False and options.tf32 is False
                and options.fused_adamw is False, 'Exact a03 head-off FP32 options required')
        stream = open_native_input(original_reference, selection, selected_ref, deps)
        first_corpus = stream.next()
        shape = actual_shape(first_corpus)
        require(not torch.cuda.is_initialized(), 'CPU maximum selection/native decode must precede CUDA initialization')
        deadline_check(preparation_deadline)
        cpu_preparation = dict(elapsed_seconds=time.monotonic() - started,
            CUDA_initialized_after_actual_native_decode=False, reader_workers=0,
            entire_selected_native_record_decoded=True, cropped_or_substituted=False, actual_shape=shape)
        write(args.output / 'CPU_PREPARATION.json', cpu_preparation)
        environment = bind_environment(runtime, GPU)
        observed_environment = {key: environment[key] for key in
            ('torch_version', 'cuda_version', 'gpu_name', 'gpu_total_bytes')}
        observed_environment['driver_version'] = environment['gpu']['driver_version']
        require(observed_environment == deps['expected_runtime'],
                'Actual original CUDA/Torch/driver/physical-memory environment differs')
        resources.append(strict_resources(args.output, expect_owned=False))
        configuration.update(environment)
        configuration.update(data_version=stream.bindings, capacity_producer_kind=KIND,
            source_package=pin, Root_actual_frames=root_frames, selection=selected_ref,
            maximum_selection=selection, wandb_version=str(wandb.__version__),
            resident_models=1, warmup_updates=2, observed_updates=20, total_actual_updates=22,
            original_sampler_used=False, sampler_trajectory_or_ABBA_speed_acceptance=False,
            universal_8M_shape_or_loader_coverage=False, auto_qualification=False,
            CPU_preparation=cpu_preparation,
            complete_tested_source_graph_reference=deps['raw_refs']['full_CPU_Root_closure'])
        # Calls the existing manual builder but records this true custom argv.
        # No paired/single command, role or qualify_invocation is fabricated.
        integration = load_performance_execution(runtime, model_config, configuration, resident_models=1)
        torch.manual_seed(0)
        torch.cuda.manual_seed_all(0)
        model = build_performance_model(model_config, options, execution=integration).cuda().train()
        require(all(p.dtype == torch.float32 for p in model.parameters()), 'Actual model parameters must be F32')
        configuration['performance_execution_request'] = execution_request_reference(runtime)
        configuration['performance_execution'] = model.v3_performance_execution
        configuration['configuration_sha256'] = canonical_sha(configuration)
        configuration_ref = write(args.output / 'configuration.json', configuration)
        optimizer = make_adamw(model, a4['optimizer'], options)
        weights = LossWeights.from_mapping(configuration['loss_weights'])
        policy = Phase1LossPolicy.from_mapping(a4['loss_policy'])
        supervision = SupervisionConfig.from_variant('S')
        # Exact existing single_a_benchmark persistent offline layout.
        os.environ['WANDB_MODE'] = 'offline'
        os.environ['WANDB_CACHE_DIR'] = str(args.output / 'cache')
        os.environ['WANDB_DATA_DIR'] = str(args.output / 'wandb_data')
        tracker = wandb.init(project='mfm_model_v3_development', mode='offline', dir=str(args.output),
            name=f'native_S_max712_R1_{os.environ["SLURM_JOB_ID"]}', config=configuration)
        tracking_run_id = tracker.id
        SDK_directory = Path(tracker.dir).parent
        resources.append(strict_resources(args.output, expect_owned=True))
        original_shape = None
        for ordinal in range(22):
            deadline_check(total_deadline)
            tick = time.perf_counter()
            corpus = first_corpus if ordinal == 0 else stream.next()
            first_corpus = None
            observed_shape = actual_shape(corpus)
            require(observed_shape == shape, 'Native maximum shape/edge population changed')
            receipt = corpus_receipt(corpus, stream.index)
            if first_receipt is None:
                first_receipt = receipt
                original_shape = observed_shape
            require(receipt['receipt_sha256'] == first_receipt['receipt_sha256'],
                    'Epoch0 selected native three-view content changed across updates')
            loader_seconds = time.perf_counter() - tick
            batch = corpus.encoder_batch.to('cuda', non_blocking=False)
            torch.cuda.synchronize()
            compute_tick = time.perf_counter()
            optimizer.zero_grad(set_to_none=True)
            with execution_context(options):
                outputs = performance_forward_pretrain(model, batch, supervision.objectives)
                loss = compute_phase1_loss(outputs, batch, None, supervision, weights,
                    Phase1JointSchedule(), ordinal, policy=policy)
                require(bool(torch.isfinite(loss.total)), 'Nonfinite selected-native loss')
                loss.total.backward()
                norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
                require(bool(torch.isfinite(norm)), 'Nonfinite selected-native gradient')
                optimizer.step()
            torch.cuda.synchronize()
            compute_seconds = time.perf_counter() - compute_tick
            require(compute_seconds > 0, 'Positive actual compute duration required')
            steps_completed += 1
            stream.commit(corpus)
            step_resource = strict_resources(args.output, expect_owned=True)
            resources.append(step_resource)
            final_optimizer = optimizer_metadata(optimizer)
            require(final_optimizer['parameter_state_entries'] > 0, 'Actual Adam state not materialized')
            row = dict(optimizer_updates=ordinal + 1, measured_after_warmup=ordinal >= 2,
                loss=float(loss.total.detach().cpu()), gradient_norm=float(norm.detach().cpu()),
                loader_seconds=loader_seconds, compute_seconds=compute_seconds,
                actual_input=receipt, shape=observed_shape, valid_label_counts=dict(loss.counts),
                committed_selected_base_exposures=stream.committed_base_samples,
                performance_execution=execution_observation(model), optimizer_state=final_optimizer,
                resources=step_resource, producer_kind=KIND, original_sampler_cursor=None)
            learning_rates = [float(group['lr']) for group in optimizer.param_groups]
            row['learning_rates'] = learning_rates
            SDK_row = dict(optimizer_updates=ordinal + 1, loss=row['loss'],
                learning_rate=learning_rates[0], gradient_norm=row['gradient_norm'],
                loader_seconds=loader_seconds, compute_seconds=compute_seconds,
                update_seconds_before_SDK_log=time.perf_counter() - tick,
                base_records=receipt['base_records'], native_atoms=receipt['native_atoms'],
                physical_graphs=observed_shape['physical_graphs'], physical_atoms=observed_shape['physical_atoms'],
                base_records_per_compute_second=receipt['base_records'] / compute_seconds,
                native_atoms_per_compute_second=receipt['native_atoms'] / compute_seconds,
                physical_graphs_per_compute_second=observed_shape['physical_graphs'] / compute_seconds,
                physical_atoms_per_compute_second=observed_shape['physical_atoms'] / compute_seconds,
                peak_allocated_bytes=step_resource['peak_allocated_bytes'],
                peak_reserved_bytes=step_resource['peak_reserved_bytes'],
                owned_NVML_memory_bytes=sum(item['used_memory_bytes'] for item in
                    step_resource['gpu_observation']['compute_processes'] if item['own']),
                process_rss_sum_bytes=step_resource['process_rss_sum_bytes'],
                output_bytes=step_resource['output_bytes'], measured_after_warmup=ordinal >= 2,
                selected_maximum_ordinal=selection['selected_logical_ordinal'],
                all_maximum_tie_count=selection['all_maximum_tie_count'],
                **{'learning_rate/group_' + str(i): value for i, value in enumerate(learning_rates)},
                **{'valid_label_count/' + key: value for key, value in loss.counts.items()})
            # Persist exactly22 real update rows, step1..22, original SDK API.
            tracker.log(SDK_row, step=ordinal + 1, commit=True)
            SDK_log_calls_returned += 1
            last_SDK_row = SDK_row
            row['SDK_history_projection'] = SDK_row
            append_json(args.output / 'steps.jsonl', row)
            durable_step_rows += 1
            del outputs, loss, batch, corpus
            print(json.dumps(dict(optimizer_updates=steps_completed, selected_maxN=MAX_N,
                                  resident_models=1, capacity_qualification=False)), flush=True)
        require(stream.read_count == stream.committed_base_samples == steps_completed
                == durable_step_rows == SDK_log_calls_returned == 22,
                'Exactly22 actual updates, durable source rows and SDK log calls required')
        stream.index.verify_unchanged()
        require(reference(args.output / 'steps.jsonl', 16 << 20)['bytes'] <= 16 << 20,
                'Finite22-row resource journal bound exceeded')
        deadline_check(total_deadline)
        _, _, _ = verify_sources(args.pins_sha256, total_deadline)
        source_after = dict(source_package=reference(HERE / 'source_pins.json'),
                            complete_tested_projection_current=True)
        status = 'NATIVE_MAX_SINGLETON_R1_22_UPDATES_COMPLETED'
        summary_payload = dict(schema='model_v3_native_max_R1_summary_v1',
            status=status, source_package=pin, configuration=configuration_ref, selection=selected_ref,
            actual_shape=original_shape, resident_models=1, warmup_updates=2, observed_updates=20,
            actual_updates=steps_completed, selected_base_exposures=22,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_reserved_bytes=torch.cuda.max_memory_reserved(), optimizer_state=final_optimizer,
            maximum_record_retained_without_crop=True, memory_guard_fraction=.85,
            peak_semantics='whole initialized model plus all22updates including warmup/Adam; never reset after warmup',
            original_sampler_or_ABBA=False, numeric_20batch500step_acceptance=False,
            automatic_capacity_qualification=False, universal_8M_capacity_coverage=False,
            pending_actual_outer_Root_C0=True, model_checkpoint_written=False,
            tracking_run_id=tracking_run_id, tracking_mode='offline',
            throughput_semantics='compute-only rates; update_seconds_before_SDK_log excludes its subsequent SDK call; not ABBA timing')
        return 0
    except BaseException as exc:
        failure = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        if stream is not None:
            try:
                stream.close()  # Existing SInputStream.close: native handles and descriptors.
            except BaseException as exc:
                cleanup_errors.append(dict(component='native_input', type=type(exc).__name__, message=str(exc)))
        if tracker is not None:
            try:
                resources.append(strict_resources(args.output, expect_owned=True))
            except BaseException as exc:
                cleanup_errors.append(dict(component='final_resource_guard', type=type(exc).__name__, message=str(exc)))
            terminal_summary = dict(status=status if not cleanup_errors else 'CLEANUP_FAILED',
                completed_actual_updates=steps_completed, durable_source_rows=durable_step_rows,
                SDK_log_calls_returned=SDK_log_calls_returned, expected_actual_updates=22,
                failure=failure, cleanup_errors=list(cleanup_errors), source_package=pin,
                configuration=configuration_ref, selection=selected_ref,
                selected_maximum_ordinal=selection['selected_logical_ordinal'],
                all_maximum_tie_count=selection['all_maximum_tie_count'],
                resident_models=1, elapsed_seconds_before_finish=time.monotonic() - started,
                capacity_shape_diagnostic_only=True, numeric_acceptance=False,
                ABBA_or_whole_8M_acceptance=False, automatic_capacity_qualification=False)
            try:
                tracker.summary.update({'capacity_diagnostic': terminal_summary})
                expected_summary = dict(last_SDK_row or {})
                expected_summary['capacity_diagnostic'] = terminal_summary
                expected_summary_ref = write(args.output / 'SDK_expected_summary.json', expected_summary)
            except BaseException as exc:
                cleanup_errors.append(dict(component='tracking_summary', type=type(exc).__name__, message=str(exc)))
            SDK_finish_exit_code = (0 if status == 'NATIVE_MAX_SINGLETON_R1_22_UPDATES_COMPLETED'
                and failure is None and not cleanup_errors
                and steps_completed == durable_step_rows == SDK_log_calls_returned == 22 else 1)
            try:
                tracker.finish(exit_code=SDK_finish_exit_code)
                SDK_finish_returned = True
            except BaseException as exc:
                cleanup_errors.append(dict(component='tracking_finish', type=type(exc).__name__, message=str(exc)))
            if SDK_finish_returned:
                try:
                    SDK_path = SDK_directory / ('run-' + tracking_run_id + '.wandb')
                    info = SDK_path.lstat()
                    require(stat.S_ISREG(info.st_mode) and info.st_uid == 1278 and info.st_nlink == 1
                            and 0 < info.st_size <= 128 << 20, 'Original durable bounded offline SDK required')
                    SDK_descriptor = dict(path=str(SDK_path), bytes=info.st_size,
                        payload_rehashed_or_decoded_here=False, independent_native_audit_pending=True)
                except BaseException as exc:
                    cleanup_errors.append(dict(component='tracking_persistence', type=type(exc).__name__, message=str(exc)))

        if summary_payload is not None:
            summary_payload.update(status=status if not cleanup_errors else 'CLEANUP_FAILED',
                SDK=SDK_descriptor, SDK_finish_call_returned=SDK_finish_returned,
                SDK_finish_requested_exit_code=SDK_finish_exit_code, SDK_expected_summary=expected_summary_ref,
                independent_native_SDK_audit_pending=True,
                peak_allocated_bytes=max(item['peak_allocated_bytes'] for item in resources),
                peak_reserved_bytes=max(item['peak_reserved_bytes'] for item in resources))
            write(args.output / 'summary.json', summary_payload)
        write(args.output / 'run_status.json', dict(schema='model_v3_native_max_R1_status_v1',
            status=status if not cleanup_errors else 'CLEANUP_FAILED', failure=failure,
            cleanup_errors=cleanup_errors, stream_cleanup=getattr(stream, 'last_cleanup', None),
            completed_actual_updates=steps_completed, durable_source_rows=durable_step_rows,
            SDK_log_calls_returned=SDK_log_calls_returned, elapsed_seconds=time.monotonic() - started,
            configuration=configuration_ref, selection=selected_ref, source_after=source_after,
            tracking_run_id=tracking_run_id, tracking_mode='offline', SDK=SDK_descriptor,
            SDK_finish_call_returned=SDK_finish_returned, SDK_finish_requested_exit_code=SDK_finish_exit_code,
            SDK_expected_summary=expected_summary_ref, independent_native_SDK_audit_pending=True,
            original_sources_or_native_inputs_modified=False, model_checkpoint_written=False,
            actual_outer_C0_not_self_asserted=True, automatic_capacity_qualification=False))
        if cleanup_errors and failure is None:
            raise RuntimeError('Selected-native input, persistent SDK or resource cleanup failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pins-sha256', required=True)
    args = parser.parse_args()
    require(os.getuid() == 1278 and os.environ.get('SLURM_JOB_ID'), 'Actual owned GPU Slurm job required')
    destination = args.output.resolve()
    require(not args.output.exists() and destination.is_relative_to(N.resolve())
            and not destination.is_relative_to((N / 'native_S_B20k_v3').resolve())
            and not destination.is_relative_to(HERE.resolve())
            and str(args.output) == os.environ['MODEL_V3_OUT'], 'Fresh independent N child output required')
    args.output.mkdir(parents=True)
    install_termination_handler()
    locks = B / 'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'
    fd = os.open(locks / (GPU + '.lock'), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 1278 and info.st_nlink == 1,
                'Original shared physical UUID lock must be owned ordinary file')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return run(args)
    finally:
        os.close(fd)


if __name__ == '__main__':
    raise SystemExit(main())
