"""Root login metadata publisher: actual quota plus pre-quota own-output credit."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import uuid
from .support import allocated_bytes, canonical, load, need, quota_available


def publish(plan, target):
    need(os.getuid() == 1278 and socket.gethostname() == 'sonmi', 'Actual Main login user/host required for quota metadata')
    # Measuring the task's existing output BEFORE quota avoids crediting bytes
    # newly written after the quota sample. It does not free/retire any output.
    credit = allocated_bytes(plan['output_directory'])
    q = subprocess.run(['quota', '-v', '-u', 'zixiao'], capture_output=True, text=True, check=False)
    result = {'schema': 'PUBCHEM_RECONSTRUCTION_QUOTA_FEED_V1', 'status': 'UNAVAILABLE', 'uid': os.getuid(), 'username': 'zixiao', 'endpoint': '202.38.247.57:22', 'hostname': socket.gethostname(), 'pid': os.getpid(), 'observed_unix_seconds': time.time(), 'output_directory': plan['output_directory'], 'scientific_scope_sha256': plan['scientific_scope_sha256'], 'output_allocated_bytes_measured_before_quota': credit, 'query_argv': ['quota', '-v', '-u', 'zixiao'], 'returncode': q.returncode, 'raw_stdout': q.stdout, 'raw_stderr': q.stderr, 'raw_stdout_sha256': hashlib.sha256(q.stdout.encode()).hexdigest()}
    if q.returncode == 0:
        try:
            result['available_bytes'] = quota_available(q.stdout, plan['quota_device'])
            result['status'] = 'AVAILABLE'
        except BaseException as exc:
            result['error'] = repr(exc)
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending.' + uuid.uuid4().hex)
    with pending.open('xb') as stream:
        stream.write(canonical(result) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--interval', type=float, default=30)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    need(args.interval > 0, 'Positive observation interval required')
    plan = load(args.plan)
    while True:
        result = publish(plan, args.output)
        if args.once:
            print(canonical(result).decode())
            break
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
