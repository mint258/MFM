"""Actual Alpha own-tree memory and shared directory quota, without time caps."""
import os
from pathlib import Path
import threading
from .common import allocated_bytes, need
from .quota import budget_check


def memory():
    available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    pending, seen, rss = [os.getpid()], set(), 0
    while pending:
        pid = pending.pop()
        if pid in seen:continue
        seen.add(pid)
        try:
            rss += int(Path('/proc', str(pid), 'statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
            pending.extend(map(int, Path('/proc', str(pid), 'task', str(pid), 'children').read_text().split()))
        except FileNotFoundError:continue
    return rss, available


class Guard:
    def __init__(self, plan, stop_event=None, usage_provider=None, prequery_credit_provider=None):
        self.plan = plan; self.stop = stop_event if stop_event is not None else threading.Event()
        self.usage_provider = usage_provider; self.credit_provider = prequery_credit_provider
        self.done = threading.Event(); self.reason = None
        self.samples = self.peak_rss = self.peak_output = 0
        self.sample(); self.check()
        self.thread = threading.Thread(target=self.observe, daemon=True); self.thread.start()

    def sample(self):
        p = self.plan; scope = Path(p['output_scope_root'])
        own = allocated_bytes(scope) if self.usage_provider is None else self.usage_provider()
        budget_check(p, own, scope, self.credit_provider)
        rss, available = memory()
        need(rss < p['software_rss_budget_bytes'], 'Actual Alpha own process-tree RSS exceeds reviewed software budget')
        need(available >= p['minimum_node_available_bytes'], 'Actual Alpha node available memory is below reserve')
        self.samples += 1; self.peak_rss = max(self.peak_rss, rss); self.peak_output = max(self.peak_output, own)

    def observe(self):
        while not self.done.wait(5):
            try:self.sample()
            except BaseException as exc:
                self.reason = repr(exc); self.stop.set(); return

    def check(self, *args, **kwargs):
        need(not self.stop.is_set(), self.reason or 'Actual shared Alpha resource stop')

    def close(self):
        self.done.set(); self.thread.join()

    def receipt(self):
        return {'endpoint': '218.192.171.238:22', 'uid': os.getuid(), 'samples': self.samples, 'peak_own_tree_rss_bytes': self.peak_rss, 'peak_actual_output_blocks_bytes': self.peak_output, 'stop_reason': self.reason, 'arbitrary_wall_or_retry_limit': False, 'process_signals_sent': False, 'Slurm_memory_reservation_inferred_from_software_budget': False}
