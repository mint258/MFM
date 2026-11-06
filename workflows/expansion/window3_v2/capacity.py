"""Actual filesystem protection before new writes; no numerical QA."""
import json
import os
import signal

from .disk_guard import inspect_filesystem


def protect(config):
    checks = [inspect_filesystem(c) for c in config.get('disk_checks', [])]
    if any(not c['safe'] for c in checks):
        # The external job observer freezes the remaining owned job processes.
        # Stop this writer first, retaining its exact native/checkpoint state.
        print(json.dumps({'state': 'DISK_WRITE_PAUSED', 'filesystems': checks}), flush=True)
        os.kill(os.getpid(), signal.SIGSTOP)
        return protect(config)
