"""Real-process SSH cleanup boundaries; no model/data computations."""
from dataclasses import replace
import os
import sys
import time
from unittest import mock
import pytest
import exit_lifecycle as life

def scope_and_identity():
    identity=life.identity(os.getpid())
    return next(line for line in identity.cgroup.splitlines() if line.startswith("0::")),identity

def test_ssh_reaps_orphaned_grandchild():
    scope,identity=scope_and_identity()
    with mock.patch.dict(os.environ,{"P_CPU_SSH_EXECUTION_ID":"ssh:P_runtime_test"}):
        result=life.supervise([sys.executable,"-c",
            "import subprocess,sys;subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])"],
            end_epoch=time.time()+1810,scope=scope,grace_seconds=180,
            ssh_identity=identity,report=lambda event:None)
    assert result==0
    assert not life.children(os.getpid())

def test_ssh_rejects_changed_start_before_launch():
    scope,identity=scope_and_identity()
    with mock.patch.dict(os.environ,{"P_CPU_SSH_EXECUTION_ID":"ssh:P_runtime_test"}):
        with mock.patch("subprocess.Popen") as launch:
            with pytest.raises(RuntimeError,match="Actual SSH supervisor"):
                life.supervise([sys.executable,"-c","pass"],
                    end_epoch=time.time()+1810,scope=scope,grace_seconds=180,
                    ssh_identity=replace(identity,start_ticks=identity.start_ticks+1))
            launch.assert_not_called()

def test_ssh_cleanup_window_reports_not_complete():
    scope,identity=scope_and_identity()
    with mock.patch.dict(os.environ,{"P_CPU_SSH_EXECUTION_ID":"ssh:P_runtime_test"}):
        result=life.supervise([sys.executable,"-c","import time;time.sleep(60)"],
            end_epoch=time.time()+180.2,scope=scope,grace_seconds=180,
            ssh_identity=identity,report=lambda event:None)
    assert result==75
    assert not life.children(os.getpid())

def test_ssh_environment_does_not_bypass_default_slurm_path():
    scope,identity=scope_and_identity()
    with mock.patch.dict(os.environ,{"P_CPU_SSH_EXECUTION_ID":"ssh:P_runtime_test"}):
        with pytest.raises(RuntimeError,match="current allocation"):
            life.supervise([sys.executable,"-c","pass"],
                end_epoch=time.time()+1810,scope=scope,grace_seconds=180)
