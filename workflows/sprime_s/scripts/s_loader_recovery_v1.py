"""Retry only a PyTorch loader timeout from the committed record cursor.

The frozen timeout, samples, views, model and optimizer remain unchanged.
No manifest/chemistry/worker exception is classified as an I/O retry.
"""
from __future__ import annotations
import copy
import re
import time


class LoaderRetryExhausted(RuntimeError):
    pass


class RecoveringLoaderIterator:
    def __init__(self, factory, sampler, close_iterator, torch, *, role,
                 on_retry=None, max_restarts=3):
        assert type(max_restarts) is int and 0 <= max_restarts <= 3
        self.factory = factory
        self.sampler = sampler
        self.close_iterator = close_iterator
        self.torch = torch
        self.role = role
        self.on_retry = on_retry
        self.max_restarts = max_restarts
        self.restarts = 0
        self.closed = False
        self.iterator = iter(factory())

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed:
            raise StopIteration
        while True:
            try:
                return next(self.iterator)
            except RuntimeError as exc:
                if type(exc) is not RuntimeError or not re.fullmatch(
                        r'DataLoader timed out after [0-9.]+ seconds', str(exc)):
                    raise
                committed = copy.deepcopy(self.sampler.state_dict())
                if self.restarts >= self.max_restarts:
                    raise LoaderRetryExhausted(
                        f'{self.role}: exhausted {self.max_restarts} loader restarts; '
                        'committed cursor retained') from exc
                started = time.monotonic()
                # This is the existing bounded cleanup of this iterator's children.
                self.close_iterator(self.iterator)
                self.iterator = None
                assert self.sampler.state_dict() == committed, 'LOADER_RETRY_CHANGED_COMMITTED_CURSOR'
                # Recreating workers must not advance the parent's scientific RNG.
                rng = self.torch.get_rng_state().clone()
                try:
                    self.iterator = iter(self.factory())
                finally:
                    self.torch.set_rng_state(rng)
                assert self.sampler.state_dict() == committed, 'LOADER_RETRY_CHANGED_COMMITTED_CURSOR'
                self.restarts += 1
                if self.on_retry:
                    self.on_retry({'status': 'LOADER_TIMEOUT_RESTART_FROM_COMMITTED_CURSOR',
                                   'role': self.role, 'restart': self.restarts,
                                   'max_restarts': self.max_restarts,
                                   'original_timeout_error': str(exc),
                                   'committed_sampler': committed,
                                   'restart_seconds': time.monotonic() - started})

    def close(self):
        if not self.closed:
            self.closed = True
            if self.iterator is not None:
                self.close_iterator(self.iterator)
                self.iterator = None
