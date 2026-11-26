"""New F worker wiring only: real own child, exact mount and cooperative boundary."""
import os
import signal
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from finetune_entry import (CooperativeStop, validate_output_filesystem,
                            native_query, set_actual_deadline)
import exit_lifecycle


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGUSR1])
def test_worker_defers_stop_to_its_safe_boundary_and_restores_handler(sig):
    before = signal.getsignal(sig)
    with CooperativeStop() as stop:
        assert not stop.requested
        signal.raise_signal(sig)
        assert stop.requested
    assert signal.getsignal(sig) == before


def test_actual_output_ancestor_must_match_the_registered_mount():
    devices = {"/lfshome":11, "/lfshome/zixiao/F":11,
               "/share":1, "/share/home/zixiao/P":22}
    def stat(path):
        key = str(path)
        if key not in devices:
            raise FileNotFoundError(key)
        return SimpleNamespace(st_dev=devices[key])
    assert validate_output_filesystem("/lfshome/zixiao/F/new/run","/lfshome",stat) == Path("/lfshome/zixiao/F")
    with pytest.raises(ValueError,match="actual output"):
        validate_output_filesystem("/share/home/zixiao/P/newrun","/share",stat)
    with pytest.raises(ValueError,match="canonical"):
        validate_output_filesystem("/share/home/zixiao/P/newrun","/share/home",stat)


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"),reason="Requires a real native CPU allocation")
def test_native_query_reaps_its_real_child_without_custom_cgroup_scanning():
    before = exit_lifecycle.children(os.getpid())
    result = native_query(["/usr/bin/python3","-I","-S","-B","-c","print('native-fixture')"],
                          SimpleNamespace(requested=False))
    assert result.strip()=="native-fixture"
    assert exit_lifecycle.children(os.getpid()) == before


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"),reason="Requires a real native CPU allocation")
def test_deadline_comes_from_the_actual_job_and_reserves_cleanup(monkeypatch):
    keys=("P_MANAGED_HARD_END","P_MANAGED_STOP_NEW_UNITS_AT","P_MANAGED_UNIT_SECONDS")
    for key in keys:
        monkeypatch.setenv(key,os.environ.get(key,""))
    set_actual_deadline({"cleanup_seconds":180,"work_unit_seconds":1},
                        SimpleNamespace(requested=False))
    hard=float(os.environ["P_MANAGED_HARD_END"])
    cutoff=float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])
    assert hard-cutoff==180 and cutoff>time.time()
    assert float(os.environ["P_MANAGED_UNIT_SECONDS"])==1