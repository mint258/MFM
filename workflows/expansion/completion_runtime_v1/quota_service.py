"""Publish unchanged quota evidence with observable delivery latency on Lustre."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import time
from . import quota as share
from . import lustre_quota as lustre


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=['share', 'lustre'], required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path, required=True)
    args = parser.parse_args()
    share.require(os.getuid() == 1278 and socket.gethostname() == 'sonmi',
                  'Actual Main metadata publisher only')
    output = args.snapshot.absolute()
    root = Path('/lfshome/zixiao/pubchem_completion_20261103').resolve()
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    share.require(output.parent.resolve().is_relative_to(root), 'Independent Lustre control required')
    backend = share if args.backend == 'share' else lustre
    filesystem = '/dev/sda1' if args.backend == 'share' else '/lfshome/zixiao'
    identity = backend.publisher_identity()
    source = Path(__file__).resolve()
    identity['backend_source_reference'] = dict(path=identity['source_path'],
                                               sha256=identity['source_sha256'])
    identity['source_path'] = str(source)
    identity['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    share.atomic_snapshot(output.parent / (args.backend + '_publisher.json'), identity)
    while not args.stop_file.exists():
        started = time.monotonic()
        try:
            value = backend.capture(filesystem, '202.38.247.57:22', identity)
            captured = time.monotonic()
            # Timestamps stay actual. Brief delivery spacing avoids assuming
            # perfectly simultaneous wall clocks on separate hosts.
            time.sleep(.25)
            backend.atomic_snapshot(output, value)
            finished = time.monotonic()
            print(json.dumps(dict(event='ACTUAL_QUOTA_SNAPSHOT_PUBLISHED', backend=args.backend,
                generated_unix_seconds=value['generated_unix_seconds'],
                publication_completed_unix_seconds=time.time(),
                capture_elapsed_seconds=captured-started,
                delivery_elapsed_seconds=finished-captured,
                total_elapsed_seconds=finished-started)), flush=True)
        except Exception as error:
            print(json.dumps(dict(event='QUOTA_PUBLICATION_FAILED_NO_EMPTY_SUCCESS',
                backend=args.backend, error=repr(error), observed_unix_seconds=time.time(),
                elapsed_seconds=time.monotonic()-started)), flush=True)
        time.sleep(30)


if __name__ == '__main__':
    main()
