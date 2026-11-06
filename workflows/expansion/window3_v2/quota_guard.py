"""Native login-node account quota metadata for NFS compute writers.

Filesystem statvfs alone cannot express Main's user hard quota. No hashes,
receipts, data scans or scientific calls are made by this metadata publisher.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time


def parse_quota(text, username, uid, filesystem):
    header = re.search(r'Disk quotas for user\s+(\S+)\s+\(uid\s+(\d+)\)',text)
    if not header or header.group(1) != username or int(header.group(2)) != uid:
        raise ValueError('NATIVE_QUOTA_IDENTITY_DIFFERS')
    rows = [line.split() for line in text.splitlines() if line.split() and line.split()[0] == filesystem]
    if len(rows) != 1 or len(rows[0]) < 4:
        raise ValueError('NATIVE_QUOTA_FILESYSTEM_MISSING')
    used, hard = int(rows[0][1].rstrip('*')), int(rows[0][3].rstrip('*'))
    if used < 0 or hard <= 0:
        raise ValueError('FINITE_NATIVE_ACCOUNT_HARD_QUOTA_REQUIRED')
    return dict(used_bytes=used*1024,hard_limit_bytes=hard*1024,
                available_bytes=max(0,hard-used)*1024)


def inspect_quota(config, now=None):
    now = time.time() if now is None else now
    try:
        value=json.loads(Path(config['path']).read_text())
        age=now-value['observed_unix_seconds']
        if (value.get('status') != 'KNOWN' or value.get('uid') != config['uid']
                or not -5 <= age <= config['max_age_seconds']):
            raise ValueError('NATIVE_QUOTA_UNKNOWN_STALE_OR_WRONG_UID')
        free=int(value['available_bytes'])
        need=int(config['reserve_bytes'])+int(config['planned_bytes'])
        if free < 0 or need < 0: raise ValueError('NEGATIVE_QUOTA_CAPACITY')
        return dict(path=config['path'],available_bytes=free,required_bytes=need,
                    metadata_age_seconds=age,safe=free>=need,account_quota=True)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return dict(path=config['path'],safe=False,account_quota=True,unknown=str(exc))


def publish(config):
    if os.getuid() != config['uid']:
        raise RuntimeError('NATIVE_QUOTA_PUBLISHER_UID_DIFFERS')
    path=Path(config['output'])
    while not Path(config['stop_path']).exists():
        try:
            text=subprocess.check_output(['quota','-v','-u',config['username']],text=True,
                                         env=dict(os.environ,LC_ALL='C'))
            value=dict(parse_quota(text,config['username'],config['uid'],config['filesystem']),status='KNOWN')
        except (OSError,subprocess.CalledProcessError,ValueError) as exc:
            value=dict(status='UNKNOWN',error=str(exc))
        value.update(uid=os.getuid(),observed_unix_seconds=time.time())
        temporary=path.with_suffix('.pending')
        temporary.write_text(json.dumps(value)+'\n')
        os.replace(temporary,path)
        time.sleep(config.get('interval_seconds',5))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    publish(json.loads(Path(parser.parse_args().config).read_text()))
