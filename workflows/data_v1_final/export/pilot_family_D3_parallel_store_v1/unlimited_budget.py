"""User-authorized D3 storage pause, without time/memory stops.

No finite Budget constructor, wall_clock or MemoryObserver is used. A daemon
only observes account storage; scientific work waits for the 100 GB floor to
recover. 300 GB is a forecast, never a per-job output limit. Root must bind the
new-mode original IO/worker checks to this control and physical-cap plan.
"""
import json, os, pathlib, threading, time
from . import io as I, runtime_budget as Runtime, queued_quota

MODE = 'USER_UNLIMITED_CPU21_D3_20261103'
PHYSICAL_QUOTA_BYTES = 4398046511104
ACCOUNT_FLOOR_BYTES = 100000000000
INTERVAL_SECONDS = 60
QUOTA_SETTLE_SECONDS = 1.1


def _atomic_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def _telemetry():
    result = {}
    for path, key, output in (('/proc/self/status', 'VmRSS:', 'parent_rss_bytes'),
                              ('/proc/meminfo', 'MemAvailable:', 'node_MemAvailable_bytes')):
        try:
            lines = pathlib.Path(path).read_text().splitlines()
            text = next(line for line in lines if line.startswith(key))
            result[output] = int(text.split()[1]) * 1024
        except Exception:
            result[output] = None
    # Telemetry only: neither value is compared against a limit.
    return result


def enable_unlimited_worker_resources():
    # Library buffers still flush normally; actual RSS is telemetry only.
    from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import memory as parent_memory
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as generic_memory
    def measured_rss(_ignored_cap):
        try:
            text=pathlib.Path('/proc/self/status').read_text()
            return next(int(v.split()[1])*1024 for v in text.splitlines() if v.startswith('VmHWM:'))
        except Exception:return 0
    parent_memory.soft_worker_rss=measured_rss
    generic_memory.soft_worker_rss=measured_rss
    os.environ.pop(parent_memory.ENV,None)


class Budget:
    def __init__(self, plan, proof, root):
        self.plan, self.proof, self.root = plan, proof, pathlib.Path(root)
        self.account_floor_bytes = ACCOUNT_FLOOR_BYTES
        self.census_context = Runtime.StableOutputCensus(self.root)
        I.ACTIVE_CENSUS = self.census_context
        self.pause_file = self.root / 'storage_pause.json'
        self.status_file = self.root / 'storage_status.json'
        self.control = dict(mode=MODE, cap=PHYSICAL_QUOTA_BYTES,
                            storage_pause_file=str(self.pause_file), storage_status_file=str(self.status_file))
        self.done = threading.Event()
        self._ready = threading.Event()
        self._observe_lock = threading.Lock()
        self._watcher = None
        self._closed = False
        self.quota = None
        self._last = dict(mode=MODE, state='INITIAL_STORAGE_OBSERVATION_PENDING')
        self._publish(self._last, paused=True)
        # No science is dispatched before the first actual storage observation.
        self.observe()
        self._watcher = threading.Thread(target=self._loop, name='D3-storage-observer', daemon=True)
        self._watcher.start()

    def _publish(self, record, *, paused):
        record = dict(record, mode=MODE, storage_paused=paused,
                      status_updated_unix_seconds=time.time(), **_telemetry())
        self._last = record
        if paused:
            self._ready.clear()
            try:
                _atomic_json(self.pause_file, record)
                _atomic_json(self.status_file, record)
            except OSError as error:
                # Parent stays paused even when a control write fails. The
                # initial flag is retained; retry updates the same two files.
                self._last['status_write_error'] = str(error)[:1024]
        else:
            try:
                _atomic_json(self.status_file, record)
                self.pause_file.unlink(missing_ok=True)
            except OSError as error:
                self._ready.clear()
                self._last['status_write_error'] = str(error)[:1024]
                return False
            self._ready.set()
        return not paused

    def _snapshot(self):
        # allocated() returns {(device,inode,generation): st_blocks*512} for
        # retained actual inode lifetimes. It is not logical SQLite length.
        earlier = self.census_context.allocated()
        time.sleep(QUOTA_SETTLE_SECONDS)
        quota = queued_quota.observe(self.plan, earlier)
        if quota.get('credit_not_applied') is not True:
            raise ValueError('QUOTA_OBSERVER_MUST_NOT_APPLY_OWN_CREDIT')
        current = self.census_context.allocated()
        free = quota['free_bytes']
        total = quota['total_future_reserved_bytes']
        forecast = quota['own_forecast_bytes']
        if any(type(value) is not int or value < 0 for value in (free, total, forecast)) or total < forecast:
            raise ValueError('UNKNOWN_ACTUAL_QUOTA_OR_FUTURE_RESERVATION')
        # Same earlier/current min intersection as Runtime.WholeOutputMath.
        # Earlier is causally before the remote quota query by >=1.1 seconds;
        # no cross-node wall-clock comparison creates a new stop condition.
        covered = min(forecast, sum(min(amount, current.get(key, 0)) for key, amount in earlier.items()))
        other = total - forecast
        remaining_own = max(0, forecast - covered)
        remaining = other + remaining_own
        margin = free - remaining
        self.quota = quota
        return dict(state='READY' if margin >= ACCOUNT_FLOOR_BYTES else 'WAITING_FOR_ACCOUNT_STORAGE',
                    quota_observed_unix_seconds=quota['observed_unix_seconds'],
                    quota_query_started_unix_seconds=quota.get('quota_query_started_unix_seconds'),
                    free_bytes=free, total_future_reserved_bytes=total, own_forecast_bytes=forecast,
                    covered_own_outputs_bytes=covered, other_future_reserved_bytes=other,
                    remaining_own_forecast_bytes=remaining_own, remaining_future_reserved_bytes=remaining,
                    account_margin_after_remaining_future_bytes=margin, account_floor_bytes=ACCOUNT_FLOOR_BYTES,
                    earlier_allocated_entries=len(earlier), current_allocated_entries=len(current),
                    physical_quota_bytes=PHYSICAL_QUOTA_BYTES, forecast_is_not_a_task_cap=True,
                    raw_quota=quota.get('raw_quota'))

    def observe(self):
        with self._observe_lock:
            while not self.done.is_set():
                try:
                    record = self._snapshot()
                    ready = record['state'] == 'READY'
                except Exception as error:
                    record = dict(state='WAITING_FOR_QUOTA_OBSERVATION', error_type=type(error).__name__,
                                  error=str(error)[:2048], forecast_is_not_a_task_cap=True)
                    ready = False
                if self._publish(record, paused=not ready):
                    return self._last
                # Space shortage or observation/control-IO failure waits,
                # never throws a resource STOP or retries scientific work.
                self.done.wait(INTERVAL_SECONDS)
            return self._last

    def _loop(self):
        while not self.done.wait(INTERVAL_SECONDS):
            self.observe()

    def check(self, *, force=False, dispatch=True):
        # dispatch is intentionally not a legacy STOP/RSS/wall-clock gate.
        if self._closed:
            return
        if force or not self._ready.is_set():
            self.observe()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.done.set()
        if self._watcher is not None and self._watcher is not threading.current_thread():
            self._watcher.join()
        # Do not start another quota observation during close; no total-time
        # limit or MemoryObserver is introduced, and no job is signalled.
        try:
            _atomic_json(self.status_file, dict(self._last, state='CLOSED', closed_unix_seconds=time.time()))
        except OSError:
            pass
        finally:
            self.census_context.close()