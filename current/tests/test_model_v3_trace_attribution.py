from copy import deepcopy

import torch

from phychem_mfm.model.v3_profiler_attribution import analyze_trace, instrument_recompute_regions


def event(name, start, duration, *, cat="cpu_op", args=None, pid=10, tid=1, phase="X"):
    return {"name": name, "ts": start, "dur": duration, "cat": cat,
            "ph": phase, "pid": pid, "tid": tid, "args": args or {}}


def fixture_trace():
    return {"traceEvents": [
        event("model_v3/forward", 0, 100, cat="user_annotation"),
        event("model_v3/attention/dist_mlp", 10, 20, cat="user_annotation"),
        event("aten::addmm", 12, 13, args={"External id": 11, "Sequence number": 7}),
        event("model_v3/ffn", 40, 20, cat="user_annotation"),
        event("aten::mm", 45, 10, args={"External id": 33, "Sequence number": 8}),
        event("cudaLaunchKernel", 46, 1, cat="cuda_runtime", args={"correlation": 202, "External id": 33}),
        event("model_v3/backward", 100, 100, cat="user_annotation"),
        event("AddmmBackward0", 110, 30, args={"Sequence number": 7}),
        event("aten::mm", 115, 15, args={"External id": 22}),
        event("cudaLaunchKernel", 120, 1, cat="cuda_runtime", args={"correlation": 201, "External id": 22}),
        event("matrix-backward", 300, 20, cat="kernel", pid=0, tid=7,
              args={"device": 0, "stream": 7, "correlation": 201}),
        event("ffn-forward", 305, 10, cat="kernel", pid=0, tid=8,
              args={"device": 0, "stream": 8, "correlation": 202}),
    ]}


def test_unique_kernels_and_busy_union_never_add_overlapping_component_times():
    trace = fixture_trace()
    trace["traceEvents"].append(deepcopy(trace["traceEvents"][-2]))
    result = analyze_trace(trace)
    gpu = result["devices"]["0"]
    assert result["raw_kernel_events"] == 3
    assert result["unique_kernel_events"] == 2 and result["duplicate_kernel_events_removed"] == 1
    assert gpu["kernel_busy_union_us"] == gpu["exclusive_busy_total_us"] == 20
    exclusive = {row["component"]: row["microseconds"] for row in gpu["exclusive_busy_us"]}
    assert exclusive == {"dist_mlp": 10., "concurrent_multiple_components": 10.}
    summed = {row["component"]: row["microseconds"] for row in gpu["kernel_duration_sums_us_nonexclusive"]}
    assert summed == {"dist_mlp": 20., "ffn": 10.}
    assert gpu["exclusive_busy_reconciles"]
    assert sum(row["microseconds"] for row in result["cpu_thread_self_us"]) == 200


def test_missing_correlation_stays_unknown_and_sequence_maps_backward_component():
    trace = fixture_trace()
    trace["traceEvents"].append(event("unknown-kernel", 400, 5, cat="kernel", pid=0, tid=7,
                                      args={"device": 0, "correlation": 999}))
    result = analyze_trace(trace)
    rows = result["devices"]["0"]["kernel_duration_sums_us_nonexclusive"]
    assert any(row["component"] == "dist_mlp" and row["phase"] == "backward" for row in rows)
    assert any(row["component"] == "unknown" and row["microseconds"] == 5 for row in rows)
    assert result["devices"]["0"]["unknown_kernel_examples"] == ["unknown-kernel"]


def test_autograd_worker_thread_is_backward_even_without_main_thread_annotation():
    trace = fixture_trace()
    for raw in trace["traceEvents"]:
        if raw["name"] in {"AddmmBackward0"} or raw.get("args", {}).get("correlation") == 201 or raw.get("args", {}).get("External id") == 22:
            if raw["cat"] != "kernel":
                raw["tid"] = 2
    trace["traceEvents"].append(event("PyTorch Profiler (0)", 0, 1000, cat="Trace", pid="Spans", tid="Profiler"))
    result = analyze_trace(trace)
    assert result["ignored_non_cpu_span_categories"] == {"Trace": 1}
    rows = result["devices"]["0"]["kernel_duration_sums_us_nonexclusive"]
    assert any(row["component"] == "dist_mlp" and row["phase"] == "backward" for row in rows)


def test_forward_replay_scope_inside_backward_is_separate_from_backward_gradients():
    trace = fixture_trace()
    trace["traceEvents"].extend([
        event("model_v3/attribution/dist_mlp_tile", 145, 20, cat="user_annotation"),
        event("cudaLaunchKernel", 150, 1, cat="cuda_runtime", args={"correlation": 303}),
        event("replayed-linear", 350, 4, cat="kernel", pid=0, tid=7,
              args={"device": 0, "stream": 7, "correlation": 303}),
    ])
    rows = analyze_trace(trace)["devices"]["0"]["kernel_duration_sums_us_nonexclusive"]
    assert any(row["component"] == "dist_mlp" and row["phase"] == "backward_forward_replay_scope"
               and row["microseconds"] == 4 for row in rows)


def test_allocator_trace_retains_unobserved_baseline_and_avoids_causal_peak_claim():
    trace = fixture_trace()
    trace["traceEvents"].extend([
        event("[memory]", 15, 0, phase="i", args={"Device Type": 1, "Device Id": 0,
              "Addr": 1, "Bytes": 100, "Total Allocated": 1000}),
        event("[memory]", 50, 0, phase="i", args={"Device Type": 1, "Device Id": 0,
              "Addr": 2, "Bytes": 300, "Total Allocated": 1300}),
    ])
    peak = analyze_trace(trace)["allocator_trace_peaks"]["0"]
    assert peak["observed_live_bytes_by_allocation_site"] == {"dist_mlp": 100, "ffn": 300}
    assert peak["untraced_or_unreconciled_residual_bytes"] == 900
    assert peak["not_a_causal_peak_decomposition"] is True


def test_zero_duration_kernel_remains_in_unique_inventory_without_busy_time():
    trace = {"traceEvents": [event("zero-clock", 100, 0, cat="kernel", pid=0, tid=7, args={"device": 0})]}
    result = analyze_trace(trace)
    assert result["unique_kernel_events"] == result["zero_duration_kernel_events"] == 1
    assert result["devices"]["0"]["kernel_busy_union_us"] == 0


def test_recompute_markers_preserve_values_gradients_keys_and_instance_methods():
    from torch.utils.checkpoint import checkpoint
    class Tiled(torch.nn.Sequential):
        def _row_forward(self, value):
            return super().forward(value)
        def forward(self, value):
            return checkpoint(self._row_forward, value, use_reentrant=False)
    model = torch.nn.Module()
    model.dist_mlp = Tiled(torch.nn.Linear(1, 8), torch.nn.SiLU(), torch.nn.Linear(8, 2))
    reference = deepcopy(model)
    value = torch.randn(13, 1)
    before = set(vars(model.dist_mlp))
    expected = reference.dist_mlp(value)
    expected.square().sum().backward()
    with instrument_recompute_regions(model):
        actual = model.dist_mlp(value)
        actual.square().sum().backward()
    assert torch.equal(actual, expected)
    assert set(vars(model.dist_mlp)) == before
    assert tuple(model.state_dict()) == tuple(reference.state_dict())
    assert all(torch.equal(left.grad, right.grad) for left, right in zip(model.parameters(), reference.parameters()))
