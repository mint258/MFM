"""Cost metadata arithmetic; no models, predictions, labels or score inputs."""
import math


def duration_seconds(value):
    """Slurm CPU durations, including day prefixes and fractional seconds."""
    if value in (None, '', 'Unknown', 'N/A'):
        return None
    days, clock = (value.split('-', 1) if '-' in value else ('0', value))
    parts = clock.split(':')
    if len(parts) == 2:
        parts.insert(0, '0')
    if len(parts) != 3:
        raise ValueError('Unsupported Slurm duration')
    day, hour, minute = int(days), int(parts[0]), int(parts[1])
    second = float(parts[2])
    if min(day, hour, minute, second) < 0 or minute >= 60 or not 0 <= second < 60:
        raise ValueError('Invalid Slurm duration')
    return day * 86400 + hour * 3600 + minute * 60 + second


def interval_union_seconds(intervals):
    """Physical wall time on a single UUID, counting overlapping phases once."""
    checked = []
    for start, end in intervals:
        if not all(math.isfinite(v) for v in (start, end)) or end < start:
            raise ValueError('A finite closed producer interval is required')
        checked.append((start, end))
    total, previous_end = 0.0, None
    for start, end in sorted(checked):
        total += max(0.0, end - max(start, previous_end if previous_end is not None else start))
        previous_end = max(end, previous_end if previous_end is not None else end)
    return total


def identity(row):
    producer = row.get('producer', row)
    result = (row['node'], producer['uid'], producer['pid'], producer['start_ticks'])
    if result[1] != 1278 or result[2] <= 0 or result[3] < 0:
        raise ValueError('Exact owned producer identity is required')
    return result


def gpu_wall_account(rows):
    """Consume curated closed proofs; unknown exit codes remain unknown.

    These are bound-GPU producer intervals, not measured CUDA busy time,
    utilization, energy, or a monetary bill. Inventory and closure coverage
    remain the caller's responsibility.
    """
    producers = {}
    for row in rows:
        key = identity(row)
        uuid = row['gpu_uuid']
        if not isinstance(uuid, str) or not uuid.startswith('GPU-'):
            raise ValueError('An actual GPU UUID is required')
        start, end = row['started_at'], row['ended_at']
        interval_union_seconds([(start, end)])
        if key not in producers:
            producers[key] = dict(identity=list(key), gpu_uuid=uuid,
                started_at=start, ended_at=end, exit_code=row.get('exit_code'),
                sources=[row['source']])
            continue
        prior = producers[key]
        codes = {v for v in (prior['exit_code'], row.get('exit_code')) if v is not None}
        if prior['gpu_uuid'] != uuid or len(codes) > 1:
            raise ValueError('Conflicting copies of one producer proof')
        prior.update(started_at=min(prior['started_at'], start),
            ended_at=max(prior['ended_at'], end), exit_code=next(iter(codes), None))
        prior['sources'] = sorted(set(prior['sources'] + [row['source']]))
    intervals = {}
    for row in producers.values():
        intervals.setdefault(row['gpu_uuid'], []).append((row['started_at'], row['ended_at']))
    seconds = {uuid: interval_union_seconds(values) for uuid, values in sorted(intervals.items())}
    return dict(unique_producers=list(producers.values()), bound_GPU_wall_seconds_by_UUID=seconds,
        bound_GPU_wall_seconds=sum(seconds.values()),
        unknown_producer_exit_codes=sum(row['exit_code'] is None for row in producers.values()))


def cpu_account(jobs, native):
    """Separate allocated Slurm CPU time from observed CPU execution time."""
    unique_jobs = {}
    for row in jobs:
        if row['user'] != 'zixiao' or not row['name'].lower().startswith(('s_', 'srecipe', 's_recipe')):
            raise ValueError('Only the explicitly inventoried own S jobs are allowed')
        if row['job_id'] in unique_jobs and unique_jobs[row['job_id']] != row:
            raise ValueError('Use one actual accounting observation per job ID')
        unique_jobs[row['job_id']] = row
    allocated, measured, missing = 0, 0.0, []
    for row in unique_jobs.values():
        cpus, elapsed = row['allocated_cpus'], row['elapsed_seconds']
        if min(cpus, elapsed) < 0:
            raise ValueError('Negative allocation')
        allocated += cpus * elapsed
        seconds = duration_seconds(row.get('total_cpu'))
        if seconds is None:
            missing.append(row['job_id'])
        else:
            measured += seconds
    native_by_identity = {}
    for row in native:
        key = identity(row)
        value = (row.get('cpu_user_seconds'), row.get('cpu_system_seconds'))
        if key in native_by_identity and native_by_identity[key] != value:
            raise ValueError('Conflicting native CPU observations')
        if any(v is not None and (not math.isfinite(v) or v < 0) for v in value):
            raise ValueError('Invalid measured CPU time')
        native_by_identity[key] = value
    known = [sum(v) for v in native_by_identity.values() if all(x is not None for x in v)]
    return dict(Slurm_allocated_CPU_seconds=allocated, Slurm_measured_CPU_seconds=measured,
        Slurm_jobs_missing_measured_CPU_time=missing, native_measured_CPU_seconds=sum(known),
        native_producers_missing_CPU_time=sum(any(x is None for x in v) for v in native_by_identity.values()),
        native_unique_producers=len(native_by_identity),
        allocation_and_measured_times_are_different_estimands=True)
