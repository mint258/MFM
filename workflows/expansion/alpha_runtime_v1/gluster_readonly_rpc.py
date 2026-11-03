"""Exact read-only Alpha Gluster CLI RPC for compute clients without that binary."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ALLOWED = ['--remote-host=sonmi1', '--log-file=/dev/null', 'volume', 'info', 'gv1']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt-root', required=True, type=Path)
    args, cli = parser.parse_known_args()
    if cli != ALLOWED or os.getuid() != 1264 or not sys.flags.isolated:
        raise ValueError('Only exact read-only volume-info RPC as actual Alpha is allowed')
    if not args.receipt_root.absolute().is_relative_to('/gfshome/alpha'):
        raise ValueError('Own Alpha metadata receipts required')
    args.receipt_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    argv = ['/usr/bin/ssh', '-n', '-oBatchMode=yes', '-oStrictHostKeyChecking=yes',
        'sonmi1', '/usr/sbin/gluster', *ALLOWED]
    began = time.time()
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=18)
    value = dict(schema='ACTUAL_ALPHA_READONLY_NATIVE_GLUSTER_RPC_V1', uid=os.getuid(),
        hostname=socket.gethostname(), boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        pid=os.getpid(), actual_argv=argv, returncode=result.returncode,
        started_consumer_node_unix_seconds=began, ended_consumer_node_unix_seconds=time.time(),
        stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(result.stderr).hexdigest(),
        actual_stdout=result.stdout.decode('utf-8'), actual_stderr=result.stderr.decode('utf-8'),
        only_native_volume_info_permitted=True, configuration_or_clock_changed=False)
    path=args.receipt_root/('rpc_%s_%s.json'%(time.time_ns(),os.getpid()))
    with path.open('x') as stream:
        json.dump(value,stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())