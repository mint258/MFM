"""Original I1 trapezoidal whole-board telemetry estimator for new E1 runs."""
import math

def summarize_telemetry(rows,job,gpu_uuid):
    records=[x for x in rows if isinstance(x.get("power_watts"),(int,float))
             and math.isfinite(x["power_watts"]) and x["power_watts"]>=0]
    if len(records)<2:raise ValueError("Two original telemetry samples required")
    if any(str(x["job_id"])!=str(job) or x["gpu_uuid"]!=gpu_uuid for x in records):
        raise ValueError("Original training telemetry job/UUID differs")
    duration=0.;joules=0.
    for a,b in zip(records,records[1:]):
        delta=b["timestamp"]-a["timestamp"]
        if not math.isfinite(delta) or delta<=0:raise ValueError("Original telemetry time must increase")
        duration+=delta;joules+=(a["power_watts"]+b["power_watts"])*.5*delta
    return dict(power_time_weighted_mean_watts=joules/duration,
        power_observation_seconds=duration,power_samples=len(records),
        excluded_telemetry_rows=len(rows)-len(records),
        sampled_peak_memory_mib=max(x["memory_mib"] for x in records),
        power_averaging_method="Original trapezoidal time-weighted whole-board mean, unchanged")
