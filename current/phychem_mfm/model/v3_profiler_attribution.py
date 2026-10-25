"""Unique-kernel trace attribution with explicit unknown/concurrent buckets.

CPU thread self spans, summed kernel durations and disjoint device busy time
are different quantities. No inclusive profiler region totals are added here.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import functools
import hashlib
import heapq
import json
import math


@contextmanager
def instrument_recompute_regions(model):
    """Label methods that checkpoint invokes directly during backward replay."""
    from torch.profiler import record_function
    changed = []
    def wrap(module, attribute, label):
        original = getattr(module, attribute, None)
        if not callable(original):
            return
        had_instance_value = attribute in vars(module)
        prior_instance_value = vars(module).get(attribute)
        @functools.wraps(original)
        def measured(*args, **kwargs):
            with record_function(label):
                return original(*args, **kwargs)
        changed.append((module, attribute, had_instance_value, prior_instance_value))
        setattr(module, attribute, measured)
    for name, module in model.named_modules():
        if name.endswith("dist_mlp"):
            for method in ("_row_forward", "_rows"):
                wrap(module, method, "model_v3/attribution/dist_mlp_tile")
            for child in module.children():
                wrap(child, "forward", "model_v3/attribution/dist_mlp_operator")
        elif name == "geometry_head":
            wrap(module, "_predict_chunk", "model_v3/attribution/denoising_chunk")
            wrap(module, "_features", "model_v3/attribution/denoising_features")
    try:
        yield model
    finally:
        for module, attribute, existed, value in reversed(changed):
            if existed:
                setattr(module, attribute, value)
            else:
                delattr(module, attribute)


def union_length(intervals):
    ordered = sorted((float(start), float(end)) for start, end in intervals if end > start)
    if not ordered:
        return 0.
    total = 0.
    start, end = ordered[0]
    for left, right in ordered[1:]:
        if left > end:
            total += end - start
            start, end = left, right
        else:
            end = max(end, right)
    return total + end - start


def component_scope(name):
    if name.startswith("model_v3/attribution/dist_mlp_") or name == "model_v3/attention/dist_mlp":
        return "dist_mlp"
    if name.startswith("model_v3/attribution/denoising_") or name == "model_v3/denoising_head":
        return "denoising_head"
    mapping = {"model_v3/ffn": "ffn", "model_v3/other_heads": "other_heads",
               "model_v3/loss": "loss", "model_v3/optimizer": "optimizer",
               "model_v3/host_to_device": "host_to_device", "model_v3/loader_wait": "loader_wait"}
    if name in mapping:
        return mapping[name]
    if name.startswith("model_v3/attention/"):
        return "attention_" + name.rsplit("/", 1)[-1]
    return None


def _value(args, *names):
    for name in names:
        if name in args:
            return args[name]
    return None


def analyze_trace(trace):
    events = trace["traceEvents"] if isinstance(trace, dict) else trace
    cpu, threads, by_external = [], defaultdict(list), defaultdict(list)
    ignored_gpu_categories, ignored_cpu_categories, invalid_spans = defaultdict(int), defaultdict(int), 0
    gpu_categories = {"kernel", "gpu_memcpy", "gpu_memset", "gpu_user_annotation"}
    cpu_categories = {"cpu_op", "user_annotation", "cuda_runtime", "cuda_driver", "python_function"}
    for source_index, raw in enumerate(events):
        if raw.get("ph") != "X" or "ts" not in raw or "dur" not in raw:
            continue
        start, duration = float(raw["ts"]), float(raw["dur"])
        if not math.isfinite(start) or not math.isfinite(duration) or duration < 0:
            invalid_spans += 1
            continue
        if raw.get("cat") in gpu_categories:
            if raw.get("cat") != "kernel":
                ignored_gpu_categories[raw["cat"]] += 1
            continue
        if raw.get("cat") not in cpu_categories:
            ignored_cpu_categories[str(raw.get("cat"))] += 1
            continue
        if duration == 0:
            continue
        row = {"source_index": source_index, "name": raw.get("name", ""), "cat": raw.get("cat", ""),
               "start": start, "end": start + duration, "args": raw.get("args", {}),
               "pid": raw.get("pid"), "tid": raw.get("tid"), "parent": None, "children": []}
        index = len(cpu)
        cpu.append(row)
        threads[(row["pid"], row["tid"])].append(index)
        external = _value(row["args"], "External id", "External Id", "external_id")
        if external is not None:
            by_external[str(external)].append(index)
    crossing = 0
    for indices in threads.values():
        stack = []
        for index in sorted(indices, key=lambda i: (cpu[i]["start"], -cpu[i]["end"], cpu[i]["source_index"])):
            row = cpu[index]
            while stack and row["start"] >= cpu[stack[-1]]["end"]:
                stack.pop()
            while stack and row["end"] > cpu[stack[-1]]["end"]:
                crossing += 1
                stack.pop()
            if stack:
                row["parent"] = stack[-1]
                cpu[stack[-1]]["children"].append(index)
            stack.append(index)

    def ancestry(index):
        while index is not None:
            yield index
            index = cpu[index]["parent"]

    def scopes(index):
        component, phase = None, "outside_registered_regions"
        has_forward_component, backward_function = False, False
        for node in ancestry(index):
            name = cpu[node]["name"]
            backward_function |= "Backward" in name or name.startswith("autograd::engine::")
            classified = component_scope(name)
            if classified is not None and component is None:
                component = classified
                has_forward_component = classified not in {"loss", "optimizer", "loader_wait", "host_to_device"}
            if name in {"model_v3/forward", "model_v3/backward", "model_v3/loss", "model_v3/optimizer",
                        "model_v3/host_to_device", "model_v3/loader_wait"}:
                phase = name.split("/", 1)[1]
                break
        if phase == "outside_registered_regions" and backward_function:
            phase = "backward"
        if phase == "backward" and has_forward_component:
            phase = "backward_forward_replay_scope"
        return component, phase

    sequence_components = defaultdict(set)
    for index, row in enumerate(cpu):
        sequence = _value(row["args"], "Sequence number", "Sequence Number", "sequence_nr")
        if sequence is None or int(sequence) < 0 or "Backward" in row["name"] or row["name"].startswith("autograd::"):
            continue
        component, _ = scopes(index)
        if component is not None:
            sequence_components[str(sequence)].add(component)

    def classify(index):
        if index is None:
            return "unknown", "unknown", "no_cpu_correlation"
        component, phase = scopes(index)
        if component is not None:
            return component, phase, "explicit_scope"
        for node in ancestry(index):
            sequence = _value(cpu[node]["args"], "Sequence number", "Sequence Number", "sequence_nr")
            choices = sequence_components.get(str(sequence), ())
            if len(choices) == 1 and ("Backward" in cpu[node]["name"] or cpu[node]["name"].startswith("autograd::")):
                return next(iter(choices)), phase, "forward_sequence_number"
        return ("forward_other" if phase == "forward" else "unknown"), phase, "unattributed"

    def external_cpu(value):
        candidates = by_external.get(str(value), ())
        if not candidates:
            return None
        return min(candidates, key=lambda i: cpu[i]["end"] - cpu[i]["start"])

    runtime_correlations = {}
    for index, row in enumerate(cpu):
        correlation = _value(row["args"], "correlation", "Correlation id", "correlation_id")
        if correlation is not None and row["cat"] in {"cuda_runtime", "cuda_driver"}:
            runtime_correlations[str(correlation)] = index
    kernels, identities, duplicates, raw_kernel_count, invalid_kernel_count, zero_kernel_count = [], set(), 0, 0, 0, 0
    for raw in events:
        if raw.get("ph") != "X" or raw.get("cat") != "kernel":
            continue
        raw_kernel_count += 1
        args = raw.get("args", {})
        start, duration = float(raw["ts"]), float(raw["dur"])
        if not math.isfinite(start) or not math.isfinite(duration) or duration < 0:
            invalid_kernel_count += 1
            continue
        if duration == 0:
            zero_kernel_count += 1
        correlation = _value(args, "correlation", "Correlation id", "correlation_id")
        external = _value(args, "External id", "External Id", "external_id")
        device = str(_value(args, "device", "Device Id") if _value(args, "device", "Device Id") is not None else raw.get("pid"))
        stream = str(_value(args, "stream", "Stream") if _value(args, "stream", "Stream") is not None else raw.get("tid"))
        identity = (device, stream, start, duration, raw.get("name", ""), str(correlation), str(external))
        if identity in identities:
            duplicates += 1
            continue
        identities.add(identity)
        index = runtime_correlations.get(str(correlation))
        if index is None:
            index = external_cpu(external)
        component, phase, reason = classify(index)
        kernels.append({"device": device, "stream": stream, "start": start, "end": start + duration,
                        "component": component, "phase": phase, "reason": reason, "name": raw.get("name", "")})

    cpu_self, cpu_negative_self = defaultdict(float), 0
    for index, row in enumerate(cpu):
        children = [(cpu[child]["start"], cpu[child]["end"]) for child in row["children"]]
        own = row["end"] - row["start"] - union_length(children)
        if own < -1e-6:
            cpu_negative_self += 1
        component, phase, _ = classify(index)
        cpu_self[(component, phase)] += max(0., own)

    devices = {}
    for device in sorted({row["device"] for row in kernels}):
        rows = [row for row in kernels if row["device"] == device]
        boundaries = defaultdict(list)
        duration_sum, reasons = defaultdict(float), defaultdict(int)
        for index, row in enumerate(rows):
            boundaries[row["start"]].append((index, 1))
            boundaries[row["end"]].append((index, -1))
            duration_sum[(row["component"], row["phase"])] += row["end"] - row["start"]
            reasons[row["reason"]] += 1
        active, exclusive, previous = set(), defaultdict(float), None
        for moment in sorted(boundaries):
            if previous is not None and moment > previous and active:
                components = {rows[index]["component"] for index in active}
                phases = {rows[index]["phase"] for index in active}
                component = next(iter(components)) if len(components) == 1 else "concurrent_multiple_components"
                phase = next(iter(phases)) if len(phases) == 1 else "concurrent_multiple_phases"
                exclusive[(component, phase)] += moment - previous
            for index, direction in boundaries[moment]:
                if direction == 1:
                    active.add(index)
                else:
                    active.discard(index)
            previous = moment
        busy = union_length((row["start"], row["end"]) for row in rows)
        devices[device] = {
            "unique_kernels": len(rows), "kernel_busy_union_us": busy,
            "exclusive_busy_total_us": sum(exclusive.values()),
            "exclusive_busy_reconciles": abs(sum(exclusive.values()) - busy) <= max(1e-6, busy * 1e-10),
            "exclusive_busy_us": [{"component": key[0], "phase": key[1], "microseconds": value}
                                   for key, value in sorted(exclusive.items())],
            "kernel_duration_sums_us_nonexclusive": [{"component": key[0], "phase": key[1], "microseconds": value}
                                                      for key, value in sorted(duration_sum.items())],
            "correlation_methods": dict(reasons),
            "unknown_kernel_examples": [row["name"] for row in rows if row["component"] == "unknown"][:20]}
    # One chronological sweep per CPU thread avoids rescanning every CPU span
    # for every allocation event on a native20-step trace.
    memory_threads = {key: sorted(indices, key=lambda i: cpu[i]["start"]) for key, indices in threads.items()}
    memory_cursors, memory_active = defaultdict(int), defaultdict(list)
    def memory_cpu(pid, tid, timestamp):
        key = pid, tid
        indices = memory_threads.get(key, ())
        cursor = memory_cursors[key]
        active = memory_active[key]
        while cursor < len(indices) and cpu[indices[cursor]]["start"] <= timestamp:
            index = indices[cursor]
            heapq.heappush(active, (cpu[index]["end"] - cpu[index]["start"], index))
            cursor += 1
        memory_cursors[key] = cursor
        while active and cpu[active[0][1]]["end"] < timestamp:
            heapq.heappop(active)
        return active[0][1] if active else None

    memory_peaks, live = {}, defaultdict(dict)
    for raw in sorted((event for event in events if event.get("name") == "[memory]"), key=lambda event: event.get("ts", 0)):
        args = raw.get("args", {})
        if str(_value(args, "Device Type", "device_type")).lower() not in {"1", "cuda"}:
            continue
        total = _value(args, "Total Allocated", "total_allocated")
        size = _value(args, "Bytes", "bytes")
        address = _value(args, "Addr", "Address", "address")
        device = str(_value(args, "Device Id", "device"))
        if total is None or size is None or address is None:
            continue
        index = external_cpu(_value(args, "External id", "External Id", "external_id"))
        if index is None:
            index = memory_cpu(raw.get("pid"), raw.get("tid"), raw.get("ts", 0))
        component, phase, reason = classify(index)
        if int(size) > 0:
            live[device][str(address)] = (int(size), component)
        elif int(size) < 0:
            live[device].pop(str(address), None)
        if device not in memory_peaks or int(total) > memory_peaks[device]["total_allocated_bytes"]:
            sites = defaultdict(int)
            for amount, category in live[device].values():
                sites[category] += amount
            known = sum(sites.values())
            memory_peaks[device] = {"total_allocated_bytes": int(total), "timestamp_us": raw.get("ts"),
                "allocation_event_site": component, "phase": phase, "classification_reason": reason,
                "observed_live_bytes_by_allocation_site": dict(sites),
                "untraced_or_unreconciled_residual_bytes": int(total) - known,
                "not_a_causal_peak_decomposition": True}
    identity_bytes = json.dumps(sorted(identities), separators=(",", ":")).encode()
    return {"schema": "model_v3_unique_kernel_attribution_v1", "gpu_categories_in_primary_union": ["kernel"],
            "raw_kernel_events": raw_kernel_count, "unique_kernel_events": len(kernels),
            "invalid_kernel_events": invalid_kernel_count, "zero_duration_kernel_events": zero_kernel_count,
            "duplicate_kernel_events_removed": duplicates, "unique_kernel_identity_sha256": hashlib.sha256(identity_bytes).hexdigest(),
            "devices": devices, "cpu_crossing_spans": crossing, "invalid_duration_spans": invalid_spans,
            "negative_cpu_self_spans": cpu_negative_self,
            "cpu_thread_self_us": [{"component": key[0], "phase": key[1], "microseconds": value}
                                    for key, value in sorted(cpu_self.items())],
            "ignored_non_kernel_gpu_event_counts": dict(ignored_gpu_categories), "allocator_trace_peaks": memory_peaks,
            "ignored_non_cpu_span_categories": dict(ignored_cpu_categories),
            "limitations": ["CPU self spans include blocking wall time and are summed across threads, not CPU utilization.",
                            "Kernel duration sums can overlap; only exclusive_busy_us partitions device busy union.",
                            "Unknown and concurrent components are never divided among convenient categories.",
                            "Allocator live-block sites at peak do not establish causal peak-memory contributions."]}
