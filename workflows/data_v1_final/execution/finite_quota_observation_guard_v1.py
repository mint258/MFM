"""Bounded reread of one near-clock quota observation; no provider mutation.

Callers explicitly pin this SOURCE and persist ``record`` events as small resource
evidence. The original Client and its validator remain the sole admission path.
"""
import copy
import hashlib
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

SOURCE_RELATIVE_PATH = 'workflows/data_v1_final/execution/finite_quota_observation_guard_v1.py'
TIME_ERROR = 'STALE_FUTURE_OR_EXPIRED_ACCOUNT_QUOTA_PROVIDER'
MAX_NEAR_SECONDS = 1.0
MAX_WAIT_SECONDS = 1.1


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _reference(value):
    _need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}
          and type(value['path']) is str and PurePosixPath(value['path']).is_absolute()
          and '..' not in PurePosixPath(value['path']).parts
          and type(value['bytes']) is int and value['bytes'] > 0
          and type(value['sha256']) is str
          and re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None,
          'EXACT_EXPECTED_FINITE_PROVIDER_IDENTITY_REFERENCE_REQUIRED')
    return value


def _expected(client, expected):
    last = getattr(client, 'last', None)
    return (type(last) is dict and last.get('identity_reference') == expected
            and getattr(client, 'identity', None) in (None, expected))


def observe(client, *, expected_identity_reference, record,
            wall_clock=time.time, monotonic=time.monotonic, wait=time.sleep):
    """Original observation, plus at most one <=1.1s metadata-only reread.

    ``record`` is required and must persist each supplied event. Its failure is
    fail-closed. Injectable clocks/client are for existing synthetic boundaries;
    production callers omit them. No snapshot is returned without original
    Client.observe succeeding, with the exact expected identity still pinned.
    """
    expected = copy.deepcopy(_reference(expected_identity_reference))
    _need(callable(record), 'PERSISTENT_RESOURCE_EVENT_RECORDER_REQUIRED')
    try:
        result = client.observe()
    except ValueError as first:
        if str(first) != TIME_ERROR:
            raise
        now = wall_clock()
        began = monotonic()
        last = copy.deepcopy(getattr(client, 'last', None))
        sampled = last.get('observed_unix_seconds') if type(last) is dict else None
        expires = last.get('publisher_expires_unix_seconds') if type(last) is dict else None
        eligible = (_number(now) and _number(began) and _number(sampled)
                    and _number(expires) and expires > now
                    and _expected(client, expected)
                    and last.get('provider_status') == 'RUNNING'
                    and abs(sampled - now) <= MAX_NEAR_SECONDS)
        event = {'schema': 'FINITE_QUOTA_NEAR_CLOCK_REREAD_EVENT_V1',
                 'phase': 'FIRST_ORIGINAL_VALIDATOR_REJECTION',
                 'expected_identity_reference': expected,
                 'first_original_error': repr(first), 'first_actual_observation': last,
                 'actual_wall_seconds': now, 'actual_monotonic_seconds': began,
                 'eligible_for_one_original_client_reread': eligible,
                 'maximum_wait_seconds': MAX_WAIT_SECONDS,
                 'original_age_0_to120_and_expiry_guards_changed': False,
                 'native_retry_or_provider_identity_switch': False}
        record(event)
        if not eligible:
            raise
        after_record = wall_clock()
        remaining = MAX_WAIT_SECONDS - (monotonic() - began)
        if not _number(after_record) or remaining < 0:
            record(dict(event, phase='NO_REREAD_WAIT_BOUND_OR_CLOCK_UNAVAILABLE'))
            raise
        requested_wait = max(0.0, sampled - after_record)
        if requested_wait > remaining:
            record(dict(event, phase='NO_REREAD_WAIT_WOULD_EXCEED_BOUND',
                        requested_wait_seconds=requested_wait))
            raise
        if requested_wait:
            wait(requested_wait)
        before_second = wall_clock()
        elapsed = monotonic() - began
        if (not _number(before_second) or not _number(elapsed)
                or not 0 <= elapsed <= MAX_WAIT_SECONDS
                or before_second < sampled or before_second >= expires):
            record(dict(event, phase='NO_REREAD_AFTER_WAIT_GUARD',
                        requested_wait_seconds=requested_wait,
                        actual_elapsed_seconds=elapsed,
                        actual_wall_before_second=before_second))
            raise
        try:
            result = client.observe()
            _need(_expected(client, expected), 'EXPECTED_PROVIDER_IDENTITY_CHANGED_AFTER_REREAD')
        except Exception as second:
            record(dict(event, phase='SECOND_ORIGINAL_CLIENT_FAILED_STOP',
                        requested_wait_seconds=requested_wait,
                        actual_elapsed_seconds=elapsed,
                        actual_wall_before_second=before_second,
                        second_error=repr(second),
                        second_actual_observation=copy.deepcopy(getattr(client, 'last', None))))
            raise
        record(dict(event, phase='SECOND_ORIGINAL_CLIENT_ACCEPTED',
                    requested_wait_seconds=requested_wait,
                    actual_elapsed_seconds=elapsed,
                    actual_wall_before_second=before_second,
                    second_actual_observation=copy.deepcopy(getattr(client, 'last', None))))
        return result
    _need(_expected(client, expected), 'EXPECTED_PROVIDER_IDENTITY_CHANGED_AFTER_OBSERVATION')
    return result


def source_reference():
    """Main SOURCE-only pin entry; never reads a provider or scientific body."""
    path = Path(__file__).absolute()
    _need(not any(p.is_symlink() for p in (path, *path.parents)), 'GUARD_SOURCE_NO_SYMLINK')
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        _need(stat.S_ISREG(before.st_mode) and before.st_uid == 1278
              and before.st_nlink == 1 and 0 < before.st_size <= 128 << 10,
              'EXACT_MAIN_SMALL_GUARD_SOURCE')
        raw = stream.read((128 << 10) + 1)
        after = os.fstat(stream.fileno())
    frame = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    _need(frame(before) == frame(after) == frame(path.lstat())
          and len(raw) == before.st_size, 'GUARD_SOURCE_CURRENT_FD_CHANGED')
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
