"""Quota publication must survive measured clock lag without forged timestamps."""
import json
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.mark.parametrize('timeout', [False, True])
def test_delayed_atomic_publication_preserves_real_observation(tmp_path, timeout):
    output = tmp_path / 'quota.json'
    output.write_text('{"previous": true}')
    stop = tmp_path / 'stop'
    elapsed = 0.0
    sleeps = []
    observation = 1000.5

    def sleep(seconds):
        nonlocal elapsed
        sleeps.append(seconds)
        if len(sleeps) == 1:
            assert seconds == 2
            assert json.loads(output.read_text()) == {'previous': True}
            assert not output.with_suffix('.pending').exists()
        else:
            record = json.loads(output.read_text())
            assert record['observed_epoch'] == observation
            assert record['returncode'] == (-1 if timeout else 0)
            assert record['state'] == ('QUOTA_TIMEOUT' if timeout else 'RUNNING')
            assert record['generation'] == 'clock-lag-test'
            # A consumer clock lagging 0.82 seconds is now nonnegative;
            # its original 90-second limit remains intact.
            assert 0 <= observation - 0.82 + elapsed - record['observed_epoch'] <= 90
        elapsed += seconds

    result = SimpleNamespace(returncode=0, stdout='actual quota text', stderr='')
    argv = ['quota_publisher.py', '--output', str(output), '--stop', str(stop),
            '--generation', 'clock-lag-test', '--lifetime-seconds', '1']
    with patch.object(sys, 'argv', argv), \
            patch('time.monotonic', side_effect=[0, 0, 2]), \
            patch('time.time', return_value=observation), \
            patch('time.sleep', side_effect=sleep), \
            patch('subprocess.run', return_value=result) as native:
        if timeout:
            native.side_effect = subprocess.TimeoutExpired(['quota'], 25)
        runpy.run_path(str(Path(__file__).with_name('quota_publisher.py')),
                       run_name='__main__')
    assert sleeps == [2, 10]
    assert not output.with_suffix('.pending').exists()
