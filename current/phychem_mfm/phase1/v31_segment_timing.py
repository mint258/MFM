"""Opt-in synchronized, exclusive CPU/GPU segment timings (measurement only)."""
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
import csv
from pathlib import Path
import statistics
import time

_CURRENT = ContextVar('v31_segment_timing', default=None)
STAGES = ('wait_batch', 'count', 'collate', 'h2d', 'forward', 'loss',
          'backward', 'clip_optimizer', 'logging', 'checkpoint')


@contextmanager
def phase(name):
    timer = _CURRENT.get()
    if timer is None or timer.step < timer.skip:
        yield
        return
    with timer.phase(name):
        yield


class SegmentTimer:
    def __init__(self, directory, *, skip=100, synchronize=None):
        if synchronize is None:
            import torch
            synchronize = torch.cuda.synchronize
        self.sync = synchronize
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.skip, self.step = skip, 0
        self.stack, self.values, self.rows = [], defaultdict(float), []
        self.token = _CURRENT.set(self)
        self.file = (self.directory / 'segments.csv').open('x', newline='', buffering=1)
        self.writer = csv.DictWriter(self.file, fieldnames=['step', *STAGES, 'total'])
        self.writer.writeheader()

    @contextmanager
    def phase(self, name):
        self.sync()
        start = time.perf_counter()
        frame = [name, start, 0.]
        self.stack.append(frame)
        try:
            yield
        finally:
            self.sync()
            elapsed = time.perf_counter() - start
            self.stack.pop()
            self.values[name] += elapsed - frame[2]
            if self.stack:
                self.stack[-1][2] += elapsed

    def end_step(self):
        if self.step >= self.skip:
            row = dict(step=self.step + 1, **{s: self.values[s] for s in STAGES})
            row['total'] = sum(row[s] for s in STAGES)
            self.writer.writerow(row)
            self.rows.append(row)
        self.values.clear()
        self.step += 1

    def close(self):
        self.file.close()
        _CURRENT.reset(self.token)
        if not self.rows:
            return
        total = sum(r['total'] for r in self.rows)
        with (self.directory / 'summary.csv').open('x', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=['stage', 'median_seconds', 'share_of_measured_time'])
            writer.writeheader()
            for stage in STAGES:
                writer.writerow(dict(stage=stage,
                    median_seconds=statistics.median(r[stage] for r in self.rows),
                    share_of_measured_time=sum(r[stage] for r in self.rows) / total if total else 0.))

def timed(name):
    from functools import wraps
    def decorate(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            timer = _CURRENT.get()
            if timer is None or timer.step < timer.skip:
                return function(*args, **kwargs)
            with phase(name):
                return function(*args, **kwargs)
        return wrapper
    return decorate
